import os
import re
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq
from tavily import TavilyClient
from supabase import create_client
from amadeus import Client, ResponseError
from openai import OpenAI
import math

# 1. SETUP
load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
groq_backup_client = Groq(api_key=os.getenv("GROQ_API_KEY_BACKUP"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# OpenRouter API setup (fallback LLM)
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Amadeus API setup
amadeus = Client(
    client_id=os.getenv("AMADEUS_API_KEY"),
    client_secret=os.getenv("AMADEUS_API_SECRET")
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# --- TOKEN TRACKING (Groq daily limit: 100k, threshold: 90%) ---
GROQ_DAILY_LIMIT = 100000
GROQ_THRESHOLD = 0.90  # Switch at 90%
groq_tokens_used = 0
groq_backup_tokens_used = 0

def parse_timing_to_date(timing_str):
    """Parse flexible timing strings into a YYYY-MM-DD date"""
    timing_lower = timing_str.lower().strip()
    now = datetime.now()
    
    # Try standard "Month Year" format first (e.g., "September 2026")
    try:
        dt = datetime.strptime(timing_str.strip(), "%B %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    # Try "Month" only (assume current/next year)
    try:
        dt = datetime.strptime(timing_str.strip(), "%B")
        dt = dt.replace(year=now.year)
        if dt < now:
            dt = dt.replace(year=now.year + 1)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    
    # Handle relative expressions
    if "next month" in timing_lower:
        dt = now.replace(day=15) + timedelta(days=31)
        return dt.replace(day=15).strftime("%Y-%m-%d")
    if "next week" in timing_lower:
        return (now + timedelta(days=7)).strftime("%Y-%m-%d")
    if "next year" in timing_lower:
        return now.replace(year=now.year + 1, month=6, day=1).strftime("%Y-%m-%d")
    
    # Match "in X months"
    m = re.search(r"in\s+(\d+)\s+months?", timing_lower)
    if m:
        months = int(m.group(1))
        dt = now.replace(day=15)
        for _ in range(months):
            dt += timedelta(days=31)
        return dt.replace(day=15).strftime("%Y-%m-%d")
    
    # Match "in X weeks"
    m = re.search(r"in\s+(\d+)\s+weeks?", timing_lower)
    if m:
        return (now + timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")
    
    # Fallback: 3 months from now
    return (now + timedelta(days=90)).strftime("%Y-%m-%d")

def parse_duration_to_days(duration_str):
    """Parse a duration string into number of days"""
    d = duration_str.lower().strip()
    
    m = re.search(r"(\d+)\s*days?", d)
    if m:
        return int(m.group(1))
    
    m = re.search(r"(\d+)\s*weeks?", d)
    if m:
        return int(m.group(1)) * 7
    
    if "a week" in d or "one week" in d:
        return 7
    if "two weeks" in d or "2 weeks" in d:
        return 14
    
    m = re.search(r"(\d+)\s*months?", d)
    if m:
        return int(m.group(1)) * 30
    
    if "a month" in d or "one month" in d:
        return 30
    
    # Fallback
    return 7

def openrouter_request(messages, json_mode=False):
    """Fallback: Make a request via OpenRouter"""
    params = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": messages
    }
    if json_mode:
        params["response_format"] = {"type": "json_object"}
    
    response = openrouter_client.chat.completions.create(**params)
    return response

def groq_request(messages, json_mode=False, max_retries=3):
    """Smart LLM router: Groq primary → Groq backup → OpenRouter"""
    global groq_tokens_used, groq_backup_tokens_used
    
    # Check if primary Groq should switch
    if groq_tokens_used >= GROQ_DAILY_LIMIT * GROQ_THRESHOLD:
        print(f"    🔄 Groq primary at {groq_tokens_used}/{GROQ_DAILY_LIMIT} ({groq_tokens_used/GROQ_DAILY_LIMIT*100:.0f}%). Trying backup key...")
        
        # Try backup Groq key
        if groq_backup_tokens_used < GROQ_DAILY_LIMIT * GROQ_THRESHOLD:
            try:
                params = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages
                }
                if json_mode:
                    params["response_format"] = {"type": "json_object"}
                
                response = groq_backup_client.chat.completions.create(**params)
                
                if hasattr(response, 'usage') and response.usage:
                    groq_backup_tokens_used += response.usage.total_tokens
                    pct = groq_backup_tokens_used / GROQ_DAILY_LIMIT * 100
                    print(f"    📊 Groq backup tokens: {groq_backup_tokens_used}/{GROQ_DAILY_LIMIT} ({pct:.0f}%)")
                return response
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    used_match = re.search(r"Used\s+(\d+)", error_str)
                    if used_match:
                        groq_backup_tokens_used = int(used_match.group(1))
                    print(f"    ⚠️ Groq backup also rate limited. Falling back to OpenRouter...")
                else:
                    print(f"    ⚠️ Groq backup error: {e}. Falling back to OpenRouter...")
        else:
            print(f"    ⚠️ Groq backup also at {groq_backup_tokens_used/GROQ_DAILY_LIMIT*100:.0f}%. Falling back to OpenRouter...")
        
        # Both Groq keys exhausted, use OpenRouter
        try:
            return openrouter_request(messages, json_mode)
        except Exception as e:
            print(f"    ⚠️ OpenRouter failed: {e}. Trying Groq anyway...")
    
    # Try primary Groq with retry logic
    for attempt in range(1, max_retries + 1):
        try:
            params = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages
            }
            if json_mode:
                params["response_format"] = {"type": "json_object"}
            
            response = groq_client.chat.completions.create(**params)
            
            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                groq_tokens_used += response.usage.total_tokens
                pct = groq_tokens_used / GROQ_DAILY_LIMIT * 100
                print(f"    📊 Groq tokens used: {groq_tokens_used}/{GROQ_DAILY_LIMIT} ({pct:.0f}%)")
            
            return response
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str.lower():
                # Extract used tokens from error
                used_match = re.search(r"Used\s+(\d+)", error_str)
                if used_match:
                    groq_tokens_used = int(used_match.group(1))
                
                # Try backup Groq key first
                print(f"    🔄 Groq primary rate limited! Trying backup key...")
                try:
                    params = {
                        "model": "llama-3.3-70b-versatile",
                        "messages": messages
                    }
                    if json_mode:
                        params["response_format"] = {"type": "json_object"}
                    
                    response = groq_backup_client.chat.completions.create(**params)
                    
                    if hasattr(response, 'usage') and response.usage:
                        groq_backup_tokens_used += response.usage.total_tokens
                        pct = groq_backup_tokens_used / GROQ_DAILY_LIMIT * 100
                        print(f"    📊 Groq backup tokens: {groq_backup_tokens_used}/{GROQ_DAILY_LIMIT} ({pct:.0f}%)")
                    return response
                except Exception as backup_err:
                    backup_str = str(backup_err)
                    if "429" in backup_str or "rate_limit" in backup_str.lower():
                        used_match2 = re.search(r"Used\s+(\d+)", backup_str)
                        if used_match2:
                            groq_backup_tokens_used = int(used_match2.group(1))
                    print(f"    ⚠️ Groq backup also failed. Falling back to OpenRouter...")
                
                # Both Groq keys failed, try OpenRouter
                try:
                    return openrouter_request(messages, json_mode)
                except Exception as or_err:
                    print(f"    ⚠️ OpenRouter also failed: {or_err}")
                    if attempt < max_retries:
                        wait_secs = 30 * attempt
                        print(f"    ⏳ Waiting {wait_secs}s before retry...")
                        time.sleep(wait_secs)
            else:
                raise e
    raise Exception("All LLM providers failed (Groq primary, Groq backup, OpenRouter). Try again later.")

# Function to fetch flight prices from TUN with retry logic
def get_flight_price_from_tun(dest_code, travel_date, return_date=None, max_retries=3):
    """Fetch real round-trip flight prices from Tunis (TUN) to the destination IATA code"""
    origin = "TUN"
    dest_code = dest_code.upper().strip()
    for attempt in range(1, max_retries + 1):
        try:
            params = {
                "originLocationCode": origin,
                "destinationLocationCode": dest_code,
                "departureDate": travel_date,
                "adults": 1,
                "currencyCode": "USD",
                "max": 1
            }
            # Add return date for round-trip pricing
            if return_date:
                params["returnDate"] = return_date
            
            response = amadeus.shopping.flight_offers_search.get(**params)
            
            if response.data:
                price = float(response.data[0]['price']['total'])
                trip_type = "round-trip" if return_date else "one-way"
                return {"price": f"${price:.0f} ({trip_type})", "price_numeric": price}
            else:
                return {"price": "No flights found", "price_numeric": 0}
                
        except ResponseError as e:
            print(f"    ⚠️ Amadeus attempt {attempt}/{max_retries} failed for {dest_code}: {e.response.body if e.response else e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)  # Exponential backoff
            else:
                return {"price": "API Error (after retries)", "price_numeric": 0}
        except Exception as e:
            print(f"    ⚠️ Unexpected error for {dest_code}: {e}")
            return {"price": "Error", "price_numeric": 0}

def get_local_youtube_video(location):
    """Search YouTube via Tavily for a travel guide video about the destination"""
    try:
        query = f"{location} travel guide vlog"
        results = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            include_domains=["youtube.com"]
        )
        for r in results.get("results", []):
            url = r.get("url", "")
            if "youtube.com/watch" in url:
                return url
        # Fallback: YouTube search link
        return f"https://www.youtube.com/results?search_query={location.replace(' ', '+')}+travel+guide"
    except Exception as e:
        print(f"    ⚠️ YouTube search failed for {location}: {e}")
        return f"https://www.youtube.com/results?search_query={location.replace(' ', '+')}+travel+guide"

def estimate_flight_emissions(dest_iata):
    """
    Hackathon-optimized Carbon Calculator. 
    Estimates CO2 footprint from TUN to the destination.
    In production, this is where you'd call the Google TIM API:
    https://travelimpactmodel.googleapis.com/v1/flights:computeFlightEmissions
    """
    # Rough coordinates for Tunis (TUN) and popular hubs for distance estimation
    airports = {
        "TUN": (36.8510, 10.2272),
        "CDG": (49.0097, 2.5479),   # Paris
        "FCO": (41.7999, 12.2462),  # Rome
        "IST": (41.2753, 28.7519),  # Istanbul
        "BCN": (41.2974, 2.0833),   # Barcelona
        "CMN": (33.3675, -7.5898),  # Casablanca
        # Fallback coordinate if airport isn't in this quick-dict
        "DEFAULT": (45.0, 10.0) 
    }
    
    origin = airports["TUN"]
    dest = airports.get(dest_iata.upper(), airports["DEFAULT"])
    
    # Haversine formula to calculate distance in km
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    lat2, lon2 = math.radians(dest[0]), math.radians(dest[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance_km = 6371 * c
    
    # Standard TIM/ICAO estimate: ~0.115 kg CO2 per passenger per km
    co2_kg = distance_km * 0.115 
    
    # Score out of 100 (Shorter flights = higher score. < 500km = 100, > 3000km = lower)
    flight_eco_score = max(10, 100 - ((distance_km - 500) / 30))
    
    return {
        "co2_kg": round(co2_kg),
        "distance_km": round(distance_km),
        "flight_eco_score": round(flight_eco_score)
    }



def run_travel_agent(keywords, budget, timing, duration="1 week"):
    # Parse inputs
    travel_date = parse_timing_to_date(timing)
    stay_days = parse_duration_to_days(duration)
    return_date = (datetime.strptime(travel_date, "%Y-%m-%d") + timedelta(days=stay_days)).strftime("%Y-%m-%d")
    
    # Extract numeric budget
    budget_numeric = float(re.sub(r"[^\d.]", "", budget)) if re.search(r"\d", budget) else 1500.0
    
    # --- 1. CACHE CHECK ---
    cache_key = f"{keywords} | {budget} | {timing} | {duration}"
    print(f"--- 🔍 Checking database memory for: {keywords}... ---")
    
    try:
        existing_search = supabase.table("searches").select("*").eq("query", cache_key).execute()
        if existing_search.data:
            print("✅ Found a match in history! Loading instantly (0 API cost)...")
            
            data = existing_search.data[0]['result']
            if isinstance(data, str):
                recommendations_json = json.loads(data)
            else:
                recommendations_json = data
            
            # [HYBRID CACHE]: Refresh flight prices (round-trip)
            print("--- ✈️ Fetching real flight prices from Tunis (TUN)... ---")
            for dest in recommendations_json.get("destinations", []):
                iata = dest.get("nearest_airport_iata")
                dep_date = dest.get("travel_date", travel_date)
                ret_date = dest.get("return_date", return_date)
                print(f"  Looking up round-trip flights to {iata} ({dep_date} → {ret_date})...")
                
                flight_info = get_flight_price_from_tun(iata, dep_date, ret_date)
                dest["flight_price_from_tun"] = flight_info["price"]
                
                # Recalculate budget split with fresh flight price
                flight_cost = flight_info["price_numeric"]
                remaining = max(0, budget_numeric - flight_cost)
                accom_share = remaining * 0.45
                living_share = remaining * 0.55
                dest["budget_breakdown"] = {
                    "total_budget": f"${budget_numeric:.0f}",
                    "flight_round_trip": flight_info["price"],
                    "accommodation_budget": f"${accom_share:.0f} ({stay_days} nights)",
                    "living_spending_budget": f"${living_share:.0f} ({stay_days} days)",
                    "daily_spending_limit": f"${living_share / max(stay_days, 1):.0f}/day"
                }
                
                flight_url = f"https://www.google.com/travel/flights?q=Flights%20to%20{iata}%20from%20TUN%20on%20{dep_date}%20through%20{ret_date}"
                dest["flight_booking_link"] = flight_url
                
                # Generate REAL hotel booking links
                city = dest["location"].split(",")[0].strip().replace(" ", "+")
                dest["hotel_booking_link"] = f"https://www.booking.com/searchresults.html?ss={city}&checkin={dep_date}&checkout={ret_date}&group_adults=1"
                dest["hotel_booking_link_alt"] = f"https://www.airbnb.com/s/{city}/homes?checkin={dep_date}&checkout={ret_date}&adults=1"
            return recommendations_json
            
    except Exception as e:
        print(f"⚠️ Cache check issue: {e}")

    # --- 2. RUN THE AI ---
    print(f"❌ No history found. 🛠️ Starting AI Research for {keywords} in {timing} ({duration})...")

    # Query Generation
    query_prompt = f"Convert these interests into one single, short search query (max 20 words): '{keywords}' budget {budget} for {timing}, staying {duration}."
    query_response = groq_request([
            {"role": "system", "content": "You are a search query generator. Output ONLY the search query. No chat, no explanations."},
            {"role": "user", "content": query_prompt}
        ])
    search_query = query_response.choices[0].message.content.strip()
    print(f"  Search query: {search_query}")

    # Web Search (destinations + hotels)
    print("--- 🌐 Searching the live web... ---")
    search_results = tavily_client.search(query=search_query, search_depth="advanced", max_results=10)
    context = "\n".join([r['content'] for r in search_results['results']])

    # --- 2B. REDDIT / SOCIAL SENTIMENT SEARCH ---
    print("--- 💬 Searching Reddit & travel forums for real traveler tips... ---")
    social_search = tavily_client.search(
        query=f"{search_query} daily budget street food cost of living tips",
        search_depth="advanced",
        max_results=10,
        include_domains=["reddit.com", "tripadvisor.com", "lonelyplanet.com", "nomadicmatt.com", "budgetyourtrip.com", "numbeo.com"]
    )
    social_context = "\n".join([r['content'] for r in social_search['results']])
    social_urls = "\n".join([f"- {r.get('title', '')}: {r.get('url', '')}" for r in social_search['results']])

    # Synthesis & JSON Formatting
    print("--- 🧠 Groq is analyzing data... ---")
    analysis_prompt = f"""
    You are a travel concierge AI. The user is flying FROM Tunis, Tunisia (TUN airport).
    
    DESTINATION & TRAVEL INFO:
    {context}
    
    REAL TRAVELER EXPERIENCES (Reddit, Forums, Budget Sites):
    {social_context}
    
    User Request: {keywords}
    Total Budget: {budget}
    Travel Period: {timing} (departure: {travel_date}, return: {return_date})
    Duration of Stay: {duration} ({stay_days} days)
    
    CRITICAL INSTRUCTIONS:
    1. Recommend 3 destinations. For each, provide the nearest major international airport IATA code.
    2. hotel_booking_link MUST be a REAL URL (booking.com, airbnb.com, etc.).
    3. Calculate daily_living_cost using real data from the context.
    4. SUSTAINABILITY: Give a 'local_eco_score' (1-100) based on walkability, public transit quality, and local green initiatives found in the text. 
    5. OVERTOURISM: Assess the 'crowd_level'. If the context mentions it's too crowded, suggest a quieter alternative nearby.
    6. HERITAGE: Identify 1 UNESCO World Heritage site or significant historical landmark near the destination. Provide a 'heritage_story' (1-2 sentences about why it matters).
    
    RETURN ONLY A JSON OBJECT. NO INTRO TEXT.
    
    Structure:
    {{
      "destinations": [
        {{
          "rank": 1,
          "location": "City, Country",
          "nearest_airport_iata": "XXX",
          "travel_date": "{travel_date}",
          "return_date": "{return_date}",
          "pitch": "One sentence why it matches keywords",
          "sustainability_metrics": {{
            "local_eco_score": 85,
            "green_rationale": "Highly walkable city with excellent electric train networks.",
            "crowd_level": "Low/Medium/High",
            "overtourism_warning": "If High, suggest an alternative here. Else, say 'Clear'."
          }},
          "daily_living_cost": {{
            "estimated_daily_spend": "$XX/day",
            "breakdown": "Street food $X, transport $X, activities $X per day"
          }},
          "reddit_sentiment": {{
            "overall_vibe": "What travelers say",
            "insider_tip": "One unique tip"
          }},
          "heritage_spotlight": {{
            "site_name": "Name of UNESCO site or landmark",
            "heritage_story": "1-2 sentences about its historical significance",
            "type": "UNESCO / Historical Landmark / Ancient Ruins"
          }}
        }}
      ]
    }}
    """

    final_output = groq_request(
        [{"role": "user", "content": analysis_prompt}],
        json_mode=True
    )
    
    recommendations_str = final_output.choices[0].message.content
    recommendations_json = json.loads(recommendations_str)

    # --- 3. FETCH REAL FLIGHT PRICES & CALCULATE ECO DATA ---
    print("--- ✈️ Fetching flight prices & calculating Carbon Footprint... ---")
    for dest in recommendations_json.get("destinations", []):
        iata = dest.get("nearest_airport_iata")
        dep_date = dest.get("travel_date", travel_date)
        ret_date = dest.get("return_date", return_date)
        
        # 1. Flight Prices
        flight_info = get_flight_price_from_tun(iata, dep_date, ret_date)
        dest["flight_price_from_tun"] = flight_info["price"]
        
        # 2. Emissions & Eco-Score (THE NEW ADDITION)
        emissions = estimate_flight_emissions(iata)
        dest["sustainability_metrics"]["flight_co2_kg"] = emissions["co2_kg"]
        
        # Blend AI's local eco-score with the Flight's eco-score
        local_score = dest["sustainability_metrics"].get("local_eco_score", 50)
        final_eco_score = int((local_score + emissions["flight_eco_score"]) / 2)
        dest["sustainability_metrics"]["total_eco_score"] = final_eco_score
        
        # 3. Budget Split
        flight_cost = flight_info["price_numeric"]
        remaining = max(0, budget_numeric - flight_cost)
        accom_share = remaining * 0.45
        living_share = remaining * 0.55
        
        dest["budget_breakdown"] = {
            "total_budget": f"${budget_numeric:.0f}",
            "flight_round_trip": flight_info["price"],
            "accommodation": f"${accom_share:.0f}", 
            "daily_limit": f"${living_share / max(stay_days, 1):.0f}/day" 
        }
        
        # Google Flights deep link (round-trip)
        flight_url = f"https://www.google.com/travel/flights?q=Flights%20from%20TUN%20to%20{iata}%20on%20{dep_date}%20return%20{ret_date}"
        dest["flight_booking_link"] = flight_url
        
        # Generate REAL hotel booking links (search pages that always work)
        city = dest["location"].split(",")[0].strip().replace(" ", "+")
        checkin = dep_date
        checkout = ret_date
        dest["hotel_booking_link"] = f"https://www.booking.com/searchresults.html?ss={city}&checkin={checkin}&checkout={checkout}&group_adults=1"
        dest["hotel_booking_link_alt"] = f"https://www.airbnb.com/s/{city}/homes?checkin={checkin}&checkout={checkout}&adults=1"

        # YouTube travel video
        location = dest.get("location", "")
        dest["local_video_url"] = get_local_youtube_video(location)

    # --- 4. SUPABASE LOGGING ---
    try:
        supabase.table("searches").insert({
            "query": cache_key, 
            "result": recommendations_json 
        }).execute()
        print("✅ New research saved to Supabase cache.")
    except Exception as e:
        print(f"⚠️ Could not save to Supabase: {e}")

    return recommendations_json


# --- TEST IT ---
if __name__ == "__main__":
    print("=" * 50)
    print("  ✈️  TRAVEL AI CONCIERGE  ✈️")
    print("  Flying from: Tunis, Tunisia (TUN)")
    print("=" * 50)
    
    keywords = input("\n🔍 What are you looking for? (e.g., nature, hiking, quiet monuments): ").strip()
    budget = input("💰 Total budget? (e.g., $1500): ").strip()
    timing = input("📅 When do you want to travel? (e.g., September 2026, next month): ").strip()
    duration = input("⏱️  How long is your stay? (e.g., 1 week, 3 days, a month): ").strip()
    
    if not keywords:
        keywords = "nature and culture"
    if not budget:
        budget = "$1500"
    if not timing:
        timing = "next month"
    if not duration:
        duration = "1 week"
    
    print(f"\n📋 Planning: {keywords} | Budget: {budget} | When: {timing} | Duration: {duration}\n")
    
    result = run_travel_agent(
        keywords=keywords,
        budget=budget,
        timing=timing,
        duration=duration
    )
    print("\n--- ✈️  FINAL RECOMMENDATIONS ---")
    print(json.dumps(result, indent=2))