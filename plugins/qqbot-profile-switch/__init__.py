"""
Plugin: qqbot-profile-switch

Registers /profile-switch as a slash command for listing and switching
Hermes profiles in QQ Bot and other text-based chat channels.

Handlers:
  - raw_args = ""            → show current profile + list available
  - raw_args = "use <name>"  → switch to profile <name>
  - raw_args = "list"        → list all profiles
  - raw_args = "help"        → show usage
"""
import asyncio
import os
import signal
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

__all__ = ["register"]


# ---------------------------------------------------------------------------
# Profile helpers  (stdlib + optional yaml, no hermes-agent imports needed)
# ---------------------------------------------------------------------------

def _default_hermes_home() -> Path:
    """Return the root Hermes directory (always ~/.hermes on POSIX)."""
    native = Path.home() / ".hermes"
    env = os.environ.get("HERMES_HOME", "")
    if env:
        p = Path(env)
        try:
            rel = p.relative_to(native / "profiles")
            if len(rel.parts) >= 1:
                return native
        except (ValueError, AttributeError):
            pass
        return native
    return native


def _profiles_root() -> Path:
    return _default_hermes_home() / "profiles"


def _active_profile_path() -> Path:
    return _default_hermes_home() / "active_profile"


def _read_profiles() -> dict:
    profiles: dict = {"default": "Default Hermes profile"}
    root = _profiles_root()
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if d.is_dir():
                desc = f"Hermes profile at {d.name}"
                meta_path = d / "profile.yaml"
                if meta_path.exists() and yaml is not None:
                    try:
                        meta = yaml.safe_load(
                            meta_path.read_text(encoding="utf-8")
                        )
                        if isinstance(meta, dict) and "description" in meta:
                            desc = str(meta["description"])
                    except Exception:
                        pass
                profiles[d.name] = desc
    return profiles


def _get_active() -> str:
    path = _active_profile_path()
    try:
        name = path.read_text().strip()
        return name if name else "default"
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return "default"


def _set_active(name: str) -> None:
    canon = name.strip().lower()
    path = _active_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if canon == "default":
        path.unlink(missing_ok=True)
    else:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(canon + "\n")
        tmp.replace(path)


def _profile_exists(name: str) -> bool:
    canon = name.strip().lower()
    if canon == "default":
        return True
    return (_profiles_root() / canon).is_dir()


# ---------------------------------------------------------------------------
# Restart  (SIGUSR1 → graceful gateway restart)
# ---------------------------------------------------------------------------

def _schedule_restart() -> str:
    if not hasattr(signal, "SIGUSR1"):
        return " Restart the gateway for the change to take effect."

    sig = signal.SIGUSR1

    async def _kill_later():
        await asyncio.sleep(0.5)
        try:
            os.kill(os.getpid(), sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    try:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(_kill_later(), loop=loop)
        return " Gateway restarting now..."
    except RuntimeError:
        return " Restart the gateway for the change to take effect."


# ---------------------------------------------------------------------------
# Command handler  (raw_args: str → str | None)
# ---------------------------------------------------------------------------

async def _handle_profile_switch(raw_args: str) -> str:
    parts = raw_args.strip().split(maxsplit=1) if raw_args.strip() else []
    sub = parts[0].lower() if parts else None
    sub_args = parts[1] if len(parts) > 1 else ""

    # No args – show
    if sub is None or sub in ("show", "status"):
        return _format_show()

    if sub == "list":
        return _format_list()

    if sub in ("use", "switch", "set"):
        return _format_use(sub_args)

    if sub in ("help", "--help", "-h"):
        return _format_help()

    return (
        f"Unknown subcommand: '{sub}'.  "
        f"Use /profile-switch help for usage."
    )


def _format_show() -> str:
    active = _get_active()
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
        "Usage: /profile-switch use <name>",
        "Tip: Switching profiles will restart the gateway.",
    ])
    return "\n".join(lines)


def _format_list() -> str:
    active = _get_active()
    profiles = _read_profiles()
    lines = ["Available profiles:"]
    for name in profiles:
        marker = "  ← current" if name == active else ""
        lines.append(f"  • {name}{marker}")
    return "\n".join(lines)


def _format_use(args: str) -> str:
    target = args.strip()
    if not target:
        return (
            "Usage: /profile-switch use <profile-name>.  "
            "See /profile-switch list for available profiles."
        )
    if not _profile_exists(target):
        available = ", ".join(_read_profiles().keys())
        return (
            f"Profile '{target}' not found. "
            f"Available profiles: {available}"
        )
    canon = target.strip().lower()
    _set_active(canon)
    restart_msg = _schedule_restart()
    return f"Switched to profile '{canon}'.{restart_msg}"


def _format_help() -> str:
    return (
        "Usage:\n"
        "  /profile-switch         – Show current profile and list available\n"
        "  /profile-switch list    – List all available profiles\n"
        "  /profile-switch use <n> – Switch to profile <name>\n"
        "  /profile-switch help    – Show this help"
    )


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register the /profile-switch command."""
    ctx.register_command(
        name="profile-switch",
        handler=_handle_profile_switch,
        description="List and switch Hermes profiles",
        args_hint="[list|use <name>|help]",
    )