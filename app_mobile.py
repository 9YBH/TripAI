import streamlit as st
import json
from testing import run_travel_agent # Import your function

# --- UI CONFIGURATION (Mobile constraints) ---
st.set_page_config(page_title="Tunis Travel AI Mobile", page_icon="📱", layout="centered")

# Custom CSS for a "Mobile Phone" look
st.markdown("""
    <style>
    /* FORCE LIGHT THEME - Override Streamlit's dark mode globally */
    .stApp, .main, .block-container, [data-testid="stAppViewContainer"],
    [data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"],
    .element-container, .stMarkdown, [data-testid="stMarkdownContainer"] {
        color: #1a1a1a !important;
        background-color: transparent !important;
    }
    
    /* Force all text elements dark */
    .stApp p, .stApp span, .stApp label, .stApp li, .stApp div,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stCaptionContainer"] span,
    .stExpander p, .stExpander span, .stExpander label,
    [data-testid="stExpanderDetails"] p,
    [data-testid="stExpanderDetails"] span {
        color: #1a1a1a !important;
    }
    
    /* Input labels */
    .stTextInput label, .stSelectbox label {
        color: #1a1a1a !important;
    }
    
    /* Force the main container to look like a mobile screen */
    .block-container {
        max-width: 430px; /* iPhone Pro Max width */
        margin: 0 auto;
        padding: 2rem 1rem 4rem 1rem;
        background-color: #f8f9fa !important;
        border-radius: 30px;
        box-shadow: 0px 10px 30px rgba(0,0,0,0.15);
        border: 8px solid #333; /* Simulated phone bezel */
    }

    /* Main app background */
    [data-testid="stAppViewContainer"] {
        background-color: #e9ecef !important;
    }
    
    /* Hide default Streamlit header & footer for a cleaner app look */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .stButton>button { 
        width: 100%; border-radius: 25px; height: 3.5em; 
        background-color: #FF4B4B; color: white !important; font-weight: bold;
        box-shadow: 0 4px 6px rgba(255, 75, 75, 0.3);
    }
    .destination-card { 
        background-color: white !important; padding: 20px; border-radius: 20px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 25px;
        color: #1a1a1a !important;
    }
    .destination-card * { color: #333 !important; }
    .destination-card h3 { color: #1a1a1a !important; margin-bottom: 5px; font-size: 1.5rem; }
    .destination-card h4 { color: #1a1a1a !important; font-size: 1.1rem; margin-top: 15px; border-bottom: 1px solid #eee; padding-bottom: 5px;}
    .eco-badge {
        display: inline-block; padding: 5px 12px; border-radius: 15px;
        font-size: 0.8em; font-weight: bold; margin-bottom: 15px;
    }
    .eco-high { background-color: #d4edda; color: #155724 !important; }
    .eco-med { background-color: #fff3cd; color: #856404 !important; }
    .eco-low { background-color: #f8d7da; color: #721c24 !important; }
    
    /* Heritage card */
    .heritage-card {
        background-color: #fff9f0 !important; padding: 15px; border-radius: 15px;
        border-left: 4px solid #d4a373; margin: 10px 0;
    }
    .heritage-card * { color: #5a3e2b !important; }
    .heritage-card h4 { margin: 0 0 8px 0; font-size: 1rem; color: #5a3e2b !important; }
    .heritage-card p { margin: 0; font-size: 0.9rem; color: #6b4f3a !important; }
    .heritage-badge {
        display: inline-block; padding: 3px 8px; border-radius: 10px;
        background-color: #d4a373; color: white !important; font-size: 0.7em; margin-top: 5px;
    }
    
    /* App Title styling */
    .app-header { text-align: center; margin-bottom: 20px; }
    .app-header h1 { font-size: 1.8rem; margin-bottom: 0; color: #1a1a1a !important; }
    .app-header p { color: #555 !important; font-size: 0.9rem; }
    
    /* Expander text fix */
    [data-testid="stExpander"] summary span { color: #1a1a1a !important; }
    [data-testid="stExpander"] { background-color: #f8f9fa !important; border-radius: 10px; }
    
    /* Divider */
    hr { border-color: #ddd !important; }
    </style>
    """, unsafe_allow_html=True)

# --- MAIN MOBILE UI ---
st.markdown("<div class='app-header'><h1>✈️ AI Concierge</h1><p>Flying from: TUN</p></div>", unsafe_allow_html=True)

# Mobile form (No sidebar, everything is inline)
with st.container():
    keywords = st.text_input("🔍 Vibe?", placeholder="nature, quiet...")
    cols = st.columns(2)
    with cols[0]:
        budget = st.text_input("💰 Budget?", placeholder="$1500")
    with cols[1]:
        duration = st.text_input("⏱️ Stay?", placeholder="1 week")
    timing = st.text_input("📅 When?", placeholder="Sept 2026")
    
    search_btn = st.button("Generate My Trip")

st.divider()

if search_btn:
    if not keywords or not budget:
        st.error("Please fill in the keywords and budget!")
    else:
        with st.status("🤖 Analyzing destinations...", expanded=True) as status:
            st.write("Fetching live flight data...")
            st.write("Calculating carbon footprints...")
            # Run your backend function
            results = run_travel_agent(keywords, budget, timing, duration)
            status.update(label="Ready!", state="complete", expanded=False)

        # VERTICAL FEED (Mobile Layout)
        for dest in results.get("destinations", []):
            sus_metrics = dest.get("sustainability_metrics", {})
            eco_score = sus_metrics.get("total_eco_score", 50)
            
            if eco_score >= 75: badge_class = "eco-high"
            elif eco_score >= 50: badge_class = "eco-med"
            else: badge_class = "eco-low"

            budget_data = dest.get('budget_breakdown', {})
            accom = budget_data.get('accommodation', budget_data.get('accommodation_budget', 'N/A'))
            daily = budget_data.get('daily_limit', budget_data.get('daily_spending_limit', 'N/A'))

            st.markdown(f"""
            <div class="destination-card">
                <h3>{dest['location']}</h3>
                <span class="eco-badge {badge_class}">🌿 Eco-Score: {eco_score}/100</span>
                <p><b>Why:</b> {dest['pitch']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("💰 Budget Breakdown", expanded=True):
                st.caption(f"✈️ **Flight:** {dest.get('flight_price_from_tun', 'N/A')}")
                st.caption(f"🏨 **Stay:** {accom}")
                st.caption(f"🍔 **Daily:** {daily}")
            
            # Expanders act as mobile dropdown menus
            with st.expander("🌿 Eco & Impact Details"):
                st.progress(eco_score / 100.0)
                st.caption(f"**✈️ Flight CO2:** {sus_metrics.get('flight_co2_kg', 'N/A')} kg")
                st.caption(f"**🚶 Vibe:** {sus_metrics.get('green_rationale', 'N/A')}")
                
                crowd = sus_metrics.get("crowd_level", "Unknown")
                if "High" in crowd:
                    st.error(f"👥 Crowd Level: {crowd}")
                    st.warning(sus_metrics.get('overtourism_warning', 'N/A'))
                else:
                    st.success(f"👥 Crowd Level: {crowd}")

            with st.expander("💬 Reddit Sentiment"):
                st.caption(f"**Vibe:** {dest.get('reddit_sentiment', {}).get('overall_vibe', 'N/A')}")
                st.caption(f"**Tip:** {dest.get('reddit_sentiment', {}).get('insider_tip', 'N/A')}")
            
            # Heritage Spotlight
            heritage = dest.get("heritage_spotlight", {})
            if heritage and heritage.get("site_name"):
                h_type = heritage.get("type", "Landmark")
                st.markdown(f"""
                <div class="heritage-card">
                    <h4>🏛️ {heritage.get('site_name', '')}</h4>
                    <p>{heritage.get('heritage_story', '')}</p>
                    <span class="heritage-badge">{h_type}</span>
                </div>
                """, unsafe_allow_html=True)
            
            # YouTube Travel Video
            video_url = dest.get("local_video_url", "")
            if video_url and "youtube.com/watch" in video_url:
                st.markdown("**🎬 Travel Video**")
                st.video(video_url)
            elif video_url:
                st.link_button("🎬 Watch Travel Videos", video_url, use_container_width=True)
            
            # Action buttons grouped at the bottom of each card
            st.link_button(f"✈️ Book Flight", dest.get('flight_booking_link', '#'), use_container_width=True)
            st.link_button("🏨 View Hotels", dest.get('hotel_booking_link', '#'), use_container_width=True)
            st.divider()

else:
    # Empty state image
    st.image("https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=800", caption="Tap above to start planning", use_container_width=True)