import re
from datetime import datetime
from zoneinfo import ZoneInfo
from ics import Calendar, Event
from typing import List, Tuple, Optional

def parse_schedule(text: str, exclude_names: Optional[List[str]] = None) -> List[Tuple[str, str, str, str, str, str]]:
    """
    Simple parser that groups BRF→Activity→DBRF into single events.
    Returns ~35-40 events for Jonathan's schedule.
    """
    if exclude_names is None:
        exclude_names = []
        
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    events = []
    i = 0
    
    while i < len(lines):
        # Look for day
        if lines[i] in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
            day = lines[i]
            i += 1
            
            # Look for date
            if i < len(lines) and re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i]):
                date = lines[i]
                i += 1
                
                # Parse events for this day
                day_events = []
                while (i < len(lines) and 
                       lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] and
                       not re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i])):
                    
                    # Look for time pattern
                    if re.match(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L$', lines[i]):
                        event, new_i = parse_single_event(lines, i, date, exclude_names)
                        if event:
                            day_events.append(event)
                        i = new_i
                    else:
                        i += 1
                
                # Group events: BRF→Activity→DBRF becomes single event
                grouped_events = group_brf_dbrf_events(day_events)
                events.extend(grouped_events)
            else:
                i += 1
        else:
            i += 1
    
    return events

def parse_single_event(lines: List[str], start_i: int, date: str, exclude_names: List[str]) -> Tuple[Optional[Tuple[str, str, str, str, str, List[str]]], int]:
    """Parse a single time block."""
    i = start_i
    
    # Parse time
    time_match = re.match(r'^(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)$', lines[i])
    if not time_match:
        return None, i + 1
        
    start_time, end_time = time_match.groups()
    i += 1
    
    # Parse activity
    if i >= len(lines):
        return None, i
        
    activity = lines[i].strip()
    i += 1
    
    # Parse location and crew
    location = ""
    crew_list = []
    
    while (i < len(lines) and 
           not re.match(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L$', lines[i]) and
           lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] and
           not re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i])):
        
        line = lines[i].strip()
        
        # Check if it's a location (simulator names, etc.)
        if is_location(line):
            if not location:
                location = line
            i += 1
        # Check if it's a crew role
        elif is_crew_role(line):
            role = line
            i += 1
            
            # Try to get name
            if (i < len(lines) and 
                not re.match(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L$', lines[i]) and
                lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] and
                not re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i]) and
                not is_location(lines[i]) and
                not is_crew_role(lines[i])):
                
                name = lines[i].strip()
                crew_entry = f"{role}: {name}"
                
                # Check exclusions
                if not any(excluded.upper() in crew_entry.upper() for excluded in exclude_names):
                    crew_list.append(crew_entry)
                
                i += 1
            else:
                # Just role, no name
                if not any(excluded.upper() in role.upper() for excluded in exclude_names):
                    crew_list.append(role)
        else:
            i += 1
    
    return (activity, date, start_time, end_time, location, crew_list), i

def group_brf_dbrf_events(events: List[Tuple[str, str, str, str, str, List[str]]]) -> List[Tuple[str, str, str, str, str, str]]:
    """
    Group BRF→Activity→DBRF into single events.
    Returns events in format: (activity, date, start_time, end_time, location, crew_str)
    """
    if not events:
        return []
    
    grouped = []
    i = 0
    
    while i < len(events):
        activity, date, start_time, end_time, location, crew_list = events[i]
        
        # Check if this is a BRF (start of block)
        if activity == 'BRF':
            # Look for the main activity and DBRF
            main_activity = None
            main_location = ""
            all_crew = crew_list.copy()
            final_end_time = end_time
            
            # Scan forward for activities and DBRF
            j = i + 1
            while j < len(events):
                next_activity, next_date, next_start, next_end, next_location, next_crew = events[j]
                
                # Stop if we hit another BRF or different date
                if next_activity == 'BRF' or next_date != date:
                    break
                
                # Collect main activity and location
                if next_activity != 'DBRF' and not main_activity:
                    main_activity = next_activity
                    if next_location:
                        main_location = next_location
                
                # Collect all crew
                all_crew.extend(next_crew)
                
                # Update end time
                final_end_time = next_end
                
                # If this is DBRF, we're done with this block
                if next_activity == 'DBRF':
                    j += 1
                    break
                    
                j += 1
            
            # Create grouped event
            if main_activity:
                # Remove duplicate crew while preserving order
                unique_crew = []
                for crew in all_crew:
                    if crew not in unique_crew:
                        unique_crew.append(crew)
                
                crew_str = '\n'.join(unique_crew)
                grouped.append((main_activity, date, start_time, final_end_time, main_location, crew_str))
            
            i = j  # Skip to after the block
        else:
            # Standalone event (not part of BRF→DBRF block)
            crew_str = '\n'.join(crew_list)
            grouped.append((activity, date, start_time, end_time, location, crew_str))
            i += 1
    
    return grouped

def is_location(text: str) -> bool:
    """Check if text looks like a location/simulator."""
    if not text:
        return False
    
    # Simulator patterns
    patterns = [
        r'^B\d{2}[A-Z0-9]+$',  # B76S1, B75FPT1, etc.
        r'^MEM\s+AOTC',        # MEM AOTC MOD-C, etc.
        r'^\d{4}\s+[A-Z]+-\d+$',  # 2439 CR-211, etc.
    ]
    
    return any(re.match(pattern, text) for pattern in patterns)

def is_crew_role(text: str) -> bool:
    """Check if text looks like a crew role."""
    if not text:
        return False
    
    known_roles = {
        'CA', 'FO', 'SUPPORT', 'INSTR', 'INSTRUCTOR', 'PILOT',
        'FO-1', 'FO-2', 'CA-1', 'CA-2', 'TRAINEE',
        'IIT', 'IIT Conductor', 'IIT Observer', 'DEVELOPER'
    }
    
    # Check exact matches first
    if text in known_roles:
        return True
    
    # Check patterns
    patterns = [
        r'^[A-Z]{2,6}$',          # CA, FO, INSTR, etc.
        r'^[A-Z]+-[A-Z0-9]+$',    # FO-1, CA-2, etc.
        r'^IIT\s+\w+$',           # IIT Conductor, IIT Observer
    ]
    
    return any(re.match(pattern, text) for pattern in patterns)

def parse_datetime(date_str: str, time_str: str) -> datetime:
    """Convert date/time strings to timezone-aware datetime object."""
    date_obj = datetime.strptime(date_str, "%d%b%y")
    time_obj = datetime.strptime(time_str.replace("L", ""), "%H:%M").time()
    return datetime.combine(date_obj, time_obj).replace(tzinfo=ZoneInfo("America/Chicago"))

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
            print(f"Skipping event due to parsing error: {e}")
    
    month_str = parse_datetime(events[0][1], events[0][2]).strftime("%Y-%m")
    filename = f"training_schedule_{month_str}.ics"
    return filename, cal