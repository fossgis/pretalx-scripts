#! /usr/bin/env python3

import argparse
import datetime
import jinja2
import json
import logging
import os
import sys

from schedule_renderer.day import Day
from schedule_renderer.room import Room
from schedule_renderer.slot import Slot
from schedule_renderer.session import Session

PRETALX_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"
OUTPUT_TIME_FMT = "%H:%M"


def transform_pretalx_date(d):
    """Remove last colon."""
    return d[:22] + d[-2:]


def url_to_code(u):
    parts = u.split("/")
    if parts[-1] == "":
        parts = parts[:-1]
    return parts[-1]


def equal_day(d1, d2):
    return d1.year == d2.year and d1.month == d2.month and d1.day == d2.day


logging.basicConfig(level=logging.INFO, format='%(message)s', datefmt=None)

parser = argparse.ArgumentParser(description="Generate a schedule from a Pretalx JSON export")
parser.add_argument("-c", "--config", type=argparse.FileType("r"), help="configuration file")
parser.add_argument("--confirmed-only", action="store_true", help="confirmed talks only")
parser.add_argument("--editor-api", action="store_true", help="talks JSON file is from the internal API used by the schedule editor, not from the public API")
parser.add_argument("-l", "--locale", type=str, help="locale")
parser.add_argument("rooms_file", type=argparse.FileType("r"), help="rooms export of /rooms API enpoint")
parser.add_argument("input_file", type=argparse.FileType("r"), help="input file (talks JSON file or /talks API endpoint)")
parser.add_argument("template", type=str, help="template file")
parser.add_argument("output_file", type=argparse.FileType("w"), help="HTML output file")
args = parser.parse_args()

config = {"no_video_rooms": []}
if args.config:
    config.update(json.load(args.config))

talks = json.load(args.input_file)["results"]
# Drop talks without day and room.
talks = [ t for t in talks if t.get("room") and t.get("start") ]

if args.confirmed_only:
    talks = [ t for t in talks if t["state"] == "confirmed" ]

rooms_raw = json.load(args.rooms_file)["results"]

# preprocess rooms
rooms = {}
for r in rooms_raw:
    novideo = r["name"][args.locale] in config["no_video_rooms"]
    rooms[r["id"]] = Room.build(r, args.locale, novideo)

days = []

# add session codes
if args.editor_api:
    for t in talks:
        t["code"] = url_to_code(t["url"])

# set create string of speaker names separated by comma
for t in talks:
    t["speaker_names"] = ", ".join([ s["name"] for s in t["speakers"] ])

# Go through talks and look which days and start times we have
for t in talks:
    talk_day = datetime.datetime.strptime(transform_pretalx_date(t["start"]), PRETALX_DATE_FMT)
    day_found = False
    for d in days:
        if d.is_same_day(talk_day):
            day_found = True
            d.add_room(rooms[t["room"]])
            break
    if not day_found:
        days.append(Day(talk_day, rooms[t["room"]]))

days.sort(key=lambda d: d.date)

# Go through talks and look for sessions
sessions = []
for t in talks:
    sessions.append(Session(rooms[t["room"]], t))

# sort slots
sessions.sort(key=lambda s : (s.start, s.end))

# look when sessions start
sessions_starts = []
for s in sessions:
    if len(sessions_starts) == 0 or sessions_starts[-1].start < s.start:
        sessions_starts.append(Slot(s.start, s.end))
    if sessions_starts[-1].start <= s.start and sessions_starts[-1].end < s.end:
        # This is the case if two sessions s1 and s2 start at T but s1 ends at T+m but s2 at T+n
        # (n>m) without an existing session s3 starting at T+m.
        sessions_starts.append(Slot(sessions_starts[-1].end, s.end))


# set row count for sessions
slot_index = 0
for s in sessions:
    current_slot = sessions_starts[slot_index]
    # Go forward if session start is later
    if s.start > current_slot.start:
        for i in range(slot_index, len(sessions_starts)):
            if sessions_starts[i].start == s.start:
                slot_index = i
                current_slot = sessions_starts[i]
                break
    # count number of slots overlapping with this session
    next_later = slot_index + 1
    while True:
        if next_later >= len(sessions_starts):
            break
        if sessions_starts[next_later].start >= s.end:
            break
        next_later += 1
    s.row_count = next_later - slot_index
    current_slot.add_session(s)

# sort sessions in slots by room
#TODO add gaps
for s in sessions_starts:
    s.sort_sessions_and_fill_gaps()

template_searchpath = os.path.dirname(os.path.abspath(args.template))
env_table = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=template_searchpath),
                         trim_blocks=True,
                         autoescape=True
                         )
env_table.filters["weekday"] = Day.weekday
env_table.filters["equal_day"] = equal_day
schedule_tmpl_file = os.path.basename(os.path.abspath(args.template))
template_table = env_table.get_template(schedule_tmpl_file)
result = template_table.render(days=days, slots=sessions_starts, right_time=False)
args.output_file.write(result)
