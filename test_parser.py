from helpers import parse_schedule, generate_ics

SAMPLE_WITH_DAY_HEADERS = """Tue
07Apr26
09:30L / 10:00L
IIT BRF
IIT
JONATHAN AIRHART
10:00L / 12:00L
BRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
MATT WADE
IIT Observer
JONATHAN AIRHART
12:00L / 16:00L
IIT OPS 1 OBS
IIT
JONATHAN AIRHART
12:00L / 16:00L
OPS 1
B76S5
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
MATT WADE
IIT Observer
JONATHAN AIRHART
16:00L / 16:30L
DBRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
MATT WADE
IIT Observer
JONATHAN AIRHART
Wed
08Apr26
09:30L / 10:00L
IIT BRF
IIT
JONATHAN AIRHART
10:00L / 12:00L
BRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
JOHN BOOKAS
IIT Observer
JONATHAN AIRHART
12:00L / 16:00L
OPS 2
B76S5
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
JOHN BOOKAS
IIT Observer
JONATHAN AIRHART
12:00L / 16:00L
IIT OPS 2 OBS
IIT
JONATHAN AIRHART
16:00L / 16:30L
DBRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
JOHN BOOKAS
IIT Observer
JONATHAN AIRHART
Thu"""


SAMPLE_WITHOUT_DAY_HEADERS = """07Apr26
09:30L / 10:00L
IIT BRF
IIT
JONATHAN AIRHART
10:00L / 12:00L
BRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
MATT WADE
IIT Observer
JONATHAN AIRHART
12:00L / 16:00L
IIT OPS 1 OBS
IIT
JONATHAN AIRHART
12:00L / 16:00L
OPS 1
B76S5
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
MATT WADE
IIT Observer
JONATHAN AIRHART
16:00L / 16:30L
DBRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
MATT WADE
IIT Observer
JONATHAN AIRHART
08Apr26
09:30L / 10:00L
IIT BRF
IIT
JONATHAN AIRHART
10:00L / 12:00L
BRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
JOHN BOOKAS
IIT Observer
JONATHAN AIRHART
12:00L / 16:00L
OPS 2
B76S5
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
JOHN BOOKAS
IIT Observer
JONATHAN AIRHART
12:00L / 16:00L
IIT OPS 2 OBS
IIT
JONATHAN AIRHART
16:00L / 16:30L
DBRF
CA
JASON WILLIAMS
FO
DENNIS HARRUP
INSTR
JOHN BOOKAS
IIT Observer
JONATHAN AIRHART"""


def test_parse_schedule_accepts_day_headers_or_bare_dates():
    with_day_headers = parse_schedule(SAMPLE_WITH_DAY_HEADERS, ["Jonathan Airhart"])
    without_day_headers = parse_schedule(SAMPLE_WITHOUT_DAY_HEADERS, ["Jonathan Airhart"])

    assert with_day_headers == without_day_headers
    assert [event[0] for event in with_day_headers] == ["IIT BRF", "OPS 1", "IIT BRF", "OPS 2"]

    ops_1 = with_day_headers[1]
    assert ops_1[1] == "07Apr26"
    assert ops_1[2] == "10:00L"
    assert ops_1[3] == "16:30L"
    assert ops_1[4] == "B76S5"
    assert "JASON WILLIAMS" in ops_1[5]
    assert "JONATHAN AIRHART" not in ops_1[5]


def test_excluding_one_person_does_not_drop_partial_name_matches():
    sample_text = """Tue
07Apr26
10:00L / 12:00L
OPS 1
B76S5
CA
JOHN WADE
FO
MATT WADE
INSTR
JANE SMITH"""

    events = parse_schedule(sample_text, ["John Wade"])

    assert len(events) == 1
    crew = events[0][5]
    assert "JOHN WADE" not in crew
    assert "MATT WADE" in crew
    assert "JANE SMITH" in crew

def test_timezone_support():
    """ICS output should preserve Memphis local time with an explicit TZID."""
    sample_text = """Mon
06Aug25
07:00L / 08:00L
AST 1
B76FPT1"""

    events = parse_schedule(sample_text, [])
    assert len(events) == 1

    filename, cal = generate_ics(events)
    ics_text = cal.serialize()

    assert filename.endswith('.ics')
    assert "X-WR-TIMEZONE:America/Chicago" in ics_text
    assert "BEGIN:VTIMEZONE" in ics_text
    assert "TZID:America/Chicago" in ics_text
    assert "DTSTART;TZID=America/Chicago:20250806T070000" in ics_text
    assert "DTEND;TZID=America/Chicago:20250806T080000" in ics_text
    assert "DTSTART:20250806T120000Z" not in ics_text
    assert "DTEND:20250806T130000Z" not in ics_text
