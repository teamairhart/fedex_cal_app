import pytest
from helpers import parse_schedule

def test_parse_schedule_basic():
    # A small sample schedule to test parsing
    sample_text = """
    Thu 28AUG25 06:00L / 08:00L BRF     Instr JONATHAN AIRHART
    CA PAUL TIMMS
    FO DEAN TOMLINSON
    08:00L / 12:00L AST 1 MEM AOTC MOD-C 2484 A/B76FPT1 Instr JONATHAN AIRHART
    CA PAUL TIMMS
    FO DEAN TOMLINSON
    12:00L / 12:30L DBRF    Instr JONATHAN AIRHART
    """

    events = parse_schedule(sample_text, [])

    # ✅ Ensure at least one event is parsed
    assert len(events) == 1

    activity, date, start, end, location, crew = events[0]

    # ✅ Verify fields
    assert activity == "AST 1"
    assert date == "28AUG25"
    assert start == "06:00L"
    assert end == "12:30L"
    assert "B76FPT1" in location

    # ✅ Check crew contains both CA and FO
    assert "CA PAUL TIMMS" in crew
    assert "FO DEAN TOMLINSON" in crew
