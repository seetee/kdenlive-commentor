# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python tool (`kdenlive_commentor.py`) that extracts timestamped notes from Kdenlive project files (the `kdenlive:documentnotes` XML property) and merges them into a session Markdown file, repairing that file to a canonical skeleton on every run. Purpose-built for the **Samkväm** production workflow — it assumes the directory layout and session-file skeleton documented in README.md.

Python 3.10+ standard library only. No dependencies, no build step.

## Commands

```bash
python3 -m unittest                                  # run the test suite
python3 -m unittest tests.test_kdenlive_commentor.PlacementTests  # one test class
python3 kdenlive_commentor.py [dir]                  # run: session dir, parent dir, or bare from anywhere inside a session tree
```

Tests build synthetic `.kdenlive` fixtures in temp dirs (`SessionTree` helper in `tests/test_kdenlive_commentor.py`) — no committed fixture data.

## Architecture

The pipeline, all in `kdenlive_commentor.py`:

1. **Discovery** — `_discover` walks up from the start directory to find a session dir (name starts with `session_`, or contains `session_*.md`/`.txt`), falling back to scanning for `session_*` children. Episodes are subdirectories containing a same-named `.kdenlive` file, natural-sorted.

2. **Extraction** — `_extract_project` parses the `.kdenlive` XML, feeding the `kdenlive:documentnotes` Qt-richtext HTML into `_NotesParser` (an `html.parser.HTMLParser`). Headings at any level typed in Kdenlive's notes panel become section names; notes before any heading are collected under the internal `ORPHAN_SECTION` name and end up appended to the end of `#### Noteworthy` after a blank line (no separate section is written; `_prune_orphan_section` removes legacy empty/superseded ones). `<a>` tags carry `HH:MM:SS:FF` timestamps, converted to `MM:SS` (or `HH:MM:SS`) and sorted chronologically. It also reads `kdenlive:docproperties.kdenliveversion`. Per-episode parse errors warn and continue.

3. **Document model** — the session `.md` is parsed by `_parse` into a `_Block` tree (heading level/title + verbatim body lines + children) and rendered back with `_render`. A block ends at the next heading of same-or-higher level, so content after an episode under a `##`/`#` heading is never mistaken for episode content. Untouched blocks round-trip byte-for-byte.

4. **Skeleton repair** — `_ensure_skeleton` / `_ensure_episode` / `_ensure_metadata` / `_ensure_section` create anything missing: the `# Session …` title, `## Mjukvaruversioner` (seeded from `SOFTWARE_DEFAULTS` when empty), `## Avsnittsinfo`, and a `### <episode>` block with the `METADATA_FIELDS` lines per on-disk episode. `_ensure_metadata` also normalizes unbolded metadata lines (`Titel: x` → `**Titel:** x`) in place — never duplicating them. Only `#### Noteworthy` is created unconditionally; `Bryggpromenader` (and any custom section) only when notes exist for it.

5. **Managed updates** — `_set_bullets` rewrites a section's `* ` bullets (and the Bryggpromenader tally lines, auto-counted by `_tally` from `H+1`-style tokens); `_update_software` maintains the `* Kdenlive <version>` line. A per-episode release checklist is printed by `_print_report`.

## Key invariants

**Idempotency and non-destructiveness are the core contract**, and both are covered by tests — run the suite after any change to the merge logic. Rules:

- Script-managed lines only: `* ` bullets in a `####` section are replaced **only when that section has incoming notes this run**; the tally lines (`Joel:`/`Robin:`/`Henrik:`/`Kenneth:`) and the `* Kdenlive …` line are always script-managed. Everything else the user wrote must round-trip unchanged.
- Running twice must produce byte-identical output (`test_idempotent`).
- Heading levels are load-bearing: `## ` top-level sections, `### <episode-dir-name>`, `#### <section>` — section names must exactly match the headings typed in Kdenlive's notes panel.
