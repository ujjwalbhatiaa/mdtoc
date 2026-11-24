# mdtoc

A dependency-free Python CLI that generates a table of contents for a
Markdown file — GitHub-style anchors, fenced-code aware, idempotent
inserts.

## Install

No dependencies — just Python 3.8+:

```sh
python3 mdtoc.py --help
```

Or make it executable and put it on your `PATH`:

```sh
chmod +x mdtoc.py
```

## Usage

Print the TOC of a file to stdout:

```sh
python3 mdtoc.py README.md
```

```text
- [mdtoc](#mdtoc)
  - [Install](#install)
  - [Usage](#usage)
```

Read from stdin:

```sh
cat README.md | python3 mdtoc.py
```

Write (or refresh) the TOC inside the file, between markers:

```sh
python3 mdtoc.py README.md --insert
```

This inserts the block below right after the first `#` heading (or at the
top of the file when there is no H1), and replaces it on later runs:

```markdown
<!-- toc -->
- [mdtoc](#mdtoc)
  - [Install](#install)
<!-- /toc -->
```

Running `--insert` twice changes nothing — the operation is idempotent,
so it is safe in a pre-commit hook or CI step.

Verify the TOC is fresh (handy in CI):

```sh
python3 mdtoc.py README.md --check   # exit 0 = fresh, exit 1 = missing/stale
```

## Options

| Flag | Effect |
| --- | --- |
| `--insert` | Write/update the TOC in the file in place |
| `--check` | Exit 0 if the TOC is fresh, else 1 |
| `--min-depth N` | Shallowest heading level to include (default 1) |
| `--max-depth N` | Deepest heading level to include (default 6) |
| `--bullet -\|*` | List bullet character (default `-`) |

## How it works

- Only ATX headings (`#` … `######`) are collected; headings inside
  fenced code blocks (`` ``` `` or `~~~`) are ignored, and trailing
  closing hashes (`## Title ##`) are stripped.
- Anchors follow GitHub's rules: lowercase, punctuation removed, spaces
  become hyphens, repeated hyphens collapsed. Duplicate headings get
  `-1`, `-2`, … suffixes, exactly like GitHub renders them.
- Indentation is two spaces per level, relative to the shallowest
  heading included.

## Tests

```sh
python3 -m pytest tests/ -q
```

## License

MIT — see `LICENSE`.
