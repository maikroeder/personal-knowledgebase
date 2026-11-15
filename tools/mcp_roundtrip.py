#!/usr/bin/env python3
"""Read-only MCP round trip against the three kiwifs spaces (stdio proxy mode).
Writes the result to mcp-roundtrip.txt next to this script. Makes no changes in any space."""
import json
import os
import select
import subprocess
import sys
import time

KIWIFS = '/opt/homebrew/bin/kiwifs'
URL = 'http://127.0.0.1:3333'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp-roundtrip.txt')
lines = []


def log(text):
    lines.append(text)


class Client:
    def __init__(self, space):
        self.space = space
        self.proc = subprocess.Popen(
            [KIWIFS, 'mcp', '--remote', URL, '--space', space],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.next_id = 1

    def send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + '\n').encode('utf-8'))
        self.proc.stdin.flush()

    def call(self, method, params=None, timeout=15):
        rid = self.next_id
        self.next_id += 1
        msg = {'jsonrpc': '2.0', 'id': rid, 'method': method}
        if params is not None:
            msg['params'] = params
        self.send(msg)
        deadline = time.time() + timeout
        buf = b''
        while time.time() < deadline:
            ready = select.select([self.proc.stdout], [], [], 0.5)[0]
            if not ready:
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

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
        except Exception:
            pass


def short(obj, n=500):
    return json.dumps(obj, ensure_ascii=False)[:n]


for space in ('default', 'moin', 'Events'):
    log('=' * 60)
    log('SPACE ' + space)
    c = Client(space)
    init = c.call('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                 'clientInfo': {'name': 'roundtrip', 'version': '0'}})
    log('initialize: ' + short(init, 300))
    c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    tl = c.call('tools/list', {})
    tools = tl.get('result', {}).get('tools', [])
    log('tools: %d' % len(tools))
    names = []
    for t in tools:
        names.append(t['name'])
    log('names: ' + ', '.join(names))
    by_name = {}
    for t in tools:
        by_name[t['name']] = t
    for key in ('kiwi_search', 'kiwi_tree', 'kiwi_write', 'kiwi_read', 'kiwi_delete'):
        if key in by_name:
            log('schema %s: %s' % (key, short(by_name[key].get('inputSchema'), 700)))
    query = {'default': 'MoinMoin', 'moin': 'buildout', 'Events': 'meetup'}[space]
    if 'kiwi_search' in by_name:
        props = by_name['kiwi_search'].get('inputSchema', {}).get('properties', {})
        args = {}
        if 'query' in props:
            args['query'] = query
        elif 'q' in props:
            args['q'] = query
        res = c.call('tools/call', {'name': 'kiwi_search', 'arguments': args})
        log('kiwi_search(%s): %s' % (short(args, 80), short(res, 900)))
    if 'kiwi_tree' in by_name:
        res = c.call('tools/call', {'name': 'kiwi_tree', 'arguments': {}})
        log('kiwi_tree: ' + short(res, 500))
    c.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
print('written: %s (%d lines)' % (OUT, len(lines)))
