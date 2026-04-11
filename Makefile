.PHONY: monorepo-list monorepo-status monorepo-doctor monorepo-snapshot test

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
