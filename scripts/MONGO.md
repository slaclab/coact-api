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

## 
