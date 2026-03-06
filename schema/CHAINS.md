# Permission Chains Reference

This document provides a developer-friendly reference for understanding how
permissions resolve through the OpenFGA model. Each chain traces the path from
a user to a final permission check, showing every relationship that must exist
for the check to succeed.

Use these chains as a guide when:

- Debugging why a permission check is returning `true` or `false`
- Writing tuple data when new objects are created in Coact
- Understanding which tuples to remove when revoking access
- Adding new chains for future features

---

## Table of Contents

1. [Slurm Job Submission (Full Chain)](#1-slurm-job-submission-full-chain)
2. [Slurm Job Submission to a Specific Partition](#2-slurm-job-submission-to-a-specific-partition)
3. [Cluster-Level Job Submission](#3-cluster-level-job-submission)
4. [POSIX Group Membership via Feature](#4-posix-group-membership-via-feature)
5. [Net Group Membership via Feature](#5-net-group-membership-via-feature)
6. [Feature Toggle (Enable / Disable)](#6-feature-toggle-enable--disable)
7. [Repo Compute Allocation Edit](#7-repo-compute-allocation-edit)
8. [Repo Storage Allocation Edit](#8-repo-storage-allocation-edit)
9. [User Storage Allocation View](#9-user-storage-allocation-view)
10. [Request Approval](#10-request-approval)
11. [Request Visibility](#11-request-visibility)
12. [Facility Membership (Derived)](#12-facility-membership-derived)
13. [Access Group Edit](#13-access-group-edit)
14. [Repo Rename](#14-repo-rename)
15. [Audit Trail Visibility](#15-audit-trail-visibility)
16. [Server Login via Net Group](#16-server-login-via-net-group)
17. [Server Login Denied (Netgroup Not in access.conf)](#17-server-login-denied-netgroup-not-in-accessconf)

---

## 1. Slurm Job Submission (Full Chain)

**Question:** Can `member_dave` submit a job using Slurm account `slac:default`?

**Check:** `user:member_dave` → `can_submit` → `slurm_account:slac:default`

```
user:member_dave
  │
  │  tuple: user:member_dave | user_member | repo:slac/default
  ▼
repo:slac/default → member = user_member or leader or principal
  │                          ─────────────
  │                          member_dave matches user_member ✓
  │
  │  tuple: repo:slac/default | repo | feature:slac/default/slurm
  ▼
feature:slac/default/slurm → assignee = member from repo AND enabled
  │                                      ──────────────     ───────
  │                                      member_dave ✓      ↓
  │
  │  tuple: user:* | enabled | feature:slac/default/slurm
  │                                                   ✓ (gate is open)
  │
  │  assignee = ✓ AND ✓ = ✓
  │  can_use = assignee ✓
  │
  │  tuple: feature:slac/default/slurm | feature | slurm_account:slac:default
  ▼
slurm_account:slac:default → account_member = can_use from feature ✓
  │
  ▼
slurm_account:slac:default → can_submit = account_member ✓
```

**Required tuples:**
- `user:member_dave | user_member | repo:slac/default`
- `repo:slac/default | repo | feature:slac/default/slurm`
- `user:* | enabled | feature:slac/default/slurm`
- `feature:slac/default/slurm | feature | slurm_account:slac:default`

**Breaks when:**
- `member_dave` is removed from the repo
- The `enabled` tuple is deleted (feature disabled)
- The feature is unlinked from the slurm account

---

## 2. Slurm Job Submission to a Specific Partition

**Question:** Can `member_dave` submit a job to partition `roma` via account `slac:default`?

**Check:** `user:member_dave` → `can_submit` → `slurm_submission:slac:default|roma`

```
user:member_dave
  │
  │  (same chain as §1 above)
  ▼
slurm_account:slac:default → can_submit = account_member ✓
  │
  │  tuple: slurm_account:slac:default | account | slurm_submission:slac:default|roma
  ▼
slurm_submission:slac:default|roma → account_access = can_submit from account ✓
  │
  ▼
slurm_submission:slac:default|roma → can_submit = account_access ✓
```

**Additional tuples (beyond §1):**
- `slurm_account:slac:default | account | slurm_submission:slac:default|roma`
- `cluster:roma | partition | slurm_submission:slac:default|roma`

**Breaks when:**
- Any link in §1 breaks (user removed, feature disabled, etc.)
- The `slurm_submission` object is deleted (partition removed from account)

---

## 3. Cluster-Level Job Submission

**Question:** Can `member_dave` submit jobs to the `roma` cluster/partition through *any* account?

**Check:** `user:member_dave` → `can_submit_jobs` → `cluster:roma`

```
user:member_dave
  │
  │  (same chain as §1 above)
  ▼
slurm_account:slac:default → can_submit ✓
  │
  │  tuple: cluster:roma | partition | slurm_account:slac:default
  │  (OpenFGA reverses this: slurm_account has cluster as partition)
  ▼
cluster:roma → allocated_user = can_submit from slurm_account ✓
  │
  ▼
cluster:roma → can_submit_jobs = allocated_user or admin
  │                               ──────────────
  │                               ✓
  ▼
ALLOWED ✓
```

**Key insight:** This check is broader than §2. It resolves to `true` if the
user has `can_submit` on *any* `slurm_account` that has `cluster:roma` as a
`partition`. This is useful for answering "can this user use this cluster at
all?" without specifying which account.

---

## 4. POSIX Group Membership via Feature

**Question:** Is `member_dave` a member of POSIX group `slac_default_grp`?

**Check:** `user:member_dave` → `member` → `posix_group:slac_default_grp`

```
user:member_dave
  │
  │  tuple: user:member_dave | user_member | repo:slac/default
  ▼
repo:slac/default → member ✓
  │
  │  tuple: repo:slac/default | repo | feature:slac/default/posixGroup
  ▼
feature:slac/default/posixGroup → assignee = member from repo AND enabled
  │                                           ──────────────     ───────
  │                                           ✓                  ✓
  │  can_use = assignee ✓
  │
  │  tuple: feature:slac/default/posixGroup | feature | posix_group:slac_default_grp
  ▼
posix_group:slac_default_grp → group_member = can_use from feature ✓
  │
  ▼
posix_group:slac_default_grp → member = group_member or direct_member
  │                                      ────────────
  │                                      ✓
  ▼
ALLOWED ✓
```

**Note:** A service account can also be a `member` via `direct_member` without
going through the feature chain:

```
user:svc_backup
  │
  │  tuple: user:svc_backup | direct_member | posix_group:slac_default_grp
  ▼
posix_group:slac_default_grp → member = group_member or direct_member
  │                                                      ─────────────
  │                                                      ✓
  ▼
ALLOWED ✓
```

---

## 5. Net Group Membership via Feature

**Question:** Is `member_dave` a member of net group `slac_default_ng`?

**Check:** `user:member_dave` → `member` → `net_group:slac_default_ng`

```
user:member_dave
  │
  │  (same repo membership + feature chain as §4, but for netGroup feature)
  ▼
feature:slac/default/netGroup → can_use ✓
  │
  │  tuple: feature:slac/default/netGroup | feature | net_group:slac_default_ng
  ▼
net_group:slac_default_ng → group_member = can_use from feature ✓
  │
  ▼
net_group:slac_default_ng → member = group_member or direct_member ✓
```

The chain is structurally identical to §4 — only the feature name and target
type differ.

---

## 6. Feature Toggle (Enable / Disable)

**Question:** Can `leader_carol` enable or disable the Slurm feature on `repo:slac/default`?

**Check:** `user:leader_carol` → `can_enable` → `feature:slac/default/slurm`

```
user:leader_carol
  │
  │  tuple: user:leader_carol | leader | repo:slac/default
  ▼
repo:slac/default → can_manage_features = principal or leader or czar from facility
  │                                                    ──────
  │                                                    leader_carol ✓
  │
  │  tuple: repo:slac/default | repo | feature:slac/default/slurm
  ▼
feature:slac/default/slurm → can_enable = can_manage_features from repo ✓
```

**Who can toggle features:**

| Role | Resolves via |
|---|---|
| Repo principal | `principal` on `repo` → `can_manage_features` |
| Repo leader | `leader` on `repo` → `can_manage_features` |
| Facility czar | `czar` on `facility` → `czar from facility` on `repo` → `can_manage_features` |

**What happens on toggle:**
- **Enable:** Write tuple `user:* | enabled | feature:slac/default/slurm`
- **Disable:** Delete tuple `user:* | enabled | feature:slac/default/slurm`

All downstream permissions (Slurm accounts, POSIX groups, net groups) are
immediately affected — no other tuples need to change.

---

## 7. Repo Compute Allocation Edit

**Question:** Can `leader_carol` modify compute allocation `alloc_001`?

**Check:** `user:leader_carol` → `can_edit` → `repo_compute_allocation:alloc_001`

```
user:leader_carol
  │
  │  tuple: user:leader_carol | leader | repo:slac/default
  ▼
repo:slac/default → can_manage_allocations = principal or leader or czar from facility
  │                                                       ──────
  │                                                       leader_carol ✓
  │
  │  tuple: repo:slac/default | repo | repo_compute_allocation:alloc_001
  ▼
repo_compute_allocation:alloc_001 → can_edit = can_manage_allocations from repo ✓
```

**A regular member is denied:**

```
user:member_dave
  │
  │  tuple: user:member_dave | user_member | repo:slac/default
  ▼
repo:slac/default → can_manage_allocations = principal or leader or czar from facility
  │                                          user_member is NOT in this list
  ▼
DENIED ✗
```

---

## 8. Repo Storage Allocation Edit

**Question:** Can `czar_alice` modify storage allocation `storage_001`?

**Check:** `user:czar_alice` → `can_edit` → `repo_storage_allocation:storage_001`

```
user:czar_alice
  │
  │  tuple: user:czar_alice | czar | facility:slac
  ▼
facility:slac → czar ✓
  │
  │  tuple: facility:slac | facility | repo:slac/default
  ▼
repo:slac/default → can_manage_allocations = principal or leader or czar from facility
  │                                                                 ──────────────────
  │                                                                 czar_alice ✓
  │
  │  tuple: repo:slac/default | repo | repo_storage_allocation:storage_001
  ▼
repo_storage_allocation:storage_001 → can_edit = can_manage_allocations from repo ✓
```

**Key insight:** This chain demonstrates how a facility czar inherits permissions
on resources two levels deep: `facility` → `repo` → `repo_storage_allocation`.
The czar never needs a direct tuple on the allocation.

---

## 9. User Storage Allocation View

**Question:** Can `member_dave` view his own storage allocation?

**Check:** `user:member_dave` → `can_view` → `user_storage_allocation:dave_home`

```
user:member_dave
  │
  │  tuple: user:member_dave | owner | user_storage_allocation:dave_home
  ▼
user_storage_allocation:dave_home → can_view = owner or czar from facility
  │                                             ─────
  │                                             member_dave ✓
  ▼
ALLOWED ✓
```

**A czar can also view it:**

```
user:czar_alice
  │
  │  tuple: user:czar_alice | czar | facility:slac
  │  tuple: facility:slac | facility | user_storage_allocation:dave_home
  ▼
user_storage_allocation:dave_home → can_view = owner or czar from facility
  │                                                     ──────────────────
  │                                                     czar_alice ✓
  ▼
ALLOWED ✓
```

**Another user cannot:**

```
user:leader_carol
  │
  │  not owner, not czar of linked facility
  ▼
DENIED ✗
```

---

## 10. Request Approval

**Question:** Can `czar_alice` approve request `req_001`?

**Check:** `user:czar_alice` → `can_approve` → `request:req_001`

```
user:czar_alice
  │
  │  tuple: user:czar_alice | czar | facility:slac
  ▼
facility:slac → czar ✓
  │
  │  tuple: facility:slac | facility | request:req_001
  ▼
request:req_001 → can_approve = czar from facility ✓
```

The same chain applies to `can_reject`, `can_complete`, `can_refire`, and
`can_reopen` — they all resolve to `can_approve`:

```
request:req_001 → can_reject  = can_approve ✓
request:req_001 → can_complete = can_approve ✓
request:req_001 → can_refire   = can_approve ✓
request:req_001 → can_reopen   = can_approve ✓
```

**A regular user cannot approve:**

```
user:member_dave
  │
  │  not a czar on any facility linked to req_001
  ▼
request:req_001 → can_approve = czar from facility
  │                              member_dave is not a czar
  ▼
DENIED ✗
```

---

## 11. Request Visibility

**Question:** Can `member_dave` view request `req_001` that he submitted?

**Check:** `user:member_dave` → `can_view` → `request:req_001`

```
user:member_dave
  │
  │  tuple: user:member_dave | requester | request:req_001
  ▼
request:req_001 → can_view = requester or can_approve or can_view from facility
  │                           ─────────
  │                           member_dave ✓
  ▼
ALLOWED ✓
```

There are three paths to viewing a request:

| Path | Who |
|---|---|
| `requester` | The user who submitted the request |
| `can_approve` | Facility czars (who can also approve) |
| `can_view from facility` | Any facility member (broad visibility) |

---

## 12. Facility Membership (Derived)

**Question:** Is `member_dave` a member of facility `slac`?

**Check:** `user:member_dave` → `member` → `facility:slac`

```
user:member_dave
  │
  │  tuple: user:member_dave | user_member | repo:slac/default
  ▼
repo:slac/default → member = user_member or leader or principal
  │                           ───────────
  │                           member_dave ✓
  │
  │  tuple: facility:slac | facility | repo:slac/default
  │  (OpenFGA follows: facility:slac ← facility ← repo:slac/default)
  ▼
facility:slac → repo_member = member from repo ✓
  │
  ▼
facility:slac → member = [user] or repo_member
  │                                 ───────────
  │                                 ✓
  ▼
ALLOWED ✓
```

**Key insight:** Nobody needs to write a direct `member` tuple on the facility.
As soon as a user is added to any repo in the facility, they automatically
become a facility member through the derived `repo_member` relation.

---

## 13. Access Group Edit

**Question:** Can `leader_carol` edit access group `slac/default/mygroup`?

**Check:** `user:leader_carol` → `can_edit` → `access_group:slac/default/mygroup`

```
user:leader_carol
  │
  │  tuple: user:leader_carol | leader | repo:slac/default
  ▼
repo:slac/default → can_manage_access_groups = principal or leader or czar from facility
  │                                                         ──────
  │                                                         leader_carol ✓
  │
  │  tuple: repo:slac/default | repo | access_group:slac/default/mygroup
  ▼
access_group:slac/default/mygroup → can_edit = can_manage_access_groups from repo ✓
```

---

## 14. Repo Rename

**Question:** Can `leader_carol` rename repo `slac/default`?

**Check:** `user:leader_carol` → `can_rename` → `repo:slac/default`

```
user:leader_carol
  │
  │  tuple: user:leader_carol | leader | repo:slac/default
  ▼
repo:slac/default → can_rename = czar from facility
  │                               leader is NOT czar from facility
  ▼
DENIED ✗
```

**Only a facility czar can rename:**

```
user:czar_alice
  │
  │  tuple: user:czar_alice | czar | facility:slac
  │  tuple: facility:slac | facility | repo:slac/default
  ▼
repo:slac/default → can_rename = czar from facility ✓
```

**Key insight:** Renaming is a privileged operation — even repo principals and
leaders cannot do it. Only facility czars have this permission.

---

## 15. Audit Trail Visibility

**Question:** Can `czar_alice` view audit trails for facility `slac`?

**Check:** `user:czar_alice` → `can_view` → `audit_trail:slac_trail`

```
user:czar_alice
  │
  │  tuple: user:czar_alice | czar | facility:slac
  ▼
facility:slac → czar ✓
  │
  │  tuple: facility:slac | facility | audit_trail:slac_trail
  ▼
audit_trail:slac_trail → can_view = czar from facility ✓
```

**A regular member cannot:**

```
user:member_dave
  │
  │  not a czar
  ▼
DENIED ✗
```

---

## 16. Server Login via Net Group

**Question:** Can `member_dave` log in to server `sdf-login01`?

**Check:** `user:member_dave` → `can_login` → `server:sdf-login01`

The server's `/etc/security/access.conf` lists `slac_default_ng` as an allowed
netgroup. `member_dave` is a member of that netgroup through the repo's
`netGroup` feature.

```
user:member_dave
  │
  │  tuple: user:member_dave | user_member | repo:slac/default
  ▼
repo:slac/default → member = user_member or leader or principal
  │                           ───────────
  │                           member_dave ✓
  │
  │  tuple: repo:slac/default | repo | feature:slac/default/netGroup
  ▼
feature:slac/default/netGroup → assignee = member from repo AND enabled
  │                                         ──────────────     ───────
  │                                         ✓                  ✓
  │
  │  tuple: user:* | enabled | feature:slac/default/netGroup
  │
  │  can_use = assignee ✓
  │
  │  tuple: feature:slac/default/netGroup | feature | net_group:slac_default_ng
  ▼
net_group:slac_default_ng → group_member = can_use from feature ✓
  │
  ▼
net_group:slac_default_ng → member = group_member or direct_member
  │                                   ────────────
  │                                   ✓
  │
  │  tuple: net_group:slac_default_ng | allowed_netgroup | server:sdf-login01
  ▼
server:sdf-login01 → can_login = member from allowed_netgroup ✓
  │
  ▼
ALLOWED ✓
```

**Required tuples:**
- `user:member_dave | user_member | repo:slac/default`
- `repo:slac/default | repo | feature:slac/default/netGroup`
- `user:* | enabled | feature:slac/default/netGroup`
- `feature:slac/default/netGroup | feature | net_group:slac_default_ng`
- `net_group:slac_default_ng | allowed_netgroup | server:sdf-login01`

**Breaks when:**
- `member_dave` is removed from the repo
- The `netGroup` feature is disabled (the `enabled` tuple is deleted)
- The netgroup is removed from the server's `access.conf` (the `allowed_netgroup` tuple is deleted)
- The feature is unlinked from the net group

**Key insight:** This is the longest chain in the model — five hops from user to
server. Every link must hold simultaneously. Disabling the feature at the repo
level revokes login access to *all* servers that depend on netgroups derived from
that repo, across every server in the fleet.

---

## 17. Server Login Denied (Netgroup Not in access.conf)

**Question:** Can `member_dave` log in to server `sdf-gpu01` if its `access.conf` doesn't list his netgroup?

**Check:** `user:member_dave` → `can_login` → `server:sdf-gpu01`

```
user:member_dave
  │
  │  member_dave is a member of net_group:slac_default_ng ✓
  │  (via the full feature chain)
  │
  │  But server:sdf-gpu01 has NO allowed_netgroup tuple for slac_default_ng
  ▼
server:sdf-gpu01 → can_login = member from allowed_netgroup
  │                             ────────────────────────────
  │                             no allowed_netgroup matches member_dave
  ▼
DENIED ✗
```

**Key insight:** Even though the user is a valid member of a netgroup, that
netgroup must be explicitly listed in the server's `allowed_netgroup` relation
(mirroring the actual `/etc/security/access.conf` file). Access is
**server-specific**, not global.

**To grant access**, add the netgroup to the server:

```
tuple: net_group:slac_default_ng | allowed_netgroup | server:sdf-gpu01
```

**Multiple netgroups on a server:** A server can list many netgroups. A user
only needs to be a member of *one* of them to log in:

```
server:sdf-gpu01
  ├── allowed_netgroup: net_group:slac_default_ng
  ├── allowed_netgroup: net_group:slac_ml_ng
  └── allowed_netgroup: net_group:slac_gpu_ng
      │
      ▼
  can_login = member from allowed_netgroup
              (user is a member of ANY of these → ALLOWED)
```

---

## Quick Reference: Denial Patterns

When debugging a denied check, look for these common causes:

| Symptom | Likely Cause |
|---|---|
| User can't submit Slurm jobs | Feature `enabled` tuple missing (feature disabled) |
| User can't submit to a specific partition | `slurm_submission` object missing or `partition` tuple not written |
| User can't edit allocations | User is `user_member`, not `leader` or `principal` |
| User can't approve requests | User is not a `czar` on the request's facility |
| User can't rename a repo | User is not a facility `czar` (even principals can't rename) |
| User not showing as facility member | User not in any repo under that facility |
| User can't view audit trails | User is not a facility `czar` |
| POSIX/net group membership missing | Feature `enabled` tuple deleted, or user removed from repo |
| User can't log in to a server | Netgroup not in server's `allowed_netgroup`, or netGroup feature disabled, or user not in repo |
| User can log in to one server but not another | The netgroup is in one server's `access.conf` but not the other |

---

## Adding New Chains

When adding new features to the OpenFGA model, document the permission chain
here following this template:

```
## N. <Title>

**Question:** Can `<user>` do `<action>` on `<object>`?

**Check:** `user:<user>` → `<relation>` → `<type>:<object>`

    user:<user>
      │
      │  tuple: <subject> | <relation> | <object>
      ▼
    <type>:<object> → <relation> = <definition>
      │
      ▼
    ALLOWED ✓ / DENIED ✗

**Required tuples:**
- ...

**Breaks when:**
- ...
```
