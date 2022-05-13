import dataclasses
from typing import List, Optional
import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET
from typing import NewType

from datetime import datetime
from bson import ObjectId

import logging

LOG = logging.getLogger(__name__)

# the database name for all data
DB_NAME = "iris"

MongoId = strawberry.scalar(
    NewType("MongoId", object),
    serialize = lambda v: str(v),
    parse_value = lambda v: ObjectId(v),
)


# would this be useful? https://github.com/strawberry-graphql/strawberry/discussions/444

# we generally just set everything to be option so that we can create a form like experience with graphql. we impose some of the required fields in some utility functions like create_thing(). not a great use of the graphql spec, but allows to to limit the amount of code we have to write

@strawberry.input
class EppnInput:
    eppn: Optional[str] = UNSET
    fullname: Optional[str] = UNSET
    email: Optional[str] = UNSET
    organization: Optional[str] = UNSET

@strawberry.type
class Eppn(EppnInput):
    pass

@strawberry.input
class UserInput:
    _id: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    uidnumber: Optional[int] = UNSET
    eppns: Optional[List[str]] = UNSET

@strawberry.type
class User(UserInput):
    # eppnObjs is most likely a call to some external service to get the details of an eppn
    # For now we assume everyone is a SLAC person.
    @strawberry.field
    def eppnObjs(self, info) -> List[Eppn]:
        ret = [ Eppn(**{ "eppn": self.username, "fullname": self.username, "email": self.username+"@slac.stanford.edu", "organization": "slac.stanford.edu"})]
        if self.eppns is UNSET:
            return []
        for x in self.eppns:
            if '@' not in x:
                ret.append(Eppn(**{ "eppn": x, "fullname": x, "email": x+"@slac.stanford.edu", "organization": "slac.stanford.edu" }))
            else:
                ret.append(Eppn(**{ "eppn": x.split("@")[0], "fullname": x, "email": x, "organization": x.split("@")[1] }))
        return ret

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
        return [ Partition(**x) for x in  info.context.db.collection("partitions").find({"name": {"$in": self.partitions } } ) ]
    @strawberry.field
    def capacities(self, info, year: int = 0) ->List[ResourceCapacity]:
        rc_filter = { "facility": self.facility_name,  "resource": self.name }
        if year:
            rc_filter["year"] = year
        return [ ResourceCapacity(**{k:x.get(k, 0) for k in ["year", "compute", "storage", "inodes"] }) for x in  info.context.db.collection("resource_capacity").find(rc_filter) ]

@strawberry.input
class FacilityInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    description: Optional[str] = UNSET

@strawberry.type
class Facility( FacilityInput ):
    @strawberry.field
    def resources(self, info) -> List[Resource]:
        fac = info.context.db.collection("facilities").find_one({"_id": self._id })
        return [ Resource(**{"name": k, "facility_name": self.name, "type": v["type"], "partitions": v.get("partitions", []), "root": v.get("root", None)}) for k,v in fac.get("resources", {}).items() ]

@strawberry.input
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

@strawberry.input
class UserAllocationInput(AllocationInput):
    username: Optional[str] = UNSET

@strawberry.type
class UserAllocation(UserAllocationInput):
    pass

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
class PerDateUsage(Usage):
    date: Optional[datetime] = UNSET

@strawberry.type
class PerUserUsage(Usage):
    username: Optional[str] = UNSET

@strawberry.type
class PerFolderUsage(Usage):
    folder: Optional[str] = UNSET

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
    members: Optional[List[str]] = UNSET

@strawberry.type
class AccessGroup( AccessGroupInput ):
    @strawberry.field
    def memberObjs(self, info) ->List[User]:
        if self.members is UNSET:
            return []
        return info.context.db.find_users({"username": {"$in": self.members}})

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
        return info.context.db.find_facility({"name": self.facility}, exclude_fields=['resources'])

    @strawberry.field
    def allUsers(self, info) -> List[User]:
        allusernames = list(set(self.users).union(set(self.leaders).union(set(list(self.principal)))))
        return [ User(**x) for x in  info.context.db.find_users({"username": {"$in": allusernames}}) ]

    @strawberry.field
    def accessGroupObjs(self, info) ->List[AccessGroup]:
        if self.access_groups is UNSET:
            return []
        return info.context.db.collection('access_groups', {"name": {"$in": self.access_groups}})

    @strawberry.field
    def allocations(self, info, resource: str, year: int) ->List[Allocation]:
        rc_filter = { "facility": self.facility, "resource": resource, "repo": self.name}
        if year:
            rc_filter["year"] = year
        return [ Allocation(**{k:x.get(k, 0) for k in ["repo", "year", "compute", "storage", "inodes", "resource", "facility"] }) for x in  info.context.db.collection("allocations").find(rc_filter) ]

    @strawberry.field
    def userAllocations(self, info, resource: str, year: int) ->List[UserAllocation]:
        rc_filter = { "facility": self.facility, "resource": resource, "repo": self.name }
        if year:
            rc_filter["year"] = year
        return [ UserAllocation(**{k:x.get(k, 0) for k in ["repo", "year", "compute", "storage", "inodes", "resource", "facility", "username"] }) for x in  info.context.db.collection("user_allocations").find(rc_filter) ]

    @strawberry.field
    def usage(self, info, resource: str, year: int) ->List[Usage]:
        LOG.debug("Getting the usage statistics for resource %s for year %s in facility %s for repo %s", resource, year, self.facility, self.name)
        results = info.context.collection("jobs").aggregate([
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
        results = info.context.db.collection("jobs").aggregate([
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
        results = info.context.db.collection("jobs").aggregate([
            { "$match": { "facility": self.facility, "resource": resource, "year": year, "repo": self.name }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "resource" : "$resource", "year" : "$year", "username": "$username"},
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
                "username": "$_id.username",
                "totalNerscSecs": 1,
                "totalRawSecs": 1,
                "totalMachineSecs": 1,
                "averageChargeFactor": 1
            }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ PerUserUsage(**x) for x in  usage ]

    @strawberry.field
    def storageUsage(self, info, resource: str, year: int) ->List[Usage]:
        LOG.debug("Getting the storage usage statistics for resource %s for year %s in facility %s for repo %s", resource, year, self.facility, self.name)
        results = info.context.db.collection("diskusage").aggregate([
            { "$match": { "facility": self.facility, "resource": resource, "year": year, "repo": self.name }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "resource" : "$resource", "year" : "$year", "date": "$date"},
                "totalStorage": { "$sum": "$storage" },
                "totalInodes": { "$sum": "$inodes" }
            }},
            {"$sort": {"_id.date": -1}},
            {"$limit": 1},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "resource": "$_id.resource",
                "facility": "$_id.facility",
                "year": "$_id.year",
                "totalStorage": 1,
                "totalInodes": 1
            }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ Usage(**x) for x in  usage ]

    @strawberry.field
    def perDayStorageUsage(self, info, resource: str, year: int) ->List[PerDateUsage]:
        LOG.debug("Getting the per day storage usage statistics for resource %s for year %s in facility %s for repo %s", resource, year, self.facility, self.name)
        results = info.context.db.collection("diskusage").aggregate([
            { "$match": { "facility": self.facility, "resource": resource, "year": year, "repo": self.name }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "resource" : "$resource", "year" : "$year", "date": "$date"},
                "totalStorage": { "$sum": "$storage" },
                "totalInodes": { "$sum": "$inodes" }
            }},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "type": "$_id.type",
                "year": "$_id.year",
                "date": "$_id.date",
                "totalStorage": 1,
                "totalInodes": 1
            }},
            { "$sort": { "dayOfYear": 1 }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ PerDateUsage(**x) for x in  usage ]

    @strawberry.field
    def perFolderStorageUsage(self, info, resource: str, year: int) ->List[PerFolderUsage]:
        LOG.debug("Getting the per folder storage usage statistics for resource %s for year %s in facility %s for repo %s", resource, year, self.facility, self.name)
        results = info.context.db.collection("diskusage").aggregate([
            { "$match": { "facility": self.facility, "resource": resource, "year": year, "repo": self.name }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "resource" : "$resource", "year" : "$year", "date": "$date", "folder": "$folder" },
                "totalStorage": { "$sum": "$storage" },
                "totalInodes": { "$sum": "$inodes" }
            }},
            {"$sort": {"_id.date": -1}},
            {"$limit": 1},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "type": "$_id.type",
                "pool": "$_id.pool",
                "year": "$_id.year",
                "folder": "$_id.folder",
                "totalStorage": 1,
                "totalInodes": 1
            }},
            { "$sort": { "date": 1 }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ PerFolderUsage(**x) for x in  usage ]

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
    username: str
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

