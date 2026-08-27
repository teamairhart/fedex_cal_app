"""Tests for the MINT CSV parser, mirroring real report structure with fictional crew."""

from helpers import generate_ics
from mint_parser import looks_like_mint_csv, parse_mint_csv

HEADER = "EVENT NAME;FACILITY;START;NAME;ROLE;PRIMARY PHONE"
TITLE_JUNK = (
    ";;;;;8/26/26 10:26 PM\n"
    "B757 IT CA/FO 03FEB2026 (1);;;;;\n"
    "DOE, JANE (1111111);;;;;3/8/26 6:00 AM\n"
)


def test_detection():
    assert looks_like_mint_csv(TITLE_JUNK + HEADER)
    assert not looks_like_mint_csv("Tue\n07Apr26\n10:00L / 12:00L\nOPS 1")


def test_brf_grouping_dbrf_dropped_and_phones_cleaned():
    text = TITLE_JUNK + HEADER + """
BRF;;3/8/26 6:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222 CELL
;;;DOE, JANE (1111111);INSTR;(555) 333-4444 CELL 1ST
MAN 5;B75S5;3/8/26 8:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222 CELL
;;;DOE, JANE (1111111);INSTR;(555) 333-4444 CELL#
DBRF;;3/8/26 12:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222 CELL
"""
    events = parse_mint_csv(text)
    assert len(events) == 1
    activity, date, start, end, location, crew = events[0]
    assert (activity, date, start, end, location) == ("MAN 5", "08Mar26", "06:00L", "12:00L", "B75S5")
    lines = crew.split("\n")
    assert lines[0] == "CA: ALEX SMITH (1000001) — (555) 111-2222"
    assert lines[1] == "INSTR: JANE DOE (1111111) — (555) 333-4444"
    assert len(lines) == 2  # suffix variants collapse into one line per person


def test_page_break_header_mid_crew():
    text = TITLE_JUNK + HEADER + """
BRF;;4/12/26 6:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222 CELL
MAN 4;B75S3;4/12/26 8:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222 CELL
""" + HEADER + """
;;;DOE, JANE (1111111);INSTR;(555) 333-4444 CELL
DBRF;;4/12/26 12:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222 CELL
"""
    events = parse_mint_csv(text)
    assert len(events) == 1
    assert events[0][0] == "MAN 4"
    assert "INSTR: JANE DOE (1111111)" in events[0][5]  # crew row after page header still attaches


def test_one_hour_brief_uses_actual_start():
    text = HEADER + """
BRF;;8/11/26 11:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222
ASV;MEM AOTC MOD-C 2461/B757FPT1;8/11/26 12:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222
DBRF;;8/11/26 4:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222
"""
    events = parse_mint_csv(text)
    assert len(events) == 1
    assert events[0][2] == "11:00L"
    assert events[0][3] == "16:00L"


def test_cross_midnight_block():
    # BRF 18:00 -> CMT2 20:00 (+4h = midnight); its DBRF lands on the NEXT day
    # and must be dropped without disturbing that day's real events.
    text = HEADER + """
BRF;;4/27/26 6:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222
CMT2;B76S5;4/27/26 8:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222
DBRF;;4/28/26 12:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222
BRF;;4/28/26 10:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222
OPS 4;B76S4;4/28/26 12:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222
DBRF;;4/28/26 4:00 PM;SMITH, ALEX (1000001);CA;(555) 111-2222
"""
    events = parse_mint_csv(text)
    assert [(e[0], e[1], e[2], e[3]) for e in events] == [
        ("CMT2", "27Apr26", "18:00L", "00:00L"),
        ("OPS 4", "28Apr26", "10:00L", "16:00L"),
    ]
    # generate_ics must roll the midnight end into the next day
    _, cal = generate_ics(events)
    assert "DTSTART;TZID=America/Chicago:20260427T180000" in cal.serialize()
    assert "DTEND;TZID=America/Chicago:20260428T000000" in cal.serialize()


def test_duplicate_events_merge_crew():
    text = HEADER + """
CQGS;MEM AOTC MOD-D 3006B;4/9/26 1:00 PM;SMITH, ALEX (1000001);FO;(555) 111-2222
CQGS;MEM AOTC MOD-D 3006B;4/9/26 1:00 PM;BROWN, PAT (1000002);CA;(555) 555-6666
CQGS;MEM AOTC MOD-D 3006B;4/9/26 1:00 PM;SMITH, ALEX (1000001);FO;(555) 111-2222
"""
    events = parse_mint_csv(text)
    assert len(events) == 1
    assert events[0][2] == "13:00L"
    assert events[0][3] == "17:00L"  # ground default 4h
    lines = events[0][5].split("\n")
    assert len(lines) == 2
    assert any("ALEX SMITH" in l for l in lines) and any("PAT BROWN" in l for l in lines)


def test_special_durations_and_skips():
    text = HEADER + """
SC FLY;;3/3/26 3:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222
TOUR;B76S1;6/30/26 8:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222
LMS ETOPS;;4/13/26 7:30 AM;SMITH, ALEX (1000001);CA;(555) 111-2222
B757 PEPP;B75S1;8/28/26 10:00 AM;SMITH, ALEX (1000001);INSTR;(555) 111-2222
B757 PEPP;B75S1;8/29/26 8:00 AM;SMITH, ALEX (1000001);INSTR;(555) 111-2222
"""
    events = parse_mint_csv(text)
    by_name = {(e[0], e[1]): (e[2], e[3]) for e in events}
    assert ("SC FLY", "03Mar26") not in by_name
    assert by_name[("TOUR", "30Jun26")] == ("08:00L", "10:00L")
    assert by_name[("LMS ETOPS", "13Apr26")] == ("07:30L", "08:30L")
    assert by_name[("B757 PEPP", "28Aug26")] == ("10:00L", "12:00L")  # off-grid start -> 2h
    assert by_name[("B757 PEPP", "29Aug26")] == ("08:00L", "12:00L")  # on-grid start -> 4h


def test_exclusion_keeps_non_instructing_roles():
    text = HEADER + """
MAN 1;B75S5;3/8/26 8:00 AM;DOE, JANE (1111111);INSTR;(555) 333-4444 CELL
;;;SMITH, ALEX (1000001);CA;(555) 111-2222
OPS 1;B75S5;3/9/26 8:00 AM;DOE, JANE (1111111);SUPPORT;(555) 333-4444 CELL
;;;SMITH, ALEX (1000001);CA;(555) 111-2222
OPS 2;B75S5;3/10/26 8:00 AM;DOE, JANE (1111111);IIT Observer;(555) 333-4444 CELL
;;;SMITH, ALEX (1000001);CA;(555) 111-2222
"""
    events = parse_mint_csv(text, ["Jane Doe"])
    crews = {e[0]: e[5] for e in events}
    assert "JANE DOE" not in crews["MAN 1"]  # instructing role -> excluded
    assert "SUPPORT: JANE DOE (1111111) — (555) 333-4444" in crews["OPS 1"]
    assert "IIT Observer: JANE DOE (1111111)" in crews["OPS 2"]
    assert all("ALEX SMITH" in crew for crew in crews.values())


def test_missing_phone_and_unparseable_name():
    text = HEADER + """
MAN 1;B75S5;3/8/26 8:00 AM;DOE, JANE;INSTR;
"""
    events = parse_mint_csv(text)
    assert events[0][5] == "INSTR: DOE, JANE"  # no ID to reformat, no phone to append


def test_continuation_start_rows_create_additional_sessions():
    # Small MINT exports list extra sessions of the same event as rows with a
    # new START but blank EVENT NAME/FACILITY, crew following underneath.
    text = HEADER + """
CQGS;MEM AOTC 2053;9/9/26 1:00 PM;SMITH, ALEX (1000001);FO;(555) 111-2222
;;;BROWN, PAT (1000002);CA;(555) 555-6666
;;9/21/26 1:00 PM;JONES, SAM (1000003);FO;(555) 777-8888
;;;WHITE, KIM (1000004);CA;(555) 999-0000
"""
    events = parse_mint_csv(text)
    assert [(e[0], e[1], e[2], e[3], e[4]) for e in events] == [
        ("CQGS", "09Sep26", "13:00L", "17:00L", "MEM AOTC 2053"),
        ("CQGS", "21Sep26", "13:00L", "17:00L", "MEM AOTC 2053"),  # name+facility inherited
    ]
    assert "PAT BROWN" in events[0][5] and "SAM JONES" not in events[0][5]
    assert "SAM JONES" in events[1][5] and "KIM WHITE" in events[1][5]


def test_international_phone_kept_verbatim():
    text = HEADER + """
CMT1;B76S2;8/29/26 8:00 AM;CRUZ, GLENN (1000005);CA;011+63-920-9893787 CELL
;;;SMITH, ALEX (1000001);FO;1 (555) 111-2222 CELL
"""
    events = parse_mint_csv(text)
    lines = events[0][5].split("\n")
    assert lines[0] == "CA: GLENN CRUZ (1000005) — 011+63-920-9893787"  # not squeezed into US format
    assert lines[1] == "FO: ALEX SMITH (1000001) — 1 (555) 111-2222"  # 11 digits kept verbatim too


def test_open_slot_renders_as_bare_slot_label():
    text = HEADER + """
OPS 1;B76S5;3/8/26 8:00 AM;SMITH, ALEX (1000001);CA;(555) 111-2222
;;;B767 SUPPORT CA, OPEN (0000013);SUPPORT;
"""
    events = parse_mint_csv(text)
    lines = events[0][5].split("\n")
    assert "SUPPORT: B767 SUPPORT CA" in lines
    assert not any("OPEN" in line or "0000013" in line for line in lines)
