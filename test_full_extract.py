import asyncio, json
from engine.nlp_handler import extract_entities
from engine.regex_handler import extract_links, extract_fee, check_mycsd
from engine.config import DEEPSEEK_API_KEY_ENV
import os, unicodedata

text = (
    '\U0001f399️ "People may forget what you said, but they will never forget how you made them feel." \U0001f399️\n\n'
    'Want your presentations to be memorable, powerful, and captivating?\n\n'
    'Join us for \U0001f525 *CREATIVE STRATEGIES FOR DYNAMIC PRESENTATION* \U0001f525\n\n'
    "An exclusive online session where you’ll learn how to speak with confidence, creativity, and impact.\n\n"
    '\U0001f5d3️ 21 May 2026\n'
    '⏰ 8:00 PM – 10:00 PM\n'
    '\U0001f4bb Cisco Webex\n'
    '\U0001f4b0 Fee: Only RM1\n'
    '✅ MYCSD will be provided\n\n'
    'This is your chance to master the art of powerful presentations and leave a lasting impression every time you speak!\n\n'
    'Secure your spot now \U0001f447\n'
    '\U0001f517https://forms.gle/js29UVT6eSyQbbf57\n\n'
    'For any enquiries:\n'
    '☎️ Alwinder Singh (017-5100 557)\n'
    '☎️ Herinder Kaur (019-552 3652)'
)

norm = unicodedata.normalize('NFKC', text)

print("=== NLP EXTRACTION ===")
nlp_results = extract_entities(norm)
print(f"title: {nlp_results['title']!r}")
print(f"date_spacy: {nlp_results['date_spacy']!r}")
print(f"time_spacy: {nlp_results['time_spacy']!r}")
print(f"venue: {nlp_results['venue']!r}")
print(f"title_scores: {nlp_results['title_scores']}")
print(f"title_candidates: {nlp_results['title_candidates']}")

print("\n=== REGEX ===")
links = extract_links(norm)
print(f"links: {links}")
print(f"fee: {extract_fee(norm)}")
print(f"mycsd: {check_mycsd(norm)}")

print("\n=== KEY CHECK ===")
dates = nlp_results.get("date_spacy", [])
times = nlp_results.get("time_spacy", [])
print(f"dates empty? {not dates}")
print(f"times empty? {not times}")
print(f"AI trigger? {(not dates) or (not times)}")
print(f"DEEPSEEK_API_KEY set: {bool(os.getenv('DEEPSEEK_API_KEY'))}")
