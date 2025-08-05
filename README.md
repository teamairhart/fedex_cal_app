
# 📅 FedEx Training Schedule → iCalendar (.ics)

**Modern web application** that converts your FedEx training schedule into an `.ics` calendar file for import into Apple Calendar, Outlook, or Google Calendar.  Go to https://teamairhart-fedex-cal-app.streamlit.app/

## ✈️ How to Use

1. **Go to your FedEx schedule webpage** (VIPS Training Schedule)
2. **Copy the entire page** with `Ctrl+A` → `Ctrl+C` (or `Cmd+A` → `Cmd+C` on Mac)
3. **Paste it into the app** - no need to save files or clean up the data!
4. **Preview your events** and download your `.ics` calendar file

The app intelligently extracts just the schedule data from the full webpage, so you can copy/paste everything without worry!

---

## 🚀 Web Application

### Quick Start
```bash
# Clone the repository
git clone https://github.com/teamairhart/fedex_cal_app.git
cd fedex_cal_app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the Flask app
python flask_app.py
```

Then open your browser to `http://localhost:5001`

### Features ✨
- **🎯 Smart Copy/Paste**: Handles full webpage content or just schedule data
- **📱 Modern Interface**: Responsive design with FedEx 767 background
- **👀 Live Preview**: See your events before downloading
- **🔧 Crew Filtering**: Exclude your name from crew notes automatically
- **📅 Perfect Formatting**: Groups BRF→Activity→DBRF into single events
- **🕐 Time Zone Ready**: Always outputs in Central Time (America/Chicago)
- **📍 Location Extraction**: Pulls simulator/facility codes (B76FPT1, etc.)

### Also Included
- **Command Line Version**: `python main.py` (requires `schedule.txt` file)
- **Streamlit Version**: `streamlit run app.py` for simple web interface

---

## 🛠️ Technical Details

### Supported Formats
- **Tabular Format**: Direct copy from VIPS training schedule webpage
- **Multi-line Format**: Clean schedule data with each field on separate lines
- **Full Webpage**: Copy entire VIPS page with navigation, headers, etc.

### Event Processing
- Groups training blocks (BRF → Main Activity → DBRF) into single calendar events
- Extracts activity types: AST 1, AST 2, AST 3, ASV, CMT2, BETA SIM, LOE, PV, etc.
- Pulls facility/simulator codes: B76FPT1, B75S1, B76S2, etc.
- Processes crew roles: CA, FO, INSTR, SUPPORT, DEVELOPER, FO-1, FO-2
- Filters excluded names from crew notes (put your name to exclude yourself)

### Output
- **Filename**: `training_schedule_YYYY-MM.ics`
- **Time Zone**: America/Chicago (Central Time)
- **Compatibility**: Works with Apple Calendar, Google Calendar, Outlook, and most calendar apps