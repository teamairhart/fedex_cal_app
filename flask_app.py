from flask import Flask, render_template, request, send_file, jsonify
import io
import os
from helpers import parse_schedule, generate_ics

app = Flask(__name__)
app.secret_key = 'fedex-schedule-converter-secret-key'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_schedule():
    try:
        # Get form data
        schedule_text = request.form.get('schedule_text', '').strip()
        exclude_names = request.form.get('exclude_names', '').strip()
        
        if not schedule_text:
            return jsonify({'error': 'Please provide schedule text'}), 400
        
        # Parse exclude names
        exclude_list = [name.strip() for name in exclude_names.split(',') if name.strip()]
        
        # Parse schedule
        events = parse_schedule(schedule_text, exclude_list)
        
        if not events:
            return jsonify({'error': 'No valid events found in the schedule. Please check your input.'}), 400
        
        # Generate ICS file
        filename, calendar = generate_ics(events)
        ics_content = calendar.serialize()
        
        # Create file-like object
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
        schedule_text = request.form.get('schedule_text', '').strip()
        exclude_names = request.form.get('exclude_names', '').strip()
        
        if not schedule_text:
            return jsonify({'error': 'Please provide schedule text'}), 400
        
        # Parse exclude names
        exclude_list = [name.strip() for name in exclude_names.split(',') if name.strip()]
        
        # Parse schedule
        events = parse_schedule(schedule_text, exclude_list)
        
        if not events:
            return jsonify({'error': 'No valid events found in the schedule'}), 400
        
        # Format events for display
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
            'events': formatted_events[:5]  # Show first 5 events
        })
        
    except Exception as e:
        return jsonify({'error': f'Error parsing schedule: {str(e)}'}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)