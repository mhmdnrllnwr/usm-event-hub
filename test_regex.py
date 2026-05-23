import unicodedata, re, sys

# Exact text from user's DB raw_text — uses actual emoji chars
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

norm = unicodedata.normalize("NFKC", text)

print("=== EMOJI CHARS IN TEXT ===")
for i, ch in enumerate(text):
    if ord(ch) > 127:
        print(f"  pos={i} U+{ord(ch):04X} repr={ch!r} category={unicodedata.category(ch)}")

print("\n=== LINE SPLIT ===")
lines = text.split("\n")
for i, line in enumerate(lines):
    print(f"  line {i}: {line!r}")

print("\n=== DATE REGEX (general fallback) ===")
pat = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})\b")
for i, line in enumerate(lines):
    matches = pat.findall(line)
    if matches:
        print(f"  line {i} MATCH: {matches}")
    else:
        preview = line[:60]
        print(f"  line {i}: no match ({preview!r})")

print("\n=== TIME REGEX (general fallback) ===")
pat2 = re.compile(r"(\d{1,2}[\.:]\d{2}\s*(?:AM|PM|am|pm))")
for i, line in enumerate(lines):
    matches = pat2.findall(line)
    if matches:
        print(f"  line {i} MATCH: {matches}")

print("\n=== SPA-CY CLEANED TEXT ===")
cleaned = unicodedata.normalize('NFKC', text)
cleaned = re.sub(r'[^\w\s\-\:\.\/]', ' ', cleaned)
print(repr(cleaned[:200]))

print("\n=== DONE ===")
