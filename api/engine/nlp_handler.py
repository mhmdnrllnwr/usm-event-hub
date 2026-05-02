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
    
    # Process text with spaCy NER
    doc = nlp(text)
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    entities = {
        "title": "Untitled Event", 
        "venue": "Online",
        "organizer": None,
        "date_spacy": [],
        "time_spacy": []
    }
    
    # Extract entities using spaCy
    for ent in doc.ents:
        if ent.label_ in ["FAC", "LOC"]:
            entities["venue"] = ent.text
        elif ent.label_ == "ORG":
            # Taking the first ORG as organizer usually works, or gather them
            if not entities["organizer"]:
                entities["organizer"] = ent.text
        elif ent.label_ == "DATE":
            entities["date_spacy"].append(ent.text)
        elif ent.label_ == "TIME":
            entities["time_spacy"].append(ent.text)

    # 2. STRATEGY: Heuristic Scoring Method
    # Evaluate the first 3 non-empty lines using specific scoring rules
    raw_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    best_score = -999
    best_title = "Untitled Event"

    for i, raw_line in enumerate(raw_lines[:3]):
        # Normalize line
        norm_line = unicodedata.normalize('NFKC', raw_line)
        score = 0
        
        # Line Position
        if i == 0:
            score += 2
        elif i == 1:
            score += 1
            
        # Brackets: Does the line start and end with [ and ] or 【 and 】?
        if (norm_line.startswith('[') and norm_line.endswith(']')) or \
           (norm_line.startswith('【') and norm_line.endswith('】')):
            score += 5
            
        # Bold Wrap: Is the line wrapped in * or **?
        if (norm_line.startswith('**') and norm_line.endswith('**')) or (norm_line.startswith('*') and norm_line.endswith('*') and not norm_line.startswith('**')):
            score += 3
            
        # All Caps: Is the line > 80% uppercase?
        # Temporarily removing symbols to calculate uppercase density
        alpha_chars = [c for c in norm_line if c.isalpha()]
        if alpha_chars:
            upper_density = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_density > 0.8:
                score += 2
                
        # Negative Keywords
        lower_line = norm_line.lower()
        if any(bad in lower_line for bad in ["days to go", "ready to", "join us"]):
            score -= 10
            
        # Give preference to highest score, ensure it's at least a valid phrase
        if score > best_score and len(norm_line.split()) > 1:
            best_score = score
            best_title = norm_line

    if best_score > 0 and best_title != "Untitled Event":
        # Clean title styling before assigning (removes *, [, ], 【, 】)
        entities["title"] = re.sub(r'^[\*\[\]【】]+|[\*\[\]【】]+$', '', best_title).strip()

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

    # 5. FALLBACK: Venue, Date, Time keyword extraction
    for line in raw_text.split('\n'):
        norm_kw_line = unicodedata.normalize('NFKC', line)
        
        # Venue Extraction
        if entities["venue"] == "Online" and re.search(r'(venue|tempat|lokasi|platform)\s*[:\-]', norm_kw_line, re.IGNORECASE):
            venue_match = re.split(r'(venue|tempat|lokasi|platform)\s*[:\-]', norm_kw_line, maxsplit=1, flags=re.IGNORECASE)
            if len(venue_match) > 2:
                potential_venue = venue_match[2].strip()
                potential_venue = re.sub(r'^[^\w\s\'\"\(\)]+', '', potential_venue).strip()
                if potential_venue:
                    entities["venue"] = potential_venue
                    
        # Date Extraction using labels
        if re.search(r'(date|tarikh|hari|period|tempoh)\s*[:\-]', norm_kw_line, re.IGNORECASE):
            date_match = re.split(r'(date|tarikh|hari|period|tempoh)\s*[:\-]', norm_kw_line, maxsplit=1, flags=re.IGNORECASE)
            if len(date_match) > 2:
                val = date_match[2].strip()
                val = re.sub(r'^[^\w\s]+', '', val).strip()
                if val:
                    val = re.sub(r'[-–—]', '-', val)
                    # Support splitting fully formed date ranges directly in NLP
                    if re.search(r'\s+(to|hingga)\s+', val, re.IGNORECASE):
                        parts = re.split(r'\s+(?:to|hingga)\s+', val, flags=re.IGNORECASE)
                        entities["date_spacy"].insert(0, f"{parts[0].strip()} hingga {parts[1].strip()}")
                    elif "-" in val:
                        parts = val.split("-")
                        # Only symmetric split if both sides are likely dates (not "15-20 Nov")
                        if len(parts[0].split()) > 1 and len(parts[1].split()) > 1:
                            entities["date_spacy"].insert(0, f"{parts[0].strip()} hingga {parts[1].strip()}")
                        else:
                            entities["date_spacy"].insert(0, val)
                    else:
                        entities["date_spacy"].insert(0, val)
                    
        # Time Extraction using labels
        if re.search(r'(time|masa|waktu)\s*[:\-]', norm_kw_line, re.IGNORECASE):
            time_match = re.split(r'(time|masa|waktu)\s*[:\-]', norm_kw_line, maxsplit=1, flags=re.IGNORECASE)
            if len(time_match) > 2:
                val = time_match[2].strip()
                val = re.sub(r'^[^\w\s]+', '', val).strip()
                if val:
                    # Normalize various dash formats to standard hyphen
                    val = re.sub(r'[-–—]', '-', val)
                    # Split range strings if "to" or "-" or "hingga" is clearly used
                    if re.search(r'\s+(to|hingga)\s+', val, re.IGNORECASE):
                        parts = re.split(r'\s+(?:to|hingga)\s+', val, flags=re.IGNORECASE)
                        entities["time_spacy"] = [parts[0].strip(), parts[1].strip()] + entities["time_spacy"]
                    elif "-" in val:
                        parts = val.split("-")
                        entities["time_spacy"] = [parts[0].strip(), parts[1].strip()] + entities["time_spacy"]
                    else:
                        entities["time_spacy"].insert(0, val)

    return entities