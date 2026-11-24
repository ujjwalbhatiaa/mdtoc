"""Tests for mdtoc — Markdown table-of-contents generator."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mdtoc

SAMPLE = """# Project

Intro text.

## Getting Started

### Install

## Usage

### Basic

### Advanced

# Appendix
"""


def run_cli(*argv, stdin=None):
    return subprocess.run(
        [sys.executable, str(Path(mdtoc.__file__)), *argv],
        input=stdin, capture_output=True, text=True, check=False,
    )


# --- slugify ---

def test_slug_basic():
    assert mdtoc.slugify("Hello World", set()) == "hello-world"


def test_slug_strips_punctuation():
    assert mdtoc.slugify("What's New in C++?", set()) == "whats-new-in-c"


def test_slug_keeps_underscores_and_numbers():
    assert mdtoc.slugify("Step 2: setup_env", set()) == "step-2-setup_env"


def test_slug_collapses_hyphens_and_spaces():
    assert mdtoc.slugify("a  --  b", set()) == "a-b"


def test_slug_duplicates_get_suffixes():
    seen = set()
    assert mdtoc.slugify("Setup", seen) == "setup"
    assert mdtoc.slugify("Setup", seen) == "setup-1"
    assert mdtoc.slugify("Setup", seen) == "setup-2"


def test_slug_empty_title_falls_back():
    assert mdtoc.slugify("!!!", set()) == "section"


# --- heading extraction ---

def test_extract_atx_levels():
    lines = ["# One", "## Two", "###### Six", "####### Seven"]
    assert mdtoc.extract_headings(lines) == [(1, "One"), (2, "Two"), (6, "Six")]


def test_extract_strips_closing_hashes():
    assert mdtoc.extract_headings(["## Title ##"]) == [(2, "Title")]


def test_extract_ignores_code_fences():
    lines = ["# Real", "```", "# Not a heading", "```", "## Also real",
             "~~~", "## Hidden", "~~~", "# End"]
    assert mdtoc.extract_headings(lines) == [
        (1, "Real"), (2, "Also real"), (1, "End")]


def test_extract_ignores_empty_heading():
    assert mdtoc.extract_headings(["# ", "## Real"]) == [(2, "Real")]


# --- TOC rendering ---

def test_build_toc_indentation_and_links():
    headings = [(1, "Project"), (2, "Getting Started"), (3, "Install")]
    assert mdtoc.build_toc(headings) == [
        "- [Project](#project)",
        "  - [Getting Started](#getting-started)",
        "    - [Install](#install)",
    ]


def test_build_toc_depth_window():
    headings = [(1, "A"), (2, "B"), (3, "C")]
    assert mdtoc.build_toc(headings, min_depth=2, max_depth=2) == ["- [B](#b)"]


def test_build_toc_star_bullet():
    assert mdtoc.build_toc([(1, "A")], bullet="*") == ["* [A](#a)"]


def test_build_toc_duplicate_titles():
    headings = [(1, "Setup"), (2, "Setup"), (2, "Setup")]
    assert mdtoc.build_toc(headings) == [
        "- [Setup](#setup)",
        "  - [Setup](#setup-1)",
        "  - [Setup](#setup-2)",
    ]


# --- insert / check ---

def test_insert_after_first_h1_when_no_markers():
    lines = SAMPLE.splitlines()
    toc = mdtoc.build_toc(mdtoc.extract_headings(lines))
    out = mdtoc.insert_toc(lines, toc)
    assert out[0] == "# Project"
    assert out[1] == ""
    assert out[2] == "<!-- toc -->"
    assert out[3] == "- [Project](#project)"
    assert "<!-- /toc -->" in out


def test_insert_at_top_when_no_h1():
    lines = ["Some text.", "", "## Section"]
    out = mdtoc.insert_toc(lines, ["- [Section](#section)"])
    assert out[0] == "<!-- toc -->"
    assert out[1] == "- [Section](#section)"
    assert out[2] == "<!-- /toc -->"


def test_insert_replaces_stale_toc():
    lines = ["# T", "", "<!-- toc -->", "- [Old](#old)", "<!-- /toc -->",
             "", "## New"]
    out = mdtoc.insert_toc(lines, ["- [T](#t)", "  - [New](#new)"])
    assert out == ["# T", "", "<!-- toc -->", "- [T](#t)",
                   "  - [New](#new)", "<!-- /toc -->", "", "## New"]


def test_insert_is_idempotent():
    lines = SAMPLE.splitlines()
    toc = mdtoc.build_toc(mdtoc.extract_headings(lines))
    once = mdtoc.insert_toc(lines, toc)
    twice = mdtoc.insert_toc(once, toc)
    assert once == twice


def test_check_fresh_and_stale():
    lines = SAMPLE.splitlines()
    toc = mdtoc.build_toc(mdtoc.extract_headings(lines))
    assert mdtoc.check_toc(lines, toc) is False  # no markers yet
    inserted = mdtoc.insert_toc(lines, toc)
    assert mdtoc.check_toc(inserted, toc) is True
    stale = inserted[:]
    stale[3] = "- [Wrong](#wrong)"
    assert mdtoc.check_toc(stale, toc) is False


# --- CLI end to end ---

def test_cli_prints_toc(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(SAMPLE)
    result = run_cli(str(doc))
    assert result.returncode == 0
    assert "- [Project](#project)" in result.stdout
    assert "  - [Getting Started](#getting-started)" in result.stdout
    assert "    - [Install](#install)" in result.stdout


def test_cli_stdin():
    result = run_cli(stdin="# Hi\n\n## There\n")
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "- [Hi](#hi)", "  - [There](#there)"]


def test_cli_insert_and_check_roundtrip(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(SAMPLE)
    assert run_cli(str(doc), "--insert").returncode == 0
    text = doc.read_text()
    assert "<!-- toc -->" in text and "<!-- /toc -->" in text
    assert run_cli(str(doc), "--check").returncode == 0
    # Second insert must not change the file.
    before = doc.read_text()
    assert run_cli(str(doc), "--insert").returncode == 0
    assert doc.read_text() == before


def test_cli_check_fails_when_stale(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(SAMPLE)
    run_cli(str(doc), "--insert")
    doc.write_text(doc.read_text() + "\n## Brand New Section\n")
    result = run_cli(str(doc), "--check")
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_cli_max_depth(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(SAMPLE)
    result = run_cli(str(doc), "--max-depth", "2")
    assert result.returncode == 0
    assert "Install" not in result.stdout
    assert "Getting Started" in result.stdout


def test_cli_missing_file():
    result = run_cli("no-such-file.md")
    assert result.returncode == 2
    assert "no such file" in result.stderr


def test_cli_insert_needs_a_file():
    result = run_cli("--insert", stdin="# Hi\n")
    assert result.returncode == 2


def test_cli_bad_depth():
    result = run_cli("--max-depth", "9", stdin="# Hi\n")
    assert result.returncode == 2
