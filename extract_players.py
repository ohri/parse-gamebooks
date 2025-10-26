import pdfplumber
import csv
import re
import os
import urllib.request

def parse_lineup_line(line):
    """Parse a single lineup line into players for both teams."""
    players = []

    # Each line has 4 sections: HOU Offense, HOU Defense, SEA Offense, SEA Defense
    # Pattern: POS NUM NAME
    pattern = r'([A-Z/]+)\s+(\d+)\s+([A-Z]\.[A-Za-z\'-]+)'

    matches = re.findall(pattern, line)

    # There should be 4 matches per line (one for each column)
    # Columns 0 and 1 are Houston, columns 2 and 3 are Seattle
    for idx, (position, number, name) in enumerate(matches):
        team = 'Houston Texans' if idx < 2 else 'Seattle Seahawks'
        players.append({
            'team': team,
            'name': name,
            'position': position,
            'status': 'starter'
        })

    return players

def parse_two_column_line(line):
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

    # Pattern: POS NUM NAME
    pattern = r'([A-Z/]+)\s+(\d+)\s+([A-Z]\.[A-Za-z\'-]+)'

    # Parse left half (Houston)
    matches_left = re.findall(pattern, left_half)
    for position, number, name in matches_left:
        players.append({
            'team': 'Houston Texans',
            'name': name,
            'position': position,
            'status': 'backup'
        })

    # Parse right half (Seattle)
    matches_right = re.findall(pattern, right_half)
    for position, number, name in matches_right:
        players.append({
            'team': 'Seattle Seahawks',
            'name': name,
            'position': position,
            'status': 'backup'
        })

    return players

def parse_player_list(text, team_name, status):
    """Parse a comma-separated or space-separated list of players."""
    players = []

    # Pattern: POS NUM NAME
    pattern = r'([A-Z/]+)\s+(\d+)\s+([A-Z]\.[A-Za-z\'-]+)'

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
    """Load the players database and create a lookup dictionary."""
    players_db = {}

    if not os.path.exists(db_path):
        print(f"Players database not found at {db_path}")
        return players_db

    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                gsis_id = row.get('gsis_id', '')
                if not gsis_id:
                    continue

                # Get all name variants
                display_name = row.get('display_name', '')
                short_name = row.get('short_name', '')
                football_name = row.get('football_name', '')
                first_name = row.get('first_name', '')
                last_name = row.get('last_name', '')
                team = row.get('latest_team', '')

                player_data = {
                    'gsis_id': gsis_id,
                    'display_name': display_name,
                    'short_name': short_name,
                    'latest_team': team
                }

                # Store by multiple name formats with team
                name_variants = []

                # Add display name
                if display_name:
                    name_variants.append(display_name)

                # Add short name from database (e.g., "T.Woolen")
                if short_name:
                    name_variants.append(short_name)

                # Add football name
                if football_name:
                    name_variants.append(football_name)

                # Generate first initial + last name (e.g., "N.Collins")
                if first_name and last_name:
                    name_variants.append(f"{first_name[0]}.{last_name}")

                # Store all variants
                for name in name_variants:
                    if name:
                        key = (name.lower().strip(), team.upper())
                        if key not in players_db:
                            players_db[key] = player_data

        print(f"Loaded {len(players_db)} player records from database")
        return players_db
    except Exception as e:
        print(f"Error loading players database: {e}")
        return {}

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

def match_player_to_database(player_name, team_name, players_db):
    """Match a player to the database and return their GSIS ID."""
    team_abbr = get_team_abbr(team_name)
    player_name_lower = player_name.lower().strip()

    # Strategy 1: Exact match with team
    key = (player_name_lower, team_abbr)
    if key in players_db:
        return players_db[key]['gsis_id']

    # Strategy 2: Try without team (for players who may have changed teams)
    for (name, team), data in players_db.items():
        if name == player_name_lower:
            return data['gsis_id']

    # Strategy 3: Try with spaces removed (e.g., "N.Collins" vs "N. Collins")
    player_name_no_space = player_name_lower.replace(' ', '')
    for (name, team), data in players_db.items():
        if name.replace(' ', '') == player_name_no_space and team == team_abbr:
            return data['gsis_id']

    # Strategy 4: Try partial match on last name only (as last resort)
    if '.' in player_name:
        last_name = player_name.split('.')[-1].lower().strip()
        for (name, team), data in players_db.items():
            if team == team_abbr and name.endswith(last_name):
                return data['gsis_id']

    return None

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
                players = parse_lineup_line(line)
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
                    texans_part = parts[0]
                    seahawks_part = 'CB 1 D.Kendrick' + parts[1]

                    texans_players = parse_player_list(texans_part, 'Houston Texans', 'backup')
                    seahawks_players = parse_player_list(seahawks_part, 'Seattle Seahawks', 'backup')

                    all_players.extend(texans_players)
                    all_players.extend(seahawks_players)

            # Process remaining substitution lines (they have both teams)
            for line_idx in range(first_sub_line_idx + 1, not_active_idx):
                line = lines[line_idx]
                if 'Did Not Play' not in line:
                    players = parse_two_column_line(line)
                    all_players.extend(players)

        # Parse "Did Not Play" section
        if did_not_play_idx and not_active_idx:
            dnp_line_idx = did_not_play_idx + 1
            if dnp_line_idx < len(lines):
                dnp_line = lines[dnp_line_idx]

                # Split at "QB 2 D.Lock"
                if 'QB 2 D.Lock' in dnp_line:
                    parts = dnp_line.split('QB 2 D.Lock')
                    texans_dnp_text = parts[0]
                    seahawks_dnp_text = 'QB 2 D.Lock' + parts[1]

                    texans_dnp = parse_player_list(texans_dnp_text, 'Houston Texans', 'did_not_play')
                    seahawks_dnp = parse_player_list(seahawks_dnp_text, 'Seattle Seahawks', 'did_not_play')

                    all_players.extend(texans_dnp)
                    all_players.extend(seahawks_dnp)

        # Parse inactive players
        if not_active_idx:
            # Process first inactive line
            first_inactive_idx = not_active_idx + 1
            if first_inactive_idx < len(lines):
                inactive_line = lines[first_inactive_idx]

                # Split at "3QB 6 J.Milroe"
                if '3QB 6 J.Milroe' in inactive_line:
                    parts = inactive_line.split('3QB 6 J.Milroe')
                    texans_inactive_text = parts[0]
                    seahawks_inactive_text = '3QB 6 J.Milroe' + parts[1]

                    texans_inactive = parse_player_list(texans_inactive_text, 'Houston Texans', 'inactive')
                    seahawks_inactive = parse_player_list(seahawks_inactive_text, 'Seattle Seahawks', 'inactive')

                    all_players.extend(texans_inactive)
                    all_players.extend(seahawks_inactive)

            # Process second inactive line if it exists
            second_inactive_idx = not_active_idx + 2
            if second_inactive_idx < len(lines) and 'Field Goals' not in lines[second_inactive_idx]:
                # This line likely only has Seattle inactives
                inactive_line2 = lines[second_inactive_idx]
                # Check if it starts with a position (Seattle) or continues Houston
                # If it starts with uppercase letter followed by slash or space and number, it's likely Seattle
                if re.match(r'^[A-Z]', inactive_line2):
                    seahawks_inactive2 = parse_player_list(inactive_line2, 'Seattle Seahawks', 'inactive')
                    all_players.extend(seahawks_inactive2)
                else:
                    texans_inactive2 = parse_player_list(inactive_line2, 'Houston Texans', 'inactive')
                    all_players.extend(texans_inactive2)

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
        # Write game score as a comment if available
        if game_score:
            sqlfile.write(f"-- {game_score}\n")
            sqlfile.write(f"-- Week {week}, Season {season}\n")
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

            sqlfile.write(sql + "\n")

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

    pdf_path = args.pdf_file
    week = args.week

    # Generate output filename from input filename (change to .sql)
    output_path = os.path.splitext(pdf_path)[0] + '.sql'

    print(f"Extracting player data from {pdf_path}...")
    players, game_score, season, teams = extract_players_from_pdf(pdf_path)

    # Use season from command line if provided, otherwise use from PDF
    if args.season:
        season = args.season
        print(f"Using season from command line: {season}")
    elif season:
        print(f"Using season from PDF: {season}")
    else:
        print("ERROR: Could not determine season from PDF. Please provide --season parameter.")
        exit(1)

    if game_score:
        print(f"Game Score: {game_score}")

    print(f"Found {len(players)} players")

    # Download and load players database
    db_path = 'players.csv'
    download_players_database(db_path)
    players_db = load_players_database(db_path)

    # Match players to database and add GSIS IDs
    print("\nMatching players to database...")
    matched_count = 0
    unmatched_players = []
    non_standard_gsis = []

    for player in players:
        gsis_id = match_player_to_database(player['name'], player['team'], players_db)
        player['gsis_id'] = gsis_id if gsis_id else ''

        if gsis_id:
            matched_count += 1
            # Check if GSIS ID follows standard format (00-XXXXXXX)
            if not gsis_id.startswith('00-'):
                non_standard_gsis.append({
                    'name': player['name'],
                    'team': player['team'],
                    'gsis_id': gsis_id,
                    'position': player['position'],
                    'status': player['status']
                })
        else:
            unmatched_players.append(f"{player['name']} ({player['team']})")

    print(f"Matched {matched_count}/{len(players)} players ({matched_count*100//len(players)}%)")

    if unmatched_players:
        print(f"\nUnmatched players ({len(unmatched_players)}):")
        for name in unmatched_players[:10]:  # Show first 10
            print(f"  - {name}")
        if len(unmatched_players) > 10:
            print(f"  ... and {len(unmatched_players) - 10} more")

    if non_standard_gsis:
        print(f"\n!!! WARNING: {len(non_standard_gsis)} player(s) with non-standard GSIS ID format (will be excluded):")
        for p in non_standard_gsis[:15]:  # Show first 15
            print(f"  - {p['name']:20} ({p['team']:20}) | GSIS: {p['gsis_id']:15} | {p['position']:3} {p['status']}")
        if len(non_standard_gsis) > 15:
            print(f"  ... and {len(non_standard_gsis) - 15} more")

    # Filter out players with non-standard GSIS IDs
    players_with_standard_gsis = [p for p in players if p.get('gsis_id', '').startswith('00-')]

    if len(players_with_standard_gsis) < len(players):
        print(f"\nExcluded {len(players) - len(players_with_standard_gsis)} player(s) without standard GSIS ID")

    print(f"\nGenerating SQL statements for {len(players_with_standard_gsis)} players...")
    print(f"Week: {week}, Season: {season}")
    print(f"Saving to {output_path}...")
    save_to_sql(players_with_standard_gsis, output_path, week, season, teams, game_score)

    print("Done!")
    print(f"\nFirst few entries:")
    for player in players_with_standard_gsis[:10]:
        gsis = player.get('gsis_id', '')[:10] + '...' if len(player.get('gsis_id', '')) > 10 else player.get('gsis_id', 'N/A')
        print(f"  {gsis:13} | {player['team']:20} | {player['name']:20} | {player['position']:5} | {player['status']}")

    # Show stats by team (for saved players only)
    texans_count = len([p for p in players_with_standard_gsis if p['team'] == 'Houston Texans'])
    seahawks_count = len([p for p in players_with_standard_gsis if p['team'] == 'Seattle Seahawks'])
    print(f"\nHouston Texans: {texans_count} players")
    print(f"Seattle Seahawks: {seahawks_count} players")

    # Show stats by status (for saved players only)
    starters = len([p for p in players_with_standard_gsis if p['status'] == 'starter'])
    backups = len([p for p in players_with_standard_gsis if p['status'] == 'backup'])
    inactive = len([p for p in players_with_standard_gsis if p['status'] == 'inactive'])
    dnp = len([p for p in players_with_standard_gsis if p['status'] == 'did_not_play'])
    print(f"\nStarters: {starters}, Backups: {backups}, Inactive: {inactive}, Did Not Play: {dnp}")
