#!/bin/bash
# Auth matrix against a running multi-space kiwifs with --auth perspace.
# Reads keys from ~/.kiwi-tokens/*.txt, prints only HTTP status codes, never keys.
B=http://127.0.0.1:3333/api/kiwi
T=$HOME/.kiwi-tokens
OUT="$(dirname "$0")/auth_check.txt"

key() {
  awk '/^[[:space:]]*Key:/ {print $2; exit}' "$T/$1.txt"
}

code() {
  # code <tokenfile-or-none> <url>
  if [ "$1" = none ]; then
    curl -s -o /dev/null -w "%{http_code}" "$2"
  else
    printf 'Authorization: Bearer %s\n' "$(key "$1")" | curl -s -o /dev/null -w "%{http_code}" -H @- "$2"
  fi
}

{
  echo "== no token"
  echo "default tree: $(code none $B/tree)"
  echo "moin tree:    $(code none $B/moin/tree)"
  echo "Events tree:  $(code none $B/Events/tree)"
  echo "/mcp:         $(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' http://127.0.0.1:3333/mcp)"
  echo "== moin-read (moin/read)"
  echo "moin tree:    $(code moin-read $B/moin/tree)"
  echo "moin search:  $(code moin-read "$B/moin/search?q=buildout")"
  echo "Events tree:  $(code moin-read $B/Events/tree)"
  echo "default tree: $(code moin-read $B/tree)"
  echo "== events-write (Events/write)"
  echo "Events tree:  $(code events-write $B/Events/tree)"
  echo "moin tree:    $(code events-write $B/moin/tree)"
  echo "default tree: $(code events-write $B/tree)"
  echo "== default-write (default/write)"
  echo "default tree: $(code default-write $B/tree)"
  echo "moin tree:    $(code default-write $B/moin/tree)"
  echo "== admin-default (default/admin)"
  echo "default tree: $(code admin-default $B/tree)"
  echo "moin tree:    $(code admin-default $B/moin/tree)"
  echo "== admin-moin (moin/admin)"
  echo "moin tree:    $(code admin-moin $B/moin/tree)"
  echo "Events tree:  $(code admin-moin $B/Events/tree)"
  echo "== admin-events (Events/admin)"
  echo "Events tree:  $(code admin-events $B/Events/tree)"
  echo "default tree: $(code admin-events $B/tree)"
  echo "== wrong token"
  echo "moin tree:    $(printf 'Authorization: Bearer kiwi_ro_0000000000000000\n' | curl -s -o /dev/null -w '%{http_code}' -H @- $B/moin/tree)"
} > "$OUT" 2>&1
echo "written: $OUT"
