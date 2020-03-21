#! /usr/bin/env python3

import argparse
import json
import os.path
import re
import requests
import sys
from schedule_renderer.resource import Resource


def should_store(resource, destination_directory):
    path = resource.get_destination_path(destination_directory)
    return not os.path.isfile(path)


parser = argparse.ArgumentParser(description="Download attachments from Pretalx")
parser.add_argument("-d", "--description-filter", type=str, help="Download only attachments which match the provided regular expression")
parser.add_argument("--nocache", action="store_true", help="download all files even if they are already present in the output directory")
parser.add_argument("-u", "--url-prefix", type=str, help="URL prefix for Pretalx (usually protocol and hostname only)", default="https://pretalx.com")
parser.add_argument("json_export", type=argparse.FileType("r"), help="Pretalx API /talks response")
parser.add_argument("destination_directory", type=str, help="destination_directory")

args = parser.parse_args()

if not os.path.isdir(args.destination_directory):
    sys.stderr.write("ERROR: {} is not a directory\n".format(args.destination_directory))
    exit(1)

data = json.load(args.json_export)
talks = data["results"]

headers = {"user-agent": "pretalx-scripts.download_attachements/0.1"}

filter_re = None
if args.description_filter:
    filter_re = re.compile(args.description_filter)

count = 0
count_downloaded = 0
for t in talks:
    resources = t.get("resources", [])
    resources = [ Resource(t["code"], args.url_prefix, **r) for r in resources ]
    if filter_re:
        resources = [ r for r in resources if filter_re.search(r.description) ]
    count += len(resources)
    for r in resources:
        if not args.nocache and not should_store(r, args.destination_directory):
            sys.stderr.write("skip {} {}\n".format(t.get("code"), t.get("title")))
            continue
        path = r.get_destination_path(args.destination_directory)
        sys.stderr.write("downloading {} {} -> {}\n".format(r.code, r.url, path))
        count_downloaded += 1
        rr = requests.get(r.url, headers=headers)
        if rr.status_code != 200:
            sys.stderr.write("ERROR: HTTP status code {}\n".format(rr.status_code))
            exit(1)
        with open(path, "wb") as outfile:
            for chunk in rr.iter_content(chunk_size=1024):
                outfile.write(chunk)

if len(resources) == 0:
    sys.stderr.write("WARNING: The event has no resources or no resources are left after filtering.\n")
    exit(0)
sys.stderr.write("{} resources found, {} were downloaded.\n".format(count, count_downloaded))
