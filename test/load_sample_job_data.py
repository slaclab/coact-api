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
    parser.add_argument("datafile", help="Load jobs data from this file.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    tz = pytz.timezone('America/Los_Angeles')
    with open(args.datafile, "r") as f:
        jobs = json.load(f)

    # Data for mapping jobs to repos/facilities
    # Given a partition, determine the unique facility
    # Given a facility, find all repos
    # Given a user, find all repos
    # Given a facility and a qos, find all repos

    facilities = requests.post("http://localhost:17669/irisapi/graphql", json={"query": "query{facilities(filter: {}){ name resources{ name partitionObjs { name } } }}"}).json()["data"]["facilities"]
    partition2facility = { partition["name"] : {"facility": facility["name"], "resource": rsrc["name"]} for facility in facilities for rsrc in facility["resources"] for partition in rsrc.get("partitionObjs", []) }
    print(partition2facility)
    # partition2facility = { partition : {"facility": facility["name"], "resource": rname} for facility in facilities for rname, rsrc in facility["resources"].items() for partition in rsrc.get("partitions", []) }
    reporesp = requests.post("http://localhost:17669/irisapi/graphql", json={"query": "query{repos(filter:{}){ name facility principal leaders users }}"})
    reporesp.raise_for_status()
    repos = reporesp.json()["data"]["repos"]
    repo_names = [ x["name"] for x in repos ]
    user2reposlst = {}
    facility2reposlst = {}
    for repo in repos:
        def addUsrRepo(usr, repo):
            if not usr in user2reposlst:
                user2reposlst[usr] = list()
            user2reposlst[usr].append(repo["name"])
        for user in repo.get("users", {}):
            addUsrRepo(user, repo)
        def addFacRepo(facility, repo):
            if not facility in facility2reposlst:
                facility2reposlst[facility] = []
            facility2reposlst[facility].append(repo)
        addFacRepo(repo["facility"], repo["name"])

    print(user2reposlst)

    qoses = requests.post("http://localhost:17669/irisapi/graphql", json={"query":"query{qos{ name repo qos partition}}"}).json()["data"]["qos"]
    qos2repolst = { (x["partition"], x["name"]) : x["repo"] for x in qoses }

    user2repos = { k: set(v) for k,v in user2reposlst.items() }
    facility2repos = { k: set(v) for k,v in facility2reposlst.items() }
    qos2repos = { k: set(v) for k,v in qos2repolst.items()}

    for job in jobs:
        # Fix up everything with a "_ts"
        for k, v in job.items():
            if k.endswith("_ts"):
                job[k] = dateparser.parse(v)
        job["year"] = job["start_ts"].year

        # Map job to repo.
        # First, try to get as much information as we can from the partition name.
        facility = partition2facility[job["partition_name"]]
        job["facility"] = facility["facility"]
        job["resource"] = facility["resource"]

        acc_name = job.get("account_name", None)
        if acc_name and acc_name in repo_names:
            job["repo"] = acc_name
            logger.info(f"Mapping {job['job_id']} to {job['repo']} based on account name")
            continue

        facrepos = facility2repos.get(facility["facility"], set())
        logger.debug("Repos from facliity %s for job %s are %s", facility["facility"], job["job_id"], facrepos)
        usrrepos = user2repos.get(job["user_name"], set())
        logger.debug("Repos from user %s for job %s are %s", job["user_name"], job["job_id"], usrrepos)

        # See if we have any common repos from the facility side and from the user side.
        common_repos = facrepos & usrrepos
        if not common_repos:
            raise Exception(f"We should have at least a few common repos for {job['job_id']} From facility {facrepos} and from user {usrrepos}")

        if len(common_repos) == 1:
            logger.debug("We have only one common repo from the facility and from the user side")
            job["repo"] = list(common_repos)[0]
            logger.info(f"Mapping {job['job_id']} to {job['repo']} based on facility and user repos")
            continue

        # We have more than one repo from the facility and the user side.
        # Use the qos partition index to map now.
        qosrepos = qos2repos.get((job["partition_name"], job["qos"]), set())
        common_repos = facrepos & usrrepos & qosrepos
        if not common_repos:
            raise Exception(f"We should have at least a few common repos for {job['job_id']} From facility {facrepos} and from user {usrrepos} From QOS {qosrepos}")

        if len(common_repos) == 1:
            job["repo"] = list(common_repos)[0]
            logger.info(f"Mapping {job['job_id']} to {job['repo']} based on facility, user and qos repos")
            continue

        logger.warn(f"Breaking the tie arbitrarily for {job['job_id']} as we have too many repos")
        job["repo"] = list(common_repos)[0]

        raise Exception(f"Cannot map job to repo %s {job['job_id']}")

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
    print(jobstr)
    requests.post("http://localhost:17669/irisapi/graphql", json={"query": jobstr}).json()
