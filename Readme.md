# personal-knowledgebase

Installation instructions and example client configuration for a personal knowledge base: a folder of Markdown
pages served by [KiwiFS](https://docs.kiwifs.com) on a Mac, versioned with git, searchable, and reachable from
Claude Desktop and Claude Code through the Model Context Protocol (MCP). Code behind the paper *Personal
Knowledge Base* (`~/Writing/PersonalKnowledgeBasePaper`).

There is no code of our own yet. KiwiFS ships as one binary, `kiwifs`, which provides the knowledge root, the
server with its web UI, and the MCP server. This repository holds the steps and the configuration around it.

## Install

Requirements: macOS with Homebrew (Apple Silicon assumed: Homebrew prefix `/opt/homebrew`; on Intel it is
`/usr/local`), and Claude Desktop and/or the Claude Code CLI.

1. Install the binary and check it:

   ```bash
   brew install kiwifs/tap/kiwifs
   kiwifs --version
   which kiwifs                      # expected: /opt/homebrew/bin/kiwifs
   ```

   Alternatives: `curl -fsSL https://raw.githubusercontent.com/kiwifs/kiwifs/main/install.sh | sh` (read the
   script first), or `go install github.com/kiwifs/kiwifs@latest` (needs Go 1.25).

2. Create the knowledge root:

   ```bash
   mkdir -p ~/Knowledge
   kiwifs init --root ~/Knowledge/kiwi --template kb
   ```

   `kb` is the default template, and 0.19.58 accepted it. The templates guide (`docs.kiwifs.com/guides/templates`)
   calls `knowledge`, which the repository README still shows, a retired name that errors and points to
   `memory`; that name was not run. `kiwifs init` does not create a git repository: `git -C ~/Knowledge/kiwi log
   --oneline` right after it fails with "not a git repository".

3. Smoke test the server and its web UI. Bind to localhost, because the default bind address is `0.0.0.0`:

   ```bash
   kiwifs serve --root ~/Knowledge/kiwi --host 127.0.0.1 --port 3333
   # in another terminal:
   curl -sI http://127.0.0.1:3333/
   open http://127.0.0.1:3333/
   ```

   Stop it with Ctrl-C. Step 4 does not need a running server.

   Without `--host` the server listens on `0.0.0.0:3333`, that is on all interfaces, with no authentication
   unless `--auth` is given. That is what happened on the first run (see below). Once the server had run, the root
   was a git repository on `main` with no commits yet (`git log` says "your current branch 'main' does not have
   any commits yet"). After a first page was created, `git log --oneline` showed one commit,
   `f84d099 (HEAD -> main) human:web-ui: <page name>.md`. That commit changes only the page itself; the files of
   the `kb` template stay untracked (`git status --short`). Commit them by hand if you want them in the history.

4. Register the MCP server with the clients. Use the absolute path of the binary and an absolute knowledge root:
   Claude Desktop does not inherit the shell's `PATH` and does not expand `~`.

   Claude Desktop: merge the `kiwifs` entry of `config/claude_desktop_config.example.json` into
   `~/Library/Application Support/Claude/claude_desktop_config.json` (keep any existing `mcpServers`), adjust the
   two paths if yours differ, then quit Claude Desktop completely (Cmd+Q) and start it again.

   Claude Code:

   ```bash
   claude mcp add --scope user kiwifs -- /opt/homebrew/bin/kiwifs mcp --root /Users/maik/Knowledge/kiwi
   claude mcp list
   ```

   Both entries start their own `kiwifs mcp` process on the same root (in-process mode). If you also keep
   `kiwifs serve` running on that root, use proxy mode instead (`config/claude_desktop_config.proxy.example.json`;
   add `--api-key` to the arguments when the server runs with `--auth apikey`), so that only one process owns the
   search index and the git repository.

5. Verify the MCP server. List its tools from a shell (the documentation says there are 78):

   ```bash
   printf '%s\n' \
     '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"check","version":"0"}}}' \
     '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
     '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
     | kiwifs mcp --root ~/Knowledge/kiwi
   ```

   Then, in Claude Desktop or Claude Code, ask the client to write a test page, read it back and search for it,
   and check that a commit appeared with `git -C ~/Knowledge/kiwi log --oneline`.

### Optional: a remote KiwiFS server

To reach a KiwiFS server that someone else runs (it serves MCP at `/mcp`), register it with Claude Code over HTTP. Keep the
API key out of the command line history and out of any file you commit:

```bash
read -rs KIWI_API_KEY && export KIWI_API_KEY
claude mcp add --scope user --transport http kiwifs-remote https://<server>/mcp --header "Authorization: Bearer $KIWI_API_KEY"
claude mcp list
```

`claude mcp add` does not contact the server; `claude mcp list` does, and should print `Connected`. Claude Code stores the
header, key included, in `~/.claude.json` in plain text. Whether a given server wants a bearer header or an `X-API-Key`
header, or only a browser sign-in, depends on how its owner started it. `kiwifs mcp --remote https://<server>
--api-key ...` is the documented proxy alternative (its base URL has no `/mcp`); it was not run.

Update with `kiwifs update`.

## Second phase: three spaces on one server (2026-11-15)

Until 2026-11-15 23:44 the knowledge root `~/Knowledge/kiwi` was the `--root` (the space `default`), and the server
served it with `moin` and `Events` added. Since 2026-11-16 00:00 (layout B, see "Authentication per space") the
`--root` is a hub that holds only the `kb` template pages and the keys, and all three knowledge roots are spaces.
Everything below was run on 2026-11-15 and 16; who ran what is listed under "What has and has not been run".

| Space (URL name) | Root | Content |
| --- | --- | --- |
| `default` | `~/Knowledge/hub` | template pages only, plus `.kiwi/config.toml` with the keys (denied through the API) |
| `kiwi` | `~/Knowledge/kiwi` | own pages, unchanged |
| `moin` | `~/Knowledge/moin` | 4708 pages converted from a MoinMoin wiki, year folders |
| `Events` | `~/Knowledge/events` | personal events, same page schema as the OpenHeidelberg Events space |

```bash
kiwifs serve --root ~/Knowledge/hub --space kiwi=$HOME/Knowledge/kiwi --space moin=$HOME/Knowledge/moin \
  --space Events=$HOME/Knowledge/events --host 127.0.0.1 --port 3333 --auth perspace
```

The log then says `space "moin" mounted at /api/kiwi/moin`, and the web UI has a space switcher. The REST routes
are `/api/kiwi/<space>/tree`, `/search?q=` and `/file?path=`; `/api/kiwi/<space>/mcp` does not exist (404), only
`/mcp` on the server. The file watcher is announced only for the default root; after copying files into the
`moin` or `Events` root, run `kiwifs reindex --root <root> --fts-only` (about 3 s for 4700 pages). Do not copy
thousands of files into a root while the server is running: the first test did that and the shutdown afterwards
took very long (see the paper, Results).

### Import a MoinMoin wiki (`tools/moin2md.py`)

The source is a MoinMoin DesktopEdition 1.5.5a wiki (`wiki/data/pages/<Name>/{current,revisions/NNNNNNNN}`). The
converter only reads it.

```bash
python3 tools/moin2md.py <wiki>/data/pages <out-dir> [--sample N --seed S] [--max-bytes B] [--imported-at TS]
```

Rules, each one decided on 2026-11-15:

- Only live pages: `current` must name an existing revision with text. Pages whose `current` points beyond the top
  revision (Moin 1.5 deletion), pages with only an edit-lock and empty directories are skipped, and listed in
  `<out-dir>/_report.json`. Only the latest revision is converted.
- Titles stay exactly as they were, including `--`, numbered prefixes and trailing `@@@`. The page name is also kept
  in `moin_source`. The file name is the slugged title; names over 150 characters are cut and get a hash.
- Folders are years: the year of the page's first entry in `wiki/data/edit-log` (the file times of the revisions
  are useless: most carry 2012). Pages without an edit-log entry go to `undated/`. `moin_created` and
  `moin_modified` come from the same log.
- Tags: `imported/moin`, one `moin/<prefix>` tag per `--` prefix level, and `series/<name>` for `Name-NN ...` and
  `Name-YYYY-MM-DD` titles. No other hierarchy.
- Markup: headings, lists, tables, code blocks (a longer fence when the code contains fences), emphasis and links
  (to live pages as `[[2012/page|label]]`, links in tables without the label because a `|` would split the cell).
  Macros (`Navigation`, `Include`, `PageOutline`) become HTML comments without brackets, because `kiwifs lint`
  reads `[[...]]` inside a comment as a link. `#format`, `#pragma` and `#acl` lines are dropped (also after leading
  `##` comments), `#language` goes to a `language:` field, and a `#format plain` page is kept as one code block.
- `--imported-at` keeps the import time stable, so that a re-run changes only the files that really changed.

Result and the numbers are in the paper (section 6). Procedure used: dry run into a scratch folder, `kiwifs init
--root <root> --template kb` for the new root, `rsync -a --exclude _report.json <dry-run>/ <root>/` with the server
stopped, `git init -b main && git add -A && git commit`, `kiwifs reindex --fts-only`, `kiwifs lint`. Expected lint
output for the `moin` root: 3 broken links and 3 missing titles that come from the template's own files, 54
duplicate heading anchors and 2 skipped heading levels that come from the old pages.

### The Events space

`events-seed/` holds `SCHEMA.md` (the page schema: `uid`, `title`, `event_kind`, `publish_state`, `tier`, quoted UTC
and local times, `timezone`, `all_day`, `location`, `organizer`, `tags`) and three pages marked EXAMPLE under
`private/`. Create the space with `kiwifs init --root ~/Knowledge/events --template kb`, copy the seed over it,
remove the template's example folders, commit, reindex and lint (clean after the removal and a `title:` in
`SCHEMA.md`).

### MCP, one entry per space

`kiwifs mcp --remote <url> --space <name>` proxies to the running server and scopes every call to one space. The
in-process entry from step 4 must be removed first (`claude mcp remove kiwifs`), otherwise two processes write to
the same git repository.

```bash
claude mcp add --scope user kiwi-personal -- /bin/bash $HOME/Code/personal-knowledgebase/tools/kiwi-mcp.sh kiwi kiwifs-kiwi-write
claude mcp add --scope user kiwi-moin -- /bin/bash $HOME/Code/personal-knowledgebase/tools/kiwi-mcp.sh moin kiwifs-moin-read
claude mcp add --scope user kiwi-events -- /bin/bash $HOME/Code/personal-knowledgebase/tools/kiwi-mcp.sh Events kiwifs-events-write
```

These are the entries with authentication on (registered 2026-11-16 00:03, `claude mcp list` printed `Connected` for all
three). The wrapper `tools/kiwi-mcp.sh <space> <Keychain item>` reads the key from the macOS Keychain and starts
`kiwifs mcp --remote http://127.0.0.1:3333 --space <space> --api-key <key>`; no key is stored in `~/.claude.json`.
The entries before authentication (`kiwifs mcp --remote http://127.0.0.1:3333 --space default|moin|Events`, no key)
now get 401. Claude's keys are a read key for `moin` and write keys for `kiwi` and `Events`.

`config/claude_desktop_config.multispace.example.json` has the same three entries for Claude Desktop, with the wrapper
(not merged into the real file yet). Each space offers 71 tools (81 since 0.19.94). `kiwi_write` takes an `actor` argument that becomes the git
author; pass `claude`, so `git log --format=%an` separates agent writes from human ones. In this first setup there was no authentication (`--auth none`; the server binds to `127.0.0.1` only); see
"Authentication per space" below for what replaced it and what is still open.

### Helper scripts (`tools/`)

All read-only except `mcp_writetest.py`, which writes and deletes two pages in the `Events` space and leaves
commits, and `merge_tokens.py`, which rewrites the key list in `~/Knowledge/kiwi/.kiwi/config.toml`. Each check writes
its result next to itself (`tools/*.txt` is ignored by git).

- `check_spaces.sh`: status codes and a search per space against the running server.
- `mcp_probe.sh`: collects `kiwifs mcp`, `token` and `serve` help texts and probes `/mcp` into `mcp-probe.txt`.
- `mcp_roundtrip.py`: lists the tools and searches in each space through the proxy, into `mcp-roundtrip.txt`.
- `mcp_writetest.py`: write, read back, write an invalid page, delete both, git log; into `mcp-writetest.txt`.
- `lint_summary.py`: counts `kiwifs lint --json` output by kind.
- `kiwi-mcp.sh`: the MCP proxy for one space with its key from the Keychain (see above).
- `keychain_import.sh`: copies the keys from `~/.kiwi-tokens/<name>.txt` into Keychain items `kiwifs-<name>`; the script
  holds no key and prints item names only.
- `mcp_roundtrip_auth.py`: read-only round trip through the wrapper for the three spaces and two negative cases (a
  wrong key, no key); prints sizes and error text, into `mcp-roundtrip-auth.txt`.
- `strip_old_auth.py`: removes the `[auth]` block from a root's `config.toml` (used once, on the old default root).
- `apikey_check.py`: throwaway-server test of `--auth apikey` for REST, `/mcp` and the proxy's `KIWI_API_KEY` (see below).
- `merge_tokens.py`: puts the keys from `~/.kiwi-tokens/*.txt` (the output of `kiwifs token create`) back into
  `config.toml` as `[[auth.api_keys]]` entries, because each `token create` replaces the list; sets mode 600,
  keeps a backup, prints space, scope and actor only.
- `auth_check.sh`: HTTP status per token for the hub and the three spaces against the running server (keys sent through stdin, never
  printed), into `auth_check.txt`.
- `auth_check2.py`, `auth_check3.py`: calls to the server's `/mcp` endpoint with and without a token, and reads
  of `.kiwi/config.toml`; print status, sizes and True/False only, into `auth_check2.txt`, `auth_check3.txt`.

### Authentication per space (2026-11-15 23:26 to 2026-11-16 00:03)

`--auth perspace` with scoped tokens replaced `--auth none`. Everything here was run by Maik in a terminal; the AI
collaborator read the result files that the scripts wrote. No key was pasted into the conversation (masked output only).

How it works, as observed with 0.19.58:

- `kiwifs token create --root ~/Knowledge/kiwi --space S --scope read|write|admin --actor NAME` (first layout; in
  layout B the root is `~/Knowledge/hub`) writes an
  `[[auth.api_keys]]` entry (`actor`, `key`, `scope`, `space`) into `<root>/.kiwi/config.toml`, sets `[auth] type =
  "perspace"` and prints the key once. `serve` must be started with `--auth perspace` as well; the flag was passed
  explicitly because it is unknown whether the flag default `none` would override the file.
- Tokens live in the config of the `--root` only, and are valid for the other spaces as well: a `moin` read token gets
  200 on `moin` and 401 on the other two, an `Events` write token 200 on `Events` only, and so on. An admin token
  covers its own space only, so the web UI needs one admin token per space. No token and a wrong token give 401 on all
  three spaces. The file API refuses `.kiwi/config.toml` (400).
- Each `token create` replaced the key list instead of appending: four creates left one key, and three more with the
  server stopped left one key. `kiwifs token list` printed "No API tokens configured." while the file held a key, so
  it was not used. `tools/merge_tokens.py` restores the keys from the files that `create` was redirected into.
  Procedure: stop the server, `rm` the old files, create all tokens (one file each in `~/.kiwi-tokens`, mode 600), run
  `python3 tools/merge_tokens.py`, check with `grep -c 'key = '`, start the server, run `bash tools/auth_check.sh`.
- The file watcher of the default root committed `.kiwi/config.toml` to that root's own git repository (commit
  `fswatch: .kiwi/config.toml`, 23:29, one key inside). That repository tracked nothing else and has no remote. The file
  was untracked (`git rm --cached`), listed in `.git/info/exclude`, and every key was replaced at 23:41; the old key is
  dead and remains only in that old commit. A new `config.toml` is mode 644 by default; `merge_tokens.py` sets 600.
- Result matrix after the rotation (server with `--auth perspace`, 23:42): all lines as expected (see
  `tools/auth_check.sh`); nothing was returned without a valid token on the REST routes.

What is still open:

- In `--auth perspace` mode, `/mcp` of the server (the streamable-HTTP endpoint) answers without a token (0.19.58 and
  0.19.94; a per-space token sent to it made no difference), and still does in layout B, where it
  serves only the hub. Observations from the first layout: with no token: `initialize` 200,
  `tools/list` 71 tools, a search and a tree call returned data from the default root. A search for a word that
  exists only in `moin` returned an empty result, so `/mcp` serves the `--root` only. Reading `.kiwi/config.toml` and a
  path with `..` through it were refused. Writes through `/mcp` were not tried. The proxies registered per space
  (`kiwifs mcp --remote ... --space S`) are not affected, but nothing stops another process or a web page from
  calling `/mcp` on `127.0.0.1:3333`; whether the server answers cross-site requests was not tested.
- Layout B (decided 23:44, running since 23:59): the server runs with `--root ~/Knowledge/hub` and mounts the three
  knowledge roots with `--space`. The hub came from a test: `kiwifs serve` on an empty folder (port 3334) initialised it
  itself (git repository, `.kiwi/`, the `kb` template pages); that folder was copied to `~/Knowledge/hub`, and its
  `config.toml` is excluded from git. The tokens were created with `--root ~/Knowledge/hub` and `--space kiwi|moin|Events`
  (six keys: read for `moin`, write for `kiwi` and `Events` as actor `claude`, one admin per space as `maik`);
  `strip_old_auth.py` removed the old keys from the kiwi root's config. Result of `tools/auth_check.sh`: each token
  gets 200 on its own space and 401 on the other two; without a token 401 on kiwi, moin and Events; `/mcp` answers 200
  but serves the hub: a search for a word from the notes and for a word found only in `moin` returned nothing, and the
  tree lists template files only. Two rules follow: a space without keys in `config.toml` is open (the hub answers 200
  without a token, and so did a test server started with `--auth perspace` and no keys at all), so `tools/auth_check.sh`
  runs after every config change; and `kiwifs serve` initialises any empty root it is given.
- MCP entries with keys (00:01 to 00:03): the six keys were copied into the macOS Keychain
  (`tools/keychain_import.sh`, items `kiwifs-<name>`). `tools/mcp_roundtrip_auth.py`: the three spaces through the wrapper
  gave 71 tools and answered search and tree; `moin` with the `Events` key gave `invalid API key (HTTP 401)`, `moin` with
  no key gave `missing bearer token (HTTP 401)`; so the proxy sends the key as a bearer token. The key is visible in `ps`
  to the same user while a proxy runs. `kiwi_tree` on `moin` returns about 226,000 characters, so a client must not call it
  without a path. The three Claude Code entries were registered with the wrapper and printed `Connected`. A non-interactive call from Claude Code at 00:10 (`claude -p`, allowed to use only
  `mcp__kiwi-moin__kiwi_search`, asked for the number of results for one word) was answered with 153: a Claude Code
  session reached `moin` through the entry, the wrapper, the Keychain key and the server. An interactive session and
  Claude Desktop were not tried.
- The key store is a plain file (mode 600) in the `--root`. The keys of the first token round were partly shown in
  masked form (four characters) in the conversation; all of them were replaced.

### Update to 0.19.94 and the web UI (2026-11-16, 00:14 to 00:22)

- Web UI and keys. With keys on a space, the web UI of 0.19.58 cannot sign in: selecting `moin` showed "Your session has
  expired. Please refresh the page to sign in again." (a generic text for any 401), and a search returned nothing. The
  UI's JavaScript bundle (read in the browser pane, nothing typed) has no `Authorization` header, no `Bearer`, no cookie
  handling and no key field; the hub, which has no key, loads. The docs page on auth tokens does not cover the UI. The
  REST matrix and the MCP checks had passed, so this was found only when the UI was opened; the UI was not part of the
  checks of layout B, and the step should have included it.
- `kiwifs update` worked at 00:17 (0.19.58 to 0.19.94; the earlier attempt on 2026-11-15 timed out). It replaces
  `/opt/homebrew/bin/kiwifs` without Homebrew knowing, so a later `brew upgrade kiwifs` may complain. The roots were
  backed up first, with the server stopped (`tar -czf ~/Knowledge-backup-20261116.tgz -C ~ Knowledge`: 18 MB, 10215
  entries, mode 600; it contains the hub's `config.toml` with the keys, so keep it private).
- The server started with the same command without warnings. `tools/auth_check.sh`, `mcp_roundtrip_auth.py` and
  `auth_check3.py` gave the same results as before the update, except that each space now offers 81 tools instead of
  71. The UI bundle changed (8.9 MB to 8.2 MB) and still has no Authorization header, no Bearer and no key field, so
  0.19.94 cannot sign in either.
- Options for browsing: (1) a read-only proxy that adds the keys (GET and HEAD only; while it runs, anything on the
  machine that reaches its port reads all spaces without a key); (2) none, using Claude and the files. Not decided at
  the time of writing; the default is (2).

### `/mcp` in apikey mode (2026-11-16, 09:14)

A member of the OpenHeidelberg project said that the server does authenticate MCP (`--auth apikey`, `--api-key`,
`${KIWI_API_KEY}`). `tools/apikey_check.py` tests that against a throwaway server (port 3334, empty temporary root,
random throwaway key that is never printed; nothing in `~/Knowledge` is touched). Result with 0.19.94:

- REST: 401 without a token, 200 with the key, 401 with a wrong key.
- `/mcp` over HTTP without a token: `initialize`, `tools/list` and a tool call all 401. With the key as bearer token:
  200, 81 tools, the tool call works. So the open `/mcp` is a property of `perspace` mode, not of the server.
- The stdio proxy `kiwifs mcp --remote <url>` does not read `KIWI_API_KEY`: started with the variable and no flag, it got
  401 on a tool call, like a proxy with no key. The key has to go on the command line (`--api-key`), as `kiwi-mcp.sh`
  does.
- The price of apikey mode is one key for everything: no read-only key for `moin` at the server. The layout of this
  setup (perspace, hub root) stays; the choice between the two is the owner's and not made at the time of writing.

## Uninstall

```bash
brew uninstall kiwifs && brew untap kiwifs/tap
claude mcp remove kiwifs
```

Remove the `kiwifs` entry from `claude_desktop_config.json`. The knowledge root is not touched; it is a normal
directory with a git history.

## Troubleshooting

- Claude Desktop shows no server: check the JSON for syntax errors and the two paths; look in
  `~/Library/Logs/Claude/` for the `mcp*.log` files.
- `git` complains about a lock file in the knowledge root: two processes share the root; see step 4.
- Port 3333 is taken: choose another with `--port`.

## Layout

```
README.md
CLAUDE.md
config/claude_desktop_config.example.json         in-process (stdio) MCP entry for Claude Desktop
config/claude_desktop_config.proxy.example.json   proxy MCP entry (a running kiwifs serve)
config/claude_desktop_config.multispace.example.json   three proxy entries, one per space, with the Keychain wrapper
events-seed/                                      SCHEMA.md and three example event pages
tools/moin2md.py                                  MoinMoin 1.5 to Markdown converter
tools/*.sh, tools/*.py                            read-only checks and an MCP round trip (see above)
```

## What has and has not been run

Run by Maik on 2026-10-31 in a terminal on the Mac (Apple Silicon, `/opt/homebrew`); the output was pasted into
the conversation, and the AI collaborator did not observe the run:

- `brew install kiwifs/tap/kiwifs` (output not recorded); `kiwifs --version` printed `kiwifs version 0.19.58`;
  `which kiwifs` printed `/opt/homebrew/bin/kiwifs`. Release 0.19.81 was available.
- `kiwifs init --root ~/Knowledge/kiwi --template kb`: `Initialized knowledge at /Users/maik/Knowledge/kiwi
  (template: kb)`.
- `git -C ~/Knowledge/kiwi log --oneline` right after that: `fatal: not a git repository`.
- `kiwifs serve --root /Users/maik/Knowledge/kiwi` (no `--host`): it indexed 14 files, enabled async git commits
  and a file watcher, found Pandoc 3.10.1 and XeLaTeX, did not find Marp CLI, MkDocs, Typst or pandoc-crossref,
  and listened on `http://0.0.0.0:3333`. No check of the web UI was reported.
- `git log --oneline` afterwards: `fatal: your current branch 'main' does not have any commits yet`.
- `kiwifs serve --root /Users/maik/Knowledge/kiwi --host 127.0.0.1` (second start, 16:11): it listened on
  `http://127.0.0.1:3333`. Its log matched the first start except for the "indexed 14 files" line, which did not
  appear (not examined). No check of the web UI and no `git log` were reported for this run.

- After Maik created a page (16:16), `git -C ~/Knowledge/kiwi log --oneline` printed one commit:
  `f84d099 (HEAD -> main) human:web-ui: <page name>.md`. `git show --stat f84d099`: author
  `human:web-ui <kiwifs@internal>`, one file changed (the page), 2 insertions. `git status --short`: the template
  files `.gitattributes`, `.gitignore`, `.kiwi/`, `README.md`, `SCHEMA.md`, `faq/`, `getting-started/`, `guides/`,
  `index.md`, `playbook.md`, `reference/` and `troubleshooting/` are untracked.
- `claude mcp add --scope user kiwifs -- /opt/homebrew/bin/kiwifs mcp --root /Users/maik/Knowledge/kiwi` (16:24):
  `Added stdio MCP server kiwifs with command: ... to user config` and `File modified: /Users/maik/.claude.json`.
  `claude mcp list`: `kiwifs: /opt/homebrew/bin/kiwifs mcp --root /Users/maik/Knowledge/kiwi - ✔ Connected`. The
  connection check passed; no tool list or tool call was reported.
- `claude mcp add --scope user --transport http kiwifs-oh https://<server>/mcp --header "Authorization: Bearer
  $KIWI_API_KEY"` (2026-11-01, 19:18, key read with `read -rs`): `Added HTTP MCP server kiwifs-oh with URL: ... to
  user config`, header printed as `[REDACTED]`, `File modified: /Users/maik/.claude.json`. `claude mcp list`
  (19:19): `kiwifs: ... - ✔ Connected` and `kiwifs-oh: https://<server>/mcp (HTTP) - ✔ Connected`. No tool names
  or calls were reported. The server is a remote KiwiFS of the OpenHeidelberg project; its host name is left out
  here.

Run by Maik on 2026-11-15 in a terminal on the Mac; the output was pasted into the conversation:

- `kiwifs update` (0.19.58 to 0.19.94): `context deadline exceeded` while downloading; the binary stayed 0.19.58.
  `brew update` and `brew outdated` showed no newer version in the `kiwifs/tap` tap. No upgrade was done.
- A first test root was filled by `rsync` with the flat dry run while `kiwifs serve` ran: the log's last request
  is at 21:00:36 and `shutdown complete` at 21:26:32, after repeated Ctrl-C. When the first Ctrl-C was pressed was
  not recorded. A later shutdown of a server on an unchanged root took about 12 s (Maik's estimate).
- `kiwifs reindex --root <test root> --fts-only`: 4722 files in about 3 s. `kiwifs lint --json` on the flat dry run
  found 173 issues; the second and third dry runs (nested fences, table links, macro comments, processing
  instructions) brought it to the 62 listed above.
- The real import: `kiwifs init --root ~/Knowledge/moin --template kb`, extraction, `rsync`, `git commit` at
  2026-11-15 22:00:12 +0100, a second commit after the fix for processing instructions after `##` comments and for
  line endings of one page, `kiwifs reindex` (4722 files in 2.5 s), `kiwifs lint` (see above). `git status` clean,
  no CR characters, `.kiwi/state/` ignored by the `.gitignore` that `init` wrote.
- `~/Knowledge/events`: init, seed copy, commit, removal of the template pages, `SCHEMA.md` title, `kiwifs lint`:
  `clean - no issues`; three commits.
- `kiwifs serve` with the default root and `moin`: the log shows the space mounted, and a screenshot from Maik shows
  the web UI space switcher listing `default` (17 files) and `moin` (4723 files). With all three roots,
  `tools/check_spaces.sh` printed 200 for the three trees and found the expected pages per space; whether the web UI
  lists `Events` in its switcher was not reported.
- `claude mcp remove kiwifs` and the three `claude mcp add ... --space ...` commands above; `claude mcp list`
  printed `Connected` for `kiwi-personal`, `kiwi-moin`, `kiwi-events` and `kiwifs-oh`.
- `tools/mcp_probe.sh`, `tools/mcp_roundtrip.py` and `tools/mcp_writetest.py`: Maik ran them; the AI collaborator
  read their output files and observed: `/mcp` answers an `initialize` (protocol 2025-03-26), `/api/kiwi/<space>/mcp`
  answers 404; 71 tools per space; a search per space found the expected pages; `kiwi_write` to `Events` returned
  `Written ...`, the git author of the commit was the `actor` value, an invalid page (no frontmatter, unclosed code
  fence) was accepted as well, and `kiwi_delete` removed both pages; the three test commits remain in the history.

Run by the AI collaborator on 2026-11-15 in a Linux VM on the Mac (read-only on the Moin folder): the inventory and
census of the wiki (5107 entries in `data/pages`; 4994 with `current`; 285 of them deleted or empty; 112 without
`current`; 26290 revision files; 7 attachment files on 5 pages) and every dry run of `tools/moin2md.py` (4708 pages
written, one page of 9.5 MB left out with `--max-bytes`). It could not run `kiwifs` there (no binary), nor `cargo`.
Every `kiwifs` result above is the output Maik pasted or a file his scripts wrote.

Run by the AI collaborator on 2026-10-31 in a Linux cloud container: both example configuration files parse as
JSON.

Not run: the Claude Desktop half of step 4 (the multi-space example is written, not merged); a tool call from Claude Desktop or from an interactive Claude Code session (the one client call, `claude -p` at 00:10, was
non-interactive; every other round trip was driven by a script through the proxy); a launchd agent for the server; a rollback from the backup;
the uninstall steps; a check of how `markdown lint reject-errors` decides what to reject. The `claude mcp add` syntax is
now confirmed. The location of the Claude Desktop logs and the JSON-RPC handshake in step 5 were written from
general knowledge of those tools and are still the least certain parts.
