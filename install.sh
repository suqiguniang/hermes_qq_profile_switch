#!/usr/bin/env bash
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Hermes QQ Profile Switch..."
echo "Target: $HERMES_HOME"
echo ""

# 1. Install hook
echo "[1/3] Installing hook (command:profile)..."
mkdir -p "$HERMES_HOME/hooks/command-profile"
cp "$SCRIPT_DIR/hooks/command-profile/HOOK.yaml" "$HERMES_HOME/hooks/command-profile/"
cp "$SCRIPT_DIR/hooks/command-profile/handler.py" "$HERMES_HOME/hooks/command-profile/"
echo "  -> $HERMES_HOME/hooks/command-profile/"

# 2. Install plugin
echo "[2/3] Installing plugin (profile-switch)..."
mkdir -p "$HERMES_HOME/plugins/qqbot-profile-switch"
cp "$SCRIPT_DIR/plugins/qqbot-profile-switch/plugin.yaml" "$HERMES_HOME/plugins/qqbot-profile-switch/"
cp "$SCRIPT_DIR/plugins/qqbot-profile-switch/__init__.py" "$HERMES_HOME/plugins/qqbot-profile-switch/"
echo "  -> $HERMES_HOME/plugins/qqbot-profile-switch/"

# 3. Enable plugin in config
echo "[3/3] Enabling plugin in config.yaml..."
CONFIG="$HERMES_HOME/config.yaml"
if [ -f "$CONFIG" ]; then
    # Check if already enabled
    if grep -q "qqbot-profile-switch" "$CONFIG" 2>/dev/null; then
        echo "  -> Already enabled, skipping."
    else
        # Use Python to safely edit YAML
        python3 -c "
import yaml
with open('$CONFIG') as f:
    data = yaml.safe_load(f)
enabled = data.setdefault('plugins', {}).setdefault('enabled', [])
if 'qqbot-profile-switch' not in enabled:
    enabled.append('qqbot-profile-switch')
with open('$CONFIG', 'w') as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
print('  -> Added to plugins.enabled')
" || echo "  ⚠  Could not auto-enable. Add 'qqbot-profile-switch' to plugins.enabled manually."
    fi
else
    echo "  ⚠  $CONFIG not found. Plugin files installed but not enabled."
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Restart your Hermes gateway:  hermes gateway restart"
echo "  2. In QQ, try: /profile"
echo ""