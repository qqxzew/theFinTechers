PY ?= .venv/Scripts/python
export PYTHONPATH := .
export PYTHONIOENCODING := utf-8

.PHONY: test lint isolation worlds eval api ui demo

test:        ## unit + property + integration tests
	$(PY) -m pytest tests -q

lint:        ## ruff + import-linter (red/blue separation) + label-leak grep
	$(PY) -m ruff check .
	.venv/Scripts/lint-imports
	sh scripts/check_isolation.sh

worlds:      ## generate seeded red-team worlds (dev 7,101; held-out 202,303)
	for s in 7 101 202 303; do $(PY) -m redteam.generate --seed $$s --out data/redteam/seed$$s; done

eval:        ## full reproducible evaluation -> eval/report.json, eval/report.md, pitch_numbers.json
	$(PY) -m eval.run_all

api:         ## FastAPI backend on :8000 (demo world = STAJ_WORLD, default data/redteam/seed707)
	$(PY) -m api.server

ui:          ## Vite dev server on :5173 against the real API
	cd ui && VITE_API_BASE=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1

demo:        ## seed data -> run nodes + radar -> evaluation -> API (open http://127.0.0.1:5173 after `make ui`)
	$(MAKE) worlds
	$(MAKE) eval
	$(MAKE) api
