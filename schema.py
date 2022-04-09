from auth import Authnz

from typing import List, Optional
import strawberry
from strawberry.types import Info

from models import get_db, to_dict, create_thing, \
        User, UserInput, find_users, \
        Repo, RepoInput, find_repos, \
        Facility, FacilityInput, find_facilities, \
        Resource, Role, Qos, Job 

import logging
from pprint import pprint

LOG = logging.getLogger(__name__)

authn = Authnz()


def assert_one( items, thing, filter ):
    if len(items) == 0:
        raise AssertionError( f"did not find {thing} matching {to_dict(filter)}")
    if len(items) > 1:
        raise AssertionError( f"found too many {thing} matching {to_dict(filter)}")

@strawberry.type
class Query:
    
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def users(self, info: Info, filter: Optional[UserInput] ) -> List[User]:
        users = find_users( info, filter )
        return users
        
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def user(self, info: Info, filter: Optional[UserInput] ) -> User:
        users = find_users( info, filter )
        assert_one( users, 'user', filter)
        return users[0]

    
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def roles(self, info: Info) -> List[Role]:
        roles = get_db(info, "roles").find()
        return [ Role(**x) for x in roles ]
    
    def role(self, name: str, info: Info) -> Role:
        therole = get_db(info, "roles").find_one({"name": name})
        if therole:
            return Role(**therole)
        return None

    
    @strawberry.field
    @authn.authentication_required
    def facilities(self, info: Info, filter: Optional[FacilityInput]) -> List[Facility]:
        return find_facilities( info, filter, exclude_fields=['resources',] )
        
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def facility(self, name: str, info: Info, filter: Optional[FacilityInput]) -> Facility:
        facilities = find_facilities( info, filter )
        assert_one( facilities, 'facility', filter)
        return facilities[0]

        
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def repos(self, info: Info, filter: Optional[RepoInput]) -> List[Repo]:
        return find_repos( info, filter, exclude_fields=['roles'] )
    
    @strawberry.field
    @authn.authentication_required
    @authn.check_repo
    @authn.authorization_required("read")
    def repo(self, name: str, info: Info) -> Repo:
        repos = find_repos( info, filter, exclude_fields=['roles',])
        assert_one( repos, 'repo', filter)
        return repo[0]
        
        
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def qos(self, info: Info) -> List[Qos]:
        qoses = list(get_db(info,"qos").find({}))
        return [Qos(**x) for x in qoses]




@strawberry.type
class Mutation:

    @strawberry.mutation
    @authn.authentication_required
    @authn.authorization_required("write")
    def userCreate(self, data: UserInput, info: Info) -> User:
        return create_thing( 'users', info, data, required_fields=[ 'username', 'uid_number', 'eppns' ], find_existing={ 'name': data.username } )

    @strawberry.mutation
    @authn.authentication_required
    @authn.authorization_required("write")
    def userUpdate(self, data: UserInput, info: Info) -> User:
        pass
        
    @strawberry.mutation
    @authn.authentication_required
    @authn.authorization_required("write")
    def userUpdateEppn(self, eppns: List[str], info: Info) -> User:
        pass

    @strawberry.mutation
    @authn.authentication_required
    @authn.authorization_required("write")
    def facilityCreate(self, data: FacilityInput, info: Info) -> Facility:
        return create_thing( 'facilities', info, data, required_fields=[ 'name' ], find_existing={ 'name': data.name } )
        
    @strawberry.mutation
    @authn.authentication_required
    @authn.authorization_required("write")
    def repoCreate(self, data: RepoInput, info: Info) -> Repo:
        return create_thing( 'repos', info, data, required_fields=[ 'name' ], find_existing={ 'name': data.name } )


    @strawberry.mutation
    def importJobs(self, jobs: List[Job], info: Info) -> str:
        jbs = [dict(j.__dict__.items()) for j in jobs]
        get_db(info,"jobs").insert_many(jbs)
        return "Done"