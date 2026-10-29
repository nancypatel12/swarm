# Deploy

How Swarm goes online and stays up, free to use and free to host, through the end of judging (December 15, 2026).

## What runs where

| Part | Where | Cost |
|---|---|---|
| API | Render, free web plan, from `render.yaml` | $0 |
| Page | Vercel, free plan | $0 |
| Model calls | Nebius Token Factory, as always | Your credits, capped by Swarm's budgets |

Every run still calls Nemotron on Nebius Token Factory, which is what the rules require. Other hosts were ruled out by cost: Nebius AI Cloud endpoints default to an H100, the smallest CPU machine kept up for seven weeks costs more than the builder credits, and Hugging Face now charges for Docker Spaces.

Render's free plan is small (0.1 CPU, 512 MB), which is enough: a run spends almost all its time waiting on Nemotron and Tavily.

## 01. Deploy the API on Render

1. Sign in at [render.com](https://render.com) with GitHub. Render may ask for a card to verify the account; the free plan doesn't charge it.
2. Choose **New → Blueprint**, connect the `nancypatel12/swarm` repository, and let Render read `render.yaml`.
3. Render asks for the values marked `sync: false`:

| Name | Value |
|---|---|
| `NEBIUS_API_KEY` | Your Token Factory key |
| `TAVILY_API_KEY` | Your Tavily key |
| `FRONTEND_ORIGINS` | Leave blank for now; set it in step 02 |

4. **Apply.** The build takes a few minutes. When the service is **Live**, `https://swarm-api.onrender.com/api/health` (or the address Render shows) returns `{"ok": true, "accepting": true}`.

The model names, `SWARM_TRUST_PROXY=1` and the health check come from `render.yaml`. Render sits behind Cloudflare, so each visitor is told apart by the `CF-Connecting-IP` header Cloudflare sets.

Render's disk doesn't survive a restart or a new deploy: runs saved by visitors, and the spend ledger, start over. The example is in the image, so it always works, and the prepaid Nebius credits stay the hard limit.

## 02. Deploy the page on Vercel

1. Sign in at [vercel.com](https://vercel.com) with GitHub and choose **Add New → Project**.
2. Import `nancypatel12/swarm`.
3. **Root Directory:** `frontend`. Framework: Next.js, detected automatically.
4. **Environment variable:** `NEXT_PUBLIC_API_URL` = the API's address from step 01, with no slash at the end.
5. **Deploy**, and note the production address, such as `https://swarm-<something>.vercel.app`.
6. Back on Render, set `FRONTEND_ORIGINS` to that address under the service's **Environment**. Render redeploys with it.

`NEXT_PUBLIC_API_URL` is built into the page, so changing it means redeploying the page.

## 03. Keep it awake

Render's free plan sleeps after 15 minutes without visitors, and the next visitor waits about a minute. In the GitHub repository, open **Settings → Secrets and variables → Actions → Variables** and add `API_URL` = the API's address. The "Keep the API awake" workflow then calls the health check every 10 minutes. One always-on free service fits inside Render's 750 free hours a month.

## 04. The budget

Two locks, so nobody can spend more than you meant to.

**On Nebius, first:** keep the account on prepaid credits, with no card on file and auto top-up off. Then the most anyone can spend is the credits already there; Nebius stops serving when they run out. Do the same on Tavily, or stay on its free plan.

**In Swarm:** every new run checks, in order, the pause switch, the total budget, today's budget, the visitor's runs today and the runs this hour. Tokens are written to `SWARM_DATA_DIR/spend.json` after every model call, so restarting the server process doesn't reset them; on a free Space, a full restart of the Space does, which is why the Nebius lock comes first. When a limit is hit, visitors see a plain message, the status line says "Examples only, new runs paused", and the example and every saved link keep working. A run that has started finishes even if it crosses a budget, so leave a margin.

| Setting | Default | About |
|---|---|---|
| `SWARM_TOTAL_TOKENS` | 20,000,000 | 150 runs, for the whole judging period |
| `SWARM_DAILY_TOKENS` | 1,000,000 | 8 runs a day |
| `SWARM_RUNS_PER_VISITOR` | 3 | a day, per address |
| `SWARM_MAX_RUNS_PER_HOUR` | 6 | across everyone |

A run was 117,000 to 133,000 tokens in the real runs in `reports/`. At Nebius's listed Super price ($0.30 per million input tokens, $0.90 per million output), that's roughly $0.05 to $0.10 a run; check your own bill before trusting that. To stop new runs at once, set `SWARM_PAUSED=1` and restart.


## 05. Add more examples

Examples are finished runs anyone can open without spending anything. After an approved real run, copy `backend/data/<run id>.json` into `backend/examples/`, add a `"label"` field, commit and push; Render redeploys.

## 06. Check it from outside

| Check | How |
|---|---|
| The API is up | `curl <api address>/api/health` returns `"accepting": true` |
| The page reaches it | The status line on the live page says Online |
| The example opens | Click it on the live page, in a private window |
| A new question works | One real run; it's paid, so it's approved first |
| No secrets in the repo | Keys live only in Render's environment |
