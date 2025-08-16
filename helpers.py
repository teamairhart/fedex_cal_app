import re
from datetime import datetime
from zoneinfo import ZoneInfo
from ics import Calendar, Event
from typing import List, Tuple, Optional, Set

# Known FedEx training activities (helps with accuracy, falls back to pattern detection for unknown)
KNOWN_ACTIVITIES = {
    # Core activities
    'BRF', 'DBRF', 'Tour', 'INTRO',
    
    # AST Series
    'AST1', 'AST 1', 'AST2', 'AST 2', 'AST3', 'AST 3', 'ASV',
    
    # Operations
    'OPS1', 'OPS 1', 'OPS2', 'OPS 2', 'OPS3', 'OPS 3', 'OPS4', 'OPS 4',
    
    # Procedures
    'PRO1', 'PRO 1', 'PRO2', 'PRO 2', 'PRO3', 'PRO 3', 'PRO4', 'PRO 4',
    'PRO5', 'PRO 5', 'PRO6', 'PRO 6', 'PRO7', 'PRO 7',
    'PV', 'Procedures Validation',
    
    # Maneuvers
    'MAN1', 'MAN 1', 'MAN2', 'MAN 2', 'MAN3', 'MAN 3', 'MAN4', 'MAN 4',
    'MAN5', 'MAN 5', 'MAN6', 'MAN 6', 'MAN7', 'MAN 7',
    'MV', 'Maneuvers Validation',
    
    # CMT Series (Crew Member Training)
    'CMT', 'CMT1', 'CMT 1', 'CMT2', 'CMT 2', 'CMV', 'IMV',
    
    # Special training
    'LOE', 'HF', 'CQGS', 'EFVS', 'EET', 'IGS', 'ETOPS',
    'LCT', 'LCV', 'LCT/CET', 'SCT', 'SCV',
    'DIFF', 'Diff Requal',
    
    # Line training
    'LRT1', 'LRT 1', 'LRT2', 'LRT 2', 'LRT3', 'LRT 3',
    'C-SRT', 'LRT3/C-SRT',
    
    # Recency/Currency
    'RMV', 'C-RMV', 'RMV/C-RMV', 'RLOE',
    'RSMT-EG', 'RMSV-SG',
    
    # Technology/Systems
    'HUD', 'API',
    
    # Classroom/Emergency
    'Sys Class', 'Emerg Training', 'Emg Equip',
    
    # Initial/Advanced training
    'IMT1', 'FPM', 'CLOE',
    
    # Simulator types
    'Alpha', 'Alpha Sim', 'Beta', 'BETA SIM',
    
    # IIT Training
    'IIT', 'IIT Observe', 'IIT Conduct', 'IIT SYS3 Observe/EE',
    
    # Other
    'RB-S', 'UPSET RECOVERY'
}

# Known FedEx training locations (helps with accuracy, falls back to pattern detection for unknown)
KNOWN_LOCATIONS = {
    # Simulator patterns (most common)
    'B75S1', 'B75S2', 'B75S3', 'B75S4', 'B75S5',
    'B76S1', 'B76S2', 'B76S3', 'B76S4', 'B76S5',
    'B77S1', 'B77S2', 'B77S3', 'B77S4', 'B77S5',
    
    # Classroom simulators
    'B75C1', 'B75C2', 'B76C1',
    
    # Flight Training Devices
    'B75FPT1', 'B75FPT2', 'B76FPT1', 'B76FPT2', 'B77FPT1', 'B77FPT2',
    
    # Specific rooms/buildings
    'MEM AOTC MOD-C', '2439 CR-211', '2438 CR-210', '2013 EVACMEM',
    
    # General classroom/building locations
    'MEM Building', 'Training Center', 'Classroom A', 'Classroom B',
    'Conference Room', 'Flight Ops', 'Dispatch'
}

# Known crew roles (for accurate crew parsing)
KNOWN_CREW_ROLES = {
    'CA', 'FO', 'SUPPORT', 'INSTR', 'DEVELOPER', 
    'FO-1', 'FO-2', 'CA 1', 'CA 2',
    'TRAINEE-A', 'TRAINEE-B',
    'IIT Conductor', 'IIT Observer',
    'PILOT', 'INSTRUCTOR'
}

def normalize_activity_name(activity: str) -> str:
    """Normalize activity names to handle variations like 'AST1' vs 'AST 1'."""
    if not activity:
        return activity
    
    # Remove extra whitespace
    activity = activity.strip()
    
    # Create both spaced and non-spaced versions for comparison
    # Examples: "AST1" -> "AST 1", "CMT2" -> "CMT 2"
    if re.match(r'^[A-Z]+\d+$', activity):
        # Add space before number: "AST1" -> "AST 1"
        spaced_version = re.sub(r'([A-Z]+)(\d+)', r'\1 \2', activity)
        if spaced_version in KNOWN_ACTIVITIES:
            return spaced_version
    elif re.match(r'^[A-Z]+ \d+$', activity):
        # Remove space: "AST 1" -> "AST1"
        no_space_version = activity.replace(' ', '')
        if no_space_version in KNOWN_ACTIVITIES:
            return no_space_version
    
    return activity

def is_known_activity(activity: str) -> bool:
    """Check if an activity is in our known list (with normalization)."""
    if not activity:
        return False
    
    # Check exact match first
    if activity in KNOWN_ACTIVITIES:
        return True
    
    # Check normalized version
    normalized = normalize_activity_name(activity)
    return normalized in KNOWN_ACTIVITIES

def is_known_location(location: str) -> bool:
    """Check if a location is in our known list."""
    if not location:
        return False
    return location in KNOWN_LOCATIONS

def is_likely_location(line: str) -> bool:
    """Use pattern detection to identify likely locations when not in known list."""
    if not line:
        return False
    
    line = line.strip()
    
    # Known patterns for FedEx locations
    patterns = [
        r'^B\d{2}[A-Z0-9]+$',           # B76S1, B75FPT1, etc.
        r'^\d{4} [A-Z]+-\d+$',          # 2439 CR-211, 2438 CR-210
        r'^MEM [A-Z]+',                 # MEM Building, MEM AOTC MOD-C
        r'^Training Center',            # Training Center variations
        r'^Classroom [A-Z0-9]',         # Classroom A, B, etc.
        r'^Conference Room',            # Conference Room variations
        r'Building$',                   # Ends with "Building"
        r'Room$',                       # Ends with "Room"
    ]
    
    return any(re.match(pattern, line) for pattern in patterns)

def is_crew_role_line(line: str) -> bool:
    """Check if a line represents a crew role (with hybrid approach)."""
    if not line:
        return False
    
    line = line.strip()
    
    # Check known crew roles first
    if any(line.startswith(role) for role in KNOWN_CREW_ROLES):
        return True
    
    # Pattern-based fallback for unknown crew roles
    # Common patterns: ALL CAPS, ends with numbers, contains specific keywords
    patterns = [
        r'^[A-Z]{2,4}$',               # CA, FO, INSTR, etc.
        r'^[A-Z]+ \d+$',               # CA 1, FO 2, etc.
        r'^[A-Z]+-[A-Z0-9]+$',         # FO-1, TRAINEE-A, etc.
        r'[Ii]nstructor',              # Instructor variations
        r'[Pp]ilot',                   # Pilot variations
        r'[Tt]rainee',                 # Trainee variations
    ]
    
    return any(re.match(pattern, line) for pattern in patterns)

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
                        
                        # Extract activity and location from remaining text
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
                        
                        # Extract location (B76FPT1, etc.)
                        location_match = re.search(r'B\d{2}[A-Z0-9]+', remaining)
                        if location_match:
                            processed_lines.append(location_match.group())
            elif re.search(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', line):
                # This is a continuation line with just time and activity (no day/date)
                time_match = re.search(r'(\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L)', line)
                if time_match:
                    processed_lines.append(time_match.group(1))
                    
                    # Extract activity and location from remaining text
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
                    
                    # Extract location (B76FPT1, etc.)
                    location_match = re.search(r'B\d{2}[A-Z0-9]+', remaining)
                    if location_match:
                        processed_lines.append(location_match.group())
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
        current_date = None
        current_day = None
        
        # Look for day pattern (Mon, Tue, Wed, etc.) OR direct date pattern (30Jun25)
        if lines[i] in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
            current_day = lines[i]
            i += 1
            
            # Next line should be date (e.g., 04Aug25)
            if i < len(lines) and re.match(r'\d{2}[A-Za-z]{3}\d{2}', lines[i]):
                current_date = lines[i]
                i += 1
        elif re.match(r'\d{2}[A-Za-z]{3}\d{2}', lines[i]):
            # Direct date pattern (no day name) - new format support
            current_date = lines[i]
            current_day = None  # We don't have the day name in this format
            i += 1
                
        # Only proceed if we have a valid date
        if current_date:
            # Collect all events for this day
            day_events = []
            while i < len(lines) and lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] and not re.match(r'\d{2}[A-Za-z]{3}\d{2}', lines[i]):
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
                            
                            # Collect location if present (hybrid approach)
                            location = ""
                            # Look ahead for location (known locations first, then pattern detection)
                            for j in range(i, min(i + 10, len(lines))):
                                if j < len(lines):
                                    potential_location = lines[j].strip()
                                    if is_known_location(potential_location) or is_likely_location(potential_location):
                                        location = potential_location
                                        break
                            
                            # Collect crew members
                            crew_notes = []
                            temp_i = i
                            while temp_i < len(lines) and not re.match(r'\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', lines[temp_i]) and lines[temp_i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] and not re.match(r'\d{2}[A-Za-z]{3}\d{2}', lines[temp_i]):
                                line = lines[temp_i].strip()
                                
                                # Skip location lines and activity names (hybrid approach)
                                if (is_known_location(line) or is_likely_location(line) or 
                                    is_known_activity(line)):
                                    temp_i += 1
                                    continue
                                    
                                # Check if it's a crew role line (hybrid approach)
                                if is_crew_role_line(line):
                                    # Get the name on the next line
                                    if temp_i + 1 < len(lines):
                                        name_line = lines[temp_i + 1].strip()
                                        # Make sure it's not another time/day/activity/location line (hybrid approach)
                                        if (not re.match(r'\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L', name_line) and 
                                            name_line not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] and
                                            not re.match(r'\d{2}[A-Za-z]{3}\d{2}', name_line) and
                                            not is_known_location(name_line) and not is_likely_location(name_line) and
                                            not is_known_activity(name_line) and not is_crew_role_line(name_line)):
                                            
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