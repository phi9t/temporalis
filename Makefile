.PHONY: constellation-list constellation-status constellation-doctor constellation-snapshot test

constellation-list:
	python3 -m monoctl.cli list

constellation-status:
	python3 -m monoctl.cli status

constellation-doctor:
	python3 -m monoctl.cli doctor

constellation-snapshot:
	python3 -m monoctl.cli snapshot

test:
	pytest -q
