import pytest
from helpers import parse_schedule

def test_parse_schedule_basic():
    # A small sample schedule to test parsing (multi-line format)
    sample_text = """Thu
28Aug25
06:00L / 08:00L
BRF
INSTR
JONATHAN AIRHART
CA
PAUL TIMMS
FO
DEAN TOMLINSON
08:00L / 12:00L
AST 1
B76FPT1
INSTR
JONATHAN AIRHART
CA
PAUL TIMMS
FO
DEAN TOMLINSON
12:00L / 12:30L
DBRF
INSTR
JONATHAN AIRHART
CA
PAUL TIMMS
FO
DEAN TOMLINSON"""

    events = parse_schedule(sample_text, [])

    # ✅ Ensure at least one event is parsed
    assert len(events) == 1

    activity, date, start, end, location, crew = events[0]

    # ✅ Verify fields
    assert activity == "AST 1"
    assert date == "28Aug25"
    assert start == "06:00L"
    assert end == "12:30L"
    assert "B76FPT1" in location

    # ✅ Check crew contains both CA and FO
    assert "PAUL TIMMS" in crew
    assert "DEAN TOMLINSON" in crew
