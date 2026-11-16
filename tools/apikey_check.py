#!/usr/bin/env python3
"""Does `kiwifs serve --auth apikey --api-key K` protect /mcp, and does `kiwifs mcp --remote` read KIWI_API_KEY?
Starts a throwaway server on port 3334 with an empty temporary root and a random throwaway key, runs the checks,
stops the server and removes the root. Touches nothing in ~/Knowledge. Prints no key; writes apikey-check.txt."""
import json
import os
import secrets
import select
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

KIWIFS = '/opt/homebrew/bin/kiwifs'
PORT = 3334
BASE = 'http://127.0.0.1:%d' % PORT
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apikey-check.txt')
lines = []


def log(text):
    lines.append(text)


def http(method, path, token=None, payload=None, session=None):
    headers = {'Accept': 'application/json, text/event-stream'}
    data = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(payload).encode()
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return resp.status, resp.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return 0, str(e)


def parse(body):
    text = body.strip()
    if text.startswith('{'):
        try:
            return json.loads(text)
        except ValueError:
            return None
    for line in text.split('\n'):
        if line.startswith('data:'):
            try:
                return json.loads(line[5:].strip())
            except ValueError:
                return None
    return None


def summarize(msg):
    if msg is None:
        return 'unparsable'
    if 'error' in msg:
        return 'error: ' + json.dumps(msg['error'])[:160]
    result = msg.get('result', {})
    text = json.dumps(result)
    if result.get('isError'):
        return 'isError: ' + text[:200]
    return 'ok, %d chars (not printed)' % len(text)


def mcp_http(label, token):
    log('-- /mcp over HTTP, ' + label)
    init = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': '2025-03-26', 'capabilities': {},
                       'clientInfo': {'name': 'apikey-check', 'version': '0'}}}
    status, body = http('POST', '/mcp', token, init)
    log('initialize: HTTP %s %s' % (status, summarize(parse(body)) if status == 200 else body[:120].replace('\n', ' ')))
    status, body = http('POST', '/mcp', token, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})
    msg = parse(body)
    count = 0
    if msg and 'result' in msg:
        count = len(msg['result'].get('tools', []))
    log('tools/list: HTTP %s, %d tools' % (status, count))
    status, body = http('POST', '/mcp', token, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                                                  'params': {'name': 'kiwi_tree', 'arguments': {}}})
    log('tools/call kiwi_tree: HTTP %s, %s' % (status, summarize(parse(body)) if status == 200 else body[:120].replace('\n', ' ')))


def proxy(label, env_extra):
    log('-- kiwifs mcp --remote (stdio proxy), ' + label)
    env = dict(os.environ)
    env.pop('KIWI_API_KEY', None)
    for k in env_extra:
        env[k] = env_extra[k]
    p = subprocess.Popen([KIWIFS, 'mcp', '--remote', BASE], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, env=env)

    def call(rid, method, params=None):
        msg = {'jsonrpc': '2.0', 'id': rid, 'method': method}
        if params is not None:
            msg['params'] = params
        p.stdin.write((json.dumps(msg) + '\n').encode())
        p.stdin.flush()
        deadline = time.time() + 15
        buf = b''
        while time.time() < deadline:
            ready = select.select([p.stdout], [], [], 0.5)[0]
            if not ready:
                continue
            chunk = os.read(p.stdout.fileno(), 65536)
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                try:
                    obj = json.loads(line.decode())
                except ValueError:
                    continue
                if obj.get('id') == rid:
                    return obj
        return {'error': 'timeout'}

    init = call(1, 'initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                  'clientInfo': {'name': 'apikey-check', 'version': '0'}})
    log('initialize: ' + summarize(init))
    p.stdin.write((json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n').encode())
    p.stdin.flush()
    log('tools/call kiwi_tree: ' + summarize(call(2, 'tools/call', {'name': 'kiwi_tree', 'arguments': {}})))
    p.terminate()


def main():
    key = secrets.token_hex(32)
    root = tempfile.mkdtemp(prefix='kiwi-apikey-test-')
    server = subprocess.Popen([KIWIFS, 'serve', '--root', root, '--host', '127.0.0.1', '--port', str(PORT),
                               '--auth', 'apikey', '--api-key', key],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        up = False
        for i in range(40):
            time.sleep(0.5)
            status, body = http('GET', '/api/kiwi/tree')
            if status != 0:
                up = True
                break
        log('throwaway server started: %s (root %s, key not printed)' % (up, os.path.basename(root)))
        if not up:
            return
        log('-- REST /api/kiwi/tree')
        log('no token: HTTP %s' % http('GET', '/api/kiwi/tree')[0])
        log('with the key: HTTP %s' % http('GET', '/api/kiwi/tree', key)[0])
        log('wrong key: HTTP %s' % http('GET', '/api/kiwi/tree', 'wrong-' + key[:8])[0])
        mcp_http('no token', None)
        mcp_http('with the key as bearer', key)
        proxy('key in env KIWI_API_KEY only, no --api-key flag', {'KIWI_API_KEY': key})
        proxy('no key anywhere', {})
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except Exception:
            server.kill()
        shutil.rmtree(root, ignore_errors=True)
        f = open(OUT, 'w')
        f.write('\n'.join(lines) + '\n')
        f.close()
        print('written: ' + OUT)


sys.exit(main())
