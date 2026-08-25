.PHONY: demo test install
install: ; pip install -e .
test: ; pytest -q
demo: ; rotor-scope demo
