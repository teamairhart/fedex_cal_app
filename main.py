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

import re
from datetime import datetime
from zoneinfo import ZoneInfo  # Built-in timezone support
from ics import Calendar, Event  # Library to generate ICS files

# -----------------------------------------------------------
# STEP 1: Load the schedule text from file
# -----------------------------------------------------------
with open("schedule.txt", "r") as file:
    lines = file.read().splitlines()  # Split by lines for easier parsing

# -----------------------------------------------------------
# STEP 2: Define regex patterns to match schedule rows
# -----------------------------------------------------------

# This pattern matches lines WITH the day and date at the start:
# Example: "Thu 28AUG25 06:00L / 08:00L BRF"
pattern_full = r"([A-Z][a-z]{2})\s+(\d{2}[A-Z]{3}\d{2})\s+(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)\s+([A-Z0-9\-]+(?:\s[0-9])?)"

# This pattern matches lines WITHOUT day/date (they continue the same block):
# Example: "08:00L / 12:00L AST 1"
pattern_partial = r"(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)\s+([A-Z0-9\-]+(?:\s[0-9])?)"

matches = []          # List of all rows we find
current_day = None    # Keep track of last seen day
current_date = None   # Keep track of last seen date

# -----------------------------------------------------------
# STEP 3: Go through each line and capture schedule rows
# -----------------------------------------------------------
for line in lines:
    m_full = re.search(pattern_full, line)
    m_part = re.search(pattern_partial, line)

    if m_full:
        # If the line has day+date, update current_day/date
        current_day, current_date, start, end, activity = m_full.groups()
        matches.append((current_day, current_date, start, end, activity))
    elif m_part and current_day and current_date:
        # If line doesn't have day+date, use the last saved ones
        start, end, activity = m_part.groups()
        matches.append((current_day, current_date, start, end, activity))

# -----------------------------------------------------------
# STEP 4: Group rows into event blocks (BRF → DBRF)
# -----------------------------------------------------------
blocks = []       # Each block is a list of rows for that event
current_block = []

for m in matches:
    day, date, start, end, activity = m

    if activity == "BRF":
        # Start of a new block
        current_block = [m]
    elif activity == "DBRF" and current_block:
        # End of the current block
        current_block.append(m)
        blocks.append(current_block)
        current_block = []
    else:
        # Middle rows belong to the current block
        if current_block:
            current_block.append(m)

# -----------------------------------------------------------
# STEP 5: Function to convert date/time strings into datetime
# -----------------------------------------------------------
def parse_datetime(date_str, time_str):
    """
    Convert date like '28AUG25' and time like '06:00L' into
    a timezone-aware datetime object (America/Chicago).
    """
    date_obj = datetime.strptime(date_str, "%d%b%y")
    time_obj = datetime.strptime(time_str.replace("L", ""), "%H:%M").time()
    dt = datetime.combine(date_obj, time_obj)
    return dt.replace(tzinfo=ZoneInfo("America/Chicago"))

# -----------------------------------------------------------
# STEP 6: Process each block to extract activity, location, crew
# -----------------------------------------------------------
final_events = []

for block in blocks:
    start_row = block[0]       # BRF row
    end_row = block[-1]        # DBRF row

    day = start_row[0]
    date = start_row[1]
    start_time = start_row[2]
    end_time = end_row[3]

    # Find the first "real" event in the block
    main_row = next((r for r in block if r[4] not in ["BRF", "DBRF"]), None)
    activity = main_row[4] if main_row else "Training"

    # Find the full line in the original text that matches the main event
    main_row_text = next((l for l in lines if main_row and main_row[2] in l and main_row[3] in l), None)

    # Extract location from the main_row_text
    location = ""
    if main_row_text:
        parts = main_row_text.split()
        # Find where the activity appears in the line
        for idx, p in enumerate(parts):
            if p == activity.split()[0]:  # Match first part of activity
                after_activity = parts[idx + 1:]
                break
        # Clean out words like "Instr" and your name
        after_activity_clean = [
            p for p in after_activity
            if "Instr" not in p and "JONATHAN" not in p and "AIRHART" not in p
        ]
        if after_activity_clean:
            # Take the last part after the slash (e.g., B76FPT1)
            location = after_activity_clean[-1].split("/")[-1]

    # Collect crew names for this block
    crew_notes = []
    if main_row_text:
        start_index = lines.index(main_row_text) + 1
        for i in range(start_index, len(lines)):
            # Stop if we hit the next BRF (start of new block)
            if "BRF" in lines[i] and i > start_index:
                break
            if any(lines[i].strip().startswith(role) for role in ["CA", "FO", "SUPPORT"]):
                crew_notes.append(lines[i].strip())

    # Save event details
    final_events.append((activity, date, start_time, end_time, location, "\n".join(crew_notes)))

# -----------------------------------------------------------
# STEP 7: Build the ICS Calendar
# -----------------------------------------------------------
cal = Calendar()

for activity, date_str, start_str, end_str, location, notes in final_events:
    start_dt = parse_datetime(date_str, start_str)
    end_dt = parse_datetime(date_str, end_str)

    event = Event()
    event.name = activity                # Event title
    event.begin = start_dt
    event.end = end_dt
    event.location = location           # Facility code (e.g., B76FPT1)
    event.description = notes           # Crew list

    cal.events.add(event)

# -----------------------------------------------------------
# STEP 8: Save file as training_schedule_YYYY-MM.ics
# -----------------------------------------------------------
month_str = parse_datetime(final_events[0][1], final_events[0][2]).strftime("%Y-%m")
filename = f"training_schedule_{month_str}.ics"

with open(filename, "w") as f:
    f.writelines(cal)

print(f"✅ ICS file created: {filename}")
