import spacy
import unicodedata
import re

nlp = spacy.load("en_core_web_sm")

def normalize_and_clean(text):
    """Converts fancy fonts to normal text and removes noise."""
    # Step 1: Normalize Unicode (Bold -> Normal)
    text = unicodedata.normalize('NFKC', text)
    # Step 2: Remove emojis/symbols that break upper-case detection
    # This keeps only alphanumeric, spaces, and basic punctuation
    text = re.sub(r'[^\w\s\-\:\.\/]', ' ', text)
    return text

def extract_entities(raw_text):
    # 1. Prepare the text
    clean_text = normalize_and_clean(raw_text)
    
    entities = {
        "title": "Untitled Event",
        "venue": "Online"
    }

    # 2. THE SHOUT HUNTER: Find the longest ALL CAPS phrase
    # This looks for sequences of words that are ALL CAPS and at least 3 words long
    caps_patterns = re.findall(r'\b[A-Z\s]{10,}\b', clean_text)
    if caps_patterns:
        # Pick the longest one found, as it's usually the main title
        best_match = max(caps_patterns, key=len).strip()
        # Clean up any double spaces caused by emoji removal
        entities["title"] = " ".join(best_match.split())

    # 3. VENUE Extraction (Explicit search)
    for line in clean_text.split('\n'):
        l_lower = line.lower()
        if any(key in l_lower for key in ["platform:", "venue:", "location:"]):
            entities["venue"] = line.split(":", 1)[1].strip()
            break
            
    # 4. FALLBACK: If no 'Shout' found, use the old keyword logic
    if entities["title"] == "Untitled Event":
        keywords = ["workshop", "talk", "seminar", "competition", "program"]
        for line in clean_text.split('\n'):
            if any(k in line.lower() for k in keywords):
                entities["title"] = line.strip()[:100]
                break

    return entities