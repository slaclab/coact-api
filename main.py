from os import environ

from functools import wraps
from typing import List

from fastapi import FastAPI, Depends, Request, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
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
mongo = MongoClient(
        host=MONGODB_URL, tz_aware=True, connect=True,
        username=environ.get("MONGODB_USER", None), 
        password=environ.get("MONGODB_PASSWORD", None) )
LOG.info("connected to %s" % (mongo,))

USER_FIELD_IN_HEADER = environ.get('USERNAME_FIELD','REMOTE_USER')

class CustomContext(BaseContext):

    LOG = logging.getLogger(__name__)

    user: str = None
    roles: List[str] = []
    privileges: List[str] = []

    def __init__(self, *args, **kwargs):
        self.LOG.debug(f"In CustomContext.__init__ {args} {kwargs}")
        self.user = None
        self.roles = []
        self.privileges = []
        self.repo = None
        self.db = mongo

    def __str__(self):
        return f"CustomContext User: {self.user} Roles: {self.roles} Privileges: {self.privileges}"

    def authn(self):
        self.user = self.request.headers.get(USER_FIELD_IN_HEADER, None)
        if not self.user:
            self.user = environ.get("USER")
        self.roles = [ "Admin" ]
        self.privileges = [ "read" ]
        self.LOG.debug( f"context authn {self}")

def custom_context_dependency() -> CustomContext:
    return CustomContext()

async def get_context(custom_context: CustomContext = Depends(custom_context_dependency),):
    return custom_context

schema = Schema(query=Query, mutation=Mutation, config=StrawberryConfig(auto_camel_case=True))
graphql_app = GraphQLRouter(
  schema,
  context_getter=get_context,
)

app = FastAPI()
origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(graphql_app, prefix="/graphql")
