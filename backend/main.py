"""
Technical Video Intelligence Bot — FastAPI Backend
Pipeline: Video/YouTube → Whisper STT → GPT-4o Analysis → Markdown + Jira JSON
"""

import os
import json
import asyncio
import tempfile
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from agents.ingestor import VideoIngestor
from agents.transcriber import TranscriptionAgent
from agents.analyzer import AnalysisAgent
from agents.distiller import DistillerAgent
from agents.output_generator import OutputGenerator

load_dotenv()

app = FastAPI(
    title="Technical Video Intelligence Bot",
    description="Upload a meeting/tutorial video → get structured Markdown notes + Jira JSON",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (use Redis in production)
jobs: dict = {}


# ── Models ────────────────────────────────────────────────────────────────────

class YouTubeRequest(BaseModel):
    url: str
    title: str = ""

class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | running | done | error
    stage: str   # ingest | transcribe | analyze | distill | output | complete
    progress: int  # 0-100
    result: dict | None = None
    error: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/process/youtube", response_model=JobStatus)
async def process_youtube(req: YouTubeRequest, background_tasks: BackgroundTasks):
    """Start processing a YouTube URL asynchronously."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "stage": "ingest", "progress": 0, "result": None, "error": None}
    background_tasks.add_task(run_pipeline, job_id, youtube_url=req.url)
    return JobStatus(job_id=job_id, **jobs[job_id])


@app.post("/process/upload", response_model=JobStatus)
async def process_upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Start processing an uploaded video file asynchronously."""
    if not file.filename.endswith((".mp4", ".webm", ".mkv", ".mov", ".avi", ".mp3", ".wav")):
        raise HTTPException(400, "Unsupported file type. Use mp4, webm, mkv, mov, avi, mp3, wav.")

    job_id = str(uuid.uuid4())
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"job_{job_id}_"))
    tmp_path = tmp_dir / file.filename

    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    jobs[job_id] = {"status": "queued", "stage": "ingest", "progress": 0, "result": None, "error": None}
    background_tasks.add_task(run_pipeline, job_id, file_path=str(tmp_path))
    return JobStatus(job_id=job_id, **jobs[job_id])


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    """Poll job status and retrieve results when done."""
    if job_id not in jobs:
        raise HTTPException(404, f"Job {job_id} not found")
    return JobStatus(job_id=job_id, **jobs[job_id])


@app.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE endpoint — stream stage updates in real time."""
    async def event_generator():
        last_stage = None
        timeout = 0
        while timeout < 300:  # 5 min max
            if job_id not in jobs:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            job = jobs[job_id]
            if job["stage"] != last_stage:
                last_stage = job["stage"]
                yield f"event: update\ndata: {json.dumps(job)}\n\n"
            if job["status"] in ("done", "error"):
                yield f"event: complete\ndata: {json.dumps(job)}\n\n"
                break
            await asyncio.sleep(1)
            timeout += 1

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────

async def run_pipeline(job_id: str, youtube_url: str = None, file_path: str = None):
    """Runs all 5 pipeline stages sequentially, updating job state throughout."""

    def update(stage: str, progress: int, status: str = "running"):
        jobs[job_id].update({"stage": stage, "progress": progress, "status": status})

    try:
        work_dir = Path(tempfile.mkdtemp(prefix=f"work_{job_id}_"))

        # ── Stage 1: Ingest ────────────────────────────────────────────
        update("ingest", 5)
        ingestor = VideoIngestor(work_dir)
        if youtube_url:
            audio_path, frames_dir, metadata = await ingestor.from_youtube(youtube_url)
        else:
            audio_path, frames_dir, metadata = await ingestor.from_file(file_path)
        update("ingest", 20)

        # ── Stage 2: Transcribe ────────────────────────────────────────
        update("transcribe", 25)
        transcriber = TranscriptionAgent()
        transcript = await transcriber.transcribe(audio_path)
        update("transcribe", 45)

        # ── Stage 3: Analyze ───────────────────────────────────────────
        update("analyze", 50)
        analyzer = AnalysisAgent()
        analysis = await analyzer.analyze(transcript, frames_dir, metadata)
        update("analyze", 65)

        # ── Stage 4: Distill ───────────────────────────────────────────
        update("distill", 70)
        distiller = DistillerAgent()
        distilled = await distiller.distill(analysis)
        update("distill", 85)

        # ── Stage 5: Output ────────────────────────────────────────────
        update("output", 90)
        generator = OutputGenerator()
        markdown_note = generator.to_markdown(distilled, metadata)
        jira_payload  = generator.to_jira_json(distilled, metadata)
        update("complete", 100)

        jobs[job_id].update({
            "status": "done",
            "stage": "complete",
            "progress": 100,
            "result": {
                "metadata": metadata,
                "transcript_segments": len(transcript.get("segments", [])),
                "decisions_found": len(distilled.get("decisions", [])),
                "action_items_found": len(distilled.get("action_items", [])),
                "markdown": markdown_note,
                "jira_json": jira_payload,
            }
        })

    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e), "progress": 0})
        raise
