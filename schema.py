from auth import Authnz, IsAuthenticated, IsRepoPrincipal, IsRepoLeader, IsRepoPrincipalOrLeader, IsAdmin

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


def assert_one( items, thing, filter ):
    if len(items) == 0:
        raise AssertionError( f"did not find {thing} matching {to_dict(filter)}")
    if len(items) > 1:
        raise AssertionError( f"found too many {thing} matching {to_dict(filter)}")
    return items[0]

@strawberry.type
class Query:

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def users(self, info: Info, filter: Optional[UserInput] ) -> List[User]:
        return info.context.db.find_users( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def user(self, info: Info, filter: Optional[UserInput] ) -> User:
        return info.context.db.find_user( filter )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilities(self, info: Info, filter: Optional[FacilityInput]) -> List[Facility]:
        return info.context.db.find_facilities( filter, exclude_fields=['resources',] )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facility(self, name: str, info: Info, filter: Optional[FacilityInput]) -> Facility:
        return info.context.db.find_facilities( filter )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_groups(self, info: Info, filter: Optional[AccessGroupInput]) -> List[AccessGroup]:
        return info.context.db.find_access_groups( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_group(self, info: Info, filter: Optional[AccessGroupInput]) -> AccessGroup:
        return info.context.db.find_access_group( filter )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repos(self, info: Info, filter: Optional[RepoInput]) -> List[Repo]:
        return info.context.db.find_repos( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repo(self, filter: Optional[RepoInput], info: Info) -> Repo:
        return info.context.db.find_repo( filter )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def myRepos(self, info: Info) -> List[Repo]:
        username = info.context.username
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
        return info.context.db.find_qoses( filter)



@strawberry.type
class Mutation:

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def userCreate(self, data: UserInput, info: Info) -> User:
        return info.context.db.create( 'users', data, required_fields=[ 'username', 'uidnumber', 'eppns' ], find_existing={ 'username': data.username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdate(self, data: UserInput, info: Info) -> User:
        return info.context.db.update( 'users', data, required_fields=[ '_id' ], find_existing={ '_id': data._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdateEppn(self, eppns: List[str], info: Info) -> User:
        pass


    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def facilityCreate(self, data: FacilityInput, info: Info) -> Facility:
        return info.context.db.create( 'facilities', data, required_fields=[ 'name' ], find_existing={ 'name': data.name } )


    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def accessGroupCreate(self, data: AccessGroupInput, info: Info) -> AccessGroup:
        return info.context.db.create( 'access_groups', data, required_fields=[ 'gid_number', 'name' ], find_existing={ 'gid_number': data.gid_number } )


    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def accessGroupUpdate(self, data: AccessGroupInput, info: Info) -> AccessGroup:
        return info.context.db.update( 'access_groups', info, data, required_fields=[ 'Id', ], find_existing={ '_id': data._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoCreate(self, data: RepoInput, info: Info) -> Repo:
        return info.context.db.create( 'repos', data, required_fields=[ 'name', 'facility' ], find_existing={ 'name': data.name, 'facility': data.facility } )

    @strawberry.field( permission_classes=[ IsAuthenticated, IsAdmin ] )
    def repoUpdate(self, data: RepoInput, info: Info) -> Repo:
        return info.context.db.update( 'repos', info, data, required_fields=[ 'Id' ], find_existing={ '_id': data._id } )

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def updateUserAllocation(self, repo: RepoInput, data: List[UserAllocationInput], info: Info) -> Repo:
        filter = {"name": repo.name}
        repos =  info.context.db.find_repos( filter )
        therepo = assert_one( repos, 'repo', filter)
        uas = [dict(j.__dict__.items()) for j in data]
        keys = ["facility", "repo", "resource", "year", "username"]
        for ua in uas:
            nua = {k: v for k,v in ua.items() if not v is UNSET}
            info.context.db.collection("user_allocations").replace_one({k: v for k,v in nua.items() if k in keys}, nua, upsert=True)
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def addUserToRepo(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        info.context.db.collection("repos").update_one(filter, { "$addToSet": {"users": user.username}})
        return info.context.db.find_repo(filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def removeUserFromRepo(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        repos =  info.context.db.find_repos( filter )
        therepo = assert_one( repos, 'repo', filter)
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
        if theuser == therepo.principal:
            raise Exception(theuser + " is a PI in repo " + repo.name + ". Cannot be removed from the repo")
        info.context.db.collection("repos").update_one(filter, { "$pull": {"leaders": theuser, "users": theuser}})
        return assert_one( info.context.db.find("repos", filter ), 'repos', filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def toggleUserRole(self, repo: RepoInput, user: UserInput, info: Info) -> Repo:
        filter = {"name": repo.name}
        repos = info.context.db.find_repos( filter )
        therepo = assert_one( repos, 'repo', filter)
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
        info.context.db.collection("repos").update_one({"name": repo.name}, [{ "$set":
            { "leaders": { "$cond": [
                { "$in": [ user.username, "$leaders" ] },
                { "$setDifference": [ "$leaders", [ user.username ] ] },
                { "$concatArrays": [ "$leaders", [ user.username ] ] }
                ]}}}])
        return assert_one( info.context.db.find_repos(filter), 'repos', filter)

    @strawberry.mutation( permission_classes=[ IsAuthenticated, IsRepoPrincipalOrLeader ] )
    def toggleGroupMembership(self, repo: RepoInput, user: UserInput, group: AccessGroupInput, info: Info) -> AccessGroup:
        filter = {"name": repo.name}
        repos = info.context.db.find_repos( filter )
        therepo = assert_one( repos, 'repo', filter)
        theuser = user.username
        if theuser not in therepo.users:
            raise Exception(theuser + " is not a user in repo " + repo.name)
        grpfilter = { "name": group.name }
        thegroup = assert_one( info.context.db.find_access_groups( grpfilter ), 'access_group', grpfilter)
        info.context.db.collection("access_groups").update_one({"name": group.name}, [{ "$set":
            { "members": { "$cond": [
                { "$in": [ user.username, "$members" ] },
                { "$setDifference": [ "$members", [ user.username ] ] },
                { "$concatArrays": [ "$members", [ user.username ] ] }
                ]}}}])
        return assert_one( info.context.db.find_access_groups( grpfilter ), 'access_group', grpfilter )

    @strawberry.mutation
    def importJobs(self, jobs: List[Job], info: Info) -> str:
        jbs = [dict(j.__dict__.items()) for j in jobs]
        get_db(info,"jobs").insert_many(jbs)
        return "Done"
