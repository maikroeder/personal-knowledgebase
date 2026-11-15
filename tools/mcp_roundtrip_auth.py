#!/usr/bin/env python3
"""Read-only MCP round trip through tools/kiwi-mcp.sh (key from the Keychain) for the three spaces,
plus two negative cases. Prints no key and no page content; writes mcp-roundtrip-auth.txt next to itself."""
import json
import os
import select
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WRAPPER = os.path.join(HERE, 'kiwi-mcp.sh')
OUT = os.path.join(HERE, 'mcp-roundtrip-auth.txt')
lines = []


def log(text):
    lines.append(text)


class Client:
    def __init__(self, command):
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
                if self.proc.poll() is not None:
                    break
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
        return {'error': 'timeout or process ended'}

    def stderr_tail(self):
        try:
            self.proc.terminate()
            data = self.proc.stderr.read(400)
            return data.decode('utf-8', 'replace').strip().replace('\n', ' | ')
        except Exception:
            return ''

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
        except Exception:
            pass


def summarize(res):
    if 'error' in res:
        return 'error: ' + json.dumps(res['error'])[:200]
    result = res.get('result', {})
    text = json.dumps(result)
    if result.get('isError'):
        return 'isError: ' + text[:250]
    return 'ok, %d chars (not printed)' % len(text)


def run_case(label, command, query):
    log('=' * 60)
    log(label)
    c = Client(command)
    init = c.call('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                 'clientInfo': {'name': 'roundtrip-auth', 'version': '0'}})
    log('initialize: ' + summarize(init))
    if 'error' in init:
        log('stderr: ' + c.stderr_tail())
        c.close()
        return
    c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    tl = c.call('tools/list', {})
    tools = tl.get('result', {}).get('tools', [])
    log('tools: %d' % len(tools))
    by_name = {}
    for t in tools:
        by_name[t['name']] = t
    if 'kiwi_search' in by_name:
        props = by_name['kiwi_search'].get('inputSchema', {}).get('properties', {})
        args = {}
        if 'query' in props:
            args['query'] = query
        elif 'q' in props:
            args['q'] = query
        log('kiwi_search(%s): %s' % (query, summarize(c.call('tools/call', {'name': 'kiwi_search', 'arguments': args}))))
    if 'kiwi_tree' in by_name:
        log('kiwi_tree: ' + summarize(c.call('tools/call', {'name': 'kiwi_tree', 'arguments': {}})))
    c.close()


run_case('SPACE kiwi, key kiwifs-kiwi-write', ['/bin/bash', WRAPPER, 'kiwi', 'kiwifs-kiwi-write'], 'MoinMoin')
run_case('SPACE moin, key kiwifs-moin-read', ['/bin/bash', WRAPPER, 'moin', 'kiwifs-moin-read'], 'buildout')
run_case('SPACE Events, key kiwifs-events-write', ['/bin/bash', WRAPPER, 'Events', 'kiwifs-events-write'], 'meetup')
run_case('NEGATIVE: space moin with the Events key', ['/bin/bash', WRAPPER, 'moin', 'kiwifs-events-write'], 'buildout')
run_case('NEGATIVE: space moin with no key at all',
         ['/opt/homebrew/bin/kiwifs', 'mcp', '--remote', 'http://127.0.0.1:3333', '--space', 'moin'], 'buildout')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines) + '\n')
print('written: %s (%d lines)' % (OUT, len(lines)))
