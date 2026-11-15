import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:3333"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_check3.txt")
LINES = []


def log(text):
    LINES.append(text)


def post(payload, session):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(BASE + "/mcp", data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


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


def call(name, arguments, ident):
    payload = {
        "jsonrpc": "2.0",
        "id": ident,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    status, body = post(payload, None)
    msg = parse(body)
    if msg is None:
        return status, None, body
    return status, msg, body


def describe(label, name, arguments, ident, needles):
    status, msg, body = call(name, arguments, ident)
    if msg is None:
        log("%s: %s, unparsable (%d chars)" % (label, status, len(body)))
        return
    if "error" in msg:
        log("%s: %s, error: %s" % (label, status, str(msg["error"])[:200]))
        return
    text = json.dumps(msg.get("result", {}))
    flags = []
    for n in needles:
        flags.append("%s=%s" % (n, n in text))
    log("%s: %s, isError=%s, %d chars, %s" % (label, status, bool(msg.get("result", {}).get("isError")), len(text), " ".join(flags)))
    if msg.get("result", {}).get("isError"):
        log("   message: " + text[:200])


def main():
    log("== /mcp without any token")
    describe("search MoinMoin", "kiwi_search", {"query": "MoinMoin"}, 10, [".md", "path"])
    describe("search buildout (moin-only word)", "kiwi_search", {"query": "buildout"}, 11, [".md", "path"])
    describe("tree", "kiwi_tree", {}, 12, [".md", "SCHEMA"])
    describe("read .kiwi/config.toml", "kiwi_read", {"path": ".kiwi/config.toml"}, 13, ["api_keys", "kiwi_"])
    describe("read ../moin/Readme", "kiwi_read", {"path": "../moin/.kiwi/config.toml"}, 14, ["api_keys", "kiwi_"])
    f = open(OUT, "w")
    f.write("\n".join(LINES) + "\n")
    f.close()
    print("written: " + OUT)


sys.exit(main())
