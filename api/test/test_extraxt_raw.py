import sys
import os
import json

# 1. SETUP PATHS
# Ensures that 'api' is treated as a package regardless of where you run the script
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. IMPORT REAL LOGIC
from api.engine.nlp_handler import extract_entities, normalize_and_clean
from api.engine.regex_handler import (
    extract_links, extract_dates, extract_times, extract_fee, check_mycsd
)

def process_to_model(raw_text):
    """
    Mimics the logic that should live in your FastAPI POST route.
    Maps disparate engine results into the MongoDB Schema.
    """
    # Pre-processing
    clean_text = normalize_and_clean(raw_text)
    
    # Run Engines
    nlp = extract_entities(clean_text)
    links = extract_links(clean_text)
    
    # --- Date Logic ---
    # Fallback to regex if NLP misses it
    dates = nlp.get("date_spacy") or extract_dates(clean_text)
    start_date = dates[0] if dates else "TBD"
    end_date = dates[-1] if dates else start_date

    # --- Time Logic ---
    times = nlp.get("time_spacy") or extract_times(clean_text)
    # Clean noise like '\n Platform' from strings
    start_time = times[0].split('\n')[0].strip() if times else "TBD"
    end_time = times[-1].split('\n')[0].strip() if times else start_time

    # --- Fee Logic (Prioritize RM value) ---
    fee_val = extract_fee(clean_text)
    
    # Constructing the object to match your 'Real Output'
    return {
        "title": nlp.get("title", "Untitled Event").strip(),
        "image_url": None, # Downloaded by bot, usually null initially
        "start_date": start_date,
        "end_date": end_date,
        "start_time": start_time,
        "end_time": end_time,
        "venue": nlp.get("venue", "TBD").split('\n')[0].strip(),
        "fee": fee_val,
        "registration_link": links[0] if links else "None found",
        "has_mycsd": check_mycsd(clean_text),
    }

# 3. INTERACTIVE TERMINAL HANDLER
if __name__ == "__main__":
    print("--- USM Event Hub: Extraction Engine Test ---")
    print("Paste raw Telegram message and press Ctrl+Z (Win) or Ctrl+D (Mac/Unix):")
    print("-" * 50)
    
    try:
        user_input = sys.stdin.read()
        if user_input.strip():
            final_data = process_to_model(user_input)
            
            print("\n🚀 FINAL MAPPED OUTPUT (Ready for MongoDB):")
            print(json.dumps(final_data, indent=4))
        else:
            print("Error: Empty input.")
    except Exception as e:
        print(f"Extraction Error: {e}")

        