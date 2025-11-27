from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from docwriter import queue as queue_module
from docwriter.queue import (
    process_plan_intake,
    process_plan,
    process_write,
    process_review,
    process_verify,
    process_rewrite,
    process_finalize,
)
from docwriter.stages.diagram_prep import process_diagram_prep
from docwriter.diagram_renderer import process_diagram_render
from docwriter.storage import BlobStore, JobStoragePaths
from docwriter.config import get_settings


def _config_ready() -> bool:
    try:
        settings = get_settings()
    except Exception:
        return False
    return all(
        [
            settings.openai_api_key,
            settings.openai_base_url,
            settings.blob_connection_string,
        ]
    )


pytestmark = pytest.mark.skipif(not _config_ready(), reason="Azure E2E requires cloud credentials")


@pytest.mark.e2e
def test_e2e_local_pipeline(monkeypatch):
    settings = get_settings()
    store = BlobStore()

    captured: dict[str, list[dict]] = {}

    def fake_send(queue_name: str, payload: dict) -> None:
        captured.setdefault(queue_name, []).append(payload)

    monkeypatch.setattr(queue_module, "_send", fake_send)
    monkeypatch.setattr(queue_module, "_status", lambda payload: None)

    def pop_payload(queue_name: str) -> dict:
        try:
            queue = captured[queue_name]
        except KeyError:
            pytest.fail(f"No messages captured for queue {queue_name}")
        assert queue, f"No message available in queue {queue_name}"
        payload = queue.pop(0)
        print(f"[POP] {queue_name}: {json.dumps(payload, indent=2)}")
        return payload

    def try_pop_payload(queue_name: str) -> dict | None:
        queue = captured.get(queue_name)
        if not queue:
            return None
        payload = queue.pop(0)
        print(f"[TRY_POP] {queue_name}: {json.dumps(payload, indent=2)}")
        return payload

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "doc.md"
        user_id = "test-user"
        job_data = {
            "job_id": "local-test",
            "title": "Microsoft Dynamics 365 integrations with external systems",
            "audience": "Integration architects",
            "out": str(out),
            "cycles": 1,
            "user_id": user_id,
        }
        job_paths = JobStoragePaths(user_id=user_id, job_id=job_data["job_id"])

        # Intake
        process_plan_intake(job_data)
        payload = pop_payload(settings.sb_queue_plan)
        print("[INTAKE] Questions generated; proceeding with answers upload")
        answers = {
            "audience": "Enterprise integration architects and senior Dynamics 365 developers",
            "goals": "Provide guidance for planning and implementing integrations between Dynamics 365 and third-party systems (CRM, ERP, custom apps).",
            "non_goals": "Administration of on-prem ERP systems unrelated to Dynamics 365 or low-code tutorials for citizen developers.",
            "constraints": "Must adhere to Azure security baselines, leverage Azure Integration Services where possible, and meet regional data residency rules.",
            "tone": "authoritative and pragmatic",
            "pov": "third-person, vendor-neutral",
            "structure": "Executive summary, integration patterns, security/compliance, lifecycle management, case studies, appendices",
            "must_cover": "Azure Service Bus, Power Platform connectors, Logic Apps, custom API strategies, monitoring/observability",
            "must_avoid": "Legacy on-prem BizTalk migrations unless referencing coexistence",
            "references": "Microsoft Learn docs for Dynamics 365 and Azure Integration Services",
            "diagrams": "High-level architecture diagram showing Dynamics 365, middleware (Logic Apps/Service Bus), and external systems; sequence diagram for message flow",
            "context": "Global manufacturing enterprise modernizing integrations while maintaining SAP and Salesforce back-end connectivity.",
        }
        store.put_text(blob=job_paths.intake("answers.json"), text=json.dumps(answers))
        print("[INTAKE] Answers uploaded to Blob Storage")

        # Planning
        process_plan(payload)
        payload = pop_payload(settings.sb_queue_write)
        print("[PLAN] Plan generated and queued for writing")
        plan = json.loads(store.get_text(job_paths.plan()))
        payload["plan"] = plan
        payload["dependency_summaries"] = {}

        # Writing
        process_write(payload)
        payload = pop_payload(settings.sb_queue_review)
        print("[WRITE] Draft written and queued for review")

        # Review / verify loop until finalized
        review_payload = payload
        while True:
            process_review(review_payload)
            print("[REVIEW] General/style/cohesion reviews completed")
            verify_payload = pop_payload(settings.sb_queue_verify)
            process_verify(verify_payload)
            print("[VERIFY] Verification completed")
            rewrite_payload = try_pop_payload(settings.sb_queue_rewrite)
            if rewrite_payload:
                process_rewrite(rewrite_payload)
                print("[REWRITE] Targeted rewrites applied")
                review_payload = pop_payload(settings.sb_queue_review)
                continue
            diagram_prep_payload = pop_payload(settings.sb_queue_diagram_prep)
            process_diagram_prep(diagram_prep_payload)
            render_payload = try_pop_payload(settings.sb_queue_diagram_render)
            if render_payload:
                process_diagram_render(render_payload)
            finalize_payload = pop_payload(settings.sb_queue_finalize_ready)
            process_finalize(finalize_payload)
            print("[FINALIZE] Final document stored in Blob Storage")
            break

        final_md = store.get_text(job_paths.final("md"))
        assert len(final_md) > 0
        print(f"[RESULT] Final document length: {len(final_md)} characters")
        if out.exists():
            assert out.stat().st_size > 0
            print(f"[RESULT] Local document size: {out.stat().st_size} bytes")
