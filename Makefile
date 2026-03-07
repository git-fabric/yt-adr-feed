# yt-adr-feed Makefile
# Targets: build, test, lint, docker, helm

.PHONY: install test lint docker-build docker-push helm-template clean

VERSION ?= 0.1.0
REGISTRY ?= ghcr.io/git-fabric
IMAGE_NAME ?= yt-adr-feed
FULL_IMAGE := $(REGISTRY)/$(IMAGE_NAME):$(VERSION)

# === Development ===

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src/yt_adr_feed --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

# === Docker ===

docker-build:
	docker buildx build --platform linux/amd64 -t $(FULL_IMAGE) .
	@echo "Built: $(FULL_IMAGE)"

docker-push: docker-build
	docker push $(FULL_IMAGE)
	@echo "Pushed: $(FULL_IMAGE)"

docker-run:
	docker run --rm $(FULL_IMAGE) --help

# === Helm ===

helm-template:
	helm template yt-adr-feed helm/yt-adr-feed/ \
		--set image.tag=$(VERSION)

helm-install:
	helm upgrade --install yt-adr-feed helm/yt-adr-feed/ \
		--set image.tag=$(VERSION) \
		--namespace yt-adr-feed \
		--create-namespace

helm-uninstall:
	helm uninstall yt-adr-feed --namespace yt-adr-feed

# === Local run ===

fetch:
	python -m yt_adr_feed --config config/channels.yaml fetch \
		--output-dir /tmp/adr-output \
		--skip-qdrant \
		--skip-git

fetch-dry:
	python -m yt_adr_feed --config config/channels.yaml fetch \
		--dry-run \
		--skip-qdrant \
		--skip-git

# === Clean ===

clean:
	rm -rf /tmp/adr-output /tmp/yt-adr-*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
