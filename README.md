# kdenlive-commentor

[![Vibe Coded](https://img.shields.io/badge/vibe-coded-blueviolet)](https://en.wikipedia.org/wiki/Vibe_coding)
[![Built with Claude](https://img.shields.io/badge/built%20with-Claude-D97757)](https://claude.ai)

A small Python tool that pulls the timestamped notes you write during Kdenlive episode editing and drops them straight into your session's Markdown file — in the right place, every time, no matter how many times you run it.

## What it does

When editing a multi-episode project in Kdenlive, you can use the built-in **Document Notes** panel to jot down memorable moments, funny quotes, and anything else worth keeping track of — complete with clickable timestamps. This script reads those notes and writes them into your session's `.md` file under the correct episode heading, ready for use in video descriptions, social media posts, or wherever you need them.

It converts Kdenlive's internal timestamp format (`V1 00:06:29:32`) to a clean `MM:SS` format, strips all the HTML that Kdenlive wraps around the notes, and leaves everything else in your session file completely untouched — titles, blurbs, trailers, tallies, all of it.

Run it again after adding more notes? Go ahead. Only the bullet lines get replaced. Everything else stays exactly where you put it.

## Built specifically for Samkväm

This tool is purpose-built around the **Samkväm** production workflow. It won't work out of the box with a differently structured project — it expects a specific directory layout and file naming convention that matches how Samkväm sessions and episodes are organised.

If you're not producing Samkväm, you're welcome to adapt the script to fit your own setup — it's short and straightforward.

## Directory structure

Sessions and episodes need to be laid out like this:

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

The rule is simple: any subdirectory whose name matches the `.kdenlive` file inside it is treated as an episode and processed. Everything else is left alone.

## Session file format

The session `.md` file should have episode sections that look like this:

```markdown
### avsnitt207

**Titel:** Episode title here
**Blurb (large):** The long description for YouTube...
**Blurb (short):** A short teaser line
**Trailer:** What the trailer clip covers
```

After running the script, notes from `avsnitt207.kdenlive` are inserted under `#### Noteworthy` (and any other sections you've created with `## Section Name` in Kdenlive's Document Notes panel):

```markdown
### avsnitt207

**Titel:** Episode title here
**Blurb (large):** The long description for YouTube...
**Blurb (short):** A short teaser line
**Trailer:** What the trailer clip covers

#### Noteworthy
* 06:29 A memorable quote from the episode -h
* 07:12 Another great moment -j
* 14:46 Something worth clipping -k

#### Bryggpromenader
* 05:28 H+1
```

If there's no session file yet, the script creates a minimal one from the session directory name and the episode directories it finds — just fill in the metadata and you're good to go.

## Usage

```bash
# Process a single session directory
python3 kdenlive_commentor.py /path/to/session_26_2025-06-30/

# Process all sessions under a parent directory
python3 kdenlive_commentor.py /path/to/recordings/

# Run from inside a session directory
python3 kdenlive_commentor.py
```

No external dependencies — just Python 3.10+ and its standard library.
