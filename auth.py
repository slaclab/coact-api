from strawberry.permission import BasePermission

from strawberry.types import Info
from functools import wraps
from typing import Any

from bson import ObjectId

import logging

LOG = logging.getLogger(__name__)

import models


class IsAuthenticated(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not authenticated"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn(**kwargs)
        self.LOG.debug(f"attempting permissions with {type(self).__name__} for user {user} at path {info.path.key} for privilege {kwargs}")
        if user:
            return True
        return False

class IsValidEPPN(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User does not have a valid EPPN"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        if info.context.isUserBot():
            self.LOG.debug("Bot users dont really have an EPPN")
            return True
        regis, eppn = info.context.isUserRegistered(**kwargs)
        self.LOG.debug(f"attempting permissions with {type(self).__name__} for eppn {eppn} at path {info.path.key} for privilege {kwargs}")
        if eppn:
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


class IsFacilityCzarOrAdmin(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not czar of facility"

    @classmethod
    def isFacilityCzarOrAdmin(cls, facilityname, info):
        user = info.context.authn()
        if info.context.is_admin:
            LOG.debug(f"  user {user} is admin user and is permitted to modify")
            return True
        facility = info.context.db.find_facility( { 'name': facilityname })
        if user in facility.czars:
            LOG.debug(f"  user {user} permitted to modify facility {facilityname}")
            return True
        return False
    
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        if info.context.is_admin:
            self.LOG.debug(f"  user {user} is admin user and is permitted to modify")
            return True
        if 'facility' in kwargs:
            facility = info.context.db.find_facility( { 'name': kwargs['facility']['name'] })
            if user in facility.czars:
                self.LOG.debug(f"  user {user} permitted to modify facility {facility}")
                return True
            else:
                return False
        if 'id' in kwargs:
            therequests = info.context.db.find_requests( { '_id': ObjectId(kwargs['id']) })
            if therequests and therequests[0].facilityname:
                return self.isFacilityCzarOrAdmin(therequests[0].facilityname, info)

        reponame = None
        if 'repo' in kwargs:
            reponame = kwargs['repo']['name']
            facilityname = kwargs['repo']['facility']
        elif 'request' in kwargs:
            reponame = kwargs['request']['reponame']
            facilityname = kwargs['request']['facilityname']
        elif 'id' in kwargs:
            therequests = info.context.db.find_requests( { '_id': kwargs['id'] })
            if therequests:
                reponame = therequests[0]['reponame']
                facilityname = therequests[0]['facilityname']
        else:
            reponame = kwargs['data']['name']
            facilityname = kwargs['data']['facility']
        if not facilityname:
            self.LOG.warn(f"Cannot determine facility name operating on repo {reponame}")
            return False
        facility = info.context.db.find_facility( { 'name': facilityname })
        if user in facility.czars:
            self.LOG.debug(f"  user {user} permitted to modify facility {facility}")
            return True
        return False

class IsRepoPrincipalOrLeader(BasePermission):
    LOG = logging.getLogger(__name__)
    message = "User is not principal or leader of repo"
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        user = info.context.authn()
        if info.context.is_admin:
            return True
        reponame = None
        if 'repo' in kwargs:
            if isinstance(kwargs['repo'], models.RepoInput):
                reponame = kwargs['repo'].name
                facilityname = kwargs['repo'].facility
            else:
                reponame = kwargs['repo']['name']
                facilityname = kwargs['repo']['facility']
        elif 'request' in kwargs:
            reponame = kwargs['request']['reponame']
            facilityname = kwargs['request']['facilityname']
        else:
            reponame = kwargs['data']['name']
            facilityname = kwargs['data']['facility']
        self.LOG.debug(f"attempting {type(self).__name__} permissions for user {user} at path {info.path.key} for repo {reponame} in facility {facilityname} with {kwargs}")
        if user and reponame:
            repo = None
            try:
                repo = info.context.db.find_repo( { "name": reponame, "facility": facilityname } )
                assert repo.name == reponame
            except Exception as e:
                self.LOG.warn(f"{e}")
                return False
            if info.context.is_admin and 'adminOverride' in kwargs and kwargs['adminOverride']:
                return True
            facility = info.context.db.find_facility( { 'name': facilityname })
            if user in facility.czars:
                self.LOG.debug(f"  user {user} permitted to modify facility {facility}")
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
