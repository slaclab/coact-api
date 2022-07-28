from auth import IsAuthenticated, \
        IsRepoPrincipal, \
        IsRepoLeader, \
        IsRepoPrincipalOrLeader, \
        IsAdmin, \
        IsValidEPPN

import asyncio
from threading import Thread
from typing import List, Optional, AsyncGenerator
import copy

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
        Facility, FacilityInput, \
        Resource, Qos, Job, \
        UserAllocationInput, UserAllocation, \
        ClusterInput, Cluster, \
        SDFRequestInput, SDFRequest, SDFRequestType, SDFRequestEvent, \
        RepoFacilityName

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
        return UserRegistration(**{ "isRegistered": isRegis, "eppn": eppn, "isRegistrationPending": regis_pending })

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def whoami(self, info: Info) -> User:
        return info.context.db.find_user( { "username": info.context.username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def users(self, info: Info, filter: Optional[UserInput]={} ) -> List[User]:
        return info.context.db.find_users( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def user(self, info: Info, user: UserInput ) -> User:
        return info.context.db.find_user( user )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def clusters(self, info: Info, filter: Optional[ClusterInput]={} ) -> List[Cluster]:
        return info.context.db.find_clusters( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilities(self, info: Info, filter: Optional[FacilityInput]={} ) -> List[Facility]:
        return info.context.db.find_facilities( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def requests(self, info: Info) -> List[SDFRequest]:
        if info.context.is_admin:
            return info.context.db.find_requests( {} )
        else:
            username = info.context.username
            assert username != None
            myrepos = info.context.db.find_repos( { '$or': [
                { "leaders": username },
                { "principal": username }
                ] } )
            reponames = [ x.name for x in myrepos ]
            return info.context.db.find_requests( { "reponame": {"$in": reponames } } )

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
    def allreposandfacility(self, info: Info) -> List[RepoFacilityName]:
        """
        All the repo names and their facility. No authentication needed. Just the names
        """
        return [ RepoFacilityName(**x) for x in info.context.db.collection("repos").find({}, {"_id": 0, "name": 1, "facility": 1}) ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repo(self, filter: Optional[RepoInput], info: Info) -> Repo:
        return info.context.db.find_repo( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def myRepos(self, info: Info, impersonate: Optional[str]=None) -> List[Repo]:
        username = info.context.username
        assert username != None
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

    @strawberry.field
    def qos(self, info: Info) -> List[Qos]:
        return info.context.db.find_qoses()



@strawberry.type
class Mutation:

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def userCreate(self, user: UserInput, info: Info, admin_override: bool=False) -> User:
        return info.context.db.create( 'users', user, required_fields=[ 'username', 'uidnumber', 'eppns' ], find_existing={ 'username': user.username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdate(self, user: UserInput, info: Info, admin_override: bool=False) -> User:
        return info.context.db.update( 'users', user, required_fields=[ '_id' ], find_existing={ '_id': user._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdateEppn(self, eppns: List[str], info: Info, admin_override: bool=False) -> User:
        pass

    @strawberry.field( permission_classes=[ IsValidEPPN ] )
    def newSDFAccountRequest(self, request: SDFRequestInput, info: Info) -> SDFRequest:
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing={ 'reqtype': request.reqtype.name, "eppn": request.eppn } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repoMembershipRequest(self, request: SDFRequestInput, info: Info) -> SDFRequest:
        if request.reqtype != SDFRequestType.RepoMembership or not request.reponame:
            raise Exception()
        request.username = info.context.username
        return info.context.db.create( 'requests', request, required_fields=[ 'reqtype' ], find_existing={ 'reqtype': request.reqtype.name, "username": request.username, "reponame": request.reponame } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def approveRequest(id: str, info: Info) -> bool:
        LOG.debug(id)
        thereq = info.context.db.find_request({ "_id": ObjectId(id) })
        user = info.context.authn()
        if thereq.reqtype == "RepoMembership":
            therepo = info.context.db.find_repo({"name": thereq.reponame})
            isleader = False
            if user in therepo.leaders or therepo.principal == user:
                isleader = True
            if not info.context.is_admin and not isleader:
                raise Exception("User is not an admin or a leader in the repo.")
            # These two should be in a transaction.
            info.context.db.collection("repos").update_one({"_id": therepo._id}, {"$addToSet": {"users": thereq.username}})
            info.context.db.remove( 'requests', { "_id": id } )
            return True
        elif thereq.reqtype == "UserAccount":
            if not info.context.is_admin:
                raise Exception("User is not an admin - cannot approve.")
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
            maxuidusr, maxuidnum = info.context.db.collection("users").find({}).sort([("uidnumber", -1)]).limit(1), 0
            if maxuidusr:
                maxuidnum = list(maxuidusr)[0].get("uidnumber", 0)
            info.context.db.collection("users").insert_one({ "username": preferredUserName, "uidnumber": maxuidnum+1, "eppns": [ theeppn ] })
            info.context.db.remove( 'requests', { "_id": id } )
            return True
        else:
            if not info.context.is_admin:
                raise Exception("User is not an admin")
            info.context.db.remove( 'requests', { "_id": id } )
            return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def rejectRequest(id: str, info: Info) -> bool:
        info.context.db.remove( 'requests', { "_id": id } )
        return True

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def facilityCreate(self, facility: FacilityInput, info: Info, admin_override: bool=False) -> Facility:
        return info.context.db.create( 'facilities', facility, required_fields=[ 'name' ], find_existing={ 'name': facility.name } )


    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def accessGroupCreate(self, access_group: AccessGroupInput, info: Info, admin_override: bool=False) -> AccessGroup:
        return info.context.db.create( 'access_groups', access_group, required_fields=[ 'gid_number', 'name' ], find_existing={ 'gid_number': access_group.gid_number } )


    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def accessGroupUpdate(self, access_group: AccessGroupInput, info: Info, admin_override: bool=False) -> AccessGroup:
        return info.context.db.update( 'access_groups', info, access_group, required_fields=[ 'Id', ], find_existing={ '_id': accesss_group._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoCreate(self, repo: RepoInput, info: Info, admin_override: bool=False) -> Repo:
        return info.context.db.create( 'repos', repo, required_fields=[ 'name', 'facility' ], find_existing={ 'name': repo.name, 'facility': repo.facility } )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoUpdate(self, repo: RepoInput, info: Info, admin_override: bool=False) -> Repo:
        return info.context.db.update( 'repos', info, repo, required_fields=[ 'Id' ], find_existing={ '_id': repo._id } )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def updateUserAllocation(self, repo: RepoInput, data: List[UserAllocationInput], info: Info, admin_override: bool=False, impersonate: str=None) -> Repo:
        filter = {"name": repo.name}
        therepos =  info.context.db.find_repo( filter )
        uas = [dict(j.__dict__.items()) for j in data]
        keys = ["facility", "repo", "resource", "year", "username"]
        for ua in uas:
            nua = {k: v for k,v in ua.items() if not v is UNSET}
            info.context.db.collection("user_allocations").replace_one({k: v for k,v in nua.items() if k in keys}, nua, upsert=True)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def addUserToRepo(self, repo: RepoInput, user: UserInput, info: Info, admin_override: bool=False, impersonate: str=None ) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"users": user.username}})
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def addLeaderToRepo(self, repo: RepoInput, user: UserInput, info: Info, admin_override: Optional[bool]=False, impersonate: str=None ) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"leaders": user.username}})
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipal ] )
    def changePrincipalForRepo(self, repo: RepoInput, user: UserInput, info: Info, admin_override: bool=False, impersonate: str=None ) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$set": {"principal": user.username}})
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def removeUserFromRepo(self, repo: RepoInput, user: UserInput, info: Info, admin_override: bool=False, impersonate: str=None ) -> Repo:
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
    def toggleUserRole(self, repo: RepoInput, user: UserInput, info: Info, admin_override: bool=False, impersonate: str=None ) -> Repo:
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
    def toggleGroupMembership(self, repo: RepoInput, user: UserInput, group: AccessGroupInput, info: Info, admin_override: bool=False, impersonate: str=None ) -> AccessGroup:
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

    @strawberry.mutation
    def importJobs(self, jobs: List[Job], info: Info, admin_override: bool=False) -> str:
        jbs = [dict(j.__dict__.items()) for j in jobs]
        info.context.db.collection("jobs").insert_many(jbs)
        allocation_ids = list(map(lambda x: x["allocationId"], jbs))
        usage = info.context.db.collection("jobs").aggregate([
          { "$match": { "allocationId": {"$in":  allocation_ids } }},
          { "$group": { "_id": {"allocationId": "$allocationId", "qos": "$qos", "repo": "$repo" },
              "slacsecs": { "$sum": "$slacsecs" },
              "rawsecs": { "$sum": "$rawsecs" },
              "machinesecs": { "$sum": "$machinesecs" },
              "avgcf": { "$avg": "$finalcf" }
          }},
          { "$project": {
              "_id": 0,
              "allocationId": "$_id.allocationId",
              "qos": "$_id.qos",
              "repo": "$_id.repo",
              "slacsecs": 1,
              "rawsecs": 1,
              "machinesecs": 1,
              "avgcf": 1,
          }}
        ])
        for usg in usage:
            info.context.db.collection("computeusagecache").replace_one({"allocationId": usg["allocationId"], "qos": usg["qos"]}, usg, upsert=True)
        return "Done"


requests_queue = asyncio.Queue()

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def requests(self, info: Info) -> AsyncGenerator[SDFRequestEvent, None]:
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
                        LOG.info(dumps(change))
                        theId = change["documentKey"]["_id"]
                        theRq = db["requests"].find_one({"_id": theId})
                        req = SDFRequest(**theRq) if theRq else None
                        await requests_queue.put(SDFRequestEvent(operationType=change["operationType"], theRequest=req))
                        change = change_stream.try_next()
                    except Exception as e:
                        LOG.exception("Exception processing change")
                await asyncio.sleep(1)
    asyncio.create_task(__watch_requests__())
