#!/bin/bash
# MCP stdio proxy for one KiwiFS space; the key comes from the macOS Keychain.
# usage: kiwi-mcp.sh <space> <keychain item>
# The key is passed with --api-key, so it is visible in `ps` to your own user while the proxy runs.
SPACE="$1"
ITEM="$2"
if [ -z "$SPACE" ] || [ -z "$ITEM" ]; then
  echo "usage: kiwi-mcp.sh <space> <keychain item>" >&2
  exit 2
fi
KEY="$(security find-generic-password -a "$USER" -s "$ITEM" -w 2>/dev/null)"
if [ -z "$KEY" ]; then
  echo "kiwi-mcp.sh: no key in the Keychain for item $ITEM" >&2
  exit 1
fi
exec /opt/homebrew/bin/kiwifs mcp --remote http://127.0.0.1:3333 --space "$SPACE" --api-key "$KEY"
