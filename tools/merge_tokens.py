import os
import re
import shutil
import sys
import time

CONFIG = os.path.expanduser("~/Knowledge/kiwi/.kiwi/config.toml")
TOKDIR = os.path.expanduser("~/.kiwi-tokens")
RAW_FILES = []
for _name in sorted(os.listdir(TOKDIR)):
    if _name.endswith(".txt"):
        RAW_FILES.append(_name)


def parse(path):
    fields = {}
    f = open(path)
    for line in f:
        m = re.match(r"\s*(Key|Scope|Space|Actor):\s+(\S+)", line)
        if m:
            fields[m.group(1).lower()] = m.group(2)
    f.close()
    return fields


def main():
    f = open(CONFIG)
    text = f.read()
    f.close()

    blocks = []
    summary = []
    for name in RAW_FILES:
        path = os.path.join(TOKDIR, name)
        if not os.path.exists(path):
            summary.append("skip %s: file missing" % name)
            continue
        fields = parse(path)
        ok = True
        for k in ["key", "scope", "space", "actor"]:
            if k not in fields:
                ok = False
        if not ok or not fields["key"].startswith("kiwi_"):
            summary.append("skip %s: no complete key block" % name)
            continue
        if fields["key"] in text:
            summary.append("skip %s: already in config" % name)
            continue
        block = '  [[auth.api_keys]]\n'
        block += '    actor = "%s"\n' % fields["actor"]
        block += '    key = "%s"\n' % fields["key"]
        block += '    scope = "%s"\n' % fields["scope"]
        block += '    space = "%s"\n\n' % fields["space"]
        blocks.append(block)
        summary.append("add %s: space=%s scope=%s actor=%s" % (name, fields["space"], fields["scope"], fields["actor"]))

    if not blocks:
        for line in summary:
            print(line)
        print("nothing to add")
        return 0

    lines = text.split("\n")
    last_key = -1
    for i in range(len(lines)):
        if "key = " in lines[i]:
            last_key = i
    pos = len(lines)
    for i in range(last_key + 1, len(lines)):
        if lines[i].startswith("["):
            pos = i
            break
    before = "\n".join(lines[:pos])
    after = "\n".join(lines[pos:])
    if not before.endswith("\n"):
        before += "\n\n"
    new_text = before + "".join(blocks) + after

    backup = os.path.join(TOKDIR, "config.toml.bak-%d" % int(time.time()))
    shutil.copy2(CONFIG, backup)
    os.chmod(backup, 0o600)

    f = open(CONFIG, "w")
    f.write(new_text)
    f.close()
    os.chmod(CONFIG, 0o600)

    try:
        import tomllib
        f = open(CONFIG, "rb")
        data = tomllib.load(f)
        f.close()
        keys = data["auth"]["api_keys"]
        summary.append("toml parses, %d api_keys" % len(keys))
        for entry in keys:
            summary.append("  %s %s %s" % (entry["space"], entry["scope"], entry["actor"]))
    except ImportError:
        summary.append("tomllib not available, parse check skipped")

    for line in summary:
        print(line)
    print("backup: %s" % backup)
    return 0


sys.exit(main())
