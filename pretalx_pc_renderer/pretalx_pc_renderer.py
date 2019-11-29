#! /usr/bin/env python3

import argparse
import jinja2
import json
import math
import os.path
import re
import sys

# Define Jinja2 Environment with LaTeX escaping
def escape_tex(value, linebreaks=False):
    latex_subs = [
        (re.compile(r'\\'), r'\\textbackslash'),
        (re.compile(r'([{}_#%&$])'), r'\\\1'),
        (re.compile(r'~'), r'\~{}'),
        (re.compile(r'\^'), r'\^{}'),
        (re.compile(r'"'), r"''"),
    ]
    if linebreaks:
        latex_subs.append((re.compile(r'\n'), r'\\\\'))

    result = str(value)
    for pattern, replacement in latex_subs:
        result = pattern.sub(replacement, result)
    return result


def update_submission(submission, review):
    if not review.get("score", None):
        # reviews do not necessarily have a score, for example by reviewers with a conflict of interest
        return submission
    if submission["review_count"] == 0:
        submission["average_score"] = float(review["score"])
    else:
        submission["average_score"] = (float(review["score"]) + submission["review_count"] * submission["average_score"]) / (submission["review_count"] + 1)
    submission["review_count"] += 1
    return submission


SUPPORTED_FORMATS = ("tex", "txt")

parser = argparse.ArgumentParser(description="Convert Pretalx JSON exports to various useful formats")
parser.add_argument("-f", "--format", help="output format", type=str)
parser.add_argument("-l", "--locale", help="Pretalx locale used as main language to name tracks, submission types etc.", type=str, default="en")
parser.add_argument("-m", "--max-score", help="maximum score (configured in Pretalx review settings)", type=int, required=True)
parser.add_argument("--min-score", help="minimum score (configured in Pretalx review settings)", type=int, default=0)
parser.add_argument("--max-reviews", help="maximum number of reviews to print (use -1 for unlimited)", type=int, default=-1)
parser.add_argument("--order-by", help="oder by one of the following fields: slug, title, average_score", type=str, default="code")
parser.add_argument("-o", "--output-filename", help="output filename", type=str, required=True)
parser.add_argument("-r", "--reviews", help="reviews JSON file", type=str)
parser.add_argument("-t", "--type-only", help="write only the following session type", type=str, default="all")
parser.add_argument("-T", "--track", help="write only the following track", type=str)
parser.add_argument("submissions", help="submissions JSON file")
parser.add_argument("template", help="template file")
args = parser.parse_args()

if args.format not in SUPPORTED_FORMATS:
    sys.stderr.write("Unkown output format {}\n".format(args.format))

# build dict of submissions
submissions = {}
with open(args.submissions, "r") as submissions_file:
    submissions_raw = json.load(submissions_file)
    if submissions_raw["count"] == 0:
        sys.stderr.write("ERROR: Submissions file is empty.\n")
        exit(1)
    for s in submissions_raw["results"]:
        s["average_score"] = 0.0
        s["review_count"] = 0
        s["reviews"] = []
        s["speaker_names"] = ", ".join([x["name"] for x in s["speakers"]])
        # calculate how many reviews to print per talk
        #TODO move to template
        #s["print_reviews_count"] = 8 - int(len(s["title"]) / 32) - math.floor(len(speaker_names) / 55)
        submissions[s["code"]] = s

# add reviews
if args.reviews:
    with open(args.reviews, "r") as reviews_file:
        reviews_raw = json.load(reviews_file)
        if reviews_raw["count"] == 0:
            sys.stderr.write("ERROR: Reviews file is empty.\n")
            exit(1)
        for r in reviews_raw["results"]:
            if r["submission"] not in submissions:
                # Pretalx bug #689: reviews API returns reviews of deleted submissions
                continue
            submission = submissions[r["submission"]]
            name_parts = r["user"].strip().split(" ")
            if len(name_parts) == 0:
                r["name_parts"] = ["?"]
            else:
                r["name_parts"] = name_parts
            r["text_length"] = len(r.get("text", ""))
            r["text"] = r["text"].replace("\r\n", "\n").replace("\n\n", " ")
            submission["reviews"].append(r)
            submissions[r["submission"]] = update_submission(submission, r)

submissions_list = []
for code, s in submissions.items():
    # filter out withdrawn submissions
    if s["state"] == "withdrawn":
        continue
    #TODO move to template
    #s["average_score_rounded"] = int(round(s["average_score"] * 2, 0))
    submissions_list.append(s)

submissions_list = list(filter(lambda s: s["state"] != "withdrawn", submissions_list))
if args.type_only != "all":
    submissions_list = list(filter(lambda s: s["submission_type"][args.locale] == args.type_only, submissions_list))
if args.track:
    submissions_list = list(filter(lambda s: s["track"][args.locale] == args.track, submissions_list))
if len(submissions_list) == 0:
    sys.stderr.write("WARNING: No submissions left after filtering\n")
submissions_list.sort(key=lambda s: s["{}".format(args.order_by)])
 
template_directory = os.path.dirname(os.path.abspath(args.template))
if args.format == "tex":
    jinja2_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_directory),
        block_start_string='((%',
        block_end_string='%))',
        variable_start_string='(((',
        variable_end_string=')))',
        comment_start_string='((#',
        comment_end_string='#))',
        undefined=jinja2.StrictUndefined
    )
    jinja2_env.filters['e'] = escape_tex
elif args.output_format == "txt":
    jinja2_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_directory),
        undefined=jinja2.StrictUndefined
    )

template = jinja2_env.get_template(args.template)
with open(args.output_filename, "w") as outfile:
    outfile.write(template.render(talks=submissions_list, max_score=args.max_score, locale=args.locale))
