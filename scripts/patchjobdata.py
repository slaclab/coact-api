#!/usr/bin/env python
import os
import argparse
import logging
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="This is a temporary utility that will patch job JSON data to include a proper account name etc. This utility shoud NEVER be used in production.")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("datafile", help="Patch jobs data from this file. Reads from and writes to the same file.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    with open(args.datafile, "r") as f:
        jobs = json.load(f)

    for job in jobs:
        job["accountName"] = "cxi12345"
        job["qos"] = "cxi12345"
        if not job["submitter"]:
            job["submitter"] = job["username"]

    with open(args.datafile, "w") as f:
        json.dump(jobs, f, indent=4)
