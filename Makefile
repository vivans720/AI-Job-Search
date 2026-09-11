.PHONY: backend frontend sync agent test

backend:
	@./backend.sh

frontend:
	@cd frontend && npm run dev

sync:
	@backend/.venv/bin/python scripts/sync_internshala.py

agent:
	@backend/.venv/bin/python scripts/run_job_agent.py

test:
	@backend/.venv/bin/pytest tests/ -v
