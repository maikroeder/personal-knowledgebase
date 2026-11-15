#!/usr/bin/env python3
"""MCP write round trip in the Events space ONLY (stdio proxy mode, server must be running).
1. write a valid test event page with actor "claude-test"
2. read it back
3. try to write an invalid page (unclosed code fence, no title) to see whether lint-on-write rejects it
4. delete both test pages again
Writes the result to mcp-writetest.txt next to this script. Leaves a few commits in the Events git history."""
import json
import os
import select
import subprocess
import time

KIWIFS = '/opt/homebrew/bin/kiwifs'
URL = 'http://127.0.0.1:3333'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp-writetest.txt')
EVENTS = os.path.expanduser('~/Knowledge/events')
lines = []

VALID = """---
title: "MCP TEST event"
event_kind: event
publish_state: published
tier: members
start_utc: "2026-12-30T09:00:00Z"
end_utc: "2026-12-30T10:00:00Z"
start_local: "2026-12-30T10:00:00+01:00"
end_local: "2026-12-30T11:00:00+01:00"
timezone: Europe/Berlin
all_day: false
location: "TBD"
organizer: maik
series_uid: ""
rrule: ""
occurrence_of: ""
external_url: ""
source_doc: ""
agenda: []
tags:
  - kind/event
  - topic/test
---
Temporary page written by the MCP write test. Safe to delete.
"""

INVALID = """# no frontmatter, unclosed fence

```
this fence is never closed
"""


def log(text):
    lines.append(text)


def short(obj, n=700):
    return json.dumps(obj, ensure_ascii=False)[:n]


class Client:
    def __init__(self, space):
        self.proc = subprocess.Popen(
            [KIWIFS, 'mcp', '--remote', URL, '--space', space],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.next_id = 1

    def send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + '\n').encode('utf-8'))
        self.proc.stdin.flush()

    def call(self, method, params=None, timeout=20):
        rid = self.next_id
        self.next_id += 1
        msg = {'jsonrpc': '2.0', 'id': rid, 'method': method}
        if params is not None:
            msg['params'] = params
        self.send(msg)
        deadline = time.time() + timeout
        buf = b''
        while time.time() < deadline:
            if not select.select([self.proc.stdout], [], [], 0.5)[0]:
                continue
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line.decode('utf-8'))
                except ValueError:
                    continue
                if obj.get('id') == rid:
                    return obj
        return {'error': 'timeout'}

    def tool(self, name, arguments):
        return self.call('tools/call', {'name': name, 'arguments': arguments})

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
        except Exception:
            pass


def git(*args):
    res = subprocess.run(['git', '-C', EVENTS] + list(args), capture_output=True, text=True)
    return (res.stdout + res.stderr).strip()


c = Client('Events')
c.call('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                      'clientInfo': {'name': 'writetest', 'version': '0'}})
c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
log('git before: ' + git('log', '--oneline', '-3'))

P1 = 'private/2026-12-30-mcp-test.md'
log('--- 1. write valid page')
log(short(c.tool('kiwi_write', {'path': P1, 'content': VALID, 'actor': 'claude-test'})))
time.sleep(1.5)
log('on disk: ' + str(os.path.exists(os.path.join(EVENTS, P1))))
log('--- 2. read back (first 300 chars)')
r = c.tool('kiwi_read', {'path': P1})
log(short(r, 300))
log('--- 3. write invalid page')
P2 = 'private/_mcp-test-invalid.md'
log(short(c.tool('kiwi_write', {'path': P2, 'content': INVALID, 'actor': 'claude-test'})))
time.sleep(1.5)
log('invalid on disk: ' + str(os.path.exists(os.path.join(EVENTS, P2))))
log('--- git after writes')
log(git('log', '-5', '--format=%h | author=%an | %s'))
log('--- 4. delete test pages')
log(short(c.tool('kiwi_delete', {'path': P1, 'actor': 'claude-test'})))
if os.path.exists(os.path.join(EVENTS, P2)):
    log(short(c.tool('kiwi_delete', {'path': P2, 'actor': 'claude-test'})))
time.sleep(1.5)
log('valid on disk after delete: ' + str(os.path.exists(os.path.join(EVENTS, P1))))
log('invalid on disk after delete: ' + str(os.path.exists(os.path.join(EVENTS, P2))))
log('--- git final')
log(git('log', '-6', '--format=%h | author=%an | %s'))
log('status: ' + git('status', '--short'))
c.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
print('written: %s (%d lines)' % (OUT, len(lines)))
