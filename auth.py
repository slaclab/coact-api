from strawberry.permission import BasePermission

from strawberry.types import Info
from functools import wraps
from typing import Any

import logging

LOG = logging.getLogger(__name__)

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
        reponame = None
        if 'repo' in kwargs:
            reponame = kwargs['repo']['name']
        else:
            reponame = kwargs['data']['name']
        self.LOG.debug(f"attempting {type(self).__name__} permissions for user {user} at path {info.path.key} for repo {reponame} with {kwargs}")
        if user and reponame:
            repo = None
            try:
                repo = info.context.db.find_repo( { "name": reponame } )
                assert repo.name == reponame
            except Exception as e:
                self.LOG.warn(f"{e}")
                return False
            if info.context.is_admin and 'adminOverride' in kwargs and kwargs['adminOverride']:
                return True
            if user in repo.leaders or repo.principal == user:
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

