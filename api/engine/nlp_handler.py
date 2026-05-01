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
# 1. Normalize (Bold -> Normal)
    text = normalize_and_clean(raw_text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    entities = {"title": "Untitled Event", "venue": "Online"}

    # 2. STRATEGY: Prioritize the first meaningful line
    # We skip lines that are just greetings or too short
    greetings = ["greetings", "hello", "hi", "assalam", "selamat"]
    
    for line in lines[:3]: # Check only the top 3 lines
        lower_line = line.lower()
        # Skip if it's a greeting
        if any(greet in lower_line for greet in greetings):
            continue
        # Skip if it's just an emoji or single word
        if len(line.split()) < 2:
            continue
        
        entities["title"] = line
        break

    # 3. FALLBACK: Shout Hunter (if the first line doesn't look like a title)
    if entities["title"] == "Untitled Event":
        caps_patterns = re.findall(r'\b[A-Z\s]{10,}\b', text)
        if caps_patterns:
            entities["title"] = max(caps_patterns, key=len).strip()
            
    # 4. FALLBACK: If no 'Shout' found, use the old keyword logic
    if entities["title"] == "Untitled Event":
        keywords = ["workshop", "talk", "seminar", "competition", "program"]
        for line in text.split('\n'):
            if any(k in line.lower() for k in keywords):
                entities["title"] = line.strip()[:100]
                break

    return entities