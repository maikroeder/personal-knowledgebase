#!/bin/bash
# Copies the keys from ~/.kiwi-tokens/<name>.txt into the macOS Keychain as item kiwifs-<name>.
# The script holds no key; it prints item names only. -U updates an existing item.
T=$HOME/.kiwi-tokens
for name in moin-read events-write kiwi-write admin-kiwi admin-moin admin-events; do
  if [ ! -f "$T/$name.txt" ]; then
    echo "missing: $T/$name.txt"
    continue
  fi
  KEY="$(awk '/^[[:space:]]*Key:/ {print $2; exit}' "$T/$name.txt")"
  if [ -z "$KEY" ]; then
    echo "no key found in $name.txt"
    continue
  fi
  security add-generic-password -U -a "$USER" -s "kiwifs-$name" -w "$KEY"
  if [ $? -eq 0 ]; then
    echo "stored: kiwifs-$name"
  else
    echo "FAILED: kiwifs-$name"
  fi
done
