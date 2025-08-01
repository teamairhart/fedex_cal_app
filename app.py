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
    return datetime.combine(date_obj, time_obj).replace(tzinfo=ZoneInfo("America/Chicago"))

def parse_schedule(text):
    lines = text.splitlines()

    # Regex patterns for activity rows
    pattern_full = r"([A-Z][a-z]{2})\s+(\d{2}[A-Z]{3}\d{2})\s+(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)\s+([A-Z0-9\-]+(?:\s[0-9])?)"
    pattern_partial = r"(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)\s+([A-Z0-9\-]+(?:\s[0-9])?)"

    matches = []
    current_day, current_date = None, None

    # Collect all matching rows
    for line in lines:
        m_full = re.search(pattern_full, line)
        m_part = re.search(pattern_partial, line)
        if m_full:
            current_day, current_date, start, end, activity = m_full.groups()
            matches.append((line, current_day, current_date, start, end, activity))
        elif m_part and current_day and current_date:
            start, end, activity = m_part.groups()
            matches.append((line, current_day, current_date, start, end, activity))

    # Group into event blocks
    blocks = []
    current_block = []
    for row in matches:
        _, _, _, _, _, activity = row
        if activity == "BRF":
            current_block = [row]
        elif activity == "DBRF" and current_block:
            current_block.append(row)
            blocks.append(current_block)
            current_block = []
        elif current_block:
            current_block.append(row)

    final_events = []

    for block in blocks:
        start_row, end_row = block[0], block[-1]
        date = start_row[2]
        start_time = start_row[3]
        end_time = end_row[4]

        # Find main activity row (not BRF or DBRF)
        main_row = next((r for r in block if r[5] not in ["BRF", "DBRF"]), None)
        activity = main_row[5] if main_row else "Training"
        main_row_text = main_row[0] if main_row else ""

        # Extract location
        location = ""
        match = re.search(r"\bB\d{2}[A-Z0-9]+\b", main_row_text)
        if match:
            location = match.group(0)

        # ✅ NEW CREW EXTRACTION LOGIC
        crew_notes = []
        if main_row_text in lines:
            start_idx = lines.index(main_row_text) + 1
            for i in range(start_idx, min(start_idx + 8, len(lines))):
                candidate = lines[i].strip()
                if any(candidate.startswith(r) for r in ["CA", "FO", "SUPPORT"]):
                    if candidate not in crew_notes:
                        crew_notes.append(candidate)
                elif "BRF" in candidate:
                    break

        final_events.append(
            (activity, date, start_time, end_time, location, "\n".join(crew_notes))
        )

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

# ---------- STREAMLIT APP ----------
st.markdown("### 📋 Paste Your Schedule OR Upload a File")

pasted_text = st.text_area("📌 Paste schedule here (Ctrl+A → Ctrl+C from webpage)", height=300)
uploaded_file = st.file_uploader("📂 Or upload a schedule (.txt)", type=["txt"])

schedule_text = pasted_text.strip() if pasted_text.strip() else (
    uploaded_file.read().decode("utf-8") if uploaded_file else ""
)

if schedule_text:
    events = parse_schedule(schedule_text)

    if events:
        st.success(f"✅ Found {len(events)} event blocks!")

        df = pd.DataFrame(events, columns=["Activity", "Date", "Start", "End", "Location", "Crew"])
        st.dataframe(df[["Activity", "Date", "Start", "End", "Location"]])

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
