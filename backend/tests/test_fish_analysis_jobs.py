# CAMINHO: backend/tests/test_fish_analysis_jobs.py
"""
Testes do processamento assíncrono de análise de imagens (job + polling).
Ver openspec/changes/async-fish-analysis-processing.

Cobre:
  - POST /fish/analyses/process responde 202 com job_id sem esperar o
    processamento (a validação de posse das imagens ainda é síncrona).
  - Idempotência: par de imagens com job ativo devolve o job existente.
  - GET /fish/analyses/jobs/{id}: estados queued/processing/done/error e
    isolamento por usuário (job de outro usuário -> 404).
  - FishAnalysisJobService: job obsoleto (queued/processing "preso" por
    tempo demais) é marcado como 'error' em vez de bloquear indefinidamente.
  - Limite de concorrência do processamento em background.
"""

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.fish_schemas import ProcessRequest, ProcessResponse
from app.services import fish_analysis_job_service as job_service_module
from app.services.fish_analysis_job_service import FishAnalysisJobService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def override_current_user(user_id: str = "u1", access_token: str = "tok1"):
    async def mock_current_user():
        return {"id": user_id, "email": "user@example.com", "role": "user", "access_token": access_token}
    app.dependency_overrides[main_module.get_current_user] = mock_current_user


def patch_background_noop(monkeypatch):
    """Impede que a task de background criada pelo endpoint execute
    trabalho real (rede/DB) caso o event loop lhe dê uma chance de correr
    durante o teste — os testes de endpoint verificam só a resposta
    imediata (202) ou a leitura de status, não o processamento em si."""
    monkeypatch.setattr(
        main_module, "_sync_process_fish_analysis",
        lambda data, user_id, access_token: ProcessResponse(
            analysis_id="unused", status="success", message="ok"
        ),
    )
    monkeypatch.setattr(main_module.fish_analysis_job_service, "mark_processing", lambda *a, **k: None)
    monkeypatch.setattr(main_module.fish_analysis_job_service, "mark_done", lambda *a, **k: None)
    monkeypatch.setattr(main_module.fish_analysis_job_service, "mark_error", lambda *a, **k: None)
    monkeypatch.setattr(main_module, "_mark_images_processing_error", lambda *a, **k: None)


class FakeImagesClient:
    """Fake do cliente Supabase para a checagem de posse de fish_images em
    POST /fish/analyses/process (`select("id, user_id").eq("id", ...)`).
    `rows_by_id`: id -> row dict (ausente = imagem não encontrada)."""

    def __init__(self, rows_by_id):
        self.rows_by_id = rows_by_id
        self._pending_id = None

    def table(self, name):
        assert name == "fish_images"
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        assert field == "id"
        self._pending_id = value
        return self

    def execute(self):
        row = self.rows_by_id.get(self._pending_id)
        return SimpleNamespace(data=[row] if row else [])


# ── POST /fish/analyses/process ────────────────────────────────────────────────

def test_process_creates_job_and_returns_202(client, monkeypatch):
    override_current_user(user_id="u1")
    patch_background_noop(monkeypatch)

    images = {"lat-1": {"id": "lat-1", "user_id": "u1"}, "sup-1": {"id": "sup-1", "user_id": "u1"}}
    monkeypatch.setattr(main_module, "get_user_scoped_client", lambda token: FakeImagesClient(images))
    monkeypatch.setattr(main_module.fish_analysis_job_service, "find_active_job", lambda *a, **k: None)
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "create_job",
        lambda *a, **k: {"id": "job-1", "status": "queued"},
    )

    resp = client.post("/fish/analyses/process", json={"lateral_id": "lat-1", "superior_id": "sup-1"})

    assert resp.status_code == 202
    assert resp.json() == {"job_id": "job-1", "status": "queued"}


def test_process_lateral_image_not_found_returns_404_without_creating_job(client, monkeypatch):
    override_current_user(user_id="u1")
    patch_background_noop(monkeypatch)

    images = {"sup-1": {"id": "sup-1", "user_id": "u1"}}  # lat-1 ausente
    monkeypatch.setattr(main_module, "get_user_scoped_client", lambda token: FakeImagesClient(images))
    create_calls = []
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "create_job",
        lambda *a, **k: create_calls.append((a, k)) or {"id": "x", "status": "queued"},
    )

    resp = client.post("/fish/analyses/process", json={"lateral_id": "lat-1", "superior_id": "sup-1"})

    assert resp.status_code == 404
    assert create_calls == []


def test_process_image_owned_by_another_user_returns_403_without_creating_job(client, monkeypatch):
    override_current_user(user_id="u1")
    patch_background_noop(monkeypatch)

    images = {
        "lat-1": {"id": "lat-1", "user_id": "u1"},
        "sup-1": {"id": "sup-1", "user_id": "outro-usuario"},
    }
    monkeypatch.setattr(main_module, "get_user_scoped_client", lambda token: FakeImagesClient(images))
    create_calls = []
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "create_job",
        lambda *a, **k: create_calls.append((a, k)) or {"id": "x", "status": "queued"},
    )

    resp = client.post("/fish/analyses/process", json={"lateral_id": "lat-1", "superior_id": "sup-1"})

    assert resp.status_code == 403
    assert create_calls == []


def test_process_reuses_existing_active_job_idempotent(client, monkeypatch):
    """Reenvio do mesmo par de imagens enquanto o job anterior ainda está
    queued/processing devolve o job existente, sem criar outro."""
    override_current_user(user_id="u1")
    patch_background_noop(monkeypatch)

    images = {"lat-1": {"id": "lat-1", "user_id": "u1"}, "sup-1": {"id": "sup-1", "user_id": "u1"}}
    monkeypatch.setattr(main_module, "get_user_scoped_client", lambda token: FakeImagesClient(images))
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "find_active_job",
        lambda *a, **k: {"id": "job-existing", "status": "processing"},
    )
    create_calls = []
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "create_job",
        lambda *a, **k: create_calls.append((a, k)) or {"id": "job-new", "status": "queued"},
    )

    resp = client.post("/fish/analyses/process", json={"lateral_id": "lat-1", "superior_id": "sup-1"})

    assert resp.status_code == 202
    assert resp.json() == {"job_id": "job-existing", "status": "processing"}
    assert create_calls == []  # nenhum job novo foi criado


# ── GET /fish/analyses/jobs/{job_id} ───────────────────────────────────────────

def test_get_job_processing_has_no_result_yet(client, monkeypatch):
    override_current_user(user_id="u1")
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "get_job",
        lambda job_id, user_id, access_token: {"id": job_id, "user_id": user_id, "status": "processing"},
    )

    resp = client.get("/fish/analyses/jobs/job-1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "processing"
    assert body["result"] is None
    assert body["analysis_id"] is None


def test_get_job_done_includes_result(client, monkeypatch):
    override_current_user(user_id="u1")
    result_payload = ProcessResponse(
        analysis_id="an-1", status="success", message="Análise concluída com sucesso", kvol=0.02,
    ).model_dump()
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "get_job",
        lambda job_id, user_id, access_token: {
            "id": job_id, "user_id": user_id, "status": "done",
            "analysis_id": "an-1", "result": result_payload, "error": None,
        },
    )

    resp = client.get("/fish/analyses/jobs/job-1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["analysis_id"] == "an-1"
    assert body["result"]["kvol"] == 0.02


def test_get_job_error_status_has_sanitized_message(client, monkeypatch):
    override_current_user(user_id="u1")
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "get_job",
        lambda job_id, user_id, access_token: {
            "id": job_id, "user_id": user_id, "status": "error",
            "error": main_module.GENERIC_ERROR_MESSAGE,
        },
    )

    resp = client.get("/fish/analyses/jobs/job-1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"] == main_module.GENERIC_ERROR_MESSAGE
    # nenhum detalhe interno (nome de exceção, traceback etc.) exposto
    assert "Traceback" not in (body["error"] or "")


def test_get_job_not_found_or_other_user_returns_404(client, monkeypatch):
    override_current_user(user_id="u1")
    # get_job já reconfirma a posse internamente (defesa em profundidade) —
    # aqui simulamos o retorno None que o serviço dá tanto para job
    # inexistente quanto para job de outro usuário.
    monkeypatch.setattr(
        main_module.fish_analysis_job_service, "get_job",
        lambda job_id, user_id, access_token: None,
    )

    resp = client.get("/fish/analyses/jobs/job-de-outro-usuario")

    assert resp.status_code == 404


# ── FishAnalysisJobService: jobs obsoletos ─────────────────────────────────────

class FakeJobsTable:
    """Fake mínimo do encadeamento table().select()/.update()...execute()
    do supabase-py, o suficiente para os métodos de FishAnalysisJobService
    exercitados nestes testes."""

    def __init__(self, client):
        self.client = client
        self._filters = {}
        self._op = "select"
        self._payload = None

    def select(self, *args, **kwargs):
        self._op = "select"
        return self

    def eq(self, field, value):
        self._filters[field] = value
        return self

    def in_(self, field, values):
        self._filters[field] = ("in", list(values))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def execute(self):
        row = self.client.row
        if self._op == "update":
            self.client.updates.append(dict(self._payload))
            if row is not None:
                row.update(self._payload)
            return SimpleNamespace(data=[row] if row else [])

        if row is None:
            return SimpleNamespace(data=[])
        for field, value in self._filters.items():
            if isinstance(value, tuple) and value[0] == "in":
                if row.get(field) not in value[1]:
                    return SimpleNamespace(data=[])
            elif row.get(field) != value:
                return SimpleNamespace(data=[])
        return SimpleNamespace(data=[row])


class FakeJobsClient:
    def __init__(self, row):
        self.row = row
        self.updates = []

    def table(self, name):
        assert name == "fish_analysis_job_service" or name  # apenas evita lint de arg não usado
        return FakeJobsTable(self)


def _iso(seconds_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def test_get_job_marks_orphaned_job_as_error(monkeypatch):
    monkeypatch.setattr(job_service_module, "JOB_STALE_AFTER_SECONDS", 60)
    row = {
        "id": "job-1", "user_id": "u1", "status": "processing",
        "created_at": _iso(1000), "started_at": _iso(1000),
    }
    fake_client = FakeJobsClient(row)
    monkeypatch.setattr(job_service_module, "get_user_scoped_client", lambda token: fake_client)

    svc = FishAnalysisJobService()
    result = svc.get_job("job-1", "u1", "tok")

    assert result["status"] == "error"
    assert fake_client.updates and fake_client.updates[0]["status"] == "error"


def test_get_job_does_not_touch_recent_processing_job(monkeypatch):
    monkeypatch.setattr(job_service_module, "JOB_STALE_AFTER_SECONDS", 300)
    row = {
        "id": "job-1", "user_id": "u1", "status": "processing",
        "created_at": _iso(5), "started_at": _iso(5),
    }
    fake_client = FakeJobsClient(row)
    monkeypatch.setattr(job_service_module, "get_user_scoped_client", lambda token: fake_client)

    svc = FishAnalysisJobService()
    result = svc.get_job("job-1", "u1", "tok")

    assert result["status"] == "processing"
    assert fake_client.updates == []


def test_get_job_returns_none_for_other_users_job(monkeypatch):
    row = {"id": "job-1", "user_id": "dono-verdadeiro", "status": "done"}
    fake_client = FakeJobsClient(row)
    monkeypatch.setattr(job_service_module, "get_user_scoped_client", lambda token: fake_client)

    svc = FishAnalysisJobService()
    result = svc.get_job("job-1", "outro-usuario", "tok")

    assert result is None


def test_find_active_job_ignores_stale_job_and_marks_it_error(monkeypatch):
    monkeypatch.setattr(job_service_module, "JOB_STALE_AFTER_SECONDS", 60)
    row = {
        "id": "job-1", "user_id": "u1", "status": "queued",
        "lateral_id": "lat-1", "superior_id": "sup-1",
        "created_at": _iso(1000),
    }
    fake_client = FakeJobsClient(row)
    monkeypatch.setattr(job_service_module, "get_user_scoped_client", lambda token: fake_client)

    svc = FishAnalysisJobService()
    result = svc.find_active_job("u1", "tok", "lat-1", "sup-1")

    assert result is None
    assert fake_client.updates and fake_client.updates[0]["status"] == "error"


# ── Limite de concorrência do processamento em background ─────────────────────

def test_analysis_concurrency_limit_serializes_processing(monkeypatch):
    """Com ANALYSIS_MAX_CONCURRENCY efetivo = 1, o segundo job não deve
    começar a processar antes do primeiro liberar o semáforo."""
    order = []
    first_started = threading.Event()
    release_first = threading.Event()

    def fake_sync(data: ProcessRequest, user_id: str, access_token: str) -> ProcessResponse:
        order.append(("start", data.lateral_id))
        if data.lateral_id == "lat-1":
            first_started.set()
            assert release_first.wait(timeout=2), "job-2 nunca deveria destravar job-1"
        order.append(("end", data.lateral_id))
        return ProcessResponse(analysis_id=f"an-{data.lateral_id}", status="success", message="ok")

    monkeypatch.setattr(main_module, "_sync_process_fish_analysis", fake_sync)
    monkeypatch.setattr(main_module, "_analysis_semaphore", asyncio.Semaphore(1))
    monkeypatch.setattr(main_module.fish_analysis_job_service, "mark_processing", lambda *a, **k: None)
    monkeypatch.setattr(main_module.fish_analysis_job_service, "mark_done", lambda *a, **k: None)
    monkeypatch.setattr(main_module.fish_analysis_job_service, "mark_error", lambda *a, **k: None)
    monkeypatch.setattr(main_module, "_mark_images_processing_error", lambda *a, **k: None)

    async def run():
        data1 = ProcessRequest(lateral_id="lat-1", superior_id="sup-1")
        data2 = ProcessRequest(lateral_id="lat-2", superior_id="sup-2")

        task1 = asyncio.create_task(main_module._run_analysis_job("job-1", data1, "u1", "tok1"))
        # Espera job-1 tomar o semáforo e travar dentro do processamento
        # (thread separada via asyncio.to_thread — daí o Event de threading).
        await asyncio.get_event_loop().run_in_executor(None, first_started.wait, 2)

        task2 = asyncio.create_task(main_module._run_analysis_job("job-2", data2, "u1", "tok1"))
        await asyncio.sleep(0.1)
        # job-2 não deve ter começado: concorrência limitada a 1 slot.
        assert ("start", "lat-2") not in order

        release_first.set()
        await asyncio.gather(task1, task2)

    asyncio.run(run())

    assert order.index(("end", "lat-1")) < order.index(("start", "lat-2"))
