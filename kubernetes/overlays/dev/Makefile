SECRET_PATH ?= secret/tid/coact--dev/mongo

passwords:
	mkdir -p etc/.secrets/
	vault kv get -format=table --field=MONGODB_BACKUP_PASSWORD $(SECRET_PATH) > etc/.secrets/MONGODB_BACKUP_PASSWORD
	vault kv get -format=table --field=MONGODB_CLUSTER_ADMIN_PASSWORD $(SECRET_PATH) > etc/.secrets/MONGODB_CLUSTER_ADMIN_PASSWORD
	vault kv get -format=table --field=MONGODB_CLUSTER_MONITOR_PASSWORD $(SECRET_PATH) > etc/.secrets/MONGODB_CLUSTER_MONITOR_PASSWORD
	vault kv get -format=table --field=MONGODB_USER_ADMIN_PASSWORD $(SECRET_PATH) > etc/.secrets/MONGODB_USER_ADMIN_PASSWORD
	vault kv get -format=table --field=PMM_SERVER_PASSWORD $(SECRET_PATH) > etc/.secrets/PMM_SERVER_PASSWORD
	vault kv get -format=table --field=S3_ACCESS_KEY $(SECRET_PATH) > etc/.secrets/S3_ACCESS_KEY
	vault kv get -format=table --field=S3_SECRET_KEY $(SECRET_PATH) > etc/.secrets/S3_SECRET_KEY
	vault kv get -format=table --field=COACT_USER $(SECRET_PATH) > etc/.secrets/COACT_USER
	vault kv get -format=table --field=COACT_PASSWORD $(SECRET_PATH) > etc/.secrets/COACT_PASSWORD

clear-passwords:
	rm -rf etc/.secrets/

kustomize: 
	kubectl apply -k .

apply: passwords kustomize clear-passwords

bootstrap:
	

