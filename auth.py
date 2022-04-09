from strawberry.permission import BasePermission

from strawberry.types import Info
from functools import wraps
from typing import Any

from models import get_db

import logging

class Authnz():

    LOG = logging.getLogger(__name__)
    
    def authentication_required(self, wrapped_function):
        @wraps(wrapped_function)
        def function_interceptor(*args, **kwargs):
            info = kwargs["info"]
            self.LOG.debug(info.path.key)
            info.context.authn()
            return wrapped_function(*args, **kwargs)
        return function_interceptor
        
    def authorization_required(self, *params):
        if len(params) < 1:
            raise Exception("Application privilege not specified when specifying the authorization")
        priv_name = params[0]
        def wrapper(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                info = kwargs["info"]
                self.LOG.debug("Looking to authorize {info.context.user} for privilege {priv_name} for repo {info.context.repo}")
                return f(*args, **kwargs)
            return wrapped
        return wrapper
        
    def check_repo(self, wrapped_function):
        @wraps(wrapped_function)
        def function_interceptor(*args, **kwargs):
            info = kwargs["info"]
            if info.path.key.startswith("repo"):
                info.context.repo = kwargs["name"]
                self.LOG.debug(f"Setting repo to {info.context.repo}")
            return wrapped_function(*args, **kwargs)
        return function_interceptor


class IsAuthenticated(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not authenticated"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        info.context.authn()
        self.LOG.debug(f"attempting permissions with {type(self).__name__} for user {info.context.user} at path {info.path.key} for privilege {kwargs} for repo {info.context.repo}")
        if info.context.user:
            db = get_db( info.context.db, "repos" )
            search = { "username": info.context.user }
            cursor = db.find( search )
            # why doesn't this find any relevant documents from db?
            self.LOG.debug(f"  searching {db} for {search} -> {db.count_documents(search)}")
            for u in cursor:
                self.LOG.debug(f"  found user {u}")
            return True
        return False
        
        