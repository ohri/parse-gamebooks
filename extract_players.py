import pdfplumber
import csv
import re
import os
import urllib.request
import glob

def parse_lineup_line(line, visitor_team, home_team):
    """Parse a single lineup line into players for both teams."""
    players = []

    # Each line has 4 sections: Team1 Offense, Team1 Defense, Team2 Offense, Team2 Defense
    # Pattern: POS NUM NAME (handles McCaffrey, O'Brien, To'oTo'o, Van Pran-Granger, etc.)
    pattern = r"([A-Z/]+)\s+(\d+)\s+([A-Z]\.[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*|[\'-][A-Za-z]+)(?:[\'-][A-Za-z]+)*(?:\s+[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*|[\'-][A-Za-z]+)(?:[\'-][A-Za-z]+)*)*)"

    matches = re.findall(pattern, line)

    # There should be 4 matches per line (one for each column)
    # Columns 0 and 1 are visitor team, columns 2 and 3 are home team
    for idx, (position, number, name) in enumerate(matches):
        team = visitor_team if idx < 2 else home_team
        players.append({
            'team': team,
            'name': name,
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

    # Pattern: POS NUM NAME (handles McCaffrey, O'Brien, To'oTo'o, Van Pran-Granger, etc.)
    pattern = r"([A-Z/]+)\s+(\d+)\s+([A-Z]\.[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*|[\'-][A-Za-z]+)(?:[\'-][A-Za-z]+)*(?:\s+[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*|[\'-][A-Za-z]+)(?:[\'-][A-Za-z]+)*)*)"

    # Parse left half (visitor team)
    matches_left = re.findall(pattern, left_half)
    for position, number, name in matches_left:
        players.append({
            'team': visitor_team,
            'name': name,
            'position': position,
            'status': 'backup'
        })

    # Parse right half (home team)
    matches_right = re.findall(pattern, right_half)
    for position, number, name in matches_right:
        players.append({
            'team': home_team,
            'name': name,
            'position': position,
            'status': 'backup'
        })

    return players

def parse_player_list(text, team_name, status):
    """Parse a comma-separated or space-separated list of players."""
    players = []

    # Pattern: POS NUM NAME (handles McCaffrey, O'Brien, To'oTo'o, Van Pran-Granger, etc.)
    pattern = r"([A-Z/]+)\s+(\d+)\s+([A-Z]\.[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*|[\'-][A-Za-z]+)(?:[\'-][A-Za-z]+)*(?:\s+[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*|[\'-][A-Za-z]+)(?:[\'-][A-Za-z]+)*)*)"

    matches = re.findall(pattern, text)

    for position, number, name in matches:
        players.append({
            'team': team_name,
            'name': name,
            'position': position,
            'status': status
        })

    return players

def download_players_database(output_path='players.csv'):
    """Download the nflverse players database if it doesn't exist."""
    if os.path.exists(output_path):
        print(f"Players database already exists at {output_path}")
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

                # Only consider active players
                status = row.get('status', '')
                if status != 'ACT':
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
        'Los Angeles Rams': 'LAR',
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
            if db_position == position:
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
            if db_position == position:
                return player_data['gsis_id'], 'other_name_team_position'
        # If no position match, keep first candidate
        candidate = player_list[0]['gsis_id'] if player_list else None
    else:
        candidate = None

    # Strategy 3: Return the team match even if position doesn't match (from Strategy 2)
    if candidate:
        return candidate, 'other_name_team'

    # Strategy 4: Try with spaces removed in short_name (e.g., "N.Collins" vs "N. Collins")
    player_name_no_space = player_name_lower.replace(' ', '')
    for (name, team), player_list in short_name_db.items():
        if name.replace(' ', '') == player_name_no_space and team == team_abbr and player_list:
            # Check position first
            for player_data in player_list:
                db_position = player_data.get('position', '')
                if db_position == position:
                    return player_data['gsis_id'], 'short_name_no_spaces_position'
            # Return first match if position doesn't match
            return player_list[0]['gsis_id'], 'short_name_no_spaces'

    # Strategy 5: Try with spaces removed in other names
    for (name, team), player_list in players_db.items():
        if name.replace(' ', '') == player_name_no_space and team == team_abbr and player_list:
            # Check position first
            for player_data in player_list:
                db_position = player_data.get('position', '')
                if db_position == position:
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
                    if db_position == position:
                        return player_data['gsis_id'], 'short_name_partial_lastname_position'
                # Return first match if position doesn't match
                return player_list[0]['gsis_id'], 'short_name_partial_lastname'
        # Then check other names
        for (name, team), player_list in players_db.items():
            if team == team_abbr and name.endswith(last_name) and player_list:
                # Check position first
                for player_data in player_list:
                    db_position = player_data.get('position', '')
                    if db_position == position:
                        return player_data['gsis_id'], 'other_name_partial_lastname_position'
                # Return first match if position doesn't match
                return player_list[0]['gsis_id'], 'other_name_partial_lastname'

    return None, None

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

def extract_players_from_pdf(pdf_path):
    """Main function to extract all player data from the PDF."""
    all_players = []
    game_score = None
    season = None
    teams = {}

    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()
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

        # Parse substitutions (backups)
        if substitutions_idx and not_active_idx:
            # Line after "Substitutions Substitutions" header
            first_sub_line_idx = substitutions_idx + 1

            # Process the first substitutions line differently (it's clearly split)
            if first_sub_line_idx < len(lines):
                first_sub_line = lines[first_sub_line_idx]

                # Split at "CB 1 D.Kendrick"
                if 'CB 1 D.Kendrick' in first_sub_line:
                    parts = first_sub_line.split('CB 1 D.Kendrick')
                    visitor_part = parts[0]
                    home_part = 'CB 1 D.Kendrick' + parts[1]

                    visitor_players = parse_player_list(visitor_part, visitor_team, 'backup')
                    home_players = parse_player_list(home_part, home_team, 'backup')

                    all_players.extend(visitor_players)
                    all_players.extend(home_players)

            # Process remaining substitution lines (they have both teams)
            for line_idx in range(first_sub_line_idx + 1, not_active_idx):
                line = lines[line_idx]
                if 'Did Not Play' not in line:
                    players = parse_two_column_line(line, visitor_team, home_team)
                    all_players.extend(players)

        # Parse "Did Not Play" section
        if did_not_play_idx and not_active_idx:
            dnp_line_idx = did_not_play_idx + 1
            if dnp_line_idx < len(lines):
                dnp_line = lines[dnp_line_idx]

                # Split at "QB 2 D.Lock"
                if 'QB 2 D.Lock' in dnp_line:
                    parts = dnp_line.split('QB 2 D.Lock')
                    visitor_dnp_text = parts[0]
                    home_dnp_text = 'QB 2 D.Lock' + parts[1]

                    visitor_dnp = parse_player_list(visitor_dnp_text, visitor_team, 'did_not_play')
                    home_dnp = parse_player_list(home_dnp_text, home_team, 'did_not_play')

                    all_players.extend(visitor_dnp)
                    all_players.extend(home_dnp)

        # Parse inactive players
        if not_active_idx:
            # Process first inactive line
            first_inactive_idx = not_active_idx + 1
            if first_inactive_idx < len(lines):
                inactive_line = lines[first_inactive_idx]

                # Split at "3QB 6 J.Milroe"
                if '3QB 6 J.Milroe' in inactive_line:
                    parts = inactive_line.split('3QB 6 J.Milroe')
                    visitor_inactive_text = parts[0]
                    home_inactive_text = '3QB 6 J.Milroe' + parts[1]

                    visitor_inactive = parse_player_list(visitor_inactive_text, visitor_team, 'inactive')
                    home_inactive = parse_player_list(home_inactive_text, home_team, 'inactive')

                    all_players.extend(visitor_inactive)
                    all_players.extend(home_inactive)

            # Process second inactive line if it exists
            second_inactive_idx = not_active_idx + 2
            if second_inactive_idx < len(lines) and 'Field Goals' not in lines[second_inactive_idx]:
                # This line likely only has home team inactives
                inactive_line2 = lines[second_inactive_idx]
                # Check if it starts with a position (home team) or continues visitor team
                # If it starts with uppercase letter followed by slash or space and number, it's likely home team
                if re.match(r'^[A-Z]', inactive_line2):
                    home_inactive2 = parse_player_list(inactive_line2, home_team, 'inactive')
                    all_players.extend(home_inactive2)
                else:
                    visitor_inactive2 = parse_player_list(inactive_line2, visitor_team, 'inactive')
                    all_players.extend(visitor_inactive2)

    return all_players, game_score, season, teams

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
                'inactive': 'I',
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
    parser.add_argument('pdf_file', nargs='?', default='housea.pdf', help='PDF file to process')
    parser.add_argument('--week', '-w', type=int, required=True, help='Week number')
    parser.add_argument('--season', '-s', type=int, help='Season year (defaults to year from PDF)')
    args = parser.parse_args()

    pdf_pattern = args.pdf_file
    week = args.week

    # Expand glob pattern to get list of PDF files
    pdf_files = glob.glob(pdf_pattern)

    if not pdf_files:
        print(f"ERROR: No files found matching pattern '{pdf_pattern}'")
        exit(1)

    # Download and load players database once (outside the loop)
    db_path = 'players.csv'
    download_players_database(db_path)
    short_name_db, players_db = load_players_database(db_path)
    print()  # Blank line after database loading

    # Process each PDF file
    for file_idx, pdf_path in enumerate(pdf_files, 1):
        # Generate output filename from input filename (change to .sql)
        output_path = os.path.splitext(pdf_path)[0] + '.sql'

        players, game_score, season, teams = extract_players_from_pdf(pdf_path)

        # Use season from command line if provided, otherwise use from PDF
        if args.season:
            season = args.season
        elif not season:
            print(f"ERROR: {pdf_path} - Could not determine season. Use --season parameter.")
            continue

        # Match players to database and add GSIS IDs
        matched_count = 0
        unmatched_players = []

        for player in players:
            gsis_id, strategy = match_player_to_database(player['name'], player['team'], player['position'], short_name_db, players_db)
            player['gsis_id'] = gsis_id if gsis_id else ''
            player['match_strategy'] = strategy

            if gsis_id:
                matched_count += 1
            else:
                unmatched_players.append(f"{player['name']} ({player['team']} {player['position']})")

        # Save all players (function will comment out invalid ones)
        save_to_sql(players, output_path, week, season, teams, game_score)

        # Compact single-line output
        visitor_team = teams.get('visitor', '')
        home_team = teams.get('home', '')
        match_pct = (matched_count * 100) // len(players) if len(players) > 0 else 0
        print(f"{visitor_team} @ {home_team}: {len(players)} players, {match_pct}% matched -> {output_path}")

        # Show unmatched players if any
        if unmatched_players:
            for name in unmatched_players:
                print(f"  UNMATCHED: {name}")
