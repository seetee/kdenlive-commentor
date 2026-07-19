# kdenlive-commentor

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
* files notes typed **without** a section heading under
  `#### Other comments without a home`, so nothing is ever lost;
* repairs the session file to the canonical skeleton (see below) — creating it
  from scratch if it doesn't exist yet;
* keeps the `* Kdenlive …` line under `## Mjukvaruversioner` up to date with
  the version read from the project files;
* auto-counts the **Bryggpromenader** tally from `H+1`-style notes;
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

#### Other comments without a home
* a note typed without a section heading

#### Bryggpromenader
* 05:28 H+1
* 12:03 J+1

Joel: 1
Robin: 0
Henrik: 1
Kenneth: 0
```

`Noteworthy` and `Other comments without a home` always exist for every
episode. `Bryggpromenader` only appears when the episode actually has such
notes, and its tally (counted from `J+1` / `R+1` / `H+1` / `K+1` tokens) is
recomputed on every run. Any other section you create with a heading in
Kdenlive's Document Notes panel becomes an additional `####` section.

Missing metadata fields and headings are added automatically; values you've
already filled in are never touched.

## Usage

```bash
# From anywhere inside a session tree — the session dir, an episode dir, deeper…
python3 kdenlive_commentor.py

# …or point it at a session directory
python3 kdenlive_commentor.py /path/to/session_26_2025-06-30/

# …or at a parent directory to process all sessions
python3 kdenlive_commentor.py /path/to/recordings/
```

Each run ends with a release checklist:

```
  checklist:
    ✗ avsnitt207: fill in Blurb (short)  [Noteworthy 12, Bryggpromenader 3]
    ✓ avsnitt208: ready  [Noteworthy 8]
```

No external dependencies — just Python 3.10+ and its standard library.

## Tests

```bash
python3 -m unittest
```
