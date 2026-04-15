"""
image_generator.py — Image Generation
=======================================
Primary:  OpenAI DALL-E 3 (best quality, requires API key)
Fallback: Pollinations.ai  (completely free, no API key needed)
           → https://image.pollinations.ai/prompt/{encoded_prompt}

Falls back automatically if OPENAI_API_KEY is not set.
"""

from __future__ import annotations

import os
import urllib.parse
import uuid
from pathlib import Path

import httpx

OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
STABILITY_KEY = os.getenv("STABILITY_API_KEY", "")

# Pollinations model: flux (best free model available as of 2025)
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


async def generate_image(
    client: httpx.AsyncClient,
    prompt: str,
    panel_index: int,
    session_id: str,
    width: int = 896,
    height: int = 504,
) -> str | None:
    """
    Generate an image for a given prompt.
    Returns local file path where image was saved, or None on failure.

    Priority:
      1. DALL-E 3 (if OPENAI_API_KEY set)
      2. Stability AI (if STABILITY_API_KEY set)
      3. Pollinations.ai (free, always available)
    """
    filename = f"panel_{session_id}_{panel_index:02d}_{uuid.uuid4().hex[:6]}.png"
    out_path = OUTPUTS_DIR / filename

    # Add universal negative prompt suffix
    negative_suffix = ", masterpiece, best quality, sharp focus"
    full_prompt = prompt + negative_suffix

    if OPENAI_KEY:
        result = await _dalle3(client, full_prompt, out_path)
        if result:
            return str(result)

    if STABILITY_KEY:
        result = await _stability(client, full_prompt, out_path, width, height)
        if result:
            return str(result)

    # Free fallback — always works
    result = await _pollinations(client, full_prompt, out_path, width, height, seed=panel_index * 42)
    return str(result) if result else None


async def _dalle3(client: httpx.AsyncClient, prompt: str, out_path: Path) -> Path | None:
    """Generate via OpenAI DALL-E 3."""
    try:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt[:4000],  # DALL-E 3 max prompt length
                "n": 1,
                "size": "1792x1024",
                "quality": "standard",
                "response_format": "url",
            },
            timeout=60,
        )
        if resp.status_code == 200:
            image_url = resp.json()["data"][0]["url"]
            img_resp = await client.get(image_url, timeout=30)
            if img_resp.status_code == 200:
                out_path.write_bytes(img_resp.content)
                return out_path
    except Exception as e:
        print(f"[DALL-E 3] Error: {e} — falling back")
    return None


async def _stability(client: httpx.AsyncClient, prompt: str, out_path: Path, w: int, h: int) -> Path | None:
    """Generate via Stability AI (SDXL)."""
    try:
        resp = await client.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers={
                "Authorization": f"Bearer {STABILITY_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "text_prompts": [
                    {"text": prompt, "weight": 1.0},
                    {"text": "blurry, low quality, watermark, text, distorted", "weight": -1.0},
                ],
                "cfg_scale": 7,
                "height": 576,
                "width": 1024,
                "samples": 1,
                "steps": 30,
            },
            timeout=60,
        )
        if resp.status_code == 200:
            import base64
            img_b64 = resp.json()["artifacts"][0]["base64"]
            out_path.write_bytes(base64.b64decode(img_b64))
            return out_path
    except Exception as e:
        print(f"[Stability] Error: {e} — falling back")
    return None


async def _pollinations(
    client: httpx.AsyncClient,
    prompt: str,
    out_path: Path,
    width: int,
    height: int,
    seed: int = 42,
) -> Path | None:
    """
    Generate via Pollinations.ai — completely FREE, no API key required.
    Uses the Flux model (best free model as of 2025).
    """
    try:
        encoded = urllib.parse.quote(prompt[:500])
        url = (
            f"{POLLINATIONS_BASE}/{encoded}"
            f"?width={width}&height={height}"
            f"&model=flux&seed={seed}&nologo=true&enhance=true"
        )
        resp = await client.get(url, timeout=90, follow_redirects=True)
        if resp.status_code == 200 and resp.content:
            out_path.write_bytes(resp.content)
            return out_path
    except Exception as e:
        print(f"[Pollinations] Error: {e}")
    return None