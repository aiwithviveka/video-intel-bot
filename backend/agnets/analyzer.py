"""
Agent 3 — AnalysisAgent
Uses GPT-4o to analyze transcript segments + keyframe images simultaneously.
Identifies: architectural decisions, system constraints, magic→system transitions,
            action items, speakers, and technical concepts.
"""

import os
import base64
import json
from pathlib import Path
from openai import AsyncOpenAI


ANALYSIS_SYSTEM_PROMPT = """You are a senior software architect analyzing a technical meeting or tutorial recording.

You have access to:
1. A timestamped transcript of the video
2. Keyframe screenshots extracted from the video

Your job is to produce a detailed JSON analysis identifying:

- **decisions**: Architectural or technical decisions made (with timestamps)
- **constraints**: System constraints, SLAs, performance limits, business rules stated
- **magic_to_system**: Moments where hand-wavy language ("we'll handle X", "somehow Y") transitions 
  to concrete technical specifications. These are the most valuable insights.
- **action_items**: Specific tasks assigned with owner names and deadlines if mentioned
- **concepts**: Key technical terms, technologies, or patterns discussed
- **speakers**: Names/roles mentioned in the meeting
- **summary**: 3-sentence executive summary of the entire session

Return ONLY valid JSON matching this exact schema:
{
  "summary": "string",
  "speakers": ["name or role"],
  "decisions": [
    {
      "timestamp": "HH:MM:SS",
      "title": "short title",
      "description": "what was decided",
      "rationale": "why this decision was made",
      "alternatives_rejected": ["alternative 1"],
      "impact": "high|medium|low"
    }
  ],
  "constraints": [
    {
      "timestamp": "HH:MM:SS",
      "type": "performance|security|business|technical",
      "description": "the constraint",
      "metric": "specific number or SLA if given"
    }
  ],
  "magic_to_system": [
    {
      "timestamp": "HH:MM:SS",
      "vague_statement": "what was said vaguely",
      "concrete_resolution": "what it actually means technically",
      "component_affected": "which system/service"
    }
  ],
  "action_items": [
    {
      "timestamp": "HH:MM:SS",
      "task": "what needs to be done",
      "owner": "person name or team",
      "deadline": "date or sprint if mentioned",
      "priority": "high|medium|low",
      "jira_story_points": 3
    }
  ],
  "concepts": ["concept1", "concept2"]
}"""


class AnalysisAgent:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = "gpt-4o"

    async def analyze(self, transcript: dict, frames_dir: Path, metadata: dict) -> dict:
        """Analyze transcript + frames with GPT-4o vision."""
        frames_dir = Path(frames_dir)
        frame_files = sorted(frames_dir.glob("*.jpg"))[:20]  # Max 20 frames per API call

        # Build message content
        content = []

        # Add metadata context
        content.append({
            "type": "text",
            "text": f"""=== VIDEO METADATA ===
Title: {metadata.get('title', 'Unknown')}
Duration: {metadata.get('duration_seconds', 0) // 60} minutes
Source: {metadata.get('source', 'unknown')}

=== TIMESTAMPED TRANSCRIPT ===
{self._format_transcript(transcript)}

=== KEYFRAME ANALYSIS ===
The following are screenshots extracted every 30 seconds from the video.
Analyze them for: diagrams, whiteboards, code, slides, architecture drawings.
"""
        })

        # Add keyframe images
        for i, frame_path in enumerate(frame_files):
            timestamp_sec = i * 30
            h, m, s = timestamp_sec // 3600, (timestamp_sec % 3600) // 60, timestamp_sec % 60
            ts = f"{h:02d}:{m:02d}:{s:02d}"

            with open(frame_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            content.append({
                "type": "text",
                "text": f"[Frame at {ts}]:"
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}",
                    "detail": "low"  # Use "high" for detailed diagram analysis
                }
            })

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=4000,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": content}
            ],
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Attempt to extract JSON from markdown fences
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse analysis JSON: {raw[:200]}")

    def _format_transcript(self, transcript: dict) -> str:
        """Format transcript segments into readable text with timestamps."""
        segments = transcript.get("segments", [])
        if not segments:
            return transcript.get("text", "No transcript available")

        lines = []
        for seg in segments:
            ts = seg.get("timestamp", "00:00:00")
            text = seg.get("text", "").strip()
            if text:
                lines.append(f"[{ts}] {text}")

        return "\n".join(lines)
