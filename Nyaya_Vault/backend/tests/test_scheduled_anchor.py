from __future__ import annotations

import asyncio

import pytest

from app.core.config import Settings
from app.services.blockchain_anchor import BlockchainAnchorService
from tests.fake_gateway import FakeGateway
from tests.test_blockchain_anchor import FakeAnchorClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _service(gateway: FakeGateway, **overrides):
    settings = Settings(
        _env_file=None, supabase_url="http://fake.invalid", supabase_anon_key="a", supabase_service_role_key="s",
        enable_blockchain_anchor=True, blockchain_rpc_url="http://fake-rpc.invalid",
        blockchain_private_key="0x" + "11" * 32, auto_anchor_enabled=True,
        auto_anchor_initial_delay_seconds=0.01, auto_anchor_interval_seconds=0.05, **overrides,
    )
    fake = FakeAnchorClient()
    return BlockchainAnchorService(gateway, settings, chain_client=fake), fake


async def _log(gateway, action="CASE_CREATED"):
    await gateway.append_audit_service(actor_user_id=None, case_id=None, document_id=None, action=action)


@pytest.mark.anyio
async def test_skips_when_there_is_nothing_to_anchor():
    service, fake = _service(FakeGateway())
    result = await service.run_scheduled_anchor()
    assert result["status"] == "skipped" and fake.submitted == []


@pytest.mark.anyio
async def test_anchors_new_activity_as_a_system_actor_and_marks_it_scheduled():
    gateway = FakeGateway()
    service, fake = _service(gateway)
    await _log(gateway)

    result = await service.run_scheduled_anchor()
    assert result["status"] == "anchored"
    assert len(fake.submitted) == 1
    anchor = gateway.tables["integrity_anchors"][0]
    assert anchor["created_by"] is None
    anchored_entry = next(a for a in gateway.tables["audit_logs"] if a["action"] == "AUDIT_CHAIN_ANCHORED")
    assert anchored_entry["actor_user_id"] is None
    assert anchored_entry["metadata"]["source"] == "scheduled"


@pytest.mark.anyio
async def test_does_not_re_anchor_just_because_the_anchor_logged_itself():
    """Anchoring appends its own audit entry, so the raw chain head is
    always newer than the last anchor. Without excluding anchor entries the
    scheduler would spend gas on every tick forever."""
    gateway = FakeGateway()
    service, fake = _service(gateway)
    await _log(gateway)

    assert (await service.run_scheduled_anchor())["status"] == "anchored"
    assert (await service.run_scheduled_anchor())["status"] == "skipped"
    assert (await service.run_scheduled_anchor())["status"] == "skipped"
    assert len(fake.submitted) == 1


@pytest.mark.anyio
async def test_anchors_again_once_real_activity_resumes():
    gateway = FakeGateway()
    service, fake = _service(gateway)
    await _log(gateway)
    await service.run_scheduled_anchor()

    await _log(gateway, "LOGIN")
    result = await service.run_scheduled_anchor()
    assert result["status"] == "anchored" and len(fake.submitted) == 2
    assert fake.submitted[1]["sequence"] > fake.submitted[0]["sequence"]


@pytest.mark.anyio
async def test_a_failing_tick_is_recorded_not_raised_and_the_next_tick_recovers():
    gateway = FakeGateway()
    service, fake = _service(gateway)
    await _log(gateway)

    real_submit = fake.submit_anchor
    async def boom(**_):
        raise RuntimeError("insufficient funds for gas")
    fake.submit_anchor = boom

    result = await service.run_scheduled_anchor()  # must not raise
    assert result["status"] == "error" and "insufficient funds" in result["detail"]
    assert service.schedule_info()["last_result"]["status"] == "error"
    assert gateway.tables["integrity_anchors"] == []

    fake.submit_anchor = real_submit
    assert (await service.run_scheduled_anchor())["status"] == "anchored"


@pytest.mark.anyio
async def test_unconfigured_service_reports_error_instead_of_crashing():
    gateway = FakeGateway()
    service, _ = _service(gateway)
    service.settings.blockchain_private_key = None
    await _log(gateway)
    assert (await service.run_scheduled_anchor())["status"] == "error"


@pytest.mark.anyio
async def test_background_loop_runs_on_its_own_and_stops_cleanly():
    gateway = FakeGateway()
    service, fake = _service(gateway)
    await _log(gateway)

    service.start_scheduler()
    assert service.schedule_info()["enabled"] is True
    await asyncio.sleep(0.4)
    assert len(fake.submitted) == 1  # anchored once, then idle ticks are skipped
    assert service.schedule_info()["last_run_at"] is not None

    await _log(gateway, "LOGIN")
    await asyncio.sleep(0.3)
    assert len(fake.submitted) == 2

    await service.stop_scheduler()
    assert service._task is None and service.schedule_info()["next_run_at"] is None
    await _log(gateway, "LOGIN")
    await asyncio.sleep(0.2)
    assert len(fake.submitted) == 2  # stopped means stopped


@pytest.mark.anyio
async def test_scheduler_does_not_start_when_auto_anchor_is_off():
    service, _ = _service(FakeGateway(), )
    service.settings.auto_anchor_enabled = False
    service.start_scheduler()
    assert service._task is None
    assert service.schedule_info()["enabled"] is False
