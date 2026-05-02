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
    """Detects fee status using dynamic config labels[cite: 1]."""
    
    # Create reusable patterns from config[cite: 1]
    fee_p = '|'.join(FEE_LABELS)
    free_p = '|'.join(FREE_KEYWORDS)
    curr_p = '|'.join(CURRENCY_PREFIXES)

    # 1. Check explicitly for "Fee: Free" or "Yuran: Percuma"[cite: 1]
    if re.search(fr'({fee_p})\s*[:\-]\s*({free_p}|\d{{0}})', text, re.IGNORECASE):
        return "Free"
    
    # 2. Check for Free/Percuma anywhere if no Currency (RM) digits are found[cite: 1]
    if re.search(fr'\b({free_p})\b', text, re.IGNORECASE) and not re.search(fr'{curr_p}\s*[1-9]', text, re.IGNORECASE):
        return "Free"

    # 3. Look for Currency followed by numbers, or Paid fee labels[cite: 1]
    if re.search(fr'{curr_p}\s*[1-9]+', text, re.IGNORECASE) or \
       re.search(fr'({fee_p})\s*[:\-]\s*(?!{free_p}|0)', text, re.IGNORECASE):
        return "Paid"
        
    return "Free"

def check_mycsd(text):
    return bool(re.search(r'mycsd', text, re.IGNORECASE))