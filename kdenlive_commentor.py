#!/usr/bin/env python3
"""
Extract Kdenlive episode notes into the session Markdown file.

Usage:
    kdenlive_notes.py [SESSION_DIR | PARENT_DIR]

Given a session directory (one that contains session_*.md or session_*.txt),
updates the session file with notes extracted from each episode subdirectory's
.kdenlive file.  Given a parent directory, processes all session_* children.

The session file is left structurally intact on every run — only the bullet
lines (lines starting with '* ') inside script-managed sections are replaced.
Everything else (titles, blurbs, trailers, tallies, blank lines) is kept.

If only a session_*.txt exists, a session_*.md is created from it on first run.
"""

import re
import sys
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
from html.parser import HTMLParser


# ── HTML parsing ──────────────────────────────────────────────────────────────

class _NotesParser(HTMLParser):
    """Parse Kdenlive Qt-richtext HTML into {section: [(timestamp, text)]}."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections: dict[str, list[tuple[str, str]]] = {}
        self._section: str | None = None
        self._in_a = False
        self._a_text = ''
        self._p_text = ''
        self._timestamp: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag == 'p':
            self._p_text = ''
            self._timestamp = None
        elif tag == 'a':
            self._in_a = True
            self._a_text = ''

    def handle_endtag(self, tag):
        if tag == 'a':
            self._in_a = False
            m = re.search(r'(\d{2}):(\d{2}):(\d{2}):\d+', self._a_text)
            if m:
                h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
                self._timestamp = f'{h:02d}:{mi:02d}:{s:02d}' if h else f'{mi:02d}:{s:02d}'
        elif tag == 'p':
            text = self._p_text.strip()
            if text.startswith('## '):
                name = text[3:].strip()
                self._section = name
                self.sections.setdefault(name, [])
            elif self._timestamp is not None and self._section is not None and text:
                self.sections[self._section].append((self._timestamp, text))

    def handle_data(self, data):
        if self._in_a:
            self._a_text += data
        else:
            self._p_text += data


def _extract_notes(kdenlive_path: Path) -> dict[str, list[tuple[str, str]]]:
    """Return {section_name: [(timestamp, quote)]} from a .kdenlive file."""
    root = ET.parse(kdenlive_path).getroot()
    prop = root.find(".//property[@name='kdenlive:documentnotes']")
    if prop is None or not prop.text:
        return {}
    parser = _NotesParser()
    parser.feed(prop.text)
    return parser.sections


# ── Markdown update ───────────────────────────────────────────────────────────

def _replace_section_bullets(
    text: str, episode: str, section: str, bullets: list[str]
) -> tuple[str, bool]:
    """
    Within ### episode, replace all '* ' lines inside #### section with bullets.
    Non-bullet lines (blank lines, tallies, etc.) are preserved.
    Returns (updated_text, section_was_found).
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_ep = in_sec = found = False

    for line in lines:
        s = line.rstrip()

        if re.match(r'^### \S', line):
            in_ep = (s == f'### {episode}')
            in_sec = False
        elif in_ep and re.match(r'^#### ', line):
            in_sec = (s == f'#### {section}')
            out.append(line)
            if in_sec:
                found = True
                for b in bullets:
                    out.append(b + '\n')
            continue

        if in_sec and s.startswith('* '):
            continue  # drop old bullets; new ones already written above

        out.append(line)

    return ''.join(out), found


def _insert_section(text: str, episode: str, section: str, bullets: list[str]) -> str:
    """
    Append a new #### section at the end of ### episode.
    Also strips naked bullet lines (not under a ####) from the episode block —
    these are pre-existing unstructured bullets that the new section replaces.
    Appending (rather than inserting after metadata) preserves order when called
    multiple times for different sections.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_ep = False
    in_subsec = False
    ep_end = -1

    for line in lines:
        s = line.rstrip()
        if re.match(r'^### \S', line):
            if in_ep:
                # Leaving the episode — record its end (last non-blank line)
                ep_end = len(out)
                while ep_end > 0 and not out[ep_end - 1].strip():
                    ep_end -= 1
            in_ep = (s == f'### {episode}')
            in_subsec = False
        elif in_ep and re.match(r'^#### ', line):
            in_subsec = True

        if in_ep and not in_subsec and s.startswith('* '):
            continue  # remove naked bullets; they belong in a structured section

        out.append(line)

    if in_ep:
        ep_end = len(out)
        while ep_end > 0 and not out[ep_end - 1].strip():
            ep_end -= 1

    if ep_end == -1:
        return ''.join(out)  # episode heading not found, leave unchanged

    insert = ['\n', f'#### {section}\n'] + [b + '\n' for b in bullets]
    out[ep_end:ep_end] = insert
    return ''.join(out)


def _update_session(
    md_path: Path, episode: str, notes: dict[str, list[tuple[str, str]]]
) -> None:
    """Write all extracted note sections for one episode into the session file."""
    text = md_path.read_text(encoding='utf-8')
    for section, entries in notes.items():
        if not entries:
            continue
        bullets = [f'* {ts} {quote}' for ts, quote in entries]
        text, found = _replace_section_bullets(text, episode, section, bullets)
        if not found:
            text = _insert_section(text, episode, section, bullets)
    md_path.write_text(text, encoding='utf-8')


# ── Session discovery ─────────────────────────────────────────────────────────

def _bootstrap_md(session_dir: Path, episode_dirs: list[Path]) -> Path:
    """Create a minimal session .md from the directory name and found episodes."""
    name = session_dir.name  # e.g. session_26_2025-06-30
    md = session_dir / f'{name}.md'
    # Derive a human-readable title: "Session 26 - 2025-06-30"
    title = name.replace('_', ' ', 1).replace('_', ' - ', 1).title()
    lines = [f'# {title}\n', '\n', '## Avsnittsinfo\n']
    for ep_dir in episode_dirs:
        lines += [
            '\n',
            f'### {ep_dir.name}\n',
            '\n',
            '**Titel:**\n',
            '**Blurb (large):**\n',
            '**Blurb (short):**\n',
            '**Trailer:**\n',
        ]
    md.write_text(''.join(lines), encoding='utf-8')
    print(f'  created {md.name}')
    return md


def _find_or_create_md(session_dir: Path, episode_dirs: list[Path]) -> Path:
    md = next(iter(sorted(session_dir.glob('session_*.md'))), None)
    if md:
        return md
    txt = next(iter(sorted(session_dir.glob('session_*.txt'))), None)
    if txt:
        md = txt.with_suffix('.md')
        md.write_text(txt.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'  created {md.name} from {txt.name}')
        return md
    return _bootstrap_md(session_dir, episode_dirs)


def process_session(session_dir: Path) -> None:
    print(f'session: {session_dir.name}')

    episode_dirs = sorted(
        d for d in session_dir.iterdir()
        if d.is_dir() and (d / f'{d.name}.kdenlive').exists()
    )

    if not episode_dirs:
        print('  no episode subdirectories found')
        return

    md = _find_or_create_md(session_dir, episode_dirs)

    for ep_dir in episode_dirs:
        ep_name = ep_dir.name
        notes = _extract_notes(ep_dir / f'{ep_name}.kdenlive')
        total = sum(len(v) for v in notes.values())
        if not total:
            print(f'  {ep_name}: no notes')
            continue
        _update_session(md, ep_name, notes)
        sections = ', '.join(f'{s} ({len(e)})' for s, e in notes.items() if e)
        print(f'  {ep_name}: {sections} → {md.name}')


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='session directory or parent of session directories (default: .)',
    )
    args = ap.parse_args()

    root = Path(args.directory).resolve()
    if not root.is_dir():
        sys.exit(f'error: {root} is not a directory')

    is_session = (
        root.name.startswith('session_')
        or bool(next(iter(root.glob('session_*.md')), None))
        or bool(next(iter(root.glob('session_*.txt')), None))
    )

    if is_session:
        process_session(root)
    else:
        sessions = sorted(d for d in root.iterdir() if d.is_dir() and d.name.startswith('session_'))
        if not sessions:
            sys.exit(f'error: no session_* directories found in {root}')
        for s in sessions:
            process_session(s)


if __name__ == '__main__':
    main()
