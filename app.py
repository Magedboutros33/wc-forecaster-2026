import streamlit as st

# --- CONFIGURATION ---
st.set_page_config(page_title="World Cup 2026 Forecaster", page_icon="🏆", layout="centered")

# --- INITIALIZE SESSION STATES ---
if 'theme' not in st.session_state:
    st.session_state['theme'] = 'light'
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'users' not in st.session_state:
    st.session_state['users'] = {'admin': 'password123', 'friend1': 'pass'}
if 'forecasts' not in st.session_state:
    st.session_state['forecasts'] = {}
if 'points' not in st.session_state:
    st.session_state['points'] = {'admin': 0, 'friend1': 0}

# --- CUSTOM CSS ---
def inject_custom_css():
    # Determine colors based on toggle state
    bg_color = "#0E1117" if st.session_state['theme'] == 'dark' else "#FFFFFF"
    text_color = "#FAFAFA" if st.session_state['theme'] == 'dark' else "#31333F"
    
    st.markdown(f"""
    <style>
        /* Hide the default Streamlit sidebar menu icon */
        [data-testid="collapsedControl"] {{
            display: none;
        }}
        
        /* Apply basic dark/light theme */
        .stApp {{
            background-color: {bg_color};
            color: {text_color};
        }}
        h1, h2, h3, h4, p {{
            color: {text_color} !important;
        }}
        
        /* Center the Tabs in the middle upper center */
        .stTabs [data-baseweb="tab-list"] {{
            justify-content: center;
            gap: 15px;
        }}
        
        /* Button styling for touch targets */
        .stButton>button {{
            width: 100%;
            border-radius: 8px;
            font-weight: 600;
        }}
        
        /* Center numbers in inputs */
        input[type="number"] {{
            text-align: center;
            font-size: 1.2rem;
        }}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- AUTHENTICATION VIEW ---
def login():
    st.write("") # Spacing
    st.markdown("<h1 style='text-align: center;'>🏆 WC 2026 Forecaster</h1>", unsafe_allow_html=True)
    st.write("") 
    
    # Wrap login in a slightly narrower column so it looks good on PC
    _, col, _ = st.columns([1, 2, 1])
    with col:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary"):
            if username in st.session_state['users'] and st.session_state['users'][username] == password:
                st.session_state['logged_in'] = True
                st.session_state['current_user'] = username
                st.rerun()
            else:
                st.error("Incorrect username or password.")

# --- MAIN APP VIEW ---
def main_app():
    # TOP HEADER: Push buttons to the Top Right
    # Empty column takes up 60% of space, the buttons take up 20% each
    spacer_col, theme_col, logout_col = st.columns([6, 2, 2])
    
    with theme_col:
        # Toggle theme state on click
        theme_icon = "☀️ Light" if st.session_state['theme'] == 'dark' else "🌙 Dark"
        if st.button(theme_icon):
            st.session_state['theme'] = 'dark' if st.session_state['theme'] == 'light' else 'light'
            st.rerun()
            
    with logout_col:
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    # Welcome message (Centered)
    st.markdown(f"<p style='text-align: center; font-size: 18px; color: gray;'>Welcome, <b>{st.session_state['current_user']}</b>!</p>", unsafe_allow_html=True)
    st.write("")

    # THE 4 SUBPAGES (TABS) - Centered automatically by CSS
    tab1, tab2, tab3, tab4 = st.tabs(["⚽ Matches", "🏆 Leaderboard", "📜 Rules", "🔮 Extra Forecasting"])

    with tab1:
        st.write("") # Spacing
        # Match Card Container
        with st.container(border=True):
            st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>June 15, 2026 • Group Stage</p>", unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.markdown("<h4 style='text-align: center;'>🇺🇸 USA</h4>", unsafe_allow_html=True)
                home_goals = st.number_input("USA Goals", min_value=0, max_value=15, step=1, key="home_101", label_visibility="collapsed")
            with col2:
                st.markdown("<h4 style='text-align: center; color: gray; margin-top: 10px;'>VS</h4>", unsafe_allow_html=True)
            with col3:
                st.markdown("<h4 style='text-align: center;'>🇫🇷 FRA</h4>", unsafe_allow_html=True)
                away_goals = st.number_input("FRA Goals", min_value=0, max_value=15, step=1, key="away_101", label_visibility="collapsed")
                
            st.write("") 
            if st.button("Save Forecast", type="primary"):
                user = st.session_state['current_user']
                st.session_state['forecasts'][f"{user}_101"] = (home_goals, away_goals)
                st.success("Forecast saved! Good luck.")

    with tab2:
        st.write("") 
        # Using a clean table format
        import pandas as pd
        leaderboard_data = [{"Player": k.capitalize(), "Points": v} for k, v in st.session_state['points'].items()]
        df = pd.DataFrame(leaderboard_data).sort_values(by="Points", ascending=False).reset_index(drop=True)
        df.index = df.index + 1
        st.dataframe(df, use_container_width=True)

    with tab3:
        st.write("") 
        st.markdown("""
        ### Scoring Rules 📐
        * **3 Points:** Correctly guessing the exact score.
        * **1 Point:** Correctly guessing the winner or a draw (wrong score).
        * **0 Points:** Incorrect result.
        """)

    with tab4:
        st.write("") 
        st.subheader("Extra Tournament Forecasts")
        st.write("Predict overarching tournament results before the first match kicks off!")
        
        st.selectbox("🏆 Who will win the World Cup?", ["Brazil", "France", "England", "Argentina", "Spain", "USA", "Other"])
        st.selectbox("👟 Who will be the Top Scorer (Golden Boot)?", ["Mbappe", "Haaland", "Kane", "Vinicius Jr", "Other"])
        st.button("Save Extra Forecasts")

# --- APP ROUTING ---
if not st.session_state['logged_in']:
    login()
else:
    main_app()