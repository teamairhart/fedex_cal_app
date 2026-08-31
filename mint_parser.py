"""Parser for MINT "DAILY INSTRUCTIONAL EVENT/NOTES" CSV exports.

MINT (fedex.mint-online.com) exports a semicolon-delimited report with columns
EVENT NAME;FACILITY;START;NAME;ROLE;PRIMARY PHONE. The first row of each event
carries the event fields plus the first crew member; additional crew members
follow on rows whose first three columns are empty. Report-layout junk (title
rows, repeated page headers) is interleaved and must be skipped — a page header
can even split one event's crew rows.

The report contains only START times, so durations are reconstructed from the
schedule structure (see _event_duration) and DBRF rows are dropped entirely:
a calendar event runs from its BRF start to its activity's computed end.

parse_mint_csv() returns the same event tuples as helpers.parse_schedule(), so
everything downstream (generate_ics, previews) is shared with the legacy path.
"""

import csv
import io
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from helpers import MAX_EVENTS, ScheduleTooLarge, _excluded_name_sets, _matches_excluded_name

MINT_HEADER_MARKER = "EVENT NAME;FACILITY;START"
MINT_DATETIME_FMT = "%m/%d/%y %I:%M %p"

# Sim/classroom blocks start only on this 4-hour grid; anything else is a
# special session (e.g. PEPP squeezed before the noon block).
GRID_HOURS = {0, 4, 8, 12, 16, 20}

SKIP_EVENTS = {"SC FLY"}

# Roles that mean "present but not instructing": an excluded (own) name is
# still shown for these so the calendar owner can see what role they're in.
KEEP_EXCLUDED_ROLE_WORDS = ("OBSERVER", "CONDUCTOR", "MONITOR")

NAME_ID_RE = re.compile(r"^(?P<last>[^,]+?),\s*(?P<first>.+?)\s*\((?P<id>\d+)\)$")


def looks_like_mint_csv(text: str) -> bool:
    return MINT_HEADER_MARKER in text.upper()


def _clean_phone(raw: str) -> str:
    """Strip suffix noise ('CELL 1ST', 'MOBILE', ...) and normalize US numbers.

    The number always precedes the suffix, and suffixes can contain digits
    ('CELL#1', 'CELL1ST'), so take everything up to the first letter as the
    number. A 10-digit number is formatted (xxx) xxx-xxxx; anything else
    (e.g. international '011+63-920-9893787') is kept verbatim.
    """
    core = re.match(r"[\d\s()+.\-#/]*", (raw or "").strip()).group(0).strip(" -/#.")
    digits = re.sub(r"\D", "", core)
    if len(digits) < 7:
        return ""
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return core


def _format_person(raw_name: str) -> str:
    """'AKULSCHIN, JEFF (455561)' -> 'JEFF AKULSCHIN (455561)'.

    An unfilled slot ('B767 SUPPORT CA, OPEN (0000013)') renders as just the
    slot label with no placeholder name or ID.
    """
    match = NAME_ID_RE.match(raw_name.strip())
    if not match:
        return raw_name.strip()
    if match.group("first").upper() == "OPEN":
        return match.group("last")
    return f"{match.group('first')} {match.group('last')} ({match.group('id')})"


def _crew_line(role: str, raw_name: str, raw_phone: str) -> str:
    line = f"{role}: {_format_person(raw_name)}"
    phone = _clean_phone(raw_phone)
    return f"{line} — {phone}" if phone else line


def _role_keeps_excluded(role: str) -> bool:
    r = role.upper().strip()
    return r == "SUPPORT" or any(word in r for word in KEEP_EXCLUDED_ROLE_WORDS)


def _read_raw_events(text: str) -> List[Dict]:
    """Yield {name, facility, start, crew:[(person, role, phone)]} per event row group."""
    events: List[Dict] = []
    current: Optional[Dict] = None
    for row in csv.reader(io.StringIO(text), delimiter=";"):
        if len(row) != 6:
            continue
        ev_name, facility, start, person, role, phone = (col.strip() for col in row)
        if ev_name.upper() == "EVENT NAME":
            continue  # repeated page header; crew rows resume after it
        if start and (ev_name or current is not None):
            try:
                start_dt = datetime.strptime(start, MINT_DATETIME_FMT)
            except ValueError:
                continue
            if not ev_name:
                # Another session of the current event on a different date:
                # a start time with EVENT NAME (and usually FACILITY) blank.
                ev_name = current["name"]
                facility = facility or current["facility"]
            current = {"name": ev_name, "facility": facility, "start": start_dt, "crew": []}
            events.append(current)
            if len(events) > MAX_EVENTS:
                raise ScheduleTooLarge(
                    "That export has more than %d events. "
                    "Please download a shorter date range." % MAX_EVENTS
                )
            if person:
                current["crew"].append((person, role, phone))
        elif not ev_name and not start and person and current is not None:
            current["crew"].append((person, role, phone))
        # anything else is title/layout junk
    return events


def _merge_duplicates(events: List[Dict]) -> List[Dict]:
    """Merge events with identical (name, start, facility), combining crew.

    MINT lists an event once per trainee slot group (e.g. CQGS three times for
    the same room and time); the calendar wants one event with everyone on it.
    """
    merged: Dict[Tuple, Dict] = {}
    order: List[Tuple] = []
    for ev in events:
        key = (ev["name"].upper(), ev["start"], ev["facility"].upper())
        if key in merged:
            merged[key]["crew"].extend(ev["crew"])
        else:
            merged[key] = ev
            order.append(key)
    return [merged[key] for key in order]


def _event_duration(name: str, start: datetime) -> timedelta:
    upper = name.upper()
    if "LMS" in upper:
        return timedelta(hours=1)
    if upper == "TOUR":
        return timedelta(hours=2)
    if "PEPP" in upper and (start.hour not in GRID_HOURS or start.minute != 0):
        return timedelta(hours=2)
    return timedelta(hours=4)


def _brief_duration(start: datetime) -> timedelta:
    """Fallback for a BRF with no activity after it: even-hour briefs run 2h, odd 1h."""
    return timedelta(hours=2 if start.hour % 2 == 0 else 1)


def _group_events(raw_events: List[Dict]) -> List[Dict]:
    """Pair each BRF with the next activity that day, drop DBRFs, compute ends."""
    by_day = defaultdict(list)
    for ev in raw_events:
        by_day[ev["start"].date()].append(ev)

    grouped: List[Dict] = []
    for day in sorted(by_day):
        day_events = sorted(by_day[day], key=lambda ev: ev["start"])
        consumed = [False] * len(day_events)
        for idx, ev in enumerate(day_events):
            if consumed[idx]:
                continue
            upper = ev["name"].upper()
            if upper == "DBRF" or upper in SKIP_EVENTS:
                continue
            if upper == "BRF":
                target = None
                for j in range(idx + 1, len(day_events)):
                    next_upper = day_events[j]["name"].upper()
                    if consumed[j] or next_upper in ("BRF", "DBRF") or next_upper in SKIP_EVENTS:
                        continue
                    target = j
                    break
                if target is None:
                    grouped.append({
                        "name": ev["name"],
                        "facility": ev["facility"],
                        "start": ev["start"],
                        "end": ev["start"] + _brief_duration(ev["start"]),
                        "crew": list(ev["crew"]),
                    })
                    continue
                activity = day_events[target]
                consumed[target] = True
                grouped.append({
                    "name": activity["name"],
                    "facility": activity["facility"],
                    "start": ev["start"],
                    "end": activity["start"] + _event_duration(activity["name"], activity["start"]),
                    "crew": list(ev["crew"]) + list(activity["crew"]),
                })
            else:
                grouped.append({
                    "name": ev["name"],
                    "facility": ev["facility"],
                    "start": ev["start"],
                    "end": ev["start"] + _event_duration(ev["name"], ev["start"]),
                    "crew": list(ev["crew"]),
                })
    grouped.sort(key=lambda ev: ev["start"])
    return grouped


def _format_crew(crew: List[Tuple[str, str, str]], excluded_name_sets: List[set]) -> str:
    lines: List[str] = []
    seen = set()
    for person, role, phone in crew:
        if not person:
            continue
        if _matches_excluded_name(person, excluded_name_sets) and not _role_keeps_excluded(role):
            continue
        line = _crew_line(role, person, phone)
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join(lines)


def parse_mint_csv(
    text: str, exclude_names: Optional[List[str]] = None
) -> List[Tuple[str, str, str, str, str, str]]:
    """Parse a MINT CSV export into the same event tuples as parse_schedule()."""
    excluded_name_sets = _excluded_name_sets(exclude_names or [])
    raw_events = _read_raw_events(text)
    if not raw_events:
        return []
    grouped = _group_events(_merge_duplicates(raw_events))

    tuples = []
    for ev in grouped:
        tuples.append((
            ev["name"],
            ev["start"].strftime("%d%b%y"),
            ev["start"].strftime("%H:%M") + "L",
            ev["end"].strftime("%H:%M") + "L",  # generate_ics rolls past-midnight ends to the next day
            ev["facility"],
            _format_crew(ev["crew"], excluded_name_sets),
        ))
    return tuples
