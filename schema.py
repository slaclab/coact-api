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
        UserStorageInput, UserStorage, \
        AccessGroup, AccessGroupInput, \
        Repo, RepoInput, \
        Facility, FacilityInput, Job, \
        UserAllocationInput, UserAllocation, \
        ClusterInput, Cluster, \
        CoactRequestInput, CoactRequest, CoactRequestType, CoactRequestEvent, \
        RepoFacilityName, \
        Usage, UsageInput, StorageDailyUsageInput, \
        ReportRangeInput, PerDateUsage, PerUserUsage, \
        RepoComputeAllocationInput, QosInput, RepoStorageAllocationInput, \
        AuditTrailObjectType, AuditTrail, AuditTrailInput, \
        NotificationInput, Notification

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

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userAuditTrails( self, info: Info ) -> List[AuditTrail]:
        return info.context.db.cursor_to_objlist(info.context.db.collection("audit_trail").find({ "type": AuditTrailObjectType.User.name, "name": info.context.username }).sort([("actedat", -1)]), AuditTrail)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repoAuditTrails( self, repo: RepoInput, info: Info ) -> List[AuditTrail]:
        return info.context.db.cursor_to_objlist(info.context.db.collection("audit_trail").find({ "type": AuditTrailObjectType.Repo.name, "name": repo.name }).sort([("actedat", -1)]), AuditTrail)

@strawberry.type
class Mutation:

    @strawberry.field( permission_classes=[ IsAdmin ] )
    def userCreate(self, user: UserInput, info: Info) -> User:
        user = info.context.db.create( 'users', user, required_fields=[ 'username', 'eppns', 'shell', 'preferredemail' ], find_existing={ 'username': user.username} )
        info.context.audit(AuditTrailObjectType.User, user.username, "userCreate")
        return user

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdate(self, user: UserInput, info: Info) -> User:
        user_before_update = info.context.db.find_user({'_id': user._id})
        if not info.context.username == user_before_update.username and not info.context.is_admin:
            raise Exception(f"Only admins can update other users - {info.context.username} wants to update {user.username}")
        user_after_update = info.context.db.update( 'users', user, required_fields=[ '_id' ], find_existing={ '_id': user._id } )
        info.context.audit(AuditTrailObjectType.User, user_after_update.username, "userUpdate", details=info.context.dict_diffs(user_before_update, user_after_update))
        return user_after_update

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdateEppn(self, eppns: List[str], info: Info) -> User:
        logged_in_user = info.context.username
        if len(eppns) < 1:
            raise Exception("A user must have at least one EPPN")
        existing_users = info.context.db.find_users({"eppns": {"$in": eppns}})
        if len(existing_users) != 1 or existing_users[0].username != logged_in_user:
            raise Exception("Some of the eppns are being used by another user")
        info.context.db.collection("users").update_one({"username": logged_in_user}, {"$set": { "eppns": eppns }})
        info.context.audit(AuditTrailObjectType.User, info.context.username, "userUpdateEppn", details=",".join(eppns))
        return info.context.db.find_user( {"username": logged_in_user} )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userChangeShell(self, newshell: str, info: Info) -> User:
        LOG.info("Changing shell for user %s to %s", info.context.username, newshell)
        info.context.db.collection("users").update_one({"username": info.context.username}, {"$set": {"shell": newshell}})
        info.context.audit(AuditTrailObjectType.User, info.context.username, "userChangeShell", details=newshell)
        return info.context.db.find_user( {"username": info.context.username} )

    @strawberry.field( permission_classes=[ IsFacilityCzarOrAdmin ] )
    def userStorageAllocationUpsert(self, user: UserInput, userstorage: UserStorageInput, info: Info) -> User:
        LOG.info("Creating or updating home storage allocation for user %s", user.username)
        theuser = info.context.db.find_user({'username': user.username})
        userstorage.validate()
        info.context.db.collection("user_storage_allocation").update_one(
            {"username": theuser.username, "storagename": userstorage.storagename, "purpose": userstorage.purpose },
            {"$set": { "gigabytes": userstorage.gigabytes, "rootfolder": userstorage.rootfolder}},
            upsert=True)
        info.context.audit(AuditTrailObjectType.User, theuser.username, "UserStorageAllocation", details=userstorage.purpose+"="+str(userstorage.gigabytes)+"GB on "+userstorage.storagename)
        return info.context.db.find_user({'username': user.username})

    @strawberry.field( permission_classes=[ IsValidEPPN ] )
    def requestNewSDFAccount(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        request.timeofrequest = datetime.datetime.utcnow()
        this_req = info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        info.context.notify( this_req )
        return this_req

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestRepoMembership(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoMembership or not request.reponame:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestNewRepo(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.NewRepo or not request.reponame or not request.facilityname or not request.principal:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def requestRepoComputeAllocation(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoComputeAllocation or not request.reponame or not request.clustername or not request.slachours:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def requestRepoStorageAllocation(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoStorageAllocation or not request.reponame or not request.allocationid or not request.gigabytes:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype', "allocationid", "gigabytes" ], find_existing=None)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestUserQuota(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.UserStorageAllocation or not request.storagename or not request.gigabytes:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def requestCreate(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestApprove(self, id: str, info: Info) -> bool:
        """
        This mostly checks authorization and marks the request as being approved.
        Most of the actual action, both in the database and in the external world ( SLURM, LDAP etc) happen in external subscription processing.
        """
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

            thereq.approve(info)
            return True
        else:
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            raise Exception("Approval of requests of type " + thereq.reqtype + " is not yet implemented")

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def requestReject(self, id: str, notes: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        r = thereq.reject(notes, info)
        info.context.notify(r)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def requestComplete(self, id: str, notes: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        r = thereq.complete(notes, info)
        info.context.notify(r)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def requestIncomplete(self, id: str, notes: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        r = thereq.incomplete(notes, info)
        info.context.notify(r)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def requestRefire(self, id: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        thereq.refire(info)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def accessGroupCreate(self, repo: RepoInput, accessgroup: AccessGroupInput, info: Info) -> AccessGroup:
        # We do not set the GID so that the automatic scripts can detect this fact and set the appropriate GID based on introspection of external LDAP servers.
        # This lets us at least make an attempt to match B50 GID's.
        accessgroup.gidnumber = UNSET
        if not accessgroup.members:
            accessgroup.members = []
        newgrpid = info.context.db.collection("access_groups").insert_one(info.context.db.to_dict(accessgroup)).inserted_id
        ret = info.context.db.find_access_group({"_id": newgrpid})
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "accessGroupCreate", details=accessgroup.name)
        return ret

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def accessGroupUpdate(self, repo: RepoInput, access_group: AccessGroupInput, info: Info) -> AccessGroup:
        group_before_update = info.context.db.find_access_group(access_group)
        group_after_update = info.context.db.update( 'access_groups', info, access_group, required_fields=[ 'Id', ], find_existing={ '_id': accesss_group._id } )
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "accessGroupUpdate", details=info.context.dict_diffs(group_before_update, group_after_update))
        return group_after_update

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoCreate(self, repo: RepoInput, info: Info) -> Repo:
        repo = info.context.db.create( 'repos', repo, required_fields=[ 'name', 'facility', 'principal' ], find_existing={ 'name': repo.name } )
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoCreate")
        return repo

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoUpdate(self, repo: RepoInput, info: Info) -> Repo:
        repo_before_update = info.context.db.find_repo({ 'name': repo.name })
        repo_after_update = info.context.db.update( 'repos', info, repo, required_fields=[ 'name' ], find_existing={ 'name': repo.name } )
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoUpdate", details=info.context.dict_diffs(repo_before_update, repo_after_update))
        return repo_after_update

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoUpdateUserAllocation(self, repo: RepoInput, data: List[UserAllocationInput], info: Info) -> Repo:
        filter = {"name": repo.name}
        therepos =  info.context.db.find_repo( filter )
        uas = [dict(j.__dict__.items()) for j in data]
        keys = ["username", "allocationid", ]
        for ua in uas:
            nua = {k: v for k,v in ua.items() if not v is UNSET}
            info.context.db.collection("user_allocations").replace_one({k: v for k,v in nua.items() if k in keys}, nua, upsert=True)
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoUpdateUserAllocation")
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoAddUser(self, repo: RepoInput, user: UserInput, info: Info ) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"users": user.username}})
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoAddUser", details=user.username)
        info.context.audit(AuditTrailObjectType.User, user.username, "+RepoMembership", details=repo.name)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoAddLeader(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"leaders": user.username}})
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoAddLeader", details=user.username)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipal ] )
    def repoChangePrincipal(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$set": {"principal": user.username}})
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoChangePrincipal", details=user.username)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoRemoveUser(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        therepo =  info.context.db.find_repo( filter )
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
        if theuser == therepo.principal:
            raise Exception(theuser + " is a PI in repo " + repo.name + ". Cannot be removed from the repo")
        info.context.db.collection("repos").update_one(filter, { "$pull": {"leaders": theuser, "users": theuser}})
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoRemoveUser", details=user.username)
        info.context.audit(AuditTrailObjectType.User, user.username, "-RepoMembership", details=repo.name)
        return info.context.db.find_repo( filter )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoToggleUserRole(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
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
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoToggleUserRole", details=user.username)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoToggleGroupMembership(self, repo: RepoInput, user: UserInput, group: AccessGroupInput, info: Info) -> AccessGroup:
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
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoToggleGroupMembership", details=user.username)
        return info.context.db.find_access_group( grpfilter )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoComputeAllocationUpsert(self, repo: RepoInput, repocompute: RepoComputeAllocationInput, qosinputs: List[QosInput], info: Info) -> Repo:
        rc = {"repo": repo.name}
        repo = info.context.db.find_repo( { "name": repo.name } )
        clustername = repocompute.clustername
        if not info.context.db.find_clusters({"name": clustername}):
            raise Exception("Cannot find cluster with name " + clustername)

        rc["clustername"] = clustername
        rc["start"] = repocompute.start.astimezone(pytz.utc)
        rc["end"] = repocompute.end.astimezone(pytz.utc)
        rc["qoses"] = {}
        for qosinput in qosinputs:
            rc["qoses"][qosinput.name] = { "slachours": qosinput.slachours, "chargefactor": qosinput.chargefactor }
        LOG.info(rc)
        info.context.db.collection("repo_compute_allocations").replace_one({"repo": rc["repo"], "clustername": rc["clustername"], "start": rc["start"]}, rc, upsert=True)
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoComputeAllocationUpsert", details=clustername+"="+json.dumps(rc["qoses"]))
        return info.context.db.find_repo( { "name": repo.name } )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoStorageAllocationUpsert(self, repo: RepoInput, repostorage: RepoStorageAllocationInput, info: Info) -> Repo:
        rs = {"repo": repo.name}
        repo = info.context.db.find_repo( { "name": repo.name } )
        storagename = repostorage.storagename
        if not info.context.db.collection("physical_volumes").find_one({"name": storagename}):
            raise Exception("Cannot find physical volume with name " + storagename)

        rs["storagename"] = storagename
        rs["purpose"] = repostorage.purpose
        rs["start"] = repostorage.start.astimezone(pytz.utc)
        rs["end"] = repostorage.end.astimezone(pytz.utc)
        rs["gigabytes"] = repostorage.gigabytes
        rs["rootfolder"] = repostorage.rootfolder
        LOG.info(rs)
        info.context.db.collection("repo_storage_allocations").replace_one({"repo": rs["repo"], "storagename": rs["storagename"], "purpose": rs["purpose"], "start": rs["start"]}, rs, upsert=True)
        info.context.audit(AuditTrailObjectType.Repo, repo.name, "repoStorageAllocationUpsert", details=repostorage.purpose+"="+str(repostorage.gigabytes))
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

    @strawberry.mutation(permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def auditTrailAdd(self, theaud: AuditTrailInput, info: Info) -> AuditTrail:
        if not theaud.type or not theaud.name or not theaud.action:
            raise Exception("Audit trails need type, name and action information")
        if not theaud.actedby:
            theaud.actedby = info.context.username
        if not theaud.actedat:
            theaud.actedat = datetime.datetime.utcnow()
        return info.context.db.create("audit_trail", theaud)

    @strawberry.mutation(permission_classes=[ IsAuthenticated, IsAdmin ] )
    def notificationSend(self, msg: NotificationInput, info: Info) -> bool:
        return info.context.notify_raw(to=msg.to,subject=msg.subject,body=msg.body)


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
