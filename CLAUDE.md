# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python utility that extracts player data from NFL gamebook PDFs and generates SQL statements for database import. The tool parses structured sections of official NFL gamebooks (starters, substitutions, inactive players) and matches players to their GSIS IDs using the nflverse player database.

## Common Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Parser
```bash
# Basic usage with week number (season auto-detected from PDF)
python extract_players.py <pdf_file> --week <week_number>

# Specify season explicitly
python extract_players.py housea.pdf --week 7 --season 2024

# Process multiple PDFs using glob patterns
python extract_players.py "*.pdf" --week 7
```

### Testing/Debugging
```bash
# Debug PDF structure (shows specific line ranges)
python debug_pdf.py
```

## Architecture

### Core Components

**extract_players.py** - Main parsing engine with several key subsystems:

1. **PDF Parsing Pipeline** (lines 357-512)
   - Extracts text from first page using pdfplumber
   - Identifies sections by text markers: "Lineups", "Substitutions", "Did Not Play", "Not Active"
   - Uses bbox-based extraction to split visitor/home team columns
   - Parses game metadata (date, score, teams)

2. **Player Name Parsing** (lines 8-92)
   - Complex regex patterns handle edge cases: Jo.Phillips, To'oTo'o, Van Pran-Granger, O'Brien
   - Pattern: `([A-Z/]+)\s+(\d+)\s+([A-Z][a-z]*\.[A-Z]...)`
   - Three parsing functions for different PDF layouts:
     - `parse_lineup_line()` - 4-column starter lineups
     - `parse_two_column_line()` - 2-column backups/inactive
     - `parse_player_list()` - comma/space-separated lists

3. **Player Matching System** (lines 224-306)
   - Multi-strategy fallback approach in `match_player_to_database()`
   - Strategy priority:
     1. short_name + team + position (preferred)
     2. short_name + team
     3. other name variants + team + position
     4. other name variants + team
     5. name with spaces removed
     6. partial last name match (requires team)
   - All strategies require team match (no cross-team matching)
   - Returns tuple: (gsis_id, strategy_name) for debugging

4. **Database Integration** (lines 93-184)
   - Downloads nflverse players.csv if missing
   - Builds two in-memory lookup dictionaries:
     - `short_name_db` - preferred lookup (short_name format)
     - `players_db` - fallback (display_name, football_name, first initial + last name)
   - Filters to active players or developmental players (status='ACT' or status='DEV' and ngs_status='DEV')
   - Handles multiple players with same name via lists

5. **SQL Generation** (lines 522-582)
   - Outputs Oracle PL/SQL exec statements
   - Format: `exec stats.find_or_create_rawstat_gsis('<gsis_id>', '<team>', '<opponent>', <week>, <season>, '<position>', '<status>')`
   - Status codes: S=Starter, B=Backup/DidNotPlay, I=Inactive
   - Comments out players without valid GSIS IDs (format: 00-XXXXXXX or old format like RIV553722)
   - Includes game score SQL: `exec pickem.set_nfl_score(...)`

### Key Data Structures

**Player Dictionary:**
```python
{
    'team': str,        # Full team name (e.g., "Houston Texans")
    'name': str,        # Name as parsed from PDF (e.g., "Jo.Phillips")
    'position': str,    # Position code (e.g., "WR", "QB")
    'status': str,      # 'starter', 'backup', 'inactive', 'did_not_play'
    'gsis_id': str,     # Matched GSIS ID (e.g., "00-0012345")
    'match_strategy': str  # Which strategy found the match
}
```

**Teams Dictionary:**
```python
{
    'visitor': str,  # Full visitor team name
    'home': str      # Full home team name
}
```

### Team Abbreviation Mapping

The `get_team_abbr()` function (lines 186-222) maps full team names to standard NFL abbreviations. This is critical for player matching since the nflverse database uses abbreviations while PDFs use full names.

### Important Patterns

1. **PDF Section Detection**: Uses text markers but relies on bbox coordinates for accurate column separation
2. **Name Complexity**: Parser must handle apostrophes, hyphens, capital letters mid-name, and period-separated initials
3. **Match Strategy Fallback**: Always requires team match - prevents false matches across teams
4. **GSIS ID Validation**: Only includes players with valid ID formats in final SQL output
5. **Opponent Resolution**: Uses `get_opponent()` to find opponent from teams dictionary

## Development Notes

- The parser is tightly coupled to NFL gamebook PDF format - changes to PDF structure require updating line parsing logic
- bbox coordinates are used for accurate column splitting in substitutions/inactive sections
- Recent commits show evolution of matching strategies (preferring short_name, removing cross-team matching)
- Output is intentionally compact: one line per file with match percentage and unmatched player list
