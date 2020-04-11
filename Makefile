.PHONY: default help debug run test deploy deploy-dry-run venv requirements install install-dev check-coding-style generate-sri-hashes clean full-clean

PYTHONPATH := .
VENV := .venv
PYLINT := env PYTHONPATH=$(PYTHONPATH) $(VENV)/bin/pylint
PYTHON := env PYTHONPATH=$(PYTHONPATH) $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTHON_MODULES := $(shell echo *.py $$(find . -path ./$(VENV) -prune -o -name '__init__.py' -printf '%h\n'))

DEFAULT_PYTHON := /usr/bin/python3
VIRTUALENV := /usr/bin/virtualenv

REQUIREMENTS := -r requirements.txt
SECRET_KEY=$(shell $(DEFAULT_PYTHON) -c 'import secrets; print(secrets.token_hex(16))')

default: generate-sri-hashes check-coding-style		##- Generate SRI hashes and enforce a coding standard.

help:			##- Show this help.
	@sed -e '/#\{2\}-/!d; s/\\$$//; s/:[^#\t]*/:/; s/#\{2\}- *//' $(MAKEFILE_LIST)

debug: install			##- Run debug server with a temporary in-memory database.
	env DEBUG=1 SKIP_DATABASE_CONNECTION=1 SECRET_KEY=$(SECRET_KEY) $(PYTHON) main.py

run: install			##- Run server with Firebase database. GOOGLE_APPLICATION_CREDENTIALS and PROJECT_ID have to be set.
	$(PYTHON) -OO main.py

test:			##- TODO: pytest
	@echo "TODO: Add pytest here"

deploy:			##- Deploy to Google App Engine.
	gcloud app deploy

deploy-dry-run:		##- List files that would be uploaded to App Engine.
	gcloud meta list-files-for-upload

venv:
	test -d $(VENV) || $(VIRTUALENV) -p $(DEFAULT_PYTHON) -q $(VENV)

requirements:
	$(PIP) install --upgrade -q $(REQUIREMENTS)

install: venv requirements		##- Install dependecies.

install-dev: REQUIREMENTS += -r requirements-dev.txt		##- Install development dependencies.
install-dev: venv requirements

check-coding-style: install-dev	##- Try to enforce a coding standard.
	$(PYLINT) $(PYTHON_MODULES)

generate-sri-hashes:	##- Generate Subresource Integrity hashes for stylesheets and scripts.
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

clean:			##- Clean byte-compiled / optimized / DLL files.
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d | xargs rm -fr

full-clean: clean		##- Same as clean, but in addiion remove virtualenv.
	rm -rf $(VENV)
