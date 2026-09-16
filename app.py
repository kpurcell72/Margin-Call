import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from supabase import create_client
from fetch_nfl import fetch_and_store_tuesday_lines

# Page Setup
st.set_page_config(page_title="Margin Call NFL", layout="wide")
st.title("🏈 Margin Call NFL Contest")

# Connect to Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Define Eastern Time Zone
EASTERN_TZ = ZoneInfo("America/New_York")

# Query Supabase for the latest week loaded in the database
def get_latest_synced_week():
    try:
        resp = supabase.table("games").select("week").order("week", desc=True).limit(1).execute()
        if resp.data:
            return int(resp.data[0]["week"])
    except Exception:
        pass
    return 1

# Initialize active week dynamically from Supabase
latest_week = get_latest_synced_week()
if "active_week" not in st.session_state:
    st.session_state.active_week = latest_week

# Password-Protected Admin Sync Controls in Sidebar
with st.sidebar:
    st.header("⚙️ Admin Controls")
    admin_key = st.text_input("Enter Admin Password:", type="password", key="admin_pwd_input")
    
    if admin_key == st.secrets.get("ADMIN_PASSWORD", ""):
        st.success("Admin Access Granted")
        sync_week = st.number_input(
            "Select Week to Fetch:", 
            min_value=1, 
            max_value=18, 
            value=st.session_state.active_week,
            key="sidebar_sync_week_input"
        )
        if st.button("🔄 Fetch & Sync Spreads", key="sidebar_sync_btn"):
            with st.spinner(f"Fetching Week {sync_week} spreads..."):
                try:
                    fetch_and_store_tuesday_lines(week_num=int(sync_week))
                    st.session_state.active_week = int(sync_week)
                    st.success(f"Week {sync_week} games & spreads loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error syncing games: {e}")
    elif admin_key:
        st.error("Incorrect Password")
    else:
        st.info("Enter admin password to unlock fetch controls.")

# Navigation Tabs
tab1, tab2 = st.tabs(["📌 Make Picks", "🏆 Live Leaderboard"])

with tab1:
    st.header("Weekly Picks Selection")
    user_name = st.text_input("Enter Your Name / Identifier:", key="user_name_input").strip()
    
    week = st.number_input(
        "Select Contest Week:", 
        min_value=1, 
        max_value=18, 
        value=latest_week,
        key="main_contest_week_input"
    )

    # Fetch existing picks for this user & week if user_name is entered
    user_existing_picks = {}
    if user_name:
        existing_resp = (
            supabase.table("picks")
            .select("*")
            .eq("user_name", user_name)
            .eq("week", week)
            .execute()
        )
        if existing_resp.data:
            user_existing_picks = {p["game_id"]: p["picked_team"] for p in existing_resp.data}
            st.info(f"Loaded existing picks for **{user_name}** (Week {week}). You can update unlocked picks below.")

    # Fetch Games from Database sorted chronologically
    games_resp = (
        supabase.table("games")
        .select("*")
        .eq("week", week)
        .order("kickoff_time", desc=False)
        .execute()
    )
    games = games_resp.data

    if not games:
        st.info(f"No games loaded yet for Week {week}. Use the Admin Controls in the sidebar to sync games.")
    else:
        st.subheader("Pick 5 Games (Each game locks at kickoff)")
        selected_picks = {}
        now_utc = datetime.now(timezone.utc)

        for game in games:
            # Parse kickoff time and convert to Eastern Time
            kickoff_utc = datetime.fromisoformat(game['kickoff_time'].replace('Z', '+00:00'))
            kickoff_et = kickoff_utc.astimezone(EASTERN_TZ)
            is_locked = now_utc >= kickoff_utc
            
            h_spread = game['tuesday_spread']
            a_spread = -h_spread
            
            h_label = f"{game['home_team']} ({'+' if h_spread > 0 else ''}{h_spread})"
            a_label = f"{game['away_team']} ({'+' if a_spread > 0 else ''}{a_spread})"
            
            # Format time in Eastern Time
            time_str = kickoff_et.strftime('%a %I:%M %p %Z')
            st.write(f"**{game['away_team']} @ {game['home_team']}** | Kickoff: {time_str}")
            
            saved_pick = user_existing_picks.get(game['id'])

            if is_locked:
                if saved_pick:
                    st.warning(f"🔒 Locked (Game Started) — **Your Pick: {saved_pick}**")
                    selected_picks[game['id']] = saved_pick
                else:
                    st.warning("🔒 Locked (Game Started — No Pick Submitted)")
            else:
                default_idx = 0
                if saved_pick == game['away_team']:
                    default_idx = 1
                elif saved_pick == game['home_team']:
                    default_idx = 2

                choice = st.radio(
                    f"Select pick for {game['away_team']} @ {game['home_team']}:",
                    ["None", a_label, h_label],
                    index=default_idx,
                    key=f"pick_game_{game['id']}_{user_name}"
                )
                if choice != "None":
                    picked_team = game['home_team'] if choice == h_label else game['away_team']
                    selected_picks[game['id']] = picked_team
            st.divider()

        if st.button("Submit / Update Picks", key="submit_picks_btn"):
            if not user_name:
                st.error("Please enter your name / identifier before submitting.")
            elif len(selected_picks) != 5:
                st.error(f"You must select exactly 5 picks. You currently have {len(selected_picks)} selected.")
            else:
                for game_id, team in selected_picks.items():
                    supabase.table("picks").upsert({
                        "user_name": user_name,
                        "week": week,
                        "game_id": game_id,
                        "picked_team": team
                    }).execute()
                st.success("Your picks have been successfully updated!")
                st.rerun()

with tab2:
    st.header("Live Scoreboard & Standings")

    picks_resp = supabase.table("picks").select("*").execute()
    games_df = pd.DataFrame(supabase.table("games").select("*").execute().data)

    if picks_resp.data and not games_df.empty:
        picks_df = pd.DataFrame(picks_resp.data)
        detailed_scores = []

        for _, row in picks_df.iterrows():
            game_match = games_df[games_df['id'] == row['game_id']]
            if not game_match.empty:
                game = game_match.iloc[0]
                picked = row['picked_team']
                
                home_score = game.get('home_score') or 0
                away_score = game.get('away_score') or 0
                
                if picked == game['home_team']:
                    picked_score = home_score
                    opp_score = away_score
                    spread = game['tuesday_spread']
                else:
                    picked_score = away_score
                    opp_score = home_score
                    spread = -game['tuesday_spread']
                
                status = str(game.get('status', '')).lower()
                has_started = status in ['in_progress', 'completed', 'closed', 'final', 'live'] or (home_score > 0 or away_score > 0)
                
                pts = (picked_score - opp_score) + spread if has_started else 0.0
                
                detailed_scores.append({
                    "User": row['user_name'],
                    "Week": row['week'],
                    "Picked": picked,
                    "Status": status.capitalize() if status else "Scheduled",
                    "Margin Pts": float(pts),
                    "Has Started": has_started
                })
            
        if detailed_scores:
            score_df = pd.DataFrame(detailed_scores)
            
            user_summary = []
            for user, group in score_df.groupby("User"):
                started_picks = group[group["Has Started"]]
                total_margin = float(started_picks["Margin Pts"].sum()) if not started_picks.empty else 0.0
                
                user_summary.append({
                    "User": user,
                    "Total Margin Points": total_margin
                })
            
            leaderboard = pd.DataFrame(user_summary)
            leaderboard = leaderboard.sort_values(by="Total Margin Points", ascending=False).reset_index(drop=True)
            
            leaderboard.index = leaderboard.index + 1
            leaderboard = leaderboard.reset_index().rename(columns={"index": "Rank"})

            st.subheader("🏆 Leaderboard")
            st.dataframe(
                leaderboard[["Rank", "User", "Total Margin Points"]],
                column_config={
                    "Total Margin Points": st.column_config.NumberColumn(
                        "Total Margin Points",
                        format="%+.1f",
                        help="Sum of margin points won/lost across selected games."
                    )
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.subheader("📋 Pick Breakdown")
            display_breakdown = score_df[["User", "Week", "Picked", "Status", "Margin Pts"]].copy()
            st.dataframe(
                display_breakdown,
                column_config={
                    "Margin Pts": st.column_config.NumberColumn(
                        "Margin Pts",
                        format="%+.1f"
                    )
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No matching game records found for picks.")
    else:
        st.info("No picks or game scores to display yet.")
