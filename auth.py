from strawberry.permission import BasePermission

from strawberry.types import Info
from functools import wraps
from typing import Any

import logging

LOG = logging.getLogger(__name__)

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
        username = info.context.authn()
        self.LOG.debug(f"attempting permissions with {type(self).__name__} for user {username} at path {info.path.key} for privilege {kwargs}")
        if username:
            user = info.context.db.find_user({"username": username })
            return True
        return False


class IsRepoPrincipal(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not principal of repo"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        reponame = kwargs['data']['name']
        self.LOG.debug(f"attempting {type(self).__name__} permissions for user {user} at path {info.path.key} for repo {reponame} with {kwargs}")
        if user and repo:
            repo = info.context.db.find_repo( { 'name': reponame })
            assert repo.name == repo
            if repo.principal == user:
                self.LOG.debug(f"  user {user} permitted to modify repo {repo}")
                return True
        return False


class IsRepoLeader(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not leader of repo"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        reponame = kwargs['data']['name']
        self.LOG.debug(f"attempting {type(self).__name__} permissions for user {info.context.user} at path {info.path.key} for repo {reponame} with {kwargs}")
        if user and repo:
            repo = info.context.db.find_repo( { 'name': reponame } )
            assert repo.name == reponame
            if user in repo.leaders:
                self.LOG.debug(f"  user {user} permitted to modify repo {repo}")
                return True
        return False

class IsRepoPrincipalOrLeader(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not principal or leader of repo"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        repo = None
        if 'repo' in kwargs:
            repo = kwargs['repo']['name']
        else:
            repo = kwargs['data']['name']
        self.LOG.debug(f"attempting {type(self).__name__} permissions for user {user} at path {info.path.key} for repo {repo} with {kwargs}")
        if user and repo:
            repos = info.context.db.find( "repos", { "name": repo } )
            if not len(repos) == 1:
                self.LOG.warn(f"  user {user} requesting {info.path.key} for {repo}")
                return False
            assert repos[0].name == repo
            if user in repos[0].leaders or repos[0].principal == user:
                self.LOG.debug(f"  user {user} permitted to modify repo {repo}")
                return True
        return False

class IsAdmin(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not an admin"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        if info.context.is_admin:
            return True
        return False

