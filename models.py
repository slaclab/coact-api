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
    if isinstance(obj,dict):
        return obj

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
class PartitionInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    charge_factor: Optional[float] = UNSET

@strawberry.type
class Partition(PartitionInput):
    pass

@strawberry.type
class ResourceCapacityInput:
    _id: Optional[MongoId] = UNSET
    year: Optional[int] = UNSET
    compute: Optional[float] = UNSET
    storage: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class ResourceCapacity(ResourceCapacityInput):
    pass

@strawberry.type
class Resource:
    name: str
    type: str
    facility_name: str
    partitions: List[str]
    root: str
    @strawberry.field
    def partitionObjs(self, info) -> List[Partition]:
        return [ Partition(**x) for x in  get_db(info,"partitions").find({"name": {"$in": self.partitions } } ) ]
    @strawberry.field
    def capacities(self, info, year: int = 0) ->List[ResourceCapacity]:
        rc_filter = { "facility": self.facility_name,  "resource": self.name }
        if year:
            rc_filter["year"] = year
        return [ ResourceCapacity(**{k:x.get(k, 0) for k in ["year", "compute", "storage", "inodes"] }) for x in  get_db(info,"resource_capacity").find(rc_filter) ]

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
        return [ Resource(**{"name": k, "facility_name": self.name, "type": v["type"], "partitions": v.get("partitions", []), "root": v.get("root", None)}) for k,v in fac.get("resources", {}).items() ]

@strawberry.type
class AllocationInput:
    _id: Optional[MongoId] = UNSET
    facility: Optional[str] = UNSET
    resource: Optional[str] = UNSET
    repo: Optional[str] = UNSET
    year: Optional[int] = UNSET
    compute: Optional[float] = UNSET
    storage: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class Allocation(AllocationInput):
    pass

@strawberry.type
class UserAllocation(Allocation):
    userName: Optional[str] = UNSET

@strawberry.type
class UsageInput:
    facility: Optional[str] = UNSET
    resource: Optional[str] = UNSET
    repo: Optional[str] = UNSET
    year: Optional[int] = UNSET
    totalNerscSecs: Optional[float] = UNSET
    totalRawSecs: Optional[float] = UNSET
    totalMachineSecs: Optional[float] = UNSET
    averageChargeFactor: Optional[float] = UNSET
    totalStorage: Optional[float] = UNSET
    totalInodes: Optional[float] = UNSET

@strawberry.type
class Usage(UsageInput):
    pass

@strawberry.type
class PerDayUsage(Usage):
    dayOfYear: Optional[int] = UNSET

@strawberry.type
class PerUserUsage(Usage):
    userName: Optional[str] = UNSET

@strawberry.type
class ClusterInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    node_cpu_count: Optional[int] = UNSET
    node_cpu_count_divisor: Optional[int] = UNSET
    charge_factor: Optional[float] = UNSET

@strawberry.type
class Cluster(ClusterInput):
    pass

@strawberry.input
class AccessGroupInput:
    _id: Optional[MongoId] = UNSET
    state: Optional[str] = UNSET
    gid_number: Optional[int] = UNSET
    name: Optional[str] = UNSET

@strawberry.type
class AccessGroup( AccessGroupInput ):
    pass

@strawberry.input
class RepoInput:
    _id: Optional[MongoId] = UNSET

    state: Optional[str] = UNSET
    name: Optional[str] = UNSET
    facility: Optional[str] = UNSET
    #gid_number: Optional[int] = UNSET
    access_groups: Optional[List[str]] = UNSET

    principal: Optional[str] = UNSET
    leaders: Optional[List[str]] = UNSET
    users: Optional[List[str]] = UNSET

    group: Optional[str] = UNSET
    description: Optional[str] = UNSET

@strawberry.type
class Repo( RepoInput ):
    @strawberry.field
    def facilityObj(self, info) -> Facility:
        facilityObj = get_db(info,"facilities").find_one({"name": self.facility})
        del facilityObj["resources"]
        ret = Facility(**facilityObj)
        return ret

    @strawberry.field
    def roleObjs(self, info) -> List[Role]:
        repo = get_db(info,"repos").find_one({"_id": self._id })
        LOG.debug("Roles: " + str(repo.get("roles", {})))
        return [ Role(**{ "_id": None, "name": k, "privileges": [], "players": v }) for k,v in repo.get("roles", {}).items() ]

    @strawberry.field
    def allocations(self, info, resource: str, year: int) ->List[Allocation]:
        rc_filter = { "facility": self.facility, "resource": resource, "repo": self.name}
        if year:
            rc_filter["year"] = year
        return [ Allocation(**{k:x.get(k, 0) for k in ["year", "compute", "storage", "inodes", "resource", "facility"] }) for x in  get_db(info,"allocations").find(rc_filter) ]

    @strawberry.field
    def userAllocations(self, info, resource: str, year: int) ->List[UserAllocation]:
        rc_filter = { "facility": self.facility, "resource": resource, "repo": self.name }
        if year:
            rc_filter["year"] = year
        return [ UserAllocation(**{k:x.get(k, 0) for k in ["year", "compute", "storage", "inodes", "resource", "facility", "username"] }) for x in  get_db(info,"user_allocations").find(rc_filter) ]

    @strawberry.field
    def usage(self, info, resource: str, year: int) ->List[Usage]:
        LOG.debug("Getting the usage statistics for resource %s for year %s in facility %s for repo %s", resource, year, self.facility, self.name)
        results = get_db(info,"jobs").aggregate([
            { "$match": { "facility": self.facility, "resource": resource, "year": year, "repo": self.name }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "resource" : "$resource", "year" : "$year"},
                "totalNerscSecs": { "$sum": "$nerscSecs" },
                "totalRawSecs": { "$sum": "$rawSecs" },
                "totalMachineSecs": { "$sum": "$machineSecs" },
                "averageChargeFactor": { "$avg": "$chargeFactor" }
            }},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "resource": "$_id.resource",
                "facility": "$_id.facility",
                "year": "$_id.year",
                "totalNerscSecs": 1,
                "totalRawSecs": 1,
                "totalMachineSecs": 1,
                "averageChargeFactor": 1
            }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ Usage(**x) for x in  usage ]

    @strawberry.field
    def perDayUsage(self, info, resource: str, year: int) ->List[PerDayUsage]:
        LOG.debug("Getting the per day usage statistics for resource %s for year %s in facility %s for repo %s", resource, year, self.facility, self.name)
        results = get_db(info,"jobs").aggregate([
            { "$match": { "facility": self.facility, "resource": resource, "year": year, "repo": self.name }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "resource" : "$resource", "year" : "$year", "dayOfYear": { "$dayOfYear": {"date": "$startTs", "timezone": "America/Los_Angeles"}}},
                "totalNerscSecs": { "$sum": "$nerscSecs" },
                "totalRawSecs": { "$sum": "$rawSecs" },
                "totalMachineSecs": { "$sum": "$machineSecs" },
                "averageChargeFactor": { "$avg": "$chargeFactor" }
            }},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "resource": "$_id.resource",
                "facility": "$_id.facility",
                "year": "$_id.year",
                "dayOfYear": "$_id.dayOfYear",
                "totalNerscSecs": 1,
                "totalRawSecs": 1,
                "totalMachineSecs": 1,
                "averageChargeFactor": 1
            }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ PerDayUsage(**x) for x in  usage ]

    @strawberry.field
    def perUserUsage(self, info, resource: str, year: int) ->List[PerUserUsage]:
        LOG.debug("Getting the per user usage statistics for resource %s for year %s in facility %s for repo %s", resource, year, self.facility, self.name)
        results = get_db(info,"jobs").aggregate([
            { "$match": { "facility": self.facility, "resource": resource, "year": year, "repo": self.name }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "resource" : "$resource", "year" : "$year", "userName": "$userName"},
                "totalNerscSecs": { "$sum": "$nerscSecs" },
                "totalRawSecs": { "$sum": "$rawSecs" },
                "totalMachineSecs": { "$sum": "$machineSecs" },
                "averageChargeFactor": { "$avg": "$chargeFactor" }
            }},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "resource": "$_id.resource",
                "facility": "$_id.facility",
                "year": "$_id.year",
                "userName": "$_id.userName",
                "totalNerscSecs": 1,
                "totalRawSecs": 1,
                "totalMachineSecs": 1,
                "averageChargeFactor": 1
            }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ PerUserUsage(**x) for x in  usage ]

@strawberry.type
class Qos:

    _id: MongoId
    name: str
    repo: str
    qos: str
    partition: str




@strawberry.input
class Job:

    jobId: str
    userName: str
    uid: int
    accountName: str
    partitionName: str
    qos: str
    startTs: datetime
    endTs: datetime
    ncpus: int
    allocNodes: int
    allocTres: str
    nodelist: str
    reservation: str
    reservationId: str
    submitter: str
    submitTs: datetime
    hostName: str
    officialImport: bool
    computeId: str
    elapsedSecs: float
    waitTime: float
    chargeFactor: float
    rawSecs: float
    nerscSecs: float
    machineSecs: float
    repo: str
    year: int
    facility: str
    resource: str


@strawberry.type
class StorageUsageInput:
    _id: Optional[MongoId] = UNSET
    facility: Optional[str] = UNSET
    resource: Optional[str] = UNSET
    repo: Optional[str] = UNSET
    year: Optional[int] = UNSET
    folder: Optional[int] = UNSET
    storage: Optional[float] = UNSET
    inodes: Optional[float] = UNSET
    report_date: Optional[datetime] = UNSET

@strawberry.type
class StorageUsage(StorageUsageInput):
    pass


# class mapping of the 'thing' to the class
KLASSES = {
    'users': User,
    'access_groups': AccessGroup,
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

def find_access_groups( info: Info, filter: Optional[AccessGroupInput], exclude_fields: Optional[List[str]] = [] ) -> List[AccessGroup]:
    return find_thing( 'access_groups', info, filter, exclude_fields=exclude_fields )

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


def update_thing( thing, info, data, required_fields=[ 'Id', ], find_existing={} ):
    klass = KLASSES[thing]
    things = find_thing( thing, info, find_existing )
    if len(things) == 0:
        raise Exception(f"{thing} not found with {find_existing}")
    elif len(things) > 1:
        raise Exception(f"too many {thing} matched with {find_existing}")
    new = to_dict(things[0])
    for k,v in vars(data).items():
        if v:
            new[k] = v
    db = get_db(info, thing)
    db.update_one( { '_id': new['_id'] }, { "$set": new } )
    item = klass( **new )
    return item
