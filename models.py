import typing
import strawberry
from strawberry.types import Info
from typing import NewType

from datetime import datetime
from bson import ObjectId

from db import get_db

import logging

MongoId = strawberry.scalar(
    NewType("MongoId", object),
    serialize = lambda v: str(v),
    parse_value = lambda v: ObjectId(v),
)

@strawberry.type
class User:
    
    LOG = logging.getLogger(__name__)
    
    _id: MongoId
    userid: str
    UID: int

@strawberry.type
class Role:
    
    LOG = logging.getLogger(__name__)
    
    _id: MongoId
    name: str
    privileges: typing.List[str]
    players: typing.List[str]
    playerObjs: typing.List[User]
    
    @strawberry.field
    def playerObjs(self, info) -> typing.List[User]:
        return [ User(**x) for x in list( get_db(info,"users").find({"userid": {"$in": self.players}})) ]

@strawberry.type
class Resource:
    
    LOG = logging.getLogger(__name__)
    
    name: str
    type: str
    partitions: typing.List[str]
    root: str

@strawberry.type
class Facility:
    
    LOG = logging.getLogger(__name__)
    
    _id: MongoId
    name: str
    
    @strawberry.field
    def resources(self, info) -> typing.List[Resource]:
        fac = get_db(info,"facilities").find_one({"_id": self._id })
        return [ Resource(**{"name": k, "type": v["type"], "partitions": v.get("partitions", []), "root": v.get("root", None)}) for k,v in fac.get("resources", {}).items() ]

@strawberry.type
class Repo:
    
    LOG = logging.getLogger(__name__)
    
    _id: MongoId
    name: str
    facilities: typing.List[str]
    leader: str
    group: str
    GID: int
    
    @strawberry.field
    def facilityObjs(self, info) -> typing.List[Facility]:
        facilities = list(get_db(info,"facilities").find({"name": {"$in": self.facilities}}))
        self.LOG.debug(facilities)
        for facility in facilities:
            del facility["resources"]
        return [ Facility(**x) for x in facilities ]
    
    @strawberry.field
    def roleObjs(self, info) -> typing.List[Role]:
        repo = get_db(info,"repos").find_one({"_id": self._id })
        self.LOG.debug("Roles: " + str(repo.get("roles", {})))
        return [ Role(**{ "_id": None, "name": k, "privileges": [], "players": v }) for k,v in repo.get("roles", {}).items() ]


@strawberry.type
class Qos:
    
    LOG = logging.getLogger(__name__)
    
    _id: MongoId
    name: str
    repo: str
    qos: str
    partition: str

@strawberry.input
class Job:
    
    LOG = logging.getLogger(__name__)
    
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