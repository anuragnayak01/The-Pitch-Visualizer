"""
prompt_engineer.py — 3-Call LLM Prompt Engineering Strategy
=============================================================
Based on StoryDiffusion research (NeurIPS 2024) and best practices:

  Call 1 — Extract global anchors (style/character/setting) from full narrative
  Call 2 — Confirm and map scenes to visual archetypes
  Call 3 — For each scene, build anatomically correct visual prompt using anchors

Prompt anatomy (per StoryDiffusion research):
  [Subject + action] + [specific setting + env detail] + [lighting/mood] + [style token] + [negatives]

This 3-call pattern produces measurably more consistent and vivid outputs
than a single naive "make this visual" call.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import List, Dict, Any

import httpx

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"
HEADERS = {
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01",
}


async def _call_llm(client: httpx.AsyncClient, system: str, user: str, max_tokens: int = 1024) -> str:
    """Make a single async call to the Claude API."""
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    resp = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"].strip()


async def engineer_prompts_three_call(
    narrative: str,
    scenes: List[str],
    style_token: str,
) -> List[Dict[str, Any]]:
    """
    3-call LLM strategy to engineer high-quality visual prompts.

    Returns a list of dicts: [{scene_text, prompt}, ...]
    """
    async with httpx.AsyncClient() as client:
        # ── CALL 1: Extract global visual anchors from the full narrative ──
        anchors_raw = await _call_llm(
            client,
            system=(
                "You are a visual creative director. Extract consistent visual anchors "
                "from a narrative so that every panel in a storyboard looks coherent. "
                "Return ONLY valid JSON with keys: character_description, setting_palette, "
                "lighting_mood, atmosphere. No markdown, no explanation."
            ),
            user=(
                f"Extract visual anchors from this narrative:\n\n{narrative}\n\n"
                "Return JSON only. Example: "
                '{"character_description": "...", "setting_palette": "...", '
                '"lighting_mood": "...", "atmosphere": "..."}'
            ),
            max_tokens=512,
        )

        try:
            # Strip any accidental markdown fences
            clean = re.sub(r"```json|```", "", anchors_raw).strip()
            anchors = json.loads(clean)
        except json.JSONDecodeError:
            # Fallback anchors if JSON parsing fails
            anchors = {
                "character_description": "a professional business person",
                "setting_palette": "modern corporate environment, neutral tones",
                "lighting_mood": "soft natural lighting",
                "atmosphere": "confident, optimistic",
            }

        # ── CALL 2: Map each scene to a visual archetype / composition type ──
        scenes_json = json.dumps(scenes)
        archetypes_raw = await _call_llm(
            client,
            system=(
                "You are a storyboard director. For each scene, identify the best "
                "visual composition: close-up, wide shot, over-shoulder, aerial, etc. "
                "Return ONLY a JSON array of strings matching the input array length."
            ),
            user=(
                f"Scenes: {scenes_json}\n\n"
                "Return a JSON array of composition types, one per scene. "
                'Example: ["wide establishing shot", "close-up reaction", "aerial overview"]'
            ),
            max_tokens=256,
        )

        try:
            clean = re.sub(r"```json|```", "", archetypes_raw).strip()
            archetypes = json.loads(clean)
            if not isinstance(archetypes, list) or len(archetypes) != len(scenes):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            archetypes = ["wide shot"] * len(scenes)

        # ── CALL 3: Build each per-scene prompt using the anatomy ──
        prompt_tasks = [
            _build_scene_prompt(
                client=client,
                scene_text=scene,
                archetype=archetypes[i] if i < len(archetypes) else "wide shot",
                anchors=anchors,
                style_token=style_token,
                panel_index=i + 1,
                total_panels=len(scenes),
            )
            for i, scene in enumerate(scenes)
        ]
        engineered_prompts = await asyncio.gather(*prompt_tasks)

    return [
        {"scene_text": scenes[i], "prompt": engineered_prompts[i]}
        for i in range(len(scenes))
    ]


async def _build_scene_prompt(
    client: httpx.AsyncClient,
    scene_text: str,
    archetype: str,
    anchors: Dict[str, Any],
    style_token: str,
    panel_index: int,
    total_panels: int,
) -> str:
    """Build a single, anatomically correct visual prompt for one scene."""
    prompt = await _call_llm(
        client,
        system=(
            "You are a professional AI image prompt engineer. "
            "Create a single, vivid, detailed visual prompt for a storyboard panel. "
            "Follow this exact anatomy:\n"
            "[Visual subject + specific action] + [detailed setting with environmental elements] "
            "+ [lighting and mood] + [style token] + [technical quality terms]\n"
            "The style token MUST appear verbatim at the end. "
            "Output ONLY the prompt text. No explanation, no quotes, no punctuation at start."
        ),
        user=(
            f"Scene text: {scene_text}\n"
            f"Composition: {archetype}\n"
            f"Character: {anchors.get('character_description', '')}\n"
            f"Setting palette: {anchors.get('setting_palette', '')}\n"
            f"Lighting mood: {anchors.get('lighting_mood', '')}\n"
            f"Atmosphere: {anchors.get('atmosphere', '')}\n"
            f"Style token (include verbatim): {style_token}\n"
            f"Panel {panel_index} of {total_panels}\n\n"
            "Write the complete visual prompt now:"
        ),
        max_tokens=256,
    )
    return prompt