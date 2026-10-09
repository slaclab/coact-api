"""
Unit tests for auth.ReadOnlyGuard against a toy schema and a fake context; main.py is not imported.
"""
from types import SimpleNamespace

import pytest
import strawberry
from strawberry.types import Info
from starlette.datastructures import Headers

from auth import ReadOnlyGuard


@strawberry.type
class Query:
    @strawberry.field
    def ping(self) -> int:
        return 1


@strawberry.type
class Mutation:
    @strawberry.mutation
    def write(self, info: Info) -> int:
        info.context.writes.append(1)
        return 1


SCHEMA = strawberry.Schema(query=Query, mutation=Mutation, extensions=[ReadOnlyGuard])
BOTH = "query Q { ping } mutation M { write }"


def outcome(user, document, operation_name=None, eppn=None):
    headers = {"REMOTE_USER": user, **({"x-vouch-user": eppn} if eppn else {})}
    ctx = SimpleNamespace(request=SimpleNamespace(headers=Headers(headers)), writes=[])
    res = SCHEMA.execute_sync(document, context_value=ctx, operation_name=operation_name)
    if res.errors:
        assert not ctx.writes, "resolver ran despite the error"
        return "; ".join(e.message for e in res.errors)
    return "wrote" if ctx.writes else "read"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("USERNAME_FIELD", "REMOTE_USER")
    monkeypatch.setenv("READONLY_USERNAMES", "other-bot, readonly-bot")


@pytest.mark.parametrize("user, document, operation_name, eppn, expected", [
    ("readonly-bot", "mutation { write }", None, None, "read-only account"),
    ("other-bot", "mutation { write }", None, None, "read-only account"),
    ("readonly-bot", "{ ping }", None, None, "read"),
    ("sdf-bot", "mutation { write }", None, None, "wrote"),
    # The guard keys on USERNAME_FIELD alone.
    ("readonly-bot", "mutation { write }", None, "admin@example.com", "read-only account"),
    ("readonly-bot", BOTH, "M", None, "read-only account"),
    ("readonly-bot", BOTH, "Q", None, "read"),
])
def test_readonly_guard(user, document, operation_name, eppn, expected):
    assert outcome(user, document, operation_name, eppn) == expected
