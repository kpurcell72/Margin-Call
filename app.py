import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import os
from supabase import create_client, Client
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

# Admin Sync Controls in Sidebar
with st.sidebar:
    st.header("⚙️ Admin Controls")
    sync_week = st.number_input("Select Week to Fetch:", min_value=1, max_value=18, value=1)
    if st.button("🔄 Fetch & Sync Spreads"):
        with st.spinner(f"Fetching Week {sync_week} spreads..."):
            try:
                fetch_and_store_tuesday_lines(week_num=int(sync_week))
                st.success(f"Week {sync_week} games & spreads loaded!")
                st.rerun()
            except Exception as e:
                st.error(f"Error syncing games: {e}")

# Navigation Tabs
tab1, tab2 = st.tabs(["📌 Make Picks", "🏆 Live Leaderboard"])

with tab1:
    st.header("Weekly Picks Selection")
    user_name = st.text_input("Enter Your Name / Identifier:")
    week = st.number_input("Select Contest Week:", min_value=1, max_value=18, value=1)

    # Fetch Games from Database
    games_resp = supabase.table("games").select("*").eq("week", week).execute()
    games = games_resp.data

    if not games:
        st.info("No games loaded yet for this week. Use the Admin Controls in the sidebar to sync games.")
    else:
        st.subheader("Pick 5 Games (Each game locks at kickoff)")
        selected_picks = {}
        now_utc = datetime.now(timezone.utc)

        for game in games:
            kickoff = datetime.fromisoformat(game['kickoff_time'].replace('Z', '+00:00'))
            is_locked = now_utc >= kickoff
            
            h_spread = game['tuesday_spread']
            a_spread = -h_spread
            
            h_label = f"{game['home_team']} ({'+' if h_spread > 0 else ''}{h_spread})"
            a_label = f"{game['away_team']} ({'+' if a_spread > 0 else ''}{a_spread})"
            
            st.write(f"**{game['away_team']} @ {game['home_team']}** | Kickoff: {kickoff.strftime('%a %I:%M %p UTC')}")
            
            if is_locked:
                st.warning("🔒 Locked (Game Started)")
            else:
                choice = st.radio(
                    f"Select pick for {game['away_team']} @ {game['home_team']}:",
                    ["None", a_label, h_label],
                    key=game['id']
                )
                if choice != "None":
                    picked_team = game['home_team'] if choice == h_label else game['away_team']
                    selected_picks[game['id']] = picked_team
            st.divider()

        if st.button("Submit Picks"):
            if not user_name:
                st.error("Please enter your name.")
            elif len(selected_picks) != 5:
                st.error(f"You must select exactly 5 picks. You currently selected {len(selected_picks)}.")
            else:
                for game_id, team in selected_picks.items():
                    supabase.table("picks").upsert({
                        "user_name": user_name,
                        "week": week,
                        "game_id": game_id,
                        "picked_team": team
                    }).execute()
                st.success("Your picks have been successfully submitted!")

with tab2:
    st.header("Live Scoreboard & Standings")

    # Load Picks & Games
    picks_resp = supabase.table("picks").select("*").execute()
    games_df = pd.DataFrame(supabase.table("games").select("*").execute().data)

    if picks_resp.data and not games_df.empty:
        picks_df = pd.DataFrame(picks_resp.data)
        
        # Calculate Score per Pick
        scores = []
        for _, row in picks_df.iterrows():
            game = games_df[games_df['id'] == row['game_id']].iloc[0]
            picked = row['picked_team']
            
            if picked == game['home_team']:
                picked_score = game['home_score']
                opp_score = game['away_score']
                spread = game['tuesday_spread']
            else:
                picked_score = game['away_score']
                opp_score = game['home_score']
                spread = -game['tuesday_spread']
                
            pts = (picked_score - opp_score) + spread
            scores.append({
                "User": row['user_name'],
                "Week": row['week'],
                "Picked": picked,
                "Status": game['status'],
                "Margin Pts": pts
            })
            
        score_df = pd.DataFrame(scores)
        
        # Leaderboard Summary
        leaderboard = score_df.groupby("User")["Margin Pts"].sum().reset_index()
        leaderboard = leaderboard.sort_values(by="Margin Pts", ascending=False)
        
        st.dataframe(leaderboard, use_container_width=True)
        st.subheader("Detailed Breakdown")
        st.dataframe(score_df, use_container_width=True)
    else:
        st.info("No picks or game scores to display yet.")
