#!/usr/bin/env python

import argparse
import logging
import datetime
import time
import pytz

from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport
from gql.transport.requests import RequestsHTTPTransport

LOG = logging.getLogger(__name__)

# Provide a GraphQL query
query = gql(
    """
    subscription($clientName: String) {
      requests(clientName: $clientName) {
        theRequest {
            Id
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
            clustername
            percentOfFacility
            burstPercentOfFacility
            allocated
            burstAllocated
            start
            end
            chargefactor
            actedat
            actedby
            requestedby
            timeofrequest
            computerequirement
        }
        operationType
      }
    }
"""
)


userUpsert = gql(
    """
    mutation userUpsert($user: UserInput!) {
        userUpsert(user: $user) {
            Id
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

completerequest = gql(
    """
    mutation requestComplete($Id: String!, $notes: String!) {
        requestComplete(id: $Id, notes: $notes)
    }
    """
)

getuserforeppn = gql(
    """
    query getuserforeppn($eppn: String!){
        getuserforeppn(eppn: $eppn) {
            Id
            username
        }
    }
    """
)

repocreate = gql(
    """
    mutation repoCreate($repo: RepoInput!) {
        repoCreate(repo: $repo) {
            Id
            name
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

userStorageAllocationUpsert = gql(
    """
    mutation userStorageAllocationUpsert($user: UserInput!, $userstorage: UserStorageInput!) {
        userStorageAllocationUpsert(user: $user, userstorage: $userstorage) {
            Id
        }
    }
    """
)

repoComputeAllocationUpsert = gql(
    """
    mutation repoComputeAllocationUpsert($repo: RepoInput!, $repocompute: RepoComputeAllocationInput!) {
        repoComputeAllocationUpsert(repo: $repo, repocompute: $repocompute) {
            Id
        }
    }
    """
)

repoStorageAllocationUpsert = gql(
    """
    mutation repoStorageAllocationUpsert($repo: RepoInput!, $repostorage: RepoStorageAllocationInput!) {
        repoStorageAllocationUpsert(repo: $repo, repostorage: $repostorage) {
            Id
        }
    }
    """
)

repoAppendMember = gql(
    """
    mutation repoAppendMember($repo: RepoInput!, $user: UserInput!) {
        repoAppendMember(repo: $repo, user: $user) {
            Id
        }
    }
    """
)

allAccessGroupos = gql(
    """
    query allAccesGroups($filter: AccessGroupInput!) {
        accessGroups(filter: $filter) {
            name
        }
    }
    """
)


repoChangeComputeRequirement = gql(
    """
    mutation repoChangeComputeRequirement($repo: RepoInput!, $computerequirement: ComputeRequirement!) {
        repoChangeComputeRequirement(repo: $repo, computerequirement: $computerequirement) {
            name
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

                for request in client.subscribe(query, variable_values={"clientName": "TestSubscription"}):
                    LOG.info(request)
                    theReq = request["requests"].get("theRequest", {})
                    if request["requests"]["operationType"] == "update" and theReq.get("approvalstatus", None) == "Approved":
                        if theReq.get("reqtype", None) == "UserAccount":
                            self.processUserAccount(theReq)
                        elif theReq.get("reqtype", None) == "UserStorageAllocation":
                            self.processUserStorageAllocation(theReq)
                        elif theReq.get("reqtype", None) == "NewRepo":
                            self.processNewRepo(theReq)
                        elif theReq.get("reqtype", None) == "RepoComputeAllocation":
                            self.processRepoComputeAllocations(theReq)
                        elif theReq.get("reqtype", None) == "RepoStorageAllocation":
                            self.processRepoStorageAllocations(theReq)
                        elif theReq.get("reqtype", None) == "RepoMembership":
                            self.processRepoMembership(theReq)
                        elif theReq.get("reqtype", None) == "RepoChangeComputeRequirement":
                            self.processRepoChangeComputeRequirement(theReq)
                        # Mark request as being complete
                        result = self.mutateclient.execute(completerequest, variable_values={"Id": theReq["Id"], "notes": "From unit tests"})
                        print(result)
            except Exception as e:
                LOG.exception(e)

    def processUserAccount(self, theReq):
        """
        Process UserAccount approvals
        """
        # Add a 1 minute delay for testing UI 
        time.sleep(60)
        # TODO Put in the uidnumber number here
        resp = self.mutateclient.execute(userUpsert, variable_values={"user": {
            "username": theReq["preferredUserName"],
            "eppns": [ theReq["eppn"] ],
            "shell": "/bin/bash",
            "preferredemail": theReq["eppn"]
        }})

        LOG.info("Add a request for home storage for %s", theReq["eppn"])
        resp = self.mutateclient.execute(getuserforeppn, variable_values={"eppn": theReq["eppn"]})
        username = resp["getuserforeppn"]["username"]
        LOG.info("Username for the home storage request %s", username)
        homestoragerequest = {
            "request" : {
                "reqtype" : "UserStorageAllocation",
                "requestedby" : username,
                "timeofrequest" : datetime.datetime.utcnow().astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
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
                "actedon": resp["getuserforeppn"]["Id"],
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
            result = self.mutateclient.execute(userStorageAllocationUpsert, variable_values=homestorageallocationrequest)
            print(result)

        except Exception as e:
            LOG.exception(e)

    def processNewRepo(self, theReq):
        """
        Process NewRepo approvals. Create an access group, compute and storage allocations.
        """
        LOG.info("Processing a new repo request for %s in facility %s", theReq["reponame"], theReq["facilityname"])
        repo = self.mutateclient.execute(repocreate, variable_values={"repo": {
            "name": theReq["reponame"],
            "facility": theReq["facilityname"],
            "principal": theReq["principal"],
            "leaders": [ ],
            "users": [ theReq["principal"] ]
        }})

        repo = self.mutateclient.execute(findrepo, variable_values={"filter": { "name": theReq["reponame"], "facility": theReq["facilityname"] }})["repo"]
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
                    "timeofrequest": datetime.datetime.utcnow().astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    "reponame": repo["name"],
                    "facilityname": repo["facility"],
                    "clustername": clustername,
                    "qosname": repo["name"],
                    "servers": 10
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
                    "timeofrequest": datetime.datetime.utcnow().astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
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
        alreadyCreatedAccessGroups = [ x["name"] for x in self.mutateclient.execute(allAccessGroupos, variable_values={"filter": { "name": repo["name"] }})["accessGroups"]]
        LOG.info(alreadyCreatedAccessGroups)
        if repo["name"] in alreadyCreatedAccessGroups:
            LOG.info("Repo %s already has the primary access group", repo["name"])
        else:
            try:
                allusers = list(set([repo["principal"]] + repo["users"]))
                result = self.mutateclient.execute(accessgroupcreate, variable_values={ "repo": {"Id": repo["Id"]}, "accessgroup": { "name": repo["name"], "repoid": repo["Id"], "members": allusers } })
                print(result)
            except Exception as e:
                LOG.exception(e)

    def processRepoComputeAllocations(self, theReq):
        thereponame = theReq["reponame"]
        if not thereponame:
            LOG.error(f"RepoComputeAllocation request without a repo name - cannot approve {theReq['Id']}")
        therepo = self.mutateclient.execute(findrepo, variable_values={"filter": { "name": theReq["reponame"], "facility": theReq["facilityname"] }}).get("repo", None)
        if not therepo:
            LOG.error(f"Repo with name {thereponame} does not exist - cannot approve {theReq['Id']}")
        LOG.info(therepo)

        for attr in [ "clustername", "percentOfFacility" ]:
            if not theReq.get(attr, None):
                LOG.error(f"RepoComputeAllocation request without {attr} - cannot approve {theReq['Id']}")

        if not theReq["start"]:
            theReq["start"] = datetime.datetime.utcnow().astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        if not theReq["end"]:
            theReq["end"] = datetime.datetime.utcnow().replace(year=2100, month=1, day=1).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        if not theReq["chargefactor"]:
            theReq["chargefactor"] = 1.0

        try:
            result = self.mutateclient.execute(repoComputeAllocationUpsert, variable_values={
                "repo": {"Id": therepo["Id"]},
                "repocompute": {
                    "repoid": therepo["Id"],
                    "clustername": theReq["clustername"],
                    "start": theReq["start"],
                    "end": theReq["end"],
                    "percentOfFacility":  theReq["percentOfFacility"],
                    "allocated": theReq["allocated"],
                    "burstPercentOfFacility":  theReq["burstPercentOfFacility"],
                    "burstAllocated": theReq["burstAllocated"],

                }})
            print(result)
        except Exception as e:
            LOG.exception(e)

    def processRepoStorageAllocations(self, theReq):
        thereponame = theReq["reponame"]
        if not thereponame:
            LOG.error(f"RepoStorageAllocation request without a repo name - cannot approve {theReq['Id']}")
        therepo = self.mutateclient.execute(findrepo, variable_values={"filter": { "name": theReq["reponame"], "facility": theReq["facilityname"] }}).get("repo", None)
        if not therepo:
            LOG.error(f"Repo with name {thereponame} does not exist - cannot approve {theReq['Id']}")
        LOG.info(therepo)

        for attr in [ "purpose", "storagename", "gigabytes" ]:
            if not theReq.get(attr, None):
                LOG.error(f"RepoStorageAllocation request without {attr} - cannot approve {theReq['Id']}")

        if not theReq["start"]:
            theReq["start"] = datetime.datetime.utcnow()
        if not theReq["end"]:
            theReq["end"] = datetime.datetime.utcnow().replace(year=2100, month=1, day=1)

        try:
            result = self.mutateclient.execute(repoStorageAllocationUpsert, variable_values={
                "repo": {"Id": therepo["Id"]},
                "repostorage": {
                    "repoid": therepo["Id"],
                    "purpose": theReq["purpose"],
                    "storagename": theReq["storagename"],
                    "purpose": theReq["purpose"],
                    "gigabytes": theReq["gigabytes"],
                    "rootfolder": f"/cds/data/{thereponame}/{theReq['purpose']}",
                    "start": theReq["start"].astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    "end": theReq["end"].astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                }
            })
            print(result)
        except Exception as e:
            LOG.exception(e)

    def processRepoMembership(self, theReq):
        try:
            resp = self.mutateclient.execute(repoAppendMember, variable_values={"repo": { "name": theReq["reponame"], "facility": theReq["facilityname"] }, "user": { "username": theReq["username"] }})
        except Exception as e:
            LOG.exception(e)

    def processRepoChangeComputeRequirement(self, theReq):
        therepo = self.mutateclient.execute(findrepo, variable_values={"filter": { "name": theReq["reponame"], "facility": theReq["facilityname"] }})["repo"]
        if not therepo:
            LOG.error("Cannot find repo %s  in facility %s", theReq["reponame"], theReq["facilityname"])
            return
        try:
            result = self.mutateclient.execute(repoChangeComputeRequirement, variable_values={
                "repo": {"Id": therepo["Id"]},
                "computerequirement": theReq["computerequirement"]
                })
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
