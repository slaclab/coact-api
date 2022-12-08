

## Initiate the coact database

in order to initiate the coact database we must

### get the password
kg secret mongo -o jsonpath="{.data.COACT_PASSWORD}" | base64 -d

### login to mongo database
keti mongo-rs0-0 -- mongo -u $(kubectl get secret mongo -o jsonpath="{.data.MONGODB_USER_ADMIN_USER}" | base64 -d) -p $(kubectl get secret mongo -o jsonpath="{.data.MONGODB_USER_ADMIN_PASSWORD}" | base64 -d)

### create the coact user and password
use admin
db.createUser({ user: "coact", roles: [ { db: "iris", role: "readWrite" } ], pwd: passwordPrompt() });

(exit)

## Populate the database

### create a restore pod and console into it
kubectl apply -f restore.yaml
kubectl exec -it <pod> -c mongo -- sh

### bootstrap the database with base data
mongo $MONGODB_URL -u $MONGODB_USERNAME -p $MONGODB_PASSWORD < ./scripts/bootstrap.mongo

### load the sample data/schema
mongo $MONGODB_URL -u $MONGODB_USERNAME -p $MONGODB_PASSWORD < ./scripts/sample_data_0.mongo
mongo $MONGODB_URL -u $MONGODB_USERNAME -p $MONGODB_PASSWORD < ./scripts/sample_data_1.mongo
mongo $MONGODB_URL -u $MONGODB_USERNAME -p $MONGODB_PASSWORD < ./scripts/run21coactdata.mongo

(exit)

## load fake audit data

### login to coact api pod
kubectl exec -it <pod> -c coact -- sh

### get a token for the uploads (requires user permissions)
goto https://echo-server-vouch.slac.stanford.edu/, and setup a local env variable for the cookie that contains 'slac-vouch='

export VOUCH_COOKIE="H4sIAAAAAAAA_..."


### upload sample fake audit data
./load_sample_job_data.py -c $VOUCH_COOKIE --url https://coact-dev.slac.stanford.edu/graphql 20220614.json
./load_sample_storage_usage_data.py -c $VOUCH_COOKIE --url https://coact-dev.slac.stanford.edu/graphql

(exit)

### clean up restore pod
kdel -f restore.yaml

