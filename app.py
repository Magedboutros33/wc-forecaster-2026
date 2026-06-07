import streamlit as st
import requests
import re
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
from itertools import groupby
import pytz

# --- CONFIGURATION & INITIALIZATION ---
st.set_page_config(page_title="WC 2026 Forecast", layout="wide", page_icon="⚽")

# --- INITIALIZE SUPABASE ---
@st.cache_resource
def init_connection():
    raw_url = st.secrets["SUPABASE_URL"].strip()
    clean_url = raw_url.split("/rest/v1")[0].rstrip('/')
    raw_key = st.secrets["SUPABASE_KEY"]
    clean_key = "".join(re.findall(r'[A-Za-z0-9._\-]', raw_key))
    return create_client(clean_url, clean_key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Failed to connect to database. Check your secrets configuration.")

# --- SESSION STATES ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_id' not in st.session_state: st.session_state['user_id'] = None
if 'user_name' not in st.session_state: st.session_state['user_name'] = ""

# --- FORCE LIGHT MODE & CUSTOM CSS ---
def inject_light_mode_css():
    st.markdown("""
    <style>
        .stApp { background-color: #FFFFFF !important; color: #1E1E1E !important; }
        h1, h2, h3, h4, h5, p, label, span { color: #1E1E1E !important; }
        
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, input {
            background-color: #F8F9FA !important; color: #1E1E1E !important; border: 1px solid #CCCCCC !important;
        }
        
        button[kind="primary"] { background-color: #28a745 !important; border-color: #28a745 !important; color: white !important; font-weight: bold; }
        button[kind="secondary"] { background-color: #fd7e14 !important; border-color: #fd7e14 !important; color: white !important; font-weight: bold; }
        
        input[type="number"] { text-align: center !important; font-size: 1.2rem !important; padding: 5px !important; }
        
        [data-testid="collapsedControl"] { display: none; }
        .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 15px; }
        
        /* Custom spacing for the forecast columns */
        div[data-testid="column"] { align-self: center; }
    </style>
    """, unsafe_allow_html=True)

inject_light_mode_css()

# --- OFFICIAL 2026 WORLD CUP GROUPS & FLAGS ---
GROUPS_DICT = {
    "Group A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "Group B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "Group C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "Group D": ["USA", "Paraguay", "Australia", "Türkiye"],
    "Group E": ["Germany", "Curaçao", "Côte d'Ivoire", "Ecuador"],
    "Group F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "Group G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "Group H": ["Spain", "Cabo Verde", "Saudi Arabia", "Uruguay"],
    "Group I": ["France", "Senegal", "Norway", "Iraq"],
    "Group J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "Group K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "Group L": ["England", "Croatia", "Ghana", "Panama"]
}

FLAG_URLS = {
    "Mexico": "mx", "South Africa": "za", "South Korea": "kr", "Czechia": "cz",
    "Canada": "ca", "Bosnia and Herzegovina": "ba", "Qatar": "qa", "Switzerland": "ch",
    "Brazil": "br", "Morocco": "ma", "Haiti": "ht", "Scotland": "gb-sct",
    "USA": "us", "Paraguay": "py", "Australia": "au", "Türkiye": "tr",
    "Germany": "de", "Curaçao": "cw", "Côte d'Ivoire": "ci", "Ecuador": "ec",
    "Netherlands": "nl", "Japan": "jp", "Sweden": "se", "Tunisia": "tn",
    "Belgium": "be", "Egypt": "eg", "Iran": "ir", "New Zealand": "nz",
    "Spain": "es", "Cabo Verde": "cv", "Saudi Arabia": "sa", "Uruguay": "uy",
    "France": "fr", "Senegal": "sn", "Norway": "no", "Iraq": "iq",
    "Argentina": "ar", "Algeria": "dz", "Austria": "at", "Jordan": "jo",
    "Portugal": "pt", "DR Congo": "cd", "Uzbekistan": "uz", "Colombia": "co",
    "England": "gb-eng", "Croatia": "hr", "Ghana": "gh", "Panama": "pa"
}

def get_flag(team):
    if team in FLAG_URLS: return f"https://flagcdn.com/w40/{FLAG_URLS[team]}.png"
    return "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/White_flag_of_surrender.svg/40px-White_flag_of_surrender.svg.png"

def update_group_callback(grp, pos):
    new_val = st.session_state[f"widget_{grp}_{pos}"]
    st.session_state.groups_state[grp][pos] = new_val
    current = st.session_state.groups_state[grp]
    filled = [t for t in current if t != ""]
    if len(filled) == 3 and new_val != "":
        missing_team = [t for t in GROUPS_DICT[grp] if t not in filled][0]
        empty_idx = current.index("")
        st.session_state.groups_state[grp][empty_idx] = missing_team
        st.session_state[f"widget_{grp}_{empty_idx}"] = missing_team

def clear_group_callback(grp, pos):
    st.session_state.groups_state[grp][pos] = ""
    if f"widget_{grp}_{pos}" in st.session_state:
        st.session_state[f"widget_{grp}_{pos}"] = ""

@st.cache_data(ttl=600) 
def get_matches_from_api():
    url = "https://api.football-data.org/v4/competitions/WC/matches"
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_DATA_KEY"]}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('matches', [])
        return []
    except Exception:
        return []

def calculate_points(actual_h, actual_a, pred_h, pred_a):
    if actual_h is None or actual_a is None: return 0
    if actual_h == pred_h and actual_a == pred_a: return 3
    if (actual_h > actual_a and pred_h > pred_a) or \
       (actual_h < actual_a and pred_h < pred_a) or \
       (actual_h == actual_a and pred_h == pred_a): return 1
    return 0

def save_forecast(match_id, home_goals, away_goals):
    user_id = st.session_state['user_id']
    existing = supabase.table("match_forecasts").select("id").eq("user_id", user_id).eq("match_id", match_id).execute()
    forecast_data = {"user_id": user_id, "match_id": match_id, "home_goals": home_goals, "away_goals": away_goals}
    
    if existing.data:
        supabase.table("match_forecasts").update(forecast_data).eq("id", existing.data[0]['id']).execute()
        st.toast("Forecast updated! ⚽")
    else:
        supabase.table("match_forecasts").insert(forecast_data).execute()
        st.toast("Forecast saved! ⚽")
        
    st.session_state[f"cache_h_{match_id}"] = home_goals
    st.session_state[f"cache_a_{match_id}"] = away_goals

def auth_page():
    st.write("")
    st.markdown("<h1 style='text-align: center;'>🏆 WC 2026 Forecaster</h1>", unsafe_allow_html=True)
    st.write("") 
    _, col, _ = st.columns([1, 2, 1])
    with col:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", type="primary", use_container_width=True):
                try:
                    response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = response.user.id
                    profile = supabase.table("profiles").select("name").eq("id", response.user.id).execute()
                    if profile.data: st.session_state['user_name'] = profile.data[0]['name']
                    else: st.session_state['user_name'] = "Player"
                    st.rerun()
                except Exception:
                    st.error("Login failed: Invalid email or password.")
        with tab2:
            reg_name = st.text_input("Full Name")
            reg_phone = st.text_input("Phone Number")
            reg_email = st.text_input("Email")
            reg_password = st.text_input("Password", type="password")
            if st.button("Create Account", type="primary", use_container_width=True):
                if not reg_name or not reg_email or not reg_password:
                    st.error("Please fill out all required fields.")
                else:
                    try:
                        auth_response = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                        supabase.table("profiles").insert({"id": auth_response.user.id, "name": reg_name, "email": reg_email, "phone_number": reg_phone}).execute()
                        st.success("Account created! You can now log in.")
                    except Exception as e:
                        st.error(f"Error creating account: {e}")

# --- NEW FULLY REDESIGNED MATCH RENDERER ---
def render_match(match, user_forecasts, prefix=""):
    m_id = match['id']
    status = match['status']
    home_team = match['homeTeam']['name']
    away_team = match['awayTeam']['name']
    
    home_flag = get_flag(home_team)
    away_flag = get_flag(away_team)
    
    actual_home = match['score']['fullTime'].get('home')
    actual_away = match['score']['fullTime'].get('away')

    # Convert UTC to Egypt Time (EEST)
    try:
        utc_dt = datetime.strptime(match['utcDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC)
        egypt_dt = utc_dt.astimezone(pytz.timezone('Africa/Cairo'))
        time_str = egypt_dt.strftime("%I:%M %p")
    except:
        time_str = "TBD"

    has_forecast = m_id in user_forecasts
    edit_key = f"{prefix}edit_{m_id}"
    if edit_key not in st.session_state: st.session_state[edit_key] = not has_forecast

    # Dynamic Font Sizing for long country names
    home_font = "0.95rem" if len(home_team) > 12 else "1.2rem"
    away_font = "0.95rem" if len(away_team) > 12 else "1.2rem"

    with st.container(border=True):
        # 1. MATCH TIME & STATUS
        st.markdown(f"<div style='text-align: center; color: #777; font-size: 0.85rem; font-weight: bold; margin-bottom: 12px;'>🕒 {time_str} (Egypt Time) &nbsp;•&nbsp; {status}</div>", unsafe_allow_html=True)

        # 2. TEAMS AND FLAGS (Name on top, Flag below)
        st.markdown(f"""
        <div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;'>
            <div style='flex: 1; text-align: center; display: flex; flex-direction: column; align-items: center;'>
                <div style='height: 35px; display: flex; align-items: center; justify-content: center;'>
                    <h4 style='margin: 0; font-size: {home_font}; text-align: center; line-height: 1.1;'>{home_team}</h4>
                </div>
                <img src='{home_flag}' width='50' style='border-radius: 4px; margin-top: 5px; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
            </div>
            <div style='flex: 0.4; text-align: center; align-self: center; margin-top: 15px;'>
                <span style='font-size: 1.2rem; font-weight: bold; color: #aaa;'>vs</span>
            </div>
            <div style='flex: 1; text-align: center; display: flex; flex-direction: column; align-items: center;'>
                <div style='height: 35px; display: flex; align-items: center; justify-content: center;'>
                    <h4 style='margin: 0; font-size: {away_font}; text-align: center; line-height: 1.1;'>{away_team}</h4>
                </div>
                <img src='{away_flag}' width='50' style='border-radius: 4px; margin-top: 5px; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr style='margin: 15px 0 10px 0; border: 0; border-top: 1px dashed #eee;'>", unsafe_allow_html=True)

        # 3. ACTUAL RESULTS (Side-by-side boxes)
        st.markdown("<div style='text-align: center; font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;'>Actual Result</div>", unsafe_allow_html=True)
        if actual_home is not None and actual_away is not None:
            st.markdown(f"""
            <div style='display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 15px;'>
                <div style='background-color: #f1f3f5; padding: 5px 20px; border-radius: 6px; font-size: 1.4rem; font-weight: bold; border: 1px solid #ddd;'>{actual_home}</div>
                <span style='color: #888; font-weight: bold;'>-</span>
                <div style='background-color: #f1f3f5; padding: 5px 20px; border-radius: 6px; font-size: 1.4rem; font-weight: bold; border: 1px solid #ddd;'>{actual_away}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style='display: flex; justify-content: center; align-items: center; gap: 15px; margin-bottom: 15px;'>
                <div style='background-color: #f8f9fa; color: #ccc; padding: 5px 20px; border-radius: 6px; font-size: 1.4rem; font-weight: bold; border: 1px solid #eee;'>-</div>
                <span style='color: #ccc; font-weight: bold;'>-</span>
                <div style='background-color: #f8f9fa; color: #ccc; padding: 5px 20px; border-radius: 6px; font-size: 1.4rem; font-weight: bold; border: 1px solid #eee;'>-</div>
            </div>
            """, unsafe_allow_html=True)

        # 4. FORECAST SECTION
        st.markdown("<div style='text-align: center; font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;'>Your Forecast</div>", unsafe_allow_html=True)
        
        db_home = user_forecasts.get(m_id, {}).get('home_goals', 0)
        db_away = user_forecasts.get(m_id, {}).get('away_goals', 0)
        saved_home = st.session_state.get(f"cache_h_{m_id}", db_home)
        saved_away = st.session_state.get(f"cache_a_{m_id}", db_away)
        
        is_locked = not st.session_state[edit_key]
        
        # Center the inputs using spacer columns
        fc_space1, fc_h, fc_dash, fc_a, fc_btn, fc_space2 = st.columns([1, 1.2, 0.2, 1.2, 2, 1])
        
        if is_locked:
            locked_style = "background-color: #E9ECEF; color: #555; border: 1px solid #CCC; border-radius: 6px; text-align: center; font-size: 1.2rem; padding: 4px; height: 38px; line-height: 28px; font-weight: bold;"
            fc_h.markdown(f"<div style='{locked_style}'>{saved_home}</div>", unsafe_allow_html=True)
            fc_dash.markdown("<div style='text-align: center; margin-top: 5px; font-weight: bold; color: #888;'>-</div>", unsafe_allow_html=True)
            fc_a.markdown(f"<div style='{locked_style}'>{saved_away}</div>", unsafe_allow_html=True)
            
            with fc_btn:
                # Disable changing if the match has already started/finished
                if status in ["TIMED", "SCHEDULED"]:
                    if st.button("Change", key=f"{prefix}btn_change_{m_id}", use_container_width=True, type="secondary"):
                        st.session_state[edit_key] = True
                        st.rerun()
                else:
                    st.markdown("<div style='text-align: center; padding-top: 8px; color: #dc3545; font-size: 0.85rem; font-weight: bold;'>Locked</div>", unsafe_allow_html=True)
        else:
            if status in ["TIMED", "SCHEDULED"]:
                pred_h = fc_h.number_input("H", min_value=0, value=int(saved_home), key=f"{prefix}h_{m_id}", label_visibility="collapsed")
                fc_dash.markdown("<div style='text-align: center; margin-top: 5px; font-weight: bold; color: #888;'>-</div>", unsafe_allow_html=True)
                pred_a = fc_a.number_input("A", min_value=0, value=int(saved_away), key=f"{prefix}a_{m_id}", label_visibility="collapsed")
                
                with fc_btn:
                    if st.button("Save", key=f"{prefix}btn_save_{m_id}", use_container_width=True, type="primary"):
                        save_forecast(m_id, pred_h, pred_a)
                        st.session_state[f"cache_h_{m_id}"] = pred_h
                        st.session_state[f"cache_a_{m_id}"] = pred_a
                        st.session_state[edit_key] = False
                        st.rerun()
            else:
                fc_h.markdown(f"<div style='background-color: #fff; border: 1px solid #eee; border-radius: 6px; text-align: center; padding: 4px;'>-</div>", unsafe_allow_html=True)
                fc_dash.markdown("<div style='text-align: center; margin-top: 5px; font-weight: bold; color: #888;'>-</div>", unsafe_allow_html=True)
                fc_a.markdown(f"<div style='background-color: #fff; border: 1px solid #eee; border-radius: 6px; text-align: center; padding: 4px;'>-</div>", unsafe_allow_html=True)
                fc_btn.markdown("<div style='text-align: center; padding-top: 8px; color: #dc3545; font-size: 0.85rem; font-weight: bold;'>Locked</div>", unsafe_allow_html=True)

        # 5. REWARD SECTION
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        if status in ['FINISHED', 'AWARDED']:
            if has_forecast:
                pts = calculate_points(actual_home, actual_away, saved_home, saved_away)
                bg_color = "#d4edda" if pts == 3 else ("#fff3cd" if pts == 1 else "#f8d7da")
                text_color = "#155724" if pts == 3 else ("#856404" if pts == 1 else "#721c24")
                border_color = "#c3e6cb" if pts == 3 else ("#ffeeba" if pts == 1 else "#f5c6cb")
                
                st.markdown(f"""
                <div style='background-color: {bg_color}; color: {text_color}; border: 1px solid {border_color}; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; font-size: 0.9rem;'>
                    Reward: {pts} Point{'s' if pts != 1 else ''}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style='background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; font-size: 0.9rem;'>
                    Reward: 0 Points (Missed Forecast)
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='background-color: #f8f9fa; color: #aaa; border: 1px dashed #ddd; padding: 8px; border-radius: 6px; text-align: center; font-weight: bold; font-size: 0.9rem;'>
                Reward: Pending
            </div>
            """, unsafe_allow_html=True)

# --- MAIN APP ---
def main_app():
    c1, c2 = st.columns([8, 1])
    with c2:
        if st.button("🚪 Logout"):
            try: supabase.auth.sign_out()
            except: pass
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

    st.title("⚽ World Cup 2026 Forecast Challenge")
    st.write(f"Logged in as: **{st.session_state['user_name']}**")
    
    matches = get_matches_from_api()

    try:
        forecasts_res = supabase.table("match_forecasts").select("match_id, home_goals, away_goals").eq("user_id", st.session_state['user_id']).execute()
        user_forecasts = {f['match_id']: f for f in forecasts_res.data}
    except Exception:
        user_forecasts = {}

    tab1, tab2, tab3 = st.tabs(["📅 Matches", "🏆 Leaderboard", "🔮 Extra Forecasts"])
    
    with tab1:
        st.write("")
        if not matches:
            st.warning("No matches available from the API at the moment.")
        else:
            for m in matches:
                try:
                    m['parsed_date'] = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ")
                except:
                    m['parsed_date'] = datetime.now()
            
            matches.sort(key=lambda x: x['parsed_date'])
            
            upcoming_matches = [m for m in matches if m['status'] in ['SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED']]
            historical_matches = [m for m in matches if m['status'] in ['FINISHED', 'AWARDED']]
            
            sub1, sub2, sub3 = st.tabs(["🔜 Upcoming", "⏪ Historical", "📋 All Matches"])
            
            def render_match_group(match_list, prefix):
                if not match_list:
                    st.info("No matches found in this category.")
                    return
                grouped = groupby(match_list, key=lambda x: x['parsed_date'].strftime("%A, %B %d, %Y"))
                for date_str, group in grouped:
                    st.markdown(f"<h4 style='background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-top: 25px;'>📅 {date_str}</h4>", unsafe_allow_html=True)
                    for match in group:
                        render_match(match, user_forecasts, prefix)

            with sub1: render_match_group(upcoming_matches, prefix="up_")
            with sub2: render_match_group(historical_matches, prefix="hist_")
            with sub3: render_match_group(matches, prefix="all_")

    with tab2:
        st.write("")
        st.markdown("<h3 style='text-align: center;'>🏆 Standings</h3>", unsafe_allow_html=True)
        
        users_res = supabase.table("profiles").select("id, name").execute()
        all_forecasts_res = supabase.table("match_forecasts").select("*").execute()
        
        if users_res.data:
            leaderboard_data = {u['id']: {"Player": u['name'], "Exact Scores (3pt)": 0, "Correct Outcomes (1pt)": 0, "Total Points": 0} for u in users_res.data}
            
            api_results = {}
            for m in matches:
                if m['status'] in ['FINISHED', 'AWARDED']:
                    api_results[m['id']] = {"h": m['score']['fullTime'].get('home'), "a": m['score']['fullTime'].get('away')}

            for forecast in (all_forecasts_res.data or []):
                u_id = forecast['user_id']
                m_id = forecast['match_id']
                
                if m_id in api_results and api_results[m_id]['h'] is not None:
                    act_h, act_a = api_results[m_id]['h'], api_results[m_id]['a']
                    pred_h, pred_a = forecast['home_goals'], forecast['away_goals']
                    
                    if u_id in leaderboard_data:
                        if act_h == pred_h and act_a == pred_a:
                            leaderboard_data[u_id]["Exact Scores (3pt)"] += 1
                            leaderboard_data[u_id]["Total Points"] += 3
                        elif (act_h > act_a and pred_h > pred_a) or (act_h < act_a and pred_h < pred_a) or (act_h == act_a and pred_h == pred_a):
                            leaderboard_data[u_id]["Correct Outcomes (1pt)"] += 1
                            leaderboard_data[u_id]["Total Points"] += 1

            df = pd.DataFrame(leaderboard_data.values()).sort_values(by=["Total Points", "Exact Scores (3pt)"], ascending=False).reset_index(drop=True)
            df.index += 1
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No registered players yet.")
            
    with tab3:
        st.write("")
        st.markdown("<h3 style='text-align: center;'>🔮 Tournament Predictions</h3>", unsafe_allow_html=True)
        st.write("")
        
        extra_res = supabase.table("extra_forecasts").select("*").eq("user_id", st.session_state['user_id']).execute()
        existing_extra = extra_res.data[0] if extra_res.data else None
        
        if 'groups_state' not in st.session_state:
            st.session_state.groups_state = {}
            saved_groups = existing_extra.get('groups_sort', {}) if existing_extra else {}
            for grp in GROUPS_DICT.keys():
                st.session_state.groups_state[grp] = saved_groups.get(grp, ["", "", "", ""])
                
        all_48_teams = []
        for teams in GROUPS_DICT.values(): all_48_teams.extend(teams)
        unique_teams = sorted(all_48_teams)

        def get_dd_index(options_list, saved_val):
            return options_list.index(saved_val) if saved_val in options_list else 0

        def_winner = existing_extra.get('cup_winner', '') if existing_extra else ''
        def_scorer = existing_extra.get('top_scorer', '') if existing_extra else ''
        def_most_goals = existing_extra.get('most_goals_team', '') if existing_extra else ''
        
        st.subheader("🏆 The Big Three")
        c1, c2, c3 = st.columns(3)
        with c1:
            fA, fB = st.columns([1, 4])
            with fB: cup_winner = st.selectbox("Tournament Winner", options=[""] + unique_teams, index=get_dd_index([""] + unique_teams, def_winner))
            with fA:
                if cup_winner: st.markdown(f"<img src='{get_flag(cup_winner)}' width='35' style='margin-top: 32px; border-radius: 4px;'>", unsafe_allow_html=True)
        with c2:
            top_scorer = st.text_input("Golden Boot", value=def_scorer, placeholder="e.g., Kylian Mbappé")
        with c3:
            fC, fD = st.columns([1, 4])
            with fD: most_goals = st.selectbox("Most Goals (Team)", options=[""] + unique_teams, index=get_dd_index([""] + unique_teams, def_most_goals))
            with fC:
                if most_goals: st.markdown(f"<img src='{get_flag(most_goals)}' width='35' style='margin-top: 32px; border-radius: 4px;'>", unsafe_allow_html=True)

        st.divider()
        st.subheader("📊 Group Stage Rankings")

        g_cols = st.columns(4)
        for idx, (grp_name, grp_teams) in enumerate(GROUPS_DICT.items()):
            with g_cols[idx % 4]:
                with st.container(border=True):
                    st.markdown(f"<h5 style='text-align: center; color: #1E88E5;'>{grp_name}</h5>", unsafe_allow_html=True)
                    
                    positions = ["1st", "2nd", "3rd", "4th"]
                    for i, pos in enumerate(positions):
                        current_val = st.session_state.groups_state[grp_name][i]
                        other_vals = [st.session_state.groups_state[grp_name][j] for j in range(4) if j != i]
                        avail_teams = [t for t in grp_teams if t not in other_vals]
                        options = [""] + avail_teams
                        if current_val and current_val not in options: options.append(current_val)
                            
                        col_flag, col_drop, col_clear = st.columns([1.5, 5, 1.5])
                        with col_flag:
                            if current_val: st.markdown(f"<img src='{get_flag(current_val)}' width='25' style='margin-top: 32px; border-radius: 2px;'>", unsafe_allow_html=True)
                            else: st.markdown(f"<div style='margin-top: 32px; width: 25px; height: 18px; background-color: #E0E0E0; border-radius: 2px;'></div>", unsafe_allow_html=True)
                            
                        with col_drop:
                            val = st.selectbox(
                                pos, 
                                options=options, 
                                index=options.index(current_val) if current_val in options else 0, 
                                key=f"widget_{grp_name}_{i}",
                                on_change=update_group_callback,
                                args=(grp_name, i)
                            )
                            
                        with col_clear:
                            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                            st.button("✖", key=f"clear_{grp_name}_{i}", on_click=clear_group_callback, args=(grp_name, i), use_container_width=True)

        st.write("")
        if st.button("Save All Extra Forecasts", type="primary", use_container_width=True):
            payload = {
                "user_id": st.session_state['user_id'],
                "cup_winner": cup_winner,
                "top_scorer": top_scorer,
                "most_goals_team": most_goals,
                "groups_sort": st.session_state.groups_state 
            }
            if existing_extra: supabase.table("extra_forecasts").update(payload).eq("id", existing_extra['id']).execute()
            else: supabase.table("extra_forecasts").insert(payload).execute()
            st.success("All predictions and group sortings locked in! 🔒")

# --- APP ROUTING ---
if not st.session_state.get('logged_in', False):
    auth_page()
else:
    main_app()
