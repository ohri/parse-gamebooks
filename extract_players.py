import pdfplumber
import csv
import re
import os
import urllib.request
import glob
import sys

# Player names in gamebooks use abbreviated first names (for example,
# ``T.Smith`` or ``Tr.Smith``) and can have multi-part surnames (for example,
# ``G.Van Roten``).  Keep this pattern shared by all three section parsers so
# they extract the same name regardless of where it appears in the gamebook.
PLAYER_PATTERN = re.compile(
    r"([A-Z/]+)\s+(\d+)\s+"
    r"([A-Z][a-z]*\.(?:[A-Z](?:[a-z]+)?\.?\s*)*"
    r"[A-Z](?:[a-z][A-Za-z]*|(?=['-]))(?:['-][A-Za-z]+)*"
    r"(?:\s+[A-Z](?:[a-z][A-Za-z]*|(?=['-]))(?:['-][A-Za-z]+)*)*)"
)

ANSI_COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'reset': '\033[0m',
}

def colorize(text, color, enabled):
    """Add terminal color when enabled, otherwise return plain text."""
    if not enabled or color not in ANSI_COLORS:
        return text
    return f"{ANSI_COLORS[color]}{text}{ANSI_COLORS['reset']}"

def normalize_player_name(name):
    """Normalize whitespace in names that wrap across extracted PDF lines."""
    return re.sub(r'\s+', ' ', name).strip()

def parse_lineup_line(line, visitor_team, home_team):
    """Parse a single lineup line into players for both teams."""
    players = []

    # Each line has 4 sections: Team1 Offense, Team1 Defense, Team2 Offense, Team2 Defense
    # Pattern: POS NUM NAME (handles Jo.Phillips, B.O'Neill, A.St. Brown, T.Ingram-Dawkins, O'Brien, To'oTo'o, Van Pran-Granger, etc.)
    # Requires at least one lowercase letter in the final part to avoid matching position codes
    matches = PLAYER_PATTERN.findall(line)

    # There should be 4 matches per line (one for each column)
    # Columns 0 and 1 are visitor team, columns 2 and 3 are home team
    for idx, (position, number, name) in enumerate(matches):
        team = visitor_team if idx < 2 else home_team
        players.append({
            'team': team,
            'name': normalize_player_name(name),
            'position': position,
            'status': 'starter'
        })

    return players

def parse_two_column_line(line, visitor_team, home_team):
    """Parse a line that has both teams in two columns."""
    players = []

    # Try to split the line at roughly the midpoint
    # Most lines are around 100-120 characters, so split around 55-60
    midpoint = len(line) // 2

    # Find a good split point near the midpoint (look for a comma or space)
    best_split = midpoint
    for i in range(midpoint - 10, midpoint + 10):
        if i < len(line) and (line[i] == ',' or (line[i:i+3].strip() and line[i-1:i] == ' ' and line[i].isupper())):
            best_split = i
            break

    left_half = line[:best_split]
    right_half = line[best_split:]

    # Pattern: POS NUM NAME (handles Jo.Phillips, B.O'Neill, A.St. Brown, T.Ingram-Dawkins, O'Brien, To'oTo'o, Van Pran-Granger, etc.)
    # Requires at least one lowercase letter in the final part to avoid matching position codes
    # Parse left half (visitor team)
    matches_left = PLAYER_PATTERN.findall(left_half)
    for position, number, name in matches_left:
        players.append({
            'team': visitor_team,
            'name': normalize_player_name(name),
            'position': position,
            'status': 'backup'
        })

    # Parse right half (home team)
    matches_right = PLAYER_PATTERN.findall(right_half)
    for position, number, name in matches_right:
        players.append({
            'team': home_team,
            'name': normalize_player_name(name),
            'position': position,
            'status': 'backup'
        })

    return players

def parse_player_list(text, team_name, status):
    """Parse a comma-separated or space-separated list of players."""
    players = []

    # Pattern: POS NUM NAME (handles Jo.Phillips, B.O'Neill, A.St. Brown, T.Ingram-Dawkins, O'Brien, To'oTo'o, Van Pran-Granger, etc.)
    # Requires at least one lowercase letter in the final part to avoid matching position codes
    matches = PLAYER_PATTERN.findall(text)

    for position, number, name in matches:
        players.append({
            'team': team_name,
            'name': normalize_player_name(name),
            'position': position,
            'status': status
        })

    return players

def download_players_database(output_path='players.csv', force_download=True):
    """Download the nflverse players database.

    Args:
        output_path: Path to save the database file
        force_download: If True, always download. If False, skip if file exists.
    """
    if not force_download and os.path.exists(output_path):
        print(f"Using existing players database at {output_path}")
        return output_path

    url = 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
    print(f"Downloading players database from {url}...")

    try:
        urllib.request.urlretrieve(url, output_path)
        print(f"Players database downloaded to {output_path}")
        return output_path
    except Exception as e:
        print(f"Error downloading players database: {e}")
        return None

def load_players_database(db_path='players.csv'):
    """Load the players database and create lookup dictionaries."""
    players_db = {}
    short_name_db = {}  # Separate lookup for short_name (preferred)

    if not os.path.exists(db_path):
        print(f"Players database not found at {db_path}")
        return players_db, short_name_db

    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                gsis_id = row.get('gsis_id', '')
                if not gsis_id:
                    continue

                # Skip GSIS IDs that start with alphabetic characters (old format like ABB498348)
                if gsis_id[0].isalpha():
                    continue

                # Only consider active players or developmental players (where both status and ngs_status are DEV)
                status = row.get('status', '')
                ngs_status = row.get('ngs_status', '')
                if not (status == 'ACT' or (status == 'DEV' and ngs_status == 'DEV')):
                    continue

                # Get all name variants
                display_name = row.get('display_name', '')
                short_name = row.get('short_name', '')
                football_name = row.get('football_name', '')
                first_name = row.get('first_name', '')
                last_name = row.get('last_name', '')
                team = row.get('latest_team', '')
                position = row.get('position', '')

                player_data = {
                    'gsis_id': gsis_id,
                    'display_name': display_name,
                    'short_name': short_name,
                    'first_name': first_name,
                    'latest_team': team,
                    'position': position
                }

                # Store short_name in separate database (preferred)
                if short_name:
                    key = (short_name.lower().strip(), team.upper())
                    if key not in short_name_db:
                        short_name_db[key] = []
                    short_name_db[key].append(player_data)

                # Store other name variants in main database
                name_variants = []

                # Add display name
                if display_name:
                    name_variants.append(display_name)

                # Add football name
                if football_name:
                    name_variants.append(football_name)

                # Generate first initial + last name (e.g., "N.Collins")
                if first_name and last_name:
                    name_variants.append(f"{first_name[0]}.{last_name}")

                # Store all variants - use list to handle multiple players with same name
                for name in name_variants:
                    if name:
                        key = (name.lower().strip(), team.upper())
                        if key not in players_db:
                            players_db[key] = []
                        players_db[key].append(player_data)

        print(f"Loaded {len(short_name_db)} short_name entries, {len(players_db)} other name variants")
        return short_name_db, players_db
    except Exception as e:
        print(f"Error loading players database: {e}")
        return {}, {}

def get_team_abbr(team_name):
    """Convert full team name to abbreviation."""
    team_mapping = {
        'Houston Texans': 'HOU',
        'Seattle Seahawks': 'SEA',
        'Arizona Cardinals': 'ARI',
        'Atlanta Falcons': 'ATL',
        'Baltimore Ravens': 'BAL',
        'Buffalo Bills': 'BUF',
        'Carolina Panthers': 'CAR',
        'Chicago Bears': 'CHI',
        'Cincinnati Bengals': 'CIN',
        'Cleveland Browns': 'CLE',
        'Dallas Cowboys': 'DAL',
        'Denver Broncos': 'DEN',
        'Detroit Lions': 'DET',
        'Green Bay Packers': 'GB',
        'Indianapolis Colts': 'IND',
        'Jacksonville Jaguars': 'JAX',
        'Kansas City Chiefs': 'KC',
        'Las Vegas Raiders': 'LV',
        'Los Angeles Chargers': 'LAC',
        'Los Angeles Rams': 'LA',
        'Miami Dolphins': 'MIA',
        'Minnesota Vikings': 'MIN',
        'New England Patriots': 'NE',
        'New Orleans Saints': 'NO',
        'New York Giants': 'NYG',
        'New York Jets': 'NYJ',
        'Philadelphia Eagles': 'PHI',
        'Pittsburgh Steelers': 'PIT',
        'San Francisco 49ers': 'SF',
        'Tampa Bay Buccaneers': 'TB',
        'Tennessee Titans': 'TEN',
        'Washington Commanders': 'WAS'
    }
    return team_mapping.get(team_name, '')

def positions_match(gamebook_position, database_position):
    """Return whether two position labels describe the same player group."""
    if gamebook_position == database_position:
        return True

    compatible_positions = {
        frozenset(('DB', 'SAF')),
        frozenset(('S', 'SAF')),
        frozenset(('CB', 'DB')),
        frozenset(('DL', 'DE')),
        frozenset(('DL', 'DT')),
        frozenset(('DL', 'NT')),
        frozenset(('LB', 'ILB')),
        frozenset(('LB', 'OLB')),
        frozenset(('OL', 'C')),
        frozenset(('OL', 'G')),
        frozenset(('OL', 'T')),
    }
    return frozenset((gamebook_position, database_position)) in compatible_positions

def match_player_to_database(player_name, team_name, position, short_name_db, players_db):
    """Match a player to the database and return their GSIS ID and match strategy."""
    team_abbr = get_team_abbr(team_name)
    player_name_lower = player_name.lower().strip()

    # Strategy 1: Try short_name first (preferred)
    key = (player_name_lower, team_abbr)
    if key in short_name_db:
        player_list = short_name_db[key]
        # Try to find exact position match first
        for player_data in player_list:
            db_position = player_data.get('position', '')
            if positions_match(position, db_position):
                return player_data['gsis_id'], 'short_name_team_position'
        # If no position match, keep first candidate
        if player_list:
            return player_list[0]['gsis_id'], 'short_name_team'

    # Strategy 2: Exact match with team and position (other name variants)
    if key in players_db:
        player_list = players_db[key]
        # Try to find exact position match first
        for player_data in player_list:
            db_position = player_data.get('position', '')
            if positions_match(position, db_position):
                return player_data['gsis_id'], 'other_name_team_position'
        # If no position match, keep first candidate
        candidate = player_list[0]['gsis_id'] if player_list else None
    else:
        candidate = None

    # Strategy 3: Return the team match even if position doesn't match (from Strategy 2)
    if candidate:
        return candidate, 'other_name_team'

    # Some gamebooks use more than one letter for the first-name abbreviation
    # (for example ``Tr.Smith`` for Trey Smith), while nflverse stores the
    # conventional one-letter form (``T.Smith``).  Only abbreviate the prefix
    # before the first period; the team constraint remains mandatory.
    abbreviated_prefix_match = re.match(r'^([a-z]+)\.', player_name_lower)
    abbreviated_name = re.sub(r'^([a-z])[a-z]+\.', r'\1.', player_name_lower)
    if abbreviated_name != player_name_lower:
        abbreviated_key = (abbreviated_name, team_abbr)
        player_list = short_name_db.get(abbreviated_key, [])

        # The one-initial form can be ambiguous when two teammates share a
        # surname (for example, Bi.Robinson and Br.Robinson in Atlanta).  Use
        # the extra letters from the gamebook abbreviation to disambiguate
        # before falling back to the legacy one-initial behavior.
        if abbreviated_prefix_match:
            prefix = abbreviated_prefix_match.group(1)
            prefixed_players = [
                player_data for player_data in player_list
                if player_data.get('first_name', '').lower().startswith(prefix)
            ]
            if prefixed_players:
                player_list = prefixed_players
        for player_data in player_list:
            if positions_match(position, player_data.get('position', '')):
                return player_data['gsis_id'], 'short_name_abbreviated_initial_team_position'
        if player_list:
            return player_list[0]['gsis_id'], 'short_name_abbreviated_initial_team'

        player_list = players_db.get(abbreviated_key, [])
        if abbreviated_prefix_match:
            prefix = abbreviated_prefix_match.group(1)
            prefixed_players = [
                player_data for player_data in player_list
                if player_data.get('first_name', '').lower().startswith(prefix)
            ]
            if prefixed_players:
                player_list = prefixed_players
        for player_data in player_list:
            if positions_match(position, player_data.get('position', '')):
                return player_data['gsis_id'], 'other_name_abbreviated_initial_team_position'
        if player_list:
            return player_list[0]['gsis_id'], 'other_name_abbreviated_initial_team'

    # Strategy 4: Try with spaces removed in short_name (e.g., "N.Collins" vs "N. Collins")
    player_name_no_space = player_name_lower.replace(' ', '')
    for (name, team), player_list in short_name_db.items():
        if name.replace(' ', '') == player_name_no_space and team == team_abbr and player_list:
            # Check position first
            for player_data in player_list:
                db_position = player_data.get('position', '')
                if positions_match(position, db_position):
                    return player_data['gsis_id'], 'short_name_no_spaces_position'
            # Return first match if position doesn't match
            return player_list[0]['gsis_id'], 'short_name_no_spaces'

    # Strategy 5: Try with spaces removed in other names
    for (name, team), player_list in players_db.items():
        if name.replace(' ', '') == player_name_no_space and team == team_abbr and player_list:
            # Check position first
            for player_data in player_list:
                db_position = player_data.get('position', '')
                if positions_match(position, db_position):
                    return player_data['gsis_id'], 'other_name_no_spaces_position'
            # Return first match if position doesn't match
            return player_list[0]['gsis_id'], 'other_name_no_spaces'

    # Strategy 6: Try partial match on last name only (as last resort, still requires team)
    if '.' in player_name:
        last_name = player_name.split('.')[-1].lower().strip()
        # Check short_name first
        for (name, team), player_list in short_name_db.items():
            if team == team_abbr and name.endswith(last_name) and player_list:
                # Check position first
                for player_data in player_list:
                    db_position = player_data.get('position', '')
                    if positions_match(position, db_position):
                        return player_data['gsis_id'], 'short_name_partial_lastname_position'
                # Return first match if position doesn't match
                return player_list[0]['gsis_id'], 'short_name_partial_lastname'
        # Then check other names
        for (name, team), player_list in players_db.items():
            if team == team_abbr and name.endswith(last_name) and player_list:
                # Check position first
                for player_data in player_list:
                    db_position = player_data.get('position', '')
                    if positions_match(position, db_position):
                        return player_data['gsis_id'], 'other_name_partial_lastname_position'
                # Return first match if position doesn't match
                return player_list[0]['gsis_id'], 'other_name_partial_lastname'

    return None, None

def rejoin_hyphenated_lines(text):
    """Rejoin words that are hyphenated across line breaks."""
    lines = text.split('\n')
    rejoined_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if line ends with a hyphen (word split across lines)
        if i < len(lines) - 1 and line.rstrip().endswith('-'):
            # Get the next line and extract the first word
            next_line = lines[i + 1].lstrip()
            # Find the first word on the next line (up to comma, space, or end)
            match = re.match(r'^([A-Za-z]+)', next_line)
            if match:
                continuation = match.group(1)
                # Append continuation to current line, remove it from next line
                line = line.rstrip() + continuation
                lines[i + 1] = next_line[len(continuation):]
        rejoined_lines.append(line)
        i += 1
    return '\n'.join(rejoined_lines)

def is_lower_confidence_match(strategy):
    """Return whether a match used a heuristic worth mentioning to the user."""
    # An exact short name plus team is still a strong identity match even when
    # the gamebook and database use different position labels (for example,
    # OLB vs. DL).  Only surface transformations that can plausibly identify
    # the wrong player: abbreviated initials and partial surnames.
    return bool(strategy) and any(
        marker in strategy for marker in ('abbreviated_initial', 'partial_lastname')
    )

def extract_game_date(lines):
    """Extract the game date from the PDF."""
    for line in lines:
        # Look for date line like "Date: Monday, 10/20/2025"
        if line.startswith('Date:'):
            parts = line.split()
            # Date should be in format MM/DD/YYYY
            for part in parts:
                if '/' in part:
                    date_parts = part.split('/')
                    if len(date_parts) == 3:
                        try:
                            month, day, year = date_parts
                            return int(year)
                        except ValueError:
                            continue
    return None

def extract_game_score(lines):
    """Extract the final game score from the PDF."""
    visitor_score = None
    home_score = None
    visitor_team = None
    home_team = None

    for line in lines:
        # Look for lines like "VISITOR: Houston Texans 0 6 6 7 0 19"
        if line.startswith('VISITOR:'):
            parts = line.split()
            # Team name is after VISITOR: and before the numbers
            # Numbers are at the end, last one is total
            if len(parts) >= 3:
                # Find where numbers start
                for i, part in enumerate(parts):
                    if part.isdigit():
                        visitor_team = ' '.join(parts[1:i])
                        visitor_score = parts[-1]  # Last number is total
                        break
        elif line.startswith('HOME:'):
            parts = line.split()
            if len(parts) >= 3:
                for i, part in enumerate(parts):
                    if part.isdigit():
                        home_team = ' '.join(parts[1:i])
                        home_score = parts[-1]  # Last number is total
                        break

    return visitor_team, visitor_score, home_team, home_score


def _group_words_by_line(words, tolerance=2):
    """Group pdfplumber words into visually aligned text lines."""
    lines = []
    for word in sorted(words, key=lambda item: (item['top'], item['x0'])):
        for line in lines:
            if abs(line[0]['top'] - word['top']) <= tolerance:
                line.append(word)
                break
        else:
            lines.append([word])
    return [sorted(line, key=lambda item: item['x0']) for line in lines]


def _find_team_headers(words, teams):
    """Find team names and their positions in a PDF page."""
    headers = []
    for team in teams.values():
        if not team:
            continue
        team_words = team.split()
        lower_words = [word['text'].lower() for word in words]
        for index in range(len(words) - len(team_words) + 1):
            if lower_words[index:index + len(team_words)] == [part.lower() for part in team_words]:
                headers.append({
                    'team': team,
                    'x': (words[index]['x0'] + words[index + len(team_words) - 1]['x1']) / 2,
                    'top': words[index]['top'],
                })
                break
    return headers


def _snap_values_by_unit(words, unit_headings):
    """Assign metric values to the nearest unit column in a table row.

    ``unit_headings`` contains the center of each two-column unit group.  A
    gamebook can omit blank cells from the extracted text, so values must be
    classified by their PDF coordinates rather than by their order in the
    extracted words.
    """
    values = {unit: {'snaps': '0', 'pct': '0'} for unit in unit_headings}
    numeric_words = []
    for word in words:
        value = word['text'].replace('%', '')
        if re.fullmatch(r'\d+(?:\.\d+)?', value):
            numeric_words.append((word, value))

    for word, value in numeric_words:
        unit = min(
            unit_headings,
            key=lambda candidate: abs(word['x0'] - unit_headings[candidate]),
        )
        metric = 'pct' if word['text'].endswith('%') else 'snaps'
        values[unit][metric] = value

    return values


def _unit_heading_centers(page_words, unit, heading_top=None):
    """Return centers for a unit heading, including the full ST label.

    In the gamebook PDF, ``Special Teams`` is emitted as two words.  Using
    only the x-coordinate of ``Special`` biases the nearest-column lookup
    toward the preceding defense columns, especially for snap-count cells.
    """
    centers = []
    words = [word for word in page_words
             if word['text'].lower() == unit
             and (heading_top is None or abs(word['top'] - heading_top) <= 2)]
    for word in words:
        if unit != 'special':
            centers.append((word['x0'] + word['x1']) / 2)
            continue

        teams = [candidate for candidate in page_words
                 if candidate['text'].lower() == 'teams'
                 and abs(candidate['top'] - word['top']) <= 2
                 and candidate['x0'] >= word['x1']]
        if teams:
            teams_word = min(teams, key=lambda candidate: candidate['x0'])
            centers.append((word['x0'] + teams_word['x1']) / 2)
        else:
            centers.append((word['x0'] + word['x1']) / 2)
    return centers


def _is_snap_name_token(text):
    """Return whether a table token can begin a gamebook player name."""
    return bool(re.fullmatch(r"[A-Z][A-Za-z'’-]*\.[A-Za-z'’-]+", text))


def _parse_snap_row(row_words, unit_headings):
    """Parse one player row from a playtime-percentage table."""
    player_index = None
    position_index = None
    for index, word in enumerate(row_words):
        if not _is_snap_name_token(word['text']):
            continue
        # A surname can be split into multiple PDF words, e.g. R.Van Demark
        # or K.Van Noy. Find the position token after the complete name.
        for candidate_index in range(index + 1, len(row_words)):
            if re.fullmatch(r'[A-Z][A-Z/]{0,5}', row_words[candidate_index]['text']):
                player_index = index
                position_index = candidate_index
                break
        if player_index is not None:
            break
    if player_index is None:
        return None

    player_name = normalize_player_name(
        ' '.join(word['text'] for word in row_words[player_index:position_index])
    )

    # Stop before the next team's/player's name when both table halves share a
    # visual line. This keeps absent units at zero instead of copying a value
    # from another unit or the other team's row.
    metric_end = len(row_words)
    for index in range(position_index + 1, len(row_words)):
        if _is_snap_name_token(row_words[index]['text']):
            metric_end = index
            break
    values = _snap_values_by_unit(row_words[position_index + 1:metric_end], unit_headings)

    return {
        'name': player_name,
        'position': row_words[position_index]['text'],
        'offense_snaps': values['offense']['snaps'],
        'offense_pct': values['offense']['pct'],
        'defense_snaps': values['defense']['snaps'],
        'defense_pct': values['defense']['pct'],
        'st_snaps': values['special_teams']['snaps'],
        'st_pct': values['special_teams']['pct'],
    }


def extract_snaps_from_pdf(pdf, teams):
    """Extract playtime-percentage snap rows from all pages of a gamebook."""
    snaps = []
    for page in pdf.pages:
        words = page.extract_words()
        playtime_words = [word for word in words if word['text'].lower() == 'playtime']
        if not playtime_words:
            continue

        playtime_top = min(word['top'] for word in playtime_words)
        page_words = [word for word in words if word['top'] >= playtime_top]
        lines = _group_words_by_line(page_words)

        headers = _find_team_headers(page_words, teams)
        if not headers:
            continue

        # The subtitle also contains the words "offense", "defense", and
        # "special teams". Select the actual table-header row below the team
        # headers so those subtitle coordinates cannot affect column mapping.
        team_header_bottom = max(header['top'] for header in headers)
        heading_top = None
        for line in lines:
            line_top = line[0]['top']
            line_text = {word['text'].lower() for word in line}
            if line_top >= team_header_bottom and {
                'offense', 'defense', 'special', 'teams'
            }.issubset(line_text):
                heading_top = line_top
                break

        # Unit headings are positioned above the values they describe. Keeping
        # their x-coordinates lets this work for both one-column and two-column
        # gamebook layouts, including blank metric cells.
        unit_words = {
            'offense': _unit_heading_centers(page_words, 'offense', heading_top),
            'defense': _unit_heading_centers(page_words, 'defense', heading_top),
            'special_teams': _unit_heading_centers(page_words, 'special', heading_top),
        }
        if not headers or not all(unit_words.values()):
            continue

        for line in lines:
            if not any(word['text'].endswith('%') for word in line):
                continue
            for player_index, word in enumerate(line[:-1]):
                if not _is_snap_name_token(word['text']):
                    continue

                player_x = word['x0']
                team_headers = [header for header in headers if header['top'] <= word['top']]
                if not team_headers:
                    continue
                team_header = min(team_headers, key=lambda header: abs(header['x'] - player_x))

                # Select the nearest heading of each type to this player's
                # column, avoiding the other team's duplicate headings.
                unit_headings = {}
                for unit, candidates in unit_words.items():
                    team_center = team_header['x']
                    unit_headings[unit] = min(
                        candidates,
                        key=lambda candidate: abs(candidate - team_center),
                    )

                row = _parse_snap_row(line[player_index:], unit_headings)
                if row:
                    row['team'] = team_header['team']
                    snaps.append(row)

    return snaps

def extract_players_from_pdf(pdf_path):
    """Main function to extract all player data from the PDF."""
    all_players = []
    snap_rows = []
    game_score = None
    season = None
    teams = {}

    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        page_width = first_page.width
        page_height = first_page.height

        text = first_page.extract_text()
        text = rejoin_hyphenated_lines(text)
        lines = text.split('\n')

        # Extract game date/season
        season = extract_game_date(lines)

        # Extract game score and team info
        visitor_team, visitor_score, home_team, home_score = extract_game_score(lines)
        if visitor_team and home_team:
            game_score = f"{visitor_team} {visitor_score}, {home_team} {home_score}"
            # Store team matchup for opponent lookup
            teams['visitor'] = visitor_team
            teams['home'] = home_team

        # Find key line indices
        lineups_idx = None
        substitutions_idx = None
        did_not_play_idx = None
        not_active_idx = None

        for i, line in enumerate(lines):
            if line.strip() == 'Lineups':
                lineups_idx = i
            elif 'Substitutions' in line and substitutions_idx is None:
                substitutions_idx = i
            elif 'Did Not Play' in line and did_not_play_idx is None:
                did_not_play_idx = i
            elif 'Not Active' in line and not_active_idx is None:
                not_active_idx = i

        # Parse starters (lines between Lineups and Substitutions)
        if lineups_idx and substitutions_idx:
            # Skip the header lines (Lineups, team names, Offense/Defense labels)
            start_line = lineups_idx + 3
            end_line = substitutions_idx

            for line_idx in range(start_line, end_line):
                line = lines[line_idx]
                players = parse_lineup_line(line, visitor_team, home_team)
                all_players.extend(players)

        # Parse substitutions (backups) - use bbox to split left/right halves
        if substitutions_idx and did_not_play_idx:
            # Get y-coordinates for substitutions section
            sub_start_y = None
            sub_end_y = None
            words = first_page.extract_words()
            for word in words:
                if word['text'] == 'Substitutions':
                    sub_start_y = word['top']
                if 'Did' in word['text'] and 'Not' in first_page.extract_text()[first_page.extract_text().find(word['text']):first_page.extract_text().find(word['text'])+20]:
                    sub_end_y = word['top']
                    break

            if sub_start_y and sub_end_y:
                # Extract left half (visitor) and right half (home)
                bbox_left = (0, sub_start_y, page_width/2, sub_end_y)
                bbox_right = (page_width/2, sub_start_y, page_width, sub_end_y)

                visitor_text = first_page.within_bbox(bbox_left).extract_text()
                home_text = first_page.within_bbox(bbox_right).extract_text()

                # Rejoin hyphenated words split across lines
                visitor_text = rejoin_hyphenated_lines(visitor_text)
                home_text = rejoin_hyphenated_lines(home_text)

                # Remove the "Substitutions" header
                visitor_text = visitor_text.replace('Substitutions', '').strip()
                home_text = home_text.replace('Substitutions', '').strip()

                visitor_players = parse_player_list(visitor_text, visitor_team, 'backup')
                home_players = parse_player_list(home_text, home_team, 'backup')

                all_players.extend(visitor_players)
                all_players.extend(home_players)

        # Parse "Did Not Play" section - use bbox to split left/right halves
        if did_not_play_idx and not_active_idx:
            # Get y-coordinates for DNP section
            dnp_start_y = None
            dnp_end_y = None
            words = first_page.extract_words()
            for word in words:
                if word['text'] == 'Did' and dnp_start_y is None:
                    # Check if this is "Did Not Play"
                    idx = words.index(word)
                    if idx + 2 < len(words) and words[idx+1]['text'] == 'Not' and words[idx+2]['text'] == 'Play':
                        dnp_start_y = word['top']
                if word['text'] == 'Not' and 'Active' in [w['text'] for w in words[words.index(word):words.index(word)+3]]:
                    dnp_end_y = word['top']
                    break

            if dnp_start_y and dnp_end_y:
                # Extract left half (visitor) and right half (home)
                bbox_left = (0, dnp_start_y, page_width/2, dnp_end_y)
                bbox_right = (page_width/2, dnp_start_y, page_width, dnp_end_y)

                visitor_text = first_page.within_bbox(bbox_left).extract_text()
                home_text = first_page.within_bbox(bbox_right).extract_text()

                # Rejoin hyphenated words split across lines
                visitor_text = rejoin_hyphenated_lines(visitor_text)
                home_text = rejoin_hyphenated_lines(home_text)

                # Remove headers
                visitor_text = visitor_text.replace('Did Not Play', '').strip()
                home_text = home_text.replace('Did Not Play', '').strip()

                visitor_players = parse_player_list(visitor_text, visitor_team, 'did_not_play')
                home_players = parse_player_list(home_text, home_team, 'did_not_play')

                all_players.extend(visitor_players)
                all_players.extend(home_players)

        # Parse inactive players - use bbox to split left/right halves
        if not_active_idx:
            # Get y-coordinates for Not Active section
            na_start_y = None
            na_end_y = None
            words = first_page.extract_words()
            for word in words:
                if word['text'] == 'Not' and na_start_y is None:
                    # Check if this is "Not Active"
                    idx = words.index(word)
                    if idx + 1 < len(words) and words[idx+1]['text'] == 'Active':
                        na_start_y = word['top']
                if word['text'] == 'Field' and na_start_y is not None:
                    # Check if this is "Field Goals"
                    idx = words.index(word)
                    if idx + 1 < len(words) and words[idx+1]['text'] == 'Goals':
                        na_end_y = word['top']
                        break

            if na_start_y and na_end_y:
                # Extract left half (visitor) and right half (home)
                bbox_left = (0, na_start_y, page_width/2, na_end_y)
                bbox_right = (page_width/2, na_start_y, page_width, na_end_y)

                visitor_text = first_page.within_bbox(bbox_left).extract_text()
                home_text = first_page.within_bbox(bbox_right).extract_text()

                # Rejoin hyphenated words split across lines
                visitor_text = rejoin_hyphenated_lines(visitor_text)
                home_text = rejoin_hyphenated_lines(home_text)

                # Remove headers
                visitor_text = visitor_text.replace('Not Active', '').strip()
                home_text = home_text.replace('Not Active', '').strip()

                visitor_players = parse_player_list(visitor_text, visitor_team, 'inactive')
                home_players = parse_player_list(home_text, home_team, 'inactive')

                all_players.extend(visitor_players)
                all_players.extend(home_players)

        snap_rows = extract_snaps_from_pdf(pdf, teams)

    return all_players, game_score, season, teams, snap_rows

def get_opponent(team, teams):
    """Get the opponent for a given team."""
    if team == teams.get('visitor'):
        return teams.get('home')
    elif team == teams.get('home'):
        return teams.get('visitor')
    return ''

def save_to_sql(players, output_path, week, season, teams, game_score=None):
    """Save player data as SQL statements."""
    with open(output_path, 'w', encoding='utf-8') as sqlfile:
        # Write game score as SQL command if available
        if game_score:
            sqlfile.write(f"-- {game_score}\n")
            sqlfile.write(f"-- Week {week}, Season {season}\n\n")

            # Parse the game score string (format: "Team1 Score1, Team2 Score2")
            visitor_team = teams.get('visitor', '')
            home_team = teams.get('home', '')

            # Extract scores from game_score string
            parts = game_score.split(',')
            visitor_score = '0'
            home_score = '0'

            if len(parts) >= 2:
                # Extract visitor score (last number in first part)
                visitor_parts = parts[0].strip().split()
                if visitor_parts:
                    visitor_score = visitor_parts[-1]

                # Extract home score (last number in second part)
                home_parts = parts[1].strip().split()
                if home_parts:
                    home_score = home_parts[-1]

            # Generate SQL command with full team names
            sqlfile.write(f"exec pickem.set_nfl_score( {season}, {week}, {visitor_score}, '{visitor_team}', {home_score}, '{home_team}' );\n")
            sqlfile.write("\n")

        # Write SQL statements
        for player in players:
            gsis_id = player.get('gsis_id', '')
            team = player.get('team', '')
            opponent = get_opponent(team, teams)
            position = player.get('position', '')
            status_full = player.get('status', '')
            name = player.get('name', '')

            # Convert status to single uppercase character
            status_map = {
                'starter': 'S',
                'backup': 'B',
                'inactive': 'NA',
                'did_not_play': 'B'
            }
            status = status_map.get(status_full, status_full[0].upper() if status_full else '')

            # Generate SQL statement
            sql = f"exec stats.find_or_create_rawstat_gsis('{gsis_id}', '{team}', '{opponent}', {week}, {season}, '{position}', '{status}');"

            # Check if GSIS ID is valid (standard format: 00-XXXXXXX or old format like RIV553722)
            if gsis_id and (gsis_id.startswith('00-') or (len(gsis_id) >= 8 and gsis_id[:3].isalpha() and gsis_id[3:].isdigit())):
                # Valid GSIS ID - write normally
                sqlfile.write(sql + "\n")
            else:
                # Invalid or missing GSIS ID - comment it out
                sqlfile.write(f"-- INVALID GSIS: {name} ({team}) - {sql}\n")


def save_snaps_to_sql(snaps, output_path, week, season, short_name_db, players_db):
    """Save gamebook playtime-percentage rows as scoring SQL statements."""
    with open(output_path, 'w', encoding='utf-8') as sqlfile:
        sqlfile.write(f"-- Week {week}, Season {season}\n\n")
        for snap in snaps:
            gsis_id, strategy = match_player_to_database(
                snap['name'], snap['team'], snap['position'], short_name_db, players_db
            )
            sql = (
                f"exec scoring.add_player_snaps('{gsis_id or ''}', {season}, {week}, "
                f"{snap['offense_snaps']}, {float(snap['offense_pct']) / 100:g}, "
                f"{snap['defense_snaps']}, {float(snap['defense_pct']) / 100:g}, "
                f"{snap['st_snaps']}, {float(snap['st_pct']) / 100:g});"
            )
            if gsis_id and gsis_id.startswith('00-'):
                sqlfile.write(sql + '\n')
            else:
                sqlfile.write(
                    f"-- INVALID GSIS: {snap['name']} ({snap['team']}) - {sql}\n"
                )

def save_to_csv(players, output_path, game_score=None):
    """Save player data to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        # Write game score as the first line if available
        if game_score:
            csvfile.write(f"# {game_score}\n")

        fieldnames = ['gsis_id', 'team', 'name', 'position', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for player in players:
            writer.writerow(player)

if __name__ == '__main__':
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Extract player data from NFL gamebook PDF and generate SQL statements')
    parser.add_argument('pdf_files', nargs='*', default=['housea.pdf'], help='PDF file(s) or wildcard pattern(s) to process')
    parser.add_argument('--week', '-w', type=int, required=True, help='Week number')
    parser.add_argument('--season', '-s', type=int, help='Season year (defaults to year from PDF)')
    parser.add_argument('--no-fetch', action='store_true', help='Do not download players.csv, use existing file')
    parser.add_argument('--no-color', action='store_true', help='Disable colored terminal output')
    args = parser.parse_args()

    use_color = sys.stdout.isatty() and not args.no_color and 'NO_COLOR' not in os.environ

    week = args.week

    # Expand glob patterns. This handles both quoted patterns (expanded here)
    # and unquoted patterns (already expanded by the shell into multiple args).
    pdf_files = []
    for pdf_pattern in args.pdf_files:
        pdf_files.extend(glob.glob(pdf_pattern))

    # Remove duplicates while preserving the user's argument/order.
    pdf_files = list(dict.fromkeys(pdf_files))

    if not pdf_files:
        print(colorize(f"ERROR: No files found matching: {', '.join(args.pdf_files)}", 'red', use_color))
        exit(1)

    # Download and load players database once (outside the loop)
    db_path = 'players.csv'
    download_players_database(db_path, force_download=not args.no_fetch)
    short_name_db, players_db = load_players_database(db_path)
    print()  # Blank line after database loading

    # Process each PDF file
    for file_idx, pdf_path in enumerate(pdf_files, 1):
        # Generate output filename from input filename (change to .sql)
        output_path = os.path.splitext(pdf_path)[0] + '.sql'

        players, game_score, season, teams, snap_rows = extract_players_from_pdf(pdf_path)

        # Use season from command line if provided, otherwise use from PDF
        if args.season:
            season = args.season
        elif not season:
            print(colorize(f"ERROR: {pdf_path} - Could not determine season. Use --season parameter.", 'red', use_color))
            continue

        # Match players to database and add GSIS IDs
        matched_count = 0
        unmatched_players = []
        lower_confidence_matches = []

        for player in players:
            gsis_id, strategy = match_player_to_database(player['name'], player['team'], player['position'], short_name_db, players_db)
            player['gsis_id'] = gsis_id if gsis_id else ''
            player['match_strategy'] = strategy

            if gsis_id:
                matched_count += 1
                if is_lower_confidence_match(strategy):
                    lower_confidence_matches.append(
                        f"{player['name']} ({player['team']} {player['position']}) "
                        f"-> {gsis_id} [{strategy}]"
                    )
            else:
                unmatched_players.append(f"{player['name']} ({player['team']} {player['position']})")

        # Save all players (function will comment out invalid ones)
        save_to_sql(players, output_path, week, season, teams, game_score)

        if snap_rows:
            snaps_output_path = os.path.splitext(pdf_path)[0] + '_snaps.sql'
            save_snaps_to_sql(
                snap_rows,
                snaps_output_path,
                week,
                season,
                short_name_db,
                players_db,
            )
            print(f"  Wrote {len(snap_rows)} snap rows -> {snaps_output_path}")

        # Compact single-line output
        visitor_team = teams.get('visitor', '')
        home_team = teams.get('home', '')
        match_pct = (matched_count * 100) // len(players) if len(players) > 0 else 0
        summary = f"{visitor_team} @ {home_team}: {len(players)} players, {match_pct}% matched -> {output_path}"
        summary_color = 'red' if unmatched_players else 'yellow' if lower_confidence_matches else 'green'
        print(colorize(summary, summary_color, use_color))

        # Show unmatched players if any
        if unmatched_players:
            for name in unmatched_players:
                print(colorize(f"  UNMATCHED: {name}", 'red', use_color))

        # Show fallback matches without interrupting best-effort processing.
        if lower_confidence_matches:
            print(colorize(f"  CHECK: {len(lower_confidence_matches)} lower-confidence match(es)", 'yellow', use_color))
            for match in lower_confidence_matches:
                print(colorize(f"    {match}", 'yellow', use_color))
