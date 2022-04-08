from auth import Authnz

import typing
import strawberry
from strawberry.types import Info

from models import Facility, Resource, Role, Repo, Qos, Job

import logging


authn = Authnz()

COLLECTION = "iris"

@strawberry.type
class Query:
    
    LOG = logging.getLogger(__name__)
    
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def roles(self, info: Info) -> typing.List[Role]:
        roles = info.context.db[COLLECTION]["roles"].find()
        return [ Role(**x) for x in roles ]
    
    def role(self, name: str, info: Info) -> Role:
        therole = info.context.db[COLLECTION]["roles"].find_one({"name": name})
        if therole:
            return Role(**therole)
        return None
    
    @strawberry.field
    @authn.authentication_required
    def facilities(self, info: Info) -> typing.List[Facility]:
        facilities = list(info.context.db[COLLECTION]["facilities"].find())
        for facility in facilities:
            del facility["resources"]
        return [ Facility(**x) for x in facilities ]
        
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def facility(self, name: str, info: Info) -> typing.List[Facility]:
        self.LOG.debug(f"Looking for facility {name}")
        return [ Facility(name="LCLS") ]
        
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def repos(self, info: Info) -> typing.List[Repo]:
        repos = list(info.context.db[COLLECTION]["repos"].find({}))
        for repo in repos:
            del repo["roles"]
        return [Repo(**x) for x in repos]
        
    @strawberry.field
    @authn.authentication_required
    @authn.check_repo
    @authn.authorization_required("read")
    def repo(self, name: str, info: Info) -> Repo:
        self.LOG.debug(f"Looking for repo {name}")
        therepo = info.context.db[COLLECTION]["repos"].find_one({"name": name})
        if therepo:
            del therepo["roles"]
            return Repo(**therepo)
        return None
        
    @strawberry.field
    @authn.authentication_required
    @authn.authorization_required("read")
    def qos(self, info: Info) -> typing.List[Qos]:
        qoses = list(info.context.db[COLLECTION]["qos"].find({}))
        return [Qos(**x) for x in qoses]

@strawberry.type
class Mutation:
    
    LOG = logging.getLogger(__name__)

    @strawberry.mutation
    def importJobs(self, jobs: typing.List[Job], info: Info) -> str:
        jbs = [dict(j.__dict__.items()) for j in jobs]
        info.context.db[COLLECTION]["jobs"].insert_many(jbs)
        return "Done"