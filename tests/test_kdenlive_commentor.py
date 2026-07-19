import io
import sys
import unittest
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import kdenlive_commentor as kc


def kdenlive_xml(notes_html=None, version='24.12.3'):
    props = []
    if version:
        props.append(
            f'<property name="kdenlive:docproperties.kdenliveversion">{version}</property>'
        )
    if notes_html is not None:
        props.append(
            f'<property name="kdenlive:documentnotes">{escape(notes_html)}</property>'
        )
    return f'<mlt><playlist id="main_bin">{"".join(props)}</playlist></mlt>'


def note(ts, text):
    return f'<p><a href="{ts}">{ts}</a> {text}</p>'


def heading(name):
    return f'<p>## {name}</p>'


NOTEWORTHY = (
    heading('Noteworthy')
    + note('00:06:29:32', 'A memorable quote -h')
    + note('00:03:12:01', 'Earlier moment -j')
)


class SessionTree:
    """Builds a session directory tree inside a temp dir."""

    def __init__(self, tmp, name='session_26_2025-06-30'):
        self.dir = Path(tmp) / name
        self.dir.mkdir(parents=True)

    def episode(self, name, notes_html=None, version='24.12.3', raw=None):
        ep = self.dir / name
        ep.mkdir()
        content = raw if raw is not None else kdenlive_xml(notes_html, version)
        (ep / f'{name}.kdenlive').write_text(content, encoding='utf-8')
        return ep

    @property
    def md(self):
        return self.dir / f'{self.dir.name}.md'

    def run(self):
        with redirect_stdout(io.StringIO()):
            kc.process_session(self.dir)
        return self.md.read_text(encoding='utf-8')


class BootstrapTests(unittest.TestCase):

    def test_full_skeleton_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            out = t.run()
            expected_order = [
                '# Session 26 - 2025-06-30',
                '## Mjukvaruversioner',
                '* Prism Launcher 9.2',
                '* OBS 23.0.3',
                '* Kdenlive 24.12.3',
                '## Avsnittsinfo',
                '### avsnitt207',
                '**Titel:**',
                '**Blurb (large):**',
                '**Blurb (short):**',
                '**Trailer:**',
                '#### Noteworthy',
                '* 03:12 Earlier moment -j',
                '* 06:29 A memorable quote -h',
                '#### Other comments without a home',
            ]
            positions = [out.index(s) for s in expected_order]
            self.assertEqual(positions, sorted(positions))
            self.assertNotIn('#### Bryggpromenader', out)

    def test_hour_timestamps_keep_hours(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', heading('Noteworthy') + note('01:02:03:10', 'Long -k'))
            out = t.run()
            self.assertIn('* 01:02:03 Long -k', out)

    def test_natural_episode_sort(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt10', NOTEWORTHY)
            t.episode('avsnitt9', NOTEWORTHY)
            out = t.run()
            self.assertLess(out.index('### avsnitt9'), out.index('### avsnitt10'))


class PlacementTests(unittest.TestCase):

    def test_sections_stay_inside_episode_despite_trailing_h2(self):
        """Regression: '## Övrigt' after the last episode must not swallow notes."""
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            t.md.write_text(
                '# Session 26 - 2025-06-30\n\n'
                '## Avsnittsinfo\n\n'
                '### avsnitt207\n\n'
                '**Titel:** Ett avsnitt\n'
                '**Blurb (large):** Lång\n'
                '**Blurb (short):** Kort\n'
                '**Trailer:** Trailerinfo\n\n'
                '## Övrigt\n\n'
                '* keep me\n',
                encoding='utf-8',
            )
            out = t.run()
            self.assertIn('* keep me', out)
            self.assertLess(out.index('#### Noteworthy'), out.index('## Övrigt'))
            self.assertLess(out.index('* 06:29 A memorable quote -h'), out.index('## Övrigt'))

    def test_missing_episode_heading_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            t.md.write_text(
                '# Session 26 - 2025-06-30\n\n## Avsnittsinfo\n', encoding='utf-8'
            )
            out = t.run()
            self.assertIn('### avsnitt207', out)
            self.assertIn('**Titel:**', out)
            self.assertIn('* 06:29 A memorable quote -h', out)


class RepairTests(unittest.TestCase):

    def test_missing_metadata_fields_added_values_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            t.md.write_text(
                '# Session 26 - 2025-06-30\n\n'
                '## Avsnittsinfo\n\n'
                '### avsnitt207\n\n'
                '**Titel:** Behåll mig\n\n',
                encoding='utf-8',
            )
            out = t.run()
            self.assertIn('**Titel:** Behåll mig', out)
            for field in ('Blurb (large)', 'Blurb (short)', 'Trailer'):
                self.assertIn(f'**{field}:**', out)

    def test_missing_top_sections_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            t.md.write_text('# Session 26 - 2025-06-30\n', encoding='utf-8')
            out = t.run()
            self.assertLess(out.index('## Mjukvaruversioner'), out.index('## Avsnittsinfo'))
            self.assertIn('* Prism Launcher 9.2', out)

    def test_software_version_line_updated_hand_lines_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY, version='25.04.0')
            t.md.write_text(
                '# Session 26 - 2025-06-30\n\n'
                '## Mjukvaruversioner\n\n'
                '* OBS 23.0.3 (my hand-tuned line)\n'
                '* Kdenlive 23.08.0\n\n'
                '## Avsnittsinfo\n',
                encoding='utf-8',
            )
            out = t.run()
            self.assertIn('* OBS 23.0.3 (my hand-tuned line)', out)
            self.assertIn('* Kdenlive 25.04.0', out)
            self.assertNotIn('* Kdenlive 23.08.0', out)


class ContentPreservationTests(unittest.TestCase):

    def test_hand_bullets_survive_when_no_incoming_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            t.md.write_text(
                '# Session 26 - 2025-06-30\n\n'
                '## Avsnittsinfo\n\n'
                '### avsnitt207\n\n'
                '**Titel:** X\n\n'
                '#### Other comments without a home\n'
                '* my own hand-written note\n\n',
                encoding='utf-8',
            )
            out = t.run()
            self.assertIn('* my own hand-written note', out)

    def test_old_bullets_replaced_when_notes_arrive(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            t.md.write_text(
                '# Session 26 - 2025-06-30\n\n'
                '## Avsnittsinfo\n\n'
                '### avsnitt207\n\n'
                '#### Noteworthy\n'
                '* 01:00 stale old bullet\n\n',
                encoding='utf-8',
            )
            out = t.run()
            self.assertNotIn('stale old bullet', out)
            self.assertIn('* 06:29 A memorable quote -h', out)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            brygg = (
                heading('Bryggpromenader')
                + note('00:05:28:00', 'H+1')
                + note('00:12:03:00', 'J+1')
            )
            t.episode('avsnitt207', NOTEWORTHY + brygg)
            first = t.run()
            second = t.run()
            self.assertEqual(first, second)


class BryggpromenadTests(unittest.TestCase):

    def test_tally_auto_counted_one_name_per_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            brygg = (
                heading('Bryggpromenader')
                + note('00:05:28:00', 'H+1')
                + note('00:12:03:00', 'J+1')
                + note('00:31:44:00', 'H+1')
            )
            t.episode('avsnitt207', NOTEWORTHY + brygg)
            out = t.run()
            self.assertIn('#### Bryggpromenader', out)
            self.assertIn('Joel: 1\nRobin: 0\nHenrik: 2\nKenneth: 0\n', out)

    def test_section_omitted_without_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', NOTEWORTHY)
            out = t.run()
            self.assertNotIn('#### Bryggpromenader', out)


class ExtractionTests(unittest.TestCase):

    def test_orphan_notes_get_a_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            html = (
                note('00:02:00:00', 'orphan with timestamp')
                + '<p>plain stray comment</p>'
                + NOTEWORTHY
            )
            t.episode('avsnitt207', html)
            out = t.run()
            orphan_at = out.index('#### Other comments without a home')
            self.assertIn('* 02:00 orphan with timestamp', out[orphan_at:])
            self.assertIn('* plain stray comment', out[orphan_at:])

    def test_malformed_kdenlive_does_not_abort_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            t.episode('avsnitt207', raw='<mlt><broken')
            t.episode('avsnitt208', NOTEWORTHY)
            out = t.run()
            self.assertIn('### avsnitt208', out)
            self.assertIn('* 06:29 A memorable quote -h', out)


class DiscoveryTests(unittest.TestCase):

    def test_walks_up_from_episode_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = SessionTree(tmp)
            ep = t.episode('avsnitt207', NOTEWORTHY)
            self.assertEqual(kc._discover(ep), [t.dir])

    def test_finds_session_children_naturally_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = SessionTree(tmp, 'session_9_2025-01-01')
            b = SessionTree(tmp, 'session_10_2025-02-01')
            self.assertEqual(kc._discover(Path(tmp)), [a.dir, b.dir])

    def test_session_dir_detected_by_md_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'somewhere'
            d.mkdir()
            (d / 'session_1_2025-01-01.md').write_text('# x\n', encoding='utf-8')
            self.assertEqual(kc._discover(d), [d])


if __name__ == '__main__':
    unittest.main()
