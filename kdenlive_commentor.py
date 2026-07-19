#!/usr/bin/env python3
"""
Sync Kdenlive episode notes into the Samkväm session Markdown file.

Usage:
    kdenlive_commentor.py [DIRECTORY]

Run it from anywhere inside a session tree (the session directory itself, an
episode subdirectory, or deeper) and it finds the session automatically.
Given a directory containing session_* children, all of them are processed.

On every run the session file is created if missing and repaired to the
canonical skeleton:

    # Session XX - YYYY-MM-DD

    ## Mjukvaruversioner

    ## Avsnittsinfo

    ### avsnittXXX

    **Titel:**
    **Blurb (large):**
    **Blurb (short):**
    **Trailer:**

    #### Noteworthy
    #### Bryggpromenader        (only when the episode has such notes)

Notes typed without a section heading in Kdenlive's Document Notes panel are
appended to the end of "Noteworthy" after a blank line.  A Bryggpromenader
section gets an auto-counted tally (Joel/Robin/Henrik/Kenneth, from tokens
like "H+1").  Metadata lines written without bold markers ("Titel: …") are
normalized in place to the bold form.

Only script-managed lines are ever rewritten: the '* ' bullets of sections
that have incoming notes, the Bryggpromenader tally, and the '* Kdenlive …'
version line.  Everything written by hand is preserved.  A per-episode
completeness checklist is printed after each run.
"""

import argparse
import difflib
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

__version__ = '1.0.0'


def _version() -> str:
    try:
        from importlib.metadata import version
        return version('kdenlive-commentor')
    except Exception:
        return __version__


ORPHAN_SECTION = 'Other comments without a home'
BRYGG_SECTION = 'Bryggpromenader'
STANDARD_SECTIONS = ['Noteworthy', ORPHAN_SECTION, BRYGG_SECTION]
METADATA_FIELDS = ['Titel', 'Blurb (large)', 'Blurb (short)', 'Trailer']
TALLY_NAMES = [('J', 'Joel'), ('R', 'Robin'), ('H', 'Henrik'), ('K', 'Kenneth')]

SOFTWARE_DEFAULTS = [
    '* Prism Launcher 9.2',
    '* Project Ozone 3 3.4.10',
    '* Minecraft 1.12.2',
    '* Resource packs',
    '  * Faithful 32x',
    '  * Faithful Mods - Project Ozone 3',
    '  * Ozone Resources 3',
    '* OBS 23.0.3',
]

_HEADING_RE = re.compile(r'^(#{1,6})\s+(\S.*?)\s*$')
_META_RE = re.compile(r'^\*\*(.+?):\*\*')
_META_FILLED_RE = re.compile(r'^\*\*(.+?):\*\*\s*\S')
_TALLY_LINE_RE = re.compile(r'^(Joel|Robin|Henrik|Kenneth)\s*:')
_TALLY_TOKEN_RE = re.compile(r'\b([JRHK])\s*\+\s*(\d+)', re.IGNORECASE)
_KDENLIVE_LINE_RE = re.compile(r'^\*\s+Kdenlive\b')


def _natural_key(name: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


# ── Kdenlive project extraction ───────────────────────────────────────────────

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
            # Collapse internal whitespace: embedded newlines would otherwise
            # produce lines the merge logic no longer recognizes as managed.
            text = re.sub(r'\s+', ' ', self._p_text).strip()
            if not text:
                return
            m = re.match(r'^#{1,6}\s+(.+)', text)
            if m:
                name = m.group(1).strip()
                self._section = name
                self.sections.setdefault(name, [])
            else:
                section = self._section if self._section is not None else ORPHAN_SECTION
                self.sections.setdefault(section, []).append((self._timestamp or '', text))

    def handle_data(self, data):
        if self._in_a:
            self._a_text += data
        else:
            self._p_text += data


def _ts_seconds(ts: str) -> float:
    if not ts:
        return float('inf')  # untimestamped notes sort after timestamped ones
    seconds = 0
    for part in ts.split(':'):
        seconds = seconds * 60 + int(part)
    return seconds


def _extract_project(kdenlive_path: Path) -> tuple[dict[str, list[tuple[str, str]]], str | None]:
    """Return ({section: [(timestamp, text)]}, kdenlive_version) from a .kdenlive file."""
    root = ET.parse(kdenlive_path).getroot()

    version = None
    vprop = root.find(".//property[@name='kdenlive:docproperties.kdenliveversion']")
    if vprop is not None and vprop.text and vprop.text.strip():
        version = vprop.text.strip()

    notes: dict[str, list[tuple[str, str]]] = {}
    prop = root.find(".//property[@name='kdenlive:documentnotes']")
    if prop is not None and prop.text:
        parser = _NotesParser()
        parser.feed(prop.text)
        notes = {
            section: sorted(entries, key=lambda e: _ts_seconds(e[0]))
            for section, entries in parser.sections.items() if entries
        }
    return notes, version


# ── Markdown document model ───────────────────────────────────────────────────

class _Block:
    """A heading and its content: verbatim body lines plus nested sub-blocks."""

    __slots__ = ('level', 'title', 'heading_line', 'lines', 'children')

    def __init__(self, level: int, title: str, heading_line: str | None = None):
        self.level = level
        self.title = title
        self.heading_line = heading_line
        self.lines: list[str] = []
        self.children: list['_Block'] = []


def _parse(text: str) -> _Block:
    root = _Block(0, '')
    stack = [root]
    for line in text.splitlines(keepends=True):
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            while stack[-1].level >= level:
                stack.pop()
            block = _Block(level, m.group(2), line)
            stack[-1].children.append(block)
            stack.append(block)
        else:
            stack[-1].lines.append(line)
    return root


def _render(block: _Block) -> str:
    parts = []
    if block.heading_line:
        parts.append(block.heading_line)
    parts.extend(block.lines)
    parts.extend(_render(child) for child in block.children)
    return ''.join(parts)


def _new_block(level: int, title: str) -> _Block:
    block = _Block(level, title, f'{"#" * level} {title}\n')
    block.lines = ['\n']
    return block


def _find_block(block: _Block, level: int, title: str) -> _Block | None:
    for child in block.children:
        if child.level == level and child.title == title:
            return child
        found = _find_block(child, level, title)
        if found:
            return found
    return None


def _locate(block: _Block, target: _Block) -> tuple[_Block, int] | None:
    for i, child in enumerate(block.children):
        if child is target:
            return block, i
        found = _locate(child, target)
        if found:
            return found
    return None


def _insert_child(parent: _Block, pos: int, block: _Block) -> None:
    """Insert a child block, ensuring a blank line precedes its heading."""
    if pos == 0:
        if parent.lines and parent.lines[-1].strip():
            parent.lines.append('\n')
        elif not parent.lines and parent.heading_line:
            parent.lines.append('\n')
    else:
        prev = parent.children[pos - 1]
        while prev.children:
            prev = prev.children[-1]
        if not prev.lines or prev.lines[-1].strip():
            prev.lines.append('\n')
    parent.children.insert(pos, block)


# ── Skeleton repair ───────────────────────────────────────────────────────────

def _session_title(dirname: str) -> str:
    m = re.match(r'^session_(\d+)_(.+)$', dirname)
    return f'Session {m.group(1)} - {m.group(2)}' if m else dirname


def _ensure_skeleton(root: _Block, title: str) -> tuple[_Block, _Block]:
    """Ensure # title, ## Mjukvaruversioner and ## Avsnittsinfo exist."""
    h1 = next((c for c in root.children if c.level == 1), None)
    if h1 is None:
        h1 = _new_block(1, title)
        _insert_child(root, 0, h1)

    software = _find_block(root, 2, 'Mjukvaruversioner')
    if software is None:
        software = _new_block(2, 'Mjukvaruversioner')
        software.lines = []
        _insert_child(h1, 0, software)

    info = _find_block(root, 2, 'Avsnittsinfo')
    if info is None:
        info = _new_block(2, 'Avsnittsinfo')
        parent, idx = _locate(root, software)
        _insert_child(parent, idx + 1, info)

    return software, info


def _ensure_episode(root: _Block, info: _Block, name: str) -> _Block:
    episode = _find_block(root, 3, name)
    if episode is not None:
        return episode
    episode = _Block(3, name, f'### {name}\n')
    episode.lines = ['\n'] + [f'**{f}:**\n' for f in METADATA_FIELDS] + ['\n']
    pos = len(info.children)
    for i, child in enumerate(info.children):
        if child.level == 3 and _natural_key(child.title) > _natural_key(name):
            pos = i
            break
    _insert_child(info, pos, episode)
    return episode


def _ensure_metadata(episode: _Block) -> None:
    # Normalize unbolded metadata lines ("Titel: x") to the bold form in place.
    for i, line in enumerate(episode.lines):
        for field in METADATA_FIELDS:
            m = re.match(rf'^{re.escape(field)}\s*:\s*(.*?)\s*$', line)
            if m:
                value = m.group(1)
                episode.lines[i] = f'**{field}:** {value}\n' if value else f'**{field}:**\n'
                break

    present = set()
    last_meta = None
    for i, line in enumerate(episode.lines):
        m = _META_RE.match(line)
        if m:
            present.add(m.group(1))
            last_meta = i
    missing = [f for f in METADATA_FIELDS if f not in present]
    if not missing:
        return
    insert = [f'**{f}:**\n' for f in missing]
    if last_meta is not None:
        pos = last_meta + 1
    else:
        pos = 0
        while pos < len(episode.lines) and not episode.lines[pos].strip():
            pos += 1
        if pos == 0:
            insert = ['\n'] + insert
    episode.lines[pos:pos] = insert
    end = pos + len(insert)
    if end >= len(episode.lines) or episode.lines[end].strip():
        episode.lines.insert(end, '\n')


def _ensure_section(episode: _Block, name: str) -> _Block:
    for child in episode.children:
        if child.title == name:
            return child
    block = _new_block(4, name)
    if name in STANDARD_SECTIONS:
        rank = STANDARD_SECTIONS.index(name)
        pos = 0
        for i, child in enumerate(episode.children):
            if child.title in STANDARD_SECTIONS and STANDARD_SECTIONS.index(child.title) < rank:
                pos = i + 1
    else:
        pos = len(episode.children)
    _insert_child(episode, pos, block)
    return block


# ── Managed content updates ───────────────────────────────────────────────────

def _tally(entries: list[tuple[str, str]]) -> list[tuple[str, int]]:
    counts = {full: 0 for _, full in TALLY_NAMES}
    by_initial = {initial: full for initial, full in TALLY_NAMES}
    for _, text in entries:
        for initial, num in _TALLY_TOKEN_RE.findall(text):
            counts[by_initial[initial.upper()]] += int(num)
    return [(full, counts[full]) for _, full in TALLY_NAMES]


def _bullet(entry: tuple[str, str]) -> str:
    ts, text = entry
    return f'* {ts} {text}' if ts else f'* {text}'


def _set_bullets(section: _Block, bullets: list[str],
                 tally: list[tuple[str, int]] | None = None,
                 appendix: list[str] | None = None) -> None:
    """Replace the managed lines of a section, keeping hand-written extras."""
    extra = [
        line for line in section.lines
        if line.strip() and not line.startswith('* ') and not _TALLY_LINE_RE.match(line)
    ]
    lines = [f'{b}\n' for b in bullets]
    if appendix:
        lines += ['\n'] + [f'{b}\n' for b in appendix]
    if tally is not None:
        lines += ['\n'] + [f'{name}: {count}\n' for name, count in tally]
    if extra:
        lines += ['\n'] + extra
    lines.append('\n')
    section.lines = lines


def _prune_orphan_section(episode: _Block, incoming_bullets: set[str]) -> None:
    """
    Drop a legacy 'Other comments without a home' section when it is empty or
    contains nothing but bullets now emitted at the end of Noteworthy.  A
    section holding any other hand-written content is left untouched.
    """
    for i, child in enumerate(episode.children):
        if child.title == ORPHAN_SECTION and not child.children:
            leftover = [
                line for line in child.lines
                if line.strip() and line.strip() not in incoming_bullets
            ]
            if not leftover:
                del episode.children[i]
            return


def _update_software(software: _Block, version: str | None) -> None:
    if not any(line.strip() for line in software.lines):
        software.lines = ['\n'] + [f'{line}\n' for line in SOFTWARE_DEFAULTS]
        if version:
            software.lines.append(f'* Kdenlive {version}\n')
        software.lines.append('\n')
        return
    if not version:
        return
    for i, line in enumerate(software.lines):
        if _KDENLIVE_LINE_RE.match(line):
            software.lines[i] = f'* Kdenlive {version}\n'
            return
    end = len(software.lines)
    while end and not software.lines[end - 1].strip():
        end -= 1
    software.lines.insert(end, f'* Kdenlive {version}\n')


# ── Session processing ────────────────────────────────────────────────────────

def _locate_session_file(session_dir: Path) -> tuple[Path, str]:
    """Return (md_path, current_text); a session_*.txt is promoted on write."""
    md = next(iter(sorted(session_dir.glob('session_*.md'))), None)
    if md:
        return md, md.read_text(encoding='utf-8')
    txt = next(iter(sorted(session_dir.glob('session_*.txt'))), None)
    if txt:
        return txt.with_suffix('.md'), txt.read_text(encoding='utf-8')
    return session_dir / f'{session_dir.name}.md', ''


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


def _show_episode(session_dir: Path, episode: str) -> bool:
    """Print an episode's block from the session file; True if found."""
    _, original = _locate_session_file(session_dir)
    if not original:
        return False
    block = _find_block(_parse(original), 3, episode)
    if block is None:
        return False
    print(_render(block).rstrip('\n'))
    return True


def _print_report(root: _Block, episode_names: list[str]) -> None:
    print('  checklist:')
    for name in episode_names:
        episode = _find_block(root, 3, name)
        if episode is None:
            print(f'    ✗ {name}: not in session file')
            continue
        filled = {m.group(1) for line in episode.lines if (m := _META_FILLED_RE.match(line))}
        missing = [f for f in METADATA_FIELDS if f not in filled]
        counts = [
            f'{c.title} {sum(1 for line in c.lines if line.startswith("* "))}'
            for c in episode.children
            if any(line.startswith('* ') for line in c.lines)
        ]
        notes_txt = ', '.join(counts) if counts else 'no notes yet'
        if missing:
            print(f'    ✗ {name}: fill in {", ".join(missing)}  [{notes_txt}]')
        else:
            print(f'    ✓ {name}: ready  [{notes_txt}]')


def process_session(session_dir: Path, dry_run: bool = False) -> int:
    """Process one session directory; returns the number of warnings."""
    print(f'session: {session_dir.name}')
    warnings = 0

    episode_dirs = sorted(
        (d for d in session_dir.iterdir()
         if d.is_dir() and (d / f'{d.name}.kdenlive').exists()),
        key=lambda d: _natural_key(d.name),
    )
    if not episode_dirs:
        print('  no episode subdirectories found')
        return warnings

    md, original = _locate_session_file(session_dir)
    if original and not original.endswith('\n'):
        original += '\n'

    root = _parse(original)
    software, info = _ensure_skeleton(root, _session_title(session_dir.name))

    kdenlive_version = None
    episode_names = [d.name for d in episode_dirs]

    for ep_dir in episode_dirs:
        name = ep_dir.name
        episode = _ensure_episode(root, info, name)
        _ensure_metadata(episode)
        _ensure_section(episode, 'Noteworthy')
        _prune_orphan_section(episode, set())

        try:
            notes, version = _extract_project(ep_dir / f'{name}.kdenlive')
        except (ET.ParseError, OSError) as exc:
            print(f'  {name}: WARNING - could not read project file ({exc})')
            warnings += 1
            continue
        kdenlive_version = version or kdenlive_version

        orphans = notes.pop(ORPHAN_SECTION, [])
        orphan_bullets = [_bullet(e) for e in orphans]
        _prune_orphan_section(episode, set(orphan_bullets))

        if notes or orphans:
            # Naked bullets directly under the episode heading are leftovers
            # from the pre-section format; the structured sections replace them.
            episode.lines = [line for line in episode.lines if not line.startswith('* ')]
            if orphans:
                notes.setdefault('Noteworthy', [])
            for section_name, entries in notes.items():
                section = _ensure_section(episode, section_name)
                bullets = [_bullet(e) for e in entries]
                appendix = None
                if section_name == 'Noteworthy' and orphan_bullets:
                    if bullets:
                        appendix = orphan_bullets
                    else:
                        bullets = orphan_bullets
                tally = _tally(entries) if section_name == BRYGG_SECTION else None
                _set_bullets(section, bullets, tally, appendix)
            counts = {s: len(e) for s, e in notes.items()}
            if orphans:
                counts['Noteworthy'] += len(orphans)
            summary = ', '.join(f'{s} ({n})' for s, n in counts.items())
            print(f'  {name}: {summary}')
        else:
            print(f'  {name}: no notes')

    _update_software(software, kdenlive_version)

    on_disk = set(episode_names)
    for child in info.children:
        if child.level == 3 and child.title not in on_disk:
            print(f"  WARNING - section '### {child.title}' has no matching episode directory")
            warnings += 1

    updated = _render(root)
    if updated == original:
        print(f'  {md.name} already up to date')
    elif dry_run:
        print(f'  dry run - {md.name} would be {"updated" if md.exists() else "created"}:')
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f'{md.name} (current)',
            tofile=f'{md.name} (updated)',
        )
        for line in diff:
            print('    ' + line.rstrip('\n'))
    else:
        created = not md.exists()
        if not created:
            md.with_name(md.name + '.bak').write_text(original, encoding='utf-8')
        _write_atomic(md, updated)
        note = '' if created else ' (previous version in .bak)'
        print(f'  {"created" if created else "updated"} {md.name}{note}')

    _print_report(root, episode_names)
    return warnings


# ── Entry point ───────────────────────────────────────────────────────────────

def _is_session_dir(path: Path) -> bool:
    return (
        path.name.startswith('session_')
        or any(path.glob('session_*.md'))
        or any(path.glob('session_*.txt'))
    )


def _discover(start: Path) -> list[Path]:
    """Sessions to process: walk up to a session dir, else scan for children."""
    for candidate in (start, *start.parents):
        if _is_session_dir(candidate):
            return [candidate]
    return sorted(
        (d for d in start.iterdir() if d.is_dir() and d.name.startswith('session_')),
        key=lambda d: _natural_key(d.name),
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        'directory',
        nargs='?',
        default='.',
        help='any directory inside a session tree, a session directory, or a '
             'parent of session_* directories (default: current directory)',
    )
    ap.add_argument(
        '--dry-run',
        action='store_true',
        help='show what would change as a diff, without writing anything',
    )
    ap.add_argument(
        '--show',
        metavar='EPISODE',
        help="print an episode's metadata and notes from the session file, then exit",
    )
    ap.add_argument('--version', action='version', version=f'%(prog)s {_version()}')
    args = ap.parse_args()

    start = Path(args.directory).resolve()
    if not start.is_dir():
        sys.exit(f'error: {start} is not a directory')

    sessions = _discover(start)
    if not sessions:
        sys.exit(
            f'error: {start} is not inside a session directory and contains '
            'no session_* directories'
        )

    if args.show:
        if not any(_show_episode(s, args.show) for s in sessions):
            sys.exit(f'error: episode {args.show!r} not found in any session file')
        return

    warnings = sum(process_session(s, dry_run=args.dry_run) for s in sessions)
    if warnings:
        sys.exit(1)


if __name__ == '__main__':
    main()
