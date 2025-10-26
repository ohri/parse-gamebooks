# NFL Gamebook Parser

Python script to extract player data from NFL gamebook PDFs and generate SQL statements for database import.

## Features

- Extracts player information from NFL gamebook PDFs (starters, backups, inactive players)
- Matches players with GSIS IDs from the nflverse database
- Generates SQL statements for Oracle database import
- Excludes players without standard GSIS ID format (00-XXXXXXX)
- Automatically downloads nflverse players database if not present

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

```bash
python extract_players.py <pdf_file> --week <week_number> [--season <season_year>]
```

### Examples

```bash
# Process a gamebook for week 7 (season auto-detected from PDF)
python extract_players.py housea.pdf --week 7

# Process a gamebook for week 7 of 2024 season
python extract_players.py housea.pdf --week 7 --season 2024
```

## Output

The script generates a `.sql` file with the same base name as the input PDF containing:
- Game score and week/season info as comments
- SQL statements in the format:
  ```sql
  exec stats.find_or_create_rawstat_gsis('<gsis_id>', '<team>', '<opponent>', <week>, <season>, '<position>', '<status>');
  ```

### Status Codes
- `S` - Starter
- `B` - Backup (includes "Did Not Play" players)
- `I` - Inactive

## Data Source

Player GSIS IDs are matched against the [nflverse players database](https://github.com/nflverse/nflverse-data/releases/download/players/players.csv).
