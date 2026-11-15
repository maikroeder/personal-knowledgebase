#!/bin/bash
# Read-only checks against a running multi-space kiwifs on 127.0.0.1:3333
B=http://127.0.0.1:3333/api/kiwi
for sp in moin Events; do
  curl -s -o /dev/null -w "$sp tree: %{http_code}\n" "$B/$sp/tree"
done
curl -s -o /dev/null -w "default tree: %{http_code}\n" "$B/tree"
echo "--- Events tree (first 500 chars)"
curl -s "$B/Events/tree" | head -c 500; echo
echo "--- Events search: meetup"
curl -s "$B/Events/search?q=meetup" | head -c 500; echo
echo "--- moin search: buildout (first 200 chars)"
curl -s "$B/moin/search?q=buildout" | head -c 200; echo
echo "--- default search: MoinMoin"
curl -s "$B/search?q=MoinMoin" | head -c 300; echo
echo "--- done"
