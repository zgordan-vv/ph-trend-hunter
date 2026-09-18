"""
Analyzer and feature extraction module for Product Hunt launches.
Computes positioning archetypes, tagline framing, and engagement metrics.
"""

import re
from typing import Dict, List, Any


ARCHETYPE_RULES = [
    ("Open Source Alternative", [
        r"\bopen[- ]source\b", r"\boss\b", r"\balternative to\b", r"\bself[- ]hosted\b", r"\bgithub\b"
    ]),
    ("Developer Tools & Infra", [
        r"\bapi\b", r"\bcli\b", r"\bdatabase\b", r"\bdev\b", r"\bdeveloper\b", r"\bsdk\b",
        r"\bcode\b", r"\bgit\b", r"\bbackend\b", r"\bdebugging\b", r"\bterminal\b", r"\bllm[- ]ops\b"
    ]),
    ("AI Agent & Autonomous Workflow", [
        r"\bagent\b", r"\bautonomous\b", r"\bworkflow\b", r"\bcopilot\b", r"\bai assistant\b",
        r"\bprompt\b", r"\bgpt\b", r"\bautomate\b", r"\bautopilot\b"
    ]),
    ("Design & Visual Generation", [
        r"\bdesign\b", r"\bui\b", r"\bux\b", r"\bfigma\b", r"\bvideo\b", r"\bimage\b",
        r"\bcanvas\b", r"\bmockup\b", r"\b3d\b", r"\banimation\b"
    ]),
    ("Creator & Content Studio", [
        r"\bcreator\b", r"\bpodcast\b", r"\byoutube\b", r"\bnewsletter\b", r"\baudio\b",
        r"\bvoice\b", r"\btranscription\b", r"\bcontent\b", r"\bsubstack\b"
    ]),
    ("Sales, CRM & Growth", [
        r"\bsales\b", r"\bcrm\b", r"\blead\b", r"\boutreach\b", r"\bgrowth\b", r"\bemail\b",
        r"\bconversion\b", r"\bprospect\b", r"\banalytics\b"
    ]),
    ("Micro-SaaS & Productivity", [
        r"\bnotion\b", r"\bnotes\b", r"\btasks\b", r"\bcalendar\b", r"\bproductivity\b",
        r"\bextension\b", r"\bbookmark\b", r"\bfinance\b", r"\binvoice\b"
    ])
]


def detect_archetype(name: str, tagline: str, description: str, topics: List[str]) -> str:
    combined_text = f"{name} {tagline} {description} {' '.join(topics)}".lower()
    
    # Priority check for open source positioning
    for archetype, patterns in ARCHETYPE_RULES:
        for p in patterns:
            if re.search(p, combined_text):
                return archetype
                
    return "Specialist Utility"


def detect_framing_style(tagline: str) -> str:
    t = tagline.lower()
    
    # Outcome-driven: "Turn X into Y", "Build in minutes", "Get X without Y"
    if re.search(r"\b(turn|build|create|generate|get|make|transform)\b.*\b(into|in|without|from|fast)\b", t):
        return "Outcome-Driven"
        
    # Problem-driven: "Stop X", "No more X", "Never lose X again", "Tired of"
    if re.search(r"\b(stop|no more|never|tired of|ditch|kill|fix)\b", t):
        return "Problem-Driven"
        
    # Analogy-driven: "Linear for X", "Stripe for Y", "Canva meets..."
    if re.search(r"\b(for|meets|like)\b.*(notion|stripe|linear|figma|airtable|slack|github)", t):
        return "Analogy-Driven"
        
    # Technical/Architecture: "Open-source", "Zero-config", "Rust-based", "Lightweight"
    if re.search(r"\b(open[- ]source|zero[- ]config|rust|lightweight|self[- ]hosted|privacy[- ]first)\b", t):
        return "Technical-Credibility"
        
    # Feature-list description: "The all-in-one platform for..."
    if re.search(r"\b(all[- ]in[- ]one|platform|tool for|suite|simple)\b", t):
        return "Feature-Descriptor"
        
    return "Direct-Utility"


def analyze_launch(launch: Dict[str, Any]) -> Dict[str, Any]:
    """Enriches a raw launch record with semantic attributes."""
    name = launch.get("name", "")
    tagline = launch.get("tagline", "")
    description = launch.get("description", "")
    topics = launch.get("topics", [])
    if isinstance(topics, str):
        import json
        try:
            topics = json.loads(topics)
        except Exception:
            topics = [topics]
            
    votes = launch.get("votes_count", 0)
    comments = launch.get("comments_count", 0)
    
    archetype = detect_archetype(name, tagline, description, topics)
    framing = detect_framing_style(tagline)
    
    # Engagement ratio: comments per 100 upvotes
    engagement_ratio = round((comments / max(1, votes)) * 100, 1)
    
    words_in_tagline = len(tagline.split())
    tagline_brevity = "punchy (<7 words)" if words_in_tagline <= 7 else "detailed (8-14 words)" if words_in_tagline <= 14 else "long (>14 words)"
    
    return {
        **launch,
        "archetype": archetype,
        "framing_style": framing,
        "engagement_ratio": engagement_ratio,
        "tagline_brevity": tagline_brevity,
        "words_in_tagline": words_in_tagline
    }
