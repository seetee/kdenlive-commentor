# kdenlive-commentor

[![Tests](https://github.com/seetee/kdenlive-commentor/actions/workflows/test.yml/badge.svg)](https://github.com/seetee/kdenlive-commentor/actions/workflows/test.yml)
[![Vibe Coded](https://img.shields.io/badge/vibe-coded-blueviolet)](https://en.wikipedia.org/wiki/Vibe_coding)
[![Built with Claude](https://img.shields.io/badge/built%20with-Claude-D97757)](https://claude.ai)

A small Python tool that pulls the timestamped notes you write during Kdenlive
episode editing and drops them straight into your session's Markdown file — in
the right place, every time, no matter how many times you run it. It also keeps
the session file itself in shape: missing files, headings, and metadata fields
are created and repaired automatically on every run.

## What it does

When editing a multi-episode project in Kdenlive, you can use the built-in
**Document Notes** panel to jot down memorable moments, funny quotes, and
anything else worth keeping track of — complete with clickable timestamps.
This script reads those notes and writes them into your session's `.md` file
under the correct episode heading, ready for use in video descriptions, social
media posts, or wherever you need them.

On every run it:

* converts Kdenlive's internal timestamp format (`00:06:29:32`) to a clean
  `MM:SS` format (or `HH:MM:SS` past the hour) and sorts notes chronologically;
* strips all the HTML that Kdenlive wraps around the notes;
* appends notes typed **without** a section heading to the end of
  `#### Noteworthy` (after a blank line), so nothing is ever lost;
* repairs the session file to the canonical skeleton (see below) — creating it
  from scratch if it doesn't exist yet, and normalizing metadata lines written
  without bold markers (`Titel: …` becomes `**Titel:** …` in place);
* keeps the `* Kdenlive …` line under `## Mjukvaruversioner` up to date with
  the version read from the project files;
* auto-counts the **Bryggpromenader** tally from `H+1`-style notes;
* builds a paste-ready **YouTube chapter list** (`#### Kapitel`) per episode
  from the Bryggpromenader entries and any note you star (see below);
* prints a per-episode release checklist so you instantly see what still needs
  filling in.

Run it again after adding more notes? Go ahead. Only script-managed lines (note
bullets, the tally, the Kdenlive version line) are ever replaced. Everything
you wrote by hand — titles, blurbs, trailers, stray sections — stays exactly
where you put it.

## Built specifically for Samkväm

This tool is purpose-built around the **Samkväm** production workflow. It won't
work out of the box with a differently structured project — it expects the
directory layout and file naming convention below. If you're not producing
Samkväm, you're welcome to adapt the script to fit your own setup — it's short
and straightforward.

## Directory structure

```
recordings/
└── session_26_2025-06-30/
    ├── session_26_2025-06-30.md         ← session notes file (created if missing)
    ├── session_26_2025-06-30.kdenlive   ← main rough-cut project (not processed)
    ├── sources/                          ← raw recordings (not processed)
    ├── avsnitt207/
    │   ├── avsnitt207.kdenlive          ← episode project with notes ✓
    │   └── ...
    └── avsnitt208/
        ├── avsnitt208.kdenlive          ← episode project with notes ✓
        └── ...
```

The rule is simple: any subdirectory whose name matches the `.kdenlive` file
inside it is treated as an episode and processed. Everything else is left
alone. Episodes are sorted naturally (`avsnitt9` before `avsnitt10`).

## Session file format

The script creates and maintains this skeleton:

```markdown
# Session 26 - 2025-06-30

## Mjukvaruversioner

* Prism Launcher 9.2
* Project Ozone 3 3.4.10
* Minecraft 1.12.2
* Resource packs
  * Faithful 32x
  * Faithful Mods - Project Ozone 3
  * Ozone Resources 3
* OBS 23.0.3
* Kdenlive 25.04.2

## Avsnittsinfo

### avsnitt207

**Titel:**
**Blurb (large):**
**Blurb (short):**
**Trailer:**

#### Noteworthy
* 06:29 A memorable quote -h
* 14:46 Something worth clipping -k

* a note typed without a section heading

#### Bryggpromenader
* 05:28 H+1
* 12:03 J+1

Joel: 1
Robin: 0
Henrik: 1
Kenneth: 0

#### Kapitel
00:00 Äventyret börjar!
05:28 Henrik tar en lång promenad på en kort brygga
06:29 Grottan öppnas
12:03 Joel tar en lång promenad på en kort brygga
```

`Noteworthy` always exists for every episode; notes typed without a section
heading are appended to its end after a blank line. `Bryggpromenader` only
appears when the episode actually has such notes, and its tally (counted from
`J+1` / `R+1` / `H+1` / `K+1` tokens) is recomputed on every run. Any other
section you create with a heading in Kdenlive's Document Notes panel becomes
an additional `####` section.

Missing metadata fields and headings are added automatically; values you've
already filled in are never touched. Metadata lines written without bold
markers (`Titel: …`) are normalized in place.

### YouTube chapters

The `#### Kapitel` section is a chapter list ready to paste into a YouTube
description. It always opens with `00:00 Äventyret börjar!`, every
Bryggpromenader entry becomes a chapter named after who walked the plank, and
you can flag any other note as a chapter by typing a `*` directly after the
timestamp in Kdenlive's Document Notes panel:

```
00:06:29:32* Grottan öppnas -h
```

The `*` is stripped from the note bullet, and the trailing speaker token
(`-h`) is dropped from the chapter title. The section only appears when there
is at least one real chapter. Note YouTube's rules: chapters are recognized
only with at least 3 entries, the first at `00:00`, each ≥10 seconds long.

## Install

```bash
pipx install git+https://github.com/seetee/kdenlive-commentor.git
```

…or skip installing and run the script directly with `python3 kdenlive_commentor.py`.

## Usage

```bash
# From anywhere inside a session tree — the session dir, an episode dir, deeper…
kdenlive-commentor

# …or point it at a session directory
kdenlive-commentor /path/to/session_26_2025-06-30/

# …or at a parent directory to process all sessions
kdenlive-commentor /path/to/recordings/

# Preview what would change as a diff, without writing anything
kdenlive-commentor --dry-run

# Print an episode's metadata and notes for copy-pasting, then exit
kdenlive-commentor --show avsnitt207
```

Each run ends with a release checklist:

```
  checklist:
    ✗ avsnitt207: fill in Blurb (short)  [Noteworthy 12, Bryggpromenader 3]
    ✓ avsnitt208: ready  [Noteworthy 8]
```

Safety details:

* Before the session file is modified, the previous version is saved next to it
  as `<name>.md.bak`, and the write itself is atomic (a crash can never leave a
  half-written file).
* The exit code is non-zero when any warning was printed (unreadable project
  file, or a `### avsnittXXX` section with no matching directory — e.g. after
  renaming an episode folder).

No external dependencies — just Python 3.10+ and its standard library.

## Tests

```bash
python3 -m unittest
```
