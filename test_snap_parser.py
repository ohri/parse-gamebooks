import unittest
from pathlib import Path

from extract_players import extract_players_from_pdf, load_players_database, match_player_to_database


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

    def test_duplicate_short_name_uses_compatible_position(self):
        players_csv = Path('/Users/ohri/Downloads/2026/w6/players.csv')
        if not players_csv.exists():
            self.skipTest(f"local player database not found: {players_csv}")

        short_name_db, players_db = load_players_database(str(players_csv))
        gsis_id, strategy = match_player_to_database(
            'D.Key', 'Denver Broncos', 'DB', short_name_db, players_db
        )
        self.assertEqual(gsis_id, '00-0036683')
        self.assertEqual(strategy, 'short_name_team_position')

    def test_apostrophe_name_is_preserved_for_status_and_snaps(self):
        pdf_path = Path('/Users/ohri/Downloads/2026/w6/w6houjax.pdf')
        players_csv = Path('/Users/ohri/Downloads/2026/w6/players.csv')
        if not pdf_path.exists() or not players_csv.exists():
            self.skipTest('local Houston-Jacksonville fixture not found')

        players, _, _, _, snaps = extract_players_from_pdf(str(pdf_path))
        status_rows = [row for row in players if row['name'] == "H.To'oTo'o"]
        snap_rows = [row for row in snaps if row['name'] == "H.To'oTo'o"]
        self.assertEqual(len(status_rows), 1)
        self.assertEqual(status_rows[0]['status'], 'starter')
        self.assertEqual(len(snap_rows), 1)
        self.assertEqual(snap_rows[0]['defense_snaps'], '70')
        self.assertEqual(snap_rows[0]['defense_pct'], '99')

        short_name_db, players_db = load_players_database(str(players_csv))
        gsis_id, _ = match_player_to_database(
            "H.To'oTo'o", 'Houston Texans', 'LB', short_name_db, players_db
        )
        self.assertEqual(gsis_id, '00-0038599')


if __name__ == '__main__':
    unittest.main()
