#!/usr/bin/env python3

"""
Load sample data from SLURM into the jobs collection.
"""

import os
import sys
import json
import logging
import argparse
import requests
import csv
from datetime import datetime
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
    parser.add_argument("-r", "--resource_name", help="The name of the resource, typically something like compute", default='compute')
    parser.add_argument("--timezone", help="Timezone to use for analysis", default='America/Los_Angeles' )
    parser.add_argument("--dry_run", help="Do not insert data into Coact", default=False, action='store_true' )
    parser.add_argument("datafile", help="Load slurm jobs data from this (json) file.")
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
    logging.info(f"Authenticated as {user}")

    # load and process the slurm json file
    tz = pytz.timezone(args.timezone)
    with open(args.datafile, "r") as f:
        jobs = json.load(f)

    # We rely on the accountName mapping directly to the reponame.
    # What do we do with jobs that do not maintain this mapping?
    # Perhaps have a default repo and send them there?
    # We map the job to the resource based on the qos. If we only have one resource, we simply map to that.

    q = """
        query{
            repos(filter:{}){
                name
                facility
                principal
                leaders
                users
                allocations(resource: "%s"){
                    resource
                    qoses{
                        name
                        slachours
                        chargefactor
                    }
                }
            }
            clusters(filter:{}){
                name
                chargefactor
                members
            }
        }
    """
    reporesp = requests.post(args.url, cookies=cookies, json={"query": q % args.resource_name})
    reporesp.raise_for_status()
    repos = { x["name"] : x for x in reporesp.json()["data"]["repos"] }
    for repo in repos.values():
        qos2resource = {}
        qos2cf = {}
        for alloc in repo.get("allocations", []):
            for qos in alloc.get("qoses", []):
                qos2resource[qos["name"]] = alloc["resource"]
                qos2cf[qos["name"]] = qos["chargefactor"]
        repo["qos2resource"] = qos2resource
        repo["qos2cf"] = qos2cf
        logging.info("found repo {repo}")

    nodename2cf = {}
    for cluster in reporesp.json()["data"]["clusters"]:
        for member in cluster.get("members", []):
            nodename2cf[member] = cluster["chargefactor"]

    for job in jobs:
        # Fix up everything with a "_ts"
        for k, v in job.items():
            if k.endswith("Ts"):
                job[k] = dateparser.parse(v)
        job["year"] = job["startTs"].year

        # Map job to repo.
        acc_name = job.get("accountName", None)
        if acc_name and acc_name in repos.keys():
            job["repo"] = acc_name
            job["facility"] = repos[acc_name]["facility"]
            job["resource"] = repos[acc_name]["qos2resource"][job["qos"]]
            job["priocf"] = repos[acc_name]["qos2cf"][job["qos"]]
            job["hwcf"] = mean(map(lambda x : nodename2cf[x], NodeList(job["nodelist"]).sorted()))
            job["finalcf"] = job["priocf"] * job["hwcf"]
            job["rawSecs"] = job["elapsedSecs"] * job["allocNodes"] # elapsed seconds * number of nodes
            job["machineSecs"] = job["rawSecs"] * job["hwcf"] # raw seconds after applying the hardware charge factor
            job["nodeSecs"] = job["machineSecs"] * job["priocf"] # machineSecs after applying the priority charge factor
            # TODO we also need to apply a factor if the quota has been exceeded.
            logger.info(f"Mapping {job['jobId']} to {job['repo']} based on account name")
        else:
            raise Exception(f"Cannot map job to repo %s {job['jobId']}, account {job['accountName']}")

        # Use qos to map to proper resource


    def encodeJobVal(v):
        if isinstance(v, datetime):
            return '"' + v.replace(tzinfo=pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ') + '"'
        return json.dumps(v)
    def encodeJob(jb):
        ret = "{ "
        for k,v in jb.items():
             ret = ret + k + ": " + encodeJobVal(v) + ","
        ret = ret + " }"
        return ret

 
    if not args.dry_run:
        jobstr = "mutation{importJobs( jobs: [" +  ",\n".join([encodeJob(x) for x in jobs ]) + "])}"
        requests.post(args.url, json={"query": jobstr}).json()
