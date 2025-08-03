"""
FedEx Calendar App
------------------
This script reads a copied FedEx training schedule from a text file (`schedule.txt`),
parses the schedule into individual BRF→DBRF event blocks, and outputs a properly
formatted `.ics` calendar file that can be imported into Apple Calendar or any
calendar app.

Features:
✅ Groups training blocks (BRF → DBRF) into one event
✅ Extracts main activity (e.g., AST 1, LOE, etc.)
✅ Extracts the correct facility code (e.g., B76FPT1)
✅ Adds crew names (CA, FO, SUPPORT) as event notes
✅ Always outputs events in Central Time (America/Chicago)
✅ Creates file: training_schedule_YYYY-MM.ics

Dependencies:
- Python 3.9+ (because it uses `zoneinfo`)
- The `ics` library (`pip install ics`)

Usage:
1. Paste your schedule text into `schedule.txt`
2. Run: `python main.py`
3. Import the generated `.ics` file into your calendar
"""

from helpers import parse_schedule, generate_ics

try:
    with open("schedule.txt", "r") as file:
        schedule_text = file.read()
    
    # Parse with configurable excluded names
    exclude_names = ["Jonathan", "Airhart"]  # Add your name here
    events = parse_schedule(schedule_text, exclude_names)
    
    if not events:
        print("❌ No events found in schedule.txt")
        exit(1)
    
    # Generate ICS file
    filename, cal = generate_ics(events)
    
    with open(filename, "w") as f:
        f.writelines(cal)
    
    print(f"✅ ICS file created: {filename}")
    print(f"📅 Found {len(events)} events")

except FileNotFoundError:
    print("❌ schedule.txt not found. Please create this file with your schedule text.")
except Exception as e:
    print(f"❌ Error: {str(e)}")
