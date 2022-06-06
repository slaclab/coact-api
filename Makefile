DOCKER ?= docker
REPO ?= slaclab
IMAGE ?= coact
TAG ?= latest

MONGOD ?= /usr/local/Cellar/mongodb-community@4.4/4.4.13/bin/mongod
WORK_DIR ?= new-iris

build:
	$(DOCKER) build . -f Dockerfile -t $(REPO)/$(IMAGE):$(TAG)

push: build
	$(DOCKER) push $(REPO)/$(IMAGE):$(TAG)

apply:
	cd kubernetes/overlays/dev/ && make apply


make-venv:
	virtualenv $(WORK_DIR)
	$(WORK_DIR)/bin/pip install -r new-iris/requirements.txt

start-mongod:
	mkdir -p mongodb && $(MONGOD) --config mongod.conf
	
start-app:
	./bin/uvicorn main:app  --reload