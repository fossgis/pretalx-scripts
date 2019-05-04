#! /usr/bin/env python3

import argparse
import enum
import json
import math
from matplotlib import pyplot as plt
from matplotlib import ticker as mtpl_ticker
import os.path
import sys


class Task(enum.Enum):
    FD_PER_REVIEWER = "frequency_distribution_per_reviewer"
    REVIEW_COUNT_FD = "frequency_distribution_of_reviews_per_submission"

    def __str__(self):
        return self.value


def col_and_row(idx, row_width):
    return int(idx / row_width), idx % row_width


def frequency_distribution_per_reviewer():
    reviewers = {}
    # build lists of scores per reviewer
    for r in reviews:
        user = r.get("user")
        score = r.get("score")
        if user not in reviewers:
            reviewers[user] = [score]
        else:
            reviewers[user].append(score)
    num_reviewers = len(reviewers)
    rows = int(math.ceil(num_reviewers / 4.0))
    cols = 4
    fig, axes = plt.subplots(ncols=cols, nrows=rows)
    i = 0
    for name, scores in reviewers.items():
        col, row = col_and_row(i, cols)
        row = i % 4
        a = axes[col][row]
        a.hist(scores, [0, 1, 2, 3, 4], align="left", rwidth=0.5)
        a.set_xlabel("score")
        a.set_ylabel("count")
        a.get_yaxis().set_major_locator(mtpl_ticker.MaxNLocator(integer=True, nbins=4))
        a.get_xaxis().set_major_locator(mtpl_ticker.MaxNLocator(integer=True))
        if args.pseudonymous:
            a.set_title("R{}".format(i+1))
        else:
            a.set_title(name)
        i += 1
    for j in range(i, rows * cols):
        col, row = col_and_row(j, cols)
        fig.delaxes(axes[col][row])
    fig.tight_layout()
    fig.savefig(args.plot_outfile, format=os.path.splitext(args.plot_outfile.name)[1][1:])


def review_count_frequency_dist():
    if not args.submissions:
        sys.stderr.write("ERROR: missing submissions input file\n")
        exit(1)
    s = json.load(args.submissions)["results"]
    submissions = {v["code"]:0 for v in s if v["state"] in ["submitted", "accepted", "confirmed", "rejected"]}
    for r in reviews:
        if r["submission"] in submissions:
            submissions[r["submission"]] += 1
    numbers = [v for k, v in submissions.items()]
    fig, ax = plt.subplots(ncols=1, nrows=1)
    ax.hist(numbers, range(0, max(numbers)), align="left", rwidth=0.5)
    ax.set_xlabel("reviews")
    ax.set_ylabel("count")
    ax.get_yaxis().set_major_locator(mtpl_ticker.MaxNLocator(steps=(1, 5, 10)))
    ax.get_xaxis().set_major_locator(mtpl_ticker.MaxNLocator(integer=True))
    fig.savefig(args.plot_outfile, format=os.path.splitext(args.plot_outfile.name)[1][1:])


parser = argparse.ArgumentParser(description="Analyse reviews")
parser.add_argument("-p", "--pseudonymous", action="store_true", help="pseudonymous output")
parser.add_argument("-P", "--plot-outfile", required=True, help="plot frequency distribution graphs to file", type=argparse.FileType("wb"))
parser.add_argument("-s", "--submissions", help="submissions export from Pretalx API as JSON", type=argparse.FileType("r"))
parser.add_argument("-t", "--task", required=True, help="task", type=Task, choices=list(Task))
parser.add_argument("reviews_file", help="reviews JSON file", type=argparse.FileType("r"))
args = parser.parse_args()

reviews = json.load(args.reviews_file)["results"]

if not args.plot_outfile:
    sys.stderr.write("ERROR: No output file. Only plot tasks are supported and they require an output file.")
    exit(1)

if args.task == Task.FD_PER_REVIEWER:
    frequency_distribution_per_reviewer()
elif args.task == Task.REVIEW_COUNT_FD:
    review_count_frequency_dist()
