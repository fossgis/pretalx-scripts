#! /usr/bin/env python3

import argparse
import csv
import datetime
import json
import sys


CET = datetime.timezone(offset=datetime.timedelta(hours=1), name="Europe/Berlin")
PRETALX_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
OUTPUT_DATE_FORMAT = "%d.%m.%Y %H:%M"

def talk_in_range(time_range, talk_slot):
    slot_start = datetime.datetime.strptime(talk_slot["start"], OUTPUT_DATE_FORMAT)
    return slot_start >= time_range[0] and slot_start <= time_range[1]


parser = argparse.ArgumentParser(description="Convert schedule JSON to CSV")
parser.add_argument("-a", "--all-in-one", help="one line per speaker and talk", action="store_true")
parser.add_argument("-A", "--all", help="include submissions without slots and rejected/cancelled submissions if not excluded by other filters", action="store_true")
parser.add_argument("-l", "--locale", type=str, help="locale of the event", required=True)
parser.add_argument("--no-repeat", help="don't repeat a speaker (just write a list of speakers, one speaker per line and one line per speaker)", action="store_true")
parser.add_argument("-q", "--question-answers", help="output answers by speakers on the questions asked in the CfP form", action="store_true")
parser.add_argument("-R", "--reviews-file", help="reviews JSON file", type=argparse.FileType("r"))
parser.add_argument("--rating", help="output rating (average and count)", action="store_true")
parser.add_argument("-s", "--state-only", help="only this state (e.g. 'submitted' or 'accepted')", type=str, default=None)
parser.add_argument("-t", "--type-only", help="only this submission type", type=str, default=None)
parser.add_argument("-f", "--date_from", help="start date YYYY-mm-dd")
parser.add_argument("-T", "--date_to", help="end date YYYY-mm-dd")
parser.add_argument("talks_file", help="JSON file with talks (/talks endpoint of Pretalx API or program editor JSON")
parser.add_argument("speakers_file", help="JSON file with speakers (/speakers endpoint of Pretalx API)")
parser.add_argument("csv_file", help="CSV output file")
args = parser.parse_args()

if args.rating and not args.reviews_file:
    sys.stderr.write("ERROR: reviews.json missing\n")
    exit(1)

talks = []
with open(args.talks_file, "r") as infile:
    talks = json.load(infile)["results"]

if not args.all:
    talks = [x for x in talks if x.get("slot", None) not in [None, []]]

# format dates
for t in talks:
    if args.all and t.get("slot") is None:
        t["slot"] = {"start": None, "end": None}
        continue
    for field in ["start", "end"]:
        m = datetime.datetime.strptime(t["slot"][field], PRETALX_DATE_FORMAT)
        m = m.astimezone(CET)
        if field == "start":
            t["slot"][field] = m.strftime("%d.%m.%Y %H:%M")
        else:
            t["slot"][field] = m.strftime("%H:%M")

# filter talks by date
if args.date_from and args.date_to:
    date_from = datetime.datetime.strptime(args.date_from, "%Y-%m-%d")
    date_to = datetime.datetime.strptime(args.date_to, "%Y-%m-%d")
    talks = [t for t in talks if talk_in_range((date_from, date_to), t["slot"])]

if args.state_only:
    talks = [t for t in talks if t["state"] == args.state_only]

if args.type_only:
    talks = [t for t in talks if t["submission_type"][args.locale] == args.type_only]

reviews = {}
if args.reviews_file:
    reviews_raw = json.load(args.reviews_file)["results"]
    # assign review data to talks
    for r in reviews_raw:
        if r["submission"] in reviews:
            reviews[r["submission"]].append(r)
        else:
            reviews[r["submission"]] = [r]
    for t in talks:
        reviews_this = reviews.get(t["code"])
        if reviews_this is not None:
            t["ratings_average"] = float(sum([r["score"] for r in reviews_this])) / len(reviews_this)
            t["ratings_count"] = len(reviews_this)

speakers_by_talk = {}
spakers = []
with open(args.speakers_file, "r") as infile:
    speakers = json.load(infile)["results"]

for s in speakers:
    for sub in s["submissions"]:
        talk_info = speakers_by_talk.get(sub, [])
        talk_info.append({"name": s["name"], "email": s["email"], "code": s["code"], "answers": s["answers"]})
        speakers_by_talk[sub] = talk_info

speakers_with_accepted_submissions = set()
for t in talks:
    try:
        speakers_this = speakers_by_talk[t["code"]]
    except KeyError as err:
        sys.stderr.write("Failed to find speaker of talk {} {}!\n".format(t["code"], t["title"]))
        continue
    for s in speakers_this:
        speakers_with_accepted_submissions.add(s["code"])
    if args.all_in_one:
        t["names"] = ", ".join([x["name"] for x in speakers_this])
        t["email"] = ",".join([x["email"] for x in speakers_this])
#       t.update(t["slot"])

speakers_for_output = set()
if args.no_repeat:
    if args.rating:
        sys.stderr.write("ERROR: Cannot write review information if submissions of a speaker are squashed into one line\n")
        exit(1)
    for submission_id, talk_info in speakers_by_talk.items():
        for s in talk_info:
            if s["code"] not in speakers_with_accepted_submissions:
                continue
            speakers_for_output.add((s["name"], s["email"]))
    with open(args.csv_file, "w") as outfile:
        writer = csv.writer(outfile, delimiter=";")
        writer.writerow(["name", "email"])
        for s in speakers_for_output:
            writer.writerow(list(s))
    sys.exit(0)

answered_questions_over_all_submissions = set()
if args.question_answers:
    for t in talks:
        for q in t.get("answers", []):
            answered_questions_over_all_submissions.add(q["question"]["id"])
    for s in speakers:
        for q in s.get("answers", []):
            answered_questions_over_all_submissions.add(q["question"]["id"])
answered_questions_over_all_submissions = list(answered_questions_over_all_submissions)

with open(args.csv_file, "w") as outfile:
    writer = csv.writer(outfile, delimiter=";")
    header_row = ["code", "names","email", "start", "end", "state", "submission_type", "title"]
    if args.rating:
        header_row.append("rating_average")
        header_row.append("rating_count")
    if args.question_answers:
        header_row += answered_questions_over_all_submissions
    writer.writerow(header_row)
    for t in talks:
        #if args.type_only is not None and args.type_only != t["state"]:
        #    continue
        if args.all_in_one:
            row = [
                t["code"],
                t["names"],
                t["email"],
                t["slot"]["start"],
                t["slot"]["end"],
                t["state"],
                t["submission_type"][args.locale],
                t["title"]
            ]
            if t.get("ratings_average") is not None:
                row.append("{:.2f}".format(t.get("ratings_average")))
                row.append(t.get("ratings_count"))
            else:
                row.append(None)
                row.append(None)
            if args.question_answers:
                answers = {q["question"]["id"]:q["answer"] for q in t["answers"]}
                # We have to check if the question is available in the talk dict because some questions are targeted to speakers only
                for q in answered_questions_over_all_submissions:
                    row.append(answers.get(q))
            writer.writerow(row)

        else:
            for s in speakers_by_talk[t["code"]]:
                #writer.writerow(t)
                row = [
                    t["code"],
                    s["name"],
                    s["email"],
                    t["slot"]["start"],
                    t["slot"]["end"],
                    t["state"],
                    t["submission_type"][args.locale],
                    t["title"]
                ]
                if args.rating:
                    if t.get("ratings_average") is not None:
                        row.append("{:.2f}".format(t.get("ratings_average")))
                        row.append(t.get("ratings_count"))
                    else:
                        row.append(None)
                        row.append(None)
                if args.question_answers:
                    answers = {q["question"]["id"]:q["answer"] for q in t["answers"]}
                    answers.update({q["question"]["id"]:q["answer"] for q in s["answers"] if q["question"]["target"] != "submission" or q["submission"] == t["code"]})
                    # We have to check if the question is available in the talk dict because some questions are targeted to speakers only
                    for q in answered_questions_over_all_submissions:
                        row.append(answers.get(q))
                writer.writerow(row)
