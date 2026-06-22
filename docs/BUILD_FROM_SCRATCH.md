# Repository Scaffold Commands

These commands reproduce the folder structure before adding file contents.

```bash
mkdir -p driver-retention-copilot/{app/{agents,compliance,data,diagnostics,domain,integrations,memory,orchestration,rag,ui},data,docs/decisions,evaluations,scripts,tests,.github/{workflows,ISSUE_TEMPLATE}}
cd driver-retention-copilot

touch pyproject.toml README.md Makefile Dockerfile compose.yaml .env.example .gitignore .pre-commit-config.yaml
touch app/{__init__.py,api.py,cli.py,config.py,container.py,exceptions.py,observability.py}
touch app/agents/{__init__.py,base.py,heuristic_strategist.py,openai_strategist.py}
touch app/compliance/{__init__.py,engine.py,rules.py}
touch app/data/{__init__.py,driver_repository.py,ledger_repository.py,ticket_repository.py}
touch app/diagnostics/{__init__.py,extractor.py}
touch app/domain/{__init__.py,enums.py,models.py}
touch app/integrations/{__init__.py,incentive_adapter.py}
touch app/memory/{__init__.py,sqlite_store.py}
touch app/orchestration/{__init__.py,copilot.py}
touch app/rag/{__init__.py,policy_store.py}
touch app/ui/{__init__.py,streamlit_app.py}
touch scripts/{generate_eval_trace.py,ingest_policy.py}
touch tests/{__init__.py,conftest.py,factories.py}
touch docs/{TECHNICAL_DESIGN.md,BUSINESS_INTENT.md,TEST_STRATEGY.md,GIT_WORKFLOW.md,PRODUCTION_READINESS.md}
```

Then copy the supplied assignment data into `data/` and use the README commands to install and test.
