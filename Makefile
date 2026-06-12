export PATH := /opt/homebrew/bin:$(CURDIR)/.venv/bin:$(PATH)

.PHONY: monorepo-init monorepo-list monorepo-status monorepo-doctor monorepo-snapshot test explorer-gen-data explorer-build explorer-dev kilvin-doctor kilvin-real-smoke kilvin-pages-check

monorepo-init:
	./.monorepo/monoctl init

monorepo-list:
	./.monorepo/monoctl list

monorepo-status:
	./.monorepo/monoctl status

monorepo-doctor:
	./.monorepo/monoctl doctor

monorepo-snapshot:
	./.monorepo/monoctl snapshot

test:
	pytest -q

explorer-gen-data:
	./explorer/scripts/workflow.sh gen-data

explorer-build:
	./explorer/scripts/workflow.sh build

explorer-dev:
	./explorer/scripts/workflow.sh dev

kilvin-doctor:
	python3 scripts/kilvin_doctor.py

kilvin-real-smoke:
	python3 scripts/kilvin_real_smoke.py

kilvin-pages-check:
	python3 scripts/kilvin_pages_check.py --url $(or $(PAGES_URL),https://phi9t.github.io/temporalis/data/kilvin/internals.json)
