from flask import Flask, render_template, request, send_file, jsonify
import io
import os
from helpers import parse_schedule, generate_ics, DEFAULT_TZ

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

@app.route('/')
def index():
    # NOTE: Ensure your templates/index.html exists and includes fields:
    #  - textarea name="schedule_text"
    #  - input name="exclude_names"
    #  - optional select name="timezone" (defaults to America/Chicago)
    #  - optional checkbox name="export_utc"
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_schedule():
    try:
        schedule_text = (request.form.get('schedule_text') or '').strip()
        exclude_names = (request.form.get('exclude_names') or '').strip()
        tz_str = (request.form.get('timezone') or DEFAULT_TZ).strip()
        export_utc = bool(request.form.get('export_utc'))  # checkbox → 'on' present

        if not schedule_text:
            return jsonify({'error': 'Please provide schedule text'}), 400

        exclude_list = [name.strip() for name in exclude_names.split(',') if name.strip()]
        events = parse_schedule(schedule_text, exclude_list)
        if not events:
            return jsonify({'error': 'No valid events found in the schedule. Please check your input.'}), 400

        filename, calendar = generate_ics(events, tz_str=tz_str, export_utc=export_utc)
        ics_content = calendar.serialize()

        ics_file = io.BytesIO(ics_content.encode('utf-8'))
        ics_file.seek(0)

        return send_file(
            ics_file,
            as_attachment=True,
            download_name=filename,
            mimetype='text/calendar'
        )

    except Exception as e:
        return jsonify({'error': f'Error processing schedule: {str(e)}'}), 500

@app.route('/preview', methods=['POST'])
def preview_schedule():
    try:
        schedule_text = (request.form.get('schedule_text') or '').strip()
        exclude_names = (request.form.get('exclude_names') or '').strip()
        tz_str = (request.form.get('timezone') or DEFAULT_TZ).strip()
        export_utc = bool(request.form.get('export_utc'))

        if not schedule_text:
            return jsonify({'error': 'Please provide schedule text'}), 400

        exclude_list = [name.strip() for name in exclude_names.split(',') if name.strip()]
        events = parse_schedule(schedule_text, exclude_list)
        if not events:
            return jsonify({'error': 'No valid events found in the schedule'}), 400

        formatted_events = []
        for activity, date, start, end, location, crew in events:
            formatted_events.append({
                'activity': activity,
                'date': date,
                'start': start,
                'end': end,
                'location': location,
                'crew': crew.split('\n') if crew else []
            })

        return jsonify({
            'success': True,
            'event_count': len(events),
            'timezone': tz_str,
            'export_utc': export_utc,
            'events': formatted_events
        })

    except Exception as e:
        return jsonify({'error': f'Error parsing schedule: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)