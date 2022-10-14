import os
import dataclasses
from typing import List, Optional, Dict
import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET
from typing import NewType
from enum import Enum
import re

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

@strawberry.enum
class SDFRequestType(Enum):
    UserAccount = "UserAccount"
    NewRepo = "NewRepo"
    NewFacility = "NewFacility"
    RepoMembership = "RepoMembership"
    UserStorageAllocation = "UserStorageAllocation"
    RepoStorageAllocation = "RepoStorageAllocation"
    FacilityStorageAllocation = "FacilityStorageAllocation"
    RepoComputeAllocation = "RepoComputeAllocation"
    FacilityComputeAllocation = "FacilityComputeAllocation"

@strawberry.input
class SDFRequestInput:
    reqtype: Optional[SDFRequestType] = UNSET
    requestedby: Optional[str] = UNSET
    timeofrequest: Optional[datetime] = UNSET
    eppn: Optional[str] = UNSET
    username: Optional[str] = UNSET
    preferredUserName: Optional[str] = UNSET
    reponame: Optional[str] = UNSET
    facilityname: Optional[str] = UNSET
    principal: Optional[str] = UNSET
    clustername: Optional[str] = UNSET
    qosname: Optional[str] = UNSET
    volumename: Optional[str] = UNSET
    intent: Optional[str] = UNSET
    slachours: Optional[float] = 0
    gigabytes: Optional[float] = 0
    inodes: Optional[float] = 0
    notes: Optional[str] = UNSET

@strawberry.type
class SDFRequest(SDFRequestInput):
    _id: Optional[MongoId] = UNSET

@strawberry.type
class SDFRequestEvent:
    operationType: str
    theRequest: Optional[SDFRequest] = UNSET

@strawberry.input
class EppnInput:
    eppn: Optional[str] = UNSET
    fullname: Optional[str] = UNSET
    email: Optional[str] = UNSET
    organization: Optional[str] = UNSET

@strawberry.type
class Eppn(EppnInput):
    pass

@strawberry.type
class UserStorageUsage:
    _id: MongoId
    gigabytes: float
    inodes: float
    date: datetime
    allocid: MongoId

@strawberry.type
class UserStorage:
    _id: MongoId
    username: str
    intent: str
    gigabytes: float
    inodes: float
    volumename: str
    mount: str
    usage: Optional[UserStorageUsage]


@strawberry.type
class UserRegistration(EppnInput):
    isRegistered: Optional[bool] = UNSET
    isRegistrationPending: Optional[bool] = UNSET

@strawberry.input
class UserInput:
    _id: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    uidnumber: Optional[int] = UNSET
    eppns: Optional[List[str]] = UNSET
    preferredemail: Optional[str] = UNSET
    shell: Optional[str] = UNSET
    homequota: Optional[float] = UNSET
    homeused: Optional[float] = UNSET

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
    @strawberry.field
    def isAdmin(self, info) -> bool:
        admins = re.sub( "\s", "", os.environ.get("ADMIN_USERNAMES",'')).split(',')
        return self.username in admins
    @strawberry.field
    def groups(self, info) -> List[str]:
        grps = info.context.db.collection("access_groups").find({"members": self.username})
        if not grps:
            return []
        return [ x["name"] for x in grps]
    @strawberry.field
    def storages(self, info) -> List[UserStorage]:
        storages = list(info.context.db.collection("user_storage_allocation").find({"username": self.username}))
        if not storages:
            return []
        for storage in storages:
            usages = list(info.context.db.collection("user_storage_usage").find({"allocid": storage["_id"]}).sort([("date", -1)]).limit(1))
            if usages:
                storage["usage"] = UserStorageUsage(**usages[0])
            else:
                storage["usage"] = UserStorageUsage(**{"_id": None, "allocid": storage["_id"], "gigabytes": 0, "inodes": 0, "date": datetime.utcnow() })
        print(storages)
        return [ UserStorage(**storage) for storage in storages ]

@strawberry.type
class RepoFacilityName:
    name: str
    facility: str

@strawberry.input
class ClusterInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    nodecpucount: Optional[int] = UNSET
    nodecpucountdivisor: Optional[int] = UNSET
    nodegpucount: Optional[int] = UNSET
    nodememgb: Optional[int] = UNSET
    nodegpumemgb: Optional[int] = UNSET
    chargefactor: Optional[float] = UNSET
    nodecpusmt: Optional[int] = UNSET
    members: Optional[List[str]] = UNSET

@strawberry.type
class Cluster(ClusterInput):
    pass

@strawberry.input
class ClusterCapacityInput:
    name: Optional[str] = UNSET
    slachours: Optional[float] = UNSET
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class ClusterCapacity(ClusterCapacityInput):
    @strawberry.field
    def cluster(self, info) -> Cluster:
        clusdefn = info.context.db.collection("clusters").find_one({"name": self.name})
        print(clusdefn)
        return Cluster(**clusdefn)

@strawberry.input
class ResourceInput:
    name: Optional[str] = UNSET
    type: Optional[str] = UNSET

@strawberry.type
class Resource(ResourceInput):
    pass

@strawberry.input
class CapacityInput:
    _id: Optional[MongoId] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET

@strawberry.type
class Capacity(CapacityInput):
    @strawberry.field
    def clusters(self, info) -> List[ClusterCapacity]:
        cap = info.context.db.collection("capacity").find_one({"_id": self._id})
        return [ ClusterCapacity(**{ k: c[k] for k in ["name", "slachours"] }) for c in cap.get("clusters", []) ]
    @strawberry.field
    def storage(self, info) -> List[ClusterCapacity]:
        cap = info.context.db.collection("capacity").find_one({"_id": self._id})
        return [ ClusterCapacity(**{ k: c[k] for k in ["name", "gigabytes", "inodes"] }) for c in cap.get("storage", []) ]

@strawberry.input
class FacilityInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    description: Optional[str] = UNSET
    resources: Optional[List[str]] = UNSET
    serviceaccount: Optional[str] = UNSET
    servicegroup: Optional[str] = UNSET
    czars: Optional[List[str]] = UNSET

@strawberry.type
class Facility( FacilityInput ):
    @strawberry.field
    def capacity(self, info) -> Optional[Capacity]:
        caps = list(info.context.db.collection("capacity").find({"facility": self.name }).sort([("end", -1)]).limit(1))
        if caps:
            cap = caps[0]
            return Capacity(**{k : cap[k] for k in [ "_id", "start", "end" ]})
        else:
            return None

@strawberry.input
class QosInput:
    name: Optional[str] = UNSET
    slachours: Optional[float] = UNSET
    chargefactor: Optional[float] = UNSET

@strawberry.type
class Qos(QosInput):
    pass

@strawberry.input
class VolumeInput:
    name: Optional[str] = UNSET
    purpose: Optional[str] = UNSET # science-data, group etc
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class Volume(VolumeInput):
    pass

@strawberry.type
class UsageInput:
    facility: Optional[str] = UNSET
    resource: Optional[str] = UNSET
    repo: Optional[str] = UNSET
    qos: Optional[str] = UNSET
    rawsecs: Optional[float] = UNSET
    machinesecs: Optional[float] = UNSET
    slacsecs: Optional[float] = UNSET
    avgcf: Optional[float] = UNSET
    totalStorage: Optional[float] = UNSET
    totalInodes: Optional[float] = UNSET

@strawberry.type
class Usage(UsageInput):
    pass

@strawberry.type
class PerDayUsage(Usage):
    year: Optional[int] = UNSET
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

@strawberry.input
class RepoComputeAllocationInput:
    _id: Optional[MongoId] = UNSET
    repo: Optional[str] = UNSET
    clustername: Optional[str] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET

@strawberry.type
class RepoComputeAllocation(RepoComputeAllocationInput):
    qoses: Optional[List[Qos]] = UNSET
    @strawberry.field
    def qoses(self, info) ->List[Qos]:
        me = info.context.db.collection("repo_compute_allocations").find_one({"_id": self._id})
        qoses = []
        # GraphQL can't really handle nested dicts. So, we maintain dicts in the database and convert to arrays when sending data across.
        for k,v in me.get("qoses", {}).items():
            q = { "name": k }
            q.update(v)
            qoses.append(q)
        return [ Qos(**q) for q in qoses ]
    @strawberry.field
    def volumes(self, info) ->List[Volume]:
        me = info.context.db.collection("repo_compute_allocations").find_one({"_id": self._id})
        vols = [ {"purpose": k} | m for k,v in me.get("volumes", {}).items() for m in v ]
        return [ Volume(**x) for x in vols ]
    @strawberry.field
    def usage(self, info) ->List[Usage]:
        """
        Overall usage; so pick up from the cached collections.
        """
        LOG.debug("Getting the total usage for repo %s", self.repo)
        usages = []
        for qos in self.qoses(info):
            usg = info.context.db.collection("computeusagecache").find_one({"allocationId": self._id, "qos": qos.name})
            if not usg:
                continue
            usages.append({
                "repo": self.repo,
                "resource": self.clustername,
                "qos": qos.name,
                "rawsecs": usg["rawsecs"],
                "machinesecs": usg["machinesecs"],
                "slacsecs": usg["slacsecs"],
                "avgcf": usg["avgcf"]
            })
        return [ Usage(**x) for x in  usages ]
    @strawberry.field
    def perDayUsage(self, info, year: int) ->List[PerDayUsage]:
        LOG.debug("Getting the per day usage statistics for cluster %s for year %s in for repo %s", self.clustername, year, self.repo)
        results = info.context.db.collection("jobs").aggregate([
            { "$match": { "clustername": self.clustername, "year": year, "repo": self.repo }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "clustername" : "$clustername", "year" : "$year", "dayOfYear": { "$dayOfYear": {"date": "$startTs", "timezone": "America/Los_Angeles"}}},
                "slacsecs": { "$sum": "$slacsecs" },
                "rawsecs": { "$sum": "$rawsecs" },
                "machinesecs": { "$sum": "$machinesecs" },
                "avgcf": { "$avg": "$finalcf" }
            }},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "resource": "$_id.clustername",
                "facility": "$_id.facility",
                "year": "$_id.year",
                "dayOfYear": "$_id.dayOfYear",
                "slacsecs": 1,
                "rawsecs": 1,
                "machinesecs": 1,
                "avgcf": 1
            }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ PerDayUsage(**x) for x in  usage ]

    @strawberry.field
    def perUserUsage(self, info, year: int) ->List[PerUserUsage]:
        LOG.debug("Getting the per user usage statistics for cluster %s for year %s in for repo %s", self.clustername, year, self.repo)
        results = info.context.db.collection("jobs").aggregate([
            { "$match": { "clustername": self.clustername, "year": year, "repo": self.repo }},
            { "$group": { "_id": {"repo": "$repo", "facility": "$facility", "clustername" : "$clustername", "year" : "$year", "username": "$username"},
                "slacsecs": { "$sum": "$slacsecs" },
                "rawsecs": { "$sum": "$rawsecs" },
                "machinesecs": { "$sum": "$machinesecs" },
                "avgcf": { "$avg": "$finalcf" }
            }},
            { "$project": {
                "_id": 0,
                "repo": "$_id.repo",
                "resource": "$_id.clustername",
                "facility": "$_id.facility",
                "username": "$_id.username",
                "slacsecs": 1,
                "rawsecs": 1,
                "machinesecs": 1,
                "avgcf": 1
            }}
        ])
        usage = list(results)
        LOG.debug(usage)
        return [ PerUserUsage(**x) for x in  usage ]

@strawberry.input
class UserAllocationInput():
    repo: Optional[str] = UNSET
    resource: Optional[str] = UNSET
    facility: Optional[str] = UNSET
    username: Optional[str] = UNSET
    percent: Optional[float] = UNSET # For now, we use one number for compute and storage..

@strawberry.type
class UserAllocation(UserAllocationInput):
    pass

@strawberry.input
class AccessGroupInput:
    _id: Optional[MongoId] = UNSET
    state: Optional[str] = UNSET
    gid_number: Optional[int] = UNSET # perhaps we should use a linux non-specific name?
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
class VolumeUsage:
    _id: Optional[MongoId] = UNSET
    facility: Optional[str] = UNSET
    name: Optional[str] = UNSET
    type: Optional[str] = UNSET
    accessgroups: Optional[List[str]] = UNSET
    path: Optional[str] = UNSET # Path object? how about uri for s3?


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
        return info.context.db.find_facility({"name": self.facility}, exclude_fields=["policies"])

    @strawberry.field
    def allUsers(self, info) -> List[User]:
        allusernames = list(set(self.users).union(set(self.leaders).union(set(list(self.principal)))))
        return info.context.db.find_users({"username": {"$in": allusernames}})

    @strawberry.field
    def accessGroupObjs(self, info) ->List[AccessGroup]:
        if self.access_groups is UNSET:
            return []
        return info.context.db.find_access_groups({"name": {"$in": self.access_groups}})

    @strawberry.field
    def currentComputeAllocations(self, info) ->List[RepoComputeAllocation]:
        """
        Each repo can have multiple allocation objects.
        This call should return an array of "current" allocations; one for each compute resource.
        """
        rc_filter = { "facility": self.facility, "repo": self.name}
        # More complex; we want to return the "current" per resource type.
        current_allocs = info.context.db.collection("repo_compute_allocations").aggregate([
            { "$match": { "repo": self.name }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"repo": "$repo", "clustername": "$clustername"}, "origid": {"$first": "$_id"}}},
        ])
        current_alloc_ids = list(map(lambda x: x["origid"], current_allocs))
        return [ RepoComputeAllocation(**{k:x.get(k, 0) for k in ["_id", "repo", "clustername", "start", "end" ] }) for x in  info.context.db.collection("repo_compute_allocations").find({"_id" : {"$in": current_alloc_ids}})]

    @strawberry.field
    def userAllocations(self, info, resource: str) ->List[UserAllocation]:
        rc_filter = { "facility": self.facility, "resource": resource, "repo": self.name }
        return [ UserAllocation(**{k:x.get(k, 0) for k in ["facility", "resource", "repo", "username", "percent"] }) for x in  info.context.db.collection("user_allocations").find(rc_filter) ]

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

@strawberry.input
class Job:
    jobId: str
    username: str
    uid: int
    accountName: str
    partitionName: str
    qos: str
    allocationId: MongoId
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
    officialImport: bool
    elapsedSecs: float
    waitSecs: float
    # After this, all the values are computed ( some of them are matched from info in the database)
    priocf: float
    hwcf: float
    finalcf: float
    rawsecs: float # elapsed seconds * number of nodes
    machinesecs: float # raw seconds after applying the hardware charge factor
    slacsecs: float # machinesecs after applying the priority charge factor
    repo: str
    year: int
    facility: str
    clustername: str

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
