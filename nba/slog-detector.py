# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "balldontlie",
#     "rich",
#     "typer",
#     "python-dotenv", # For loading environment variables from .env
# ]
# ///

import datetime
import os
import sys

import balldontlie
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# --- CONFIGURATION ---
API_KEY_ENV_VAR = "BALLDONTLIE_API_KEY"

BALLDONTLIE_API_KEY: str | None = None

# Initialize Typer App
app = typer.Typer(help="Analyzes the NBA schedule to identify back-to-back (B2B) and 3-in-3 fatigue situations.")


def fetch_games_for_dates(dates: list[str], api_key: str) -> dict[str, list[dict[str, str]]]:
    """
    Fetches the NBA schedule for multiple dates in a single API request.
    The balldontlie API endpoint is: GET /games.

    Args:
        dates: A list of dates in 'YYYY-MM-DD' format.
        api_key: The API key used for the balldontlie service.

    Returns:
        A dictionary mapping each date string to a list of its games,
        where each game dict has 'home_team' and 'visitor_team' keys.
        Returns an empty dict if the API call fails.
    """
    # Use the securely loaded API key to initialize the client
    api = balldontlie.BalldontlieAPI(api_key=api_key)
    games_by_date: dict[str, list[dict[str, str]]] = {date: [] for date in dates}

    try:
        rprint(f"Making single API request to balldontlie for dates: {', '.join(dates)}...")
        api_response = api.nba.games.list(dates=dates)
        games_data = api_response.data

        # Process the list of game dictionaries and group by date
        if games_data:
            for game in games_data:
                game_date_dt = datetime.datetime.fromisoformat(game.date.replace('Z', '+00:00')).date()
                game_date_str = game_date_dt.strftime('%Y-%m-%d')

                if game_date_str in games_by_date:
                    home_abbr = game.home_team.abbreviation
                    visitor_abbr = game.visitor_team.abbreviation

                    if home_abbr and visitor_abbr:
                        games_by_date[game_date_str].append({
                            "home_team": home_abbr,
                            "visitor_team": visitor_abbr
                        })

        for date_str, games in games_by_date.items():
            if games:
                rprint(f"-> Successfully processed {len(games)} games for [bold green]{date_str}[/bold green].")
            else:
                rprint(f"-> Found no games for [dim]{date_str}[/dim].")

    except Exception as e:
        rprint(f"[bold red]CRITICAL ERROR: Failed to fetch live data from balldontlie for dates {dates}.[/bold red]")
        rprint(f"Details: {e}")
        return {}

    return games_by_date


def get_teams_playing_on_date(games: list[dict[str, str]]) -> set[str]:
    """Extracts a set of all team abbreviations playing on a given day."""
    teams = set()
    for game in games:
        teams.add(game['home_team'])
        teams.add(game['visitor_team'])
    return teams

def print_key():
    """Prints the fatigue key"""
    rprint("\n[bold cyan]📊 SCHEDULE FATIGUE KEY:[/bold cyan]")
    rprint("- [green]🟢[/green] [bold green]Rested[/bold green]: Last game was [bold]2+ days ago[/bold].")
    rprint("- [yellow]🟠[/yellow] [bold yellow]B2B[/bold yellow] (Back-to-Back): Playing today after playing [bold]yesterday[/bold].")
    rprint("- [red]🔴[/red] [bold red]3/3[/bold red] (Three-in-Three): Playing today after playing [bold]yesterday AND two days ago[/bold] (Triple-Fatigue).")
    rprint()

def _get_fatigue_status(team_abbr: str, teams_playing_yesterday: set[str], teams_playing_two_days_ago: set[str]) -> str:
    """Calculates the raw fatigue status for a team."""
    is_playing_yesterday = team_abbr in teams_playing_yesterday
    is_playing_two_days_ago = team_abbr in teams_playing_two_days_ago

    is_3in3 = is_playing_yesterday and is_playing_two_days_ago
    is_b2b = is_playing_yesterday

    if is_3in3:
        # 3/3 overrides B2B
        return "3/3"
    elif is_b2b:
        return "B2B"
    else:
        # Rested means last game was 2+ days ago
        return "Rested"

def _get_fatigue_rich_string(status: str) -> str:
    """Converts the raw fatigue status string into a Rich formatted string."""
    if status == "3/3":
        return "[bold red]🔴[/bold red]" # Three-in-Three: Critical Fatigue
    elif status == "B2B":
        return "[bold yellow]🟠[/bold yellow]" # Back-to-Back: High Fatigue
    else:
        return "[bold green]🟢[/bold green]" # Rested: Low Fatigue

@app.command(name="analyze")
def analyze_schedule_command(
        # Use typer.Option to make the date configurable via CLI, with a default of today
        date_str: str = typer.Option(
            (datetime.date.today()).strftime('%Y-%m-%d'),
            "--date",
            "-d",
            help="The target date for NBA schedule analysis (YYYY-MM-DD). Defaults to today.",
            show_default=True,
        ),
):
    """
    Analyzes the schedule for the given date to identify back-to-backs (B2B)
    and 3-in-3 situations, outputting results using the rich library.
    """

    if not BALLDONTLIE_API_KEY:
        rprint(f"[bold red]FATAL ERROR: API Key Missing![/bold red]")
        raise typer.Exit(code=1)

    # Initialize rich Console for all output
    console = Console()

    try:
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        console.print(f"[bold red]Error:[/bold red] Invalid date format. Please use YYYY-MM-DD (e.g., 2024-11-20).")
        raise typer.Exit(code=1)

    target_date_str = target_date.strftime('%Y-%m-%d')
    date_yesterday_str = (target_date - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    date_two_days_ago_str = (target_date - datetime.timedelta(days=2)).strftime('%Y-%m-%d')

    console.rule(f"[bold white on blue] NBA Schedule Fatigue Status for {target_date_str} [/bold white on blue]")

    dates_to_fetch = [target_date_str, date_yesterday_str, date_two_days_ago_str]

    games_by_date = fetch_games_for_dates(dates_to_fetch, BALLDONTLIE_API_KEY)

    # Extract the games for each day from the requests result
    games_today = games_by_date.get(target_date_str, [])

    if not games_today:
        console.print(f"\n[i]No NBA games found for the target date {target_date_str}.[/i]")
        return

    games_yesterday = games_by_date.get(date_yesterday_str, [])
    games_two_days_ago = games_by_date.get(date_two_days_ago_str, [])


    # Get Teams Playing on each Day
    teams_playing_yesterday = get_teams_playing_on_date(games_yesterday)
    teams_playing_two_days_ago = get_teams_playing_on_date(games_two_days_ago)

    simplified_results: list[str] = []

    for game in games_today:
        home_team_abbr = game['home_team']
        visitor_team_abbr = game['visitor_team']

        # Home Team Status
        home_status = _get_fatigue_status(home_team_abbr, teams_playing_yesterday, teams_playing_two_days_ago)
        home_emoji = _get_fatigue_rich_string(home_status)

        # Visitor Team Status
        visitor_status = _get_fatigue_status(visitor_team_abbr, teams_playing_yesterday, teams_playing_two_days_ago)
        visitor_emoji = _get_fatigue_rich_string(visitor_status)

        # Format: (Visitor Emoji) VIS [at] HOME (Home Emoji)
        game_line = f"{visitor_emoji} [bold]{visitor_team_abbr}[/bold] [dim]at[/dim] [bold]{home_team_abbr}[/bold] {home_emoji}"

        simplified_results.append(game_line)

    if not simplified_results:
        console.print(f"\n[i]No NBA games could be analyzed for {target_date_str} due to missing data or no games scheduled.[/i]")
        return

    table = Table(title=f"[bold] {target_date_str} Matchups ({len(simplified_results)} Games)[/bold]",
                  show_header=True,
                  header_style="bold underline white on black",
                  border_style="dim",
                  show_lines=True)

    table.add_column("GAME MATCHUP", justify="left", style="cyan")

    for game_line in simplified_results:
        table.add_row(game_line)

    print_key()
    console.print(table)

def test_fatigue_logic():
    """
    Tests the core fatigue calculation logic
    with various combinations of previous game schedules.
    """
    rprint("\n[bold yellow]--- Running Fatigue Logic Tests ---[/bold yellow]")

    # Define the teams that played on previous days for the tests
    TEAMS_YESTERDAY = set(["PHX", "DEN", "TOR", "SAC"])
    TEAMS_TWO_DAYS_AGO = set(["GSW", "DEN", "TOR", "NYK"])

    test_cases = [
        # Team, Expected Status, Description
        ("LAL", "Rested", "Case 1: Rested (Played neither day)"),
        ("SAC", "B2B", "Case 2: B2B (Played yesterday only)"),
        ("DEN", "3/3", "Case 3: 3/3 (Played yesterday AND two days ago)"),
        ("NYK", "Rested", "Case 4: Rested (Played two days ago only)"),
    ]

    all_passed = True
    for team_abbr, expected_status, description in test_cases:
        actual_status = _get_fatigue_status(team_abbr, TEAMS_YESTERDAY, TEAMS_TWO_DAYS_AGO)

        if actual_status == expected_status:
            rprint(f"{description}: [bold green]PASS[/bold green] (Team {team_abbr} -> {actual_status})")
        else:
            rprint(f"{description}: [bold red]FAIL[/bold red] (Team {team_abbr}: Expected {expected_status}, Got {actual_status})")
            all_passed = False

    if all_passed:
        rprint("[bold white on green]ALL 4 TESTS PASSED[/bold white on green]")
    else:
        rprint("[bold white on red]ONE OR MORE TESTS FAILED[/bold white on red]")

    rprint("[bold yellow]---------------------------------[/bold yellow]")


if __name__ == "__main__":
    # Load variables from a local .env file (if present)
    load_dotenv()

    # Retrieve the API Key from the environment
    BALLDONTLIE_API_KEY = os.getenv(API_KEY_ENV_VAR)

    if not BALLDONTLIE_API_KEY:
        rprint(f"[bold red]FATAL ERROR: API Key Missing![/bold red]")
        rprint(f"The environment variable [bold yellow]{API_KEY_ENV_VAR}[/bold yellow] must be set.")
        rprint("Please create a `.env` file in the same directory with the content:")
        rprint(f"[dim]{API_KEY_ENV_VAR}=your-actual-api-key[/dim]")
        sys.exit(1)

    # Run the Typer application
    app()

    # test_fatigue_logic()