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
| `AccessGroup` | `access_group` | `members` → `member` relation; linked back to its parent `repo` |
| `Cluster` | `cluster` | Standalone compute resource |
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
# Can czar_alice view repo slac/default?
fga query check user:czar_alice can_view repo:slac/default

# Can member_dave approve request req_001?
fga query check user:member_dave can_approve request:req_001
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
    response = await client.check(ClientCheckRequest(
        user="user:czar_alice",
        relation="can_approve",
        object="request:req_001",
    ))
    print(response.allowed)  # True
```
