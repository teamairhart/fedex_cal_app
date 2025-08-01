import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from ics import Calendar, Event
import re
import pandas as pd

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="FedEx Schedule to Calendar", layout="wide")

# ---------- FIXED BACKGROUND IMAGE ----------
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://upload.wikimedia.org/wikipedia/commons/5/55/FedEx_Express_Boeing_767-300F_N101FE.jpg");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# ---------- TITLE ----------
st.markdown("<h1 style='text-align: center; color: #4D148C;'>📅 FedEx Training Schedule → iCalendar (.ics)</h1>", unsafe_allow_html=True)

# ---------- INSTRUCTIONS ----------
st.markdown("""
### ✈️ How to Use
1️⃣ Go to your FedEx schedule webpage.  
2️⃣ Copy the entire schedule (Ctrl+A → Ctrl+C).  
3️⃣ Paste it into a `.txt` file (e.g., `schedule.txt`).  
4️⃣ Upload the `.txt` file below.  
5️⃣ Download the generated `.ics` file to import into your calendar.
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

        location = ""
        if main_row_text:
            parts = main_row_text.split()
            for idx, p in enumerate(parts):
                if p == activity.split()[0]:
                    after_activity = parts[idx + 1:]
                    break
            after_activity_clean = [p for p in after_activity if "Instr" not in p and "JONATHAN" not in p and "AIRHART" not in p]
            if after_activity_clean:
                location = after_activity_clean[-1].split("/")[-1]

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

# ---------- UPLOAD ----------
uploaded_file = st.file_uploader("📂 Upload your schedule (.txt)", type=["txt"])

if uploaded_file:
    text = uploaded_file.read().decode("utf-8")
    events = parse_schedule(text)

    if events:
        st.success(f"✅ Found {len(events)} event blocks!")

        # Show table
        df = pd.DataFrame(events, columns=["Activity", "Date", "Start", "End", "Location", "Crew"])
        st.dataframe(df[["Activity", "Date", "Start", "End", "Location"]])

        # Preview first event
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
        st.error("❌ No valid events found.")
else:
    st.info("⬆️ Upload a `.txt` schedule to get started.")
