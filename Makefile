DOCKER ?= docker
REPO ?= slaclab
IMAGE ?= coact
TAG ?= latest

build:
	$(DOCKER) build . -f Dockerfile -t $(REPO)/$(IMAGE):$(TAG)

push: build
	$(DOCKER) push $(REPO)/$(IMAGE):$(TAG)

apply:
	cd kubernetes/overlays/dev/ && make apply
