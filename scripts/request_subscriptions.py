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

    createrequest = gql(
        """
        mutation createRequest($request: CoactRequestInput!) {
            createRequest(request: $request) {
                Id
                reqtype
                requestedby
                timeofrequest
            }
        }
        """
    )

    approverequest = gql(
        """
        mutation approveRequest($Id: String!) {
            approveRequest(id: $Id)
        }
        """
    )

    getuserforeppn = gql(
        """
        query getuserforeppn($eppn: String!){
            getuserforeppn(eppn: $eppn) {
                username
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
                theReq = request["requests"].get("theRequest", {})
                if request["requests"]["operationType"] == "update" and theReq.get("approvalstatus", None) == "Approved":
                    if theReq.get("reqtype", None) == "UserAccount":
                        LOG.info("Add a request for home storage for %s", theReq["eppn"])
                        resp = mutateclient.execute(getuserforeppn, variable_values={"eppn": theReq["eppn"]})
                        username = resp["getuserforeppn"]["username"]
                        LOG.info("Username for the home storage request %s", username)
                        homestoragerequest = {
                            "request" : {
                                "reqtype" : "UserStorageAllocation",
                                "requestedby" : username,
                                "timeofrequest" : datetime.datetime.utcnow().isoformat(),
                                "username" : username,
                                "storagename" : "sdfhome",
                                "purpose" : "home",
                                "gigabytes" : 20
                            }
                        }
                        try:
                            result = mutateclient.execute(createrequest, variable_values=homestoragerequest)
                            print(result)
                            # Now approve the request
                            LOG.info("Approving therequest for home storage for %s - %s", theReq["eppn"], result["createRequest"]["Id"])
                            result = mutateclient.execute(approverequest, variable_values={"Id": result["createRequest"]["Id"]})
                            print(result)

                        except Exception as e:
                            LOG.exception(e)


        except Exception as e:
            LOG.exception(e)
