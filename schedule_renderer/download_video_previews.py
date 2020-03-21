#! /usr/bin/env python3

import argparse
import json
import os.path
import re
import requests
import sys
import schedule_renderer.resource
from schedule_renderer.video import Video


def get_destination_path(destination_directory, clean_filename):
    return os.path.join(destination_directory, clean_filename)


def should_store(destination_directory, clean_filename):
    path = get_destination_path(destination_directory, clean_filename)
    return not os.path.isfile(path)


def fetch_and_save(code, url, filename, args):
    fname = schedule_renderer.resource.filename_from_url(url)
    if not args.nocache and not should_store(args.destination_directory, fname):
        sys.stderr.write("skip as already cached: {}\n".format(code))
        return
    path = get_destination_path(args.destination_directory, fname)
    sys.stderr.write("downloading {} {} -> {}\n".format(code, url, path))
    rr = requests.get(url, headers=headers)
    if rr.status_code != 200:
        sys.stderr.write("ERROR: HTTP status code {}\n".format(rr.status_code))
        exit(1)
    with open(path, "wb") as outfile:
        for chunk in rr.iter_content(chunk_size=1024):
            outfile.write(chunk)



parser = argparse.ArgumentParser(description="Download video preview images from media.ccc.de")
parser.add_argument("--nocache", action="store_true", help="download all files even if they are already present in the output directory")
parser.add_argument("metadata_file", type=argparse.FileType("r"), help="Metadata from media.ccc.de in JSON format (https://media.ccc.de/public/conferences/CONFERENCE_SLUG")
parser.add_argument("destination_directory", type=str, help="destination_directory")

args = parser.parse_args()

if not os.path.isdir(args.destination_directory):
    sys.stderr.write("ERROR: {} is not a directory\n".format(args.destination_directory))
    exit(1)

data = json.load(args.metadata_file)
videos = Video.load_media_ccc_de_json(data)
headers = {"user-agent": "pretalx-scripts.download_video_previews/0.1"}

for k, v in videos.items():
    fetch_and_save(k, v.thumb_url, v.thumb_filename(), args)
    fetch_and_save(k, v.poster_url, v.poster_filename(), args)
