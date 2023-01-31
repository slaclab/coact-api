from os import environ
import re
import json
from datetime import datetime

from functools import wraps
from typing import List, Optional
from enum import Enum

from fastapi import FastAPI, Depends, Request, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry import Schema
from strawberry.schema.config import StrawberryConfig
from strawberry.arguments import UNSET

from pymongo import MongoClient
from bson import ObjectId

from models import User, AccessGroup, Repo, Facility, Cluster, CoactRequest, CoactRequestStatus, AuditTrail, AuditTrailObjectType
from schema import Query, Mutation, Subscription, start_change_stream_queues

import smtplib
#import aiosmtplib #
from email.message import EmailMessage
import jinja2
import os
import inspect

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

EMAIL_SERVER_HOST = os.getenv( 'COACT_EMAIL_SERVER_HOST', 'smtp.slac.stanford.edu' )
EMAIL_SERVER_PORT = os.getenv( 'COACT_EMAIL_SERVER_PORT', 25 )


class CustomContext(BaseContext):

    LOG = logging.getLogger(__name__)

    username: str = None
    fullname: str = None
    origin_username: str = None
    is_admin: bool = False
    is_impersonating: bool = False
    showallforczars: bool = False

    def __init__(self, *args, **kwargs):
        self.db = DB(mongo,DB_NAME)
        self.email = Email(EMAIL_SERVER_HOST, EMAIL_SERVER_PORT)

    def __str__(self):
        return f"CustomContext User: {self.username} is_admin {self.is_admin}"

    def isUserRegistered(self, **kwargs):
        eppn = None
        if bool(environ.get('PREFER_EPPN',False)):
            eppn = self.request.headers.get(environ.get('EPPN_FIELD',None), None)
            if eppn:
                users = self.db.find_users( { 'eppns': eppn } )
                self.LOG.debug(f"found eppn {eppn} as user {users}")
                self.fullname = self.request.headers.get(environ.get('FULLNAME_FIELD','REMOTE_GECOS'), None)
                return len(users) > 0, eppn

        username = self.request.headers.get(USER_FIELD_IN_HEADER, None)
        if username:
            users = self.db.find_users( { 'username': username } )
            return len(users) > 0, eppn

        return False, None

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
            self.fullname = self.request.headers.get(environ.get('FULLNAME_FIELD','REMOTE_GECOS'), None)
            admins = re.sub( "\s", "", environ.get("ADMIN_USERNAMES",'')).split(',')
            if self.origin_username in admins:
                self.is_admin = True
                self.LOG.warn(f"admin user {self.username} identified")
                if 'coactimp' in self.request.headers and self.request.headers['coactimp'] and self.request.headers['coactimp'] != 'null':
                    user = self.db.find_user( { 'username': self.request.headers['coactimp'] } )
                    self.LOG.warning(f"user {self.username} is impersonating {user.username}")
                    self.username = user.username
                    self.fullname = "N/A (Impersonating)"
                    self.is_admin = False
                    self.is_impersonating = True
            else:
                if 'coactimp' in self.request.headers and self.request.headers['coactimp'] and self.request.headers['coactimp'] != 'null':
                    raise Exception(f"unauthorised attempt by user {self.username} to impersonate {kwargs['impersonate']}")
            self.showallforczars = json.loads(self.request.headers.get("coactshowall", "false"))
            if self.showallforczars:
                facilities = self.db.find_facilities({ 'czars': self.username })
                if not facilities and not self.is_admin:
                    raise Exception(f"Showall is set for user {self.username} who is not an admin  czar")

        return self.username

    def audit(self, type: AuditTrailObjectType, name: str, action: str, actedby=None, actedat=None, details=""):
        if not actedby:
            actedby = self.username
        if not actedat:
            actedat = datetime.utcnow()
        atrail = AuditTrail(type=type, name=name, action=action, actedby=actedby, actedat=actedat, details=details)
        return self.db.create("audit_trail", atrail)

    def notify_raw(self, to: List[str], subject: str, body: str) -> bool:
        email = self.email.create( to=to, subject=subject, body=body )
        return self.email.send( email ) 

    def notify(self,request: CoactRequest) -> bool:
        # lets try to be clever and reduce the amount of code we have to write by determing who called us
        this_frame = inspect.currentframe()
        caller = inspect.getouterframes(this_frame, 2)[1][3]
        request_type = f"{request.reqtype}"
        request_status = f"{CoactRequestStatus(request.approvalstatus).name}"
        template_prefix = f"{request_type}_{request_status}"
        facility = request.facilityname
        czars = self.db.czars( facility )
        czar_emails = self.db.email_for( czars )
        user_email = [ request.eppn, ]
        user = [ request.preferredUserName, ]
        LOG.info(f">>> TEMPLATE: {template_prefix}, FACILITY: {facility}, CZARS: {czars}, CZAR EMAIL: {czar_emails}, USER: {user}, EMAIL: {user_email}")
        return self.email.notify( request_type=request_type, request_status=request_status, data=self.db.to_dict(request), template_prefix=template_prefix, user=user_email, czars=czar_emails )


    def dict_diffs(self, prev, curr):
        """ Difference between two dicts suitable for history. Does not process embedded arrays/dicts """
        def __expand_dict__(d, prefix=""):
            arr = []
            for k, v in d.items():
                if isinstance(v, dict):
                    arr.extend(__expand_dict__(v, prefix + "." + k if prefix else k))
                elif isinstance(v, list):
                    for counter, arrayval in enumerate(v):
                        arr.append((prefix + "." + k + "[" + str(counter) + "]" if prefix else k + "[" + str(counter) + "]", arrayval))
                else:
                    arr.append((prefix + "." + k if prefix else k, v))
            return arr

        prev_dict = self.db.to_dict(prev)
        curr_dict = self.db.to_dict(curr)
        fwd_changes = dict(set(__expand_dict__(curr_dict)) - set(__expand_dict__(prev_dict)))
        bwd_changes = dict(set(__expand_dict__(prev_dict)) - set(__expand_dict__(curr_dict)))
        changed = fwd_changes.keys() & bwd_changes.keys()
        added = fwd_changes.keys() - bwd_changes.keys()
        removed = bwd_changes.keys() - fwd_changes.keys()
        all_changes = [ str(k) + ": " + str(bwd_changes[k]) + " -> " + str(fwd_changes[k]) for k in changed ]
        all_changes.extend([ str(k) + ": N/A -> " + str(fwd_changes[k]) for k in added ])
        all_changes.extend([ str(k) + ": " + str(bwd_changes[k]) + " -> N/A" for k in removed ])
        return "\n".join(all_changes)

    @classmethod
    def ensure_attrs(cls, attrnames, obj, message):
        """
        Make sure the obj has the specied attributes. If not raise an exception.
        """
        for attrname in attrnames:
            if not getattr(obj, attrname):
                raise Exception(message.format(attrname))


class DB:
    LOG = logging.getLogger(__name__)
    KLASSES = {
        'users': User,
        'clusters': Cluster,
        'access_groups': AccessGroup,
        'repos': Repo,
        'facilities': Facility,
        'requests': CoactRequest,
        'audit_trail': AuditTrail,
    }
    def __init__(self, mongo, db_name):
        self._db = mongo
        self.db_name = db_name
    def db(self):
        return self._db[self.db_name]
    def collection(self, collection: str):
        return self._db[self.db_name][collection]

    @classmethod
    def to_dict(cls, obj ):
        d = {}
        if isinstance(obj,dict):
            for k, v in obj.items():
                if not v is UNSET:
                    d[k] = v
            return d
        for k,v in obj.__dict__.items():
            #LOG.warn(f"field {k} is {v} ({type(v)})")
            if v or isinstance(v, list):
                d[k] = v
                if v is UNSET:
                    del d[k]
                # We should permit empty lists; these are perfectly acceptable values and are necessary for the in operator.
                # if isinstance(v,list) and len(v) == 0:
                #     del d[k]
        return d

    @classmethod
    def cursor_to_objlist(cls, cursor, klass, exclude_fields=[]):
        items = []
        for item in cursor:
            LOG.debug(f" found {klass} {item}")
            for x in exclude_fields:
                if x in item:
                    del item[x]
            items.append( klass(**item) )
        return items
    def find(self, thing: str, filter, exclude_fields=[] ):
        search = self.to_dict(filter)
        self.LOG.debug(f"searching for {thing} using {filter} -> {search} (excluding fields {exclude_fields})")
        cursor = self.collection(thing).find(search)
        klass = self.KLASSES[thing]
        return self.cursor_to_objlist(cursor, klass, exclude_fields)
    def assert_one(self, items, filter):
        if len(items) == 0:
            raise AssertionError( f"did not find any matching items using filter {filter}" )
        elif len(items) > 1:
            raise AssertionError( f"found too many items using filter {filter}, only expecting one" )
        return items[0]
    def find_repos(self, filter):
        return self.find("repos", filter, exclude_fields=["access_groups"])
    def find_repo(self, filter):
        return self.assert_one( self.find_repos( filter ), filter )
    def find_users(self, filter):
        return self.find("users", filter)
    def find_clusters(self, filter):
        return self.find("clusters", filter)
    def find_user(self, filter):
        return self.assert_one( self.find_users( filter ), filter )
    def find_facilities(self, filter, exclude_fields: Optional[list[str]]=[] ):
        return self.find("facilities", filter, exclude_fields)
    def find_request(self, filter):
        return self.assert_one(self.find("requests", filter), filter)
    def find_requests(self, filter, exclude_fields: Optional[list[str]]=[] ):
        return self.find("requests", filter, exclude_fields)
    def find_facility(self, filter, exclude_fields: Optional[list[str]]=[] ):
        return self.assert_one( self.find_facilities( filter, exclude_fields ), filter )
    def find_access_groups(self, filter):
        return self.find("access_groups", filter, exclude_fields=["repo"])
    def find_access_group(self, filter):
        return self.assert_one( self.find_access_groups( filter ), filter )
    def find_audit_trails(self, filter):
        return self.find("audit_trail", filter)

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
        for k, v in vars(data).items():
            if isinstance(v, Enum):
                setattr(data, k, v.name)
        the_thing = klass( **vars(data) )
        self.LOG.info(f"adding {thing} with {data} -> {the_thing}")
        db = self.collection(thing)
        self.LOG.debug(f'checking {thing} does not already exist witih {find_existing}')
        if find_existing and db.find_one( find_existing ):
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

    def remove(self, thing, id):
        db = self.collection(thing)
        print(id)
        db.remove( { '_id': ObjectId(id["_id"]) } )

    def czars(self, facilityname: str) -> List[str]:
        f = self.collection("facilities").find_one({"name": facilityname}, {"_id": 0, "czars": 1})
        return f['czars']

    def email_for( self, username: List[str] ) -> List[str]:
        l = [ { "username": n } for n in username ]
        return [ e['preferredemail'] for e in self.collection('users').find({"$or": l}) ]
        

class Email:
    LOG = logging.getLogger(__name__)
    assets_path=None
    template_extension = '.jinja2'
    def __init__(self, server, port, fm='s3df-help@slac.stanford.edu', subject_prefix='[Coact] ', assets_path='./assets/notifications/email/'):
        self._smtp = smtplib.SMTP(host=server,port=port)
        self.fm = fm
        self.subject_prefix = subject_prefix
        self.assets_path = assets_path
        template_loader = jinja2.FileSystemLoader(searchpath=self.assets_path)
        self.j2 = jinja2.Environment(loader=template_loader)

    def render(self, template_file, params):
        t = self.j2.get_template( template_file )
        self.LOG.debug(f"rendering {template_file} with vars {params}")
        return t.render(**params)
        
    def create(self, to: List[str], subject: str, body: str, cc: List[str] = [], bcc: List[str] = []) -> EmailMessage:
        email = EmailMessage()
        email["From"] = self.fm
        email["To"] = ', '.join(to)
        if len(cc):
            email["Cc"] = ', '.join(cc)
        if len(bcc):
            email["Bcc"] = ', '.join(bcc)
        email["Subject"] = self.subject_prefix + subject
        email.set_content(body)
        return email

    def send(self, email: EmailMessage) -> bool:
        self._smtp.send_message(email)
        return True

    def notify(self, request_type: str, request_status: str, data: dict, template_prefix: str, user: str, czars: List[str] = [] ) -> bool:
        # one request may need to inform multiple parties, so we
        # assume that any files with the prefix template_prefix should be
        # send to the parties in the template file name's suffix
        # get list of files matching
        templates = [ f for f in os.listdir(self.assets_path) if f.startswith(template_prefix) and f.endswith(self.template_extension) ]
        self.LOG.info(f"Found templates {templates}")
        for t in templates:
            to = []
            cc = []
            bcc = []
            email = None
            if t.endswith( '_czar' + self.template_extension ):
                to = czars
            elif t.endswith( '_user' + self.template_extension ):
                to = user
                cc = czars
            elif t.endswith( '_admin' + self.template_extension ):
                to = admins
            body = self.render( t, data ) 
            email = self.create( to, f'{request_type} {request_status}', body, cc=cc, bcc=bcc )
            LOG.debug(f"sending email from template {t}: {email}")
            self.send( email )
        return False
    

def custom_context_dependency() -> CustomContext:
    return CustomContext()

async def get_context(custom_context: CustomContext = Depends(custom_context_dependency),):
    return custom_context

start_change_stream_queues(mongo[DB_NAME])

# normal graphql api
schema = Schema(query=Query, mutation=Mutation, config=StrawberryConfig(auto_camel_case=True))
graphql_app = GraphQLRouter(
  schema,
  context_getter=get_context,
)

# duplicate api at different endpoint for service accounts
service_schema = Schema(query=Query, mutation=Mutation, subscription=Subscription, config=StrawberryConfig(auto_camel_case=True))
graphql_service_app = GraphQLRouter(
  service_schema,
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
app.include_router(graphql_service_app, prefix="/graphql-service")
