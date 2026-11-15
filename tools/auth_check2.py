import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:3333"
TOKDIR = os.path.expanduser("~/.kiwi-tokens")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_check2.txt")
LINES = []


def log(text):
    LINES.append(text)


def key(name):
    f = open(os.path.join(TOKDIR, name + ".txt"))
    for line in f:
        parts = line.split()
        if len(parts) == 2 and parts[0] == "Key:":
            f.close()
            return parts[1]
    f.close()
    return None


def post(url, payload, token, session):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    if session:
        headers["Mcp-Session-Id"] = session
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        body = resp.read().decode("utf-8", "replace")
        return resp.status, resp.headers.get("Mcp-Session-Id"), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, e.headers.get("Mcp-Session-Id"), body


def parse(body):
    text = body.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except ValueError:
            return None
    for line in text.split("\n"):
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except ValueError:
                return None
    return None


def mcp_session(label, token):
    log("== /mcp " + label)
    url = BASE + "/mcp"
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "auth_check2", "version": "0"},
        },
    }
    status, session, body = post(url, init, token, None)
    log("initialize: %s session=%s" % (status, bool(session)))
    if status != 200:
        return
    post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, token, session)
    status, _, body = post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, token, session)
    msg = parse(body)
    tools = []
    if msg and "result" in msg:
        tools = msg["result"].get("tools", [])
    log("tools/list: %s, %d tools" % (status, len(tools)))
    arg = None
    for t in tools:
        if t.get("name") == "kiwi_search":
            props = t.get("inputSchema", {}).get("properties", {})
            for cand in ["query", "q", "text"]:
                if cand in props:
                    arg = cand
                    break
    if not arg:
        log("kiwi_search or its query argument not found; no call made")
        return
    call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "kiwi_search", "arguments": {arg: "buildout"}},
    }
    status, _, body = post(url, call, token, session)
    msg = parse(body)
    if msg is None:
        log("tools/call: %s, unparsable body (%d chars)" % (status, len(body)))
        return
    if "error" in msg:
        log("tools/call: %s, error: %s" % (status, str(msg["error"])[:200]))
        return
    result = msg.get("result", {})
    text = json.dumps(result)
    if result.get("isError"):
        log("tools/call: %s, isError: %s" % (status, text[:200]))
    else:
        log("tools/call: %s, ok, %d chars of result (not printed)" % (status, len(text)))


def get(url, token):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    mcp_session("no token", None)
    mcp_session("moin-read token", key("moin-read"))
    log("== config.toml readable through the file API (body not printed)")
    cases = [
        ("default-write", "default", "/api/kiwi/file?path=.kiwi/config.toml"),
        ("admin", "default", "/api/kiwi/file?path=.kiwi/config.toml"),
        ("moin-read", "moin", "/api/kiwi/moin/file?path=.kiwi/config.toml"),
        ("events-write", "Events", "/api/kiwi/Events/file?path=.kiwi/config.toml"),
    ]
    for name, space, path in cases:
        status, body = get(BASE + path, key(name))
        log("%s on %s: %s, contains api_keys: %s" % (name, space, status, "api_keys" in body))
    f = open(OUT, "w")
    f.write("\n".join(LINES) + "\n")
    f.close()
    print("written: " + OUT)


sys.exit(main())
