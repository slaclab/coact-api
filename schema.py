from auth import Authnz, IsAuthenticated

from typing import List, Optional
import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET

from models import get_db, to_dict, create_thing, update_thing, find_thing, \
        User, UserInput, find_users, \
        AccessGroup, AccessGroupInput, find_access_groups, \
        Repo, RepoInput, find_repos, \
        Facility, FacilityInput, find_facilities, \
        Resource, Role, Qos, Job, \
        UserAllocationInput, UserAllocation

import logging

LOG = logging.getLogger(__name__)


def assert_one( items, thing, filter ):
    if len(items) == 0:
        raise AssertionError( f"did not find {thing} matching {to_dict(filter)}")
    if len(items) > 1:
        raise AssertionError( f"found too many {thing} matching {to_dict(filter)}")

@strawberry.type
class Query:

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def users(self, info: Info, filter: Optional[UserInput] ) -> List[User]:
        users = find_users( info, filter )
        return users

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def user(self, info: Info, filter: Optional[UserInput] ) -> User:
        users = find_users( info, filter )
        assert_one( users, 'user', filter)
        return users[0]


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def roles(self, info: Info) -> List[Role]:
        roles = get_db(info, "roles").find()
        return [ Role(**x) for x in roles ]

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def role(self, name: str, info: Info) -> Role:
        therole = get_db(info, "roles").find_one({"name": name})
        if therole:
            return Role(**therole)
        return None


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilities(self, info: Info, filter: Optional[FacilityInput]) -> List[Facility]:
        return find_facilities( info, filter, exclude_fields=['resources',] )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facility(self, name: str, info: Info, filter: Optional[FacilityInput]) -> Facility:
        facilities = find_facilities( info, filter )
        assert_one( facilities, 'facility', filter)
        return facilities[0]


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_groups(self, info: Info, filter: Optional[AccessGroupInput]) -> List[AccessGroup]:
        return find_access_groups( info, filter, exclude_fields=[] )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def access_group(self, info: Info, filter: Optional[AccessGroupInput]) -> AccessGroup:
        access_groups = find_access_groups( info, filter )
        assert_one( access_groups, 'access_group', filter)
        return access_groups[0]


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repos(self, info: Info, filter: Optional[RepoInput]) -> List[Repo]:
        return find_repos( info, filter, exclude_fields=['roles'] )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repo(self, filter: Optional[RepoInput], info: Info) -> Repo:
        repos = find_repos( info, filter, exclude_fields=['roles',])
        assert_one( repos, 'repo', filter)
        return repos[0]
        
    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reposWithUser( self, info: Info, username: str ) -> List[Repo]:
        repos = find_thing( 'repos', info, { "users": username } )
        return repos

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reposWithLeader( self, info: Info, username: str ) -> List[Repo]:
        repos = find_thing( 'repos', info, { "leaders": username } )
        return repos

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def reposWithPrincipal( self, info: Info, username: str ) -> List[Repo]:
        repos = find_thing( 'repos', info, { "principal": username } )
        return repos
        
    @strawberry.field
    def qos(self, info: Info) -> List[Qos]:
        qoses = list(get_db(info,"qos").find({}))
        return [Qos(**x) for x in qoses]




@strawberry.type
class Mutation:

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userCreate(self, data: UserInput, info: Info) -> User:
        return create_thing( 'users', info, data, required_fields=[ 'username', 'uidnumber', 'eppns' ], find_existing={ 'name': data.username } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdate(self, data: UserInput, info: Info) -> User:
        return update_thing( 'users', info, data, required_fields=[ 'Id' ], find_existing={ '_id': data._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def userUpdateEppn(self, eppns: List[str], info: Info) -> User:
        pass


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def facilityCreate(self, data: FacilityInput, info: Info) -> Facility:
        return create_thing( 'facilities', info, data, required_fields=[ 'name' ], find_existing={ 'name': data.name } )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def accessGroupCreate(self, data: AccessGroupInput, info: Info) -> AccessGroup:
        return create_thing( 'access_groups', info, data, required_fields=[ 'gid_number', 'name' ], find_existing={ 'gid_number': data.gid_number } )


    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def accessGroupUpdate(self, data: AccessGroupInput, info: Info) -> AccessGroup:
        return update_thing( 'access_groups', info, data, required_fields=[ 'Id', ], find_existing={ '_id': data._id } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repoCreate(self, data: RepoInput, info: Info) -> Repo:
        return create_thing( 'repos', info, data, required_fields=[ 'name', 'facility' ], find_existing={ 'name': data.name, 'facility': data.facility } )

    @strawberry.field( permission_classes=[ IsAuthenticated ] )
    def repoUpdate(self, data: RepoInput, info: Info) -> Repo:
        return update_thing( 'repos', info, data, required_fields=[ 'Id' ], find_existing={ '_id': data._id } )

    @strawberry.mutation( permission_classes=[ IsAuthenticated ] )
    def updateUserAllocation(self, data: List[UserAllocationInput], info: Info) -> str:
        uas = [dict(j.__dict__.items()) for j in data]
        keys = ["facility", "repo", "resource", "year", "username"]
        for ua in uas:
            nua = {k: v for k,v in ua.items() if not isinstance(v, type(UNSET))}
            get_db(info,"user_allocations").replace_one({k: v for k,v in nua.items() if k in keys}, nua, upsert=True)
        return "Done"

    @strawberry.mutation
    def importJobs(self, jobs: List[Job], info: Info) -> str:
        jbs = [dict(j.__dict__.items()) for j in jobs]
        get_db(info,"jobs").insert_many(jbs)
        return "Done"
