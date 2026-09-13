# backend-isolated-runtime Specification

## Purpose
TBD - defined by change fix-langchain-dependency-mismatch. Update Purpose after archiving.

## Requirements

### Requirement: Backend runs from an isolated virtual environment
The backend SHALL be executable from a dedicated Python virtual environment (`backend/.venv`) containing exactly the dependency versions pinned in `backend/requirements.txt`, independent of any packages installed in the machine's global/user Python environment.

#### Scenario: Backend app module imports successfully
- **WHEN** `app.main` is imported using the Python interpreter from `backend/.venv`
- **THEN** the import succeeds with no `ModuleNotFoundError` or version-conflict error raised by `langchain`, `langchain-core`, `langchain-community`, `langchain-openai`, `gotrue`, or `httpx`

### Requirement: Transitive dependency versions are pinned to prevent regressions
Any transitive dependency whose latest version within its declared range is known to break this backend (confirmed by testing) SHALL be pinned explicitly in `backend/requirements.txt`, so that a fresh install does not silently re-introduce the incompatibility.

#### Scenario: Fresh install resolves a working gotrue version
- **WHEN** `pip install -r backend/requirements.txt` is run in a clean environment with network access to PyPI
- **THEN** the resolved `gotrue` version is `2.4.4` (pinned), not an unpinned newer version that passes an unsupported `proxy` argument to `httpx.Client`

#### Scenario: Backend server starts
- **WHEN** `uvicorn app.main:app` is started using the Python interpreter from `backend/.venv`
- **THEN** the FastAPI application initializes without raising an import-time exception

### Requirement: Global Python environment remains unaffected
Creating and populating the backend's isolated virtual environment SHALL NOT change any package version in the machine's global/user Python environment used by other, unrelated tools.

#### Scenario: Unrelated global packages keep their versions
- **WHEN** the backend's isolated virtual environment is created and populated with `backend/requirements.txt`
- **THEN** packages installed in the global/user Python environment for unrelated tools (e.g. `langgraph`, `langgraph-checkpoint`, `langgraph-prebuilt`, `langchain-chroma`) keep the exact versions they had before this change
