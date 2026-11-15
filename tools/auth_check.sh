#!/bin/bash
# Auth matrix against a running multi-space kiwifs (layout B: hub root plus spaces kiwi, moin, Events).
# Reads keys from ~/.kiwi-tokens/*.txt, prints only HTTP status codes, never keys.
B=http://127.0.0.1:3333/api/kiwi
T=$HOME/.kiwi-tokens
OUT="$(dirname "$0")/auth_check.txt"

key() {
  awk '/^[[:space:]]*Key:/ {print $2; exit}' "$T/$1.txt"
}

code() {
  if [ "$1" = none ]; then
    curl -s -o /dev/null -w "%{http_code}" "$2"
  else
    printf 'Authorization: Bearer %s\n' "$(key "$1")" | curl -s -o /dev/null -w "%{http_code}" -H @- "$2"
  fi
}

row() {
  # row <token> : tree status on hub, kiwi, moin, Events
  echo "hub $(code "$1" $B/tree) | kiwi $(code "$1" $B/kiwi/tree) | moin $(code "$1" $B/moin/tree) | Events $(code "$1" $B/Events/tree)"
}

{
  echo "== no token (hub | kiwi | moin | Events)"
  row none
  echo "/mcp: $(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' http://127.0.0.1:3333/mcp)"
  for name in moin-read events-write kiwi-write admin-kiwi admin-moin admin-events; do
    echo "== $name"
    row $name
  done
  echo "== moin-read search"
  echo "moin search: $(code moin-read "$B/moin/search?q=buildout")"
  echo "== wrong token"
  printf 'Authorization: Bearer kiwi_ro_0000000000000000\n' | curl -s -o /dev/null -w 'moin tree: %{http_code}\n' -H @- $B/moin/tree
} > "$OUT" 2>&1
echo "written: $OUT"
