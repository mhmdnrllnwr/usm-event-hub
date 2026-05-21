import re
from dateparser.search import search_dates
from .config import CURRENCY_PREFIXES, FEE_LABELS, FREE_KEYWORDS

def extract_links(text):
    url_pattern = r'https?://[^\s]+'
    links = re.findall(url_pattern, text)
    return [link.rstrip('.,!?)') for link in links]

def extract_dates_and_times(text):
    """
    Extracts dates and times using dateparser instead of custom regex.
    `search_dates` returns a list of tuples: (substring, datetime_obj)
    """
    
    found_dates = search_dates(text)
    dates_extracted = []
    if found_dates:
        for substring, obj in found_dates:
            dates_extracted.append(substring)
    return dates_extracted

def extract_dates(text):
    # Backward compatibility, or can just use extract_dates_and_times directly
    return extract_dates_and_times(text)

def extract_times(text):
    # dateparser handles both dates and times together if found
    return extract_dates_and_times(text)


def extract_fee(text):
    """Detects fee status using safe regex escaping and prioritized logic."""
    
    # Use re.escape to handle symbols like '$' safely
    fee_p = '|'.join(map(re.escape, FEE_LABELS))
    free_p = '|'.join(map(re.escape, FREE_KEYWORDS))
    curr_p = '|'.join(map(re.escape, CURRENCY_PREFIXES))

    # 1. PRIORITY: If we see a currency followed by a number > 0, it's PAID
    # Example: "RM 10" or "$5"
    if re.search(fr'({curr_p})\s*[1-9]\d*', text, re.IGNORECASE):
        return "Paid"

    # 2. Check for explicit "Fee: Free" or "Yuran: Percuma"
    if re.search(fr'({fee_p})\s*[:\-]\s*({free_p})', text, re.IGNORECASE):
        return "Free"
    
    # 3. Check for Free/Percuma anywhere if no price was found in Step 1[cite: 1]
    if re.search(fr'\b({free_p})\b', text, re.IGNORECASE):
        return "Free"

    # 4. Check for Paid labels with no price yet found[cite: 1]
    # Example: "Fee: Paid" or "Bayaran: Dibutuhkan"
    if re.search(fr'({fee_p})\s*[:\-]\s*(?!{free_p}|0)', text, re.IGNORECASE):
        return "Paid"

    return "Free"

def check_mycsd(text):
    return bool(re.search(r'mycsd', text, re.IGNORECASE))