import os
import requests
from supabase import create_client, Client

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_and_store_tuesday_lines(week_num, season=2026):
    """Fetches lines from The Odds API and locks them into Supabase for the week."""
    url = f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/?apiKey={ODDS_API_KEY}&regions=us&markets=spreads"
    response = requests.get(url).json()

    for item in response:
        game_id = item['id']
        home_team = item['home_team']
        away_team = item['away_team']
        kickoff_time = item['commence_time']

        # Get point spread for home team
        home_spread = 0.0
        try:
            bookmaker = item['bookmakers'][0]
            market = next(m for m in bookmaker['markets'] if m['key'] == 'spreads')
            outcome = next(o for o in market['outcomes'] if o['name'] == home_team)
            home_spread = float(outcome['point'])
        except Exception:
            pass

        # Save or update game in Supabase
        game_data = {
            "id": game_id,
            "season": season,
            "week": week_num,
            "home_team": home_team,
            "away_team": away_team,
            "kickoff_time": kickoff_time,
            "tuesday_spread": home_spread,
            "status": "scheduled"
        }
        supabase.table("games").upsert(game_data).execute()
    print("Tuesday spreads successfully updated and locked.")

def update_live_scores():
    """Polls ESPN public API for live scores and updates Supabase."""
    espn_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    res = requests.get(espn_url).json()

    for event in res.get('events', []):
        status_type = event['status']['type']['state'] # 'pre', 'in', 'post'
        status_text = event['status']['type']['shortDetail']
        
        competition = event['competitions'][0]
        home_comp = next(c for c in competition['competitors'] if c['homeAway'] == 'home')
        away_comp = next(c for c in competition['competitors'] if c['homeAway'] == 'away')

        home_team = home_comp['team']['displayName']
        home_score = int(home_comp.get('score', 0))
        away_score = int(away_comp.get('score', 0))

        db_status = 'scheduled'
        if status_type == 'in':
            db_status = f"Live: {status_text}"
        elif status_type == 'post':
            db_status = 'Final'

        # Match game by team names in database
        response = supabase.table("games").select("id").eq("home_team", home_team).execute()
        if response.data:
            game_id = response.data[0]['id']
            supabase.table("games").update({
                "home_score": home_score,
                "away_score": away_score,
                "status": db_status
            }).eq("id", game_id).execute()

if __name__ == "__main__":
    update_live_scores()
