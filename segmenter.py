"""
segmenter.py — Narrative Segmentation
======================================
Uses spaCy for robust sentence segmentation (handles abbreviations, quoted speech,
edge cases far better than simple split() or NLTK sentence tokenizer).

Each sentence becomes a discrete scene object.
"""

from __future__ import annotations

import re
from typing import List


def segment_narrative(text: str, max_scenes: int = 6, min_scenes: int = 3) -> List[str]:
    """
    Segment narrative text into logical scenes using spaCy.
    Falls back to regex-based splitting if spaCy is unavailable.

    Args:
        text: Input narrative paragraph (3-5 sentences ideally)
        max_scenes: Cap scenes to avoid too many API calls
        min_scenes: Ensure at least this many scenes

    Returns:
        List of scene strings
    """
    try:
        import spacy  # type: ignore
        # Try to load English model; fall back to blank if not downloaded
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            nlp = spacy.blank("en")
            # Add sentencizer as fallback
            if "sentencizer" not in nlp.pipe_names:
                nlp.add_pipe("sentencizer")

        doc = nlp(text.strip())
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    except ImportError:
        # Pure regex fallback — handles most punctuation edge cases
        sentences = _regex_segment(text)

    # Merge very short fragments (< 20 chars) with the previous sentence
    merged = _merge_short_fragments(sentences, min_len=20)

    # If too many scenes, combine adjacent pairs
    while len(merged) > max_scenes:
        merged = _combine_adjacent_pairs(merged)

    # If too few, try splitting on semicolons / em-dashes
    if len(merged) < min_scenes:
        merged = _expand_with_clauses(merged, target=min_scenes)

    return merged[:max_scenes]


def _regex_segment(text: str) -> List[str]:
    """Regex-based sentence splitter as fallback."""
    # Split on sentence-ending punctuation followed by whitespace and capital letter
    pattern = r'(?<=[.!?])\s+(?=[A-Z])'
    parts = re.split(pattern, text.strip())
    return [p.strip() for p in parts if p.strip()]


def _merge_short_fragments(sentences: List[str], min_len: int = 20) -> List[str]:
    """Merge sentences that are too short into the previous one."""
    if not sentences:
        return sentences
    result = [sentences[0]]
    for s in sentences[1:]:
        if len(s) < min_len and result:
            result[-1] = result[-1].rstrip() + " " + s
        else:
            result.append(s)
    return result


def _combine_adjacent_pairs(sentences: List[str]) -> List[str]:
    """Combine adjacent pairs of sentences to reduce total count."""
    result = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            result.append(sentences[i] + " " + sentences[i + 1])
        else:
            result.append(sentences[i])
    return result


def _expand_with_clauses(sentences: List[str], target: int) -> List[str]:
    """Try splitting on semicolons or em-dashes to get more scenes."""
    expanded = []
    for s in sentences:
        sub = re.split(r'[;—]', s)
        sub = [p.strip() for p in sub if p.strip()]
        if len(sub) > 1:
            expanded.extend(sub)
        else:
            expanded.append(s)
        if len(expanded) >= target:
            break
    return expanded if len(expanded) >= target else sentences