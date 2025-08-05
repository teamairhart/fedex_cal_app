import re
from datetime import datetime
from zoneinfo import ZoneInfo
from ics import Calendar, Event
from typing import List, Tuple, Optional

def parse_datetime(date_str: str, time_str: str) -> datetime:
    """Convert date/time strings to timezone-aware datetime object."""
    date_obj = datetime.strptime(date_str, "%d%b%y")
    time_obj = datetime.strptime(time_str.replace("L", ""), "%H:%M").time()
    return datetime.combine(date_obj, time_obj).replace(tzinfo=ZoneInfo("America/Chicago"))

def preprocess_schedule_text(text: str) -> str:
    """Extract and normalize schedule data from various input formats."""
    
    # Debug output for development
    # print(f"DEBUG: Original text length: {len(text)}")
    # print(f"DEBUG: First 200 chars: {repr(text[:200])}")
    
    # If the text contains webpage content, try to extract just the schedule part
    lines = text.splitlines()
    
    # Look for the start of actual schedule data
    schedule_start = -1
    schedule_end = len(lines)
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        # Look for patterns that indicate schedule start
        if (re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{2}[A-Z]{3}\d{2}', line_stripped) or
            re.search(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)$', line_stripped)):
            if schedule_start == -1:
                schedule_start = i
                # print(f"DEBUG: Found schedule start at line {i}: {repr(line_stripped)}")
        
        # Look for patterns that indicate schedule end (common webpage footer content)
        if any(phrase in line_stripped.lower() for phrase in [
            'external links', 'feedback', 'company links', 'copyright', 'privacy policy',
            'sitemap', 'all rights reserved', 'fedex.com', 'terms of use'
        ]):
            schedule_end = i
            # print(f"DEBUG: Found schedule end at line {i}: {repr(line_stripped)}")
            break
    
    if schedule_start != -1:
        schedule_lines = lines[schedule_start:schedule_end]
        # print(f"DEBUG: Extracted {len(schedule_lines)} lines from original {len(lines)} lines")
    else:
        schedule_lines = lines
        # print("DEBUG: No schedule markers found, using all lines")
    
    # Check format types
    has_tabular_format = any('\t' in line and re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\t\d{2}[A-Za-z]{3}\d{2}', line.strip()) for line in schedule_lines)
    has_original_format = any(re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{2}[A-Za-z]{3}\d{2}\s+\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', line.strip()) for line in schedule_lines)
    
    # print(f"DEBUG: Detected tabular format: {has_tabular_format}")
    # print(f"DEBUG: Detected original format: {has_original_format}")
    
    if has_tabular_format:
        # Convert tabular format to multi-line format
        processed_lines = []
        current_day = None
        current_date = None
        
        for line in schedule_lines:
            line = line.strip()
            if not line:
                continue
            
            # Clean up tabs and normalize spacing
            line = re.sub(r'\t+', '\t', line)  # Normalize multiple tabs to single tab
                
            # Check if this is a main schedule line (starts with day)
            if re.search(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\t\d{2}[A-Z]{3}\d{2}', line):
                # print(f"DEBUG: Processing tabular line: {repr(line)}")
                
                # Split by tabs to get fields
                fields = line.split('\t')
                if len(fields) >= 4:
                    day = fields[0]
                    date = fields[1] 
                    time = fields[2]
                    activity = fields[3]
                    
                    # Only add day/date once per day
                    if current_day != day or current_date != date:
                        processed_lines.append(day)
                        processed_lines.append(date)
                        current_day = day
                        current_date = date
                    
                    processed_lines.append(time)
                    processed_lines.append(activity)
                    
                    # Add any facility info (like B76FPT2)
                    if len(fields) > 6:
                        facility_field = fields[6]
                        facility_match = re.search(r'B\d{2}[A-Z0-9]+', facility_field)
                        if facility_match:
                            processed_lines.append(facility_match.group())
                    
                    # Add crew information from remaining fields
                    if len(fields) > 5:
                        role = fields[5] if fields[5] else None
                        name = fields[6] if len(fields) > 6 and not re.search(r'B\d{2}[A-Z0-9]+', fields[6]) else None
                        
                        if role and role.strip():
                            processed_lines.append(role.strip().upper())
                            if name and name.strip():
                                processed_lines.append(name.strip())
                    
                    # print(f"DEBUG: Added: {day}, {date}, {time}, {activity}")
            
            elif '\t' in line:
                # This might be crew information on subsequent lines
                fields = line.split('\t')
                if len(fields) >= 2:
                    role = fields[0].strip()
                    name = fields[1].strip()
                    
                    if role and name:
                        processed_lines.append(role.upper())
                        processed_lines.append(name)
                        # print(f"DEBUG: Added crew: {role} - {name}")
            
            elif line and not re.search(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', line):
                # Regular line, add as-is
                processed_lines.append(line)
        
        result = '\n'.join(processed_lines)
        # print(f"DEBUG: Converted tabular to multi-line format")
        # print(f"DEBUG: Final result (first 500 chars): {repr(result[:500])}")
        return result
    elif has_original_format:
        # Convert original single-line format to multi-line format
        processed_lines = []
        
        for line in schedule_lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this is a main schedule line (starts with day and has time)
            if re.search(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{2}[A-Za-z]{3}\d{2}\s+\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', line):
                # Extract components using the original regex patterns
                day_date_match = re.search(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{2}[A-Za-z]{3}\d{2})', line)
                if day_date_match:
                    day, date = day_date_match.groups()
                    processed_lines.append(day)
                    processed_lines.append(date)
                    
                    # Extract time pattern
                    time_match = re.search(r'(\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L)', line)
                    if time_match:
                        processed_lines.append(time_match.group(1))
                        
                        # Extract activity (everything between time and crew roles)
                        remaining = line[time_match.end():].strip()
                        # Look for activity before any facility info or crew roles
                        activity_match = re.search(r'^([A-Z][A-Z0-9\s]*?)(?:\s+(?:MEM|B\d{2}|Instr|CA|FO|SUPPORT))', remaining)
                        if activity_match:
                            activity = activity_match.group(1).strip()
                            processed_lines.append(activity)
                        else:
                            # Fallback - take first few words
                            words = remaining.split()
                            if words:
                                activity = ' '.join(words[:2])  # Take first 2 words as activity
                                processed_lines.append(activity)
            elif re.search(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', line):
                # This is a continuation line with just time and activity (no day/date)
                time_match = re.search(r'(\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L)', line)
                if time_match:
                    processed_lines.append(time_match.group(1))
                    
                    # Extract activity (everything between time and crew roles)
                    remaining = line[time_match.end():].strip()
                    # Look for activity before any facility info or crew roles
                    activity_match = re.search(r'^([A-Z][A-Z0-9\s]*?)(?:\s+(?:MEM|B\d{2}|Instr|CA|FO|SUPPORT))', remaining)
                    if activity_match:
                        activity = activity_match.group(1).strip()
                        processed_lines.append(activity)
                    else:
                        # Fallback - take first few words
                        words = remaining.split()
                        if words:
                            activity = ' '.join(words[:2])  # Take first 2 words as activity
                            processed_lines.append(activity)
            else:
                # Regular line (crew info, etc.)
                processed_lines.append(line)
        
        result = '\n'.join(processed_lines)
        # print(f"DEBUG: Converted original format to multi-line format")
        return result
    else:
        # Already in multi-line format or needs no conversion
        result = '\n'.join(line.strip() for line in schedule_lines if line.strip())
        # print(f"DEBUG: Using multi-line format as-is")
        return result

def parse_schedule(text: str, exclude_names: Optional[List[str]] = None) -> List[Tuple[str, str, str, str, str, str]]:
    """Parse FedEx schedule text into structured events."""
    if exclude_names is None:
        exclude_names = []
    
    # Preprocess the input to handle different formats
    processed_text = preprocess_schedule_text(text)
    # print(f"DEBUG: Preprocessed text (first 500 chars): {repr(processed_text[:500])}")
    
    lines = [line.strip() for line in processed_text.splitlines() if line.strip()]
    
    events = []
    i = 0
    
    while i < len(lines):
        # Look for day pattern (Mon, Tue, Wed, etc.)
        if lines[i] in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
            current_day = lines[i]
            i += 1
            
            # Next line should be date (e.g., 04Aug25)
            if i < len(lines) and re.match(r'\d{2}[A-Za-z]{3}\d{2}', lines[i]):
                current_date = lines[i]
                i += 1
                
                # Collect all events for this day
                day_events = []
                while i < len(lines) and lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                    # Look for time pattern (e.g., 06:00L / 08:00L)
                    if re.match(r'\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', lines[i]):
                        time_parts = lines[i].split(' / ')
                        start_time = time_parts[0].strip()
                        end_time = time_parts[1].strip()
                        i += 1
                        
                        # Next line should be activity
                        if i < len(lines):
                            activity = lines[i].strip()
                            i += 1
                            
                            # Collect location if present
                            location = ""
                            # Look ahead for location pattern (B76FPT1, etc.)
                            for j in range(i, min(i + 10, len(lines))):
                                if j < len(lines) and re.match(r'B\d{2}[A-Z0-9]+', lines[j]):
                                    location = lines[j]
                                    break
                            
                            # Collect crew members
                            crew_notes = []
                            temp_i = i
                            while temp_i < len(lines) and not re.match(r'\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', lines[temp_i]) and lines[temp_i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                                line = lines[temp_i].strip()
                                # Skip location lines and activity names
                                if (re.match(r'B\d{2}[A-Z0-9]+', line) or 
                                    line in ['BRF', 'DBRF', 'AST 1', 'AST 2', 'AST 3', 'ASV', 'CMT2', 'BETA SIM', 'LOE', 'PV', 'UPSET RECOVERY']):
                                    temp_i += 1
                                    continue
                                    
                                # Check if it's a crew role line
                                if any(line.startswith(prefix) for prefix in ['CA', 'FO', 'SUPPORT', 'INSTR', 'DEVELOPER', 'FO-1', 'FO-2']):
                                    # Get the name on the next line
                                    if temp_i + 1 < len(lines):
                                        name_line = lines[temp_i + 1].strip()
                                        # Make sure it's not another time/day/activity line
                                        if (not re.match(r'\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', name_line) and 
                                            name_line not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] and
                                            not re.match(r'B\d{2}[A-Z0-9]+', name_line) and
                                            name_line not in ['BRF', 'DBRF', 'AST 1', 'AST 2', 'AST 3', 'ASV', 'CMT2', 'BETA SIM', 'LOE', 'PV', 'UPSET RECOVERY']):
                                            
                                            crew_entry = f"{line}: {name_line}"
                                            # Filter out excluded names
                                            if not any(name.upper() in crew_entry.upper() for name in exclude_names):
                                                crew_notes.append(crew_entry)
                                            temp_i += 2  # Skip both role and name lines
                                        else:
                                            # No name found, just add the role
                                            if not any(name.upper() in line.upper() for name in exclude_names):
                                                crew_notes.append(line)
                                            temp_i += 1
                                    else:
                                        # No next line available, just add the role
                                        if not any(name.upper() in line.upper() for name in exclude_names):
                                            crew_notes.append(line)
                                        temp_i += 1
                                else:
                                    temp_i += 1
                            
                            day_events.append({
                                'activity': activity,
                                'date': current_date,
                                'start_time': start_time,
                                'end_time': end_time,
                                'location': location,
                                'crew': crew_notes
                            })
                    else:
                        i += 1
                
                # Group events into BRF -> DBRF blocks
                brf_block = []
                for event in day_events:
                    if event['activity'] == 'BRF':
                        brf_block = [event]
                    elif event['activity'] == 'DBRF' and brf_block:
                        brf_block.append(event)
                        
                        # Find the main activity (not BRF or DBRF)
                        main_activity = 'Training'
                        main_location = ''
                        for e in brf_block:
                            if e['activity'] not in ['BRF', 'DBRF']:
                                main_activity = e['activity']
                                main_location = e['location']
                                break
                        
                        # Use time from BRF to DBRF
                        start_time = brf_block[0]['start_time']
                        end_time = brf_block[-1]['end_time']
                        
                        # Combine all crew from the block
                        all_crew = []
                        for e in brf_block:
                            all_crew.extend(e['crew'])
                        # Remove duplicates while preserving order
                        unique_crew = []
                        for crew in all_crew:
                            if crew not in unique_crew:
                                unique_crew.append(crew)
                        
                        events.append((main_activity, current_date, start_time, end_time, main_location, '\n'.join(unique_crew)))
                        brf_block = []
                    elif brf_block:
                        brf_block.append(event)
            else:
                i += 1
        else:
            i += 1
    
    # print(f"DEBUG: Parsed {len(events)} events")
    # for i, event in enumerate(events):
    #     print(f"DEBUG: Event {i+1}: {event[0]} on {event[1]} from {event[2]} to {event[3]}")
    
    return events

def generate_ics(events: List[Tuple[str, str, str, str, str, str]]) -> Tuple[str, Calendar]:
    """Generate ICS calendar from events list."""
    if not events:
        raise ValueError("No events provided")
    
    cal = Calendar()
    for activity, date_str, start_str, end_str, location, notes in events:
        try:
            start_dt = parse_datetime(date_str, start_str)
            end_dt = parse_datetime(date_str, end_str)
            
            event = Event()
            event.name = activity
            event.begin = start_dt
            event.end = end_dt
            event.location = location
            event.description = notes
            cal.events.add(event)
        except ValueError as e:
            print(f"Warning: Skipping event due to parsing error: {e}")
    
    month_str = parse_datetime(events[0][1], events[0][2]).strftime("%Y-%m")
    filename = f"training_schedule_{month_str}.ics"
    return filename, cal