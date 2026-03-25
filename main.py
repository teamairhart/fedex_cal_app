"""
FedEx Calendar App — CLI
------------------------
Reads `schedule.txt`, parses BRF→Activity→DBRF blocks, and outputs an `.ics` file.

Usage:
1. Paste your schedule text into `schedule.txt`
2. Run: `python main.py`
"""

from helpers import DEFAULT_TZ, parse_schedule, generate_ics

try:
    with open("schedule.txt", "r", encoding="utf-8") as file:
        schedule_text = file.read()

    exclude_names = []  # Add names to exclude here if needed
    events = parse_schedule(schedule_text, exclude_names)

    if not events:
        print("❌ No events found in schedule.txt")
        raise SystemExit(1)

    filename, cal = generate_ics(events)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(cal.serialize())

    print(f"✅ ICS file created: {filename}")
    print(f"📅 Found {len(events)} events | TZ={DEFAULT_TZ}")

except FileNotFoundError:
    print("❌ schedule.txt not found. Please create this file with your schedule text.")
except Exception as e:
    print(f"❌ Error: {str(e)}")
