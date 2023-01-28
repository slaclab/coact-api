#!/usr/bin/env python

import argparse
import logging
import datetime

from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport
from gql.transport.requests import RequestsHTTPTransport

LOG = logging.getLogger(__name__)

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
            purpose
            gigabytes
            storagename
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
    mutation repoInitializeComputeAllocation($repo: RepoInput!, $repocompute: RepoComputeAllocationInput!, $qosinputs: [QosInput!]! ) {
      repoInitializeComputeAllocation(repo: $repo, repocompute: $repocompute, qosinputs: $qosinputs) {
        name
      }
    }
    """
)

repostorageallocationmutation = gql(
    """
    mutation repoInitializeStorageAllocation($repo: RepoInput!, $repostorage: RepoStorageAllocationInput! ) {
      repoInitializeStorageAllocation(repo: $repo, repostorage: $repostorage) {
        name
      }
    }
    """
)

createrequest = gql(
    """
    mutation requestCreate($request: CoactRequestInput!) {
        requestCreate(request: $request) {
            Id
            reqtype
            requestedby
            timeofrequest
        }
    }
    """
)

accessgroupcreate = gql(
    """
    mutation accessGroupCreate($repo: RepoInput!, $accessgroup: AccessGroupInput!) {
        accessGroupCreate(repo: $repo, accessgroup: $accessgroup) {
            name
        }
    }
    """
)

approverequest = gql(
    """
    mutation requestApprove($Id: String!) {
        requestApprove(id: $Id)
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

findrepo = gql(
    """
    query findrepo($filter: RepoInput!) {
        repo(filter: $filter) {
            Id
            name
            facility
            principal
            users
            accessGroupObjs {
                name
            }
            currentComputeAllocations {
                clustername
                start
                end
                qoses {
                    slachours
                    chargefactor
                }
            }
            currentStorageAllocations {
                purpose
                storagename
                rootfolder
                start
                end
                gigabytes
                inodes
            }
        }
    }
    """
)

createAuditTrail = gql(
    """
    mutation auditTrailAdd($theaud: AuditTrailInput!) {
        auditTrailAdd(theaud: $theaud) {
            Id
        }
    }
    """
)

updateuserstorageallocation = gql(
    """
    mutation userInitializeOrUpdateStorageAllocation($user: UserInput!, $userstorage: UserStorageInput!) {
        userInitializeOrUpdateStorageAllocation(user: $user, userstorage: $userstorage) {
            Id
        }
    }
    """
)

class ProcessRequests:
    def __init__(self, args):
        self.reqtransport = RequestsHTTPTransport(url=args.mutationurl, verify=True, retries=3)
        self.mutateclient = Client(transport=self.reqtransport, fetch_schema_from_transport=True)

    def subscribeAndProcess(self, args):
        while True:
            try:
                transport = WebsocketsTransport(url=args.url)
                client = Client(transport=transport, fetch_schema_from_transport=False)

                for request in client.subscribe(query):
                    LOG.info(request)
                    theReq = request["requests"].get("theRequest", {})
                    if request["requests"]["operationType"] == "update" and theReq.get("approvalstatus", None) == "Approved":
                        if theReq.get("reqtype", None) == "UserAccount":
                            self.processUserAccount(theReq)
                        elif theReq.get("reqtype", None) == "UserStorageAllocation":
                            self.processUserStorageAllocation(theReq)
                        elif theReq.get("reqtype", None) == "NewRepo":
                            self.processNewRepo(theReq)
            except Exception as e:
                LOG.exception(e)

    def processUserAccount(self, theReq):
        """
        Process UserAccount approvals
        """
        LOG.info("Add a request for home storage for %s", theReq["eppn"])
        resp = self.mutateclient.execute(getuserforeppn, variable_values={"eppn": theReq["eppn"]})
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
            result = self.mutateclient.execute(createrequest, variable_values=homestoragerequest)
            print(result)
            # Now approve the request
            LOG.info("Approving therequest for home storage for %s - %s", theReq["eppn"], result["requestCreate"]["Id"])
            result = self.mutateclient.execute(approverequest, variable_values={"Id": result["requestCreate"]["Id"]})
            print(result)
            result = self.mutateclient.execute(createAuditTrail, variable_values={ "theaud": {
                "type": "User",
                "name": username,
                "action": "UserAccountDone",
                "details": "Test audit trail from scripts"
            }})
            print(result)

        except Exception as e:
            LOG.exception(e)

    def processUserStorageAllocation(self, theReq):
        """
        Kick on the script to create home folders; once this succeeds update coact with the allocation and rootfolder.
        """
        LOG.info("Actually creating home storage for %s", theReq["username"])
        username = theReq["username"]
        homestorageallocationrequest = {
            "user" : {
                "username" : username,
            },
            "userstorage" : {
                "username": username,
                "purpose": theReq["purpose"],
                "gigabytes": theReq["gigabytes"],
                "storagename": theReq["storagename"],
                "rootfolder": "<prefix>/home/" + username[0] + "/" + username
            }
        }
        try:
            result = self.mutateclient.execute(updateuserstorageallocation, variable_values=homestorageallocationrequest)
            print(result)

        except Exception as e:
            LOG.exception(e)




    def processNewRepo(self, theReq):
        """
        Process NewRepo approvals. Create an access group, compute and storage allocations.
        """
        LOG.info("Processing a new repo request for %s in facility %s", theReq["reponame"], theReq["facilityname"])
        repo = self.mutateclient.execute(findrepo, variable_values={"filter": { "name": theReq["reponame"] }})["repo"]
        LOG.info(repo)
        fac2cluster = {
            "LCLS": ["roma", "milano"],
            "CryoEM": ["roma", "milano"],
            "SUNCAT": ["roma"],

        }
        fac2purpose = {
            "LCLS": {
                "data": {
                    "storagename": "sdfdata",
                    "gigabytes": 50000,
                    "rootfolder": lambda reponame: "<prefix>/" + reponame[0:3] + "/" + reponame + "/xtc"
                },
                "scratch": {
                    "storagename": "sdfdata",
                    "gigabytes": 100,
                    "rootfolder": lambda reponame: "<prefix>/" + reponame[0:3] + "/" + reponame + "/scratch"
                }
            },
            "CryoEM": {
                "data": {
                    "storagename": "sdfdata",
                    "gigabytes": 50000,
                    "rootfolder": lambda reponame: "<prefix>/" + reponame + "/data"
                },
                "scratch": {
                    "storagename": "sdfdata",
                    "gigabytes": 100,
                    "rootfolder": lambda reponame: "<prefix>/" + reponame + "/scratch"
                }
            },
            "SUNCAT": {
                "data": {
                    "storagename": "sdfdata",
                    "gigabytes": 50000,
                    "rootfolder": lambda reponame: "<prefix>/" + reponame + "/data"
                },
                "scratch": {
                    "storagename": "sdfdata",
                    "gigabytes": 100,
                    "rootfolder": lambda reponame: "<prefix>/" + reponame + "/scratch"
                }
            }
        }

        # Create compute allocations
        alreadyallocatedclusternames = map(lambda x: x["clustername"], repo["currentComputeAllocations"])
        for clustername in fac2cluster[theReq["facilityname"]]:
            if clustername in alreadyallocatedclusternames:
                LOG.info("Repo %s already has an allocation in cluster %s. Skipping asking for new allocations", repo["name"], clustername)
                continue
            defaultComputeAllocation = {
                "request" : {
                    "reqtype": "RepoComputeAllocation",
                    "requestedby": repo["principal"],
                    "timeofrequest": datetime.datetime.utcnow().isoformat(),
                    "reponame": repo["name"],
                    "facilityname": repo["facility"],
                    "clustername": clustername,
                    "qosname": repo["name"],
                    "slachours": 2000
                }
            }
            try:
                result = self.mutateclient.execute(createrequest, variable_values=defaultComputeAllocation)
                print(result)
                # Now approve the request
                LOG.info("Approving therequest for compute for %s on %s - %s", repo["name"], clustername, result["requestCreate"]["Id"])
                result = self.mutateclient.execute(approverequest, variable_values={"Id": result["requestCreate"]["Id"]})
                print(result)
            except Exception as e:
                LOG.exception(e)

        # Create storage allocations
        alreadyallocatedstoragepurposes = map(lambda x: x["purpose"], repo["currentStorageAllocations"])
        for purpose, reqvals in fac2purpose[theReq["facilityname"]].items():
            if purpose in alreadyallocatedstoragepurposes:
                LOG.info("Repo %s already has an storage allocation for purpose %s. Skipping asking for new allocations", repo["name"], purpose)
                continue
            defaultStorageAllocation = {
                "request" : {
                    "reqtype": "RepoStorageAllocation",
                    "requestedby": repo["principal"],
                    "timeofrequest": datetime.datetime.utcnow().isoformat(),
                    "reponame": repo["name"],
                    "facilityname": repo["facility"],
                    "storagename": reqvals["storagename"],
                    "purpose": purpose,
                    "gigabytes": reqvals["gigabytes"],
                    "rootfolder": reqvals["rootfolder"](repo["name"])
                }
            }
            try:
                result = self.mutateclient.execute(createrequest, variable_values=defaultStorageAllocation)
                print(result)
                # Now approve the request
                LOG.info("Approving therequest for storage for %s on %s - %s", repo["name"], purpose, result["requestCreate"]["Id"])
                result = self.mutateclient.execute(approverequest, variable_values={"Id": result["requestCreate"]["Id"]})
                print(result)
            except Exception as e:
                LOG.exception(e)
        # Create the main access group
        alreadyCreatedAccessGroups = map(lambda x: x["name"], repo["accessGroupObjs"])
        if repo["name"] in alreadyCreatedAccessGroups:
            LOG.info("Repo %s already has the primary access group", repo["name"])
        else:
            try:
                allusers = list(set([repo["principal"]] + repo["users"]))
                result = self.mutateclient.execute(accessgroupcreate, variable_values={ "repo": {"name": repo["name"]}, "accessgroup": { "name": repo["name"], "repo": repo["name"], "members": allusers } })
                print(result)
            except Exception as e:
                LOG.exception(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process request approvales. For now, this is mainly for testing")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("-u", "--url", help="The URL to the CoAct GraphQL API", default="wss://coact-dev.slac.stanford.edu/graphql")
    parser.add_argument("-m", "--mutationurl", help="The URL to the CoAct GraphQL API for mutations", default="https://coact-dev.slac.stanford.edu/graphql")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    pr = ProcessRequests(args)
    pr.subscribeAndProcess(args)
