import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from hashlib import sha1
from typing import List, Tuple, Optional

# ------------------------------
# Defaults
# ------------------------------
DEFAULT_TZ = "America/Chicago"

# Both parsers do some pairwise work per day (brief/debrief pairing, crew
# de-duplication), so an unbounded event count is a CPU sink on a public
# endpoint. A full year of real schedule is a few hundred events.
MAX_EVENTS = 2000


class ScheduleTooLarge(ValueError):
    """Raised when input exceeds what these endpoints will process."""

DAY_HEADER_RE = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)(day)?$", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{2}[A-Za-z]{3}\d{2}$")
TIME_RANGE_RE = re.compile(r"^(\d{2}:\d{2}L)\s*/\s*(\d{2}:\d{2}L)$")

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

def _name_tokens(s: str) -> List[str]:
    """Return uppercase alpha tokens for name matching."""
    return re.findall(r"[A-Z]{2,}", s.upper())


def _excluded_name_sets(exclude_names: List[str]) -> List[set[str]]:
    return [set(tokens) for name in exclude_names if (tokens := _name_tokens(name))]


def _matches_excluded_name(candidate: str, excluded_names: List[set[str]]) -> bool:
    candidate_tokens = set(_name_tokens(candidate))
    if not candidate_tokens:
        return False
    return any(excluded_name.issubset(candidate_tokens) for excluded_name in excluded_names)


def is_day_header(text: str) -> bool:
    return bool(text and DAY_HEADER_RE.match(text.strip()))


def is_date_header(text: str) -> bool:
    return bool(text and DATE_RE.match(text.strip()))


def is_time_range(text: str) -> bool:
    return bool(text and TIME_RANGE_RE.match(text.strip()))


@dataclass(frozen=True)
class SerializedCalendar:
    content: str

    def serialize(self) -> str:
        return self.content


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
    excluded_names = _excluded_name_sets(exclude_names)
    events = []
    i = 0

    while i < len(lines):
        if is_day_header(lines[i]) and i + 1 < len(lines) and is_date_header(lines[i + 1]):
            i += 1

        if not is_date_header(lines[i]):
            i += 1
            continue

        date = lines[i]
        i += 1

        day_events = []
        while i < len(lines) and not is_date_header(lines[i]) and not is_day_header(lines[i]):
            if is_time_range(lines[i]):
                event, new_i = parse_single_event(lines, i, date, excluded_names)
                if event:
                    day_events.append(event)
                    if len(events) + len(day_events) > MAX_EVENTS:
                        raise ScheduleTooLarge(
                            "That schedule has more than %d events. "
                            "Please export a shorter date range." % MAX_EVENTS
                        )
                i = new_i
            else:
                i += 1

        events.extend(group_brf_dbrf_events(day_events))

    return events


def parse_single_event(
    lines: List[str], start_i: int, date: str, excluded_names: List[set[str]]
) -> Tuple[Optional[Tuple[str, str, str, str, str, List[str]]], int]:
    """Parse a single time block and return ((activity,date,start,end,location,crew_list), next_index)."""
    i = start_i

    time_match = TIME_RANGE_RE.match(lines[i])
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

    while (
        i < len(lines)
        and not is_time_range(lines[i])
        and not is_day_header(lines[i])
        and not is_date_header(lines[i])
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
                and not is_time_range(lines[i])
                and not is_day_header(lines[i])
                and not is_date_header(lines[i])
                and not is_location(lines[i])
                and not is_crew_role(lines[i])
            ):
                name = lines[i].strip()
                crew_entry = f"{role}: {name}"
                if not _matches_excluded_name(name, excluded_names):
                    crew_list.append(crew_entry)
                i += 1
            else:
                crew_list.append(role)
        else:
            i += 1

    return (activity, date, start_time, end_time, location, crew_list), i


def _activity_rank(event: Tuple[str, str, str, str, str, List[str]]) -> Tuple[int, int, int, int]:
    activity, _, _, _, location, crew_list = event
    activity_upper = activity.upper()
    observerish = activity_upper.endswith(" OBS") or " OBS " in activity_upper
    return (
        0 if observerish else 1,
        1 if location else 0,
        len(crew_list),
        1 if re.search(r"\d", activity_upper) else 0,
    )


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

        if activity.upper() == 'BRF':
            candidate_events: List[Tuple[str, str, str, str, str, List[str]]] = []
            all_crew = crew_list.copy()
            final_end_time = end_time
            j = i + 1
            while j < len(events):
                next_activity, next_date, next_start, next_end, next_location, next_crew = events[j]
                if next_activity.upper() == 'BRF' or next_date != date:
                    break
                if next_activity.upper() != 'DBRF':
                    candidate_events.append(events[j])
                all_crew.extend(next_crew)
                final_end_time = next_end
                if next_activity.upper() == 'DBRF':
                    j += 1
                    break
                j += 1

            if candidate_events:
                main_activity, _, _, _, main_location, _ = max(candidate_events, key=_activity_rank)
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

VTIMEZONE_CHICAGO = [
    "BEGIN:VTIMEZONE",
    "TZID:America/Chicago",
    "X-LIC-LOCATION:America/Chicago",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:-0600",
    "TZOFFSETTO:-0500",
    "TZNAME:CDT",
    "DTSTART:19700308T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:-0500",
    "TZOFFSETTO:-0600",
    "TZNAME:CST",
    "DTSTART:19701101T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def _format_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _format_utc_stamp(value: datetime) -> str:
    return value.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")


def _format_central_stamp(value: datetime) -> str:
    return value.astimezone(ZoneInfo(DEFAULT_TZ)).strftime("%Y%m%dT%H%M%S")


def _fold_ics_line(line: str, limit: int = 75) -> List[str]:
    if len(line) <= limit:
        return [line]

    folded = []
    remaining = line
    while len(remaining) > limit:
        folded.append(remaining[:limit])
        remaining = " " + remaining[limit:]
    folded.append(remaining)
    return folded

def generate_ics(
    events: List[Tuple[str, str, str, str, str, str]],
    tz_str: str = DEFAULT_TZ,
    export_utc: bool = False,
) -> Tuple[str, SerializedCalendar]:
    """Generate an ICS calendar encoded in Memphis local time."""
    if not events:
        raise ValueError("No events provided")

    # The source schedule is always listed in Memphis local time.
    tz_str = DEFAULT_TZ

    starts_dt = []
    ends_dt = []
    now_utc = datetime.now(tz=ZoneInfo("UTC"))
    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//fdx-cal-app//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:FedEx Training Schedule",
        f"X-WR-TIMEZONE:{DEFAULT_TZ}",
        "X-PUBLISHED-TTL:PT1H",
        *VTIMEZONE_CHICAGO,
    ]

    for activity, date_str, start_str, end_str, location, notes in events:
        start_dt = parse_datetime(date_str, start_str, tz_str)
        end_dt = parse_datetime(date_str, end_str, tz_str)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # handle cross-midnight

        # Stable UID → re-import updates instead of duplicates
        uid_key = f"{activity}|{start_dt.isoformat()}|{end_dt.isoformat()}|{location}"
        uid = sha1(uid_key.encode()).hexdigest() + "@fdx-cal-app"

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_format_utc_stamp(now_utc)}",
            f"CREATED:{_format_utc_stamp(now_utc)}",
            f"LAST-MODIFIED:{_format_utc_stamp(now_utc)}",
            f"DTSTART;TZID={DEFAULT_TZ}:{_format_central_stamp(start_dt)}",
            f"DTEND;TZID={DEFAULT_TZ}:{_format_central_stamp(end_dt)}",
            f"SUMMARY:{_format_ics_text(activity)}",
        ]
        if location:
            event_lines.append(f"LOCATION:{_format_ics_text(location)}")
        if notes:
            event_lines.append(f"DESCRIPTION:{_format_ics_text(notes)}")
        event_lines.append("END:VEVENT")
        calendar_lines.extend(event_lines)

        starts_dt.append(start_dt)
        ends_dt.append(end_dt)

    first = min(starts_dt)
    last = max(ends_dt)
    if first.year == last.year and first.month == last.month:
        month_str = f"{first:%Y-%m}"
    else:
        month_str = f"{first:%Y-%m}_to_{last:%Y-%m}"
    filename = f"training_schedule_{month_str}.ics"
    calendar_lines.append("END:VCALENDAR")

    serialized_lines = []
    for line in calendar_lines:
        serialized_lines.extend(_fold_ics_line(line))

    if export_utc:
        # Kept for backward compatibility, but intentionally ignored.
        pass

    return filename, SerializedCalendar("\r\n".join(serialized_lines) + "\r\n")
