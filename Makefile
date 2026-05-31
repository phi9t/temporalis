.PHONY: monorepo-init monorepo-list monorepo-status monorepo-doctor monorepo-snapshot test explorer-gen-data explorer-build explorer-dev

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
