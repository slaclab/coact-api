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
2. [Cluster-Level Job Submission](#2-cluster-level-job-submission)
3. [Non-Preemptable Job Denied (No Facility Purchases)](#3-non-preemptable-job-denied-no-facility-purchases)
4. [Preemptable Job Always Allowed (No Purchases Needed)](#4-preemptable-job-always-allowed-no-purchases-needed)
5. [POSIX Group Membership via Feature](#5-posix-group-membership-via-feature)
6. [Net Group Membership via Feature](#6-net-group-membership-via-feature)
7. [Feature Toggle (Enable / Disable)](#7-feature-toggle-enable--disable)
8. [Repo Compute Allocation Edit](#8-repo-compute-allocation-edit)
9. [Repo Storage Allocation Edit](#9-repo-storage-allocation-edit)
10. [User Storage Allocation View](#10-user-storage-allocation-view)
11. [Request Approval](#11-request-approval)
12. [Request Visibility](#12-request-visibility)
13. [Facility Membership (Derived)](#13-facility-membership-derived)
14. [Access Group Edit](#14-access-group-edit)
15. [Repo Rename](#15-repo-rename)
16. [Audit Trail Visibility](#16-audit-trail-visibility)
17. [Server Login via Net Group](#17-server-login-via-net-group)
18. [Server Login Denied (Netgroup Not in access.conf)](#18-server-login-denied-netgroup-not-in-accessconf)

---

## 1. Slurm Job Submission (Full Chain)

**Question:** Can `member_dave` submit a `normal` (non-preemptable) job to partition `roma` via account `slac:default`, given that facility `slac` has purchased nodes on cluster `roma`?

**Check:** `user:member_dave` → `can_submit` → `slurm_job:slac:default|roma|normal`

This is the longest Slurm chain and traces every hop from user identity through
repo membership, feature gate, account membership, and finally the QoS purchase
gate.

```
user:member_dave
  │
  │  tuple: user:member_dave | user_member | repo:slac/default
  ▼
repo:slac/default → member = user_member or leader or principal
  │                           ───────────
  │                           member_dave matches user_member ✓
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
  │
  │  tuple: slurm_account:slac:default | account | slurm_job:slac:default|roma|normal
  ▼
slurm_job:slac:default|roma|normal → account_access = can_submit from account ✓
  │
  │  tuple: user:* | purchase_satisfied | slurm_job:slac:default|roma|normal
  │  (written because facility slac has active compute purchases on cluster roma)
  ▼
slurm_job:slac:default|roma|normal → can_submit = account_access AND purchase_satisfied
  │                                                ──────────────     ──────────────────
  │                                                ✓                  ✓
  ▼
ALLOWED ✓
```

**Required tuples:**
- `user:member_dave | user_member | repo:slac/default`
- `repo:slac/default | repo | feature:slac/default/slurm`
- `user:* | enabled | feature:slac/default/slurm`
- `feature:slac/default/slurm | feature | slurm_account:slac:default`
- `slurm_account:slac:default | account | slurm_job:slac:default|roma|normal`
- `cluster:roma | partition | slurm_job:slac:default|roma|normal`
- `slurm_qos:normal | qos | slurm_job:slac:default|roma|normal`
- `user:* | purchase_satisfied | slurm_job:slac:default|roma|normal`

**Breaks when:**
- `member_dave` is removed from the repo
- The `enabled` tuple is deleted (feature disabled)
- The feature is unlinked from the slurm account
- The `slurm_job` object is deleted (partition removed from account)
- The `purchase_satisfied` tuple is removed (facility purchases expire)

**When to write `purchase_satisfied`:**
This tuple should be written when a `FacilityComputeAllocation` or
`facility_compute_purchases` record exists for this facility + cluster
combination with a current time window (`start ≤ now < end`).

**When to remove `purchase_satisfied`:**
When the facility's compute purchases for this cluster expire or are deleted.
This immediately blocks all non-preemptable job submissions for repos in that
facility on that cluster.

---

## 2. Cluster-Level Job Submission

**Question:** Can `member_dave` submit jobs to the `roma` cluster/partition through *any* account?

**Check:** `user:member_dave` → `can_submit_jobs` → `cluster:roma`

```
user:member_dave
  │
  │  (same chain as §1 above, up to slurm_account)
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

**Key insight:** This check is broader than §1. It resolves to `true` if the
user has `can_submit` on *any* `slurm_account` that has `cluster:roma` as a
`partition`. This is useful for answering "can this user use this cluster at
all?" without specifying which account. Note that this does not check QoS — use
a `slurm_job` check (§1, §3, §4) to verify QoS-level access.

---

## 3. Non-Preemptable Job Denied (No Facility Purchases)

**Question:** Can `member_dave` submit a `normal` job to partition `milano` via account `slac:default`, given that facility `slac` has **not** purchased nodes on cluster `milano`?

**Check:** `user:member_dave` → `can_submit` → `slurm_job:slac:default|milano|normal`

```
user:member_dave
  │
  │  (§1 chain: user → repo → feature → slurm_account)
  ▼
slurm_account:slac:default → can_submit = account_member ✓
  │
  │  tuple: slurm_account:slac:default | account | slurm_job:slac:default|milano|normal
  ▼
slurm_job:slac:default|milano|normal → account_access = can_submit from account ✓
  │
  │  purchase_satisfied = ??? (NO tuple exists — facility has no purchases on milano)
  │                        ✗
  ▼
slurm_job:slac:default|milano|normal → can_submit = account_access AND purchase_satisfied
  │                                                  ✓             AND ✗
  ▼
DENIED ✗
```

**Key insight:** The user passes every check in the chain — they are a repo
member, the Slurm feature is enabled, they have account access — but the final
`AND purchase_satisfied` intersection fails because no one has purchased nodes
on `milano` for this facility.

**The user's options:**
1. Submit as `preemptable` instead (see §4) — always allowed
2. Ask the facility czar to purchase nodes on `milano`

**What would fix it:**
```
fga tuple write user:* purchase_satisfied slurm_job:slac:default|milano|normal
```

This applies equally to `onshift` and `offshift` QoS levels — they also
require purchases.

---

## 4. Preemptable Job Always Allowed (No Purchases Needed)

**Question:** Can `member_dave` submit a `preemptable` job to partition `milano` via account `slac:default`, even though the facility has no purchases on `milano`?

**Check:** `user:member_dave` → `can_submit` → `slurm_job:slac:default|milano|preemptable`

```
user:member_dave
  │
  │  (§1 chain: user → repo → feature → slurm_account)
  ▼
slurm_account:slac:default → can_submit = account_member ✓
  │
  │  tuple: slurm_account:slac:default | account | slurm_job:slac:default|milano|preemptable
  ▼
slurm_job:slac:default|milano|preemptable → account_access = can_submit from account ✓
  │
  │  tuple: user:* | purchase_satisfied | slurm_job:slac:default|milano|preemptable
  │  (gate is ALWAYS open for preemptable — this tuple is never removed)
  ▼
slurm_job:slac:default|milano|preemptable → can_submit = account_access AND purchase_satisfied
  │                                                       ✓             AND ✓
  ▼
ALLOWED ✓
```

**Key insight:** Preemptable jobs use the exact same `can_submit`
definition (`account_access AND purchase_satisfied`) as non-preemptable ones.
The difference is operational: the `purchase_satisfied` tuple on preemptable
`slurm_job` objects is **written once and never removed**, regardless of
whether the facility has purchases. This means:

| QoS | `purchase_satisfied` tuple | Behavior |
|---|---|---|
| `preemptable` | Always present (never deleted) | Always allowed if user has account access |
| `normal` | Present only when facility has purchases | Denied when purchases expire |
| `onshift` | Present only when facility has purchases | Denied when purchases expire |
| `offshift` | Present only when facility has purchases | Denied when purchases expire |

**Comparison of `milano` access for `member_dave`:**

```
slurm_job:slac:default|milano|preemptable → can_submit ✓  (purchase_satisfied always set)
slurm_job:slac:default|milano|normal      → can_submit ✗  (no purchase_satisfied)
slurm_job:slac:default|milano|onshift     → can_submit ✗  (no purchase_satisfied)
slurm_job:slac:default|milano|offshift    → can_submit ✗  (no purchase_satisfied)
```

The user can still use `milano` — but their jobs may be preempted (killed) at
any time to make room for jobs from facilities that have purchased nodes.

---

## 5. POSIX Group Membership via Feature

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

## 6. Net Group Membership via Feature

**Question:** Is `member_dave` a member of net group `slac_default_ng`?

**Check:** `user:member_dave` → `member` → `net_group:slac_default_ng`

```
user:member_dave
  │
  │  (same repo membership + feature chain as §5, but for netGroup feature)
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

The chain is structurally identical to §5 — only the feature name and target
type differ.

---

## 7. Feature Toggle (Enable / Disable)

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

## 8. Repo Compute Allocation Edit

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

## 9. Repo Storage Allocation Edit

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

## 10. User Storage Allocation View

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

## 11. Request Approval

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

## 12. Request Visibility

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

## 13. Facility Membership (Derived)

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

## 14. Access Group Edit

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

## 15. Repo Rename

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

## 16. Audit Trail Visibility

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

## 17. Server Login via Net Group

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

## 18. Server Login Denied (Netgroup Not in access.conf)

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
| User can't submit to a specific partition | `slurm_job` object missing or `partition` tuple not written |
| User can submit preemptable but not normal jobs | `purchase_satisfied` tuple missing on the non-preemptable `slurm_job` object — facility has no compute purchases for that cluster |
| User can submit normal jobs on one cluster but not another | Facility has purchases on one cluster but not the other — `purchase_satisfied` only set on the purchased cluster's `slurm_job` objects |
| User lost non-preemptable access they previously had | Facility's compute purchases expired — `purchase_satisfied` tuples were removed |
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
