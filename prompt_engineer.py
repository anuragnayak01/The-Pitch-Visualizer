"""
prompt_engineer.py — 3-Call LLM Prompt Engineering Strategy
=============================================================
Uses Pollinations.ai FREE text API — no API key required!
Endpoint: https://text.pollinations.ai/

Based on StoryDiffusion research (NeurIPS 2024) and best practices:

  Call 1 — Extract global anchors (style/character/setting) from full narrative
  Call 2 — Confirm and map scenes to visual archetypes
  Call 3 — For each scene, build anatomically correct visual prompt using anchors

Prompt anatomy (per StoryDiffusion research):
  [Subject + action] + [specific setting + env detail] + [lighting/mood] + [style token] + [negatives]
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import List, Dict, Any

import httpx

# Pollinations.ai free text API — no API key needed
POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/"
MODEL = "openai"  # Uses GPT-4o under the hood, completely free


async def _call_llm(
    client: httpx.AsyncClient,
    system: str,
    user: str,
    max_tokens: int = 1024,
    retries: int = 3,
) -> str:
    """Make a single async call to Pollinations.ai text API."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }

    for attempt in range(retries):
        try:
            resp = await client.post(
                POLLINATIONS_TEXT_URL,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()

            # Pollinations returns plain text or JSON depending on request
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                data = resp.json()
                # Handle OpenAI-style response format
                if "choices" in data:
                    return data["choices"][0]["message"]["content"].strip()
                # Handle simple text response
                if "text" in data:
                    return data["text"].strip()
                return str(data).strip()
            else:
                # Plain text response
                return resp.text.strip()

        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)  # exponential backoff
                continue
            print(f"[Pollinations LLM] Error after {retries} attempts: {e}")
            return ""

    return ""


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
                "lighting_mood, atmosphere. No markdown, no explanation, no extra text."
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
            clean = re.sub(r"```json|```", "", anchors_raw).strip()
            # Extract JSON object if extra text is present
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match:
                clean = match.group(0)
            anchors = json.loads(clean)
        except (json.JSONDecodeError, AttributeError):
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
                "Return ONLY a JSON array of strings matching the input array length. "
                "No markdown, no explanation, no extra text."
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
            match = re.search(r'\[.*\]', clean, re.DOTALL)
            if match:
                clean = match.group(0)
            archetypes = json.loads(clean)
            if not isinstance(archetypes, list) or len(archetypes) != len(scenes):
                raise ValueError("Invalid archetypes format")
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

    # Fallback if LLM returns empty
    if not prompt:
        prompt = (
            f"{scene_text}, {anchors.get('setting_palette', 'modern setting')}, "
            f"{anchors.get('lighting_mood', 'natural lighting')}, {style_token}"
        )

    return prompt