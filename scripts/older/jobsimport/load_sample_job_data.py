#!/usr/bin/env python

import argparse
import logging
import gzip
import json

from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport
from gql.transport.requests import RequestsHTTPTransport

LOG = logging.getLogger(__name__)

importJobs = gql(
    """
    mutation importJobs($jobs: [Job!]!) {
        importJobs(jobs: $jobs) {
                insertedCount
                upsertedCount
                modifiedCount
                deletedCount
        }
    }
    """
)

class JobLoader:
    def __init__(self, args):
        self.reqtransport = RequestsHTTPTransport(url=args.mutationurl, verify=True, retries=3)
        self.mutateclient = Client(transport=self.reqtransport, fetch_schema_from_transport=True)

    def loadJobs(self, datafile):
        with gzip.open(datafile, 'rb') as f:
            jobs = json.load(f)
        LOG.info("Loaded %s jobs from the file %s", len(jobs), datafile)
        for job in jobs:
            job["jobId"] = int(job["jobId"])
            job["startTs"] = job["startTs"].replace("Z", ".000Z")
        try:
            result = self.mutateclient.execute(importJobs, variable_values={"jobs": jobs})["importJobs"]
            print(f"Imported jobs Inserted={result['insertedCount']}, Upserted={result['upsertedCount']} Deleted={result['deletedCount']}, Modified={result['modifiedCount']}")
        except Exception as e:
            LOG.exception(e)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Load sample data from SLURM into the jobs collection")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("-m", "--mutationurl", help="The URL to the CoAct GraphQL API for mutations, for example, https://coact-dev.slac.stanford.edu/graphql", required=True)
    parser.add_argument("datafile", help="Load slurm jobs data from this (json) file. The file should be a compressed gzip file.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARN)

    pr = JobLoader(args)
    pr.loadJobs(args.datafile)
