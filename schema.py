from auth import IsAuthenticated, \
        IsRepoPrincipal, \
        IsRepoLeader, \
        IsRepoPrincipalOrLeader, \
        IsAdmin, \
        IsValidEPPN, \
        IsFacilityCzarOrAdmin

import asyncio
from threading import Thread
from typing import List, Optional, AsyncGenerator
import copy
import datetime
import pytz
import json
from string import Template

import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET
from bson import ObjectId
from bson.json_util import dumps

from models import \
        MongoId, \
        User, UserInput, UserRegistration, \
        AccessGroup, AccessGroupInput, \
        Repo, RepoInput, \
        Facility, FacilityInput, Job, \
        UserAllocationInput, UserAllocation, \
        ClusterInput, Cluster, \
        CoactRequestInput, CoactRequest, CoactRequestType, CoactRequestEvent, \
        RepoFacilityName, \
        Usage, UsageInput, StorageDailyUsageInput, \
        ReportRangeInput, PerDateUsage, PerUserUsage, \
        RepoComputeAllocationInput, QosInput, RepoStorageAllocationInput

import logging
LOG = logging.getLogger(__name__)


@strawberry.type
class Query:
    @strawberry.field
    def amIRegistered(self, info: Info) -> UserRegistration:
        isRegis, eppn = info.context.isUserRegistered()
        regis_pending = False
        if not isRegis:
            regis_pending = len(info.context.db.find("requests", {"reqtype" : "UserAccount", "eppn" : eppn})) == 1
        return UserRegistration(**{ "isRegistered": isRegis, "eppn": eppn, "isRegistrationPending": regis_pending, "fullname": info.context.fullname })

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def whoami(self, info: Info) -> User:
        user = info.context.db.find_user( { "username": info.context.username } )
        user.fullname = info.context.fullname
        return user

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def users(self, info: Info, filter: Optional[UserInput]={} ) -> List[User]:
        return info.context.db.find_users( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def user(self, info: Info, user: UserInput ) -> User:
        return info.context.db.find_user( user )

    @strawberry.field
    def getuserforeppn(self, info: Info, eppn: str) -> User:
        user = info.context.db.collection("users").find_one( {"eppns": eppn} )
        return User(**user)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def clusters(self, info: Info, filter: Optional[ClusterInput]={} ) -> List[Cluster]:
        return info.context.db.find_clusters( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilities(self, info: Info, filter: Optional[FacilityInput]={} ) -> List[Facility]:
        return info.context.db.find_facilities( filter)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requests(self, info: Info, fetchprocessed: Optional[bool]=False, showmine: Optional[bool]=True) -> Optional[List[CoactRequest]]:
        """
        Separate queries for admin/czar/leader/user
        """
        queryterms = []
        if showmine:
            username = info.context.username
            if not username:
                return []
            queryterms.append({ "requestedby": username })
            crsr = info.context.db.collection("requests").find( {"$or": queryterms } ).sort([("timeofrequest", -1)])
            return info.context.db.cursor_to_objlist(crsr, CoactRequest, exclude_fields={})
        if not fetchprocessed:
            queryterms.append({"approvalstatus": {"$exists": False}})
        if info.context.is_admin:
            queryterms.append({"reqtype": {"$not": {"$in": [ "RepoMembership" ]}}})
        else:
            username = info.context.username
            assert username != None
            myfacs = list(info.context.db.find_facilities({"czars": username}))
            if myfacs:
                czarqueryterms = [{"facilityname": {"$in": [ x.name for x in myfacs ]}}]
                myfacnms = [ x.name for x in myfacs ]
                myrepos = info.context.db.find_repos( { '$or': [
                    { "leaders": username },
                    { "principal": username },
                    { "facility": {"$in": myfacnms }}
                    ] } )
                reponames = [ x.name for x in myrepos ]
                czarqueryterms.append({ "reponame": {"$in": reponames } })
                queryterms.append({ "$or": czarqueryterms })
            else:
                queryterms.append({"reqtype": "RepoMembership"})
                myrepos = info.context.db.find_repos( { '$or': [
                    { "leaders": username },
                    { "principal": username }
                    ] } )
                if myrepos:
                    reponames = [ x.name for x in myrepos ]
                    queryterms.append({ "reponame": {"$in": reponames } })

        finalqueryterms = {"$and": queryterms }
        LOG.info("Looking for requests using %s",  finalqueryterms)
        crsr = info.context.db.collection("requests").find(finalqueryterms).sort([("timeofrequest", -1)])
        return info.context.db.cursor_to_objlist(crsr, CoactRequest, exclude_fields={})

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facility(self, info: Info, filter: Optional[FacilityInput]) -> Facility:
        return info.context.db.find_facilities( filter )[0]


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_groups(self, info: Info, filter: Optional[AccessGroupInput]={} ) -> List[AccessGroup]:
        return info.context.db.find_access_groups( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_group(self, info: Info, filter: Optional[AccessGroupInput]) -> AccessGroup:
        return info.context.db.find_access_group( filter )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repos(self, info: Info, filter: Optional[RepoInput]={} ) -> List[Repo]:
        return info.context.db.find_repos( filter )

    @strawberry.field
    def facilityNames(self, info: Info) -> List[str]:
        """
        Just the facility names. No authentication needed.
        """
        return [ x["name"] for x in info.context.db.collection("facilities").find({}, {"_id": 0, "name": 1}) ]

    @strawberry.field
    def allreposandfacility(self, info: Info) -> List[RepoFacilityName]:
        """
        All the repo names and their facility. No authentication needed. Just the names
        """
        return [ RepoFacilityName(**x) for x in info.context.db.collection("repos").find({}, {"_id": 0, "name": 1, "facility": 1}) ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repo(self, filter: RepoInput, info: Info) -> Repo:
        return info.context.db.find_repo( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def myRepos(self, info: Info) -> List[Repo]:
        username = info.context.username
        assert username != None
        if info.context.showallforczars:
            LOG.error("Need to show all repos for a czar")
            facilities = info.context.db.find_facilities({ 'czars': username })
            if not facilities:
                raise Exception("No facilities found for czar " + username)
            return info.context.db.find_repos( { "facility": { "$in": [ x.name for x in facilities ] } } )
        else:
            return info.context.db.find_repos( { '$or': [
                { "users": username },
                { "leaders": username },
                { "principal": username }
                ] } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reposWithUser( self, info: Info, username: str ) -> List[Repo]:
        # want to search in principal and leaders too...
        return info.context.find( 'repos', { "users": username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reposWithLeader( self, info: Info, username: str ) -> List[Repo]:
        return info.context.db.find_repos( { "leaders": username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reposWithPrincipal( self, info: Info, username: str ) -> List[Repo]:
        return info.context.db.find_repos( { "principal": username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reportFacilityComputeByDay( self, info: Info, clustername: str, range: ReportRangeInput, group: str ) -> List[PerDateUsage]:
        LOG.debug("Getting compute daily data for cluster %s from %s to %s grouped by %s", clustername, range.start, range.end, group)
        if group == "Day":
            timegrp = "$date"
        elif group == "Month":
            timegrp = { "$dateTrunc": {"date": "$date", "unit": "month", "timezone": "America/Los_Angeles"}}
        else:
            raise Exception(f"Unsupported group by {group}")
        usgs = info.context.db.collection("repo_daily_compute_usage").aggregate([
          { "$lookup": { "from": "repo_compute_allocations", "localField": "allocationid", "foreignField": "_id", "as": "allocation"}},
          { "$unwind": "$allocation" },
          { "$match": { "allocation.clustername": clustername, "date": {"$gte": range.start, "$lte": range.end} } },
          { "$group": { "_id": {"repo": "$allocation.repo", "date" : timegrp }, "slachours": {"$sum":  "$slachours"}} },
          { "$project": { "_id": 0, "repo": "$_id.repo", "date": "$_id.date", "slachours": 1 }},
          { "$sort": { "date": -1 }}
        ])
        return info.context.db.cursor_to_objlist(usgs, PerDateUsage, {})

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reportFacilityComputeByUser( self, info: Info, clustername: str, range: ReportRangeInput ) -> List[PerUserUsage]:
        LOG.debug("Getting compute user data for cluster %s from %s to %s ", clustername, range.start, range.end)
        usgs = info.context.db.collection("jobs").aggregate([
          { "$match": { "startTs": {"$gte": range.start, "$lte": range.end} } },
          { "$lookup": { "from": "repo_compute_allocations", "localField": "allocationid", "foreignField": "_id", "as": "allocation"}},
          { "$unwind": "$allocation" },
          { "$match": { "allocation.clustername": clustername } },
          { "$group": { "_id": {"repo": "$allocation.repo", "username" : "$username" }, "slachours": {"$sum":  "$slachours"}} },
          { "$project": { "_id": 0, "repo": "$_id.repo", "username": "$_id.username", "slachours": 1 }},
          { "$sort": { "slachours": -1 }}
        ])
        return info.context.db.cursor_to_objlist(usgs, PerUserUsage, {})

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reportFacilityStorage( self, info: Info, storagename: str, purpose: Optional[str] = UNSET ) -> List[Usage]:
        LOG.debug("Storage report for storage %s for purpose %s ", storagename, purpose)
        groupby = {"repo": "$allocation.repo" }
        project = { "_id": 0, "repo": "$_id.repo", "gigabytes": 1, "inodes": 1 }
        if purpose:
            groupby["purpose"] = purpose
            project["purpose"] = "$_id.purpose"
        usgs = info.context.db.collection("repo_overall_storage_usage").aggregate([
          { "$lookup": { "from": "repo_storage_allocations", "localField": "allocationid", "foreignField": "_id", "as": "allocation"}},
          { "$unwind": "$allocation" },
          { "$match": { "allocation.storagename": storagename } },
          { "$group": { "_id": groupby, "gigabytes": {"$sum":  "$gigabytes"}, "inodes": {"$sum":  "$inodes"} }},
          { "$project": project },
          { "$sort": { "gigabytes": -1 }}
        ])
        return info.context.db.cursor_to_objlist(usgs, Usage, {})

@strawberry.type
class Mutation:

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def userCreate(self, user: UserInput, info: Info) -> User:
        return info.context.db.create( 'users', user, required_fields=[ 'username', 'uidnumber', 'eppns' ], find_existing={ 'username': user.username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdate(self, user: UserInput, info: Info) -> User:
        return info.context.db.update( 'users', user, required_fields=[ '_id' ], find_existing={ '_id': user._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdateEppn(self, eppns: List[str], info: Info) -> User:
        logged_in_user = info.context.username
        if len(eppns) < 1:
            raise Exception("A user must have at least one EPPN")
        existing_users = info.context.db.find_users({"eppns": {"$in": eppns}})
        if len(existing_users) != 1 or existing_users[0].username != logged_in_user:
            raise Exception("Some of the eppns are being used by another user")
        info.context.db.collection("users").update_one({"username": logged_in_user}, {"$set": { "eppns": eppns }})
        return info.context.db.find_user( {"username": logged_in_user} )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def changeUserShell(self, newshell: str, info: Info) -> User:
        LOG.info("Changing shell for user %s to %s", info.context.username, newshell)
        info.context.db.collection("users").update_one({"username": info.context.username}, {"$set": {"shell": newshell}})
        return info.context.db.find_user( {"username": info.context.username} )

    @strawberry.field( permission_classes=[ IsValidEPPN ] )
    def newSDFAccountRequest(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repoMembershipRequest(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoMembership or not request.reponame:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def newRepoRequest(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.NewRepo or not request.reponame or not request.facilityname or not request.principal:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoComputeAllocationRequest(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoComputeAllocation or not request.reponame or not request.clustername or not request.slachours:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoStorageAllocationRequest(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoStorageAllocation or not request.reponame or not request.allocationid or not request.gigabytes:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype', "allocationid", "gigabytes" ], find_existing=None)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userQuotaRequest(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.UserStorageAllocation or not request.storagename or not request.gigabytes:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def createRequest(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def approveRequest(id: str, info: Info) -> bool:
        LOG.debug(id)
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        user = info.context.authn()

        isAdmin = info.context.is_admin
        isCzar = False
        isLeader = False
        if thereq.reponame:
            therepos = info.context.db.find_repos({"name": thereq.reponame})
            if therepos:
                therepo = info.context.db.find_repo({"name": thereq.reponame})
                if user in therepo.leaders or therepo.principal == user:
                    isLeader = True
                facilities = info.context.db.find_facilities({ 'czars': user })
                if facilities:
                    if therepo.facility in [ x.name for x in facilities]:
                        isCzar = True
            else:
                if not thereq.reqtype == "NewRepo":
                    raise Exception("Can't find repo with reponame " + thereq.reponame)
        if thereq.facilityname:
            facilities = info.context.db.find_facilities({ 'czars': user })
            if facilities:
                if thereq.facilityname in [ x.name for x in facilities]:
                    isCzar = True

        if thereq.reqtype == "RepoMembership":
            if not isAdmin and not isCzar and not isLeader:
                raise Exception("User is not an admin, czar or a leader in the repo.")
            # These two should be in a transaction.
            info.context.db.collection("repos").update_one({"_id": therepo._id}, {"$addToSet": {"users": thereq.username}})
            thereq.approve(info)
            return True
        elif thereq.reqtype == "UserAccount":
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            theeppn = thereq.eppn
            if not theeppn:
                raise Exception("Account request without a eppn - cannot approve.")
            # Check if the preferredUserName already is in use
            preferredUserName = thereq.preferredUserName
            if not preferredUserName:
                raise Exception("Account request without a preferred user id - cannot approve.")
            alreadyExistingUser = info.context.db.collection("users").find_one( { "username": preferredUserName} )
            if alreadyExistingUser:
                raise Exception("User with username " + preferredUserName + " already exists - cannot approve.")
            thefacility = thereq.facilityname
            if not thefacility:
                raise Exception("Account request without a facility - cannot approve.")

            # We do not explicitly set the UID so that the automatic scripts can detect this fact and set the appropriate UID based on introspection of external LDAP servers.
            # This lets us at least make an attempt to match B50 UID's and then maybe use a range for external EPPN's
            info.context.db.collection("users").insert_one({ "username": preferredUserName, "eppns": [ theeppn ], "shell": "/bin/bash", "preferredemail": theeppn })
            thereq.approve(info)
            return True
        elif thereq.reqtype == "UserStorageAllocation":
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            theuser = thereq.username
            if not theuser or not info.context.db.collection("users").find_one( { "username": theuser } ):
                raise Exception(f"Cannot find user object for {theuser}")
            thestoragename = thereq.storagename
            if not thestoragename:
                raise Exception(f"Please specify the volume")
            thepurpose = thereq.purpose
            if not thepurpose:
                raise Exception(f"Please specify the purpose; this is used to identify which allocation to update")
            if not thereq.gigabytes:
                raise Exception(f"Please specify the storage request as gigabytes")

            alloc = info.context.db.collection("user_storage_allocation").find_one( { "username": theuser, "storagename": thestoragename, "purpose": thepurpose } )
            if not alloc:
                info.context.db.collection("user_storage_allocation").insert_one({
                    "username": theuser,
                    "storagename": thestoragename,
                    "purpose": thepurpose,
                    "gigabytes": thereq.gigabytes,
                    "inodes": thereq.inodes,
                    "rootfolder": "<prefix>/home/" + theuser[0] + "/" + theuser
                })
            else:
                info.context.db.collection("user_storage_allocation").update_one(
                    { "username": theuser, "storagename": thestoragename, "purpose": thepurpose },
                    {"$set": {"gigabytes": thereq.gigabytes, "inodes": thereq.inodes }}
                )
            thereq.approve(info)
            return True
        elif thereq.reqtype == "NewRepo":
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            thereponame = thereq.reponame
            if not thereponame:
                raise Exception("New repo request without a repo name - cannot approve.")
            if info.context.db.find_repos( {"name": thereponame} ):
                raise Exception(f"Repo with name {thereponame} already exists")
            if not thereq.facilityname:
                raise Exception(f"When creating a new repo, please specify the facility.")
            if not thereq.principal:
                raise Exception(f"When creating a new repo, please specify the principal.")
            if not info.context.db.find_facility({"name": thereq.facilityname}):
                raise Exception(f"Facility {thereq.facilityname} does not seem to be a valid facility")
            if not info.context.db.find_user({"username": thereq.principal}):
                raise Exception(f"The principal {thereq.principal} does not seem to exist")

            info.context.db.collection("repos").insert_one({
                  "name": thereponame,
                  "facility": thereq.facilityname,
                  "principal": thereq.principal,
                  "leaders": [  ],
                  "users": [ thereq.principal  ],
                  "access_groups": []
              })
            thereq.approve(info)
            return True
        elif thereq.reqtype == "RepoComputeAllocation":
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            thereponame = thereq.reponame
            if not thereponame:
                raise Exception("RepoComputeAllocation request without a repo name - cannot approve.")
            if not info.context.db.find_repos( {"name": thereponame} ):
                raise Exception(f"Repo with name {thereponame} does not exist")
            theclustername = thereq.clustername
            if not theclustername:
                raise Exception("RepoComputeAllocation request without a cluster name - cannot approve.")
            if not info.context.db.find_clusters( {"name": theclustername} ):
                raise Exception(f"Cluster with name {theclustername} does not exist")
            theqosname = thereq.qosname
            if not theqosname:
                raise Exception("RepoComputeAllocation request without a QOS name - cannot approve.")
            if not thereq.slachours:
                raise Exception("RepoComputeAllocation without a slachours - cannot approve.")
            if not thereq.start:
                thereq.start = datetime.datetime.utcnow()
            if not thereq.end:
                thereq.end = datetime.datetime.utcnow().replace(year=2100)
            if not thereq.chargefactor:
                thereq.chargefactor = 1.0

            clusterallocs = [ x for x in info.context.db.find_repo( {"name": thereponame} ).currentComputeAllocations(info) if x.clustername == theclustername ]
            if not clusterallocs or len(clusterallocs) < 1:
                info.context.db.collection("repo_compute_allocations").insert_one({
                    "repo": thereponame,
                    "clustername": theclustername,
                    "start": thereq.start,
                    "end": thereq.end,
                    "qoses": {
                        theqosname: {
                            "slachours": thereq.slachours,
                            "chargefactor": thereq.chargefactor
                        }
                    }
                })
            else:
                if len(clusterallocs) != 1:
                    raise AssertionError( f"Found more than one current allocation for repo {thereponame} on cluster {theclustername}" )
                clusteralloc = clusterallocs[0]
                theqos = [ q for q in clusteralloc.qoses(info) if q.name == theqosname ][0]
                if not theqos:
                    raise Exception(f"Cannot find a QOS with the name {theqosname} for the cluster with name {theclustername} for repo {thereponame}")

                info.context.db.collection("repo_compute_allocations").update_one(
                    {"_id": ObjectId(clusteralloc._id)},
                    {"$set": {"qoses."+theqosname+".slachours": thereq.slachours}}
                )
            thereq.approve(info)
            return True
        elif thereq.reqtype == "RepoStorageAllocation":
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            thereponame = thereq.reponame
            if not thereponame:
                raise Exception("RepoComputeAllocation request without a repo name - cannot approve.")
            therepo = info.context.db.find_repo( {"name": thereponame} )
            if not therepo:
                raise Exception(f"Repo with name {thereponame} does not exist")
            if not thereq.purpose:
                raise Exception(f"Request for storage without purpose")
            if not thereq.storagename:
                raise Exception(f"Request for storage without storagename")
            if not thereq.gigabytes:
                raise Exception(f"Request for storage without gigabytes")
            if not thereq.start:
                thereq.start = datetime.datetime.utcnow()
            if not thereq.end:
                thereq.end = datetime.datetime.utcnow().replace(year=2100)

            storageallocs = [ x for x in info.context.db.find_repo( {"name": thereponame} ).currentStorageAllocations(info) if x.purpose == thereq.purpose ]
            if not storageallocs:
                info.context.db.collection("repo_storage_allocations").insert_one({
                    "repo": thereponame,
                    "purpose": thereq.purpose,
                    "start": thereq.start,
                    "end": thereq.end,
                    "storagename": thereq.storagename,
                    "purpose": thereq.purpose,
                    "gigabytes": thereq.gigabytes,
                    "rootfolder": thereq.rootfolder,
                })
            else:
                if len(storageallocs) != 1:
                    raise AssertionError( f"Found more than one current storage allocation for repo {thereponame} for purpose {thereq.purpose}" )
                storagealloc = storageallocs[0]
                info.context.db.collection("repo_storage_allocations").update_one(
                    {"_id": ObjectId(storagealloc._id)},
                    {"$set": {"gigabytes": thereq.gigabytes, "inodes": thereq.inodes}}
                )

            thereq.approve(info)
            return True
        else:
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            raise Exception("Approval of requests of type " + thereq.reqtype + " is not yet implemented")

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def rejectRequest(id: str, notes: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        thereq.reject(notes, info)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def completeRequest(id: str, notes: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        thereq.complete(notes, info)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def markRequestIncomplete(id: str, notes: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        thereq.incomplete(notes, info)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def facilityCreate(self, facility: FacilityInput, info: Info) -> Facility:
        return info.context.db.create( 'facilities', facility, required_fields=[ 'name' ], find_existing={ 'name': facility.name } )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def accessGroupCreate(self, repo: RepoInput, accessgroup: AccessGroupInput, info: Info) -> AccessGroup:
        # We do not set the GID so that the automatic scripts can detect this fact and set the appropriate GID based on introspection of external LDAP servers.
        # This lets us at least make an attempt to match B50 GID's.
        accessgroup.gidnumber = UNSET
        if not accessgroup.members:
            accessgroup.members = []
        newgrpid = info.context.db.collection("access_groups").insert_one(info.context.db.to_dict(accessgroup)).inserted_id
        ret = info.context.db.find_access_group({"_id": newgrpid})
        return ret

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def accessGroupUpdate(self, repo: RepoInput, access_group: AccessGroupInput, info: Info) -> AccessGroup:
        return info.context.db.update( 'access_groups', info, access_group, required_fields=[ 'Id', ], find_existing={ '_id': accesss_group._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoCreate(self, repo: RepoInput, info: Info) -> Repo:
        return info.context.db.create( 'repos', repo, required_fields=[ 'name', 'facility' ], find_existing={ 'name': repo.name, 'facility': repo.facility } )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoUpdate(self, repo: RepoInput, info: Info) -> Repo:
        return info.context.db.update( 'repos', info, repo, required_fields=[ 'Id' ], find_existing={ '_id': repo._id } )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def updateUserAllocation(self, repo: RepoInput, data: List[UserAllocationInput], info: Info) -> Repo:
        filter = {"name": repo.name}
        therepos =  info.context.db.find_repo( filter )
        uas = [dict(j.__dict__.items()) for j in data]
        keys = ["username", "allocationid", ]
        for ua in uas:
            nua = {k: v for k,v in ua.items() if not v is UNSET}
            info.context.db.collection("user_allocations").replace_one({k: v for k,v in nua.items() if k in keys}, nua, upsert=True)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def addUserToRepo(self, repo: RepoInput, user: UserInput, info: Info ) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"users": user.username}})
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def addLeaderToRepo(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"leaders": user.username}})
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipal ] )
    def changePrincipalForRepo(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$set": {"principal": user.username}})
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def removeUserFromRepo(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        therepo =  info.context.db.find_repo( filter )
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
        if theuser == therepo.principal:
            raise Exception(theuser + " is a PI in repo " + repo.name + ". Cannot be removed from the repo")
        info.context.db.collection("repos").update_one(filter, { "$pull": {"leaders": theuser, "users": theuser}})
        return info.context.db.find_repo( filter )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def toggleUserRole(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        therepo = info.context.db.find_repo( filter )
        theuser = user.username
        if theuser not in therepo.users:
            LOG.warning(theuser + " is not a user in repo " + repo.name)
        info.context.db.collection("repos").update_one({"name": repo.name}, [{ "$set":
            { "leaders": { "$cond": [
                { "$in": [ user.username, "$leaders" ] },
                { "$setDifference": [ "$leaders", [ user.username ] ] },
                { "$concatArrays": [ "$leaders", [ user.username ] ] }
                ]}}}])
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def toggleGroupMembership(self, repo: RepoInput, user: UserInput, group: AccessGroupInput, info: Info) -> AccessGroup:
        filter = {"name": repo.name}
        therepo = info.context.db.find_repo( filter )
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
        grpfilter = { "name": group.name }
        thegroup = info.context.db.find_access_group( grpfilter )
        info.context.db.collection("access_groups").update_one({"name": group.name}, [{ "$set":
            { "members": { "$cond": [
                { "$in": [ user.username, "$members" ] },
                { "$setDifference": [ "$members", [ user.username ] ] },
                { "$concatArrays": [ "$members", [ user.username ] ] }
                ]}}}])
        return info.context.db.find_access_group( grpfilter )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def initializeRepoComputeAllocation(self, repo: RepoInput, repocompute: RepoComputeAllocationInput, qosinputs: List[QosInput], info: Info) -> Repo:
        rc = {"repo": repo.name}
        repo = info.context.db.find_repo( { "name": repo.name } )
        clustername = repocompute.clustername
        if not info.context.db.find_clusters({"name": clustername}):
            raise Exception("Cannot find cluster with name " + clustername)

        if repo.currentComputeAllocations(info):
            for rca in repo.currentComputeAllocations(info):
                if rca.clustername == clustername:
                    raise Exception("Repo " + repo.name + "already has a compute allocation for cluster " + clustername)
        rc["clustername"] = clustername
        rc["start"] = repocompute.start.astimezone(pytz.utc)
        rc["end"] = repocompute.end.astimezone(pytz.utc)
        rc["qoses"] = {}
        for qosinput in qosinputs:
            rc["qoses"][qosinput.name] = { "slachours": qosinput.slachours, "chargefactor": qosinput.chargefactor }
        LOG.info(rc)
        info.context.db.collection("repo_compute_allocations").insert_one(rc)
        return info.context.db.find_repo( { "name": repo.name } )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def initializeRepoStorageAllocation(self, repo: RepoInput, repostorage: RepoStorageAllocationInput, info: Info) -> Repo:
        rs = {"repo": repo.name}
        repo = info.context.db.find_repo( { "name": repo.name } )
        storagename = repostorage.storagename
        if not info.context.db.collection("physical_volumes").find_one({"name": storagename}):
            raise Exception("Cannot find physical volume with name " + storagename)

        if repo.currentStorageAllocations(info):
            for rsa in repo.currentStorageAllocations(info):
                if rsa.purpose == repostorage.purpose:
                    raise Exception("Repo " + repo.name + "already has a storage allocation for purpose  " + purpose)
        rs["storagename"] = storagename
        rs["purpose"] = repostorage.purpose
        rs["start"] = repostorage.start.astimezone(pytz.utc)
        rs["end"] = repostorage.end.astimezone(pytz.utc)
        rs["gigabytes"] = repostorage.gigabytes
        rs["inodes"] =  repostorage.inodes
        rs["rootfolder"] = repostorage.rootfolder

        LOG.info(rs)
        info.context.db.collection("repo_storage_allocations").insert_one(rs)
        return info.context.db.find_repo( { "name": repo.name } )

    @strawberry.mutation
    def importJobs(self, jobs: List[Job], info: Info) -> str:
        jbs = [dict(j.__dict__.items()) for j in jobs]
        info.context.db.collection("jobs").insert_many(jbs)
        allocation_ids = list(map(lambda x: x["allocationid"], jbs))
        info.context.db.collection("jobs").aggregate([
          { "$match": { "allocationid": {"$in":  allocation_ids } }},
          { "$group": { "_id": {"allocationid": "$allocationid", "qos": "$qos", "repo": "$repo" },
              "slachours": { "$sum": "$slachours" },
              "rawsecs": { "$sum": "$rawsecs" },
              "machinesecs": { "$sum": "$machinesecs" },
              "avgcf": { "$avg": "$finalcf" }
          }},
          { "$project": {
              "_id": 0,
              "allocationid": "$_id.allocationid",
              "qos": "$_id.qos",
              "repo": "$_id.repo",
              "slachours": 1,
              "rawsecs": 1,
              "machinesecs": 1,
              "avgcf": 1,
          }},
          { "$merge": { "into": "repo_overall_compute_usage", "whenMatched": "replace" } }
        ])

        info.context.db.collection("jobs").aggregate([
          { "$match": { "allocationid": {"$in":  allocation_ids } }},
          { "$group":
            { "_id": {"allocationid": "$allocationid", "username": "$username", "repo": "$repo"},
                "slachours": { "$sum": "$slachours" },
                "rawsecs": { "$sum": "$rawsecs" },
                "machinesecs": { "$sum": "$machinesecs" },
                "avgcf": { "$avg": "$finalcf" }
            }},
            { "$project": {
                "_id": 0,
                "allocationid": "$_id.allocationid",
                "username": "$_id.username",
                "repo": "$_id.repo",
                "slachours": 1,
                "rawsecs": 1,
                "machinesecs": 1,
                "avgcf": 1
            }},
            { "$merge": { "into": "repo_peruser_compute_usage", "whenMatched": "replace" } }
        ])

        info.context.db.collection("jobs").aggregate([
          { "$match": { "allocationid": {"$in":  allocation_ids } }},
          { "$group":
            { "_id": { "allocationid": "$allocationid", "repo": "$repo", "date" : { "$dateTrunc": {"date": "$startTs", "unit": "day", "timezone": "America/Los_Angeles"}}},
                "slachours": { "$sum": "$slachours" },
                "rawsecs": { "$sum": "$rawsecs" },
                "machinesecs": { "$sum": "$machinesecs" },
                "avgcf": { "$avg": "$finalcf" }
            }
           },
           { "$project": {
                "_id": 0,
                "allocationid": "$_id.allocationid",
                "repo": "$_id.repo",
                "date": "$_id.date",
                "slachours": 1,
                "rawsecs": 1,
                "machinesecs": 1,
                "avgcf": 1
            }},
            { "$merge": { "into": "repo_daily_compute_usage", "whenMatched": "replace" } }
        ])

        return "Done"

    @strawberry.mutation
    def importRepoStorageUsage(self, usages: List[StorageDailyUsageInput], info: Info) -> str:
        usgs = [dict(j.__dict__.items()) for j in usages]
        info.context.db.collection("repo_daily_storage_usage").insert_many(usgs)
        info.context.db.collection("repo_daily_storage_usage").aggregate([
            { "$sort": { "date": -1 }},
            { "$group": { "_id": "$allocationid", "allocationid": {"$first": "$allocationid"}, "date": {"$first": "$date"}, "gigabytes": {"$first": "$gigabytes"}, "inodes": {"$first": "$inodes"}}},
            { "$merge": { "into": "repo_overall_storage_usage", "whenMatched": "replace" } }
        ])
        return "Done"

requests_queue = asyncio.Queue()

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def requests(self, info: Info) -> AsyncGenerator[CoactRequestEvent, None]:
        while True:
            req = await requests_queue.get()
            yield req

def start_change_stream_queues(db):
    """
    Create a asyncio task to watch for change streams.
    We create one task per collection for now.
    """
    async def __watch_requests__():
        with db["requests"].watch() as change_stream:
            while change_stream.alive:
                change = change_stream.try_next()
                while change is not None:
                    try:
                        LOG.info("Publishing a request")
                        LOG.info(dumps(change))
                        theId = change["documentKey"]["_id"]
                        theRq = db["requests"].find_one({"_id": theId})
                        req = CoactRequest(**theRq) if theRq else None
                        await requests_queue.put(CoactRequestEvent(operationType=change["operationType"], theRequest=req))
                        change = change_stream.try_next()
                    except Exception as e:
                        LOG.exception("Exception processing change")
                await asyncio.sleep(1)
    asyncio.create_task(__watch_requests__())
