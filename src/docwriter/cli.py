from __future__ import annotations

from pathlib import Path
from typing import Optional
import typer

from .queue import (
    Job,
    send_job,
    send_resume,
    worker_plan,
    worker_plan_intake,
    worker_intake_resume,
    worker_write,
    worker_review,
    worker_verify,
    worker_rewrite,
    worker_finalize,
)


app = typer.Typer(help="DocWriter v3 — AI Document Writer")


@app.command()
def generate(
    title: Optional[str] = typer.Argument(None),
    audience: Optional[str] = typer.Argument(None),
    title_option: Optional[str] = typer.Option(None, "--title", "-t", help="Document title"),
    audience_option: Optional[str] = typer.Option(None, "--audience", "-a", help="Target audience"),
    out: Path = typer.Option(Path("document.md"), "--out", help="Output Markdown file"),
    cycles: int = typer.Option(1, "--cycles", min=1, help="Max review/rewrite cycles"),
):
    """Enqueue a job for the stage-driven pipeline (>60 pages)."""
    title = title_option or title
    audience = audience_option or audience
    if not title or not audience:
        raise typer.BadParameter("Both title and audience are required (use positional args or --title/--audience).")
    job = Job(title=title, audience=audience, out=str(out), cycles=cycles)
    job_id = send_job(job)
    typer.echo(f"Enqueued job: {job_id}")


@app.command()
def plan(
    title: Optional[str] = typer.Argument(None),
    audience: Optional[str] = typer.Argument(None),
    title_option: Optional[str] = typer.Option(None, "--title", "-t", help="Document title"),
    audience_option: Optional[str] = typer.Option(None, "--audience", "-a", help="Target audience"),
    out: Path = typer.Option(Path("plan.json"), "--out", help="Plan JSON output"),
):
    """Alias for enqueueing a job; plan occurs in the PLAN stage worker."""
    title = title_option or title
    audience = audience_option or audience
    if not title or not audience:
        raise typer.BadParameter("Both title and audience are required (use positional args or --title/--audience).")
    job = Job(title=title, audience=audience, out=str(out))
    job_id = send_job(job)
    typer.echo(f"Enqueued job: {job_id}")


@app.command()
def queue(
    title: Optional[str] = typer.Argument(None),
    audience: Optional[str] = typer.Argument(None),
    title_option: Optional[str] = typer.Option(None, "--title", "-t", help="Document title"),
    audience_option: Optional[str] = typer.Option(None, "--audience", "-a", help="Target audience"),
    out: Path = typer.Option(Path("document.md"), "--out", help="Output Markdown file"),
    cycles: int = typer.Option(1, "--cycles", min=1, help="Max review/rewrite cycles"),
):
    """Enqueue a generation job for a worker to process (Azure Service Bus)."""
    title = title_option or title
    audience = audience_option or audience
    if not title or not audience:
        raise typer.BadParameter("Both title and audience are required (use positional args or --title/--audience).")
    job = Job(title=title, audience=audience, out=str(out), cycles=cycles)
    job_id = send_job(job)
    typer.echo(f"Enqueued job: {job_id}")


@app.command()
def worker():
    """Run a legacy single-queue worker (deprecated). Use stage workers instead."""
    typer.echo("Use: docwriter worker-plan | worker-write | worker-review | worker-verify | worker-rewrite | worker-finalize")


@app.command("worker-plan-intake")
def worker_plan_intake_cmd():
    """Worker for intake stage (questions)."""
    worker_plan_intake()


@app.command("worker-intake-resume")
def worker_intake_resume_cmd():
    """Worker to advance from intake to plan when answers are ready."""
    worker_intake_resume()


@app.command("worker-plan")
def worker_plan_cmd():
    """Worker for planning stage."""
    worker_plan()


@app.command("worker-write")
def worker_write_cmd():
    """Worker for writing stage."""
    worker_write()


@app.command("worker-review")
def worker_review_cmd():
    """Worker for review stage."""
    worker_review()


@app.command("worker-verify")
def worker_verify_cmd():
    """Worker for verify stage."""
    worker_verify()


@app.command("worker-rewrite")
def worker_rewrite_cmd():
    """Worker for targeted rewrite stage."""
    worker_rewrite()


@app.command("worker-finalize")
def worker_finalize_cmd():
    """Worker for finalize stage."""
    worker_finalize()


@app.command()
def resume(
    job_id: Optional[str] = typer.Argument(None),
    answers: Optional[Path] = typer.Argument(
        None, help="Optional local answers JSON; if omitted, read existing blob."
    ),
    job_id_option: Optional[str] = typer.Option(None, "--job-id", help="Job identifier"),
    answers_option: Optional[Path] = typer.Option(
        None, "--answers", help="Optional local answers JSON; overrides blob copy"
    ),
):
    """Signal resume for a job, optionally uploading a new answers JSON."""
    from azure.core.exceptions import ResourceNotFoundError
    from .storage import BlobStore

    job_id = job_id_option or job_id
    answers = answers_option or answers
    if not job_id:
        raise typer.BadParameter("job_id is required (positional or --job-id).")

    store = BlobStore()
    blob_path = f"jobs/{job_id}/intake/answers.json"

    if answers is not None:
        data = answers.read_text(encoding="utf-8")
        store.put_text(blob=blob_path, text=data)
        typer.echo(f"Uploaded answers from {answers} for job {job_id}")
    else:
        try:
            store.get_text(blob_path)
        except ResourceNotFoundError as exc:
            raise typer.BadParameter(
                "No answers found in Blob Storage. Provide a local answers JSON via --answers."
            ) from exc
        typer.echo(f"Found existing answers in Blob Storage for job {job_id}")

    send_resume(job_id)
    typer.echo(f"Signaled resume for job {job_id}")


@app.command()
def monitor():
    """Simple console status monitor (subscribe to status topic)."""
    import json as _json
    from .config import get_settings
    try:
        from azure.servicebus import ServiceBusClient  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("azure-servicebus not installed") from e

    settings = get_settings()
    with ServiceBusClient.from_connection_string(settings.sb_connection_string) as client:
        with client.get_subscription_receiver(settings.sb_topic_status, settings.sb_status_subscription, max_wait_time=30) as receiver:
            typer.echo("Listening for status events. Ctrl+C to quit.")
            while True:
                messages = receiver.receive_messages(max_message_count=20, max_wait_time=30)
                for m in messages:
                    try:
                        payload = _json.loads(str(m))
                    except Exception:
                        payload = _json.loads("".join([b.decode("utf-8") for b in m.body]))
                    typer.echo(_json.dumps(payload))
                    receiver.complete_message(m)
