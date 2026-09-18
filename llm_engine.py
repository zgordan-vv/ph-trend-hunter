"""
LLM Reasoning Layer for Product Hunt Trend Hunter.
Uses Google Gemini (or compatible LLM) to provide qualitative analysis,
uncover subtle positioning nuances, and formulate novel hypotheses.
Falls back cleanly to heuristic NLP when no API key is configured.
"""

import json
import os
import urllib.request
from typing import Dict, List, Any, Optional


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def call_gemini(prompt: str, temperature: float = 0.4) -> Optional[str]:
    """Invokes Gemini REST API directly with standard library (no extra SDK required)."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    # Using Gemini 2.5 Flash endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 1200
        }
    }
    
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except Exception as e:
        print(f"[LLM Error] Failed to call Gemini API: {e}")
        return None

    return None


def generate_genesis_llm_insights(day_10_date: str, total_products: int, winners: List[Dict[str, Any]]) -> Optional[str]:
    """Generates deep qualitative insights for Day 10 Genesis report using an LLM."""
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        return None

    winners_text = "\n".join([
        f"- Day {w.get('date')}: '{w.get('name')}' ({w.get('archetype')}) — Tagline: \"{w.get('tagline')}\" ({w.get('votes_count')} votes, {w.get('comments_count')} comments)"
        for w in winners
    ])

    prompt = f"""You are an expert venture investor and product strategist analyzing 10 continuous days of Product Hunt daily #1 winners.
Here are the 10 daily winners:
{winners_text}

Task:
Provide a concise, sharp analysis answering: "Why did these winners win over the competition?"
1. Identify the 2-3 psychological or positioning levers that worked across all 10 winners.
2. Note what failed or lost traction (e.g., generic AI wrappers vs vertical utilities).
3. Formulate 1 non-obvious hypothesis about where startup launch strategies are heading.

Write in a crisp, direct, analytical tone without marketing fluff or hype clichés."""

    return call_gemini(prompt)


def generate_daily_calibration_llm_insights(
    day_number: int,
    date_str: str,
    winner: Dict[str, Any],
    runner_ups: List[Dict[str, Any]],
    active_hypotheses: List[Dict[str, Any]]
) -> Optional[str]:
    """Uses LLM to evaluate today's winners against active beliefs and identify subtle shifts."""
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        return None

    hyps_summary = "\n".join([
        f"- [{h.get('status')}] {h.get('title')}: {h.get('statement')} (Confidence: {int(h.get('confidence_score', 0.5)*100)}%)"
        for h in active_hypotheses
    ])

    runners_summary = "\n".join([
        f"#{p.get('rank')} '{p.get('name')}' ({p.get('archetype')}): \"{p.get('tagline')}\" ({p.get('votes_count')} votes)"
        for p in runner_ups
    ])

    prompt = f"""You are evaluating Day {day_number} of Product Hunt launches ({date_str}).

Today's #1 Winner:
- Name: {winner.get('name')}
- Archetype: {winner.get('archetype')}
- Tagline: "{winner.get('tagline')}"
- Votes: {winner.get('votes_count')} | Comments: {winner.get('comments_count')}

Top Contenders:
{runners_summary}

Active Hypotheses we are testing:
{hyps_summary}

Questions:
1. Did today's winner support or challenge our active hypotheses?
2. What specific messaging or positioning decision gave today's winner the edge over the runners-up?
3. Is there any emerging anomaly or subtle pattern that warrants a new hypothesis?

Respond in 3 concise, high-signal paragraphs."""

    return call_gemini(prompt)
