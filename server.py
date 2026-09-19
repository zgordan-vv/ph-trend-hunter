"""
FastAPI Server for Product Hunt Trend Hunter.
Natively supported by Vercel serverless and local uvicorn.
"""

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from db import (
    init_db, db_client, get_tracked_days_count,
    get_distinct_dates, set_state, get_state
)
from collector import seed_historical_data, fetch_live_producthunt
from scheduler import scheduler


app = FastAPI(title="PH Trend Hunter", description="Autonomous Product Hunt Evolutionary Intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
STATIC_DIR = os.path.join(BASE_DIR, "static")


@app.on_event("startup")
def on_startup():
    try:
        init_db()
        # In local non-Vercel environment, start background scheduler
        if not os.environ.get("VERCEL"):
            if get_tracked_days_count() == 0:
                seed_historical_data()
            scheduler.start()
    except Exception as e:
        print(f"[Startup Warning] {e}")


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    # Check public or static index.html
    for d in [PUBLIC_DIR, STATIC_DIR]:
        p = os.path.join(d, "index.html")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return "<h1>PH Trend Hunter</h1><p>index.html not found</p>"


@app.get("/api/cron")
@app.get("/api/cron/daily")
def handle_vercel_cron():
    """Daily cron endpoint invoked automatically by Vercel Cron at 00:05 UTC."""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        res = fetch_live_producthunt(today_str)
        set_state("last_run_time", datetime.utcnow().isoformat())
        set_state("last_run_status", f"Vercel Cron completed for {today_str}. Winner: {res.get('winner', 'N/A')}")
        return {"status": "success", "cron": "daily", "date": today_str, "result": res}
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/api/status")
def get_status():
    days_count = get_tracked_days_count()
    dates = get_distinct_dates()
    phase = "Genesis Achieved & Continuously Calibrating" if days_count >= 10 else f"Baseline Accumulation ({days_count}/10 days)"
    
    launches_row = db_client.fetchone("SELECT COUNT(*) as cnt FROM launches")
    total_launches = launches_row["cnt"] if launches_row else 0

    val_row = db_client.fetchone("SELECT COUNT(*) as cnt FROM hypotheses WHERE status = 'validated'")
    validated_hyps = val_row["cnt"] if val_row else 0

    act_row = db_client.fetchone("SELECT COUNT(*) as cnt FROM hypotheses WHERE status IN ('active', 'emerging')")
    active_hyps = act_row["cnt"] if act_row else 0

    return {
        "days_tracked": days_count,
        "distinct_dates": dates,
        "current_phase": phase,
        "total_launches": total_launches,
        "validated_hypotheses": validated_hyps,
        "active_hypotheses": active_hyps,
        "environment": "vercel_serverless" if os.environ.get("VERCEL") else "standalone",
        "database_type": "vercel_postgres" if db_client.use_pg else "sqlite",
        "scheduler": {
            "autonomous_running": True,
            "type": "Vercel Cron (Daily 00:05 UTC)" if os.environ.get("VERCEL") else "Background Daemon Thread",
            "last_run_time": get_state("last_run_time", "Vercel Cron active" if os.environ.get("VERCEL") else "Daemon active"),
            "last_run_status": get_state("last_run_status", "Autonomous schedule active")
        },
        "current_time_utc": datetime.utcnow().isoformat()
    }


@app.get("/api/conclusions")
def get_conclusions():
    query = """
    SELECT c.*, d.winner_name, d.winner_tagline
    FROM conclusions c
    LEFT JOIN daily_summaries d ON c.date = d.date
    ORDER BY c.day_number DESC
    """
    rows = db_client.fetchall(query)
    for r in rows:
        shift_query = """
        SELECT l.*, h.title as hypothesis_title, h.category as hypothesis_category
        FROM hypothesis_logs l
        JOIN hypotheses h ON l.hypothesis_id = h.id
        WHERE l.date = ?
        ORDER BY ABS(l.delta) DESC
        """
        shifts = db_client.fetchall(shift_query, (r["date"],))
        r["belief_shifts"] = shifts
        if isinstance(r.get("revised_theses"), str):
            try:
                r["revised_theses"] = json.loads(r["revised_theses"])
            except Exception:
                pass
    return {"conclusions": rows}


HYPOTHESIS_PLAYBOOKS = {
    "hyp_oss_momentum": {
        "what_it_means": "Products with open-source repositories and transparent self-hosting options outrank proprietary SaaS tools by converting developer skepticism into credibility.",
        "why_it_works": "Product Hunt voters on Tuesday-Thursday are heavily developer and tech-early-adopter biased. Open-source signals longevity, zero vendor lock-in, and auditability.",
        "founder_do": "Highlight GitHub stars, self-hosted Docker commands, or 'Apache 2.0 / MIT' in the first 2 sentences and media gallery.",
        "founder_dont": "Do not hide self-hosting behind an enterprise contact sales gate if positioning as open-source.",
        "good_example": "Supabase: 'The Open Source Firebase Alternative'",
        "bad_example": "Generic Cloud: 'The modern cloud data platform'"
    },
    "hyp_outcome_framing": {
        "what_it_means": "Framing your product around the end-state transformation ('Turn X into Y', 'Ship in minutes') captures twice as many top 2 finishes as listing internal software features.",
        "why_it_works": "Casual scrollers make voting decisions in under 2.5 seconds. Transformations paint an immediate mental picture of relief or superpower, whereas feature lists require cognitive work to decipher.",
        "founder_do": "Structure your tagline as: [Active Verb] + [Painful Input] into [Desired Desirable Outcome].",
        "founder_dont": "Avoid 'All-in-one platform for...', 'The next generation tool for...', or 'AI-powered suite'.",
        "good_example": "Lovable: 'Turn ideas into full-stack web apps in minutes'",
        "bad_example": "AppBuilder: 'An AI-powered integrated development environment with modular components'"
    },
    "hyp_discussion_velocity": {
        "what_it_means": "A healthy ratio of at least 10 comments per 100 upvotes separates durable community winners from artificial upvote spikes that collapse by evening.",
        "why_it_works": "Product Hunt's ranking algorithm penalizes vote bursts that lack organic creator dialogue, reply depth, and back-and-forth maker discussions.",
        "founder_do": "Reply to every single comment within 10 minutes with thoughtful questions, behind-the-scenes stories, or roadmaps.",
        "founder_dont": "Never drop generic 'Thanks for the support!' single-line replies that kill discussion threads.",
        "good_example": "Maker sharing origin failure story in first comment and asking users about their biggest workflow bottleneck.",
        "bad_example": "500 upvotes with only 12 bot-like congratulations comments."
    },
    "hyp_vertical_ai": {
        "what_it_means": "AI tools laser-focused on a single workflow or profession (e.g. immigration lawyer drafts, orthotist modeling) outperform general AI chatbots and prompt wrappers.",
        "why_it_works": "The community suffers from generic AI fatigue. A tool with tailored domain schemas and bespoke inputs solves a painful problem immediately without prompt engineering.",
        "founder_do": "Target one specific persona and show their exact pain being resolved with zero prompt setup.",
        "founder_dont": "Do not market as 'Your personal AI assistant for everything' or 'Universal AI productivity copilot'.",
        "good_example": "Klu.so: 'Turn customer support tickets into verified Jira bug reports'",
        "bad_example": "OmniGen: 'ChatGPT on steroids for modern professionals'"
    },
    "hyp_weekend_indie": {
        "what_it_means": "Saturday and Sunday feature lower vote volume hurdles, allowing niche creator utilities, fun indie apps, and developer micro-tools to clinch #1 easily.",
        "why_it_works": "Venture-backed B2B companies launch Tuesday through Thursday. Weekend traffic consists of makers, weekend hobbyists, and casual tech explorers looking for delight.",
        "founder_do": "Launch fun utilities, developer toys, audio/visual experimental tools, or open-source side projects on Saturday/Sunday.",
        "founder_dont": "Avoid launching heavyweight enterprise B2B compliance or sales software on a Sunday morning.",
        "good_example": "RetroSound 8-bit: 'Turn modern Spotify songs into authentic GameBoy chiptunes' (Weekend #1)",
        "bad_example": "Enterprise SOC2 Automated Compliance Monitor launching Sunday 00:01 PST."
    },
    "hyp_brevity_punch": {
        "what_it_means": "Taglines of 7 words or fewer convert higher on mobile cards and feed views because they avoid truncation and deliver an instant hook.",
        "why_it_works": "Over 60% of Product Hunt browsing happens on mobile devices or fast desktop skimming. Long taglines get cut off with ellipses or skipped altogether.",
        "founder_do": "Trim your tagline ruthlessly until every single remaining word carries functional weight.",
        "founder_dont": "Don't cram keywords, funding news, or multi-clause descriptions into the tagline.",
        "good_example": "Raycast: 'Your shortcut to everything' (4 words)",
        "bad_example": "Comprehensive desktop launcher tool designed to streamline developer workflows and app switching (12 words)"
    }
}


@app.get("/api/hypotheses")
def get_hypotheses():
    rows = db_client.fetchall("SELECT * FROM hypotheses ORDER BY confidence_score DESC")
    for r in rows:
        history_query = """
        SELECT l.id, l.date, l.day_number, l.old_confidence, l.new_confidence, l.delta, l.reason,
               p.id as launch_id, p.name as launch_name, p.tagline as launch_tagline, p.rank as launch_rank,
               p.votes_count as launch_votes, p.archetype as launch_archetype, p.framing_style as launch_framing
        FROM hypothesis_logs l
        LEFT JOIN launches p ON l.evidence_launch_id = p.id
        WHERE l.hypothesis_id = ?
        ORDER BY l.day_number DESC
        LIMIT 8
        """
        r["history"] = db_client.fetchall(history_query, (r["id"],))
        
        # Attach playbook
        playbook = HYPOTHESIS_PLAYBOOKS.get(r["id"])
        if not playbook:
            playbook = {
                "what_it_means": r.get("statement", ""),
                "why_it_works": "Empirical patterns observed across daily rank #1-#3 placements.",
                "founder_do": f"Align your launch positioning with {r.get('category', 'market dynamics')}.",
                "founder_dont": "Avoid generic untargeted messaging.",
                "good_example": "Leading rank #1 winner in this category.",
                "bad_example": "Lagging product with misplaced positioning."
            }
        r["playbook"] = playbook

    return {"hypotheses": rows}



@app.get("/api/launches")
def get_launches(date: Optional[str] = None):
    if date:
        rows = db_client.fetchall("SELECT * FROM launches WHERE date = ? ORDER BY rank ASC", (date,))
    else:
        latest = db_client.fetchone("SELECT DISTINCT date FROM launches ORDER BY date DESC LIMIT 1")
        if latest:
            rows = db_client.fetchall("SELECT * FROM launches WHERE date = ? ORDER BY rank ASC", (latest["date"],))
            date = latest["date"]
        else:
            rows = []
    for r in rows:
        if isinstance(r.get("topics"), str):
            try:
                r["topics"] = json.loads(r["topics"])
            except Exception:
                pass
    return {"launches": rows, "date": date}


@app.get("/api/trends")
def get_trends():
    archetype_stats = db_client.fetchall("""
    SELECT archetype, COUNT(*) as count
    FROM launches
    WHERE rank <= 3
    GROUP BY archetype
    ORDER BY count DESC
    """)
    framing_stats = db_client.fetchall("""
    SELECT framing_style, COUNT(*) as count
    FROM launches
    WHERE rank = 1
    GROUP BY framing_style
    ORDER BY count DESC
    """)
    vote_progression = db_client.fetchall("""
    SELECT d.date, d.day_number, d.median_votes, d.winner_name,
           (SELECT votes_count FROM launches l WHERE l.date = d.date AND l.rank = 1) as winner_votes
    FROM daily_summaries d
    ORDER BY d.date ASC
    """)
    return {
        "archetype_distribution": archetype_stats,
        "framing_distribution": framing_stats,
        "vote_progression": vote_progression
    }


@app.post("/api/chat")
async def handle_chat_query(request: Request):
    try:
        body = await request.json()
        message = body.get("message", "").strip()
        history = body.get("history", [])
        if not message:
            return JSONResponse({"status": "error", "error": "Message is required"}, status_code=400)
        
        from llm_engine import ask_ph_assistant
        result = ask_ph_assistant(message, history=history)
        return {
            "status": "success",
            "answer": result.get("answer"),
            "sources": result.get("sources", []),
            "learned": result.get("learned"),
            "found": result.get("found", False)
        }
    except Exception as e:
        import traceback
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)


@app.get("/api/chat/knowledge")
def get_user_knowledge_api():
    from db import get_all_user_knowledge
    return {"status": "success", "knowledge": get_all_user_knowledge()}


@app.post("/api/chat/clear-knowledge")
def clear_user_knowledge_api():
    from db import clear_all_user_knowledge
    clear_all_user_knowledge()
    return {"status": "success", "message": "Knowledge cleared"}



@app.post("/api/actions/trigger")
def trigger_cycle():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    res = fetch_live_producthunt(today_str)
    set_state("last_run_time", datetime.utcnow().isoformat())
    set_state("last_run_status", f"Manual run completed for {today_str}. Winner: {res.get('winner', 'N/A')}")
    return {"status": "success", "result": res}


@app.post("/api/actions/seed")
def seed_data():
    import traceback
    try:
        if db_client.use_pg:
            # Drop legacy tables with character restrictions and recreate fresh
            for table in ["hypotheses", "hypothesis_logs", "conclusions", "launches", "daily_summaries", "system_state"]:
                try:
                    db_client.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                except Exception:
                    pass
            init_db()
        res = seed_historical_data()
        return {"status": "success", "result": res}
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)


@app.post("/api/actions/autonomous-toggle")
def toggle_auto():
    if not os.environ.get("VERCEL"):
        if scheduler.running:
            scheduler.stop()
        else:
            scheduler.start()
        return {"status": "success", "autonomous_running": scheduler.running}
    return {"status": "success", "message": "On Vercel, autonomous mode is managed via Vercel Cron in vercel.json"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    init_db()
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
