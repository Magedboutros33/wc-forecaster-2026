import streamlit as st
from supabase import create_client, Client

# --- CONFIGURATION ---
st.set_page_config(page_title="World Cup 2026 Forecaster", page_icon="🏆", layout="centered")

# --- INITIALIZE SUPABASE ---
@st.cache_resource
def init_connection():
    # Trim trailing slashes if present in the secret URL
    url = st.secrets["SUPABASE_URL"].strip().rstrip('/')
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error(f"Failed to connect to database. Check your secrets configuration. Error: {e}")

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

# --- AUTHENTICATION VIEW (LOGIN & SIGNUP) ---
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
                    # Log in with Supabase Auth
                    response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                    user = response.user
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = user.id
                    
                    # Fetch their name from our custom profiles table
                    profile = supabase.table("profiles").select("name").eq("id", user.id).execute()
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
                    st.error("Please fill out all required fields (Name, Email, Password).")
                else:
                    try:
                        # 1. Create user in Supabase Auth backend
                        auth_response = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                        new_user_id = auth_response.user.id
                        
                        # 2. Add supplementary information to public.profiles table
                        supabase.table("profiles").insert({
                            "id": new_user_id,
                            "name": reg_name,
                            "email": reg_email,
                            "phone_number": reg_phone
                        }).execute()
                        
                        st.success("Account created successfully! You can now switch to the Login tab.")
                    except Exception as e:
                        st.error(f"Error creating account: {e}")

# --- MAIN APP VIEW ---
def main_app():
    spacer_col, theme_col, logout_col = st.columns([6, 2, 2])
    
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

    with tab1:
        st.info("Match forecasting will connect to the database in the next step!")
    with tab2:
        st.info("Leaderboard will connect to the database in the next step!")
    with tab3:
         st.markdown("### Scoring Rules 📐\n* **3 Points:** Exact score.\n* **1 Point:** Correct winner/draw.\n* **0 Points:** Incorrect result.")
    with tab4:
        st.info("Extra forecasting will connect to the database in the next step!")

# --- APP ROUTING ---
if not st.session_state.get('logged_in', False):
    auth_page()
else:
    main_app()
