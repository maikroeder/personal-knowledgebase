#!/usr/bin/env python3
"""Convert a MoinMoin 1.5 data/pages tree to Markdown (read-only on the source).

Usage:
    moin2md.py SRC_PAGES_DIR OUT_DIR [--sample N] [--seed S] [--max-bytes B]

Rules:
- Only live pages are converted: `current` must name an existing revision with
  non-empty text. Deleted pages (current beyond the top revision), edit-lock
  only directories and empty pages are skipped and listed in report.json.
- Only the latest revision is converted. Source files are never modified.
- Code is protected before inline conversion; links resolve only to live pages.
"""
import json
import os
import random
import re
import sys
import time
import unicodedata
from datetime import datetime
from datetime import timezone

LINK_STYLE = 'wikilink'  # single place to change the link syntax


def decode_name(dirname):
    """Moin 1.5 quoting: (xx..) hex of utf-8 bytes; '_' is a space."""
    out = []
    buf = bytearray()
    i = 0
    n = len(dirname)
    while i < n:
        ch = dirname[i]
        if ch == '(':
            j = dirname.find(')', i)
            if j > 0:
                hexs = dirname[i + 1:j]
                try:
                    buf.extend(bytes.fromhex(hexs))
                    i = j + 1
                    continue
                except ValueError:
                    pass
        if buf:
            out.append(buf.decode('utf-8', 'replace'))
            buf = bytearray()
        out.append(' ' if ch == '_' else ch)
        i += 1
    if buf:
        out.append(buf.decode('utf-8', 'replace'))
    return unicodedata.normalize('NFC', ''.join(out))


def slug_part(text):
    text = unicodedata.normalize('NFC', text).lower()
    res = []
    last_dash = False
    for ch in text:
        if ch.isalnum():
            res.append(ch)
            last_dash = False
        elif not last_dash:
            res.append('-')
            last_dash = True
    s = ''.join(res).strip('-')
    return s or 'untitled'


def parse_name(name):
    """Split a Moin page name into hierarchy chain, title and metadata.

    '--' is the author's hierarchy delimiter; a real '/' is a subpage unless
    the name contains a URL. Trailing '@' runs are a status marker.
    """
    marker = ''
    mm = re.search(r'\s*(@+)\s*$', name)
    base = name
    if mm:
        marker = mm.group(1)
        base = name[:mm.start()]
    if re.search(r'\b(?:https?|ftp|svn|git):', base):
        segments = [base]
    else:
        segments = base.split('/')
    chain = []
    for seg in segments:
        for part in seg.split('--'):
            part = part.strip()
            if part:
                chain.append(part)
    if not chain:
        chain = [base.strip() or name]
    title = chain[-1]
    series = ''
    seq = ''
    date = ''
    m = re.match(r'^([A-Za-z]+)-(\d{4})-(\d{2})-(\d{2})$', title)
    if m:
        series = m.group(1).lower()
        date = '%s-%s-%s' % (m.group(2), m.group(3), m.group(4))
    else:
        m = re.match(r'^([A-Za-z]+)-(\d{1,3})(?::\s*|\s+)(.+)$', title)
        if m:
            series = m.group(1).lower()
            seq = m.group(2)
            title = m.group(3).strip()
    return {'chain': chain, 'title': title, 'marker': marker,
            'series': series, 'seq': seq, 'date': date}


def page_to_path(name):
    """Flat path: the whole original title slugged, no directories."""
    slug = slug_part(name)
    if len(slug) > 150:
        import hashlib
        h = hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]
        slug = slug[:140].rstrip('-') + '-' + h
    return slug


CAMEL = re.compile(r'(?<![\w/!\[:`])(!?)((?:[A-Z][a-z0-9]+){2,})(?![\w])')


class Converter:
    def __init__(self, index):
        self.index = index  # lower(name) -> path (no .md)
        self.stats = {}
        self.unresolved = {}
        self.macros = {}
        self.cur_name = ''

    def bump(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    def resolve(self, target):
        t = unicodedata.normalize('NFC', target.strip().strip('"'))
        if t.startswith('/'):
            t = self.cur_name + t
        elif t.startswith('../'):
            base = self.cur_name.rsplit('/', 1)[0] if '/' in self.cur_name else ''
            t = (base + '/' + t[3:]) if base else t[3:]
        t = t.replace('_', ' ') if t not in self.index else t
        path = self.index.get(t.lower())
        if path is None:
            key = t
            self.unresolved[key] = self.unresolved.get(key, 0) + 1
        return path

    def link(self, path, label):
        if label and label != path:
            return '[[%s|%s]]' % (path, label)
        return '[[%s]]' % path

    def inline(self, text):
        # protect inline code
        codes = []
        keep = []

        def K(val):
            keep.append(val)
            return '\x00K%d\x00' % (len(keep) - 1)

        def stash_code(m):
            codes.append(m.group(1))
            return '\x00C%d\x00' % (len(codes) - 1)

        text = re.sub(r'\{\{\{(.+?)\}\}\}', stash_code, text)
        text = re.sub(r'`([^`]+)`', stash_code, text)
        # macros
        def macro(m):
            name = m.group(1)
            key = '[[' + name + ']]'
            self.macros[key] = self.macros.get(key, 0) + 1
            if name == 'BR':
                return '  \n'
            return '<!-- moin-macro: %s -->' % m.group(0).strip('[]<>')

        text = re.sub(r'\[\[([A-Za-z]+)(?:\([^\]]*\))?\]\]', lambda m: K(macro(m)), text)
        text = re.sub(r'<<([A-Za-z]+)(?:\([^>]*\))?>>', lambda m: K(macro(m)), text)
        # bracket links
        def bracket(m):
            inner = m.group(1).strip()
            if inner.startswith('http://') or inner.startswith('https://') or inner.startswith('ftp://') or inner.startswith('mailto:'):
                parts = inner.split(None, 1)
                if len(parts) == 2:
                    return '[%s](%s)' % (parts[1], parts[0])
                return '<%s>' % parts[0]
            if inner.startswith('attachment:') or inner.startswith('drawing:'):
                self.bump('attachment_links')
                return '<!-- moin-attachment: %s -->' % inner
            if inner.startswith('wiki:'):
                rest = inner[5:]
                parts = rest.split(None, 1)
                tgt = parts[0].split(':', 1)
                if tgt[0] == 'Self' and len(tgt) == 2:
                    p = self.resolve(tgt[1])
                    if p:
                        return self.link(p, parts[1] if len(parts) == 2 else '')
                self.bump('interwiki_unconverted')
                return '<!-- moin-link: %s -->' % inner
            if inner.startswith(':'):
                body = inner[1:]
                if ':' in body:
                    tgt, label = body.split(':', 1)
                else:
                    tgt, label = body, ''
                p = self.resolve(tgt)
                if p:
                    return self.link(p, label.strip())
                return label.strip() or tgt
            if inner.startswith('"'):
                end = inner.find('"', 1)
                if end > 0:
                    tgt = inner[1:end]
                    label = inner[end + 1:].strip()
                    p = self.resolve(tgt)
                    if p:
                        return self.link(p, label)
                    return label or tgt
            parts = inner.split(None, 1)
            if not parts:
                return m.group(0)
            if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', parts[0]):
                self.bump('other_scheme_links')
                return '<!-- moin-link: %s -->' % inner
            p = self.index.get(unicodedata.normalize('NFC', parts[0]).lower())
            if p and re.match(r'^[A-Z]', parts[0]):
                return self.link(p, parts[1] if len(parts) == 2 else '')
            return m.group(0)

        text = re.sub(r'\[((?:[^\[\]\n])+)\]', lambda m: K(bracket(m)), text)

        # CamelCase wiki words
        def camel(m):
            if m.group(1) == '!':
                return m.group(2)
            word = m.group(2)
            p = self.index.get(word.lower())
            if p is None:
                self.bump('camel_unresolved')
                return word
            self.bump('camel_resolved')
            return '[[%s]]' % p if p.rsplit('/', 1)[-1] == slug_part(word) and p == slug_part(word) else '[[%s|%s]]' % (p, word)

        text = CAMEL.sub(lambda m: K(camel(m)), text)
        # emphasis
        text = re.sub(r"'''(.+?)'''", r'**\1**', text)
        text = re.sub(r"''(.+?)''", r'*\1*', text)
        text = re.sub(r'__(.+?)__', r'<u>\1</u>', text)
        text = re.sub(r',,(.+?),,', r'<sub>\1</sub>', text)
        text = re.sub(r'\^(.+?)\^', r'<sup>\1</sup>', text)
        text = re.sub(r'--\((.+?)\)--', r'~~\1~~', text)
        # restore kept pieces, then code
        guard = 0
        while '\x00K' in text and guard < 5:
            text = re.sub(r'\x00K(\d+)\x00', lambda m: keep[int(m.group(1))], text)
            guard += 1
        def unstash(m):
            c = codes[int(m.group(1))]
            if '`' in c:
                return '``' + c + '``'
            return '`' + c + '`'

        text = re.sub(r'\x00C(\d+)\x00', unstash, text)
        return text

    def close_fence(self, out, start, lang):
        longest = 0
        for k in range(start + 1, len(out)):
            for run in re.findall(r'`{3,}', out[k]):
                if len(run) > longest:
                    longest = len(run)
        fence = '`' * max(3, longest + 1)
        out[start] = fence + lang
        out.append(fence)
        if longest >= 3:
            self.bump('nested_fence_blocks')

    def convert(self, name, raw):
        self.cur_name = name
        lines = raw.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        out = []
        pis = []
        i = 0
        n = len(lines)
        in_code = False
        code_depth = 0
        code_start = 0
        code_lang = ''
        fm_lang = ''
        # processing instructions at top
        while i < n and lines[i].startswith('#'):
            if lines[i].startswith('##'):
                self.bump('comments_dropped')
            else:
                pis.append(lines[i])
            i += 1
        in_table = False
        while i < n:
            line = lines[i]
            if in_code:
                # nested braces count
                code_depth += line.count('{{{') - line.count('}}}')
                if code_depth <= 0:
                    idx = line.rfind('}}}')
                    before = line[:idx] if idx >= 0 else line
                    if before.strip():
                        out.append(before)
                    self.close_fence(out, code_start, code_lang)
                    in_code = False
                    rest = line[idx + 3:] if idx >= 0 else ''
                    if rest.strip():
                        out.append(self.inline(rest))
                else:
                    out.append(line)
                i += 1
                continue
            stripped = line.strip()
            if line.startswith('##'):
                self.bump('comments_dropped')
                i += 1
                continue
            # code block start: a line that is only {{{ or {{{#!lang, or starts with {{{ and has no closing on the line
            m = re.match(r'^(\s*)\{\{\{(#!\S+)?\s*$', line)
            if m or (stripped.startswith('{{{') and '}}}' not in stripped):
                lang = ''
                first_rest = ''
                if m:
                    if m.group(2):
                        lang = m.group(2)[2:]
                        if lang in ('wiki', 'plain'):
                            lang = ''
                else:
                    first_rest = stripped[3:]
                    if first_rest.startswith('#!'):
                        parts = first_rest[2:].split(None, 1)
                        lang = parts[0]
                        first_rest = parts[1] if len(parts) == 2 else ''
                        if lang in ('wiki', 'plain'):
                            lang = ''
                    # Moin allows content right after {{{ ; keep it
                fence = '```'
                code_start = len(out)
                code_lang = lang
                out.append(fence + lang)
                if first_rest.strip():
                    out.append(first_rest)
                in_code = True
                code_depth = 1
                self.bump('code_blocks')
                i += 1
                continue
            # one-line block {{{ ... }}} alone handled by inline()
            # headings
            hm = re.match(r'^(=+)\s+(.*?)\s+\1\s*$', line)
            if hm:
                level = min(len(hm.group(1)), 6)
                out.append('#' * level + ' ' + self.inline(hm.group(2)))
                self.bump('headings')
                i += 1
                continue
            if re.match(r'^-{4,}\s*$', line):
                out.append('---')
                i += 1
                continue
            # tables
            if line.startswith('||'):
                cells = line.strip().strip('|').split('||')
                clean = []
                for c in cells:
                    c = re.sub(r'^<[^>]*>', '', c.strip())
                    cell = self.inline(c.strip())
                    # a '|' label separator would be read as a cell border; links in tables lose their label
                    cell = re.sub(r'\[\[([^\]|]+)\|[^\]]*\]\]', r'[[\1]]', cell)
                    clean.append(cell.replace('|', '\\|'))
                row = '| ' + ' | '.join(clean) + ' |'
                if not in_table:
                    out.append(row)
                    out.append('|' + '|'.join([' --- '] * len(clean)) + '|')
                    in_table = True
                else:
                    out.append(row)
                i += 1
                continue
            else:
                if in_table:
                    out.append('')
                    in_table = False
            # lists
            lm = re.match(r'^(\s+)\*\s+(.*)$', line)
            if lm:
                depth = max((len(lm.group(1)) - 1) // 2, 0)
                out.append('  ' * depth + '- ' + self.inline(lm.group(2)))
                i += 1
                continue
            nm = re.match(r'^(\s+)(?:1|a|A|i|I)\.\s+(.*)$', line)
            if nm:
                depth = max((len(nm.group(1)) - 1) // 3, 0)
                out.append('   ' * depth + '1. ' + self.inline(nm.group(2)))
                i += 1
                continue
            dm = re.match(r'^(\s+)(.+?)::\s+(.*)$', line)
            if dm and not line.startswith('||'):
                out.append('- **' + self.inline(dm.group(2)) + '**: ' + self.inline(dm.group(3)))
                i += 1
                continue
            out.append(self.inline(line))
            i += 1
        if in_code:
            self.close_fence(out, code_start, code_lang)
            self.bump('unclosed_code_blocks')
        text = '\n'.join(out).strip('\n') + '\n'
        return text, pis


def yaml_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    args = sys.argv[1:]
    src = args[0]
    outdir = args[1]
    sample = 0
    seed = 1
    max_bytes = 1000000
    imported_at = ''
    k = 2
    while k < len(args):
        if args[k] == '--sample':
            sample = int(args[k + 1])
            k += 2
        elif args[k] == '--seed':
            seed = int(args[k + 1])
            k += 2
        elif args[k] == '--imported-at':
            imported_at = args[k + 1]
            k += 2
        elif args[k] == '--max-bytes':
            max_bytes = int(args[k + 1])
            k += 2
        else:
            raise SystemExit('unknown arg ' + args[k])

    report = {'skipped': {}, 'collisions': [], 'too_big': [], 'non_wiki_format': []}
    live = {}  # name -> (revfile, rev)
    for d in sorted(os.listdir(src)):
        dp = os.path.join(src, d)
        if not os.path.isdir(dp):
            continue
        name = decode_name(d)
        cur = os.path.join(dp, 'current')
        if not os.path.isfile(cur):
            report['skipped'].setdefault('no_current', []).append(name)
            continue
        rev = open(cur).read().strip()
        rp = os.path.join(dp, 'revisions', rev) if rev else ''
        if not rev or not os.path.isfile(rp):
            report['skipped'].setdefault('deleted_or_missing_revision', []).append(name)
            continue
        live[name] = (rp, rev, d)

    # first/last edit time per page from the wiki edit-log (microseconds)
    first = {}
    last = {}
    elog = os.path.join(os.path.dirname(os.path.abspath(src)), 'edit-log')
    if os.path.isfile(elog):
        for line in open(elog, encoding='utf-8', errors='replace'):
            f = line.rstrip('\n').split('\t')
            if len(f) < 4:
                continue
            try:
                ts = int(f[0]) // 1000000
            except ValueError:
                continue
            if f[3] not in first or ts < first[f[3]]:
                first[f[3]] = ts
            if f[3] not in last or ts > last[f[3]]:
                last[f[3]] = ts

    def year_of(dirname):
        if dirname in first:
            return time.strftime('%Y', time.gmtime(first[dirname]))
        return 'undated'

    index = {}
    used = {}
    for name in sorted(live):
        p = year_of(live[name][2]) + '/' + page_to_path(name)
        if p in used:
            report['collisions'].append([name, used[p]])
            p = p + '-' + str(len([x for x in used if x.startswith(p)]) + 1)
        used[p] = name
        index[name.lower()] = p
    names = sorted(live)
    if sample:
        rnd = random.Random(seed)
        names = rnd.sample(names, min(sample, len(names)))

    conv = Converter(index)
    now = imported_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    written = 0
    for name in names:
        rp, rev, dname = live[name]
        size = os.path.getsize(rp)
        if size > max_bytes:
            report['too_big'].append([name, size])
            continue
        raw = open(rp, 'rb').read().decode('utf-8')
        if not raw.strip():
            report['skipped'].setdefault('empty_text', []).append(name)
            continue
        try:
            body, pis = conv.convert(name, raw)
        except Exception as exc:
            report.setdefault('errors', []).append([name, repr(exc)])
            continue
        skip = False
        for pi in pis:
            low = pi.lower()
            if low.startswith('#format') and 'wiki' not in low:
                report['non_wiki_format'].append([name, pi])
                plain = raw.replace('\r\n', '\n').replace('\r', '\n')
                longest = 0
                for run in re.findall(r'`{3,}', plain):
                    if len(run) > longest:
                        longest = len(run)
                fence = '`' * max(3, longest + 1)
                body = fence + '\n' + plain.strip('\n') + '\n' + fence + '\n'
        info = parse_name(name)
        fm = ['---', 'title: ' + yaml_str(name), 'moin_source: ' + yaml_str(name),
              'moin_revision: ' + yaml_str(rev), 'imported_at: "' + now + '"']
        if dname in first:
            fm.append('moin_created: "' + time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(first[dname])) + '"')
            fm.append('moin_modified: "' + time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(last[dname])) + '"')
        fm.append('tags:')
        fm.append('  - imported/moin')
        pref = []
        for part in info['chain'][:-1]:
            pref.append(slug_part(part))
            fm.append('  - moin/' + '/'.join(pref))
        if info['series']:
            fm.append('  - series/' + info['series'])
        for pi in pis:
            if pi.lower().startswith('#language'):
                fm.insert(5, 'language: ' + yaml_str(pi.split(None, 1)[1] if ' ' in pi else ''))
        fm.append('---')
        target = os.path.join(outdir, index[name.lower()] + '.md')
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(fm) + '\n\n' + body)
        written += 1
    report['live_pages'] = len(live)
    report['written'] = written
    report['stats'] = conv.stats
    report['macros'] = conv.macros
    top = sorted(conv.unresolved.items(), key=lambda kv: -kv[1])[:60]
    report['unresolved_links_top'] = top
    report['unresolved_links_distinct'] = len(conv.unresolved)
    for key in list(report['skipped']):
        report['skipped'][key + '_count'] = len(report['skipped'][key])
        report['skipped'][key] = report['skipped'][key][:10]
    with open(os.path.join(outdir, '_report.json'), 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print(json.dumps({k2: report[k2] for k2 in ('live_pages', 'written', 'stats', 'macros', 'unresolved_links_distinct')}, indent=1))
    print('skipped:', {k2: v for k2, v in report['skipped'].items() if k2.endswith('_count')})
    print('too_big:', report['too_big'], 'collisions:', len(report['collisions']), 'non_wiki:', len(report['non_wiki_format']))


if __name__ == '__main__':
    main()
