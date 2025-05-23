from auth import IsAuthenticated, \
        IsRepoPrincipalOrLeader, \
        IsAdmin, \
        IsValidEPPN, \
        IsFacilityCzarOrAdmin

import asyncio
from threading import Thread
from typing import List, Optional, AsyncGenerator
import math
import datetime
import pytz
import json
import random
import string

import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET
from bson import ObjectId
from bson.json_util import dumps
from pymongo import ReplaceOne

from models import \
        MongoId, \
        User, UserInput, UserRegistration, \
        UserStorageInput, UserStorage, \
        AccessGroup, AccessGroupInput, \
        Repo, RepoInput, \
        Facility, FacilityInput, Job, \
        UserAllocationInput, UserAllocation, \
        ClusterInput, Cluster, ClusterTotals, \
        CoactRequestInput, CoactRequest, CoactRequestType, \
        CoactRequestEvent, CoactRequestStatus, CoactRequestWithPerms, \
        CoactRequestFilter, RepoFacilityName, \
        Usage, UsageInput, StorageDailyUsageInput, \
        ReportRangeInput, PerDateUsage, PerUserUsage, \
        RepoComputeAllocationInput, RepoStorageAllocationInput, \
        AuditTrailObjectType, AuditTrail, AuditTrailInput, \
        NotificationInput, Notification, ComputeRequirement, BulkOpsResult, StatusResult, \
        CoactDatetime, NormalizedJob, FacillityPastXUsage, RepoPastXUsage, \
        NameDesc, RepoFeature, RepoFeatureInput

import logging
LOG = logging.getLogger(__name__)

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        elif isinstance(o, float) and not math.isfinite(o):
            return str(o)
        elif isinstance(o, datetime.datetime):
            # Use var d = new Date(str) in JS to deserialize
            # d.toJSON() in JS to convert to a string readable by datetime.strptime(str, '%Y-%m-%dT%H:%M:%S.%fZ')
            return o.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        return json.JSONEncoder.default(self, o)

@strawberry.type
class Query:
    @strawberry.field
    def amIRegistered(self, info: Info) -> UserRegistration:
        request_id = None
        isRegis, eppn = info.context.isUserRegistered()
        userid = info.context.username
        regis_pending = False
        if not isRegis:
            regis_pending = len(info.context.db.find("requests", {"reqtype" : "UserAccount", "eppn" : eppn})) >= 1
            if regis_pending:
                thereq = list(info.context.db.collection("requests").find({"reqtype" : "UserAccount", "eppn" : eppn}).sort([("approvalstatus", -1), ("timeofrequest", -1)]))[0]
                request_id = thereq["_id"]
                userid = thereq["preferredUserName"]
            else:
                if info.context.eppn:
                    filter ={"eppns": info.context.eppn}
                    LOG.info("Looking up user from service using %s", filter)
                    lookupObjs = info.context.lookupUsersFromService(filter)
                    if lookupObjs and lookupObjs[0].username:
                        LOG.info("Found EPPN in lookup service %s", lookupObjs[0].username)
                        userid = lookupObjs[0].username
                    else:
                        LOG.warn("No matches from the user lookup service for eppn {}", info.context.eppn)
                else:
                    LOG.warn("Cannot determine the EPPN from HTTP headers")
        return UserRegistration(**{ "isRegistered": isRegis, "eppn": eppn, "isRegistrationPending": regis_pending, "fullname": info.context.fullname, "username": userid, "requestId": request_id })

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
    def getuserforeppn(self, info: Info, eppn: str) -> Optional[User]:
        user = info.context.db.collection("users").find_one( {"eppns": eppn} )
        return User(**user) if user else None
    
    @strawberry.field
    def usersMatchingUserName(self, info: Info, regex: str) -> Optional[List[User]]:
        users = info.context.db.collection("users").find( {"username": {"$regex": regex}} )
        return [ User(**user) for user in users ] if users else []

    @strawberry.field
    def usersMatchingUserNames(self, info: Info, regexes: List[str]) -> Optional[List[User]]:
        userlist = {}
        for regex in regexes:
            LOG.info("Searching for users matching %s", regex)
            users = info.context.db.collection("users").find( {"username": {"$regex": regex}} )
            userlist.update({x["username"]: x for x in users})
        return [ User(**user) for user in userlist.values() ] if userlist else []

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def usersLookupFromService(self, info: Info, filter: UserInput ) -> List[User]:
        return info.context.lookupUsersFromService( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def clusters(self, info: Info, filter: Optional[ClusterInput]={} ) -> List[Cluster]:
        return info.context.db.find_clusters( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def clusterPurchases(self, info: Info) -> List[ClusterTotals]:
        purchases = info.context.db.collection("facility_compute_purchases").aggregate([
            {"$group": { "_id": "$clustername", "totalservers": { "$sum": "$servers" } }},
            {"$project": { "_id": 0, "clustername": "$_id", "totalpurchased": "$totalservers"}}
        ])
        return [ ClusterTotals(**x) for x in purchases ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def storagenames(self, info: Info ) -> List[str]:
        return [x["name"] for x in info.context.db.collection("physical_volumes").find({})]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def storagepurposes(self, info: Info ) -> List[str]:
        return [ "data", "group", "scratch" ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilities(self, info: Info, filter: Optional[FacilityInput]={} ) -> List[Facility]:
        return info.context.db.find_facilities( filter)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilitiesIManage(self, info: Info ) -> List[Facility]:
        filter = { "czars" : info.context.username }
        if info.context.is_admin:
            filter = {}        
        return info.context.db.find_facilities( filter)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestTypes(self, info: Info ) -> List[str]:
        return [x[0] for x in CoactRequestType.__members__.items()]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestStatuses(self, info: Info ) -> List[str]:
        return [x[0] for x in CoactRequestStatus.__members__.items()]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requests(self, info: Info, fetchprocessed: Optional[bool]=False, showmine: Optional[bool]=True, filter: Optional[CoactRequestFilter]=UNSET) -> Optional[List[CoactRequestWithPerms]]:
        """
        Separate queries for admin/czar/leader/user
        """
        def __filter_to_query__():
            qterms = []
            if filter.reqtype:
                qterms.append({"reqtype": filter.reqtype.name})
            if filter.approvalstatus != UNSET:
                if filter.approvalstatus == 0:
                    qterms.append({"$or": [{"approvalstatus": filter.approvalstatus}, {"approvalstatus": {"$exists": False}}]})
                else:
                    qterms.append({"approvalstatus": filter.approvalstatus})
            if filter.reponame:
                qterms.append({ "reponame": {"$regex": filter.reponame}})
            if filter.facilityname:
                qterms.append({"facilityname": filter.facilityname})
            if filter.foruser:
                qterms.append({"$or": [{ "username": {"$regex": filter.foruser} }, { "preferredUserName": {"$regex": filter.foruser}}]})
            if filter.windowbegin and filter.windowend:
                qterms.append({"$and": [ { "timeofrequest": { "$gte": filter.windowbegin.astimezone(pytz.utc) } }, { "timeofrequest": { "$lt": filter.windowend.astimezone(pytz.utc) } } ]})
            return qterms

        def __fetch_requests__(qterms, applyperms=None):
            if filter:
                LOG.info(filter)
                # We only use certain terms from the filter; this is mainly a bug from the GraphQL defaults getting in the way of filter
                fqterms = __filter_to_query__()
                LOG.info(fqterms)
                if fqterms:
                    if "$and" in qterms:
                        qterms["$and"].extend(fqterms)
                    else:
                        if qterms:
                            fqterms.append(qterms)
                        qterms = {"$and": fqterms}

            LOG.info("Looking for requests using %s",  JSONEncoder(indent=4).encode(qterms))
            crsr = info.context.db.collection("requests").find(qterms).sort([("timeofrequest", -1)])
            rqs = info.context.db.cursor_to_objlist(crsr, CoactRequestWithPerms, exclude_fields={})
            if applyperms:
                for rq in rqs:
                    applyperms(rq)
            return rqs

        username = info.context.username
        assert username != None

        if showmine:
            return __fetch_requests__({"$or": [{ "requestedby": username }, { "username": username }, { "preferredUserName": username }]})

        myfacs = list(x.name for x in info.context.db.find_facilities({"czars": username}))
        isadmin = info.context.is_admin and not info.context.is_impersonating
        isczar = len(myfacs) != 0
        if isadmin:
            def __set_both_true__(rq):
                rq.canapprove = True
                rq.canrefire = True
            LOG.info("Requests for admin")
            queryterms = {}
            if not fetchprocessed:
                queryterms = {"$or": [{"approvalstatus": {"$exists": False}}, {"approvalstatus": {"$in": [0]}}]}
            return __fetch_requests__(queryterms, __set_both_true__)
        elif isczar:
            def __set_czar_perm__(rq):
                rq.canapprove = True
                rq.canrefire = True
            LOG.info("Requests for czar")
            queryterms = [{"facilityname": {"$in": myfacs }}]
            if not fetchprocessed:
                queryterms.append({"$or": [{"approvalstatus": {"$exists": False}}, {"approvalstatus": {"$in": [0]}}]}) # NotActedOn = 0
            return __fetch_requests__({"$and": queryterms }, __set_czar_perm__)
        else:
            LOG.info("Requests for regular user")
            leaderrepos = [ { "reponame": x.name, "facilityname": x.facility } for x in info.context.db.find_repos( { '$or': [ { "leaders": username }, { "principal": username } ] } ) ]
            queryterms = []
            permsfn = None
            if leaderrepos:
                myreqs = [{ "requestedby": username }, { "username": username }, { "preferredUserName": username }]
                myreqs.extend(leaderrepos)
                queryterms.append({"$or": myreqs })
                def __leaderpermfn__(rq):
                    if rq.reqtype == CoactRequestType.RepoMembership.name and { "reponame": rq.reponame, "facilityname": rq.facilityname } in leaderrepos:
                        rq.canapprove = True
                permsfn = __leaderpermfn__
            else:
                queryterms.append({"$or": [{ "requestedby": username }, { "username": username }, { "preferredUserName": username }]})
            if not fetchprocessed:
                queryterms.append({"$or": [{"approvalstatus": {"$exists": False}}, {"approvalstatus": {"$in": [0]}}]}) # NotActedOn = 0
            return __fetch_requests__({"$and": queryterms }, permsfn)

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def requestsExistingForEPPN(self, info: Info, eppn: str) -> Optional[List[CoactRequest]]:
        crsr = info.context.db.collection("requests").find({"eppn": eppn}).sort([("timeofrequest", -1)])
        return info.context.db.cursor_to_objlist(crsr, CoactRequest, exclude_fields={})

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def requestsExistingForUser(self, info: Info, username: str) -> Optional[List[CoactRequest]]:
        crsr = info.context.db.collection("requests").find({"username": username}).sort([("timeofrequest", -1)])
        return info.context.db.cursor_to_objlist(crsr, CoactRequest, exclude_fields={})

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def requestsExistingForRepo(self, info: Info, reponame: str, facilityname: str) -> Optional[List[CoactRequest]]:
        crsr = info.context.db.collection("requests").find({"reponame": reponame, "facilityname": facilityname}).sort([("timeofrequest", -1)])
        return info.context.db.cursor_to_objlist(crsr, CoactRequest, exclude_fields={})

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facility(self, info: Info, filter: Optional[FacilityInput]) -> Facility:
        return info.context.db.find_facilities( filter )[0]
    
    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilityRecentComputeUsage(self, info: Info, past_minutes: int, skipQoses: List[str] = [ "preemptable" ]) -> Optional[List[FacillityPastXUsage]]:
        """
        Compute the past_x report ( compute usage used in the past 5 minutes ) straight from the jobs collection.
        Used mainly to enforce burst allocation usage
        """
        past_x_start = datetime.datetime.utcnow() - datetime.timedelta(minutes=past_minutes)
        pacificdaylight = pytz.timezone('America/Los_Angeles')
        LOG.info("Computing the past_x aggregate for %s minutes using jobs whose start time is > %s (%s)", past_minutes, past_x_start.astimezone(pacificdaylight), past_x_start.isoformat())
        myfacs = [ x.name for x in Query().facilitiesIManage(info) ]
        aggs = list(info.context.db.collection("jobs").aggregate([
            { "$match": { "endTs": { "$gte": past_x_start }, "qos": { "$nin": skipQoses }}},
            { "$project": { 
                "allocationId": 1, 
                "resourceHours": {
                    "$cond": {
                        "if": { "$gte": [ "$startTs", {"$literal": past_x_start}]},
                        "then": "$resourceHours",
                        "else": {
                            "$multiply": [
                                "$resourceHours", 
                                { "$divide": [
                                    {"$subtract": [ "$endTs", {"$literal": past_x_start}]}, 
                                    {"$subtract": [ "$endTs", "$startTs"]}
                                ]}
                        ]}
                    }            
                }
            }},
            { "$group": { "_id": {"allocationId": "$allocationId" }, "resourceHours": { "$sum": "$resourceHours" }}},
            { "$project": { "_id": 0, "allocationId": "$_id.allocationId", "resourceHours": 1 }},
            { "$lookup": { "from": "repo_compute_allocations", "localField": "allocationId", "foreignField": "_id", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$group": { "_id": {"repoid": "$allocation.repoid", "clustername": "$allocation.clustername" }, "resourceHours": {"$sum":  "$resourceHours"}} },
            { "$project": { "_id": 0, "repoid": "$_id.repoid", "clustername": "$_id.clustername", "resourceHours": 1 }},
            { "$lookup": { "from": "repos", "localField": "repoid", "foreignField": "_id", "as": "repo"}},
            { "$unwind": "$repo" },
            { "$match": {"repo.facility": {"$in": myfacs}}},
            { "$group": { "_id": {"facility": "$repo.facility", "clustername": "$clustername" }, "resourceHours": {"$sum":  "$resourceHours"}} },
            { "$project": { "_id": 0, "facility": "$_id.facility", "clustername": "$_id.clustername", "resourceHours": 1, "percentUsed": { "$literal": 0.0 } }}
        ]))
        purs = list(info.context.db.collection("facility_compute_purchases").aggregate([
            { "$lookup": { "from": "clusters", "localField": "clustername", "foreignField": "name", "as": "cluster"}},
            { "$unwind": "$cluster" },
            { "$project": { "_id": 0, "facility": "$facility", "clustername": "$clustername", "purchasedNodes": { "$multiply": [ "$servers", "$cluster.nodecpucount"  ] } }},
        ]))
        fac2prs = { (x["facility"], x["clustername"]) : x["purchasedNodes"]*(past_minutes/60.0) for x in purs }
        for usg in aggs:
            adj = fac2prs.get((usg["facility"], usg["clustername"]), 0)
            if adj:
                usg["percentUsed"] = (usg["resourceHours"]/adj)*100.0

        return [ FacillityPastXUsage(**{k:x.get(k, 0) for k in ["facility", "clustername", "resourceHours", "percentUsed" ] }) for x in aggs ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_groups(self, info: Info, filter: Optional[AccessGroupInput]={} ) -> List[AccessGroup]:
        return info.context.db.find_access_groups( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_group(self, info: Info, filter: Optional[AccessGroupInput]) -> AccessGroup:
        return info.context.db.find_access_group( filter )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repos(self, info: Info, filter: Optional[RepoInput]={} ) -> List[Repo]:
        username = info.context.username
        assert username != None
        myfacs = list(x.name for x in info.context.db.find_facilities({"czars": username}))
        isczar = len(myfacs) != 0
        isadmin = info.context.is_admin and not info.context.is_impersonating
        search = info.context.db.to_dict(filter)
        if isadmin:
            pass
        elif isczar:
            if "facility" not in search:
                search["facility"]= { "$in": myfacs }
        else:
            search["users"] = username
        LOG.debug(f"searching for repos using {filter} -> {search}")
        cursor = info.context.db.collection("repos").find(search)
        return info.context.db.cursor_to_objlist(cursor, Repo, exclude_fields=["access_groups", "features"])

    @strawberry.field
    def facilityNames(self, info: Info) -> List[str]:
        """
        Just the facility names. No authentication needed.
        """
        return [ x["name"] for x in info.context.db.collection("facilities").find({}, {"_id": 0, "name": 1}) ]
    
    @strawberry.field
    def facilityNameDescs(self, info: Info) -> List[NameDesc]:
        """
        Just the facility names and descriptions. No authentication needed.
        """
        return [ NameDesc(**x) for x in info.context.db.collection("facilities").find({}, {"_id": 0, "name": 1, "description": 1}) ]

    @strawberry.field
    def allreposandfacility(self, info: Info) -> List[RepoFacilityName]:
        """
        All the repo names and their facility. No authentication needed. Just the names
        """
        return [ RepoFacilityName(**x) for x in info.context.db.collection("repos").find({}, {"_id": 0, "name": 1, "facility": 1}) ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def myreposandfacility(self, info: Info) -> List[RepoFacilityName]:
        """
        My repo names and their facility. Just the names
        """
        username = info.context.username
        assert username != None
        myfacs = list(x.name for x in info.context.db.find_facilities({"czars": username}))
        isadmin = info.context.is_admin and not info.context.is_impersonating
        isczar = len(myfacs) != 0
        if isadmin:
            return [ RepoFacilityName(**x) for x in info.context.db.collection("repos").find({}, {"_id": 0, "name": 1, "facility": 1}) ]
        elif isczar:
            return [ RepoFacilityName(**x) for x in info.context.db.collection("repos").find({"facility": {"$in": myfacs}}, {"_id": 0, "name": 1, "facility": 1}) ]
        else:
            return [ RepoFacilityName(**x) for x in info.context.db.collection("repos").find({ '$or': [ { "users": username }, { "leaders": username }, { "principal": username }]}, {"_id": 0, "name": 1, "facility": 1}) ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repo(self, filter: RepoInput, info: Info) -> Repo:
        username = info.context.username
        assert username != None
        myfacs = list(x.name for x in info.context.db.find_facilities({"czars": username}))
        isczar = len(myfacs) != 0
        isadmin = info.context.is_admin and not info.context.is_impersonating
        search = info.context.db.to_dict(filter)
        if isadmin:
            pass
        elif isczar:
            search["facility"]= { "$in": myfacs }
        else:
            search["users"] = username
        LOG.debug(f"searching for repos using {filter} -> {search}")
        theRepo = info.context.db.collection("repos").find_one(search)
        return info.context.db.cursor_to_objlist([theRepo], Repo, exclude_fields=["access_groups", "features"])[0]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def myRepos(self, info: Info) -> List[Repo]:
        username = info.context.username
        assert username != None
        allrepos = {}
        allrepos.update({ (x.facility, x.name) : x for x in info.context.db.find_repos( { '$or': [
            { "users": username },
            { "leaders": username },
            { "principal": username }
        ] } )})
        
        if info.context.showallforczars:
            if info.context.is_admin:
                allrepos = { (x.facility, x.name) : x for x in info.context.db.find_repos( { } )}
            else:
                LOG.error("Need to show all repos for a czar")
                facilities = info.context.db.find_facilities({ 'czars': username })
                if not facilities:
                    raise Exception("No facilities found for czar " + username)
                allrepos.update({ (x.facility, x.name) : x for x in info.context.db.find_repos( { "facility": { "$in": [ x.name for x in facilities ] } } )})
        
        return sorted(allrepos.values(), key=lambda x: x.name)

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
    def reposInFacilityWithComputeRequirement( self, info: Info, facility: str, computerequirement: ComputeRequirement ) -> List[str]:
        matches = info.context.db.collection("repo_compute_allocations").aggregate([
            {"$match": {"computerequirement": computerequirement.name }},
            { "$lookup": { "from": "repos", "localField": "repoid", "foreignField": "_id", "as": "repo"}},
            { "$unwind": "$repo" },
            {"$match": {"repo.facility": facility }},
            { "$project": { "name": "$repo.name" }}
        ])
        return list(set([ x["name"] for x in matches ]))

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
            { "$match": { "date": {"$gte": range.start, "$lte": range.end} } },
            { "$lookup": { "from": "repo_compute_allocations", "localField": "allocationId", "foreignField": "_id", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$match": { "allocation.clustername": clustername } },
            { "$group": { "_id": {"repoid": "$allocation.repoid", "date" : timegrp }, "resourceHours": {"$sum":  "$resourceHours"}} },
            { "$project": { "_id": 0, "repoid": "$_id.repoid", "date": "$_id.date", "resourceHours": 1 }},
            { "$lookup": { "from": "repos", "localField": "repoid", "foreignField": "_id", "as": "repo"}},
            { "$unwind": "$repo" },
            { "$project": { "_id": 0, "repo": "$repo.name", "facility": "$repo.facility", "date": "$date", "resourceHours": 1 }},
            { "$sort": { "date": -1 }}
        ])
        return info.context.db.cursor_to_objlist(usgs, PerDateUsage, {})

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reportFacilityComputeByUser( self, info: Info, clustername: str, range: ReportRangeInput ) -> List[PerUserUsage]:
        LOG.debug("Getting compute user data for cluster %s from %s to %s ", clustername, range.start, range.end)
        usgs = info.context.db.collection("repo_daily_peruser_compute_usage").aggregate([
            { "$match": { "date": {"$gte": range.start, "$lte": range.end} } },
            { "$lookup": { "from": "repo_compute_allocations", "localField": "allocationId", "foreignField": "_id", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$match": { "allocation.clustername": clustername } },
            { "$group": { "_id": {"repoid": "$allocation.repoid", "username" : "$username" }, "resourceHours": {"$sum":  "$resourceHours"}} },
            { "$project": { "_id": 0, "repoid": "$_id.repoid", "username": "$_id.username", "resourceHours": 1 }},
            { "$lookup": { "from": "repos", "localField": "repoid", "foreignField": "_id", "as": "repo"}},
            { "$unwind": "$repo" },
            { "$project": { "_id": 0, "repo": "$repo.name", "facility": "$repo.facility", "username": "$username", "resourceHours": 1 }},
            { "$sort": { "resourceHours": -1 }}
        ])
        return info.context.db.cursor_to_objlist(usgs, PerUserUsage, {})


    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin  ] )
    def reportFacilityComputeOverall( self, info: Info, clustername: str, group: str) -> List[PerDateUsage]:
        LOG.debug("Getting compute overall data by faciliy for cluster %s grouped by %s", clustername, group)
        if group == "Day":
            timegrp = "$date"
        elif group == "Week":
            timegrp = { "$dateTrunc": {"date": "$date", "unit": "week", "timezone": "America/Los_Angeles"}}
        elif group == "Month":
            timegrp = { "$dateTrunc": {"date": "$date", "unit": "month", "timezone": "America/Los_Angeles"}}
        else:
            raise Exception(f"Unsupported group by {group}")

        usgs = info.context.db.collection("repo_daily_compute_usage").aggregate([
            { "$lookup": { "from": "repo_compute_allocations", "localField": "allocationId", "foreignField": "_id", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$match": { "allocation.clustername": clustername } },
            { "$group": { "_id": {"repoid": "$allocation.repoid", "date" : timegrp }, "resourceHours": {"$sum":  "$resourceHours"}} },
            { "$project": { "_id": 0, "repoid": "$_id.repoid", "date": "$_id.date", "resourceHours": 1 }},
            { "$lookup": { "from": "repos", "localField": "repoid", "foreignField": "_id", "as": "repo"}},
            { "$unwind": "$repo" },
            { "$group": { "_id": {"facility": "$repo.facility", "date" : "$date" }, "resourceHours": {"$sum":  "$resourceHours"}} },
            { "$project": { "_id": 0, "facility": "$_id.facility", "date": "$_id.date", "resourceHours": 1 }},
            { "$sort": { "date": 1, "facility": 1 }}
        ])
        return info.context.db.cursor_to_objlist(usgs, PerDateUsage, {})

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reportFacilityStorage( self, info: Info, storagename: str, purpose: Optional[str] = UNSET ) -> List[Usage]:
        LOG.debug("Storage report for storage %s for purpose %s ", storagename, purpose)
        groupby = {"repoid": "$allocation.repoid" }
        project = { "_id": 0, "repoid": "$_id.repoid", "gigabytes": 1, "inodes": 1 }
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
    def repoRecentComputeUsage(self, info: Info, past_minutes: int, skipQoses: List[str] = [ "preemptable" ]) -> Optional[List[RepoPastXUsage]]:
        """
        Compute the past_x report for all my repos ( compute usage used in the past x minutes ) straight from the jobs collection.
        This query may not perform well if the range is for more than a couple of days.
        In that case, use the reportFacilityComputeByDay to get a daily breakdown.
        """
        past_x_start = datetime.datetime.utcnow() - datetime.timedelta(minutes=past_minutes)
        pacificdaylight = pytz.timezone('America/Los_Angeles')
        LOG.info("Computing the past_x aggregate for %s minutes using jobs whose start time is > %s (%s) skipping qoses %s", past_minutes, past_x_start.astimezone(pacificdaylight), past_x_start.isoformat(), ",".join(skipQoses))
        aggs = list(info.context.db.collection("jobs").aggregate([
            { "$match": { "endTs": { "$gte": past_x_start }, "qos": { "$nin": skipQoses }}},
            { "$project": { 
                "allocationId": 1, 
                "resourceHours": {
                    "$cond": {
                        "if": { "$gte": [ "$startTs", {"$literal": past_x_start}]},
                        "then": "$resourceHours",
                        "else": {
                            "$multiply": [
                                "$resourceHours", 
                                { "$divide": [
                                    {"$subtract": [ "$endTs", {"$literal": past_x_start}]}, 
                                    {"$subtract": [ "$endTs", "$startTs"]}
                                ]}
                        ]}
                    }            
                }
            }},
            { "$group": { "_id": {"allocationId": "$allocationId" }, "resourceHours": { "$sum": "$resourceHours" }}},
            { "$project": { "_id": 0, "allocationId": "$_id.allocationId", "resourceHours": 1 }},
            { "$lookup": { "from": "repo_compute_allocations", "localField": "allocationId", "foreignField": "_id", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$group": { "_id": {"repoid": "$allocation.repoid", "clustername": "$allocation.clustername" }, "resourceHours": {"$sum":  "$resourceHours"}} },
            { "$project": { "_id": 0, "repoid": "$_id.repoid", "clustername": "$_id.clustername", "resourceHours": 1 }},
            { "$lookup": { "from": "repos", "localField": "repoid", "foreignField": "_id", "as": "repo"}},
            { "$unwind": "$repo" },
            { "$project": { "_id": 0, "name": "$repo.name", "facility": "$repo.facility", "clustername": "$clustername", "resourceHours": 1, "percentUsed": { "$literal": 0.0 } }}
        ]))
        purs = list(info.context.db.collection("facility_compute_purchases").aggregate([
            { "$lookup": { "from": "clusters", "localField": "clustername", "foreignField": "name", "as": "cluster"}},
            { "$unwind": "$cluster" },
            { "$project": { "_id": 0, "facility": "$facility", "clustername": "$clustername", "purchasedNodes": { "$multiply": [ "$servers", "$cluster.nodecpucount"  ] } }},
        ]))
        fac2prs = { (x["facility"], x["clustername"]) : x["purchasedNodes"]*(past_minutes/60.0) for x in purs}
        for usg in aggs:
            adj = fac2prs.get((usg["facility"], usg["clustername"]), 0)
            if adj:
                usg["percentUsed"] = (usg["resourceHours"]/adj)*100.0
        my_repos = [ (x.name, x.facility) for x in Query().repos(info) ]
        return [ RepoPastXUsage(**{k:x.get(k, 0) for k in ["name", "facility", "clustername", "resourceHours", "percentUsed" ] }) for x in aggs if (x["name"], x["facility"]) in my_repos ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userAuditTrails( self, info: Info ) -> List[AuditTrail]:
        userObj = info.context.db.find_user({"username": info.context.username })
        return info.context.db.cursor_to_objlist(info.context.db.collection("audit_trail").find({ "type": AuditTrailObjectType.User.name, "actedon": userObj._id }).sort([("actedat", -1)]), AuditTrail)

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repoAuditTrails( self, repo: RepoInput, info: Info ) -> List[AuditTrail]:
        repoObj = info.context.db.find_repo(repo)
        return info.context.db.cursor_to_objlist(info.context.db.collection("audit_trail").find({ "type": AuditTrailObjectType.Repo.name, "actedon": repoObj._id }).sort([("actedat", -1)]), AuditTrail)
    
    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repoComputeJobs( self, rca: RepoComputeAllocationInput, past_x_mins: int, info: Info ) -> List[NormalizedJob]:
        past_x_start = datetime.datetime.utcnow() - datetime.timedelta(minutes=past_x_mins)
        jobs = info.context.db.collection("jobs").aggregate([
            { "$match": {"endTs": { "$gte": past_x_start }, "allocationId": rca._id }},
            { "$project": { 
                "_id": 0,
                "allocationId": 1,
                "jobId": 1,
                "username": 1,
                "qos": 1,
                "startTs": 1,
                "endTs": 1,
                "resourceHours": 1,
                "normalizedResourceHours": {
                    "$cond": {
                        "if": { "$gte": [ "$startTs", {"$literal": past_x_start}]},
                        "then": "$resourceHours",
                        "else": {
                            "$multiply": [
                                "$resourceHours", 
                                { "$divide": [
                                    {"$subtract": [ "$endTs", {"$literal": past_x_start}]}, 
                                    {"$subtract": [ "$endTs", "$startTs"]}
                                ]}
                        ]}
                    }            
                },
                "durationMillis": {"$subtract": [ "$endTs", "$startTs"]}
            }},
            {"$sort": { "jobId": -1 }}
        ])
        return info.context.db.cursor_to_objlist(jobs, NormalizedJob)
    

@strawberry.type
class Mutation:

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def userUpsert(self, user: UserInput, info: Info) -> User:
        user = info.context.db.update( 'users', user, required_fields=[ 'username', 'eppns', 'shell', 'preferredemail' ], find_existing={ 'username': user.username }, upsert=True )
        info.context.audit(AuditTrailObjectType.User, user._id, "userUpsert")
        return user

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdate(self, user: UserInput, info: Info) -> User:
        u = info.context.db.to_dict(user)
        for k in list(u.keys()):
          if not k in ( '_id', 'username' ):
            del u[k]
        user_before_update = info.context.db.find_user( u )
        if not info.context.username == user_before_update.username and not info.context.is_admin:
            raise Exception(f"Only admins can update other users - {info.context.username} wants to update {user.username}")
        user_after_update = info.context.db.update( 'users', user, required_fields=[ '_id' ], find_existing={ '_id': user_before_update._id } )
        info.context.audit(AuditTrailObjectType.User, user_after_update._id, "userUpdate", details=info.context.dict_diffs(user_before_update, user_after_update))
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
        info.context.audit(AuditTrailObjectType.User, info.context._id, "userUpdateEppn", details=",".join(eppns))
        return info.context.db.find_user( {"username": logged_in_user} )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userChangeShell(self, newshell: str, info: Info) -> User:
        LOG.info("Changing shell for user %s to %s", info.context.username, newshell)
        info.context.db.collection("users").update_one({"username": info.context.username}, {"$set": {"shell": newshell}})
        info.context.audit(AuditTrailObjectType.User, info.context._id, "userChangeShell", details=newshell)
        return info.context.db.find_user( {"username": info.context.username} )

    @strawberry.field( permission_classes=[ IsFacilityCzarOrAdmin ] )
    def userStorageAllocationUpsert(self, user: UserInput, userstorage: UserStorageInput, info: Info) -> User:
        LOG.info("Creating or updating home storage allocation for user %s", user)
        theuser = info.context.db.find_user(user)
        userstorage.validate()
        info.context.db.collection("user_storage_allocation").update_one(
            {"username": theuser.username, "storagename": userstorage.storagename, "purpose": userstorage.purpose },
            {"$set": { "gigabytes": userstorage.gigabytes, "rootfolder": userstorage.rootfolder}},
            upsert=True)
        info.context.audit(AuditTrailObjectType.User, theuser._id, "UserStorageAllocation", details=userstorage.purpose+"="+str(userstorage.gigabytes)+"GB on "+userstorage.storagename)
        return theuser

    @strawberry.field( permission_classes=[ IsValidEPPN ] )
    def requestNewSDFAccount(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        request.timeofrequest = datetime.datetime.utcnow()
        if request.approvalstatus == CoactRequestStatus.PreApproved:
            if not IsFacilityCzarOrAdmin.isFacilityCzarOrAdmin(request.facilityname, info):
                raise Exception("Only facility czars and admin can create preapproved requests")
        eppnparts = request.eppn.split("@")
        request.eppn = eppnparts[0] + "@" + eppnparts[1].lower()
        userAlreadyExists = info.context.db.collection("users").find_one( {"eppns": request.eppn} ) != None
        LOG.info(f"Check for user already exists yields {userAlreadyExists}")
        # Check if the user already has a pending/completed request for this facility
        exis_req = info.context.db.find_requests({'reqtype': 'UserAccount', 'eppn': request.eppn, 'facilityname': request.facilityname})
        if exis_req:
            raise Exception(f"There is aready a request for this user in this facility with status {CoactRequestStatus(exis_req[0].approvalstatus).name}")
        if not request.preferredUserName:
            raise Exception(f"We are not able to determine your user id with certainty. It's likely that your user account setup has not completed yet or we may be having an outage upstream. Could you please try again later? If you continue to experience this error, please contact <b>s3df-help@slac.stanford.edu</b>")
        this_req = info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing={'reqtype': 'UserAccount', 'eppn': request.eppn, 'facilityname': request.facilityname, 'approvalstatus': { "$exists": False }} )
        if request.approvalstatus == CoactRequestStatus.PreApproved and userAlreadyExists:
            LOG.info("The user account for %s has already been created; approving the preapproved request and skipping sending emails", request.eppn)
            this_req.approve(info)
        else:
            info.context.notify( this_req )
        return this_req

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestRepoMembership(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoMembership or not request.reponame or not request.facilityname:
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
        if request.reqtype != CoactRequestType.RepoComputeAllocation or not request.reponame or not request.facilityname or not request.clustername or request.percent_of_facility < 0.0:
            raise Exception("Please specify the required parameters")
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        facility = info.context.db.find_facility({"name": request.facilityname})
        current_purchases = [x.purchased for x in facility.computepurchases(info) if x.clustername == request.clustername]
        if not current_purchases:
            raise Exception("The facility " + request.facilityname + " does not have access to the cluster "+ request.clustername)
        current_purchase = current_purchases[0] if current_purchases else 0
        request.allocated = (current_purchase/100.0)*request.percent_of_facility
        request.burst_allocated = (current_purchase/100.0)*request.burst_percent_of_facility
        LOG.info("Current purchase for %s is %s. Allocating %s", request.facilityname, current_purchase, request.allocated)
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def requestRepoStorageAllocation(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoStorageAllocation or not request.reponame or not request.facilityname or not request.allocationid or not request.gigabytes:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype', "allocationid", "gigabytes" ], find_existing=None)

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def requestRepoChangeComputeRequirement(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.RepoChangeComputeRequirement or not request.reponame or not request.facilityname:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestUserQuota(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.UserStorageAllocation or not request.storagename or not request.gigabytes:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
    
    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestUserChangeShell(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.UserChangeShell or not request.shell:
            raise Exception()
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = CoactRequestStatus.Approved
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requestUserPublicHtml(self, request: CoactRequestInput, info: Info) -> CoactRequest:
        if request.reqtype != CoactRequestType.UserPublicHtml or request.publichtml is UNSET:
            raise Exception("Incorrect request type")
        existing = info.context.db.find_requests(CoactRequestInput(username=info.context.username, reqtype=CoactRequestType.UserPublicHtml.name, publichtml=request.publichtml))
        if existing and any(map(lambda x : x.approvalstatus != CoactRequestStatus.Completed, existing)):
            raise Exception("A request for turning on public HTML already exists and will be processed shortly.")
        request.username = info.context.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = CoactRequestStatus.Approved
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
            therepos = info.context.db.find_repos({"name": thereq.reponame, "facility": thereq.facilityname})
            if therepos:
                therepo = info.context.db.find_repo({"name": thereq.reponame, "facility": thereq.facilityname})
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
            theeppn = thereq.eppn
            if not theeppn:
                raise Exception("Account request without a eppn - cannot approve.")
            okToApprove = isAdmin or isCzar
            if not okToApprove:
                raise Exception("User is not an admin or a czar")
            # Check if the preferredUserName already is in use
            preferredUserName = thereq.preferredUserName
            if not preferredUserName:
                raise Exception("Account request without a preferred user id - cannot approve.")
            alreadyExistingUser = info.context.db.collection("users").find_one( { "username": preferredUserName} )
            if alreadyExistingUser:
                LOG.info("User with username " + preferredUserName + " already exists")
            thefacility = thereq.facilityname
            if not thefacility:
                raise Exception("Account request without a facility - cannot approve.")
            luuserobj = info.context.lookupUserInServiceUsingEPPN(theeppn)
            if not luuserobj or not luuserobj.get("uidnumber", None):
                # UID number is null; either no UNIX account or we have not synced yet.
                raise Exception("It's likely that the user does not have a UNIX account or that the caches have not synced yet. Cannot approve now; please try again later.")
            
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
            thefacility = thereq.facilityname
            if not thefacility:
                raise Exception("New repo request without a facility - cannot approve.")
            if info.context.db.find_repos( {"name": thereponame, "facility": thefacility} ):
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
            thefacility = thereq.facilityname
            if not thefacility:
                raise Exception("RepoComputeAllocation request without a facility - cannot approve.")
            if not info.context.db.find_repos( {"name": thereponame, "facility": thefacility} ):
                raise Exception(f"Repo with name {thereponame} does not exist")
            theclustername = thereq.clustername
            if not theclustername:
                raise Exception("RepoComputeAllocation request without a cluster name - cannot approve.")
            if not info.context.db.find_clusters( {"name": theclustername} ):
                raise Exception(f"Cluster with name {theclustername} does not exist")
            if thereq.percent_of_facility < 0:
                raise Exception("RepoComputeAllocation without a percent of facility - cannot approve.")
            if thereq.allocated < 0:
                raise Exception("RepoComputeAllocation without an absolute allocation - cannot approve.")
            if thereq.burst_percent_of_facility < 0:
                raise Exception("RepoComputeAllocation without a burst percent of facility - cannot approve.")
            if thereq.burst_allocated < 0:
                raise Exception("RepoComputeAllocation without an absolute burst allocation - cannot approve.")
            if not thereq.start:
                thereq.start = datetime.datetime.utcnow()
            if not thereq.end:
                thereq.end = datetime.datetime.utcnow().replace(year=2100, month=1, day=1)
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
            thefacility = thereq.facilityname
            if not thefacility:
                raise Exception("RepoComputeAllocation request without a facility - cannot approve.")
            therepo = info.context.db.find_repo( {"name": thereponame, "facility": thefacility} )
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
                thereq.end = datetime.datetime.utcnow().replace(year=2100, month=1, day=1)

            thereq.approve(info)
            return True
        elif thereq.reqtype == "RepoChangeComputeRequirement":
            if not isAdmin and not isCzar:
                raise Exception("User is not an admin or a czar")
            thereponame = thereq.reponame
            if not thereponame:
                raise Exception("RepoComputeAllocation request without a repo name - cannot approve.")
            thefacility = thereq.facilityname
            if not thefacility:
                raise Exception("RepoComputeAllocation request without a facility - cannot approve.")
            therepo = info.context.db.find_repo( {"name": thereponame, "facility": thefacility} )
            if not therepo:
                raise Exception(f"Repo with name {thereponame} does not exist")
            if not thereq.computerequirement:
                raise Exception(f"The new compute requirement was not specified")
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

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def requestReopen(self, id: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        if thereq.approvalstatus != -1:
            raise Exception("We can only reopen rejected requests. Did you mean refire?")
        thereq.reopen(info)
        return True

    @strawberry.field
    def requestApprovePreApproved(self, id: str, info: Info) -> bool:
        """
        Separate mutation for preapproved requests; this use case may not have authentication.
        For now, we only support PreApproved UserAccount requests.
        This also gives us a chance to check external systems for username overlap etc.
        """
        LOG.debug(id)
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        isRegis, eppn = info.context.isUserRegistered()
        oktoapprove = thereq.reqtype == "UserAccount" and thereq.approvalstatus == CoactRequestStatus.PreApproved and eppn == thereq.eppn
        if not oktoapprove:
            raise Exception("Cannot approve preapproved request " + id)
        if isRegis:
            raise Exception("User is already registered for request " + id)
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
        other_preapproved_requests = info.context.db.find_requests({"reqtype" : "UserAccount", "eppn" : eppn, "approvalstatus": 4})
        if other_preapproved_requests:
            LOG.info("Automatically approving other preapproved requests for the same user")
            for oreq in other_preapproved_requests:
                LOG.info("Approving another preapproved request %s for the facility %s", oreq._id, oreq.facilityname)
                oreq.approve(info)
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def requestUpdateFacility(self, id: str, newfacility: str, info: Info) -> bool:
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        if not thereq:
            raise Exception("Cannot find request with id")
        if thereq.approvalstatus not in [ CoactRequestStatus.NotActedOn, CoactRequestStatus.Rejected, CoactRequestStatus.PreApproved ]:
            raise Exception("Requests in this state cannot be modified")
        thereq.changeFacility(info, newfacility)
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        info.context.notify( thereq )
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
        info.context.audit(AuditTrailObjectType.Repo, ret.repoid, "accessGroupCreate", details=accessgroup.name)
        return ret

    @strawberry.field( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def accessGroupUpdate(self, repo: RepoInput, access_group: AccessGroupInput, info: Info) -> AccessGroup:
        group_before_update = info.context.db.find_access_group(access_group)
        group_after_update = info.context.db.update( 'access_groups', info, access_group, required_fields=[ 'Id', ], find_existing={ '_id': access_group._id } )
        info.context.audit(AuditTrailObjectType.Repo, group_after_update.repoid, "accessGroupUpdate", details=info.context.dict_diffs(group_before_update, group_after_update))
        return group_after_update

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoUpsert(self, repo: RepoInput, info: Info) -> Repo:
        repo = info.context.db.update( 'repos', repo, required_fields=[ 'name', 'facility', 'principal' ], find_existing={ 'name': repo.name, 'facility': repo.facility }, upsert=True )
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "RepoUpsert")
        return repo

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoCreate(self, repo: RepoInput, info: Info) -> Repo:
        repo = info.context.db.create( 'repos', repo, required_fields=[ 'name', 'facility', 'principal' ], find_existing={ 'name': repo.name, 'facility': repo.facility } )
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "repoCreate")
        return repo

    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoUpdate(self, repo: RepoInput, info: Info) -> Repo:
        repo_before_update = info.context.db.find_repo({ 'name': repo.name, "facility": repo.facility })
        repo_after_update = info.context.db.update( 'repos', repo, required_fields=[ 'name', 'facility' ], find_existing={ 'name': repo.name, "facility": repo.facility } )
        info.context.audit(AuditTrailObjectType.Repo, repo_after_update._id, "repoUpdate", details=info.context.dict_diffs(repo_before_update, repo_after_update))
        return repo_after_update

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoUpdateUserAllocation(self, repo: RepoInput, data: List[UserAllocationInput], info: Info) -> Repo:
        filter = {"name": repo.name, "facility": repo.facility}
        therepo =  info.context.db.find_repo( filter )
        uas = [dict(j.__dict__.items()) for j in data]
        keys = ["username", "allocationid", ]
        for ua in uas:
            nua = {k: v for k,v in ua.items() if not v is UNSET}
            info.context.db.collection("user_allocations").replace_one({k: v for k,v in nua.items() if k in keys}, nua, upsert=True)
        info.context.audit(AuditTrailObjectType.Repo, therepo._id, "repoUpdateUserAllocation")
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoAddUser(self, repo: RepoInput, user: UserInput, info: Info ) -> Repo:
        filter = {"name": repo.name, "facility": repo.facility}
        repoObj = info.context.db.find_repo(filter)
        userObj = info.context.db.find_user({"username": user.username})
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"users": user.username}})
        repoObj = info.context.db.find_repo(filter)
        request: CoactRequestInput = CoactRequestInput()
        request.reqtype = CoactRequestType.RepoMembership
        request.reponame = repo.name
        request.facilityname = repoObj.facility
        request.username = user.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = 1
        info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        info.context.audit(AuditTrailObjectType.Repo, repoObj._id, "repoAddUser", details=user.username)
        info.context.audit(AuditTrailObjectType.User, userObj._id, "+RepoMembership", details=repo.name)
        return repoObj

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoAppendMember(self, repo: RepoInput, user: UserInput, info: Info ) -> Repo:
        """
        Add a user to a repo without creating a request. This is meant to be used by backend processors after updating the various external systems.
        """
        filter = {"name": repo.name, "facility": repo.facility}
        repoObj = info.context.db.find_repo(filter)
        userObj = info.context.db.find_user({"username": user.username})
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"users": user.username}})
        repoObj = info.context.db.find_repo(filter)
        info.context.audit(AuditTrailObjectType.Repo, repoObj._id, "repoAddUser", details=user.username)
        info.context.audit(AuditTrailObjectType.User, userObj._id, "+RepoMembership", details=repo.name)
        return repoObj

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoAddLeader(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name, "facility": repo.facility}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"leaders": user.username}})
        ret = info.context.db.find_repo(filter)
        info.context.audit(AuditTrailObjectType.Repo, ret._id, "repoAddLeader", details=user.username)
        return ret

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoChangePrincipal(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name, "facility": repo.facility}
        repoObj = info.context.db.find_repo(filter)
        if user.username not in repoObj.users:
            raise Exception(user.username + " is not a user in repo " + repo.name)        
        info.context.db.collection("repos").update_one(filter, { "$set": {"principal": user.username}})
        ret = info.context.db.find_repo(filter)
        info.context.audit(AuditTrailObjectType.Repo, ret._id, "repoChangePrincipal", details=user.username)
        return ret

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoRemoveUser(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name, "facility": repo.facility}
        therepo =  info.context.db.find_repo( filter )
        userObj = info.context.db.find_user( { "username": user.username } )
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
        if theuser == therepo.principal:
            raise Exception(theuser + " is a PI in repo " + repo.name + ". Cannot be removed from the repo")
        request: CoactRequestInput = CoactRequestInput()
        request.reqtype = CoactRequestType.RepoRemoveUser
        request.reponame = repo.name
        request.facilityname = repo.facility
        request.username = user.username
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = 1
        info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        info.context.db.collection("repos").update_one(filter, { "$pull": {"leaders": theuser, "users": theuser}})
        info.context.audit(AuditTrailObjectType.Repo, therepo._id, "repoRemoveUser", details=user.username)
        info.context.audit(AuditTrailObjectType.User, userObj._id, "-RepoMembership", details=repo.name)
        return info.context.db.find_repo( filter )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoToggleUserRole(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name, "facility": repo.facility}
        therepo = info.context.db.find_repo( filter )
        theuser = user.username
        if theuser not in therepo.users:
            LOG.warning(theuser + " is not a user in repo " + repo.name)
        info.context.db.collection("repos").update_one({"name": repo.name, "facility": repo.facility}, [{ "$set":
            { "leaders": { "$cond": [
                { "$in": [ user.username, "$leaders" ] },
                { "$setDifference": [ "$leaders", [ user.username ] ] },
                { "$concatArrays": [ "$leaders", [ user.username ] ] }
                ]}}}])
        info.context.audit(AuditTrailObjectType.Repo, therepo._id, "repoToggleUserRole", details=user.username)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def repoToggleGroupMembership(self, repo: RepoInput, user: UserInput, group: AccessGroupInput, info: Info) -> AccessGroup:
        filter = {"name": repo.name, "facility": repo.facility}
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
        info.context.audit(AuditTrailObjectType.Repo, therepo._id, "repoToggleGroupMembership", details=user.username)
        return info.context.db.find_access_group( grpfilter )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoComputeAllocationUpsert(self, repo: RepoInput, repocompute: RepoComputeAllocationInput, info: Info) -> Repo:
        repo = info.context.db.find_repo( repo )
        rc = {"repoid": repo._id}
        clustername = repocompute.clustername
        if not info.context.db.find_clusters({"name": clustername}):
            raise Exception("Cannot find cluster with name " + clustername)
        
        rc["clustername"] = clustername
        rc["start"] = repocompute.start.astimezone(pytz.utc)
        rc["end"] = repocompute.end.astimezone(pytz.utc)
        rc["percent_of_facility"] = repocompute.percent_of_facility
        rc["allocated"] = repocompute.allocated
        rc["burst_percent_of_facility"] = repocompute.burst_percent_of_facility
        rc["burst_allocated"] = repocompute.burst_allocated
        LOG.info(rc)
        if repocompute._id:
            rc["_id"] = repocompute._id
            info.context.db.collection("repo_compute_allocations").replace_one({"_id": rc["_id"]}, rc, upsert=False)
        else:
            info.context.db.collection("repo_compute_allocations").replace_one({"repoid": rc["repoid"], "clustername": rc["clustername"], "start": rc["start"]}, rc, upsert=True)
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "repoComputeAllocationUpsert", details=clustername+"="+json.dumps(rc["allocated"])+"("+json.dumps(rc["percent_of_facility"])+"%)")
        return info.context.db.find_repo( repo )
    
    @strawberry.field( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoChangeComputeRequirement(self, repo: RepoInput, computerequirement: ComputeRequirement, info: Info) -> Repo:
        repo = info.context.db.find_repo( repo )
        info.context.db.collection("repos").update_one({"_id": repo._id}, {"$set": {"computerequirement": computerequirement.name}})
        return info.context.db.find_repo( repo )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoStorageAllocationUpsert(self, repo: RepoInput, repostorage: RepoStorageAllocationInput, info: Info) -> Repo:
        repo = info.context.db.find_repo( repo )
        rs = {"repoid": repo._id}
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
        info.context.db.collection("repo_storage_allocations").replace_one({"repoid": rs["repoid"], "storagename": rs["storagename"], "purpose": rs["purpose"], "start": rs["start"]}, rs, upsert=True)
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "repoStorageAllocationUpsert", details=repostorage.purpose+"="+str(repostorage.gigabytes))
        return info.context.db.find_repo( repo )
    
    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsFacilityCzarOrAdmin ] )
    def repoRenameRepo(self, repo: RepoInput, newname: str, info: Info) -> Repo:
        repo = info.context.db.find_repo( repo )
        if not repo:
            raise Exception(f"Cannot find specified repo")
        facility = repo.facility
        reponame = repo.name
        existing_repos = info.context.db.find_repos( { "name": newname, "facility": facility } )
        if existing_repos:
            raise Exception(f"The facility {facility} already has another repo with the name {newname}")
        info.context.db.collection("repos").update_one({"_id": repo._id}, {"$set": { "name": newname }})
        info.context.db.collection("requests").update_many({ "reponame": reponame, "facilityname": facility }, {"$set": { "reponame": newname }})
        request: CoactRequestInput = CoactRequestInput()
        request.reqtype = CoactRequestType.RenameRepo
        request.reponame = newname
        request.facilityname = repo.facility
        request.previousName = repo.name
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = 1
        info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "repoRenameRepo", details=f"Name changed from {repo.name} to {newname}")
        repo = info.context.db.find_repo( {"_id": repo._id} )
        return repo

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoAddNewFeature(self, repo: RepoInput, feature: RepoFeatureInput, info: Info) -> Repo:
        repo = info.context.db.find_repo( repo )
        if not repo:
            raise Exception(f"Cannot find specified repo")
        if info.context.db.collection("repos").find_one({"_id": repo._id}).get("features", {}).get(feature.name, None):
            raise Exception(f"A feature with this name already exists")
        info.context.db.collection("repos").update_one({"_id": repo._id}, {"$set": { "features."+feature.name: {"state": feature.state, "options": feature.options} }})
        request: CoactRequestInput = CoactRequestInput()
        request.reqtype = CoactRequestType.RepoUpdateFeature
        request.reponame = repo.name
        request.facilityname = repo.facility
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = 1
        info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        repo = info.context.db.find_repo( {"_id": repo._id} )
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "repoNewFeature", details=info.context.dict_diffs({}, info.context.db.to_dict(feature)))
        return repo

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoDeleteFeature(self, repo: RepoInput, featurename: str, info: Info) -> Repo:
        repo = info.context.db.find_repo( repo )
        if not repo:
            raise Exception(f"Cannot find specified repo")
        if not info.context.db.collection("repos").find_one({"_id": repo._id}).get("features", {}).get(featurename, None):
            raise Exception(f"A feature with this name does not exist")
        previousfeature = info.context.db.collection("repos").find_one({"_id": repo._id}).get("features", {})[featurename]
        previousfeature["name"] = featurename
        info.context.db.collection("repos").update_one({"_id": repo._id}, {"$unset": { "features."+featurename: 1 }})
        request: CoactRequestInput = CoactRequestInput()
        request.reqtype = CoactRequestType.RepoUpdateFeature
        request.reponame = repo.name
        request.facilityname = repo.facility
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = 1
        info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        repo = info.context.db.find_repo( {"_id": repo._id} )
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "repoDeleteFeature", details=info.context.dict_diffs(previousfeature, {}))
        return repo

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoUpdateFeature(self, repo: RepoInput, feature: RepoFeatureInput, info: Info) -> Repo:
        repo = info.context.db.find_repo( repo )
        if not repo:
            raise Exception(f"Cannot find specified repo")
        featurename = feature.name
        if not info.context.db.collection("repos").find_one({"_id": repo._id}).get("features", {}).get(featurename, None):
            raise Exception(f"A feature with this name does not exist")
        previousfeature = info.context.db.collection("repos").find_one({"_id": repo._id}).get("features", {})[featurename]
        previousfeature["name"] = featurename
        info.context.db.collection("repos").update_one({"_id": repo._id}, {"$set": { "features."+featurename: {"state": feature.state, "options": feature.options} }})
        request: CoactRequestInput = CoactRequestInput()
        request.reqtype = CoactRequestType.RepoUpdateFeature
        request.reponame = repo.name
        request.facilityname = repo.facility
        request.requestedby = info.context.username
        request.timeofrequest = datetime.datetime.utcnow()
        request.approvalstatus = 1
        info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        repo = info.context.db.find_repo( {"_id": repo._id} )
        info.context.audit(AuditTrailObjectType.Repo, repo._id, "repoUpdateFeature", details=info.context.dict_diffs(previousfeature, info.context.db.to_dict(feature)))
        return repo


    @strawberry.field( permission_classes=[ IsFacilityCzarOrAdmin ] )
    def facilityAddCzar(self, facility: FacilityInput, user: UserInput, info: Info) -> Facility:
        filter = {"name": facility.name}
        userObj = info.context.db.find_user({"username": user.username})
        info.context.db.collection("facilities").update_one(filter, { "$addToSet": {"czars": user.username}})
        info.context.audit(AuditTrailObjectType.User, userObj._id, "+FacilityCzar", details=facility.name)
        return info.context.db.find_facility(filter)

    @strawberry.field( permission_classes=[ IsFacilityCzarOrAdmin ] )
    def facilityRemoveCzar(self, facility: FacilityInput, user: UserInput, info: Info) -> Facility:
        filter = {"name": facility.name}
        userObj = info.context.db.find_user({"username": user.username})
        info.context.db.collection("facilities").update_one(filter, { "$pull": {"czars": user.username}})
        info.context.audit(AuditTrailObjectType.User, userObj._id, "-FacilityCzar", details=facility.name)
        return info.context.db.find_facility(filter)

    @strawberry.field( permission_classes=[ IsAdmin ] )
    def facilityAddUpdateComputePurchase(self, facility: FacilityInput, cluster: ClusterInput, purchase: float, info: Info) -> Facility:
        facility = info.context.db.find_facility(filter=facility)
        if not facility:
            raise Exception("Cannot find requested facility " + str(facility))
        cluster = info.context.db.find_cluster(filter=cluster)
        if not cluster:
            raise Exception("Cannot find requested cluster " + str(cluster))
        if purchase and purchase < 0.0:
            raise Exception("Invalid purchase amount " + str(purchase))

        todaysdate = datetime.datetime.utcnow()
        cp = list(info.context.db.collection("facility_compute_purchases").find({"facility": facility.name, "clustername": cluster.name, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }).sort([("start", -1)]).limit(1))
        alloc_id = None
        if cp:
            alloc_id = cp[0]["_id"]
            info.context.db.collection("facility_compute_purchases").update_one({"_id": alloc_id}, {"$set": {"servers": purchase}}) 
        else:
            alloc_id = info.context.db.collection("facility_compute_purchases").insert_one({ "facility": facility.name, "clustername": cluster.name, "start": todaysdate, "end": datetime.datetime.fromisoformat("2100-01-01T00:00:00").replace(tzinfo=datetime.timezone.utc), "servers": purchase }).inserted_id

        request: CoactRequestInput = CoactRequestInput()
        request.reqtype = CoactRequestType.FacilityComputeAllocation
        request.facilityname = facility.name
        request.clustername = cluster.name
        request.allocated = purchase
        request.allocationid = alloc_id
        request.requestedby = info.context.username
        request.timeofrequest = todaysdate
        request.approvalstatus = 1
        info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing=None )
        
        return info.context.db.find_facility(facility)

    @strawberry.field( permission_classes=[ IsAdmin ] )
    def facilityAddUpdateStoragePurchase(self, facility: FacilityInput, purpose: str, storagename: Optional[str], purchase: float, info: Info) -> Facility:
        facility = info.context.db.find_facility(filter=facility)
        if not facility:
            raise Exception("Cannot find requested facility " + str(facility))
        if purchase < 0.0:
            raise Exception("Invalid purchase amount")
        if not purpose or len(purpose) < 2:
            raise Exception("For storage purposes, one needs to have a purpose")

        todaysdate = datetime.datetime.utcnow()
        cp = list(info.context.db.collection("facility_storage_purchases").find({"facility": facility.name, "purpose": purpose, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }).sort([("start", -1)]).limit(1))
        if cp:
            info.context.db.collection("facility_storage_purchases").update_one({"_id": cp[0]["_id"]}, {"$set": {"gigabytes": purchase}}) 
        else:
            if not storagename:
                raise Exception("When purchasing new storage, please specify a storage name")
            info.context.db.collection("facility_storage_purchases").insert_one({ "facility": facility.name, "purpose": purpose, "storagename": storagename, "start": todaysdate, "end": datetime.datetime.fromisoformat("2100-01-01T00:00:00").replace(tzinfo=datetime.timezone.utc), "gigabytes": purchase })

        return info.context.db.find_facility(facility)

    @strawberry.field( permission_classes=[ IsFacilityCzarOrAdmin ] )
    def facilityUpdateDescription(self, facility: FacilityInput, newdescription: str, info: Info) -> Facility:
        thefacility = info.context.db.find_facility(filter=facility)
        if not thefacility:
            raise Exception("Cannot find requested facility " + str(facility))
        thefacility.description = newdescription
        info.context.db.collection("facilities").update_one({"_id": thefacility._id}, {"$set": { "description": newdescription }})
        return info.context.db.find_facility(facility)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def jobsImport( self, jobs: List[Job], info: Info ) -> BulkOpsResult:
        jbs = [ ReplaceOne({"jobId": j.jobId, "startTs": j.startTs }, info.context.db.to_dict(j), upsert=True) for j in jobs ]
        bulkopsresult = info.context.db.collection("jobs").bulk_write(jbs)
        LOG.info("Imported jobs Inserted=%s, Upserted=%s, Modified=%s, Deleted=%s,", bulkopsresult.inserted_count, bulkopsresult.upserted_count, bulkopsresult.modified_count, bulkopsresult.deleted_count)
        return BulkOpsResult(insertedCount=bulkopsresult.inserted_count, upsertedCount=bulkopsresult.upserted_count, deletedCount=bulkopsresult.deleted_count, modifiedCount=bulkopsresult.modified_count)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def jobsAggregateForDate( self, thedate: CoactDatetime, info: Info ) -> StatusResult:
        pacificdaylight = pytz.timezone('America/Los_Angeles')
        starttime = thedate.astimezone(pacificdaylight).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
        endtime = starttime + datetime.timedelta(days=1)
        LOG.info("Aggregating jobs whose startTs is between %s and %s", starttime, endtime)
        datebucket = thedate.astimezone(pacificdaylight).replace(hour=0, minute=0, second=0, microsecond=0)
        info.context.db.collection("jobs").aggregate([
          { "$match": { "startTs": { "$gte": starttime,  "$lt": endtime }, "qos": { "$ne": "preemptable" }}},
          { "$project": { "allocationId": 1, "startTs": 1, "username": 1, "resourceHours": 1 }},
          { "$group": { "_id": {"allocationId": "$allocationId", "date" : datebucket, "username": "$username" }, "resourceHours": { "$sum": "$resourceHours" }}},
          { "$project": { "_id": 0, "allocationId": "$_id.allocationId", "date": "$_id.date", "username": "$_id.username", "resourceHours": 1 }},
          { "$merge": { "into": "repo_daily_peruser_compute_usage", "on": ["allocationId", "date", "username"],  "whenMatched": "replace" }}
        ])

        info.context.db.collection("repo_daily_peruser_compute_usage").aggregate([
          { "$project": { "allocationId": 1, "username": 1, "resourceHours": 1 }},
          { "$group": { "_id": {"allocationId": "$allocationId", "username": "$username" }, "resourceHours": { "$sum": "$resourceHours" }}},
          { "$project": { "_id": 0, "allocationId": "$_id.allocationId", "username": "$_id.username", "resourceHours": 1 }},
          { "$merge": { "into": "repo_peruser_compute_usage", "on": ["allocationId", "username"],  "whenMatched": "replace" }}
        ])

        info.context.db.collection("repo_daily_peruser_compute_usage").aggregate([
          { "$project": { "allocationId": 1, "date": 1, "resourceHours": 1 }},
          { "$group": { "_id": {"allocationId": "$allocationId", "date" : "$date" }, "resourceHours": { "$sum": "$resourceHours" }}},
          { "$project": { "_id": 0, "allocationId": "$_id.allocationId", "date": "$_id.date", "resourceHours": 1 }},
          { "$merge": { "into": "repo_daily_compute_usage", "on": ["allocationId", "date"], "whenMatched": "replace" }}
        ])
        info.context.db.collection("repo_daily_peruser_compute_usage").aggregate([
          { "$project": { "allocationId": 1, "resourceHours": 1 }},
          { "$group": { "_id": {"allocationId": "$allocationId" }, "resourceHours": { "$sum": "$resourceHours" }}},
          { "$project": { "_id": 0, "allocationId": "$_id.allocationId", "resourceHours": 1 }},
          { "$merge": { "into": "repo_overall_compute_usage", "on": ["allocationId"], "whenMatched": "replace" }}
        ])

        return StatusResult( status=True )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsAdmin ] )
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
        if not theaud.type or not theaud.actedon or not theaud.action:
            raise Exception("Audit trails need type, actedon and action information")
        if not theaud.actedby:
            theaud.actedby = info.context.username
        if not theaud.actedat:
            theaud.actedat = datetime.datetime.utcnow()
        return info.context.db.create("audit_trail", theaud)

    @strawberry.mutation(permission_classes=[ IsAuthenticated, IsAdmin ] )
    def notificationSend(self, msg: NotificationInput, info: Info) -> bool:
        return info.context.notify_raw(to=msg.to,subject=msg.subject,body=msg.body)


all_request_subscriptions = dict()

class RequestSubscription:
    def __init__(self, requestType):
        self.requestType = requestType
        self.requests_queue = asyncio.Queue()
    async def push_request(self, request: CoactRequest, change):
        if self.requestType:
            if self.requestType.value == request.reqtype:
                await self.requests_queue.put(CoactRequestEvent(operationType=change["operationType"], theRequest=request))
        else:
            await self.requests_queue.put(CoactRequestEvent(operationType=change["operationType"], theRequest=request))

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def requests(self, info: Info, requestType: Optional[CoactRequestType]=UNSET, clientName: Optional[str]=None) -> AsyncGenerator[CoactRequestEvent, None]:
        generatedClientName = False
        if not clientName:
            clientName = ''.join(random.choices(string.ascii_letters+string.digits, k=20))
            generatedClientName = True
        if clientName not in all_request_subscriptions:
            my_subscription = RequestSubscription(requestType)
            all_request_subscriptions[clientName] = my_subscription
        try:
            while True:
                req = await all_request_subscriptions[clientName].requests_queue.get()
                yield req
        except:
            pass
        if generatedClientName:
            LOG.warn("Removing anonymous subsctiption %s", clientName)
            del all_request_subscriptions[clientName]
        else:
            LOG.warn("Keeping long lived subsctiption for client with name %s around", clientName)

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
                        LOG.info("Publishing a request to %s queues", len(all_request_subscriptions))
                        LOG.info(dumps(change))
                        theId = change["documentKey"]["_id"]
                        theRq = db["requests"].find_one({"_id": theId})
                        if theRq:
                            req = CoactRequest(**theRq)
                            await asyncio.gather(*[subscription.push_request(req, change) for subscription in all_request_subscriptions.values() ])
                        change = change_stream.try_next()
                    except Exception as e:
                        LOG.exception("Exception processing change")
                await asyncio.sleep(1)
    asyncio.create_task(__watch_requests__())
