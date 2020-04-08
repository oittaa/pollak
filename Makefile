.PHONY: all generate_sri_hashes

all: generate_sri_hashes

generate_sri_hashes:
	for url in $$(grep -v integrity templates/base.html | grep -oP '^\s*<link rel="stylesheet" href="\Khttps[^"]*|^\s*<script src="\Khttps[^"]*'); \
	do \
	sri=$$(curl -s "$$url" | openssl dgst -sha384 -binary | openssl base64 -A); \
		sed -i '/^\s*<\(link\|script\) /s#'$$url'#'$$url'" integrity="sha384-'$$sri'" crossorigin="anonymous#' templates/base.html; \
	done


