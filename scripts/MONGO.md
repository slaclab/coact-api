# useful mongo database manipulation examples

## connect to mongo instance

```
keti mongo-rs0-0 -- mongo -u $(kubectl get secret mongo -o jsonpath="{.data.COACT_USER}" | base64 -d) -p $(kubectl get secret mongo -o jsonpath="{.data.COACT_PASSWORD}" | base64 -d)
> use iris
```

## delete a user
db.users.remove( { "username": "pav" } );
db.requests.remove( { "reqtype": "UserAccount", "eppn": "pav@slac.stanford.edu" } );

## clear request from database (no history)


## modify resources for a facility

## LDAP-synced posix fields on users

`users.gidnumber`, `users.secondarygids` and `users.ldapsyncedat` mirror LDAP (primary gid from AD, secondary
gids from SDF LDAP posixGroup membership). They are written only by the `usersPosixSync` mutation (bulk
snapshot pushed by `user-lookup/sync_posix.py`) and `userPosixRefresh` (single user, called by coactd after it
changes LDAP). They are deliberately not on `UserInput`, so `userUpsert`/`userUpdate` never touch them. Do not
edit them by hand; re-run the sync instead. `uidnumber` is owned by coactd provisioning and is only *reported*
by the sync when it disagrees with LDAP.

```
// users never synced (expected: bots / accounts not in LDAP)
db.users.find({ ldapsyncedat: { $exists: false } }, { username: 1, isbot: 1 })
// last sync outcome
db.sync_status.findOne({ _id: "posix_ldap" })
```

## 
