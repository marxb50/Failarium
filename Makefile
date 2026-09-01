.PHONY: install-local test demo

install-local:
	uv tool install --editable .

test:
	python -m unittest discover -s tests -v

demo:
	failarium capture --root examples/known-failure --out known-failure.failarium --name known-failure --force -- python task.py
	failarium verify known-failure.failarium
	failarium replay known-failure.failarium
