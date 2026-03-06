# Coact OpenFGA Authorization Model

This directory contains the [OpenFGA](https://openfga.dev/) authorization model for the Coact API. OpenFGA is a relationship-based access control (ReBAC) system that models permissions as relationships between objects.

## Files

| File | Description |
|---|---|
| `model.fga` | The OpenFGA authorization model definition (DSL v1.1) |
| `tuples.example.yaml` | Example relationship tuples to illustrate how data is written |

## Entity Mapping

The following table maps Coact's Strawberry/GraphQL models (in `models.py`) to OpenFGA types:

| Strawberry Model | OpenFGA Type | Notes |
|---|---|---|
| `User` | `user` | The identity type — referenced by other types, no relations defined on it |
| `Facility` | `facility` | `czars` field → `czar` relation; `serviceaccount` → `serviceaccount` relation |
| `Repo` | `repo` | `principal`, `leaders`, `users` → three distinct relations with a derived `member` union |
| `RepoFeature` | `feature` | Toggleable capability on a repo; `state` → `enabled` relation gate |
| _(external)_ | `slurm_account` | Slurm account named `<facility>:<repo>`, membership derived from `feature` |
| _(external)_ | `slurm_qos` | Slurm QoS level (e.g. `normal`, `preemptable`, `onshift`, `offshift`) |
| _(external)_ | `slurm_submission` | Intersection of a Slurm account, partition, and QoS — `can_submit` requires account access AND `purchase_satisfied` gate |
| `Cluster` | `cluster` | Compute resource that maps directly to a Slurm partition |
| _(external)_ | `posix_group` | POSIX group projected from a `feature` on a repo |
| _(external)_ | `net_group` | Netgroup projected from a `feature` on a repo |
| _(external)_ | `server` | A machine using `/etc/security/access.conf`; login derived from `net_group` membership |
| `AccessGroup` | `access_group` | `members` → `member` relation; linked back to its parent `repo` |
| `RepoComputeAllocation` | `repo_compute_allocation` | Permissions inherited from the parent `repo` |
| `RepoStorageAllocation` | `repo_storage_allocation` | Permissions inherited from the parent `repo` |
| `UserStorage` | `user_storage_allocation` | Owned by a user, managed by the facility czar |
| `CoactRequest` | `request` | Workflow permissions tied to the `facility` czar role |
| `AuditTrail` | `audit_trail` | View-only, scoped to a facility |
| `Notification` | `notification` | Scoped to recipients |

## Relationships

### Facility

```text
facility
  ├── admin            (user)          — global administrators (maps to ADMIN_USERNAMES)
  ├── czar             (user)          — facility managers (from Facility.czars)
  ├── serviceaccount   (user)          — automation / service identity
  ├── member           (user | derived)— explicit members OR derived via repo membership
  └── repo_member      (derived)       — anyone who is a member of any repo in this facility
```

- A **czar** can manage repos, approve requests, and manage compute/storage purchases within their facility.
- An **admin** has all czar permissions plus the ability to manage czars themselves.
- **member** is a union: direct members OR anyone who is a `member` of a `repo` that has this facility as its `facility` relation.

### Repo

```text
repo
  ├── facility         (facility)      — the facility this repo belongs to
  ├── principal        (user)          — the PI / owner of the repo
  ├── leader           (user)          — co-leaders with management rights
  ├── user_member      (user)          — regular repo members
  └── member           (derived)       — union of user_member, leader, and principal
```

- **principal** and **leader** can manage users, allocations, features, and access groups.
- **user_member** can view the repo but cannot make management changes.
- The facility's **czar** inherits management permissions on all repos in that facility via `czar from facility`.

### Feature (Slurm, POSIX Group, Net Group)

```text
feature
  ├── repo             (repo)          — the repo this feature belongs to
  ├── enabled          (user:*)        — gate: present when the feature is active
  └── assignee         (derived)       — repo members AND enabled (intersection)
```

#### How Features Work

Features use an **intersection** pattern to model the enabled/disabled toggle:

1. A `feature` object (e.g. `feature:slac/default/slurm`) is linked to its repo.
2. When the feature's `state` is `true`, a tuple `user:* | enabled | feature:slac/default/slurm` is written. This opens the gate for all users.
3. The `assignee` relation is defined as `member from repo and enabled` — an intersection. This means a user must **both** be a member of the repo **and** the feature must be enabled.
4. When the feature is disabled, the `enabled` tuple is removed. The intersection fails for everyone, so no one has `can_use` even if they are repo members.

### Cluster (Slurm Partition)

```text
cluster
  ├── admin            (user)          — cluster administrators
  ├── allocated_user   (derived)       — users who can submit to slurm accounts on this partition
  ├── can_view         (user, user:*)  — who can see this cluster
  ├── can_edit         (admin)         — who can modify the cluster
  └── can_submit_jobs  (derived)       — allocated_user OR admin
```

A Coact `Cluster` maps directly to a Slurm **partition**. The `allocated_user` relation is derived from any `slurm_account` that has this cluster as a partition — if a user has `can_submit` on a `slurm_account` that lists this cluster as a `partition`, they are an `allocated_user` on the cluster.

### Slurm Account

```text
slurm_account (named <facility>:<repo>)
  ├── feature          (feature)       — the feature that controls access
  ├── facility         (facility)      — the facility scope
  ├── partition        (cluster)       — the cluster(s) / Slurm partition(s) this account can submit to
  └── account_member   (derived)       — whoever can_use the linked feature
```

A Slurm account is linked to one or more **partitions** (clusters) via the `partition` relation. Account membership is derived from the linked feature — when the Slurm feature is enabled on a repo, all repo members become `account_member`.

### Slurm QoS

```text
slurm_qos (named by QoS level, e.g. "normal", "preemptable", "onshift", "offshift")
  ├── admin            (user)          — QoS administrators
  ├── can_view         (user, user:*)  — who can see this QoS level
  └── can_manage       (admin)         — who can modify the QoS
```

QoS levels control job scheduling priority and preemptability:

| QoS | Description | Requires Facility Purchase? |
|---|---|---|
| `preemptable` | Jobs can be killed at any time; lowest priority | No — always available |
| `normal` | Standard priority | Yes |
| `onshift` | Higher priority during shift hours | Yes |
| `offshift` | Lower priority outside shift hours | Yes |

The purchase requirement is enforced at the `slurm_submission` level (see below), not on the `slurm_qos` type itself. The QoS type is a simple reference object.

### Slurm Submission (Account + Partition + QoS)

```text
slurm_submission (named <account>|<partition>|<qos>, e.g. "slac:default|roma|normal")
  ├── account              (slurm_account) — the Slurm account
  ├── partition            (cluster)       — the Slurm partition (cluster)
  ├── qos                  (slurm_qos)     — the QoS level
  ├── account_access       (derived)       — whoever has can_submit on the account
  ├── purchase_satisfied   (user:*)        — gate: open when facility has purchases for the partition
  └── can_submit           (derived)       — account_access AND purchase_satisfied (intersection)
```

The `slurm_submission` type models the intersection of a Slurm account, a specific partition, and a QoS level. It answers the question: **"Can this user submit a job to partition X using account Y at QoS level Z?"**

The `purchase_satisfied` relation acts as a gate:
- **Preemptable QoS:** Always write `user:* | purchase_satisfied` — no purchase is needed, so the gate is always open.
- **Non-preemptable QoS (normal, onshift, offshift):** Only write `user:* | purchase_satisfied` when the facility has active compute purchases for the target cluster. Remove it when purchases expire or don't exist.

This means a facility without node purchases on a cluster can still use that cluster — but only with preemptable jobs.

#### Full Slurm Permission Resolution

The complete chain from user to job submission (non-preemptable) looks like this:

```text
User is member of repo:slac/default
          │
          ▼
feature:slac/default/slurm → assignee = (member from repo) AND (enabled)
          │                                    │                     │
          │                              user is a member?     user:* tuple exists?
          │                                    ✓                     ✓
          ▼
feature:slac/default/slurm → can_use = assignee ✓
          │
          ▼
slurm_account:slac:default → account_member = can_use from feature ✓
          │
          ├─→ slurm_account:slac:default → can_submit = account_member ✓
          │
          ▼
slurm_submission:slac:default|roma|normal → account_access = can_submit from account ✓
          │
          │   purchase_satisfied = user:* tuple exists?
          │                        ✓ (facility has purchased nodes on roma)
          │
          ▼
slurm_submission:slac:default|roma|normal → can_submit = account_access AND purchase_satisfied ✓
```

For a preemptable submission, the chain is the same but `purchase_satisfied` is always present:

```text
slurm_submission:slac:default|milano|preemptable → account_access ✓
          │
          │   purchase_satisfied = user:* (always open for preemptable)
          │                        ✓
          ▼
slurm_submission:slac:default|milano|preemptable → can_submit = account_access AND purchase_satisfied ✓
```

For a non-preemptable submission on a cluster **without** purchases, the check fails:

```text
slurm_submission:slac:default|milano|normal → account_access ✓
          │
          │   purchase_satisfied = (no tuple exists!)
          │                        ✗
          ▼
slurm_submission:slac:default|milano|normal → can_submit = account_access AND purchase_satisfied ✗
                                                                               DENIED — no purchases
```

In plain English:
1. **Is the user a member of the repo?** (e.g. `member_dave` is a `user_member` of `repo:slac/default`)
2. **Is the Slurm feature enabled on the repo?** (the `enabled` tuple exists on `feature:slac/default/slurm`)
3. **Is the Slurm account linked to the partition?** (the `partition` tuple links `cluster:roma` to `slurm_account:slac:default`)
4. **Does the submission object tie the account, partition, and QoS together?** (`slurm_submission:slac:default|roma|normal` links all three)
5. **Is the purchase requirement satisfied?** (For preemptable: always. For non-preemptable: only when the facility has active compute purchases for the cluster)

If any link in the chain is missing — the user isn't in the repo, the feature is disabled, the account doesn't have access to that partition, or the facility hasn't purchased nodes for a non-preemptable QoS — the check returns denied.

#### Disabling Access

There are multiple points where access can be revoked:

| Action | Effect |
|---|---|
| Remove user from repo | User loses `account_member` on all Slurm accounts for that repo |
| Disable the Slurm feature (`state: false`) | Delete the `enabled` tuple → all repo members lose `can_submit` at every QoS level |
| Remove a partition from an account | Delete the `partition` tuple on `slurm_account` and the `slurm_submission` objects → no jobs at any QoS |
| Facility loses compute purchases on a cluster | Delete `purchase_satisfied` on non-preemptable `slurm_submission` objects for that cluster → users can still submit preemptable jobs but not normal/onshift/offshift |
| Facility gains compute purchases on a cluster | Write `user:* \| purchase_satisfied` on the non-preemptable `slurm_submission` objects → normal/onshift/offshift jobs become available |

### POSIX Group

```text
posix_group
  ├── feature          (feature)       — the feature that controls access
  ├── facility         (facility)      — the facility scope
  ├── group_member     (derived)       — whoever can_use the linked feature
  ├── direct_member    (user)          — independently added members (e.g. service accounts)
  └── member           (derived)       — union of group_member and direct_member
```

### Net Group

```text
net_group
  ├── feature          (feature)       — the feature that controls access
  ├── facility         (facility)      — the facility scope
  ├── group_member     (derived)       — whoever can_use the linked feature
  ├── direct_member    (user)          — independently added members
  └── member           (derived)       — union of group_member and direct_member
```

### Server

```text
server
  ├── facility         (facility)      — the facility the server belongs to
  ├── admin            (user)          — server administrators
  ├── allowed_netgroup (net_group)     — netgroups listed in /etc/security/access.conf
  ├── can_login        (derived)       — member of any allowed_netgroup
  ├── can_view         (user, user:*)  — who can see this server
  └── can_manage       (admin, czar)   — admin or facility czar
```

A server represents a physical or virtual machine that uses `/etc/security/access.conf` to control login access. Each server lists one or more `net_group` objects via the `allowed_netgroup` relation — these correspond to the netgroup entries in the server's `access.conf` file.

A user can log in to a server if they are a `member` of **any** `net_group` that is an `allowed_netgroup` on that server. The full chain is:

```text
User is member of repo:slac/default
          │
          ▼
feature:slac/default/netGroup → can_use ✓ (feature enabled + repo member)
          │
          ▼
net_group:slac_default_ng → member = group_member ✓
          │
          │  tuple: net_group:slac_default_ng | allowed_netgroup | server:sdf-login01
          ▼
server:sdf-login01 → can_login = member from allowed_netgroup ✓
```

If a netgroup is removed from a server's `access.conf`, delete the `allowed_netgroup` tuple — all users who were logging in via that netgroup immediately lose access. If a new netgroup is added, write a new tuple.

### Access Group

```text
access_group
  ├── repo             (repo)          — the parent repo
  └── member           (user)          — direct members of this sub-group
```

- View permission is granted to direct members OR anyone who can view the parent repo.
- Edit permission is delegated to whoever has `can_manage_access_groups` on the parent repo.

### Allocations

```text
repo_compute_allocation
  └── repo             (repo)          — the repo this allocation belongs to

repo_storage_allocation
  └── repo             (repo)          — the repo this allocation belongs to

user_storage_allocation
  ├── owner            (user)          — the user who owns this quota
  └── facility         (facility)      — the facility that governs it
```

- Repo allocation permissions are fully inherited from the parent `repo`.
- User storage allocations are viewable by the owner and editable by the facility czar.

### Request (Approval Workflow)

```text
request
  ├── requester        (user)          — who submitted the request
  ├── facility         (facility)      — the facility the request targets
  └── repo             (repo)          — the repo the request targets (if applicable)
```

- The **requester** can always view their own request.
- **Approval**, **rejection**, **completion**, **refire**, and **reopen** are all gated on the facility `czar` role.
- **change_facility** is a separate, explicitly granted permission (admin-level).

### Audit Trail

```text
audit_trail
  └── facility         (facility)      — the facility scope
```

- Only facility czars can view audit trails.

### Notification

```text
notification
  └── recipient        (user)          — who the notification is for
```

## Permissions Summary

### Facility Permissions

| Permission | Granted To |
|---|---|
| `can_view` | `member`, `czar`, `admin` |
| `can_edit` | `czar`, `admin` |
| `can_manage_czars` | `admin` |
| `can_manage_repos` | `czar`, `admin` |
| `can_manage_compute_purchases` | `czar`, `admin` |
| `can_manage_storage_purchases` | `czar`, `admin` |
| `can_approve_requests` | `czar`, `admin` |

### Repo Permissions

| Permission | Granted To |
|---|---|
| `can_view` | `member`, facility `czar` |
| `can_edit` | `principal`, `leader`, facility `czar` |
| `can_manage_users` | `principal`, `leader`, facility `czar` |
| `can_add_user` | `principal`, `leader`, facility `czar` |
| `can_remove_user` | `principal`, `leader`, facility `czar` |
| `can_toggle_role` | `principal`, `leader`, facility `czar` |
| `can_manage_allocations` | `principal`, `leader`, facility `czar` |
| `can_manage_features` | `principal`, `leader`, facility `czar` |
| `can_manage_access_groups` | `principal`, `leader`, facility `czar` |
| `can_change_compute_requirement` | facility `czar` |
| `can_rename` | facility `czar` |

### Feature Permissions

| Permission | Granted To |
|---|---|
| `can_use` | repo `member` (when feature is enabled) |
| `can_view` | anyone who can view the parent repo |
| `can_enable` | anyone who has `can_manage_features` on the repo |
| `can_disable` | anyone who has `can_manage_features` on the repo |

### Cluster Permissions

| Permission | Granted To |
|---|---|
| `can_view` | any user (public) |
| `can_edit` | `admin` |
| `can_submit_jobs` | `allocated_user` (derived from slurm accounts), `admin` |

### Slurm Account Permissions

| Permission | Granted To |
|---|---|
| `can_submit` | `account_member` (derived from feature `can_use`) |
| `can_view` | `account_member`, facility `czar` |
| `can_manage` | facility `czar` |

### Slurm QoS Permissions

| Permission | Granted To |
|---|---|
| `can_view` | any user (public) |
| `can_manage` | `admin` |

### Slurm Submission Permissions

| Permission | Granted To |
|---|---|
| `can_submit` | `account_access` AND `purchase_satisfied` (intersection — user must have account membership and the purchase gate must be open) |

### POSIX Group / Net Group Permissions

| Permission | Granted To |
|---|---|
| `can_view` | `member` (derived + direct), facility `czar` |
| `can_manage` | facility `czar` |

### Server Permissions

| Permission | Granted To |
|---|---|
| `can_login` | Any user who is a `member` of an `allowed_netgroup` on the server |
| `can_view` | Any user (public) |
| `can_manage` | `admin`, facility `czar` |

### Request Permissions

| Permission | Granted To |
|---|---|
| `can_view` | `requester`, anyone who `can_approve`, facility viewers |
| `can_approve` | facility `czar` |
| `can_reject` | facility `czar` (same as `can_approve`) |
| `can_complete` | facility `czar` (same as `can_approve`) |
| `can_refire` | facility `czar` (same as `can_approve`) |
| `can_reopen` | facility `czar` (same as `can_approve`) |
| `can_change_facility` | explicitly granted users |

## Getting Started

### Prerequisites

Install the OpenFGA CLI:

```sh
brew install openfga/tap/fga
```

Or download from [GitHub Releases](https://github.com/openfga/cli/releases).

### Validate the Model

```sh
fga model validate --file schema/model.fga
```

### Run a Local OpenFGA Server (for development)

```sh
docker run -p 8080:8080 -p 3000:3000 openfga/openfga run
```

### Create a Store and Write the Model

```sh
# Create a store
fga store create --name coact

# Write the authorization model
fga model write --file schema/model.fga

# Write example tuples
fga tuple write --file schema/tuples.example.yaml
```

### Check a Permission

```sh
# Can member_dave submit to the slurm account slac:default?
fga query check user:member_dave can_submit slurm_account:slac:default

# Can member_dave submit a normal (non-preemptable) job to roma?
fga query check user:member_dave can_submit slurm_submission:slac:default|roma|normal

# Can member_dave submit a preemptable job to milano (no purchases)?
fga query check user:member_dave can_submit slurm_submission:slac:default|milano|preemptable

# Can member_dave submit a normal job to milano? (should be DENIED — no purchases)
fga query check user:member_dave can_submit slurm_submission:slac:default|milano|normal

# Can member_dave submit jobs on the roma cluster/partition at all?
fga query check user:member_dave can_submit_jobs cluster:roma

# Can member_dave log in to server sdf-login01?
fga query check user:member_dave can_login server:sdf-login01

# Can member_dave use the slurm feature?
fga query check user:member_dave can_use feature:slac/default/slurm

# Can czar_alice manage the posix group?
fga query check user:czar_alice can_manage posix_group:slac_default_grp
```

### Python SDK Integration

Install the SDK:

```sh
pip install openfga-sdk
```

Example check in Python:

```python
from openfga_sdk import ClientConfiguration, OpenFgaClient, ClientCheckRequest

config = ClientConfiguration(
    api_url="http://localhost:8080",
    store_id="<your-store-id>",
    authorization_model_id="<your-model-id>",
)

async with OpenFgaClient(config) as client:
    # Can member_dave submit a normal job to roma? (facility has purchases)
    response = await client.check(ClientCheckRequest(
        user="user:member_dave",
        relation="can_submit",
        object="slurm_submission:slac:default|roma|normal",
    ))
    print(response.allowed)  # True

    # Can member_dave submit a normal job to milano? (no purchases)
    response = await client.check(ClientCheckRequest(
        user="user:member_dave",
        relation="can_submit",
        object="slurm_submission:slac:default|milano|normal",
    ))
    print(response.allowed)  # False — purchase_satisfied not set

    # Can member_dave submit a preemptable job to milano?
    response = await client.check(ClientCheckRequest(
        user="user:member_dave",
        relation="can_submit",
        object="slurm_submission:slac:default|milano|preemptable",
    ))
    print(response.allowed)  # True — preemptable is always allowed
```

### Toggling a Feature

To **enable** a feature (e.g. when `repoAddNewFeature` or `repoUpdateFeature` sets `state: true`):

```sh
fga tuple write user:* enabled feature:slac/default/slurm
```

To **disable** a feature (e.g. when `repoDeleteFeature` or `state: false`):

```sh
fga tuple delete user:* enabled feature:slac/default/slurm
```

When the `enabled` tuple is removed, the intersection in `assignee` fails for all users, immediately revoking access to the linked slurm_account, posix_group, or net_group — and transitively, any `server` whose login depends on those net_groups.

### Managing Facility Compute Purchases (QoS Gating)

When a facility **purchases** nodes on a cluster, open the gate on non-preemptable submission objects:

```sh
# Facility slac just purchased nodes on cluster roma — enable normal QoS
fga tuple write user:* purchase_satisfied slurm_submission:slac:default|roma|normal
fga tuple write user:* purchase_satisfied slurm_submission:slac:default|roma|onshift
fga tuple write user:* purchase_satisfied slurm_submission:slac:default|roma|offshift
```

When a facility's purchases **expire** or are removed:

```sh
# Facility slac no longer has purchases on cluster roma — revoke non-preemptable QoS
fga tuple delete user:* purchase_satisfied slurm_submission:slac:default|roma|normal
fga tuple delete user:* purchase_satisfied slurm_submission:slac:default|roma|onshift
fga tuple delete user:* purchase_satisfied slurm_submission:slac:default|roma|offshift
```

Preemptable submissions are unaffected — their `purchase_satisfied` tuple is never removed.

### Managing Server Access (access.conf)

To **add** a netgroup to a server's `access.conf`:

```sh
fga tuple write net_group:slac_default_ng allowed_netgroup server:sdf-login01
```

To **remove** a netgroup from a server's `access.conf`:

```sh
fga tuple delete net_group:slac_default_ng allowed_netgroup server:sdf-login01
```

When a netgroup is removed from a server, all users who derived `can_login` through that netgroup immediately lose access. If the user is a member of another netgroup that is still listed on the server, they retain access.

### Adding a Partition to a Slurm Account

When a `RepoComputeAllocation` is created linking a repo to a cluster, write the corresponding tuples. You need a `slurm_submission` object for each QoS level:

```sh
# Link the partition to the slurm account
fga tuple write cluster:roma partition slurm_account:slac:default

# Create submission objects for each QoS level
# Preemptable (always open)
fga tuple write slurm_account:slac:default account slurm_submission:slac:default|roma|preemptable
fga tuple write cluster:roma partition slurm_submission:slac:default|roma|preemptable
fga tuple write slurm_qos:preemptable qos slurm_submission:slac:default|roma|preemptable
fga tuple write user:* purchase_satisfied slurm_submission:slac:default|roma|preemptable

# Normal (gated on purchases)
fga tuple write slurm_account:slac:default account slurm_submission:slac:default|roma|normal
fga tuple write cluster:roma partition slurm_submission:slac:default|roma|normal
fga tuple write slurm_qos:normal qos slurm_submission:slac:default|roma|normal
# Only write purchase_satisfied if facility has active purchases on this cluster:
# fga tuple write user:* purchase_satisfied slurm_submission:slac:default|roma|normal
```

### Removing a Partition from a Slurm Account

When a `RepoComputeAllocation` is removed:

```sh
# Remove all submission objects for this account+partition (all QoS levels)
fga tuple delete slurm_account:slac:default account slurm_submission:slac:default|roma|preemptable
fga tuple delete cluster:roma partition slurm_submission:slac:default|roma|preemptable
fga tuple delete slurm_qos:preemptable qos slurm_submission:slac:default|roma|preemptable
fga tuple delete user:* purchase_satisfied slurm_submission:slac:default|roma|preemptable

fga tuple delete slurm_account:slac:default account slurm_submission:slac:default|roma|normal
fga tuple delete cluster:roma partition slurm_submission:slac:default|roma|normal
fga tuple delete slurm_qos:normal qos slurm_submission:slac:default|roma|normal
fga tuple delete user:* purchase_satisfied slurm_submission:slac:default|roma|normal

# Unlink the partition from the account
fga tuple delete cluster:roma partition slurm_account:slac:default
```
