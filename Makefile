# MQTTForge - developer task runner
#
#   make help      show available targets
#   make test      run the unit + integration test suite
#   make selftest  run the end-to-end self-test against the embedded broker
#   make build     build sdist + wheel into dist/
#   make bench     quick throughput benchmark on the embedded broker
#   make broker    start the embedded broker on port 1883
#   make clean     remove build artifacts

PYTHON ?= python3
PKG    := mqttforge

.PHONY: help install install-dev test selftest build bench broker clean

help:
	@echo "MQTTForge make targets"
	@echo "  make install     install the package in editable mode"
	@echo "  make install-dev install with development extras"
	@echo "  make test        run the full test suite"
	@echo "  make selftest    end-to-end self-test (embedded broker)"
	@echo "  make bench       throughput benchmark"
	@echo "  make broker      start the embedded broker on 0.0.0.0:1883"
	@echo "  make build       build sdist and wheel"
	@echo "  make clean       remove build artifacts"

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m unittest discover -s tests -v

selftest:
	$(PYTHON) -m $(PKG) selftest

bench:
	$(PYTHON) -m $(PKG) bench --messages 1000 --qos 1 --size 256

broker:
	$(PYTHON) -m $(PKG) broker --host 0.0.0.0 --port 1883

build:
	./build.sh

clean:
	rm -rf build dist ./*.egg-info
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
