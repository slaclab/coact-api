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



class IsFacilityCzar(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not czar of facility"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        facilityname = kwargs['data']['name']
        self.LOG.debug(f"attempting {type(self).__name__} permissions for user {user} at path {info.path.key} for facility {facilityname} with {kwargs}")
        if user and repo:
            facility = info.context.db.find_facility( { 'name': facilityname })
            assert facility.name == facilityname
            if user in facility.czars:
                self.LOG.debug(f"  user {user} permitted to modify facility {facility}")
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

class IsPermittedToModifyRepo(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not authorized to modify repo"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        repo = None
        if 'repo' in kwargs:
            repo = kwargs['repo']['name']
        else:
            repo = kwargs['data']['name']
        self.LOG.debug(f"attempting {type(self).__name__} permissions for user {user} at path {info.path.key} for repo {repo} with {kwargs}")
        if user and repo:
            # check against the repo
            repos = info.context.db.find( "repos", { "name": repo } )
            if not len(repos) == 1:
                self.LOG.warn(f"  user {user} requesting {info.path.key} for {repo}") # raise AssertError instead?
                return False
            assert repos[0].name == repo
            if user in repos[0].leaders or repos[0].principal == user:
                self.LOG.debug(f"  user {user} permitted to modify repo {repo}")
                return True
            # check against the czar, but only if not true
            else:
                facility = info.context.db.find_facility( { 'name': repos[0].facility })
                assert facility.name == repos[0].facility
                if user in facility.czars:
                    self.LOG.debug(f"  user {user} permitted to modify repo {repo} as czar for facility {facility}")
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

