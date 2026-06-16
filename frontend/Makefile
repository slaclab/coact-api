CONTAINER_RT ?= podman
REPO ?= slaclab/coact-ui
TAG ?= latest


all: build push

build: FORCE
	$(CONTAINER_RT) build . -t $(REPO):$(TAG)

push: build
	$(CONTAINER_RT) push $(REPO):$(TAG)


FORCE: ;
