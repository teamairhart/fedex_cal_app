import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from ics import Calendar, Event
import re
import pandas as pd

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="FedEx Schedule to Calendar", layout="wide")

# ---------- TITLE ----------
st.markdown("<h1 style='text-align: center; color: #4D148C;'>📅 FedEx Training Schedule → iCalendar (.ics)</h1>", unsafe_allow_html=True)

# ---------- INSTRUCTIONS ----------
st.markdown("""
### ✈️ How to Use
1️⃣ Go to your FedEx schedule webpage.  
2️⃣ **Ctrl+A → Ctrl+C** to copy the entire schedule.  
3️⃣ Paste it below OR upload a `.txt` file.  
4️⃣ Scroll down to preview and download your `.ics` calendar file.
""")

st.divider()

# ---------- HELPER FUNCTIONS ----------
def parse_datetime(date_str, time_str):
    date_obj = datetime.strptime(date_str, "%d%b%y")
    time_obj = datetime.strptime(time_str.replace("L", ""), "%H:%M").time()
    dt = datetime.combine(date_obj, time_obj)
    return dt.replace(tzinfo=ZoneInfo("America/Chicago"))

def parse_schedule(text):
    lines = text.splitlines()
    pattern_full = r"([A-Z][a-z]{2})\s+(\d{2}[A-Z]{3}\d{2})\s+(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)\s+([A-Z0-9\-]+(?:\s[0-9])?)"
    pattern_partial = r"(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)\s+([A-Z0-9\-]+(?:\s[0-9])?)"

    matches = []
    current_day, current_date = None, None

    for line in lines:
        m_full = re.search(pattern_full, line)
        m_part = re.search(pattern_partial, line)

        if m_full:
            current_day, current_date, start, end, activity = m_full.groups()
            matches.append((current_day, current_date, start, end, activity))
        elif m_part and current_day and current_date:
            start, end, activity = m_part.groups()
            matches.append((current_day, current_date, start, end, activity))

    blocks, current_block = [], []
    for m in matches:
        if m[4] == "BRF":
            current_block = [m]
        elif m[4] == "DBRF" and current_block:
            current_block.append(m)
            blocks.append(current_block)
            current_block = []
        elif current_block:
            current_block.append(m)

    final_events = []
    for block in blocks:
        start_row, end_row = block[0], block[-1]
        date, start_time, end_time = start_row[1], start_row[2], end_row[3]

        main_row = next((r for r in block if r[4] not in ["BRF", "DBRF"]), None)
        activity = main_row[4] if main_row else "Training"
        main_row_text = next((l for l in lines if main_row and main_row[2] in l and main_row[3] in l), None)

        # ✅ FIXED LOCATION EXTRACTION
        location = ""
        if main_row_text:
            # Look specifically for simulator codes like B76FPT1, B75S1, etc.
            match = re.search(r"\bB\d{2}[A-Z0-9]+\b", main_row_text)
            if match:
                location = match.group(0)

        # Crew notes (CA, FO, SUPPORT)
        crew_notes = []
        if main_row_text:
            start_idx = lines.index(main_row_text) + 1
            for i in range(start_idx, len(lines)):
                if "BRF" in lines[i] and i > start_idx:
                    break
                if any(lines[i].strip().startswith(r) for r in ["CA", "FO", "SUPPORT"]):
                    crew_notes.append(lines[i].strip())

        final_events.append((activity, date, start_time, end_time, location, "\n".join(crew_notes)))

    return final_events

def generate_ics(events):
    cal = Calendar()
    for activity, date_str, start_str, end_str, location, notes in events:
        start_dt = parse_datetime(date_str, start_str)
        end_dt = parse_datetime(date_str, end_str)

        e = Event()
        e.name = activity
        e.begin = start_dt
        e.end = end_dt
        e.location = location
        e.description = notes
        cal.events.add(e)

    month_str = parse_datetime(events[0][1], events[0][2]).strftime("%Y-%m")
    filename = f"training_schedule_{month_str}.ics"
    return filename, cal

# ---------- INPUT SECTION ----------
st.markdown("### 📋 Paste Your Schedule OR Upload a File")

# Text area for pasting
pasted_text = st.text_area("📌 Paste schedule here (Ctrl+A → Ctrl+C from webpage)", height=300)

# Optional file upload
uploaded_file = st.file_uploader("📂 Or upload a schedule (.txt)", type=["txt"])

# Determine which input to use
schedule_text = ""
if pasted_text.strip():
    schedule_text = pasted_text.strip()
elif uploaded_file:
    schedule_text = uploaded_file.read().decode("utf-8")

# ---------- PARSE + PREVIEW ----------
if schedule_text:
    events = parse_schedule(schedule_text)

    if events:
        st.success(f"✅ Found {len(events)} event blocks!")

        # Show table of events
        df = pd.DataFrame(events, columns=["Activity", "Date", "Start", "End", "Location", "Crew"])
        st.dataframe(df[["Activity", "Date", "Start", "End", "Location"]])

        # Show first event preview
        first = events[0]
        st.markdown(f"""
        ### 📅 First Event Preview
        **Title:** {first[0]}  
        **Date:** {first[1]}  
        **Time:** {first[2]} → {first[3]}  
        **Location:** {first[4]}  
        **Crew:**  
        ```
{first[5]}
        ```
        """)

        # Generate ICS for download
        filename, cal = generate_ics(events)
        ics_data = cal.serialize().encode("utf-8")

        st.download_button(
            label="📥 Download ICS File",
            data=ics_data,
            file_name=filename,
            mime="text/calendar",
            type="primary"
        )
    else:
        st.error("❌ No valid events found. Please check your pasted text.")
else:
    st.info("⬆️ Paste your schedule above or upload a `.txt` file to continue.")
