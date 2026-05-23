import spacy, unicodedata, re

nlp = spacy.load("en_core_web_sm")

text = '\U0001f5d3️ 21 May 2026'
cleaned = unicodedata.normalize('NFKC', text)
cleaned2 = re.sub(r'[^\w\s\-\:\.\/]', ' ', cleaned)

print(f"Original: {text!r}")
print(f"Cleaned:  {cleaned2!r}")

doc = nlp(cleaned2)
for ent in doc.ents:
    print(f"  spaCy: {ent.text!r} label={ent.label_}")

# Also test what user's text looks like after cleaning
full_text = (
    '\U0001f399️ "People may forget what you said, but they will never forget how you made them feel." \U0001f399️\n\n'
    'Want your presentations to be memorable, powerful, and captivating?\n\n'
    'Join us for \U0001f525 *CREATIVE STRATEGIES FOR DYNAMIC PRESENTATION* \U0001f525\n\n'
    "An exclusive online session where you’ll learn how to speak with confidence, creativity, and impact.\n\n"
    '\U0001f5d3️ 21 May 2026\n'
    '⏰ 8:00 PM – 10:00 PM\n'
    '\U0001f4bb Cisco Webex\n'
    '\U0001f4b0 Fee: Only RM1\n'
    '✅ MYCSD will be provided'
)
clean_full = unicodedata.normalize('NFKC', full_text)
clean_full2 = re.sub(r'[^\w\s\-\:\.\/]', ' ', clean_full)
doc2 = nlp(clean_full2)
print("\n=== Full text spaCy DATE entities ===")
for ent in doc2.ents:
    if ent.label_ == "DATE":
        print(f"  {ent.text!r}")
