import os
import shutil
import sys
import time

path = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Knowledge/kiwi/.kiwi/config.toml")
f = open(path)
lines = f.read().split("\n")
f.close()
start = -1
end = -1
for i in range(len(lines)):
    if lines[i].strip() == "[auth]" and start < 0:
        start = i
    if start >= 0 and i > start and lines[i].startswith("[") and not lines[i].strip().startswith("[[auth"):
        end = i
        break
if start < 0 or end < 0:
    print("no [auth] block followed by another table; nothing changed")
    sys.exit(1)
removed = 0
for i in range(start, end):
    if "key = " in lines[i]:
        removed += 1
backup = os.path.expanduser("~/.kiwi-tokens/%s.bak-%d" % (os.path.basename(path), int(time.time())))
shutil.copy2(path, backup)
os.chmod(backup, 0o600)
new_lines = lines[:start] + lines[end:]
f = open(path, "w")
f.write("\n".join(new_lines))
f.close()
os.chmod(path, 0o600)
print("removed the [auth] block with %d key(s) from %s" % (removed, path))
print("backup: " + backup)
