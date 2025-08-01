
# 📅 FedEx Training Schedule → iCalendar (.ics)

Easily convert your FedEx training schedule into an `.ics` calendar file for import into Apple Calendar, Outlook, or Google Calendar.

🚀 **Try It Online:**  
👉 [Click here to open the app](https://teamairhart-fedex-cal-app.streamlit.app)

---


## 📌 Setup

1. Clone this repository or download the files.
2. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate

3. Install dependencies:

    pip install -r requirements.txt



📌 Usage

Paste your copied schedule text into schedule.txt.

Run the script:

python main.py

A file named training_schedule_YYYY-MM.ics will be created.

Open the .ics file to import events into your calendar.

📌 Features
✅ Groups BRF→DBRF blocks into single events
✅ Extracts main activity (e.g., AST 1, LOE)
✅ Extracts correct facility code (e.g., B76FPT1)
✅ Adds crew names in the event description
✅ Always outputs times in Central Time (America/Chicago)