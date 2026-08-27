from flask import Flask, render_template, request, send_file, jsonify
import io
import os
from helpers import parse_schedule, generate_ics, DEFAULT_TZ
from mint_parser import parse_mint_csv, looks_like_mint_csv

app = Flask(__name__)

def get_schedule_text(req):
    """Uploaded file takes priority over pasted text."""
    uploaded = req.files.get('schedule_file')
    if uploaded and uploaded.filename:
        return uploaded.read().decode('utf-8-sig', errors='replace').strip()
    return (req.form.get('schedule_text') or '').strip()

def parse_any(schedule_text, exclude_list):
    """Auto-detect MINT CSV export vs. legacy webpage copy/paste."""
    if looks_like_mint_csv(schedule_text):
        return parse_mint_csv(schedule_text, exclude_list), 'MINT CSV'
    return parse_schedule(schedule_text, exclude_list), 'webpage paste'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_schedule():
    try:
        schedule_text = get_schedule_text(request)
        exclude_names = (request.form.get('exclude_names') or '').strip()

        if not schedule_text:
            return jsonify({'error': 'Please provide schedule text or upload a file'}), 400

        exclude_list = [name.strip() for name in exclude_names.split(',') if name.strip()]
        events, _ = parse_any(schedule_text, exclude_list)
        if not events:
            return jsonify({'error': 'No valid events found in the schedule. Please check your input.'}), 400

        filename, calendar = generate_ics(events)
        ics_content = calendar.serialize()

        ics_file = io.BytesIO(ics_content.encode('utf-8'))
        ics_file.seek(0)

        return send_file(
            ics_file,
            as_attachment=True,
            download_name=filename,
            mimetype='text/calendar'
        )

    except Exception:
        app.logger.exception('convert failed')
        return jsonify({'error': 'Could not process that schedule. Please check the input format.'}), 400

@app.route('/preview', methods=['POST'])
def preview_schedule():
    try:
        schedule_text = get_schedule_text(request)
        exclude_names = (request.form.get('exclude_names') or '').strip()

        if not schedule_text:
            return jsonify({'error': 'Please provide schedule text or upload a file'}), 400

        exclude_list = [name.strip() for name in exclude_names.split(',') if name.strip()]
        events, detected_format = parse_any(schedule_text, exclude_list)
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
            'timezone': DEFAULT_TZ,
            'format': detected_format,
            'events': formatted_events
        })

    except Exception:
        app.logger.exception('preview failed')
        return jsonify({'error': 'Could not parse that schedule. Please check the input format.'}), 400

@app.route('/healthz')
def healthz():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)
