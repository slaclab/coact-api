OPENAPI_V2_URL := https://raw.githubusercontent.com/openfga/api/main/docs/openapiv2/apidocs.swagger.json
OPENAPI_V2_FILE := apidocs.swagger.json
OPENAPI_V3_FILE := openapi3.json
OUTPUT_FILE := models.py

SCHEMA_FGA := schema/schema.fga
SCHEMA_JSON := schema/schema.json

.PHONY: all generate schema-json clean

all: generate

schema-json:
	@echo "Generating $(SCHEMA_JSON) from $(SCHEMA_FGA)..."
	fga model transform --file $(SCHEMA_FGA) --output-format json > $(SCHEMA_JSON)

generate:
	@echo "Downloading OpenAPI v2 spec..."
	curl -so $(OPENAPI_V2_FILE) $(OPENAPI_V2_URL)
	@echo "Converting to OpenAPI v3..."
	npx -y swagger2openapi $(OPENAPI_V2_FILE) -o $(OPENAPI_V3_FILE)
	@echo "Generating data models..."
	uv run datamodel-codegen
	@echo "Cleaning up temporary JSON files..."
	rm -f $(OPENAPI_V2_FILE) $(OPENAPI_V3_FILE)

clean:
	rm -f $(OPENAPI_V2_FILE) $(OPENAPI_V3_FILE) $(OUTPUT_FILE)
