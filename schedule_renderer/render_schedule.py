#! /usr/bin/env python3

import argparse
import datetime
import jinja2
import json
import locale
import logging
import markdown
import os
import pytz
import sys

from schedule_renderer.day import Day
from schedule_renderer.room import Room
from schedule_renderer.slot import Slot
from schedule_renderer.session import Session, ContinuedSession, Break, ExtraSession, escape_yaml_value_quote

PRETALX_DATE_FMT = "%Y-%m-%dT%H:%M:%S%z"
OUTPUT_TIME_FMT = "%H:%M"


def objtype(o):
    return type(o)


def transform_pretalx_date(d):
    """Remove last colon."""
    return d[:22] + d[-2:]


def read_datetime(d):
    return datetime.datetime.strptime(transform_pretalx_date(d), PRETALX_DATE_FMT)


def equal_day(d1, d2):
    return d1.year == d2.year and d1.month == d2.month and d1.day == d2.day


def get_speakers_from_submissions(submissions_file, talks):
    submissions = json.load(submissions_file)["results"]
    submissions = [ s for s in submissions if s.get("state") in ["accepted", "confirmed"] ]
    for s in submissions:
        for sp in s["speakers"]:
            for i in range(0, len(talks)):
                for j in range(0, len(talks[i]["speakers"])):
                    if talks[i]["speakers"][j]["name"] == sp["name"]:
                        talks[i]["speakers"][j] = sp
    return talks


logging.basicConfig(level=logging.INFO, format='%(message)s', datefmt=None)

parser = argparse.ArgumentParser(description="Generate a schedule from a Pretalx JSON export")
parser.add_argument("-c", "--config", type=argparse.FileType("r"), help="configuration file")
parser.add_argument("--confirmed-only", action="store_true", help="confirmed talks only")
parser.add_argument("--editor-api", action="store_true", help="talks JSON file is from the internal API used by the schedule editor, not from the public API")
parser.add_argument("-l", "--locale", type=str, help="locale, e.g. de_DE", default="en_EN")
parser.add_argument("--no-abstracts", action="store_true", help="don't render abstract detail pages")
parser.add_argument("-s", "--speakers", type=argparse.FileType("r"), help="JSON file from /speakers API endpoint")
parser.add_argument("--submissions", type=argparse.FileType("r"), help="JSON file from /submissions API endpoint. Required if --editor-api is used.")
parser.add_argument("--time-from", type=str, help="Render events only after this, format: YYYY-MM-DD HH:MM")
parser.add_argument("--time-to", type=str, help="Render events only until this time, format: YYYY-MM-DD HH:MM")
parser.add_argument("rooms_file", type=argparse.FileType("r"), help="rooms export of /rooms API enpoint")
parser.add_argument("input_file", type=argparse.FileType("r"), help="input file (talks JSON file or /talks API endpoint)")
parser.add_argument("template", type=str, help="template file")
parser.add_argument("output_file", type=argparse.FileType("w"), help="HTML output file")
parser.add_argument("abstract_template", type=str, help="template file for abstracts")
parser.add_argument("abstracts_out_dir", type=str, help="output directory for abstracts")
args = parser.parse_args()

if args.editor_api and not args.submissions:
    logging.error("--editor-api needs to be called with --submissions")
    exit(1)

pretalx_locale = args.locale.split("_")
if len(pretalx_locale) < 1 or len(pretalx_locale) > 2:
    # We accept a single "en" as well.
    logging.error("locale is invalid, please use the following format: de_DE (got: {})".format(args.locale))
    exit(1)
pretalx_locale = pretalx_locale[0]
locale.setlocale(locale.LC_TIME, args.locale)

config = {"no_video_rooms": [], "timezone": "UTC", "break_min_threshold": 10, "max_length": 240, "extra_sessions": [], "no_abstract_for": [], "attachment_subdirectory": "/attachments", "pretalx_url_prefix": "https://pretalx.com/"}
if args.config:
    config.update(json.load(args.config))

event_timezone = pytz.timezone(config["timezone"])

talks = json.load(args.input_file)["results"]
# Drop talks without day and room.
if args.editor_api:
    talks = [ t for t in talks if t.get("room") and t.get("start") ]
    # load submissions and apply speaker codes
    talks = get_speakers_from_submissions(args.submissions, talks)
else:
    talks = [ t for t in talks if t.get("slot") and t.get("slot").get("start") and t.get("slot").get("room") ]

if args.confirmed_only:
    talks = [ t for t in talks if t["state"] == "confirmed" ]

rooms_raw = json.load(args.rooms_file)["results"]

# preprocess rooms
rooms = {}
rooms_by_name = {}
for r in rooms_raw:
    video = r["name"][pretalx_locale] in config["video_rooms"]
    rooms[r["id"]] = Room.build(r, pretalx_locale, video)
    rooms_by_name[r["name"][pretalx_locale]] = rooms[r["id"]]

days = []

# Move start and end of slot if not using data from editor API
if not args.editor_api:
    for i in range(0, len(talks)):
        t = talks[i]
        if not args.editor_api:
            t["start"] = t["slot"]["start"]
            t["end"] = t["slot"]["end"]
            t["room"] = rooms_by_name[t["slot"]["room"][pretalx_locale]].id

# Remove talks not matching the time filters
TIME_FORMAT = "%Y-%m-%d %H:%M"
if args.time_from:
    time_from = event_timezone.localize(datetime.datetime.strptime(args.time_from, TIME_FORMAT))
    talks = [ t for t in talks if read_datetime(t["end"]) >= time_from ]
if args.time_to:
    time_to = event_timezone.localize(datetime.datetime.strptime(args.time_to, TIME_FORMAT))
    talks = [ t for t in talks if read_datetime(t["start"]) <= time_to ]

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
extra_sessions = ExtraSession.import_config(config["extra_sessions"], pretalx_locale, rooms)
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
    sessions.append(Session(rooms[t["room"]], t, pretalx_locale, config["pretalx_url_prefix"]))

# load speaker details
if args.speakers:
    speakers_raw = json.load(args.speakers)["results"]
    speakers = { s["code"]:s for s in speakers_raw }
    for s in sessions:
        s.add_speaker_details(speakers, pretalx_locale)

# add affilations to speaker names for output
for s in sessions:
    s.set_speaker_names(config.get("affiliation_question_id"))

sessions += Break.import_config(config["breaks"], days, pretalx_locale)
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

# build URLs for attachments of sessions
for s in sessions:
    for r in s.resources:
        r.set_href(config["attachment_subdirectory"])

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
result = template_table.render(days=days, slots=sessions_starts, right_time=False, timezone=event_timezone, no_abstract_for=config["no_abstract_for"])
args.output_file.write(result)

abstract_template_searchpath = os.path.dirname(os.path.abspath(args.abstract_template))
# no escaping because it is handled by the markdown module and Jekyll
env_abstr = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=abstract_template_searchpath),
                               trim_blocks=True,
                               autoescape=False)
env_abstr.filters["weekday"] = Day.weekday
env_abstr.filters["equal_day"] = equal_day
env_abstr.filters["e"] = escape_yaml_value_quote
abstr_tmpl_file = os.path.basename(os.path.abspath(args.abstract_template))
template_abstr = env_abstr.get_template(abstr_tmpl_file)
if not args.no_abstracts:
    for t in sessions:
        if not t.is_break and t.render_abstract and t.code not in config["no_abstract_for"]:
            sys.stderr.write("rendering abstract of {} {}\n".format(t.code, t.title))
            outfile_path = os.path.join(args.abstracts_out_dir, t.code) + ".html"
            with open(outfile_path, "w") as abstr_file:
                abstr_file.write(template_abstr.render(session=t, video_rooms=config["video_rooms"], short_description_html=markdown.markdown(t.short_abstract), description_html=markdown.markdown(t.long_abstract)))
