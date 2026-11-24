#!/usr/bin/env python3
"""mdtoc — generate a table of contents for a Markdown file.

Reads a Markdown file (or stdin), extracts ATX headings, and prints a
GitHub-style table of contents. With --insert it writes the TOC into the
file between <!-- toc --> and <!-- /toc --> markers (creating them after
the first H1 heading when absent). With --check it verifies the markers
hold a fresh TOC and exits non-zero when they do not.

Slugs follow GitHub's heading-anchor rules: lowercase, punctuation
removed, spaces become hyphens, duplicates get a -1, -2, ... suffix.

Usage:
    mdtoc README.md                  print the TOC to stdout
    mdtoc README.md --insert         write/update the TOC in place
    mdtoc README.md --check          exit 0 if the TOC is fresh, else 1
    mdtoc --max-depth 3 README.md    only headings up to ### (level 3)
    cat README.md | mdtoc            read from stdin
"""

import argparse
import re
import sys

TOC_START = "<!-- toc -->"
TOC_END = "<!-- /toc -->"

_ATX_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def slugify(title, seen):
    """GitHub-style anchor slug for a heading, deduplicated via `seen`."""
    slug = title.strip().lower()
    slug = _PUNCT_RE.sub("", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "section"
    base, n = slug, 1
    while slug in seen:
        slug = f"{base}-{n}"
        n += 1
    seen.add(slug)
    return slug


def extract_headings(lines):
    """Return [(level, title), ...] for ATX headings, skipping fenced code."""
    headings = []
    in_fence = False
    fence = None
    for line in lines:
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence, fence = True, marker
            elif marker == fence:
                in_fence, fence = False, None
            continue
        if in_fence:
            continue
        match = _ATX_RE.match(line.rstrip("\n"))
        if match:
            title = match.group(2).strip()
            if title:
                headings.append((len(match.group(1)), title))
    return headings


def build_toc(headings, min_depth=1, max_depth=6, bullet="-"):
    """Render TOC lines for headings within the depth window."""
    lines = []
    seen = set()
    base = None
    for level, title in headings:
        if level < min_depth or level > max_depth:
            continue
        if base is None:
            base = level
        slug = slugify(title, seen)
        indent = "  " * (level - base)
        lines.append(f"{indent}{bullet} [{title}](#{slug})")
    return lines


def find_markers(lines):
    """Return (start_index, end_index) of the toc markers, or (None, None)."""
    start = end = None
    for i, line in enumerate(lines):
        if TOC_START in line and start is None:
            start = i
        if TOC_END in line and end is None and start is not None:
            end = i
            break
    return start, end


def insert_toc(lines, toc_lines):
    """Return new lines with the TOC placed between markers.

    Replaces the content between existing markers, or inserts fresh
    markers (with the TOC) right after the first H1 heading — or at the
    top of the file when there is no H1.
    """
    start, end = find_markers(lines)
    block = [TOC_START] + toc_lines + [TOC_END]
    if start is not None and end is not None:
        return lines[: start + 1] + toc_lines + lines[end:]
    for i, line in enumerate(lines):
        if line.startswith("# "):
            return lines[: i + 1] + [""] + block + [""] + lines[i + 1 :]
    return block + [""] + lines


def check_toc(lines, toc_lines):
    """True when the markers exist and hold exactly the generated TOC."""
    start, end = find_markers(lines)
    if start is None or end is None:
        return False
    current = [line.rstrip("\n") for line in lines[start + 1 : end]]
    return current == toc_lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="mdtoc",
        description="Generate a table of contents for a Markdown file.",
    )
    parser.add_argument("file", nargs="?", default="-",
                        help="Markdown file to read (default: stdin)")
    parser.add_argument("--insert", action="store_true",
                        help="write/update the TOC in the file in place")
    parser.add_argument("--check", action="store_true",
                        help="exit 0 if the TOC is fresh, else 1")
    parser.add_argument("--min-depth", type=int, default=1,
                        help="shallowest heading level to include (default: 1)")
    parser.add_argument("--max-depth", type=int, default=6,
                        help="deepest heading level to include (default: 6)")
    parser.add_argument("--bullet", default="-", choices=["-", "*"],
                        help="list bullet character (default: -)")
    args = parser.parse_args(argv)

    if not 1 <= args.min_depth <= 6 or not 1 <= args.max_depth <= 6:
        print("mdtoc: depths must be between 1 and 6", file=sys.stderr)
        return 2
    if args.min_depth > args.max_depth:
        print("mdtoc: --min-depth must not exceed --max-depth", file=sys.stderr)
        return 2
    if (args.insert or args.check) and args.file == "-":
        print("mdtoc: --insert/--check need a file, not stdin", file=sys.stderr)
        return 2

    if args.file == "-":
        text = sys.stdin.read()
        lines = text.splitlines()
    else:
        try:
            with open(args.file, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except FileNotFoundError:
            print(f"mdtoc: no such file: {args.file}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"mdtoc: cannot read {args.file}: {exc}", file=sys.stderr)
            return 2

    toc_lines = build_toc(extract_headings(lines), args.min_depth,
                          args.max_depth, args.bullet)

    if args.insert:
        new_lines = insert_toc(lines, toc_lines)
        with open(args.file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(new_lines) + "\n")
        return 0
    if args.check:
        if check_toc(lines, toc_lines):
            print("mdtoc: table of contents is up to date")
            return 0
        print("mdtoc: table of contents is missing or stale", file=sys.stderr)
        return 1
    print("\n".join(toc_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
