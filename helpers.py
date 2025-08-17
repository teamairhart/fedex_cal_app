import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from hashlib import sha1
from typing import List, Tuple, Optional
from ics import Calendar, Event

# ------------------------------
# Defaults
# ------------------------------
DEFAULT_TZ = "America/Chicago"

# Expanded patterns for facility / simulator locations
LOCATION_PATTERNS = [
    r"^B\d{2}[A-Z0-9]+$",           # B76S1, B75FPT1, etc.
    r"^[A-Z]{3}\s+AOTC.*$",         # MEM AOTC MOD-C, etc.
    r"^[A-Z]{3}\s+SIM.*$",          # MEM SIM BAY 3, etc.
    r"^\d{3,5}\s+[A-Z]{2,}-\d+$",  # 2439 CR-211, etc.
]

KNOWN_ROLES = {
    'CA', 'FO', 'SUPPORT', 'INSTR', 'INSTRUCTOR', 'PILOT',
    'FO-1', 'FO-2', 'CA-1', 'CA-2', 'TRAINEE',
    'FO 1', 'FO 2', 'CA 1', 'CA 2',
    'IIT', 'IIT CONDUCTOR', 'IIT OBSERVER',
    # additional common variants
    'EVAL', 'OBS', 'DEV', 'PGM'
}

# ------------------------------
# Utility helpers
# ------------------------------

def _norm_name(s: str) -> set:
    """Normalize a name/entry to uppercase tokens (>=2 chars) for robust matching."""
    tokens = re.findall(r"[A-Z]{2,}", s.upper())
    return set(tokens)


def is_location(text: str) -> bool:
    if not text:
        return False
    return any(re.match(p, text) for p in LOCATION_PATTERNS)


def is_crew_role(text: str) -> bool:
    if not text:
        return False
    t = text.upper().strip()
    if t in KNOWN_ROLES:
        return True
    patterns = [
        r"^[A-Z]{2,6}$",        # CA, FO, INSTR, etc.
        r"^[A-Z]+-[A-Z0-9]+$",  # FO-1, CA-2, etc.
        r"^[A-Z]+\s+[0-9]+$",   # FO 1, CA 2, etc.
        r"^IIT\s+\w+$",         # IIT Conductor / Observer
    ]
    return any(re.match(p, t) for p in patterns)


def parse_datetime(date_str: str, time_str: str, tz_str: str = DEFAULT_TZ) -> datetime:
    """Convert date/time strings to timezone-aware datetime. Date e.g. '06Aug25', time e.g. '07:00L'."""
    d = datetime.strptime(date_str, "%d%b%y").date()
    t = datetime.strptime(time_str.replace("L", ""), "%H:%M").time()
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=ZoneInfo(tz_str))


# ------------------------------
# Core parsing
# ------------------------------

def parse_schedule(text: str, exclude_names: Optional[List[str]] = None) -> List[Tuple[str, str, str, str, str, str]]:
    """
    Parse VIPS copy/paste and group BRF→Activity→DBRF into single events.
    Returns list of tuples: (activity, date, start_time, end_time, location, crew_str)
    """
    if exclude_names is None:
        exclude_names = []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    events = []
    i = 0

    while i < len(lines):
        # Day label
        if lines[i] in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
            i += 1
            # Date like 06Aug25
            if i < len(lines) and re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i]):
                date = lines[i]
                i += 1

                # Collect all time blocks until next day/date header
                day_events = []
                while (
                    i < len(lines)
                    and lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                    and not re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i])
                ):
                    if re.match(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L$', lines[i]):
                        event, new_i = parse_single_event(lines, i, date, exclude_names)
                        if event:
                            day_events.append(event)
                        i = new_i
                    else:
                        i += 1

                # Group BRF → main activity → DBRF
                grouped_events = group_brf_dbrf_events(day_events)
                events.extend(grouped_events)
            else:
                i += 1
        else:
            i += 1

    return events


def parse_single_event(
    lines: List[str], start_i: int, date: str, exclude_names: List[str]
) -> Tuple[Optional[Tuple[str, str, str, str, str, List[str]]], int]:
    """Parse a single time block and return ((activity,date,start,end,location,crew_list), next_index)."""
    i = start_i

    time_match = re.match(r'^(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)$', lines[i])
    if not time_match:
        return None, i + 1

    start_time, end_time = time_match.groups()
    i += 1

    if i >= len(lines):
        return None, i

    activity = lines[i].strip()
    i += 1

    location = ""
    crew_list: List[str] = []

    ex_norm = _norm_name(" ".join(exclude_names))

    while (
        i < len(lines)
        and not re.match(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L$', lines[i])
        and lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        and not re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i])
    ):
        line = lines[i].strip()

        if is_location(line):
            if not location:
                location = line
            i += 1
        elif is_crew_role(line):
            role = line
            i += 1
            # Attempt to read a following name line
            if (
                i < len(lines)
                and not re.match(r'^\d{2}:\d{2}L\s*/\s*\d{2}:\d{2}L$', lines[i])
                and lines[i] not in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                and not re.match(r'^\d{2}[A-Za-z]{3}\d{2}$', lines[i])
                and not is_location(lines[i])
                and not is_crew_role(lines[i])
            ):
                name = lines[i].strip()
                crew_entry = f"{role}: {name}"
                if _norm_name(crew_entry).isdisjoint(ex_norm):
                    crew_list.append(crew_entry)
                i += 1
            else:
                if _norm_name(role).isdisjoint(ex_norm):
                    crew_list.append(role)
        else:
            i += 1

    return (activity, date, start_time, end_time, location, crew_list), i


def group_brf_dbrf_events(
    events: List[Tuple[str, str, str, str, str, List[str]]]
) -> List[Tuple[str, str, str, str, str, str]]:
    """Group BRF→Activity→DBRF blocks. Fallback to standalone if DBRF missing."""
    if not events:
        return []

    grouped: List[Tuple[str, str, str, str, str, str]] = []
    i = 0

    while i < len(events):
        activity, date, start_time, end_time, location, crew_list = events[i]

        if activity == 'BRF':
            main_activity = None
            main_location = ""
            all_crew = crew_list.copy()
            final_end_time = end_time
            j = i + 1
            while j < len(events):
                next_activity, next_date, next_start, next_end, next_location, next_crew = events[j]
                if next_activity == 'BRF' or next_date != date:
                    break
                if next_activity != 'DBRF' and not main_activity:
                    main_activity = next_activity
                    if next_location:
                        main_location = next_location
                all_crew.extend(next_crew)
                final_end_time = next_end
                if next_activity == 'DBRF':
                    j += 1
                    break
                j += 1

            if main_activity:
                # de-duplicate crews preserving order
                uniq = []
                for c in all_crew:
                    if c not in uniq:
                        uniq.append(c)
                crew_str = '\n'.join(uniq)
                grouped.append((main_activity, date, start_time, final_end_time, main_location, crew_str))
                i = j
                continue
            # Fallback: treat BRF as standalone
            grouped.append((activity, date, start_time, end_time, location, '\n'.join(crew_list)))
            i += 1
        else:
            grouped.append((activity, date, start_time, end_time, location, '\n'.join(crew_list)))
            i += 1

    return grouped


# ------------------------------
# ICS generation
# ------------------------------

def generate_ics(
    events: List[Tuple[str, str, str, str, str, str]],
    tz_str: str = DEFAULT_TZ,
    export_utc: bool = False,
) -> Tuple[str, Calendar]:
    """Generate an ICS Calendar. Returns (filename, Calendar)."""
    if not events:
        raise ValueError("No events provided")

    cal = Calendar()
    cal.creator = "fdx-cal-app 1.0"

    # Helpful calendar metadata for Apple/Google/Outlook (best-effort)
    try:
        from ics.grammar.parse import ContentLine
        cal.extra.append(ContentLine(name="X-WR-CALNAME", value="FedEx Training Schedule"))
        cal.extra.append(ContentLine(name="X-WR-TIMEZONE", value=("UTC" if export_utc else tz_str)))
        cal.extra.append(ContentLine(name="X-PUBLISHED-TTL", value="PT1H"))
    except Exception:
        pass

    starts_dt = []
    ends_dt = []

    for activity, date_str, start_str, end_str, location, notes in events:
        start_dt = parse_datetime(date_str, start_str, tz_str)
        end_dt = parse_datetime(date_str, end_str, tz_str)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # handle cross-midnight

        # Optional UTC export for maximum interop
        if export_utc:
            start_out = start_dt.astimezone(ZoneInfo("UTC"))
            end_out = end_dt.astimezone(ZoneInfo("UTC"))
        else:
            start_out = start_dt
            end_out = end_dt

        e = Event()
        e.name = activity
        e.begin = start_out
        e.end = end_out
        e.location = location
        e.description = notes

        # Stable UID → re-import updates instead of duplicates
        uid_key = f"{activity}|{start_dt.isoformat()}|{end_dt.isoformat()}|{location}"
        e.uid = sha1(uid_key.encode()).hexdigest() + "@fdx-cal-app"
        now_utc = datetime.now(tz=ZoneInfo("UTC"))
        e.created = now_utc
        e.last_modified = now_utc

        cal.events.add(e)

        starts_dt.append(start_dt)
        ends_dt.append(end_dt)

    first = min(starts_dt)
    last = max(ends_dt)
    if first.year == last.year and first.month == last.month:
        month_str = f"{first:%Y-%m}"
    else:
        month_str = f"{first:%Y-%m}_to_{last:%Y-%m}"
    filename = f"training_schedule_{month_str}.ics"
    return filename, cal