import re
import dateparser

def extract_links(text):
    url_pattern = r'https?://[^\s]+'
    links = re.findall(url_pattern, text)
    return [link.rstrip('.,!?)') for link in links]

def extract_dates_and_times(text):
    """
    Extracts dates and times using dateparser instead of custom regex.
    `search_dates` returns a list of tuples: (substring, datetime_obj)
    """
    from dateparser.search import search_dates
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
    # Check explicitly for "Free" or "Percuma" labels attached to fee/yuran words
    if re.search(r'(fee|yuran pendaftaran|yuran|bayaran)\s*[:\-]\s*(free|percuma|\d{0})', text, re.IGNORECASE):
        return "Free"
    
    # Check explicitly for Free/Percuma anywhere in the text if no RM digits found
    if re.search(r'\b(percuma|free)\b', text, re.IGNORECASE) and not re.search(r'RM\s*[1-9]', text, re.IGNORECASE):
        return "Free"

    # Looks for 'RM' followed by numbers greater than 0, or Paid fee labels
    if re.search(r'RM\s*[1-9]+', text, re.IGNORECASE) or re.search(r'(fee|yuran pendaftaran|yuran)\s*[:\-]\s*(?!free|percuma|0)', text, re.IGNORECASE):
        return "Paid"
        
    return "Free"

def check_mycsd(text):
    return bool(re.search(r'mycsd', text, re.IGNORECASE))