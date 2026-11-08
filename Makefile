.PHONY: install test lint check gallery gallery-check readme-images readme readme-check sheet release-check autonomy autonomy-status autonomy-off test-autonomy help

PY ?= .venv/bin/python

help:               ## this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install:            ## a venv with the library, its [check] extra and the dev tools
	uv venv -q .venv && uv pip install -q -p $(PY) -e ".[dev]" ruff

test:               ## the tests, with the 85% coverage floor on the checks
	$(PY) -m pytest -q --cov=styles_plot/_checks --cov-fail-under=85

lint:               ## ruff: unused names and likely bugs
	$(PY) -m ruff check styles_plot tests examples --select F,E9,B --ignore B905,B008

gallery:            ## every example for every target into gallery/ (strict), with contact sheets
	$(PY) examples/build_gallery.py --out gallery

gallery-check: gallery  ## build the gallery, then check it as CI does
	for t in post slide readme; do .venv/bin/styles-plot check gallery/$$t --vocab examples/plotstyle.toml || exit 1; done

readme-images:      ## the four README images and their sidecars into examples/figures/readme/, committed
	$(PY) examples/build_gallery.py --out examples/figures --targets readme --only dot_table key sweep methods --no-sheets

readme:             ## the README's generated blocks (the StyleError of examples/strict/refused.py, the starter builder)
	$(PY) docs/readme_blocks.py

readme-check: readme  ## README blocks up to date, images' meaning unchanged, links resolve, images pass check
	git diff --exit-code README.md
	$(PY) docs/readme_blocks.py --check
	.venv/bin/styles-plot check examples/figures/readme --vocab examples/plotstyle.toml

check: lint test gallery-check readme-check  ## everything CI checks

# Claude Code autonomy window (.claude/autonomy/, stdlib only): no permission prompts for a while (e.g. overnight); the
# old limits come back by themselves at the deadline. git push / reset --hard / clean / rm -rf stay denied.
autonomy:           ## no permission prompts until the deadline: make autonomy HOURS=10 (or UNTIL=11:00)
	python3 .claude/autonomy/autonomy.py grant $(if $(HOURS),--hours $(HOURS)) $(if $(UNTIL),--until "$(UNTIL)")

autonomy-status:    ## is a window open, until when, watcher and caffeinate alive
	python3 .claude/autonomy/autonomy.py status

autonomy-off:       ## close the window now (the old limits back)
	python3 .claude/autonomy/autonomy.py revoke

test-autonomy:      ## the autonomy window's own tests
	$(PY) -m pytest -q -p no:cacheprovider .claude/autonomy
