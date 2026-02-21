import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from database import init_db, cleanup_old_data

# Page configuration
st.set_page_config(
    page_title="Winter Weather Tracker",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide the default Streamlit multipage navigation (file names in sidebar)
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# Initialize database
init_db()

# Auto-cleanup old data (60 days - preserves storm evolution history for retrospective review)
cleanup_old_data(60)

# Sidebar navigation
st.sidebar.title("❄️ Winter Weather Tracker")
st.sidebar.markdown("Track how winter forecasts evolve over time")

page = st.sidebar.radio(
    "Navigate",
    ["Setup & Fetch Data", "Storm Watch", "Storm Dashboard", "Current Forecast", "NWS Graphics", "Forecast Evolution", "Discussion Archive", "My Observations", "Data Sources"]
)

# Import page modules
if page == "Setup & Fetch Data":
    import pages.setup as setup
    setup.show()
elif page == "Storm Watch":
    import pages.storm_watch as storm_watch
    storm_watch.show()
elif page == "Storm Dashboard":
    import pages.storm_dashboard as storm_dashboard
    storm_dashboard.show()
elif page == "Current Forecast":
    import pages.current_forecast as current
    current.show()
elif page == "NWS Graphics":
    import pages.nws_graphics as nws_graphics
    nws_graphics.show()
elif page == "Forecast Evolution":
    import pages.evolution as evolution
    evolution.show()
elif page == "Discussion Archive":
    import pages.discussions as discussions
    discussions.show()
elif page == "My Observations":
    import pages.observations as observations
    observations.show()
elif page == "Data Sources":
    import pages.data_sources as data_sources
    data_sources.show()
