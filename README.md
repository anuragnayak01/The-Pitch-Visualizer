# 🎬 The Pitch Visualizer

> **Transform narrative text into visual storyboards — instantly.**

A FastAPI-powered web service that ingests a narrative paragraph, deconstructs it into scenes, engineers vivid AI image prompts via a **3-call LLM strategy**, and generates a multi-panel visual storyboard — with live panel-by-panel streaming.

---

## 🏆 What Makes This Stand Out

This implementation is grounded in the [StoryDiffusion (NeurIPS 2024)](https://github.com/HVision-NKU/StoryDiffusion) research on consistent image generation and implements the three highest-impact techniques from the literature:

| Feature | Implementation |
|---|---|
| **3-Call LLM Strategy** | Call 1: Extract visual anchors → Call 2: Scene composition types → Call 3: Per-scene anatomical prompt |
| **Visual Consistency** | Identical style token + character/setting anchors appended to every prompt |
| **Streaming UI** | Panels appear one-by-one via Server-Sent Events (SSE) |
| **Free Fallback** | Pollinations.ai (no API key, no signup required) |
| **Style Selector** | 5 visual styles: Digital Art, Cinematic, Watercolor, Comic, Photorealistic |

---

## 📐 Architecture Overview

```
User Input (Narrative Text + Style)
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  Stage 1 — Narrative Segmentation (spaCy)           │
│  • Sentence boundary detection with edge case       │
│    handling (abbreviations, quoted speech)          │
│  • Merges fragments, caps/expands scene count       │
└─────────────────────────┬───────────────────────────┘
                          │ scenes[]
                          ▼
┌─────────────────────────────────────────────────────┐
│  Stage 2 — 3-Call LLM Prompt Engineering (Claude)   │
│                                                     │
│  Call 1: Extract global anchors from full narrative │
│          → character, setting palette, mood         │
│                                                     │
│  Call 2: Map each scene to visual archetype         │
│          → close-up, wide shot, aerial, etc.        │
│                                                     │
│  Call 3: Build per-scene anatomical prompt          │
│          [Subject+action] + [Setting] + [Lighting]  │
│          + [Style Token] + [Quality terms]          │
└─────────────────────────┬───────────────────────────┘
                          │ engineered prompts[]
                          ▼
┌─────────────────────────────────────────────────────┐
│  Stage 3 — Parallel Image Generation                │
│  Priority: DALL-E 3 → Stability AI → Pollinations   │
│  All panels generated concurrently (async)          │
└─────────────────────────┬───────────────────────────┘
                          │ image files[]
                          ▼
┌─────────────────────────────────────────────────────┐
│  Stage 4 — Storyboard Presentation                  │
│  • Streaming SSE → panels appear one-by-one         │
│  • OR batch HTML response (Jinja2 template)         │
│  • CSS grid layout: image + caption + prompt view   │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- An Anthropic API key (for LLM prompt engineering)
- Optionally: OpenAI or Stability AI key for higher-quality images

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd pitch_visualizer

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy English model
python -m spacy download en_core_web_sm
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env with your keys
```

**Minimum requirement:** Set `ANTHROPIC_API_KEY`. The app will use **Pollinations.ai** (free) for images if no other image API key is set.

### 3. Run the Server

```bash
uvicorn app:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🎨 Usage

1. **Paste** a narrative paragraph (3–5 sentences work best)
2. **Choose** a visual style from the selector
3. **Select** mode: Live Streaming (panels appear one-by-one) or Batch
4. Click **Generate Storyboard**
5. Watch your storyboard come to life!

### Example Input

> A small retail company was struggling with inventory chaos that cost them thousands monthly. They adopted our AI platform and within two weeks, stockouts dropped by 40%. The team celebrated their first perfect quarter with zero overstocking incidents. Now they're expanding to three new locations, powered by data they finally trust. The future looks brighter than ever.

---

## 🔧 Design Choices

### Why spaCy over NLTK?
spaCy's sentence boundary detection handles edge cases like abbreviations (`Mr.`, `Inc.`), quoted speech, and acronyms significantly better than NLTK's `sent_tokenize`. This directly affects how cleanly narrative text divides into scenes.

### Why 3 LLM calls instead of 1?
Research on StoryDiffusion (NeurIPS 2024) shows that visual consistency across panels requires shared anchors (character appearance, color palette, lighting). A single LLM call produces inconsistent prompts. The 3-call pattern:
- **Call 1** extracts what stays the same (anchors)  
- **Call 2** determines composition per scene  
- **Call 3** builds each prompt using those anchors

### Prompt Anatomy
Each engineered prompt follows the structure proven to maximize image quality:
```
[Subject + action] + [Setting + environmental detail] + 
[Lighting + mood] + [Style token] + [Quality terms]
```
The style token is appended **identically** to every prompt, enforcing visual consistency across all panels.

### Why FastAPI over Flask?
FastAPI's native async support enables:
- Parallel image generation (all panels at once, not sequentially)
- Server-Sent Events for streaming panel delivery
- Better performance under load

Flask remains a simpler choice for MVPs (and is validated by StoryDiffusion's own implementation).

### Image API Priority
| API | Quality | Cost | API Key |
|---|---|---|---|
| DALL-E 3 | ⭐⭐⭐⭐⭐ | ~$0.04/image | Required |
| Stability AI SDXL | ⭐⭐⭐⭐ | ~$0.002/image | Required |
| Pollinations.ai (Flux) | ⭐⭐⭐ | Free | ❌ None needed |

---

## 📁 Project Structure

```
pitch_visualizer/
├── app.py                  # FastAPI application, routes, SSE stream
├── segmenter.py            # Narrative segmentation (spaCy + fallback)
├── prompt_engineer.py      # 3-call LLM prompt engineering strategy
├── image_generator.py      # Multi-API image generation with fallback
├── templates/
│   ├── index.html          # Main UI with form + streaming storyboard
│   └── storyboard.html     # Batch mode full storyboard page
├── static/
│   ├── style.css           # Cinematic dark theme CSS
│   └── script.js           # SSE streaming + UI interactions
├── outputs/                # Generated panel images (auto-created)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 📚 References & Research

- **StoryDiffusion** — Zhou et al., NeurIPS 2024 Spotlight  
  *Consistent Self-Attention for Long-Range Image and Video Generation*  
  https://github.com/HVision-NKU/StoryDiffusion

- **Pollinations.ai** — Free open-source GenAI platform  
  https://github.com/pollinations/pollinations

- **spaCy** — Industrial-strength NLP  
  https://spacy.io

- **FastAPI** — Modern async Python web framework  
  https://fastapi.tiangolo.com

---

## 📝 License

MIT License — free to use, modify, and distribute.