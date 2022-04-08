from os import environ

from functools import wraps

from fastapi import FastAPI, Depends, Request, WebSocket, BackgroundTasks
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry import Schema
from strawberry.schema.config import StrawberryConfig

from pymongo import MongoClient

from auth import Authnz
from schema import Query, Mutation

import logging

logging.basicConfig( level=logging.DEBUG )

LOG = logging.getLogger(__name__)

authn = Authnz()
MONGODB_URL=environ.get("MONGODB_URL", "mongodb://127.0.0.1:27017/")
if not MONGODB_URL:
    print("Please use the enivironment variable MONGODB_URL to configure the database connection.")
mongo = MongoClient(host=MONGODB_URL, tz_aware=True)


class CustomContext(BaseContext):
    
    LOG = logging.getLogger(__name__)
    
    def __init__(self, *args, **kwargs):
        self.LOG.debug("In CustomContext __init__")
        self.user = None
        self.roles = []
        self.privileges = []
        self.repo = None
        self.db = mongo
        
    def __str__(self):
        return f"User: {self.user} Roles: {self.roles} Privileges: {self.privileges}"
        
    def authn(self):
        self.user = self.request.headers.get("REMOTE-USER", self.request.headers.get("remote_user", None))
        self.roles = [ "Admin" ]
        self.privileges = [ "read" ]
        self.LOG.debug(self)

def custom_context_dependency() -> CustomContext:
    LOG.debug("In custom_context_dependency")
    return CustomContext()

async def get_context(custom_context: CustomContext = Depends(custom_context_dependency),):
    LOG.debug("In get_context")
    return custom_context

schema = Schema(query=Query, mutation=Mutation, config=StrawberryConfig(auto_camel_case=False))
graphql_app = GraphQLRouter(
  schema,
  context_getter=get_context,
)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")