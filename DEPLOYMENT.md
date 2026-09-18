# Deploying PH Trend Hunter to Vercel (with Free Vercel Postgres)

This project is configured to run on **Vercel** using **Vercel Serverless Functions**, **Vercel Cron Jobs**, and **Vercel Postgres (Neon)** on the free tier.

---

## 1. Prerequisites
- A free [Vercel account](https://vercel.com).
- GitHub repository with this codebase (or Vercel CLI).

---

## 2. Step-by-Step Deployment

### Option A: Via Vercel Web Dashboard (Easiest)

1. **Push to GitHub**:
   ```bash
   cd /Users/vyacheslavzgordan/.gemini/antigravity/scratch/ph-trend-hunter
   git init
   git add .
   git commit -m "Initial commit of PH Trend Hunter"
   # Push to your GitHub repo
   ```

2. **Import into Vercel**:
   - Go to [vercel.com/new](https://vercel.com/new).
   - Select your GitHub repository.
   - Leave build settings as default (Vercel will detect `api/index.py` and `vercel.json`).
   - Click **Deploy**.

3. **Attach Free Vercel Postgres**:
   - In your project's dashboard on Vercel, navigate to the **Storage** tab.
   - Click **Create Database** -> Select **Postgres (Powered by Neon)**.
   - Choose the **Hobby (Free)** tier.
   - Click **Continue** and attach it to your project (`Production`, `Preview`, and `Development` environments).
   - *Vercel automatically sets `POSTGRES_URL` in your environment variables.*

4. **Redeploy**:
   - Go to the **Deployments** tab and trigger a redeploy (or push a commit).
   - The app will automatically connect to Vercel Postgres, initialize tables, and start tracking!

---

### Option B: Via Vercel CLI

```bash
# Install vercel CLI if not already installed
npm i -g vercel

# In project directory
cd /Users/vyacheslavzgordan/.gemini/antigravity/scratch/ph-trend-hunter

# Login and deploy
vercel

# Follow prompts to link project and deploy
```

---

## 3. How Autonomous Execution Runs on Vercel

In [`vercel.json`](vercel.json):

```json
{
  "crons": [
    {
      "path": "/api/cron",
      "schedule": "5 0 * * *"
    }
  ]
}
```

- Every day at **00:05 UTC** (shortly after Product Hunt's daily leaderboard rollover), Vercel Cron sends a `GET /api/cron` request.
- The serverless handler in [`api/index.py`](api/index.py) executes:
  1. Ingests today's top winners into Vercel Postgres.
  2. Runs the Day 10 Genesis or Day 11+ calibration engine.
  3. Updates hypotheses confidence scores and logs the daily report.
- You can inspect the cron execution history in the Vercel Dashboard under **Settings > Cron Jobs**.
