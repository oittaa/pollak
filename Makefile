.PHONY: all generate_sri_hashes

all: generate_sri_hashes

generate_sri_hashes:
	for f in $$(ls templates/*.html); \
	do \
		for url in $$(grep -vP 'integrity|recaptcha' $$f | grep -oP '^\s*<link rel="stylesheet" href="\Khttps[^"]*|^\s*<script src="\Khttps[^"]*'); \
		do \
			sri=$$(curl -s "$$url" | openssl dgst -sha384 -binary | openssl base64 -A); \
			sed -i '/^\s*<\(link\|script\) /s#'$$url'#'$$url'" integrity="sha384-'$$sri'" crossorigin="anonymous#' $$f; \
		done; \
	done


