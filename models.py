import os
import dataclasses
from typing import List, Optional, Dict
import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET
from typing import NewType
from enum import Enum, IntEnum
import re
import json

from datetime import datetime, date
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
    RepoComputeAllocation = "RepoComputeAllocation"
    RepoStorageAllocation = "RepoStorageAllocation"
    FacilityComputeAllocation = "FacilityComputeAllocation"
    FacilityStorageAllocation = "FacilityStorageAllocation"

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
    storagename: Optional[str] = UNSET
    qosname: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    allocationid: Optional[MongoId] = UNSET
    slachours: Optional[float] = 0
    gigabytes: Optional[float] = 0
    inodes: Optional[float] = 0
    notes: Optional[str] = UNSET

@strawberry.enum
class SDFRequestStatus(IntEnum):
    NotActedOn = 0
    Approved = 1
    Rejected = -1


@strawberry.type
class SDFRequest(SDFRequestInput):
    _id: Optional[MongoId] = UNSET
    approvalstatus: Optional[SDFRequestStatus] = SDFRequestStatus.NotActedOn
    actedby: Optional[str] = UNSET
    actedat: Optional[datetime] = UNSET

    def approve(self, info) -> bool:
        info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": SDFRequestStatus.Approved.value, "actedby": info.context.username, "actedat": datetime.utcnow() }})
        return True
    def reject(self, info) -> bool:
        info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": SDFRequestStatus.Rejected.value, "actedby": info.context.username, "actedat": datetime.utcnow() }})
        return True


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
    purpose: str
    gigabytes: float
    inodes: float
    storagename: str
    rootfolder: str
    usage: Optional[UserStorageUsage]


@strawberry.type
class UserRegistration(EppnInput):
    isRegistered: Optional[bool] = UNSET
    isRegistrationPending: Optional[bool] = UNSET
    fullname: Optional[str] = UNSET

@strawberry.input
class UserInput:
    _id: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    fullname: Optional[str] = UNSET
    uidnumber: Optional[int] = UNSET
    eppns: Optional[List[str]] = UNSET
    preferredemail: Optional[str] = UNSET
    shell: Optional[str] = UNSET
    publichtml: bool = False

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
    def isCzar(self, info) -> bool:
        myfacs = list(info.context.db.find_facilities({"czars": self.username}, exclude_fields=["policies"]))
        if myfacs:
            return True
        return False
    @strawberry.field
    def isImpersonating(self, info) -> bool:
        return info.context.is_impersonating
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
class ComputeAllocationInput:
    _id: Optional[MongoId] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    clustername: Optional[str] = UNSET
    slachours: Optional[float] = UNSET

@strawberry.input
class StorageAllocationInput:
    _id: Optional[MongoId] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    storagename: Optional[str] = UNSET
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class FacilityComputeAllocation(ComputeAllocationInput):
    pass

@strawberry.type
class FacilityStorageAllocation(StorageAllocationInput):
    pass

# Types for the FAcilities list view page.
@strawberry.type
class FacilityComputePurchases:
    clustername: Optional[str] = UNSET
    purchased: Optional[float] = UNSET
    allocated: Optional[float] = UNSET
    used: Optional[float] = UNSET
@strawberry.type
class FacilityStoragePurchases:
    storagename: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    purchased: Optional[float] = UNSET
    allocated: Optional[float] = UNSET
    used: Optional[float] = UNSET

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
    def computepurchases(self, info) -> Optional[List[FacilityComputePurchases]]:
        # More complex; we want to return the "current" per resource type.
        todaysdate = datetime.utcnow()
        aggs = info.context.db.collection("facility_compute_purchases").aggregate([
            { "$match": { "facility": self.name, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"clustername": "$clustername"}, "slachours": {"$sum": "$slachours"}}},
        ])
        purchases = { x["_id"]["clustername"]: { "purchased": x["slachours"] } for x in aggs }
        aaggs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_compute_allocations", "localField": "name", "foreignField": "repo", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }}
        ])
        allocs = { x["clustername"]: sum([y["slachours"] for y in x["qoses"].values()]) for x in aaggs }
        uaggs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_compute_allocations", "localField": "name", "foreignField": "repo", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }}, # This gives us current allocations
            { "$lookup": { "from": "repo_overall_compute_usage", "localField": "_id", "foreignField": "allocationid", "as": "usage"}},
            { "$unwind": "$usage" },
            { "$group": { "_id": {"clustername": "$clustername"}, "slachours": {"$sum": "$usage.slachours"}}},
        ])
        used = { x["_id"]["clustername"]: x["slachours"] for x in uaggs }
        for k,v in purchases.items():
            v["clustername"] = k
            v["allocated"] = allocs.get(k, 0)
            v["used"] = used.get(k, 0)
        return [ FacilityComputePurchases(**{k:x.get(k, 0) for k in ["clustername", "purchased", "allocated", "used" ] }) for x in purchases.values()]
    @strawberry.field
    def computeallocations(self, info) -> Optional[List[FacilityComputeAllocation]]:
        # More complex; we want to return the "current" per resource type.
        todaysdate = datetime.utcnow()
        current_allocs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_compute_allocations", "localField": "name", "foreignField": "repo", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$group": { "_id": {"clustername": "$clustername"}, "slachours": {"$sum": "$slachours"}}},
        ])
        return [ FacilityComputeAllocation(**{k:x.get(k, 0) for k in ["_id", "clustername", "slachours" ] }) for x in current_allocs]
    @strawberry.field
    def storagepurchases(self, info) -> Optional[List[FacilityStoragePurchases]]:
        # More complex; we want to return the "current" per resource type.
        todaysdate = datetime.utcnow()
        aggs = info.context.db.collection("facility_storage_purchases").aggregate([
            { "$match": { "facility": self.name, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"storagename": "$storagename", "purpose": "$purpose"}, "gigabytes": {"$sum": "$gigabytes"}}},
        ])
        purchases = { (x["_id"]["storagename"], x["_id"]["purpose"]): { "purchased": x["gigabytes"] } for x in aggs }
        LOG.error("Purchases for %s is %s", self.name, purchases)
        aaggs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_storage_allocations", "localField": "name", "foreignField": "repo", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$group": { "_id": {"storagename": "$storagename", "purpose": "$purpose"}, "gigabytes": {"$sum": "$gigabytes"}}},
        ])
        allocs = { (x["_id"]["storagename"], x["_id"]["purpose"]): x["gigabytes"] for x in aaggs }
        LOG.error("Allocations for %s is %s", self.name, allocs)
        uaggs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_storage_allocations", "localField": "name", "foreignField": "repo", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$lookup": { "from": "repo_overall_storage_usage", "localField": "_id", "foreignField": "allocationid", "as": "usage"}},
            { "$unwind": "$usage" },
            { "$group": { "_id": {"storagename": "$storagename", "purpose": "$purpose"}, "gigabytes": {"$sum": "$usage.gigabytes"}}},
        ])
        used = { (x["_id"]["storagename"], x["_id"]["purpose"]): x["gigabytes"] for x in uaggs }
        LOG.error("Used for %s is %s", self.name, used)
        for k,v in purchases.items():
            v["storagename"] = k[0]
            v["purpose"] = k[1]
            v["allocated"] = allocs.get(k, 0)
            v["used"] = used.get(k, 0)
        return [ FacilityStoragePurchases(**{k:x.get(k, 0) for k in ["storagename", "purpose", "purchased", "allocated", "used" ] }) for x in purchases.values()]

@strawberry.input
class QosInput:
    name: Optional[str] = UNSET
    slachours: Optional[float] = UNSET
    chargefactor: Optional[float] = UNSET

@strawberry.type
class Qos(QosInput):
    pass

@strawberry.input
class UsageInput:
    facility: Optional[str] = UNSET
    repo: Optional[str] = UNSET
    qos: Optional[str] = UNSET
    clustername: Optional[str] = UNSET
    storagename: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    rawsecs: Optional[float] = 0
    machinesecs: Optional[float] = 0
    slachours: Optional[float] = 0
    avgcf: Optional[float] = 0
    gigabytes: Optional[float] = 0
    inodes: Optional[float] = 0

@strawberry.type
class Usage(UsageInput):
    pass

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
class ReportRangeInput:
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET

@strawberry.input
class UserAllocationInput():
    allocationid: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    percent: Optional[float] = UNSET

@strawberry.type
class UserAllocation(UserAllocationInput):
    pass

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
    def userAllocations(self, info) ->List[UserAllocation]:
        rc_filter = { "allocationid": self._id }
        return [ UserAllocation(**{k:x.get(k, 0) for k in ["username", "percent"] }) for x in  info.context.db.collection("user_allocations").find(rc_filter) ]
    @strawberry.field
    def usage(self, info) ->List[Usage]:
        """
        Overall usage; so pick up from the cached collections.
        """
        LOG.debug("Getting the total usage for repo %s", self.repo)
        usages = []
        for qos in self.qoses(info):
            usg = info.context.db.collection("repo_overall_compute_usage").find_one({"allocationid": self._id, "qos": qos.name})
            if not usg:
                continue
            usages.append({
                "repo": self.repo,
                "clustername": self.clustername,
                "qos": qos.name,
                "rawsecs": usg["rawsecs"],
                "machinesecs": usg["machinesecs"],
                "slachours": usg["slachours"],
                "avgcf": usg["avgcf"]
            })
        return [ Usage(**x) for x in  usages ]
    @strawberry.field
    def perDateUsage(self, info) ->List[PerDateUsage]:
        results = info.context.db.collection("repo_daily_compute_usage").find({"allocationid": self._id})
        return info.context.db.cursor_to_objlist(results, PerDateUsage, exclude_fields={"_id", "allocationid"})

    @strawberry.field
    def perUserUsage(self, info) ->List[PerUserUsage]:
        results = info.context.db.collection("repo_peruser_compute_usage").find({"allocationid": self._id})
        return info.context.db.cursor_to_objlist(results, PerUserUsage, exclude_fields={"_id", "allocationid"})

@strawberry.input
class RepoStorageAllocationInput:
    _id: Optional[MongoId] = UNSET
    repo: Optional[str] = UNSET
    storagename: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    rootfolder: Optional[str] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class RepoStorageAllocation(RepoStorageAllocationInput):
    @strawberry.field
    def usage(self, info) -> Optional[Usage]:
        """
        Overall usage; so pick up from the cached collections.
        """
        LOG.debug("Getting the total storage usage for repo %s", self.repo)
        usgs = list(info.context.db.collection("repo_overall_storage_usage").find({"allocationid": self._id}).sort([("date", -1)]).limit(1))
        if not usgs:
            return Usage(**{ "repo": self.repo, "storagename": self.storagename })
        usg = usgs[0]
        return Usage(**{
            "repo": self.repo,
            "storagename": self.storagename,
            "gigabytes": usg["gigabytes"],
            "inodes": usg["inodes"]
        })
    @strawberry.field
    def perDateUsage(self, info, year: int) -> List[PerDateUsage]:
        """
        Return all the daily usages for this allocation for the specified year
        """
        jan1thisyear = datetime.now().replace(year=year,month=1, day=1)
        jan1nextyear = jan1thisyear.replace(year=year+1)
        usgs = info.context.db.collection("repo_daily_storage_usage").find({"allocationid": self._id, "date": {"$gte": jan1thisyear, "$lt": jan1nextyear}}, {"_id": 0, "date": 1, "gigabytes": 1, "inodes": 1}).sort([("date", -1)])
        if not usgs:
            return []
        return [ PerDateUsage(**x) for x in  usgs ]

@strawberry.input
class AccessGroupInput:
    _id: Optional[MongoId] = UNSET
    state: Optional[str] = UNSET
    gidnumber: Optional[int] = UNSET # perhaps we should use a linux non-specific name?
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
    #gidnumber: Optional[int] = UNSET
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
        todaysdate = datetime.utcnow()
        # More complex; we want to return the "current" per resource type.
        current_allocs = info.context.db.collection("repo_compute_allocations").aggregate([
            { "$match": { "repo": self.name, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"repo": "$repo", "clustername": "$clustername"}, "origid": {"$first": "$_id"}}},
        ])
        current_alloc_ids = list(map(lambda x: x["origid"], current_allocs))
        return [ RepoComputeAllocation(**{k:x.get(k, 0) for k in ["_id", "repo", "clustername", "start", "end" ] }) for x in  info.context.db.collection("repo_compute_allocations").find({"_id" : {"$in": current_alloc_ids}})]

    @strawberry.field
    def computeAllocation(self, info, allocationid: MongoId) -> Optional[RepoComputeAllocation]:
        """
        Return the specific storage allocation for this repo
        """
        rc_filter = { "_id": allocationid, "repo": self.name}
        alloc = info.context.db.collection("repo_compute_allocations").find_one(rc_filter)
        if not alloc:
            return None
        del alloc["qoses"]
        return RepoComputeAllocation(**alloc)

    @strawberry.field
    def currentStorageAllocations(self, info) ->List[RepoStorageAllocation]:
        """
        Each repo can have multiple allocation objects.
        This call should return an array of "current" allocations; one for each compute resource.
        """
        rc_filter = { "facility": self.facility, "repo": self.name}
        todaysdate = datetime.utcnow()
        # More complex; we want to return the "current" per resource type.
        current_allocs = info.context.db.collection("repo_storage_allocations").aggregate([
            { "$match": { "repo": self.name, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"repo": "$repo", "purpose": "$purpose"}, "origid": {"$first": "$_id"}}},
        ])
        current_alloc_ids = list(map(lambda x: x["origid"], current_allocs))
        return [ RepoStorageAllocation(**{k:x.get(k, 0) for k in ["_id", "repo", "storagename", "purpose", "rootfolder", "start", "end", "gigabytes", "inodes" ] }) for x in  info.context.db.collection("repo_storage_allocations").find({"_id" : {"$in": current_alloc_ids}})]

    @strawberry.field
    def storageAllocation(self, info, allocationid: MongoId) -> Optional[RepoStorageAllocation]:
        """
        Return the specific storage allocation for this repo
        """
        rc_filter = { "_id": allocationid, "repo": self.name}
        alloc = info.context.db.collection("repo_storage_allocations").find_one(rc_filter)
        if not alloc:
            return None
        return RepoStorageAllocation(**alloc)

@strawberry.input
class Job:
    jobId: str
    username: str
    uid: int
    accountName: str
    partitionName: str
    qos: str
    allocationid: MongoId
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
    slachours: float # machinesecs after applying the priority charge factor
    repo: str
    year: int
    facility: str
    clustername: str

@strawberry.input
class StorageDailyUsageInput:
    allocationid: Optional[MongoId] = UNSET
    date: Optional[datetime] = UNSET
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class StorageDailyUsage(StorageDailyUsageInput):
    pass
