from auth import IsAuthenticated, \
        IsRepoPrincipal, \
        IsRepoLeader, \
        IsRepoPrincipalOrLeader, \
        IsAdmin

from typing import List, Optional
import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET

from models import \
        User, UserInput, \
        AccessGroup, AccessGroupInput, \
        Repo, RepoInput, \
        Facility, FacilityInput, \
        Resource, Qos, Job, \
        UserAllocationInput, UserAllocation

import logging
LOG = logging.getLogger(__name__)


@strawberry.type
class Query:
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
    def facilities(self, info: Info, filter: Optional[FacilityInput]={} ) -> List[Facility]:
        return info.context.db.find_facilities( filter, exclude_fields=['resources',] )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facility(self, name: str, info: Info, filter: Optional[FacilityInput]) -> Facility:
        return info.context.db.find_facilities( filter )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_groups(self, info: Info, filter: Optional[AccessGroupInput]={} ) -> List[AccessGroup]:
        return info.context.db.find_access_groups( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_group(self, info: Info, filter: Optional[AccessGroupInput]) -> AccessGroup:
        return info.context.db.find_access_group( filter )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repos(self, info: Info, filter: Optional[RepoInput]={} ) -> List[Repo]:
        return info.context.db.find_repos( filter )

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
        therepos = info.context.db.find_repo( filter )
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
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
        return "Done"
