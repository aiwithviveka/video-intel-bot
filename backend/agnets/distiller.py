"""
Agent 4 — DistillerAgent
Post-processes the raw analysis:
- Deduplicates decisions
- Scores and ranks items by importance
- Validates action items have required fields
- Enriches Jira fields (labels, components, story points)
"""

import os
import json
from openai import AsyncOpenAI


DISTILL_SYSTEM = """You are a technical program manager. Given a raw analysis of a technical meeting,
clean and enrich it to make it production-ready.

Tasks:
1. Remove duplicate or near-duplicate decisions/action items
2. Assign Jira labels from this set: [backend, frontend, infra, security, performance, database, api, auth, testing, devops]
3. Fill in missing story_points estimates (1-13 fibonacci) based on complexity
4. Identify which Jira issue type each action_item maps to: Story | Task | Bug | Spike
5. Add a "component" field to each action_item (which service/repo it affects)
6. Sort decisions by impact (high first)
7. For each magic_to_system item, suggest a concrete follow-up action

Return the enriched JSON keeping the same schema, with these additions per action_item:
- "jira_issue_type": "Story|Task|Bug|Spike"
- "jira_labels": ["label1"]
- "jira_component": "service-name"
- "jira_story_points": number

Return ONLY valid JSON."""


class DistillerAgent:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def distill(self, analysis: dict) -> dict:
        """Enrich and clean the raw analysis output."""
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",  # cheaper model fine for this cleanup step
            max_tokens=3000,
            messages=[
                {"role": "system", "content": DISTILL_SYSTEM},
                {"role": "user", "content": f"Raw analysis:\n{json.dumps(analysis, indent=2)}"}
            ],
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content
        try:
            enriched = json.loads(raw)
        except json.JSONDecodeError:
            # Fall back to original if distillation fails
            enriched = analysis

        # Merge any fields the distiller dropped
        for key in analysis:
            if key not in enriched:
                enriched[key] = analysis[key]

        return enriched
