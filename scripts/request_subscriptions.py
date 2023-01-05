#!/usr/bin/env python

import argparse
import logging
import datetime

from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport
from gql.transport.requests import RequestsHTTPTransport

LOG = logging.getLogger(__name__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process request approvales. For now, this is mainly for testing")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("-u", "--url", help="The URL to the CoAct GraphQL API", default="wss://coact-dev.slac.stanford.edu/graphql")
    parser.add_argument("-m", "--mutationurl", help="The URL to the CoAct GraphQL API for mutations", default="https://coact-dev.slac.stanford.edu/graphql")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    reqtransport = RequestsHTTPTransport(
        url=args.mutationurl,
        verify=True,
        retries=3,
    )

    mutateclient = Client(transport=reqtransport, fetch_schema_from_transport=True)

    # Provide a GraphQL query
    query = gql(
        """
        subscription {
          requests {
            theRequest {
            	reqtype
                approvalstatus
            	eppn
            	preferredUserName
                reponame
                facilityname
                principal
                username
                actedat
                actedby
                requestedby
                timeofrequest
            }
            operationType
          }
        }
    """
    )

    repocomputeallocationmutation = gql(
        """
        mutation initializeRepoComputeAllocation($repo: RepoInput!, $repocompute: RepoComputeAllocationInput!, $qosinputs: [QosInput!]! ) {
          initializeRepoComputeAllocation(repo: $repo, repocompute: $repocompute, qosinputs: $qosinputs) {
            name
          }
        }
        """
    )

    repostorageallocationmutation = gql(
        """
        mutation initializeRepoStorageAllocation($repo: RepoInput!, $repostorage: RepoStorageAllocationInput! ) {
          initializeRepoStorageAllocation(repo: $repo, repostorage: $repostorage) {
            name
          }
        }
        """
    )

    while True:
        try:
            transport = WebsocketsTransport(url=args.url)

            client = Client(
                transport=transport,
                fetch_schema_from_transport=False,
            )
            for request in client.subscribe(query):
                LOG.info(request)
                if request["requests"]["operationType"] == "update" and request["requests"].get("theRequest", {}).get("reqtype", None) == "NewRepo":
                    theReq = request["requests"].get("theRequest", {})
                    if theReq.get("approvalstatus", None) == "Approved":
                        LOG.info("Need to create the allocations for %s in facility %s", theReq["reponame"], theReq["facilityname"])
                        computeparams = {
                            "repo": { "name": theReq["reponame"] },
                            "repocompute": { "repo": theReq["reponame"], "clustername": "milano", "start": datetime.datetime.utcnow().isoformat(), "end": (datetime.datetime.utcnow() + datetime.timedelta(days=365)).isoformat()},
                            "qosinputs": [
                                { "name": theReq["reponame"], "slachours": 5432, "chargefactor": 1.0 }
                            ]
                        }
                        try:
                            result = mutateclient.execute(repocomputeallocationmutation, variable_values=computeparams)
                            print(result)
                        except Exception as e:
                            LOG.exception(e)

                        storageparams = {
                            "repo": { "name": theReq["reponame"] },
                            "repostorage": {
                                "repo": theReq["reponame"], "storagename": "sdfdata", "purpose": "data",
                                "gigabytes": 50000, "inodes": 100000, "rootfolder": "<prefix>/" + theReq["reponame"] + "/xtc",
                                "start": datetime.datetime.utcnow().isoformat(), "end": (datetime.datetime.utcnow() + datetime.timedelta(days=365)).isoformat()
                            },
                        }
                        try:
                            result = mutateclient.execute(repostorageallocationmutation, variable_values=storageparams)
                            print(result)
                        except Exception as e:
                            LOG.exception(e)

                        storageparams = {
                            "repo": { "name": theReq["reponame"] },
                            "repostorage": {
                                "repo": theReq["reponame"], "storagename": "sdfdata", "purpose": "scratch",
                                "gigabytes": 100, "inodes": 10000000, "rootfolder": "<prefix>/" + theReq["reponame"] + "/scratch",
                                "start": datetime.datetime.utcnow().isoformat(), "end": (datetime.datetime.utcnow() + datetime.timedelta(days=365)).isoformat()
                            },
                        }
                        try:
                            result = mutateclient.execute(repostorageallocationmutation, variable_values=storageparams)
                            print(result)
                        except Exception as e:
                            LOG.exception(e)

        except Exception as e:
            LOG.exception(e)
