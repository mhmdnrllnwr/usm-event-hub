import re

def extract_links(text):
    url_pattern = r'https?://[^\s]+'
    links = re.findall(url_pattern, text)
    return [link.rstrip('.,!?)') for link in links]

def extract_dates(text):
    # Matches DD/MM/YYYY OR DDth Month YYYY (e.g., 9th March 2025)
    date_pattern = r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{2,4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
    return re.findall(date_pattern, text, re.IGNORECASE)

def extract_times(text):
    # Grabs all times like 8:00 PM or 9:30 PM
    time_pattern = r'\d{1,2}(?::\d{2})?\s?(?:AM|PM|am|pm)'
    return re.findall(time_pattern, text, re.IGNORECASE)

def extract_fee(text):
    # Looks for 'RM' followed by numbers. If found, it's paid.
    if re.search(r'RM\s*\d+', text, re.IGNORECASE):
        return "Paid"
    return "Free"

def check_mycsd(text):
    return bool(re.search(r'mycsd', text, re.IGNORECASE))