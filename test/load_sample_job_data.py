#!/usr/bin/env python

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
    parser.add_argument("-u", "--url", help="The URL to the CoAct GraphQL API, for example, http://localhost:17669/irisapi/graphql", required=True)
    parser.add_argument("-r", "--resource_name", help="The name of the resource, typically something like compute", required=True)
    parser.add_argument("datafile", help="Load jobs data from this file.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    tz = pytz.timezone('America/Los_Angeles')
    with open(args.datafile, "r") as f:
        jobs = json.load(f)

    # We rely on the accountName mapping directly to the reponame.
    # What do we do with jobs that do not maintain this mapping?
    # Perhaps have a default repo and send them there?
    # We map the job to the resource based on the qos. If we only have one resource, we simply map to that.


    reporesp = requests.post("http://localhost:17669/irisapi/graphql", json={"query": 'query{repos(filter:{}){ name facility principal leaders users allocations(resource: "' + args.resource_name + '"){resource qoses{name slachours}}}}'})
    reporesp.raise_for_status()
    repos = { x["name"] : x for x in reporesp.json()["data"]["repos"] }
    for repo in repos.values():
        qos2resource = {}
        for alloc in repo.get("allocations", []):
            for qos in alloc.get("qoses", []):
                qos2resource[qos["name"]] = alloc["resource"]
        repo["qos2resource"] = qos2resource

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

    jobstr = "mutation{importJobs( jobs: [" +  ",\n".join([encodeJob(x) for x in jobs ]) + "])}"
    # print(jobstr)
    requests.post("http://localhost:17669/irisapi/graphql", json={"query": jobstr}).json()
