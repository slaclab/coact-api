import logging
import re
from typing import Iterator

from coact.client.facilities import FacilitiesFacilities
from coact.client.repos import ReposRepos

from .gen.fga_relations import FacilityRelation, PosixGroupRelation, RepoRelation

__all__ = ["FacilityRelation", "RepoRelation", "PosixGroupRelation"]

logger = logging.getLogger(__name__)

_VALID_FGA_ID = re.compile(r"^[^\s]{2,256}$")


def _valid(*parts: str) -> bool:
    """Return True if all OpenFGA id parts match the required pattern."""
    for part in parts:
        if not part or not _VALID_FGA_ID.match(part):
            logger.warning("Skipping tuple: invalid OpenFGA id part %r", part)
            return False
    return True


class Facility(FacilitiesFacilities):
    @classmethod
    def from_coact(cls, data: FacilitiesFacilities) -> "Facility":
        return cls.model_validate(data.model_dump())

    def get_tuples(self) -> Iterator[tuple[str, str, str]]:
        if self.name and self.czars:
            for czar in self.czars:
                if _valid(czar, self.name):
                    yield (f"user:{czar}", FacilityRelation.CZAR, f"facility:{self.name}")


class Repo(ReposRepos):
    @classmethod
    def from_coact(cls, data: ReposRepos) -> "Repo":
        return cls.model_validate(data.model_dump())

    def _facility_member_tuples(self) -> Iterator[tuple[str, str, str]]:
        """For the 'default' repo: map each user as a facility member."""
        if self.users:
            for u in self.users:
                if _valid(u, self.facility):
                    yield (f"user:{u}", FacilityRelation.MEMBER, f"facility:{self.facility}")

    def _repo_tuples(self) -> Iterator[tuple[str, str, str]]:
        """Yield parent, admin, and member tuples for this repo object."""
        if not _valid(self.facility, self.name):
            return
        repo_obj = f"repo:{self.facility}/{self.name}"
        yield (f"facility:{self.facility}", RepoRelation.PARENT_FACILITY, repo_obj)
        if self.principal and _valid(self.principal):
            yield (f"user:{self.principal}", RepoRelation.REPO_ADMIN, repo_obj)
        if self.leaders:
            for leader in self.leaders:
                if _valid(leader):
                    yield (f"user:{leader}", RepoRelation.REPO_ADMIN, repo_obj)
        if self.users:
            for user in self.users:
                if _valid(user):
                    yield (f"user:{user}", RepoRelation.REPO_MEMBER, repo_obj)

    def get_tuples(self) -> Iterator[tuple[str, str, str]]:
        if not self.name or not self.facility:
            return
        if self.name == "default":
            yield from self._facility_member_tuples()
        yield from self._repo_tuples()


class PosixGroup:
    def __init__(self, facility: str, repo_name: str, group_name: str, members: list[str]):
        self.facility = facility
        self.repo_name = repo_name
        self.group_name = group_name
        self.members = members or []

    def get_tuples(self) -> Iterator[tuple[str, str, str]]:
        if not _valid(self.facility, self.repo_name, self.group_name):
            return
        group_obj = f"posix_group:{self.facility}/{self.repo_name}/{self.group_name}"
        repo_obj = f"repo:{self.facility}/{self.repo_name}"
        yield (repo_obj, PosixGroupRelation.PARENT_REPO, group_obj)
        for user in self.members:
            if _valid(user):
                yield (f"user:{user}", PosixGroupRelation.MEMBER, group_obj)
