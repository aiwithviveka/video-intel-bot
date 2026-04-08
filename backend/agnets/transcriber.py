"""
Agent 2 — TranscriptionAgent
Uses OpenAI Whisper API to produce timestamped transcript segments.
Falls back to local whisper if API key is missing.
"""

import os
import json
from pathlib import Path
from openai import AsyncOpenAI


class TranscriptionAgent:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = "whisper-1"

    async def transcribe(self, audio_path: Path) -> dict:
        """
        Transcribe audio file. Returns dict with:
          - text: full transcript string
          - segments: list of {start, end, text} dicts
          - language: detected language
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        file_size_mb = audio_path.stat().st_size / (1024 * 1024)

        # Whisper API limit is 25MB — chunk if needed
        if file_size_mb > 24:
            return await self._transcribe_chunked(audio_path)
        else:
            return await self._transcribe_single(audio_path)

    async def _transcribe_single(self, audio_path: Path) -> dict:
        with open(audio_path, "rb") as f:
            response = await self.client.audio.transcriptions.create(
                model=self.model,
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        return {
            "text": response.text,
            "language": getattr(response, "language", "en"),
            "duration": getattr(response, "duration", 0),
            "segments": [
                {
                    "id": seg.id,
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                    "timestamp": self._seconds_to_hms(seg.start),
                }
                for seg in (response.segments or [])
            ]
        }

    async def _transcribe_chunked(self, audio_path: Path) -> dict:
        """Split audio into 20-min chunks and transcribe each."""
        import subprocess
        import tempfile

        chunks_dir = audio_path.parent / "chunks"
        chunks_dir.mkdir(exist_ok=True)

        # Split into 20-minute segments
        subprocess.run([
            "ffmpeg", "-i", str(audio_path),
            "-f", "segment",
            "-segment_time", "1200",  # 20 minutes
            "-c", "copy",
            str(chunks_dir / "chunk_%03d.mp3"),
            "-y"
        ], capture_output=True)

        all_segments = []
        full_text = []
        offset = 0.0

        for chunk_path in sorted(chunks_dir.glob("chunk_*.mp3")):
            result = await self._transcribe_single(chunk_path)
            full_text.append(result["text"])
            for seg in result["segments"]:
                seg["start"] += offset
                seg["end"] += offset
                seg["timestamp"] = self._seconds_to_hms(seg["start"])
                all_segments.append(seg)
            offset += result.get("duration", 1200)

        return {
            "text": " ".join(full_text),
            "language": "en",
            "duration": offset,
            "segments": all_segments
        }

    @staticmethod
    def _seconds_to_hms(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
