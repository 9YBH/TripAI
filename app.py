import streamlit as st
import json
from testing import run_travel_agent # Import your function

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Tunis Travel AI", page_icon="✈️", layout="wide")

# Custom CSS for a "Smooth" Hackathon Look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; background-color: #FF4B4B; color: white; }
    .destination-card { 
        background-color: white; padding: 20px; border-radius: 15px; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px;
        color: #1a1a1a;
    }
    .destination-card h3, .destination-card h4 { color: #1a1a1a; margin-bottom: 5px; }
    .destination-card p, .destination-card li { color: #333333; }
    .eco-badge {
        display: inline-block; padding: 4px 10px; border-radius: 12px;
        font-size: 0.85em; font-weight: bold; margin-bottom: 10px;
    }
    .eco-high { background-color: #d4edda; color: #155724; }
    .eco-med { background-color: #fff3cd; color: #856404; }
    .eco-low { background-color: #f8d7da; color: #721c24; }
    .heritage-card {
        background-color: #fff9f0; padding: 15px; border-radius: 15px;
        border-left: 4px solid #d4a373; margin: 10px 0;
    }
    .heritage-card h4 { margin: 0 0 8px 0; font-size: 1rem; color: #5a3e2b; }
    .heritage-card p { margin: 0; font-size: 0.9rem; color: #6b4f3a; }
    .heritage-badge {
        display: inline-block; padding: 3px 8px; border-radius: 10px;
        background-color: #d4a373; color: white; font-size: 0.7em; margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR / INPUTS ---
st.sidebar.title("🌍 AI Concierge")
st.sidebar.info("Flying from: Tunis-Carthage (TUN)")

with st.sidebar:
    keywords = st.text_input("🔍 What are you looking for?", placeholder="nature, hiking, quiet monuments")
    budget = st.text_input("💰 Total budget?", placeholder="$1500")
    timing = st.text_input("📅 When?", placeholder="September 2026")
    duration = st.text_input("⏱️ Stay duration?", placeholder="1 week")
    
    search_btn = st.button("Generate My Trip")

# --- MAIN DISPLAY ---
st.title("Tunisia-Global Travel Planner ✈️")
st.caption("Revolutionizing tourism through AI-driven budget, sustainability, and sentiment analysis.")

if search_btn:
    if not keywords or not budget:
        st.error("Please fill in the keywords and budget!")
    else:
        with st.status("🤖 AI is researching destinations & Reddit sentiment...", expanded=True) as status:
            st.write("Fetching live data & calculating Carbon Footprint...")
            # Run your backend function
            results = run_travel_agent(keywords, budget, timing, duration)
            status.update(label="Planning Complete!", state="complete", expanded=False)

        # Display Results
        cols = st.columns(3)
        
        for i, dest in enumerate(results.get("destinations", [])):
            with cols[i]:
                # Safely extract metrics
                sus_metrics = dest.get("sustainability_metrics", {})
                eco_score = sus_metrics.get("total_eco_score", 50)
                
                # Determine Badge Color
                if eco_score >= 75: badge_class = "eco-high"
                elif eco_score >= 50: badge_class = "eco-med"
                else: badge_class = "eco-low"

                # Safely handle budget dictionary changes
                budget_data = dest.get('budget_breakdown', {})
                accom = budget_data.get('accommodation', budget_data.get('accommodation_budget', 'N/A'))
                daily = budget_data.get('daily_limit', budget_data.get('daily_spending_limit', 'N/A'))

                st.markdown(f"""
                <div class="destination-card">
                    <h3>{dest['location']}</h3>
                    <span class="eco-badge {badge_class}">🌿 Eco-Score: {eco_score}/100</span>
                    <p><b>Pitch:</b> {dest['pitch']}</p>
                    <hr>
                    <h4>💰 Budget Breakdown</h4>
                    <ul>
                        <li><b>Flight:</b> {dest.get('flight_price_from_tun', 'N/A')}</li>
                        <li><b>Stay:</b> {accom}</li>
                        <li><b>Daily:</b> {daily}</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
                # --- SUSTAINABILITY & OVERTOURISM EXPANDER ---
                with st.expander("🌿 Eco & Impact Metrics", expanded=True):
                    st.progress(eco_score / 100.0, text=f"Total Eco-Score ({eco_score}/100)")
                    st.write(f"**✈️ Flight CO2:** {sus_metrics.get('flight_co2_kg', 'N/A')} kg")
                    st.write(f"**🚶 Green Rationale:** {sus_metrics.get('green_rationale', 'N/A')}")
                    
                    # Crowd Alert Formatting
                    crowd = sus_metrics.get("crowd_level", "Unknown")
                    if "High" in crowd:
                        st.error(f"**👥 Crowd Level:** {crowd}")
                        st.warning(f"**Alert:** {sus_metrics.get('overtourism_warning', 'N/A')}")
                    else:
                        st.success(f"**👥 Crowd Level:** {crowd}")

                # --- REDDIT SENTIMENT EXPANDER ---
                with st.expander("💬 What Reddit says"):
                    st.write(f"**Vibe:** {dest.get('reddit_sentiment', {}).get('overall_vibe', 'N/A')}")
                    st.write(f"**Insider Tip:** {dest.get('reddit_sentiment', {}).get('insider_tip', 'N/A')}")
                
                # --- HERITAGE SPOTLIGHT ---
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
                
                # --- YOUTUBE TRAVEL VIDEO ---
                video_url = dest.get("local_video_url", "")
                if video_url and "youtube.com/watch" in video_url:
                    st.markdown("**🎬 Travel Video**")
                    st.video(video_url)
                elif video_url:
                    st.link_button("🎬 Watch Travel Videos", video_url, use_container_width=True)
                
                st.link_button(f"Book Flights to {dest['nearest_airport_iata']}", dest.get('flight_booking_link', '#'))
                st.link_button("🏨 Hotels (Booking.com)", dest.get('hotel_booking_link', '#'))
                if dest.get('hotel_booking_link_alt'):
                    st.link_button("🏠 Airbnb", dest['hotel_booking_link_alt'])

else:
    # Landing State
    st.image("https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1200", caption="Where will Tunis take you next?")