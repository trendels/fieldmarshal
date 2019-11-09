
test:
	pytest --doctest-glob='*.md' --doctest-modules tests src README*.md

coverage:
	pytest --doctest-modules \
		--cov=src --cov-branch --cov-report=term --cov-report=html src tests

requirements.txt: requirements.in
	pip-compile --output-file $@ $<

init: requirements.txt
	pip install -e .
	pip install --upgrade -r requirements.txt

update-deps:
	pip install --upgrade pip pip-tools
	pip-compile --upgrade --output-file requirements.txt requirements.in

update: update-deps init

.PHONY: test coverage init update-deps update
