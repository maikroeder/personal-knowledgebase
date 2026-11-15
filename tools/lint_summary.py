import json
import sys

path = '/tmp/lint.json'
if len(sys.argv) > 1:
    path = sys.argv[1]
d = json.load(open(path))
print('top-level keys:', list(d))
items = []


def walk(node):
    if isinstance(node, dict):
        if 'kind' in node:
            items.append(node)
        for key in node:
            walk(node[key])
    elif isinstance(node, list):
        for x in node:
            walk(x)


walk(d)
seen = {}
for x in items:
    seen.setdefault(x['kind'], []).append(x)
for kind in seen:
    print('==', kind, len(seen[kind]))
    for x in seen[kind][:3]:
        print(json.dumps(x, ensure_ascii=False)[:300])
for kind in ('fence-unclosed', 'frontmatter-missing-required'):
    print('== files for', kind)
    for x in seen.get(kind, []):
        print(json.dumps(x, ensure_ascii=False)[:200])
print('== broken-link targets, top 25')
count = {}
for x in seen.get('broken-link', []):
    key = str(x.get('target') or x.get('link') or x.get('message') or x)
    count[key] = count.get(key, 0) + 1
rows = sorted(count.items(), key=lambda kv: -kv[1])
for key, n in rows[:25]:
    print(n, key[:160])
