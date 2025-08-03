import streamlit as st
import pandas as pd
from helpers import parse_schedule, generate_ics

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

# ---------- USER SETTINGS ----------
exclude_names = st.sidebar.text_input("Exclude names from crew list (comma-separated):", 
                                       value="Jonathan Airhart").split(",")
exclude_names = [name.strip() for name in exclude_names if name.strip()]

# ---------- STREAMLIT APP ----------
st.markdown("### 📋 Paste Your Schedule OR Upload a File")

pasted_text = st.text_area("📌 Paste schedule here (Ctrl+A → Ctrl+C from webpage)", height=300)
uploaded_file = st.file_uploader("📂 Or upload a schedule (.txt)", type=["txt"])

schedule_text = pasted_text.strip() if pasted_text.strip() else (
    uploaded_file.read().decode("utf-8") if uploaded_file else ""
)

if schedule_text:
    try:
        events = parse_schedule(schedule_text, exclude_names)
    except Exception as e:
        st.error(f"❌ Error parsing schedule: {str(e)}")
        events = []

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

        try:
            filename, cal = generate_ics(events)
            ics_data = cal.serialize().encode("utf-8")
        except Exception as e:
            st.error(f"❌ Error generating ICS file: {str(e)}")
            filename, ics_data = None, None

        if ics_data:
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
