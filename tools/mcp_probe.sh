#!/bin/bash
# Read-only: collects help texts and probes /mcp routes; writes everything to mcp-probe.txt next to this script
OUT="$(dirname "$0")/mcp-probe.txt"
{
  echo "=== kiwifs --version"; kiwifs --version 2>&1 | grep -v 'is available' | head -3
  echo "=== kiwifs mcp --help"; kiwifs mcp --help 2>&1 | grep -v 'is available'
  echo "=== kiwifs token --help"; kiwifs token --help 2>&1 | grep -v 'is available'
  echo "=== kiwifs token create --help"; kiwifs token create --help 2>&1 | grep -v 'is available'
  echo "=== kiwifs serve --help (full)"; kiwifs serve --help 2>&1 | grep -v 'is available'
  echo "=== probe: POST /mcp on default, moin, Events (initialize)"
  for p in /mcp /api/kiwi/moin/mcp /api/kiwi/Events/mcp /api/kiwi/mcp; do
    printf "%s -> " "$p"
    curl -s -o /dev/null -w "%{http_code}\n" -X POST -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
      -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' "http://127.0.0.1:3333$p"
  done
  echo "=== initialize response on /mcp (first 600 chars)"
  curl -s -X POST -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' http://127.0.0.1:3333/mcp | head -c 600; echo
  echo "=== existing claude mcp registrations"; claude mcp list 2>&1 | sed 's/\(Bearer\) [^ ]*/\1 ***/' | head -20
} > "$OUT" 2>&1
echo "written: $OUT ($(wc -l < "$OUT") lines)"
