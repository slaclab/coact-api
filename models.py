from typing import List, Optional
import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET
from typing import NewType

from datetime import datetime
from bson import ObjectId

# from db import get_db

import logging

LOG = logging.getLogger(__name__)


# the database name for all data
DB_NAME = "iris"



MongoId = strawberry.scalar(
    NewType("MongoId", object),
    serialize = lambda v: str(v),
    parse_value = lambda v: ObjectId(v),
)


# used to map into pymongo as it doesn't like strawberry UNSET objects
def to_dict( obj ):
    d = {}
    for k,v in obj.__dict__.items():
        # LOG.warn(f"type {k} is {v}")
        if v:
            d[k] = v
    return d

def get_db( info: Info, collection: str ):
    return info.context.db[DB_NAME][collection]


# would this be useful? https://github.com/strawberry-graphql/strawberry/discussions/444

# we generally just set everything to be option so that we can create a form like experience with graphql. we impose some of the required fields in some utility functions like create_thing(). not a great use of the graphql spec, but allows to to limit the amount of code we have to write

@strawberry.input
class UserInput:
    _id: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    uid_number: Optional[int] = UNSET
    eppns: Optional[List[str]] = UNSET
    
@strawberry.type
class User(UserInput):
    pass



@strawberry.type
class Role:
    
    _id: MongoId
    name: str
    privileges: List[str]
    players: List[str]
    playerObjs: List[User]
    
    @strawberry.field
    def playerObjs(self, info) -> List[User]:
        return [ User(**x) for x in list( get_db(info,"users").find({"uid": {"$in": self.players}})) ]

@strawberry.type
class Resource:
    
    name: str
    type: str
    partitions: List[str]
    root: str


@strawberry.input
class FacilityInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    description: Optional[str] = UNSET


@strawberry.type
class Facility( FacilityInput ):
    
    @strawberry.field
    def resources(self, info) -> List[Resource]:
        fac = get_db(info,"facilities").find_one({"_id": self._id })
        return [ Resource(**{"name": k, "type": v["type"], "partitions": v.get("partitions", []), "root": v.get("root", None)}) for k,v in fac.get("resources", {}).items() ]



@strawberry.input
class RepoInput:

    _id: Optional[MongoId] = UNSET    
    name: Optional[str] = UNSET
    facility: Optional[str] = UNSET
    gid: Optional[int] = UNSET
    
    principal: Optional[str] = UNSET
    leaders: Optional[List[str]] = UNSET
    users: Optional[List[str]] = UNSET

    group: Optional[str] = UNSET
    description: Optional[str] = UNSET


@strawberry.type
class Repo( RepoInput ):
    
    @strawberry.field
    def facilityObjs(self, info) -> List[Facility]:
        facilities = list(get_db(info,"facilities").find({"name": {"$in": self.facilities}}))
        LOG.debug(facilities)
        for facility in facilities:
            del facility["resources"]
        return [ Facility(**x) for x in facilities ]
    
    @strawberry.field
    def roleObjs(self, info) -> List[Role]:
        repo = get_db(info,"repos").find_one({"_id": self._id })
        LOG.debug("Roles: " + str(repo.get("roles", {})))
        return [ Role(**{ "_id": None, "name": k, "privileges": [], "players": v }) for k,v in repo.get("roles", {}).items() ]



@strawberry.type
class Qos:
    
    _id: MongoId
    name: str
    repo: str
    qos: str
    partition: str

@strawberry.input
class Job:
    
    job_id: str
    user_name: str
    uid: int
    account_name: str
    partition_name: str
    qos: str
    start_ts: datetime
    end_ts: datetime
    ncpus: int
    alloc_nodes: int
    alloc_tres: str
    nodelist: str
    reservation: str
    reservation_id: str
    submitter: str
    submit_ts: datetime
    host_name: str
    official_import: bool
    compute_id: str
    elapsed_secs: float
    wait_time: float
    charge_factor: float
    raw_secs: float
    nersc_secs: float
    machine_secs: float
    repo: str
    year: int
    facility: str
    resource: str
    



# class mapping of the 'thing' to the class
KLASSES = {
    'users': User, 
    'repos': Repo, 
    'facilities': Facility,
}

# helper functions to prevent DRY for common queries
def find_thing( thing, info, filter, exclude_fields=[] ):
    search = to_dict(filter)
    LOG.debug(f"searching for {thing} {filter} -> {search} (excluding fields {exclude_fields})")
    cursor = get_db(info, thing).find(search)
    items = []
    klass = KLASSES[thing]
    for item in cursor:
        LOG.debug(f" found {item}")
        for x in exclude_fields:
            if x in item:
                del item[x]
        items.append( klass(**item) )
    return items

def find_users( info: Info, filter: Optional[UserInput], exclude_fields: Optional[List[str]] = [] ) -> List[User]:
    return find_thing( 'users', info, filter, exclude_fields=exclude_fields )

def find_facilities( info: Info, filter: Optional[FacilityInput], exclude_fields: Optional[List[str]] = ['resources',] ) -> List[Facility]:
    return find_thing( 'facilities', info, filter, exclude_fields=exclude_fields )

def find_repos( info: Info, filter: Optional[RepoInput], exclude_fields: Optional[List[str]] = ['roles',] ) -> List[Repo]:
    return find_thing( 'repos', info, filter, exclude_fields=exclude_fields )


# helper class to create a thing and ensure that it doesn't already exist
def create_thing( thing, info, data, required_fields=[], find_existing={ 'key': 'some_value' } ):
    klass = KLASSES[thing]
    input_data_okay = {}
    for f in required_fields:
        if getattr(data,f):
            input_data_okay[f] = True
        else:
            input_data_okay[f] = False
    if False in input_data_okay.values():
        failed = []
        for k,v in input_data_okay.items():
            if v == False:
                failed.append(k)
        raise Exception( f"input did not contain required fields {failed}")
    the_thing = klass( **vars(data) )
    LOG.info(f"adding {thing} with {data} -> {the_thing}")
    db = get_db(info,thing)
    if db.find_one( find_existing ):
        raise Exception(f"{thing} already exists with {find_existing}!")
    x = db.insert_one( to_dict(the_thing) )
    v = vars(data)
    v['_id'] = x.inserted_id
    inserted = klass( **v )
    return inserted
