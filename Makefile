CONTAINER_RT ?= podman
REPO ?= slaclab
IMAGE ?= coact-api
TAG ?= $(shell date +"%Y%m%d-%H%M")
#latest

MONGOD ?= /usr/local/Cellar/mongodb-community@4.4/4.4.13/bin/mongod
WORK_DIR ?= new-iris

all: build push

build: FORCE
	$(CONTAINER_RT) build . -f Dockerfile -t $(REPO)/$(IMAGE):$(TAG)

push: build FORCE
	$(CONTAINER_RT) push $(REPO)/$(IMAGE):$(TAG)

apply:
	cd kubernetes/overlays/dev/ && make apply


make-venv:
	virtualenv $(WORK_DIR)
	$(WORK_DIR)/bin/pip install -r new-iris/requirements.txt

start-mongod:
	mkdir -p mongodb && $(MONGOD) --config mongod.conf
	
start-app:
	./bin/uvicorn main:app  --reload

FORCE: ;
