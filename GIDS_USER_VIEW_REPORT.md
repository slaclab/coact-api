# Exposing User → gidNumbers consistent with Repo posixgroup features

## Problem

A user's POSIX gids (`gidNumber`s) are needed as a first-class view on the `User`
model. The authoritative gid lives **nested inside each `Repo`** under the
`posixgroup` feature:

```
repos.features.posixgroup = {
  "state": true,
  "options": [ "{\"name\": \"sdf-cryoem-ct123\", \"gidNumber\": 5001}" ]   // JSON strings
}
```

CoactRequests change a repo's membership list; `sdf-cli` (the `modules/coactd.py`
daemon) applies those changes and is also what *writes* the gid into the repo
feature after provisioning the group via Grouper.

Before this change there were **two parallel representations** of posix groups,
which is the source of the consistency risk:

| Representation | Holds the real gid? | Written by | Read by |
| --- | --- | --- | --- |
| `repos.features.posixgroup.options` | **Yes** (source of truth) | `sdf-cli` → `repoUpsertFeature` | `Repo.features`, `User.accessGroupObjs` |
| `access_groups` collection | Usually **no** (`accessGroupCreate` deliberately leaves `gidnumber` UNSET for LDAP introspection) | `accessGroupCreate` mutation | `Query.access_groups`, `Repo.accessGroupObjs`, `User.groups` (names only) |

## Design

Two complementary pieces keep the new `User` view consistent with the repo feature:

1. **Read view derived from the source of truth.** `User.gidNumbers` is computed
   from the *same* scan as `User.accessGroupObjs` — the `posixgroup` feature
   options of every repo the user belongs to (`users` ∪ `leaders` ∪ `principal`).
   Because both fields share one private helper (`User._posixGroupsForUser`),
   `gidNumbers` is, by construction, the deduplicated/sorted gid projection of what
   `Repo.features` exposes. No denormalized cache, no drift.

2. **Reconcile the `access_groups` projection.** So the other read paths
   (`Query.access_groups`, `Repo.accessGroupObjs`) also agree, `sdf-cli` now pushes
   the provisioned gid into the `access_groups` collection via a new
   `accessGroupUpsert` mutation whenever it writes the gid into the repo feature or
   applies a membership change.

Chosen semantics:
- Output shape: plain `List[int]` (deduped, ascending).
- Membership scope: `users` + `leaders` + `principal`.
- Disabled groups (`state == false`) are **included** (the gid still exists).

## Changes

### `coact-api/models.py` — `User`
- Added private `_posixGroupsForUser(info)` helper holding the repo-feature scan
  (factored out of the existing `accessGroupObjs`, behavior unchanged).
- `accessGroupObjs` now delegates to the helper.
- New field **`gidNumbers(info) -> List[int]`**: `sorted({ g.gidnumber for g in
  self._posixGroupsForUser(info) if g.gidnumber is not None })`.
- Exposed automatically through existing `user` / `users` / `whoami` queries.

### `coact-api/schema.py` — `Mutation`
- New **`accessGroupUpsert(repo, accessgroup)`** (`[IsAuthenticated, IsAdmin]`,
  matching `repoUpsertFeature`). Resolves the repo, then upserts the access group by
  `(repoid, name)` setting `gidnumber` + `members`, and audits as
  `accessGroupUpsert`. This is the reconcile write-path for automation.

### `sdf-cli/modules/coactd.py` — `Registration`
- New helper **`reconcile_access_group(facility, repo, group_name, gid_number,
  members, dry_run)`** executing the `accessGroupUpsert` mutation (best-effort; logs
  and continues on failure; honors `dry_run`).
- Called in **`do_new_repo`** right after the `posixgroup` feature is written.
- Called in **`do_repo_membership`** right after the `posixGroup.yaml` playbook,
  with the **effective** roster (pre-change `this['users']` adjusted by the current
  `present`/`absent` action so the reconciled members match post-request state).

### Tests
- `coact-api/tests/unit/test_user_gidnumbers.py`: dedupe across
  user/leader/principal memberships, plain-int output, multi-option features,
  inclusion of disabled groups, skipping options without a gid, empty case, and an
  explicit consistency assertion that `gidNumbers == sorted(set(accessGroupObjs
  gids))`.

## Consistency guarantees

- `User.gidNumbers` ⟺ `Repo.features.posixgroup`: same source, derived per-request —
  always consistent, no migration required.
- `access_groups` collection ⟶ kept in lockstep by `sdf-cli` on repo creation and on
  every membership change.

## Follow-ups (out of scope)

- Optional one-off migration to backfill `gidnumber` into pre-existing
  `access_groups` documents from current repo features.
- Integration test (`tests/integration/test_queries.py`) asserting
  `user { gidNumbers }` ⊆ union of `repo { features }` gids requires adding
  `gidNumbers` to the generated client (`client/queries/operations.graphql`) and a
  live server; left as a follow-up.
