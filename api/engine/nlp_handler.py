import spacy
import unicodedata
import re
from .config import NEGATIVE_TITLE_KEYWORDS, VENUE_KEYWORDS
from .config import VENUE_LABELS,VENUE_KEYWORDS, DATE_LABELS, TIME_LABELS

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except:
    nlp = None

def normalize_and_clean(text):
    """Converts fancy fonts to normal text and removes noise."""
    text = unicodedata.normalize('NFKC', text)
    # Removes emojis/symbols that break uppercase detection
    text = re.sub(r'[^\w\s\-\:\.\/]', ' ', text)
    return text

def identify_title_heuristically(raw_text):
    """Improved Heuristic Scoring for Titles."""
    raw_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    best_score = -999
    best_title = "Untitled Event"

    for i, raw_line in enumerate(raw_lines[:3]):
        norm_line = unicodedata.normalize('NFKC', raw_line)
        score = 0
        
        # Position Weight[cite: 1]
        if i == 0: score += 2
        elif i == 1: score += 1
            
        # Brackets Scoring[cite: 1]
        if (norm_line.startswith('[') and norm_line.endswith(']')) or \
           (norm_line.startswith('【') and norm_line.endswith('】')):
            score += 5
            
        # Bold Wrap Scoring[cite: 1]
        if (norm_line.startswith('**') and norm_line.endswith('**')) or \
           (norm_line.startswith('*') and norm_line.endswith('*')):
            score += 3
            
        # All Caps Density[cite: 1]
        alpha_chars = [c for c in norm_line if c.isalpha()]
        if alpha_chars:
            upper_density = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_density > 0.8: score += 2
                
        # Negative Keywords Filter (from Config)
        if any(bad in norm_line.lower() for bad in NEGATIVE_TITLE_KEYWORDS):
            score -= 15
            
        if score > best_score and len(norm_line.split()) > 1:
            best_score = score
            best_title = norm_line

    if best_score > 0:
        # Clean styling symbols[cite: 1]
        return re.sub(r'^[\*\[\]【】]+|[\*\[\]【】]+$', '', best_title).strip()
    return "Untitled Event"

def resolve_venue(extracted_venue, raw_text):
    """Improved Venue logic using dynamic config labels."""
    text_lower = raw_text.lower()
    
    # 1. Check for explicit Venue labels (Venue, Tempat, etc.)
    venue_pattern = r'(?:' + '|'.join(VENUE_LABELS) + r'):\s*([^\n]+)'
    prefix_match = re.search(venue_pattern, raw_text, re.IGNORECASE)
    if prefix_match:
        return prefix_match.group(1).strip().split('\n')[0]

    # 2. Check Online Keywords
    for platform in VENUE_KEYWORDS["online"]:
        if platform in text_lower:
            return platform.title()

    # 3. Filter out MyCSD noise from NLP guess
    if any(bad in extracted_venue.lower() for bad in VENUE_KEYWORDS["ignore_list"]):
        extracted_venue = "Online"

    # 4. Clean specific building indicators[cite: 1]
    if any(ind in extracted_venue.lower() for ind in VENUE_KEYWORDS["physical_indicators"]):
        return extracted_venue.split('\n')[0].strip()

    return extracted_venue

def extract_entities(raw_text):
    text = normalize_and_clean(raw_text)
    doc = nlp(text) if nlp else None
    
    entities = {
        "title": identify_title_heuristically(raw_text), 
        "venue": "Online",
        "organizer": None,
        "date_spacy": [],
        "time_spacy": []
    }
    
    # Standard spaCy extraction[cite: 1]
    if doc:
        for ent in doc.ents:
            if ent.label_ in ["FAC", "LOC", "GPE"]:
                entities["venue"] = ent.text
            elif ent.label_ == "ORG" and not entities["organizer"]:
                entities["organizer"] = ent.text
            elif ent.label_ == "DATE":
                entities["date_spacy"].append(ent.text)
            elif ent.label_ == "TIME":
                entities["time_spacy"].append(ent.text)

    # Apply Venue Resolver
    entities["venue"] = resolve_venue(entities["venue"], text)

    # 5. REVERTED DATETIME FALLBACK (From v1)[cite: 1]
    for line in raw_text.split('\n'):
        norm_kw_line = unicodedata.normalize('NFKC', line)
        
        # Date Extraction using labels[cite: 1]
        if re.search(r'(date|tarikh|hari|period|tempoh)\s*[:\-]', norm_kw_line, re.IGNORECASE):
            date_match = re.split(r'(date|tarikh|hari|period|tempoh)\s*[:\-]', norm_kw_line, maxsplit=1, flags=re.IGNORECASE)
            if len(date_match) > 2:
                val = re.sub(r'^[^\w\s]+', '', date_match[2].strip()).strip()
                if val:
                    val = re.sub(r'[-–—]', '-', val)
                    if re.search(r'\s+(to|hingga)\s+', val, re.IGNORECASE):
                        parts = re.split(r'\s+(?:to|hingga)\s+', val, flags=re.IGNORECASE)
                        entities["date_spacy"].insert(0, f"{parts[0].strip()} hingga {parts[1].strip()}")
                    else:
                        entities["date_spacy"].insert(0, val)
                    
        # Time Extraction using labels[cite: 1]
        if re.search(r'(time|masa|waktu)\s*[:\-]', norm_kw_line, re.IGNORECASE):
            time_match = re.split(r'(time|masa|waktu)\s*[:\-]', norm_kw_line, maxsplit=1, flags=re.IGNORECASE)
            if len(time_match) > 2:
                val = re.sub(r'^[^\w\s]+', '', time_match[2].strip()).strip()
                if val:
                    val = re.sub(r'[-–—]', '-', val)
                    if re.search(r'\s+(to|hingga)\s+', val, re.IGNORECASE):
                        parts = re.split(r'\s+(?:to|hingga)\s+', val, flags=re.IGNORECASE)
                        entities["time_spacy"] = [parts[0].strip(), parts[1].strip()] + entities["time_spacy"]
                    elif "-" in val:
                        parts = val.split("-")
                        entities["time_spacy"] = [parts[0].strip(), parts[1].strip()] + entities["time_spacy"]
                    else:
                        entities["time_spacy"].insert(0, val)

    return entities