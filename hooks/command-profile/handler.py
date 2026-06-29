"""
Hook handler for command:profile events.

Extends the built-in /profile command with:
  /profile           – show current profile and list available profiles
  /profile use <n>   – switch to profile <name> (restarts gateway)
  /profile list      – list all available profiles
  /profile help      – show usage help

Handler signature: handle(event_type: str, context: dict) -> dict | None
"""
import asyncio
import os
import signal
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------------------------------------------------------
# Helpers (TLV-style: keep deps minimal — pure stdlib + optional yaml)
# ---------------------------------------------------------------------------

def _get_default_hermes_home() -> Path:
    """Return the root Hermes directory (always ~/.hermes on POSIX)."""
    native = Path.home() / ".hermes"
    env = os.environ.get("HERMES_HOME", "")
    if env:
        p = Path(env)
        # If HERMES_HOME points inside profiles/, strip back to root
        # so active_profile reads are always from the one true location.
        try:
            rel = p.relative_to(native / "profiles")
            if len(rel.parts) >= 1:
                return native
        except (ValueError, AttributeError):
            pass
        return native
    return native


def _get_profiles_root() -> Path:
    """Return ~/.hermes/profiles/ (anchored to default HOMES, not current profile)."""
    return _get_default_hermes_home() / "profiles"


def _get_active_profile_path() -> Path:
    """Return the path to the global active_profile file."""
    return _get_default_hermes_home() / "active_profile"


def _read_profiles() -> dict:
    """Return an ordered dict of {name: description} for every profile.

    The ``default`` profile always appears first.  Named profiles are
    discovered from ``~/.hermes/profiles/<name>/``.
    """
    profiles: dict = {"default": "Default Hermes profile"}
    root = _get_profiles_root()
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if d.is_dir():
                desc = f"Hermes profile at {d.name}"
                profile_yaml = d / "profile.yaml"
                if profile_yaml.exists() and yaml is not None:
                    try:
                        meta = yaml.safe_load(profile_yaml.read_text(encoding="utf-8"))
                        if isinstance(meta, dict) and "description" in meta:
                            desc = str(meta["description"])
                    except Exception:
                        pass
                profiles[d.name] = desc
    return profiles


def _get_active_profile() -> str:
    """Read the sticky active profile name; returns 'default' if unset."""
    path = _get_active_profile_path()
    try:
        name = path.read_text().strip()
        return name if name else "default"
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return "default"


def _set_active_profile(name: str) -> None:
    """Persist *name* as the sticky active profile.

    Pass ``"default"`` to clear the override (resets to the default profile).
    """
    canon = name.strip().lower()
    path = _get_active_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if canon == "default":
        path.unlink(missing_ok=True)
    else:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(canon + "\n")
        tmp.replace(path)


def _profile_exists(name: str) -> bool:
    """Return True when *name* refers to an existing profile directory."""
    canon = name.strip().lower()
    if canon == "default":
        return True
    profiles_root = _get_profiles_root()
    return (profiles_root / canon).is_dir()


# ---------------------------------------------------------------------------
# Scheduled restart
# ---------------------------------------------------------------------------

def _schedule_restart() -> str:
    """Schedule a graceful gateway restart via SIGUSR1 after a short delay.

    Returns a user-facing blurb about what's happening.
    """
    if not hasattr(signal, "SIGUSR1"):
        return " Restart the gateway for the change to take effect."

    sig = signal.SIGUSR1

    async def _delayed_kill():
        await asyncio.sleep(0.5)  # let the response be sent first
        try:
            os.kill(os.getpid(), sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass  # gateway already stopped — no-op

    try:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(_delayed_kill(), loop=loop)
        return " Gateway restarting now..."
    except RuntimeError:
        return " Restart the gateway for the change to take effect."


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _respond(message: str) -> dict:
    return {"decision": "handled", "message": message}


def _cmd_show() -> dict:
    """Show current profile and list available profiles."""
    active = _get_active_profile()
    profiles = _read_profiles()

    lines = [
        f"Current profile: {active}",
        "",
        "Available profiles:",
    ]
    for name, desc in profiles.items():
        marker = "  ← current" if name == active else ""
        lines.append(f"  • {name}  ({desc}){marker}")
    lines.extend([
        "",
        "Usage: /profile use <name>",
        "Tip: Switching profiles will restart the gateway.",
    ])
    return _respond("\n".join(lines))


def _cmd_list() -> dict:
    """List all available profiles."""
    active = _get_active_profile()
    profiles = _read_profiles()

    lines = ["Available profiles:"]
    for name, desc in profiles.items():
        marker = "  ← current" if name == active else ""
        lines.append(f"  • {name}{marker}")
    return _respond("\n".join(lines))


def _cmd_use(args: str) -> dict:
    """Switch to a named profile."""
    target = args.strip()
    if not target:
        return _respond(
            "Usage: /profile use <profile-name>.  "
            "See /profile list for available profiles."
        )

    if not _profile_exists(target):
        profiles = _read_profiles()
        available = ", ".join(profiles.keys())
        return _respond(
            f"Profile '{target}' not found. Available profiles: {available}"
        )

    canon = target.strip().lower()
    _set_active_profile(canon)
    restart_msg = _schedule_restart()
    return _respond(f"Switched to profile '{canon}'.{restart_msg}")


def _cmd_help() -> dict:
    """Show usage."""
    return _respond(
        "Usage:\n"
        "  /profile           – Show current profile and list available ones\n"
        "  /profile list      – List all available profiles\n"
        "  /profile use <n>   – Switch to profile <name> (restarts gateway)\n"
        "  /profile help      – Show this help"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def handle(event_type: str, context: dict) -> dict | None:
    """Handle command:profile events.

    The context dict contains:
      platform, user_id, command, raw_command, args, raw_args

    Returns:
      ``{"decision": "handled", "message": "..."}`` when we recognise a
      subcommand, or ``None`` to let the built-in /profile handler run.
    """
    raw_args: str = (context.get("raw_args") or "").strip()

    # No args → let the built-in /profile run as-is for its display,
    # but ALSO show the extended info below.
    # Actually, we always "handled" so we can show the enhanced output.
    # The built-in handler only shows the profile name and home path,
    # which is less useful than listing profiles too.
    parts = raw_args.split(maxsplit=1) if raw_args else []
    subcommand = parts[0].lower() if parts else None
    sub_args = parts[1] if len(parts) > 1 else ""

    if subcommand is None or subcommand == "show":
        return _cmd_show()
    if subcommand == "list":
        return _cmd_list()
    if subcommand in ("use", "switch", "set"):
        return _cmd_use(sub_args)
    if subcommand in ("help", "--help", "-h"):
        return _cmd_help()

    return _respond(
        f"Unknown subcommand: '{subcommand}'.  Use /profile help for usage."
    )