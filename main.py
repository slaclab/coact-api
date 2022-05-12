from os import environ
import re

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

    username: str = None
    is_admin: bool = False

    def __init__(self, *args, **kwargs):
        self.db = mongo

    def __str__(self):
        return f"CustomContext User: {self.username} is_admin {self.is_admin}"

    def authn(self):
        if bool(environ.get('PREFER_EPPN',False)):
            eppn = self.request.headers.get(environ.get('EPPN_FIELD',None), None)
            # hack to lookup User collection for username
            if eppn:
                cursor = self.db['iris']['users'].find( { 'eppns': eppn } )
                users = [ u for u in cursor ]
                if len(users) == 1:
                    self.LOG.debug(f"found eppn {eppn} as usr {users[0]['username']}")
                    self.username = users[0]['username']

        if not self.username:
            self.username = self.request.headers.get(USER_FIELD_IN_HEADER, None)

        if self.username:
            admins = re.sub( "\s", "", environ.get("ADMIN_USERNAMES",'')).split(',')
            if self.username in admins:
                self.is_admin = True
                self.LOG.warn(f"admin user {self.username} identified")

        return self.username

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
