#! /usr/bin/env python3

import argparse
import datetime
import jinja2
import json
import logging
import os
import pytz
import sys

from schedule_renderer.day import Day
from schedule_renderer.room import Room
from schedule_renderer.slot import Slot
from schedule_renderer.session import Session, ContinuedSession, Break, ExtraSession

PRETALX_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"
OUTPUT_TIME_FMT = "%H:%M"


def objtype(o):
    return type(o)


def transform_pretalx_date(d):
    """Remove last colon."""
    return d[:22] + d[-2:]


def url_to_code(u):
    parts = u.split("/")
    if parts[-1] == "":
        parts = parts[:-1]
    return parts[-1]


def read_datetime(d):
    return datetime.datetime.strptime(transform_pretalx_date(d), PRETALX_DATE_FMT)


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

config = {"no_video_rooms": [], "timezone": "UTC", "break_min_threshold": 10, "max_length": 240, "extra_sessions": []}
if args.config:
    config.update(json.load(args.config))

event_timezone = pytz.timezone(config["timezone"])

talks = json.load(args.input_file)["results"]
# Drop talks without day and room.
talks = [ t for t in talks if t.get("room") and t.get("start") ]

if args.confirmed_only:
    talks = [ t for t in talks if t["state"] == "confirmed" ]

rooms_raw = json.load(args.rooms_file)["results"]

# preprocess rooms
rooms = {}
for r in rooms_raw:
    video = r["name"][args.locale] in config["video_rooms"]
    rooms[r["id"]] = Room.build(r, args.locale, video)

days = []

# add session codes
if args.editor_api:
    for t in talks:
        t["code"] = url_to_code(t["url"])

# Go through talks and look which days and start times we have
for t in talks:
    talk_day = read_datetime(t["start"])
    day_found = False
    for d in days:
        if d.is_same_day(talk_day):
            day_found = True
            d.add_room(rooms[t["room"]])
            break
    if not day_found:
        days.append(Day(talk_day, rooms[t["room"]]))

# Do the same for extra sessions (from config file)
extra_sessions = ExtraSession.import_config(config["extra_sessions"], args.locale, rooms)
for es in extra_sessions:
    talk_day = es.start
    day_found = False
    for d in days:
        if d.is_same_day(talk_day):
            day_found = True
            d.add_room(es.room)
            break
    if not day_found:
        days.append(Day(talk_day, es.room))

days.sort(key=lambda d: d.date)

# Go through talks and look for sessions
sessions = []
for t in talks:
    sessions.append(Session(rooms[t["room"]], t))

sessions += Break.import_config(config["breaks"], days, args.locale)
sessions += extra_sessions

# sort slots
sessions.sort(key=lambda s : (s.start, s.end))

# look when sessions start
sessions_starts = []
i = 0
while i < len(sessions):
    s = sessions[i]
    if len(sessions_starts) == 0:
        sessions_starts.append(Slot(s.start, s.end))
        i += 1
        continue
    if sessions_starts[-1].start < s.start:
        sessions_starts.append(Slot(s.start, s.end))
    elif sessions_starts[-1].start == s.start and sessions_starts[-1].end < s.end:
        sessions_starts.append(Slot(s.start, s.end))
    i += 1

# find overlapping slots
sessions_starts.sort(key=lambda k: (k.start, k.end))
i = 0
tmp_sessions_times = [ s.start for s in sessions_starts ] + [ s.end for s in sessions_starts ]
tmp_sessions_times.sort()

# deduplicate
sessions_times = []
for i in range(0, len(tmp_sessions_times)):
    if i == 0:
        sessions_times.append(tmp_sessions_times[0])
        continue
    if tmp_sessions_times[i] > tmp_sessions_times[i-1]:
        sessions_times.append(tmp_sessions_times[i])

# build slots
sessions_starts = []
for i in range(0, len(sessions_times) - 1):
    if sessions_times[i+1] - sessions_times[i] > datetime.timedelta(minutes=config["max_length"]):
        continue
    sessions_starts.append(Slot(sessions_times[i], sessions_times[i+1]))

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
    # if the session is longer than one slot, add it to all later slots it spans over
    if s.row_count > 1:
        for i in range(slot_index + 1, len(sessions_starts)):
            if sessions_starts[i].start < s.end:
                sessions_starts[i].add_session(ContinuedSession(s.start, s.end, s.room))

# remove slots without content to be rendered
sessions_starts = [ s for s in sessions_starts if s.rendering_required() ]

# update row counts
for i in range(0, len(sessions_starts)):
    current_slot = sessions_starts[i]
    for s in current_slot.sessions:
        if s.render_content and not s.is_break and s.end > current_slot.end:
            # look for index of last slot it belongs to
            for j in range(i+1, len(sessions_starts)):
                if sessions_starts[j].start >= s.end:
                    s.row_count = j - i
                    break

# update row counts for sessions spreading over multiple slots

# Sort rooms per day
for d in days:
    d.sort_rooms()

# sort sessions in slots by room and fill gaps
for s in sessions_starts:
    for d in days:
        if d.is_same_day(s.start):
            s.fill_gaps(d)


template_searchpath = os.path.dirname(os.path.abspath(args.template))
env_table = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=template_searchpath),
                         trim_blocks=True,
                         autoescape=True
                         )
env_table.filters["weekday"] = Day.weekday
env_table.filters["equal_day"] = equal_day
env_table.filters["type"] = objtype 
schedule_tmpl_file = os.path.basename(os.path.abspath(args.template))
template_table = env_table.get_template(schedule_tmpl_file)
result = template_table.render(days=days, slots=sessions_starts, right_time=False, timezone=event_timezone)
args.output_file.write(result)
