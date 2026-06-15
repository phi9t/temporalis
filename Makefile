export PATH := /opt/homebrew/bin:$(CURDIR)/.venv/bin:$(PATH)

.PHONY: monorepo-init monorepo-list monorepo-status monorepo-doctor monorepo-snapshot test explorer-gen-data explorer-build explorer-dev kilvin-doctor kilvin-up kilvin-down kilvin-clean kilvin-real-smoke kilvin-pages-check quickstart quickstart-check verify-release runtime-proof

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

kilvin-up:
	cd kilvin-py && ./infra/up.sh

kilvin-down:
	cd kilvin-py && ./infra/down.sh

kilvin-clean:
	python3 scripts/kilvin_clean.py $(KILVIN_CLEAN_ARGS)

kilvin-real-smoke:
	python3 scripts/kilvin_real_smoke.py

kilvin-pages-check:
	python3 scripts/kilvin_pages_check.py --url $(or $(PAGES_URL),https://phi9t.github.io/temporalis/data/kilvin/internals.json)

quickstart-check:
	python3 scripts/quickstart_check.py

quickstart: quickstart-check
	@printf '\nTemporalis quickstart is verified.\n'
	@printf 'Start the local explorer with:\n  make explorer-dev\n\n'
	@printf 'Hosted explorer:\n  https://phi9t.github.io/temporalis/\n'

verify-release:
	./.monorepo/monoctl doctor
	./explorer/scripts/workflow.sh gen-data
	PYTHONPATH=. pytest -q tests/explorer/test_lifecycle_data.py tests/hacks/test_hacks.py tests/test_kilvin_operator_scripts.py tests/test_public_release_readiness.py
	cd explorer && npm test
	cd explorer && npm run typecheck
	$(MAKE) explorer-build

runtime-proof:
	$(MAKE) kilvin-up
	$(MAKE) kilvin-real-smoke
