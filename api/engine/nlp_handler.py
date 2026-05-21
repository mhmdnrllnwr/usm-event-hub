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

def rank_title_candidates(raw_text):
    """Score title candidates from raw text. Returns list of (line, score) sorted desc."""
    raw_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    scored = []

    for i, raw_line in enumerate(raw_lines[:3]):
        norm_line = unicodedata.normalize('NFKC', raw_line)
        if len(norm_line.split()) <= 1:
            continue
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

        scored.append((norm_line, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def identify_title_heuristically(raw_text):
    """Improved Heuristic Scoring for Titles."""
    scored = rank_title_candidates(raw_text)

    if not scored:
        return "Untitled Event"

    best_line, best_score = scored[0]

    if best_score > 0:
        # Clean styling symbols[cite: 1]
        return re.sub(r'^[\*\[\]【】]+|[\*\[\]【】]+$', '', best_line).strip()
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
    
    candidates = rank_title_candidates(raw_text)

    entities = {
        "title": identify_title_heuristically(raw_text),
        "title_candidates": [line for line, _ in candidates],
        "title_scores": [score for _, score in candidates],
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
                # Only keep if contains month-like word (3+ alpha). Filters garbage like "11 31"
                if re.search(r'[A-Za-z]{3,}', ent.text):
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

    # General date pattern fallback for formats like "19 Mei 2026", "11–31 Mei 2026", 🗓 emoji lines
    if not entities["date_spacy"]:
        for line in raw_text.split('\n'):
            # Check for date range first: "11–31 Mei 2026", "11-31 May 2026"
            range_match = re.search(r'(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})', line)
            if range_match:
                start = f"{range_match.group(1)} {range_match.group(3)} {range_match.group(4)}"
                end = f"{range_match.group(2)} {range_match.group(3)} {range_match.group(4)}"
                entities["date_spacy"] = [start, end]
                break
            # Then check for single date: "19 Mei 2026"
            dates = re.findall(r'\b(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})\b', line)
            if dates:
                formatted = [f"{d} {m} {y}" for d, m, y in dates]
                entities["date_spacy"] = [formatted[0]]
                if len(formatted) > 1:
                    entities["date_spacy"].append(formatted[1])
                break

    # General time pattern fallback for formats like "8.00PM", "10:30 AM", 🕒 emoji lines
    if not entities["time_spacy"]:
        for line in raw_text.split('\n'):
            times = re.findall(r'(\d{1,2}[\.:]\d{2}\s*(?:AM|PM|am|pm))', line)
            if len(times) >= 2:
                entities["time_spacy"] = [times[0].strip(), times[1].strip()]
                break
            elif times:
                entities["time_spacy"] = [times[0].strip()]
                break

    return entities