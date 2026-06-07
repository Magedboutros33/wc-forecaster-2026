import streamlit as st
from supabase import create_client, Client
import re
import requests
from datetime import datetime
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="World Cup 2026 Forecaster", page_icon="🏆", layout="wide")

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
    st.error(f"Failed to connect to database. Check your secrets configuration. Error: {e}")

# --- FETCH LIVE API DATA ---
@st.cache_data(ttl=3600)
def get_wc_matches():
    url = "https://v3.football.api-sports.io/fixtures"
    querystring = {"league": "1", "season": "2026"}
    headers = {"x-apisports-key": st.secrets["API_FOOTBALL_KEY"]}
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        data = response.json()
        
        matches = {}
        for match in data.get('response', []):
            raw_date = match['fixture']['date']
            formatted_date = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%B %d, %Y - %H:%M")
            
            m_id = match['fixture']['id']
            matches[m_id] = {
                "id": m_id,
                "date": formatted_date,
                "status": match['fixture']['status']['short'],
                "home_team": match['teams']['home']['name'],
                "away_team": match['teams']['away']['name'],
                "home_logo": match['teams']['home']['logo'],
                "away_logo": match['teams']['away']['logo'],
                "actual_home": match['goals']['home'],
                "actual_away": match['goals']['away']
            }
        return matches
    except Exception as e:
        st.error(f"Failed to fetch match data from API: {e}")
        return {}

# --- INITIALIZE SESSION STATES ---
if 'theme' not in st.session_state:
    st.session_state['theme'] = 'light'
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ""

# --- CUSTOM CSS ---
def inject_custom_css():
    bg_color = "#0E1117" if st.session_state['theme'] == 'dark' else "#FFFFFF"
    text_color = "#FAFAFA" if st.session_state['theme'] == 'dark' else "#31333F"
    
    st.markdown(f"""
    <style>
        [data-testid="collapsedControl"] {{ display: none; }}
        .stApp {{ background-color: {bg_color}; color: {text_color}; }}
        h1, h2, h3, h4, p {{ color: {text_color} !important; }}
        .stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 15px; }}
        .stButton>button {{ width: 100%; border-radius: 8px; font-weight: 600; }}
        input[type="number"] {{ text-align: center; font-size: 1.2rem; }}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- AUTHENTICATION VIEW ---
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
            if st.button("Login", type="primary"):
                try:
                    response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = response.user.id
                    
                    profile = supabase.table("profiles").select("name").eq("id", response.user.id).execute()
                    if profile.data:
                        st.session_state['user_name'] = profile.data[0]['name']
                    else:
                        st.session_state['user_name'] = "Player"
                        
                    st.rerun()
                except Exception as e:
                    st.error("Login failed: Invalid email or password.")
                    
        with tab2:
            reg_name = st.text_input("Full Name")
            reg_phone = st.text_input("Phone Number")
            reg_email = st.text_input("Email")
            reg_password = st.text_input("Password", type="password")
            
            if st.button("Create Account", type="primary"):
                if not reg_name or not reg_email or not reg_password:
                    st.error("Please fill out all required fields.")
                else:
                    try:
                        auth_response = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                        supabase.table("profiles").insert({
                            "id": auth_response.user.id,
                            "name": reg_name,
                            "email": reg_email,
                            "phone_number": reg_phone
                        }).execute()
                        st.success("Account created! You can now log in.")
                    except Exception as e:
                        st.error(f"Error creating account: {e}")

# --- MAIN APP VIEW ---
def main_app():
    spacer_col, theme_col, logout_col = st.columns([8, 1, 1])
    
    with theme_col:
        theme_icon = "☀️ Light" if st.session_state['theme'] == 'dark' else "🌙 Dark"
        if st.button(theme_icon):
            st.session_state['theme'] = 'dark' if st.session_state['theme'] == 'light' else 'light'
            st.rerun()
            
    with logout_col:
        if st.button("🚪 Logout"):
            try:
                supabase.auth.sign_out()
            except:
                pass
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.markdown(f"<p style='text-align: center; font-size: 18px; color: gray;'>Welcome, <b>{st.session_state['user_name']}</b>!</p>", unsafe_allow_html=True)
    st.write("")

    tab1, tab2, tab3, tab4 = st.tabs(["⚽ Matches", "🏆 Leaderboard", "📜 Rules", "🔮 Extra"])

    # Load shared API match dictionary
    all_matches = get_wc_matches()

    with tab1:
        st.write("")
        if not all_matches:
            st.warning("No matches available yet from the API.")
        else:
            forecasts_res = supabase.table("match_forecasts").select("*").eq("user_id", st.session_state['user_id']).execute()
            user_forecasts = {f['match_id']: f for f in forecasts_res.data} if forecasts_res.data else {}

            m_cols = st.columns(2)
            idx = 0
            
            for m_id, match in all_matches.items():
                if match['status'] in ['NS', 'TBD']:
                    existing = user_forecasts.get(m_id)
                    def_home = existing['home_goals'] if existing else 0
                    def_away = existing['away_goals'] if existing else 0

                    with m_cols[idx % 2]:
                        with st.container(border=True):
                            st.markdown(f"<p style='text-align: center; color: gray; font-size: 14px;'>{match['date']}</p>", unsafe_allow_html=True)
                            col1, col2, col3 = st.columns([2, 1, 2])
                            with col1:
                                if match['home_logo']:
                                    st.markdown(f"<div style='text-align: center;'><img src='{match['home_logo']}' width='40'></div>", unsafe_allow_html=True)
                                st.markdown(f"<h4 style='text-align: center;'>{match['home_team']}</h4>", unsafe_allow_html=True)
                                home_goals = st.number_input("Home Goals", min_value=0, max_value=15, step=1, value=def_home, key=f"home_{m_id}", label_visibility="collapsed")
                            with col2:
                                st.markdown("<h4 style='text-align: center; color: gray; margin-top: 30px;'>VS</h4>", unsafe_allow_html=True)
                            with col3:
                                if match['away_logo']:
                                    st.markdown(f"<div style='text-align: center;'><img src='{match['away_logo']}' width='40'></div>", unsafe_allow_html=True)
                                st.markdown(f"<h4 style='text-align: center;'>{match['away_team']}</h4>", unsafe_allow_html=True)
                                away_goals = st.number_input("Away Goals", min_value=0, max_value=15, step=1, value=def_away, key=f"away_{m_id}", label_visibility="collapsed")
                                
                            st.write("") 
                            if st.button("Save Forecast", key=f"btn_{m_id}", type="primary"):
                                forecast_data = {"user_id": st.session_state['user_id'], "match_id": m_id, "home_goals": home_goals, "away_goals": away_goals}
                                if existing:
                                    supabase.table("match_forecasts").update(forecast_data).eq("id", existing['id']).execute()
                                    st.toast("Forecast updated! ⚽")
                                else:
                                    supabase.table("match_forecasts").insert(forecast_data).execute()
                                    st.toast("Forecast saved! ⚽")
                                st.rerun()
                    idx += 1

    with tab2:
        st.write("")
        st.markdown("<h3 style='text-align: center;'>🏆 Current Standings</h3>", unsafe_allow_html=True)
        
        users_res = supabase.table("profiles").select("id, name").execute()
        all_forecasts_res = supabase.table("match_forecasts").select("*").execute()
        
        if users_res.data:
            leaderboard_data = {u['id']: {"Player": u['name'], "Exact Scores (3pt)": 0, "Correct Outcomes (1pt)": 0, "Total Points": 0} for u in users_res.data}
            
            for forecast in (all_forecasts_res.data or []):
                u_id = forecast['user_id']
                m_id = forecast['match_id']
                
                if m_id in all_matches and all_matches[m_id]['status'] == 'FT':
                    act_h = all_matches[m_id]['actual_home']
                    act_a = all_matches[m_id]['actual_away']
                    pred_h = forecast['home_goals']
                    pred_a = forecast['away_goals']
                    
                    if u_id in leaderboard_data:
                        if act_h == pred_h and act_a == pred_a:
                            leaderboard_data[u_id]["Exact Scores (3pt)"] += 1
                            leaderboard_data[u_id]["Total Points"] += 3
                        elif (act_h > act_a and pred_h > pred_a) or (act_h < act_a and pred_h < pred_a) or (act_h == act_a and pred_h == pred_a):
                            leaderboard_data[u_id]["Correct Outcomes (1pt)"] += 1
                            leaderboard_data[u_id]["Total Points"] += 1

            df = pd.DataFrame(leaderboard_data.values())
            df = df.sort_values(by=["Total Points", "Exact Scores (3pt)"], ascending=False).reset_index(drop=True)
            df.index += 1
            
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No registered players yet.")

    with tab3:
         st.markdown("### Scoring Rules 📐\n* **3 Points:** Exact score.\n* **1 Point:** Correct winner/draw.\n* **0 Points:** Incorrect result.")
         
    with tab4:
        st.write("")
        st.markdown("<h3 style='text-align: center;'>🔮 Tournament Predictions</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Lock in your big-picture guesses here!</p>", unsafe_allow_html=True)
        st.write("")
        
        extra_res = supabase.table("extra_forecasts").select("*").eq("user_id", st.session_state['user_id']).execute()
        existing_extra = extra_res.data[0] if extra_res.data else None
        
        # --- OFFICIAL 2026 WORLD CUP GROUPS AND TEAMS ---
        groups_dict = {
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
        
        # Extract and sort all 48 official teams for the Big Three dropdowns
        all_48_teams = []
        for teams in groups_dict.values():
            all_48_teams.extend(teams)
        unique_teams = sorted(all_48_teams)
            
        star_players = ["Kylian Mbappé", "Erling Haaland", "Harry Kane", "Vinícius Júnior", "Jude Bellingham", "Lionel Messi", "Cristiano Ronaldo", "Kevin De Bruyne", "Other"]

        def get_dd_index(options_list, saved_val):
            return options_list.index(saved_val) if saved_val in options_list else 0
            
        def get_rank_idx(team_list, saved_list, pos):
            if saved_list and len(saved_list) > pos and saved_list[pos] in team_list:
                return team_list.index(saved_list[pos]) + 1
            return 0

        def_winner = existing_extra.get('cup_winner', '') if existing_extra else ''
        def_scorer = existing_extra.get('top_scorer', '') if existing_extra else ''
        def_most_goals = existing_extra.get('most_goals_team', '') if existing_extra else ''
        
        with st.form("extra_forecasts_form"):
            st.subheader("🏆 The Big Three")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                cup_winner = st.selectbox("Tournament Winner", options=[""] + unique_teams, index=get_dd_index([""] + unique_teams, def_winner))
            with col2:
                top_scorer = st.selectbox("Golden Boot", options=[""] + star_players, index=get_dd_index([""] + star_players, def_scorer))
            with col3:
                most_goals = st.selectbox("Most Goals (Team)", options=[""] + unique_teams, index=get_dd_index([""] + unique_teams, def_most_goals))
                
            st.divider()
            
            st.subheader("📊 Group Stage Rankings")
            st.markdown("Select the 1st, 2nd, 3rd, and 4th place finishers for all 12 groups.")

            group_sort_data = {}
            saved_groups = existing_extra.get('groups_sort', {}) if existing_extra else {}
            
            g_cols = st.columns(4)
            for idx, (grp_name, grp_teams) in enumerate(groups_dict.items()):
                with g_cols[idx % 4]:
                    with st.container(border=True):
                        st.markdown(f"<h5 style='text-align: center; color: #1E88E5;'>{grp_name}</h5>", unsafe_allow_html=True)
                        
                        saved_sort = saved_groups.get(grp_name, [])
                        
                        p1 = st.selectbox("1st", options=[""] + grp_teams, index=get_rank_idx(grp_teams, saved_sort, 0), key=f"{grp_name}_1")
                        p2 = st.selectbox("2nd", options=[""] + grp_teams, index=get_rank_idx(grp_teams, saved_sort, 1), key=f"{grp_name}_2")
                        p3 = st.selectbox("3rd", options=[""] + grp_teams, index=get_rank_idx(grp_teams, saved_sort, 2), key=f"{grp_name}_3")
                        p4 = st.selectbox("4th", options=[""] + grp_teams, index=get_rank_idx(grp_teams, saved_sort, 3), key=f"{grp_name}_4")
                        
                        group_sort_data[grp_name] = [p1, p2, p3, p4]

            st.write("")
            submitted = st.form_submit_button("Save All Extra Forecasts", type="primary", use_container_width=True)
            
            if submitted:
                payload = {
                    "user_id": st.session_state['user_id'],
                    "cup_winner": cup_winner,
                    "top_scorer": top_scorer,
                    "most_goals_team": most_goals,
                    "groups_sort": group_sort_data
                }
                
                if existing_extra:
                    supabase.table("extra_forecasts").update(payload).eq("id", existing_extra['id']).execute()
                else:
                    supabase.table("extra_forecasts").insert(payload).execute()
                    
                st.success("All predictions and group sortings locked in! 🔒")
                st.rerun()

# --- APP ROUTING ---
if not st.session_state.get('logged_in', False):
    auth_page()
else:
    main_app()
