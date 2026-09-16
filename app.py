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

# NFL Team Logo Mapping (ESPN CDN)
TEAM_LOGOS = {
    "Arizona Cardinals": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png",
    "Atlanta Falcons": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png",
    "Baltimore Ravens": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png",
    "Buffalo Bills": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
    "Carolina Panthers": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png",
    "Chicago Bears": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png",
    "Cincinnati Bengals": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png",
    "Cleveland Browns": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png",
    "Dallas Cowboys": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
    "Denver Broncos": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png",
    "Detroit Lions": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png",
    "Green Bay Packers": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png",
    "Houston Texans": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png",
    "Indianapolis Colts": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png",
    "Jacksonville Jaguars": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png",
    "Kansas City Chiefs": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
    "Las Vegas Raiders": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png",
    "Los Angeles Chargers": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png",
    "Los Angeles Rams": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png",
    "Miami Dolphins": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png",
    "Minnesota Vikings": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png",
    "New England Patriots": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png",
    "New Orleans Saints": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png",
    "New York Giants": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png",
    "New York Jets": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png",
    "Philadelphia Eagles": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
    "Pittsburgh Steelers": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png",
    "San Francisco 49ers": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
    "Seattle Seahawks": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png",
    "Tampa Bay Buccaneers": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png",
    "Tennessee Titans": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png",
    "Washington Commanders": "https://a.espncdn.com/i/teamlogos/nfl/500/was.png",
}

def get_team_logo(team_name):
    if team_name in TEAM_LOGOS:
        return TEAM_LOGOS[team_name]
    for key, url in TEAM_LOGOS.items():
        if team_name.lower() in key.lower() or key.lower() in team_name.lower():
            return url
    return "https://a.espncdn.com/i/teamlogos/nfl/500/nfl.png"

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

# Callback handlers for pick selection
def on_pick_away(game_id, away_team):
    if st.session_state.get(f"cb_away_{game_id}"):
        st.session_state[f"pick_{game_id}"] = away_team
        st.session_state[f"cb_home_{game_id}"] = False
    else:
        st.session_state[f"pick_{game_id}"] = None

def on_pick_home(game_id, home_team):
    if st.session_state.get(f"cb_home_{game_id}"):
        st.session_state[f"pick_{game_id}"] = home_team
        st.session_state[f"cb_away_{game_id}"] = False
    else:
        st.session_state[f"pick_{game_id}"] = None

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
    
    c_user, c_week = st.columns([3, 1])
    with c_user:
        user_name = st.text_input("Enter Your Name / Identifier:", key="user_name_input").strip()
    with c_week:
        week = st.number_input(
            "Contest Week:", 
            min_value=1, 
            max_value=18, 
            value=latest_week,
            key="main_contest_week_input"
        )

    # Load existing picks from database when user_name or week changes
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

    # Sync user picks to session state if state key updated
    state_key = f"loaded_{user_name}_{week}"
    if st.session_state.get("current_loaded_key") != state_key:
        st.session_state["current_loaded_key"] = state_key
        games_for_state = (
            supabase.table("games")
            .select("id, away_team, home_team")
            .eq("week", week)
            .execute().data or []
        )
        for g in games_for_state:
            saved = user_existing_picks.get(g['id'])
            st.session_state[f"pick_{g['id']}"] = saved
            st.session_state[f"cb_away_{g['id']}"] = (saved == g['away_team'])
            st.session_state[f"cb_home_{g['id']}"] = (saved == g['home_team'])

    # Fetch Games sorted chronologically
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
        # Calculate selected pick count
        selected_picks = {
            g['id']: st.session_state.get(f"pick_{g['id']}")
            for g in games
            if st.session_state.get(f"pick_{g['id']}")
        }

        st.markdown(f"### Select 5 Games `({len(selected_picks)} / 5 Selected)`")
        now_utc = datetime.now(timezone.utc)

        for game in games:
            # Parse kickoff time
            kickoff_utc = datetime.fromisoformat(game['kickoff_time'].replace('Z', '+00:00'))
            kickoff_et = kickoff_utc.astimezone(EASTERN_TZ)
            is_locked = now_utc >= kickoff_utc
            
            h_spread = game['tuesday_spread']
            a_spread = -h_spread
            
            h_spread_str = f"{'+' if h_spread > 0 else ''}{h_spread}"
            a_spread_str = f"{'+' if a_spread > 0 else ''}{a_spread}"
            time_str = kickoff_et.strftime('%a %I:%M %p ET')

            # Single-line 7-column layout with center vertical alignment
            c1, c2, c3, c4, c5, c6, c7 = st.columns([0.4, 0.5, 2.6, 2.0, 2.6, 0.5, 0.4], vertical_alignment="center")

            # Far-Left: Away Pick Box
            with c1:
                st.checkbox(
                    "",
                    key=f"cb_away_{game['id']}",
                    disabled=is_locked,
                    on_change=on_pick_away,
                    args=(game['id'], game['away_team']),
                    label_visibility="collapsed"
                )

            # Away Logo
            with c2:
                st.image(get_team_logo(game['away_team']), width=28)

            # Away Team Name & Spread
            with c3:
                st.markdown(f"**{game['away_team']}** `{a_spread_str}`")

            # Center: Kickoff Time / Lock Status
            with c4:
                if is_locked:
                    st.caption(f"🔒 **Locked** ({time_str})")
                else:
                    st.caption(f"🕒 {time_str}")

            # Home Spread & Team Name
            with c5:
                st.markdown(f"`{h_spread_str}` **{game['home_team']}**", unsafe_allow_html=True)

            # Home Logo
            with c6:
                st.image(get_team_logo(game['home_team']), width=28)

            # Far-Right: Home Pick Box
            with c7:
                st.checkbox(
                    "",
                    key=f"cb_home_{game['id']}",
                    disabled=is_locked,
                    on_change=on_pick_home,
                    args=(game['id'], game['home_team']),
                    label_visibility="collapsed"
                )

            st.markdown("<hr style='margin: 0px 0 6px 0; border: none; border-top: 1px solid #e6e6e6;'/>", unsafe_allow_html=True)

        if st.button("Submit / Update Picks", key="submit_picks_btn", type="primary"):
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
                st.success("Your picks have been successfully saved!")
                st.rerun()

with tab2:
    st.header("Live Scoreboard & Standings")

    picks_resp = supabase.table("picks").select("*").execute()
    games_df = pd.DataFrame(supabase.table("games").select("*").execute().data)

    if picks_resp.data and not games_df.empty:
        picks_df = pd.DataFrame(picks_resp.data)
        detailed_scores = []
        now_utc = datetime.now(timezone.utc)

        for _, row in picks_df.iterrows():
            game_match = games_df[games_df['id'] == row['game_id']]
            if not game_match.empty:
                game = game_match.iloc[0]
                picked = row['picked_team']
                
                # Check kickoff time vs current time
                kickoff_utc = datetime.fromisoformat(game['kickoff_time'].replace('Z', '+00:00'))
                status = str(game.get('status', '')).lower()
                has_started = now_utc >= kickoff_utc or status in ['in_progress', 'completed', 'closed', 'final', 'live']
                
                # Mask pick if game has not kicked off yet
                display_pick = picked if has_started else "🔒 Hidden until Kickoff"

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
                
                pts = (picked_score - opp_score) + spread if has_started else 0.0
                
                detailed_scores.append({
                    "User": row['user_name'],
                    "Week": row['week'],
                    "Picked": display_pick,
                    "Status": "Live / Final" if has_started else "Scheduled",
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
                        help="Sum of margin points won/lost across selected games that have kicked off."
                    )
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.subheader("📋 Pick Breakdown")
            
            # Filter breakdown by week
            available_weeks = sorted(score_df["Week"].unique())
            filter_week = st.selectbox("Filter Breakdown by Week:", ["All Weeks"] + list(available_weeks), key="lb_week_filter")
            
            if filter_week != "All Weeks":
                display_breakdown = score_df[score_df["Week"] == filter_week][["User", "Week", "Picked", "Status", "Margin Pts"]].copy()
            else:
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
