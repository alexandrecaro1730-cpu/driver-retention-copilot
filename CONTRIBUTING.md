# Contributing

Create a short-lived branch, add tests before or with behaviour changes, and run `make quality` before
opening a pull request. Business-rule changes require an explicit policy citation and boundary tests.
Never commit secrets, driver data beyond approved fixtures, generated state databases, or raw external
LLM transcripts containing personal data. See `docs/GIT_WORKFLOW.md` for naming and review rules.
