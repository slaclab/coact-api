#!/usr/bin/env python3

"""
Example of how to load storage usage info into coAct.
This loads both user and repo storage info.
"""

import os
import sys
import json
import logging
import argparse
import requests
import csv
import datetime
import pytz
import dateutil.parser as dateparser
from utils.nl import NodeList
from statistics import mean

from pymongo import MongoClient

logger = logging.getLogger(__name__)

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, float) and not math.isfinite(o):
            return str(o)
        elif isinstance(o, datetime):
            return o.replace(tzinfo=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        return json.JSONEncoder.default(self, o)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Load sample data from SLURM into the jobs collection. This is mainly for testing")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("-u", "--url", help="The URL to the CoAct GraphQL API", default="https://coact-dev.slac.stanford.edu/graphql")
    parser.add_argument("-C", "--vouch_cookie_name", help="The cookie name that Vouch expects", default='slac-vouch' )
    parser.add_argument("-c", "--cookie", help="The Vouch cookie for authenticated access to Coact", required=True )
    parser.add_argument("--timezone", help="Timezone to use for analysis", default='America/Los_Angeles' )
    parser.add_argument("--dry_run", help="Do not insert data into Coact", default=False, action='store_true' )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    # setup auth
    cookies = { args.vouch_cookie_name: args.cookie }

    # test
    q = """
        query {
            whoami {
                username
            }
        }
    """
    user = requests.post(args.url, cookies=cookies, json={'query': q}).json()['data']['whoami']['username']
    logger.info(f"Authenticated as {user}")

    tz = pytz.timezone(args.timezone)

    # We rely on the accountName mapping directly to the reponame.
    # What do we do with jobs that do not maintain this mapping?
    # Perhaps have a default repo and send them there?
    # We map the job to the resource based on the qos. If we only have one resource, we simply map to that.

    q = """
        query{
            repos(filter:{}){
                name
                facility
                currentStorageAllocations{
                    Id
                    storagename
                    purpose
                    rootfolder
                }
            }
        }
    """
    reporesp = requests.post(args.url, cookies=cookies, json={"query": q})
    reporesp.raise_for_status()
    repos = { x["name"] : x for x in reporesp.json()["data"]["repos"] }
    logger.debug(repos)
    rootfoldrers2allocs = { y["rootfolder"] : { "Id": y["Id"], "repo": x["name"], "purpose": y["purpose"] } for x in reporesp.json()["data"]["repos"] for y in x["currentStorageAllocations"] }
    logger.debug(rootfoldrers2allocs)

    def encodeUsageVal(v):
        if isinstance(v, datetime.datetime):
            return '"' + v.replace(tzinfo=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ') + '"'
        return json.dumps(v)
    def encodeUsage(jb):
        ret = "{ "
        for k,v in jb.items():
             ret = ret + k + ": " + encodeUsageVal(v) + ","
        ret = ret + " }"
        return ret


    # Loop thru the days in this year and generate some fake data
    start_date = datetime.datetime.now().replace(month=1, day=1)
    curr_date = start_date
    end_date = datetime.datetime.now()
    delta = datetime.timedelta(days=1)
    gb = 10.0
    inds = 101
    while (curr_date <= end_date):
        updates = []
        for rf, al in rootfoldrers2allocs.items():
            updates.append({"allocationid": al["Id"], "date": curr_date, "gigabytes": gb, "inodes": inds })
        curr_date += delta
        gb = gb + 0.5 # Just some random increments
        inds = inds + 3

        if not args.dry_run:
            jobstr = "mutation{importRepoStorageUsage( usages: [" +  ",\n".join([encodeUsage(x) for x in updates ]) + "])}"
            mutresp = requests.post(args.url, json={"query": jobstr})
            mutresp.raise_for_status()
