"""
The Pitch Visualizer — FastAPI Application
==========================================
Ingests narrative text → segments → engineers prompts → generates images → storyboard
Best-approach: 3-call LLM strategy + spaCy segmentation + async image generation
"""

import asyncio
import base64
import json
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from image_generator import generate_image
from prompt_engineer import engineer_prompts_three_call
from segmenter import segment_narrative

load_dotenv()

app = FastAPI(title="The Pitch Visualizer", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

templates = Jinja2Templates(directory="templates")

STYLES = {
    "digital_art": "professional digital art, clean lines, vibrant colors, concept art, trending on ArtStation",
    "cinematic": "cinematic photography, dramatic lighting, 35mm film, anamorphic lens, movie still",
    "watercolor": "soft watercolor illustration, painterly, pastel tones, artistic, hand-painted",
    "comic": "comic book illustration, bold outlines, halftone dots, expressive, graphic novel style",
    "photorealistic": "photorealistic, ultra-detailed, 8K resolution, professional photography, hyperrealistic",
}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "styles": STYLES}
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    narrative: str = Form(...),
    style: str = Form("digital_art"),
):
    """Non-streaming: generate all panels, return full storyboard page."""
    style_token = STYLES.get(style, STYLES["digital_art"])
    scenes = segment_narrative(narrative)
    engineered = await engineer_prompts_three_call(narrative, scenes, style_token)
    panels = []
    session_id = uuid.uuid4().hex[:8]

    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [
            generate_image(client, ep["prompt"], i, session_id)
            for i, ep in enumerate(engineered)
        ]
        image_paths = await asyncio.gather(*tasks)

    for i, (ep, img_path) in enumerate(zip(engineered, image_paths)):
        panels.append(
            {
                "index": i + 1,
                "scene_text": ep["scene_text"],
                "engineered_prompt": ep["prompt"],
                "image_url": f"/outputs/{Path(img_path).name}" if img_path else None,
                "image_b64": ep.get("image_b64"),
            }
        )

    return templates.TemplateResponse(
        "storyboard.html",
        {
            "request": request,
            "panels": panels,
            "narrative": narrative,
            "style": style,
            "style_token": style_token,
        },
    )


@app.post("/generate-stream")
async def generate_stream(
    narrative: str = Form(...),
    style: str = Form("digital_art"),
):
    """Streaming: panels appear one-by-one via Server-Sent Events."""
    style_token = STYLES.get(style, STYLES["digital_art"])

    async def event_stream() -> AsyncGenerator[str, None]:
        scenes = segment_narrative(narrative)
        yield f"data: {json.dumps({'type': 'scenes_ready', 'count': len(scenes)})}\n\n"

        engineered = await engineer_prompts_three_call(narrative, scenes, style_token)
        yield f"data: {json.dumps({'type': 'prompts_ready', 'count': len(engineered)})}\n\n"

        session_id = uuid.uuid4().hex[:8]

        async def gen_one(client, ep, idx):
            img_path = await generate_image(client, ep["prompt"], idx, session_id)
            return img_path

        async with httpx.AsyncClient(timeout=60) as client:
            for i, ep in enumerate(engineered):
                img_path = await gen_one(client, ep, i)
                panel = {
                    "type": "panel",
                    "index": i + 1,
                    "total": len(engineered),
                    "scene_text": ep["scene_text"],
                    "engineered_prompt": ep["prompt"],
                    "image_url": f"/outputs/{Path(img_path).name}"
                    if img_path
                    else None,
                }
                yield f"data: {json.dumps(panel)}\n\n"

        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)