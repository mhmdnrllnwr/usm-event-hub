import re

def extract_links(text):
    url_pattern = r'https?://[^\s]+'
    links = re.findall(url_pattern, text)
    return [link.rstrip('.,!?)') for link in links]

def extract_dates(text):
    # Added (\d{1,2}(?:st|nd|rd|th)?) to catch "17th" or "2nd"
    date_pattern = r'(\d{1,2}(?:st|nd|rd|th|(?:\-\d{1,2}))?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{2,4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
    return re.findall(date_pattern, text, re.IGNORECASE)

def extract_times(text):
    # Improved to handle PM/AM stuck to the numbers (e.g., 8:00PM)
    time_pattern = r'\d{1,2}(?::\d{2})?\s?(?:[AaPp]\.?[Mm]\.?)'
    return re.findall(time_pattern, text, re.IGNORECASE)

def extract_fee(text):
    # Looks for 'RM' followed by numbers. If found, it's paid.
    if re.search(r'RM\s*\d+', text, re.IGNORECASE):
        return "Paid"
    return "Free"

def check_mycsd(text):
    return bool(re.search(r'mycsd', text, re.IGNORECASE))