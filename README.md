# Product Hunt Trend Hunter 🚀

An autonomous web service and intelligence engine that tracks Product Hunt daily, discovers underlying trends, and continuously evolves its understanding of **why winners win**.

---

## How It Works Autonomously

1. **Daily Autonomous Ingestion**:
   - Runs a background daemon thread that wakes up every day at the Product Hunt daily reset (00:05 UTC).
   - Ingests top finishes (ranks #1–#10), votes, comment counts, taglines, makers, and topics into a persistent SQLite database.
   - Extracts semantic traits: positioning archetype (Open-Source Alternative, AI Agent, Dev Tools, Micro-SaaS), copy framing style (Outcome-Driven, Problem-Driven, Technical), and discussion ratio.

2. **The 10-Day Genesis Milestone**:
   - **Days 1–9**: Gathers baseline distributions across weekday and weekend launch cycles.
   - **Day 10**: Formulates its foundational model ("Genesis Synthesis"), synthesizing the initial 100 products and introducing 6 core hypotheses with baseline empirical confidence scores.

3. **Continuous Daily Calibration (Day 11+)**:
   - On every subsequent day, the engine takes the new day's winners and tests them against all active hypotheses.
   - Computes Bayesian-style confidence updates:
     - Increases confidence for confirmed hypotheses (with supporting evidence logged).
     - Decreases confidence for challenged/contradicted patterns.
     - Automatically spawns emerging hypotheses when novel winner archetypes appear.
     - Generates an Evolutionary Conclusions Report detailing what held up today, what broke, and what the updated thesis is.

4. **Web Dashboard**:
   - Real-time interactive dashboard accessible via browser at `http://localhost:8000`.
   - **Evolutionary Conclusions Timeline**: Side-by-side view of Day 10 Genesis and subsequent daily calibrations with belief shift indicators.
   - **Living Hypotheses Board**: Filter by Validated, Active, Emerging, or Refuted with visual confidence bars.
   - **Daily Winners Explorer**: Browse any tracked day's leaderboard with archetypes and copy framing badges.
   - **Macro Trends**: Charting winning archetype shares, framing styles, and upvote progression.
   - **System Controls**: Autonomous runner controls and manual execution trigger.

---

## Quick Start

### Running Locally

```bash
# 1. Navigate to the project directory
cd /Users/vyacheslavzgordan/.gemini/antigravity/scratch/ph-trend-hunter

# 2. Start the autonomous web service
./start.sh
# or: python3 server.py
```

Open your browser at **`http://localhost:8000`**.

### Running with Docker

```bash
docker build -t ph-trend-hunter .
docker run -p 8000:8000 ph-trend-hunter
```

---

## REST API Endpoints

- `GET /api/status`: System state, tracked days count, active hypotheses, scheduler health.
- `GET /api/conclusions`: Genesis report and daily calibration reports with belief shift details.
- `GET /api/hypotheses`: Living hypotheses with confidence scores and evidence logs.
- `GET /api/launches?date=YYYY-MM-DD`: Winners and metadata for a specific date.
- `GET /api/trends`: Distribution metrics for archetypes, framing styles, and vote progression.
- `POST /api/actions/trigger`: Manually trigger today's ingestion and calibration cycle.
- `POST /api/actions/seed`: Re-seed the 14-day continuous evolution dataset.
- `POST /api/actions/autonomous-toggle`: Pause or resume the autonomous daily scheduler.
