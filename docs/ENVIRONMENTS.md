# ENVIRONMENTS — dev / test / prod on the Mac mini

Three independent environments, one git worktree and one launchd service each, all behind the existing
`synaptic` wildcard tunnel (ports 8400–8420 are forwarded).

| Env | Branch | Port | Worktree | launchd label | Public URL |
|---|---|---|---|---|---|
| **dev** | `develop` | 8413 | `~/workspace/trace-graph` (the main checkout) | `com.synapsis.trace-graph-dev` | https://p8413.synaptic.synapsis-analytics.com |
| **test** | `staging` | 8414 | `~/workspace/trace-graph-envs/test` | `com.synapsis.trace-graph-test` | https://p8414.synaptic.synapsis-analytics.com |
| **prod** | `main` | 8415 | `~/workspace/trace-graph-envs/prod` | `com.synapsis.trace-graph-prod` | https://p8415.synaptic.synapsis-analytics.com |

The MELIAF taxonomy service (`:8420`, `com.synapsis.meliaf-taxonomy`) is a **separate, pre-existing service** shared
by all three. TRACE never modifies it; if it is down, tagging and `/health.taxonomy.reachable` degrade gracefully to
the vendored export.

> **The public URLs are behind nginx basic auth.** An anonymous `GET https://p8413…/health` returns
> `401 Authorization Required` from nginx — that is the shared gateway, not TRACE. Authenticated browser sessions
> reach the app normally; on the Mac itself use `http://127.0.0.1:8413|8414|8415`.

## Deploy / redeploy

```bash
bash scripts/deploy.sh dev|test|prod [--no-restart] [--reload-seed]
```

Idempotent, and the whole deployment. It:
1. creates the worktree if missing (`git worktree add`) and checks out / fast-forwards the branch;
2. creates `.venv` if missing and installs `requirements.txt`;
3. writes `.env` — **keeping any existing `TRACE_ACCESS_KEY`**, otherwise generating one — and mirrors the key into
   `data/access-key.txt` (mode 600). It copies `OPENAI_API_KEY` from the taxonomy service's `.env` when present, so
   `/api/ask` works without a second secret to manage;
4. `npm ci && npm run build` in `frontend/`;
5. loads the committed seed batches **only if the registry is empty** (`--reload-seed` forces a clean reload);
6. writes/loads the launchd plist and `launchctl kickstart -k`s the job, then waits for `/health`.

## Promotion

```bash
# develop → staging
git -C ~/workspace/trace-graph-envs/test merge --ff-only develop && bash scripts/deploy.sh test
# staging → main
git -C ~/workspace/trace-graph-envs/prod merge --ff-only staging && bash scripts/deploy.sh prod
git push origin develop staging main
```

Fast-forward only: every environment runs a commit that exists verbatim in the one below it. CI
(`.github/workflows/ci.yml`) runs pytest + frontend lint/build on every push and PR.

## Operating

```bash
# status / restart / stop
launchctl list | grep trace-graph
launchctl kickstart -k gui/$(id -u)/com.synapsis.trace-graph-dev
launchctl bootout   gui/$(id -u)/com.synapsis.trace-graph-prod      # stop (KeepAlive would restart it otherwise)
bash scripts/launchd-install.sh dev|test|prod                       # (re)write + load the plist
bash scripts/launchd-uninstall.sh dev|test|prod                     # remove the service, keep the data

# health, logs, keys
curl -s http://127.0.0.1:8413/health | jq
tail -f ~/workspace/trace-graph-envs/prod/data/server.log
cat ~/workspace/trace-graph-envs/prod/data/access-key.txt           # X-Access-Key for writes (mode 600)
```

| Thing | Where |
|---|---|
| Logs (stdout+stderr) | `<worktree>/data/server.log` |
| Database | `<worktree>/data/trace.db` (git-ignored, WAL) |
| Access key | `<worktree>/data/access-key.txt` **and** `<worktree>/.env` (both git-ignored, mode 600) |
| Published snapshots | `<worktree>/data/versions/` (committed — public data) |
| launchd plists | `~/Library/LaunchAgents/com.synapsis.trace-graph-<env>.plist` |

## Rollback

```bash
git -C ~/workspace/trace-graph-envs/prod reset --hard <previous-commit>   # code
bash scripts/deploy.sh prod
```

The registry is append-only, so code rollbacks never lose data. To roll back **data**, reload from the claim batches
(`scripts/deploy.sh prod --reload-seed`) or restore a published snapshot from `data/versions/`.

## Failure modes seen in practice

| Symptom | Cause | Fix |
|---|---|---|
| `/health` never answers after a kickstart | uvicorn died on start (bad `.env`, port in use) | `tail -50 <worktree>/data/server.log`; `lsof -nP -iTCP:<port> -sTCP:LISTEN` |
| `taxonomy.reachable: false` | the `:8420` service is down | `launchctl kickstart -k gui/$(id -u)/com.synapsis.meliaf-taxonomy`; TRACE keeps working on the vendored export |
| `401` on every write | wrong or missing `X-Access-Key` | read `<worktree>/data/access-key.txt`; note `.env` values must not carry inline comments |
| `deploy.sh` cannot fast-forward | the worktree branch diverged | resolve on the branch, never with `git branch -f` (a worktree holds its branch) |
| public URL `502` | the autossh tunnel is down | see `synapsis-agent-macos-v23/docs/architecture/ssh-tunnel.md` |

## The AWS path (documented, not built)

If TRACE outgrows the Mac mini, the CGIAR/Synapsis CI/CD playbook
(`~/.claude/knowledge/aws-deployment/cicd-workflow-guide.md`) applies as-is:

* **Branch → environment mapping already matches**: `develop` → DEV, `staging` → TST, `main` → PRD; one AWS account
  per environment (`ai-dev` 972793825893, `ai-test` 053142643230, `ai-prod` 207258148366), all `eu-central-1`.
* **Write access is CI-only**: GitHub Actions authenticates with OIDC into a per-project deploy role (created in the
  `IAMSetup` repo); no human and no agent writes to AWS with long-lived keys. Local `aws` profiles stay read-only.
* **Shape**: the SPA to **Amplify** (branch-per-environment, one build command `npm ci && npm run build`); the API as
  a container on **App Runner or ECS Fargate** behind the Amplify rewrite, or as a Lambda (`mangum`) if the
  neighbourhood/graph latency budget allows; SQLite replaced by **Aurora Serverless v2 (Postgres)** or kept as a
  read-only file in EFS/S3 if the registry stays small. The claim log is the migration unit: dump `data/claims/*.jsonl`
  into the new store and `rebuild`.
* **Stateful bits to move**: `data/versions/` → S3 (versioned bucket, public read = the FAIR artefact),
  `TRACE_ACCESS_KEY` → Secrets Manager, taxonomy base URL → the deployed taxonomy service.
* **Cost/benefit today**: the Mac mini environments cost nothing and restart in seconds; AWS becomes worth it when
  (a) people outside the tunnel need access without basic auth, (b) more than one writer needs concurrency
  guarantees SQLite cannot give, or (c) the graph outgrows a single process.
