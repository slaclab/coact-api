from os import environ
import re

from functools import wraps
from typing import List, Optional

from fastapi import FastAPI, Depends, Request, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry import Schema
from strawberry.schema.config import StrawberryConfig
from strawberry.arguments import UNSET

from pymongo import MongoClient

from schema import Query, Mutation

import logging

logging.basicConfig( level=logging.DEBUG )

LOG = logging.getLogger(__name__)

DB_NAME = environ.get("DB_NAME", "iris")
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
    origin_username: str = None
    is_admin: bool = False

    def __init__(self, *args, **kwargs):
        self.db = DB(mongo,DB_NAME)

    def __str__(self):
        return f"CustomContext User: {self.username} is_admin {self.is_admin}"

    def authn(self, **kwargs):
        if bool(environ.get('PREFER_EPPN',False)):
            eppn = self.request.headers.get(environ.get('EPPN_FIELD',None), None)
            # hack to lookup User collection for username
            if eppn:
                user = self.db.find_user( { 'eppns': eppn } )
                self.LOG.debug(f"found eppn {eppn} as user {user}")
                self.origin_username = user.username

        if not self.origin_username:
            user = self.request.headers.get(USER_FIELD_IN_HEADER, None)
            self.origin_username = self.db.find_user( { 'username': user } ).username

        if self.origin_username:
            self.username = self.origin_username
            admins = re.sub( "\s", "", environ.get("ADMIN_USERNAMES",'')).split(',')
            if self.origin_username in admins:
                self.is_admin = True
                self.LOG.warn(f"admin user {self.username} identified")
                if 'impersonate' in kwargs and kwargs['impersonate']:
                    user = self.db.find_user( { 'username': kwargs['impersonate'] } )
                    self.LOG.warning(f"user {self.username} is impersonating {user.username}")
                    self.username = user.username

        if 'impersonate' in kwargs and kwargs['impersonate'] and self.is_admin == False:
            raise Exception(f"unauthorised attempt by user {self.username} to impersonate {kwargs['impersonate']}")

        return self.username


from models import User, AccessGroup, Repo, Facility, Qos

class DB:
    LOG = logging.getLogger(__name__)
    KLASSES = {
        'users': User,
        'access_groups': AccessGroup,
        'repos': Repo,
        'facilities': Facility,
        "qos": Qos,
    }
    def __init__(self, mongo, db_name):
        self._db = mongo
        self.db_name = db_name
    def db(self):
        return self._db[self.db_name]
    def collection(self, collection: str):
        return self._db[self.db_name][collection]

    def to_dict(self, obj ):
        d = {}
        if isinstance(obj,dict):
            return obj
        for k,v in obj.__dict__.items():
            #LOG.warn(f"field {k} is {v} ({type(v)})")
            if v or isinstance(v, list):
                d[k] = v
                if isinstance(v,list) and len(v) == 0:
                    del d[k]
        return d

    def find(self, thing: str, filter, exclude_fields=[] ):
        search = self.to_dict(filter)
        self.LOG.debug(f"searching for {thing} using {filter} -> {search} (excluding fields {exclude_fields})")
        cursor = self.collection(thing).find(search)
        items = []
        klass = self.KLASSES[thing]
        for item in cursor:
            self.LOG.debug(f" found {klass} {item}")
            for x in exclude_fields:
                if x in item:
                    del item[x]
            items.append( klass(**item) )
        return items
    def assert_one(self, items):
        if len(items) == 0:
            raise AssertionError( f"did not find any matching items" )
        elif len(items) > 1:
            raise AssertionError( f"found too many items, only expecting one" )
        return items[0]
    def find_repos(self, filter):
        return self.find("repos", filter)
    def find_repo(self, filter):
        return self.assert_one( self.find_repos( filter ) )
    def find_users(self, filter):
        return self.find("users", filter)
    def find_user(self, filter):
        return self.assert_one( self.find_users( filter ) )
    def find_facilities(self, filter, exclude_fields: Optional[list[str]]=[] ):
        return self.find("facilities", filter, exclude_fields)
    def find_facility(self, filter, exclude_fields: Optional[list[str]]=[] ):
        return self.assert_one( self.find_facilities( filter, exclude_fields ) )
    def find_qoses(self):
        return self.find("qos", {})
    def find_qos(self, filter):
        return self.assert_one( self.find_qoses( filter ) )
    def find_access_groups(self, filter):
        return self.find("access_groups", filter)
    def find_access_group(self, filter):
        return self.assert_one( self.find_access_groups( filter ) )

    def create( self, thing, data, required_fields=[], find_existing={} ):
        klass = self.KLASSES[thing]
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
        self.LOG.info(f"adding {thing} with {data} -> {the_thing}")
        db = self.collection(thing)
        self.LOG.debug(f'checking {thing} does not already exist witih {find_existing}')
        if db.find_one( find_existing ):
            raise Exception(f"{thing} already exists with {find_existing}!")
        x = db.insert_one( self.to_dict(the_thing) )
        v = vars(data)
        v['_id'] = x.inserted_id
        inserted = klass( **v )
        return inserted

    def update( self, thing, data, required_fields=[ 'Id', ], find_existing={} ):
        klass = self.KLASSES[thing]

        for k,v in find_existing.items():
            if v is UNSET:
                raise Exception(f'unknown value for {k}')

        things = self.find( thing, find_existing )
        # houdl probably assert
        if len(things) == 0:
            raise Exception(f"{thing} not found with {find_existing}")
        elif len(things) > 1:
            raise Exception(f"too many {thing} matched with {find_existing}")

        new = self.to_dict(things[0])
        for k,v in vars(data).items():
            if v:
                new[k] = v
        for r in required_fields:
            if not r in new:
                raise Exception(f'required field {r} not supplied')
        db = self.collection(thing)
        db.update_one( { '_id': new['_id'] }, { "$set": new } )
        item = klass( **new )
        return item


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
