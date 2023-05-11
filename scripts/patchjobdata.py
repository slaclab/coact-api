#!/usr/bin/env python
import argparse
import logging
import json
import random

from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

logger = logging.getLogger(__name__)

findrepo = gql(
    """
    query findrepo($filter: RepoInput!) {
        repo(filter: $filter) {
            Id
            name
            facility
            principal
            users
        }
    }
    """
)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="This is a temporary utility that will patch job JSON data to include a proper account name etc. This utility shoud NEVER be used in production.")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("-u", "--url", help="The URL to the CoAct GraphQL API", required=True)
    parser.add_argument("datafile", help="Patch jobs data from this file. Reads from and writes to the same file.")
    parser.add_argument("accountname", help="Patch jobs data using account name. We expect this to be of the form <facilityname>:<reponame>")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    gqllient = Client(transport=RequestsHTTPTransport(url=args.url, verify=True, retries=3), fetch_schema_from_transport=True)
    
    facilityname = args.accountname.split(":")[0]
    reponame = args.accountname.split(":")[1]

    repo = gqllient.execute(findrepo, variable_values={"filter": { "name": reponame, "facility": facilityname }})["repo"]
    logger.info(repo)

    with open(args.datafile, "r") as f:
        jobs = json.load(f)

    for job in jobs:
        job["accountName"] = args.accountname
        job["qos"] = reponame
        job["username"] = random.choice(repo["users"])
        if not job["submitter"]:
            job["submitter"] = job["username"]

    with open(args.datafile, "w") as f:
        json.dump(jobs, f, indent=4)
