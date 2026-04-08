"""
Agent 1 — VideoIngestor
Handles: YouTube download via yt-dlp, local file processing,
         audio extraction, keyframe extraction (1 frame/30s)
"""

import asyncio
import subprocess
import json
import glob
from pathlib import Path


class VideoIngestor:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.audio_dir = work_dir / "audio"
        self.frames_dir = work_dir / "frames"
        self.audio_dir.mkdir(exist_ok=True)
        self.frames_dir.mkdir(exist_ok=True)

    async def from_youtube(self, url: str) -> tuple[Path, Path, dict]:
        """Download YouTube video, extract audio + keyframes."""
        audio_path = self.audio_dir / "audio.mp3"
        meta_path  = self.work_dir / "meta.json"

        # Download audio only (faster, sufficient for transcription)
        cmd_audio = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--output", str(audio_path.with_suffix("")),  # yt-dlp adds extension
            "--write-info-json",
            "--no-playlist",
            url
        ]
        await self._run(cmd_audio)

        # Also download video for frame extraction (lower quality)
        video_path = self.work_dir / "video.mp4"
        cmd_video = [
            "yt-dlp",
            "--format", "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "--output", str(video_path),
            "--no-playlist",
            url
        ]
        await self._run(cmd_video)

        # yt-dlp may change extension (e.g. video.mp4.webm), find actual file
        actual_videos = glob.glob(str(self.work_dir / "video.*"))
        if actual_videos:
            video_path = Path(actual_videos[0])

        # Extract keyframes (1 per 30 seconds)
        await self._extract_frames(video_path)

        # Parse metadata
        meta_files = list(self.work_dir.glob("*.info.json"))
        metadata = {}
        if meta_files:
            with open(meta_files[0]) as f:
                raw = json.load(f)
                metadata = {
                    "title": raw.get("title", "Unknown"),
                    "duration_seconds": raw.get("duration", 0),
                    "uploader": raw.get("uploader", ""),
                    "upload_date": raw.get("upload_date", ""),
                    "description": raw.get("description", "")[:500],
                    "source": "youtube",
                    "url": url
                }

        # yt-dlp adds .mp3 automatically
        actual_audio = self.audio_dir / "audio.mp3"
        if not actual_audio.exists():
            candidates = list(self.audio_dir.glob("*.mp3"))
            actual_audio = candidates[0] if candidates else audio_path

        return actual_audio, self.frames_dir, metadata

    async def from_file(self, file_path: str) -> tuple[Path, Path, dict]:
        """Process an uploaded local video/audio file."""
        src = Path(file_path)
        audio_path = self.audio_dir / "audio.mp3"

        # Convert to mp3 using ffmpeg
        cmd = [
            "ffmpeg", "-i", str(src),
            "-vn",                  # no video
            "-ar", "16000",         # 16kHz sample rate (optimal for Whisper)
            "-ac", "1",             # mono
            "-b:a", "64k",
            str(audio_path),
            "-y"
        ]
        await self._run(cmd)

        # Extract keyframes if it's a video file
        if src.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov", ".avi"):
            await self._extract_frames(src)

        metadata = {
            "title": src.stem,
            "duration_seconds": await self._get_duration(src),
            "source": "upload",
            "filename": src.name
        }

        return audio_path, self.frames_dir, metadata

    async def _extract_frames(self, video_path: Path):
        """Extract 1 frame every 30 seconds using ffmpeg."""
        output_pattern = str(self.frames_dir / "frame_%04d.jpg")
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vf", "fps=1/30,scale=1280:-1",  # 1 frame per 30s, max width 1280px
            "-q:v", "3",
            output_pattern,
            "-y"
        ]
        await self._run(cmd)

    async def _get_duration(self, path: Path) -> int:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", str(path)
        ]
        result = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await result.communicate()
        try:
            data = json.loads(stdout)
            return int(float(data["format"].get("duration", 0)))
        except Exception:
            return 0

    @staticmethod
    async def _run(cmd: list):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\nstderr: {stderr.decode()[:500]}")
        return stdout.decode()
