.PHONY: all generate_sri_hashes generate_secret_key test_server deploy_to_gae test deploy

all: generate_sri_hashes generate_secret_key

test: generate_sri_hashes test_server

deploy: generate_sri_hashes deploy_to_gae

generate_sri_hashes:
	@echo "Generating Subresource Integrity hashes"
	@for f in $$(ls templates/*.html); \
	do \
		for url in $$(grep -vP 'integrity|recaptcha' $$f | grep -oP '^\s*<link rel="stylesheet" href="\Khttps[^"]*|^\s*<script src="\Khttps[^"]*'); \
		do \
			echo "Calculating hash for $$url"; \
			sri=$$(curl -s "$$url" | openssl dgst -sha384 -binary | openssl base64 -A); \
			sed -i '/^\s*<\(link\|script\) /s#'$$url'#'$$url'" integrity="sha384-'$$sri'" crossorigin="anonymous#' $$f; \
		done; \
	done

generate_secret_key:
	@echo "You can use the following as SECRET_KEY"
	@python3 -c 'import secrets; print(secrets.token_hex(16))'

test_server:
	SECRET_KEY=$$(python3 -c 'import secrets; print(secrets.token_hex(16))') python3 main.py

deploy_to_gae:
	gcloud app deploy
