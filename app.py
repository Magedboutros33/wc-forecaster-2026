import streamlit as st
import requests
from supabase import create_client, Client

# --- CONFIGURATION & INITIALIZATION ---
st.set_page_config(page_title="WC 2026 Forecast", layout="wide", page_icon="⚽")

# Initialize Supabase Client
# Make sure these are added to your Streamlit Secrets!
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Mock User Session for testing (Replace with your actual login system)
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = "player_1"  # Temporary placeholder id
if 'username' not in st.session_state:
    st.session_state['username'] = "Maged"

# --- API CONNECTION WITH CACHING ENGINE ---
@st.cache_data(ttl=600)  # Caches match data for 10 minutes to protect your free-tier key
def get_matches_from_api():
    # 'WC' is the official API code for the FIFA World Cup
    url = "https://api.football-data.org/v4/competitions/WC/matches"
    headers = {"X-Auth-Token": st.secrets["FOOTBALL_DATA_KEY"]}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('matches', [])
        else:
            st.error(f"API Connection Error: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return []

# --- SCORING ENGINE ---
def calculate_points(actual_h, actual_a, pred_h, pred_a):
    if actual_h is None or actual_a is None: 
        return 0
    # Exact Match Score (3 Points)
    if actual_h == pred_h and actual_a == pred_a: 
        return 3
    # Correct Outcome (1 Point)
    if (actual_h > actual_a and pred_h > pred_a) or \
       (actual_h < actual_a and pred_h < pred_a) or \
       (actual_h == actual_a and pred_h == pred_a): 
        return 1
    return 0

# --- DATA WRITER (SUPABASE) ---
def save_forecast(match_id, home_goals, away_goals):
    user_id = st.session_state['user_id']
    
    # Check if this user already submitted a prediction for this specific match
    existing = supabase.table("match_forecasts") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("match_id", match_id) \
        .execute()

    forecast_data = {
        "user_id": user_id,
        "match_id": match_id,
        "home_goals": home_goals,
        "away_goals": away_goals
    }

    try:
        if existing.data:
            # Update the existing row
            supabase.table("match_forecasts") \
                .update(forecast_data) \
                .eq("id", existing.data[0]['id']) \
                .execute()
            st.toast("Forecast updated successfully! 🔄")
        else:
            # Insert a completely new row
            supabase.table("match_forecasts") \
                .insert(forecast_data) \
                .execute()
            st.toast("Forecast saved successfully! ✅")
    except Exception as e:
        st.error(f"Database error: {e}")

# --- MAIN APP INTERFACE ---
def main():
    st.title("⚽ World Cup 2026 Forecast Challenge")
    st.write(f"Logged in as: **{st.session_state['username']}**")
    
    # Fetch data safely from cached engine
    matches = get_matches_from_api()
    if not matches:
        st.warning("No matches available from the API at the moment.")
        return

    # Bulk query current user's forecasts to prevent multiple database hits
    try:
        forecasts_res = supabase.table("match_forecasts") \
            .select("match_id, home_goals, away_goals") \
            .eq("user_id", st.session_state['user_id']) \
            .execute()
        user_forecasts = {f['match_id']: f for f in forecasts_res.data}
    except Exception:
        user_forecasts = {}

    # Define Navigation Tabs
    tab1, tab2 = st.tabs(["📅 Matches & Predictions", "🏆 Leaderboard"])
    
    with tab1:
        st.subheader("Upcoming and Live Matches")
        
        for match in matches:
            m_id = match['id']
            status = match['status']
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']
            home_code = match['homeTeam'].get('tla', 'UN') # Three-letter code fallback
            away_code = match['awayTeam'].get('tla', 'UN')
            
            # Extract actual goals if the match has started or finished
            actual_home = match['score']['fullTime'].get('home')
            actual_away = match['score']['fullTime'].get('away')

            # Render match UI box
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 3])
                
                with col1:
                    # Dynamically build flag link via FlagCDN structure using country codes
                    st.image(f"https://flagcdn.com/w40/{home_code[:2].lower()}.png", width=30)
                    st.markdown(f"### {home_team}")
                    
                with col2:
                    st.markdown(f"<p style='text-align: center;'><b>Status: {status}</b></p>", unsafe_allow_html=True)
                    if actual_home is not None and actual_away is not None:
                        st.markdown(f"<h2 style='text-align: center;'>{actual_home} - {actual_away}</h2>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h4 style='text-align: center;'>vs</h4>", unsafe_allow_html=True)
                        
                with col3:
                    st.image(f"https://flagcdn.com/w40/{away_code[:2].lower()}.png", width=30)
                    st.markdown(f"### {away_team}")

                # Forecast Entry Row
                if status in ["TIMED", "SCHEDULED"]:
                    # Find previous entries if they exist
                    saved_home = user_forecasts.get(m_id, {}).get('home_goals', 0)
                    saved_away = user_forecasts.get(m_id, {}).get('away_goals', 0)
                    
                    f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
                    pred_h = f_col1.number_input(f"{home_team} Score", min_value=0, value=int(saved_home), key=f"h_{m_id}")
                    pred_a = f_col2.number_input(f"{away_team} Score", min_value=0, value=int(saved_away), key=f"a_{m_id}")
                    
                    if f_col3.button("Save", key=f"btn_{m_id}", use_container_width=True):
                        save_forecast(m_id, pred_h, pred_a)
                        st.rerun()
                else:
                    # Match finished or live, reveal user's score vs actual
                    if m_id in user_forecasts:
                        u_h = user_forecasts[m_id]['home_goals']
                        u_a = user_forecasts[m_id]['away_goals']
                        pts = calculate_points(actual_home, actual_away, u_h, u_a)
                        st.info(f"Your prediction: {u_h} - {u_a} | Points Earned: **{pts}**")
                    else:
                        st.write("You did not lock in a prediction for this match.")

    with tab2:
        st.subheader("Leaderboard Standings")
        # In a full deployment, you will query all rows from match_forecasts,
        # run calculate_points across everyone's data, group by user, and display the ordered chart here!
        st.dataframe(pd.DataFrame(columns=["Rank", "Player", "Total Points"]))
        st.info("Leaderboard scores will compute automatically as match rows change to finished status on the API.")

if __name__ == "__main__":
    main()
