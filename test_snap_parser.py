import unittest
from pathlib import Path

from extract_players import extract_players_from_pdf


ROOT = Path(__file__).parent


class SnapParserTests(unittest.TestCase):
    def assert_snap(self, pdf_name, player_name, expected):
        pdf_path = ROOT / pdf_name
        if not pdf_path.exists():
            self.skipTest(f"local gamebook fixture not found: {pdf_name}")

        _, _, _, _, rows = extract_players_from_pdf(str(pdf_path))
        matches = [row for row in rows if row['name'] == player_name]
        self.assertEqual(len(matches), 1, matches)
        row = matches[0]
        actual = tuple(
            row[field]
            for field in (
                'offense_snaps', 'offense_pct',
                'defense_snaps', 'defense_pct',
                'st_snaps', 'st_pct',
            )
        )
        self.assertEqual(actual, expected)

    def test_special_teams_does_not_become_offense(self):
        # The old left-edge heading lookup classified Atlanta's defense cells
        # as offense cells in this two-team table.
        self.assert_snap(
            'w5balatl.pdf',
            'M.Bergeron',
            ('64', '100', '5', '17', '0', '0'),
        )

    def test_special_teams_column_is_preserved(self):
        self.assert_snap(
            'w5balatl.pdf',
            'E.Jones',
            ('76', '100', '0', '0', '4', '13'),
        )

    def test_second_fixture_has_same_column_alignment(self):
        self.assert_snap(
            'w5indpit.pdf',
            'B.Hoffman',
            ('60', '100', '6', '20', '0', '0'),
        )


if __name__ == '__main__':
    unittest.main()
