.PHONY: generate-client test

generate-client: ## Regenerate src/coact/gen/ from the running API (requires the API to be up)
	uv run ariadne-codegen

test: ## Run tests
	uv run pytest