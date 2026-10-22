# AI Online Class & Meeting Assistant

A Deep Learning project for students: join an online class, upload the lecture recording (or a
transcript), and the backend transcribes it, classifies each transcript segment with a Transformer,
then generates organized notes, a summary, the questions asked, announcements and action items —
which the existing React dashboard displays.

This repository is **two applications** that run together:

| App | Path | Stack | Dev port |
|---|---|---|---|
| Frontend | `src/` | React 18 · Vite 5 · TypeScript 5.5 · Tailwind 3.4 · React Router 6 | 5173 |
| Backend | `backend/` | Python 3.11 · FastAPI 0.115 · SQLAlchemy 2.0 · SQLite | 8000 |

The existing frontend UI/theme is preserved exactly; the mock service layer it used to run on has been
replaced by real HTTP calls (`src/services/api.ts`), and `src/services/classService.ts` re-exports it so
no page had to be rewritten.

---

## 1. Prerequisites

- **Python 3.11** (3.9–3.12 recommended; **avoid 3.14** — PyTorch/faster-whisper wheels aren't
  published for it yet, and this machine already has a 3.14.2 default install that is *not* what the
  backend uses).
- **Node.js 18+** (built and tested with Node 22 / npm 10).
- No GPU, no cloud account, no paid API keys. Everything runs locally on CPU.

---

## 2. Setup

### 2.1 Backend

```powershell
cd backend

# Create the virtualenv with an explicit 3.11 interpreter (do NOT rely on the
# system `python`, which is 3.14 here).
py -3.11 -m venv .venv

# Core dependencies only — CPU-only, downloads no models.
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Configuration
copy .env.example .env
```

Edit `backend/.env` and set a real `JWT_SECRET`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

The SQLite database (`backend/data/app.db`) and the upload folder are created automatically on first
start, so there is no migration step.

### 2.2 Frontend

```powershell
# from the repository root
npm install
```

No frontend `.env` is required for local development: `src/services/api.ts` defaults to the relative
base URL `/api`, and `vite.config.ts` proxies `/api` → `http://127.0.0.1:8000`. If you deploy the backend
elsewhere, set `VITE_API_BASE_URL` (see `.env.example`).

---

## 3. Running (two terminals)

**Terminal A — backend** (from `backend/`):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

**Terminal B — frontend** (from the repository root):

```powershell
npm run dev
```

Open http://localhost:5173, create an account, then use **Join Class** to upload a recording or a
transcript.

### What to upload

| Format | Path taken | Recorded method |
|---|---|---|
| `.txt` / `.vtt` / `.srt` | Parsed directly — no model needed | `transcript-parser` |
| `.mp3` / `.wav` / `.m4a` / … | Transcribed with Whisper | `faster-whisper:<model>` |

A transcript of an actual lecture is **required for the text upload path to say anything real** — the
pipeline only ever reports what is literally in the transcript. There is a worked example at
`backend/tests/data/sample_lecture.vtt` you can upload straight from the UI.

### 3.1 Seeding a demo account

With the backend running:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

This creates the account **demo@example.com / demo1234** and gives it a class whose content is produced
by the *real* pipeline from the bundled sample transcript — it drives the actual HTTP API, so it never
inserts fabricated notes or announcements into the database. It prints the resulting counts and the
method strings, and it is idempotent (re-running signs in and adds another class).

`demo@example.com` is **not** a university address: it only works because `DEV_ALLOWED_EMAIL_DOMAINS`
(default `example.com`) is a development-only exception (§6.1). Remove that setting in production and the
demo account is locked out along with every other non-university address. The script verifies the
account's email through the same API the UI uses, so it also exercises the verification flow.

### 3.2 Demo walkthrough

1. Start both servers (§3) and seed (§3.1).
2. Open http://localhost:5173 and sign in as `demo@example.com` / `demo1234`.
3. **Dashboard** — real totals aggregated from the seeded class.
4. **My Classes** — the processed class; open it.
5. **Lecture Results** — the summary, topics, transcript segments, questions and announcements extracted
   from the transcript.
6. **Processing** — open a class with no lecture, or click *Retry processing*, to see the real job poll.
7. **Join Class** — upload `backend/tests/data/sample_lecture.vtt` yourself and watch the stages run.
8. Every results view shows the pipeline's `method` strings, so the demo never implies a model ran when
   the baseline did.

---

## 4. Testing

### 4.1 Backend test suite (in-process, no port bound)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: **46 passed**. The suite covers auth/authorization boundaries, password hashing, the full
lecture-pipeline happy path, re-processing, cross-student access denial, unsupported-upload rejection,
and the individual ML units (VTT/SRT/plain-text parsing, baseline classifier behaviour, deadline
resolution only when the transcript states it, extractive summary sentence provenance).

It also covers the university-email requirement (§6.1): registration is rejected for a non-university
domain, a personal address (Gmail/Outlook) is refused, an unverified account cannot log in or reach any
protected route, a wrong/expired verification code is refused, verification activates the account,
resend is rate-limited, password reset invalidates old tokens, and `GET /api/meetings/policy` requires a
verified account while never claiming it can join a meeting for you.

If you ever see a stale failure that contradicts a source fix, clear bytecode caches first:

```powershell
Get-ChildItem -Recurse -Filter __pycache__ -Directory | Remove-Item -Recurse -Force
```

### 4.2 Backend smoke check (real socket, real HTTP)

```powershell
.\.venv\Scripts\python.exe scripts\smoke_check.py
```

Boots the real app on `127.0.0.1:8099` in a background thread and exercises it over HTTP the way the
browser would, printing real output. Ends with `SMOKE CHECK PASSED` (or a `FAIL:` line + non-zero exit).

### 4.3 Full-stack check (the browser's actual path)

With both servers from §3 running:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_check.py --base-url http://localhost:5173
```

This goes **through the Vite proxy**, so it verifies the exact route the browser takes, and re-checks
every one of the endpoints the React pages call. `/docs` and `/openapi.json` are skipped in this mode
because the dev proxy only forwards `/api`.

### 4.4 Classifier evaluation (the only place a score is reported)

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_classifier.py            # active backend
.\.venv\Scripts\python.exe scripts\evaluate_classifier.py --backend baseline
.\.venv\Scripts\python.exe scripts\evaluate_classifier.py --json report.json
```

Measures whichever classifier is actually active against the hand-labelled dev segments in
`tests/data/labelled_segments.jsonl`, printing accuracy, macro F1, per-class precision/recall/F1/support
and a real confusion matrix. The printed `method` line says which implementation produced the numbers.

Measured baseline (`baseline-pattern-v1`, 39 segments): **accuracy 0.9231 (36/39), macro F1 0.9137** —
the three misses are DISCUSSION segments read as QUESTION (2) and INFORMATION (1).

This is a small, hand-authored **development** set, not a benchmark, and it is the same material the
baseline's patterns were tuned against. The score proves internal consistency and regression safety; it
does **not** establish generalisation, and it must always be quoted together with its method string.
`--backend real` exits non-zero with an actionable message when the Transformer isn't installed, rather
than silently scoring the baseline.

### 4.5 Frontend type-check and production build

```powershell
npm run typecheck   # tsc -b --noEmit
npm run build       # tsc -b && vite build
```

---

## 5. Optional: real model backends

The backend runs end-to-end with **zero model downloads** by default. Its built-in baselines are
deterministic and labelled as such in every response, so a baseline result can never be mistaken for a
trained-model result. To enable the real models:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
```

That pulls `faster-whisper==1.1.1`, `transformers==4.47.1` and `torch==2.5.1` (CPU). Weights are fetched
lazily the first time a model is used, then cached — nothing downloads at import time. Sizes: Whisper
75 MB–1.5 GB, Transformer checkpoints 250 MB–1.6 GB.

Then in `backend/.env`:

```ini
STT_BACKEND=whisper            # or: auto
WHISPER_MODEL=base             # tiny | base | small | medium | large-v3
SEGMENT_CLASSIFIER_BACKEND=real # or: auto
SUMMARIZER_BACKEND=real        # or: auto
```

`auto` = use the real model **if its library is installed**, otherwise fall back to the baseline and
say so. `real` = require it. `baseline` = always use the built-in deterministic path.

### Which implementation actually ran?

Every response records the method string, and `GET /api/health` reports availability:

| Stage | Baseline (always available) | Real model |
|---|---|---|
| Speech-to-text | `transcript-parser` (uploaded caption files) | `faster-whisper:<model>` |
| Segment classification | `baseline-pattern-v1` | `zero-shot:<hf-model-id>` |
| Summarization | `extractive-textrank-lite-v1` (verbatim sentences only) | `abstractive:<hf-model-id>` |
| Announcements / action items | `rules-v1` (grounded regex extraction) | — |

The Processing page prints the active backends from `/api/health` as a footnote, precisely so the UI
never implies a model ran when it didn't.

---

## 6. Configuration reference (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `APP_NAME` | AI Online Class Assistant API | Shown in OpenAPI docs |
| `API_PREFIX` | `/api` | Prefix for every router |
| `LOG_LEVEL` | `INFO` | Root log level |
| `CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | Allowed browser origins |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLAlchemy URL; a PostgreSQL URL works too |
| `JWT_SECRET` | *change this* | HS256 signing key |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | Token lifetime |
| `UPLOAD_DIR` | `./data/uploads` | Where recordings are stored |
| `MAX_UPLOAD_MB` | `200` | Upload size cap |
| `STT_BACKEND` / `SEGMENT_CLASSIFIER_BACKEND` / `SUMMARIZER_BACKEND` | `auto` | `auto` \| `real` \| `baseline` |
| `WHISPER_MODEL` | `base` | Whisper size when STT is real |
| `HF_HOME` | *unset* | Optional Hugging Face cache location |
| `UNIVERSITY_EMAIL_DOMAINS` | *empty* | Comma-separated approved university domains, e.g. `uog.edu.pk,cs.uog.edu.pk`. **No domain is hardcoded** — you decide. Empty means "no restriction". |
| `DEV_ALLOWED_EMAIL_DOMAINS` | `example.com` | Extra domains accepted **for local development only** (this is what keeps the seeded `demo@example.com` account working). Keep it empty in production. |
| `VERIFICATION_CODE_TTL_MINUTES` | `15` | How long a 6-digit verification code stays valid |
| `VERIFICATION_MAX_ATTEMPTS` | `5` | Wrong-code attempts before the code is burned |
| `VERIFICATION_RESEND_COOLDOWN_SECONDS` | `60` | Minimum gap between "resend code" requests |
| `PASSWORD_RESET_TTL_MINUTES` | `30` | Password-reset token lifetime |
| `PUBLIC_APP_URL` | `http://localhost:5173` | Base URL used to build the reset link that is emailed |
| `EMAIL_BACKEND` | `console` | `console` (log the code — development) or `smtp` (really send it) |
| `SMTP_HOST` · `SMTP_PORT` | *(blank)* · `587` | SMTP server. **Never commit real credentials.** |
| `SMTP_USERNAME` · `SMTP_PASSWORD` | *(blank)* | SMTP login — supplied through `.env` or the environment only |
| `SMTP_FROM_EMAIL` · `SMTP_FROM_NAME` | `no-reply@localhost` · AI Online Class Assistant | Envelope sender |
| `SMTP_USE_STARTTLS` · `SMTP_TIMEOUT_SECONDS` | `true` · `15` | STARTTLS upgrade and socket timeout |

Secrets live only in `.env`, which is git-ignored. `.env.example` contains placeholders only. The JWT
secret, SMTP password and any API key must come from the environment — nothing is baked into the source.

### 6.1 University email verification (configuration + delivery)

Accounts are **university-email only** and are **inactive until the email is verified**.

```ini
# backend/.env
UNIVERSITY_EMAIL_DOMAINS=uog.edu.pk            # or: uog.edu.pk,cs.uog.edu.pk
DEV_ALLOWED_EMAIL_DOMAINS=example.com           # dev-only exception for the demo seed
EMAIL_BACKEND=console                           # start here; switch to smtp when you have a mail server
```

How a student signs up:

1. `POST /api/auth/register` checks the domain **on the backend** (the browser check is only a
   convenience). A personal address such as `someone@gmail.com` is refused with
   `400 email_domain_not_allowed`; trying to *sign in* with one gives `403 email_domain_not_allowed`,
   which is what the UI turns into "Please login with university mail."
2. A 6-digit code is generated, stored only as a PBKDF2 hash, and sent to the university address.
3. `POST /api/auth/verify-email` activates the account and only then returns an access token.
   An unverified account gets `403 email_not_verified` from `/auth/login` and `401`/`403` from every
   protected route.
4. Forgot-password issues a single-use reset token (`POST /auth/forgot-password`) and
   `POST /auth/reset-password` rotates `token_version`, which invalidates every token issued earlier.

The frontend reads `GET /api/auth/policy` so the approved domains, code length and resend cooldown are
never hardcoded in the UI either; when a student types a personal address, the sign-in form shows
**"Please login with university mail."** directly under the email field.

**Delivery modes**

- **`EMAIL_BACKEND=console` (default).** There is no inbox locally, so the code is written to the backend
  log and — only while `console` is active — echoed by the API as `devVerificationCode` so the flow is
  testable. Set `EMAIL_BACKEND=smtp` to stop that echo entirely.
- **`EMAIL_BACKEND=smtp`.** Real delivery. Fill in `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
  `SMTP_PASSWORD` and `SMTP_FROM_EMAIL` in `backend/.env` (or the process environment). `devVerificationCode`
  is then always `null` and the only way to obtain the code is the student's inbox. Nothing is hardcoded
  and no credential is committed.

Honest status: the OTP flow is covered by the test suite (§4.1) and by the live-HTTP smoke check
(§4.2), but it has only ever been exercised with the **`console`** backend. Real SMTP delivery has
**not** been verified against a live mail server in this environment — configure `EMAIL_BACKEND=smtp`
and send yourself a code before claiming email delivery works.

---

## 7. API surface

All routes are mounted under `/api`. Authentication is JWT Bearer (`Authorization: Bearer <token>`);
every class/lecture route is scoped to the owning student.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Status + which ML backends are live |
| `GET` | `/auth/policy` | Approved university domains, code length, resend cooldown (drives the UI hints) |
| `POST` | `/auth/register` | Create account → **inactive**; issues a 6-digit verification code. Returns no token |
| `POST` | `/auth/verify-email` | `{email, code}` → activates the account and returns the access token |
| `POST` | `/auth/resend-verification` | Issue a new code (rate-limited → `429 resend_too_soon`) |
| `POST` | `/auth/login` | Sign in → access token. `403 email_domain_not_allowed` for a non-university address, `403 email_not_verified` until verified |
| `POST` | `/auth/forgot-password` | Email a single-use reset token (always a generic 200 — never reveals whether the account exists) |
| `POST` | `/auth/reset-password` | `{token, password}` → rotates `token_version`, revoking every earlier token |
| `GET` | `/auth/me` | Current student (used to validate a restored token) |
| `GET` | `/meetings/policy` | Why a given meeting link can't be auto-joined, which access controls apply, and the permitted alternative. Requires a verified account |
| `POST` · `GET` | `/classes` | Create a class / list my classes |
| `GET` | `/classes/{id}` | One class |
| `GET` | `/classes/{id}/lectures` | Recordings uploaded to a class |
| `GET` | `/classes/{id}/results` | Full results for a class |
| `GET` | `/classes/{id}/notes` · `/announcements` · `/questions` | Per-class outputs |
| `GET` | `/notes` · `/announcements` | Cross-class notes library / announcement inbox |
| `GET` | `/dashboard/summary` · `/dashboard/recent-classes` | Dashboard aggregates |
| `POST` | `/lectures` | Upload a recording/transcript (multipart) → lecture + job |
| `GET` | `/lectures/{id}` · `/status` · `/results` · `/transcript` | Lecture + processing job state |
| `POST` | `/lectures/{id}/process` | (Re)queue processing |
| `GET` | `/lectures/{id}/notes` · `/announcements` · `/questions` | Per-lecture outputs |

Responses are serialised to **camelCase** (`avatarInitials`, `hasNotes`, `accessToken`,
`segmentCount`, `classifierMethod`, …) so they match `src/types/index.ts` exactly.

---

## 8. How the pipeline works

```
upload ─► preprocess ─► STT ─► segment classification ─► extraction ─► notes/summary ─► persist
                                       (Transformer)        (rules-v1)   (extractive or abstractive)
```

1. **Preprocess / parse** — `.vtt`/`.srt` cues keep their timestamps and speaker labels; `.txt` is split
   into sentences; audio is handed to Whisper with a VAD filter.
2. **Segment classification** — each segment is labelled `Question`, `Info`, `Discussion` or
   `Action Item` with a confidence score.
3. **Extraction** (`rules-v1`) — questions, announcements (categorised: Deadline, Schedule Change,
   Exam, Quiz, Assignment, General Announcement) and action items with a literal assignee. A deadline is
   only emitted as a resolved date when the transcript states one; otherwise the item is marked
   `uncertain` rather than invented.
4. **Notes/summary** — the default extractive summarizer selects **only verbatim transcript sentences**.

Processing runs as a FastAPI `BackgroundTask`; the Processing page polls `GET /lectures/{id}/status`
(1 s) and renders real progress, then redirects to the lecture results.

---

## 9. Project structure

```
src/                             React frontend (unchanged design system)
  components/  common, layout, dashboard, classes, notes, announcements
  pages/       one file per route
  services/
    api.ts           the ONLY module that talks to the backend (real HTTP + camelCase + JWT)
    classService.ts  re-exports api.ts — the module pages import from
    mockService.ts   kept on disk for reference; no longer imported by the running app
  context/     AuthContext (real login/signup/me, token in sessionStorage)
  types/       shared TypeScript types (match the API wire format)
  data/        mockData.ts (reference only)

backend/
  app/main.py           FastAPI app, CORS, routers, lifespan (creates the DB)
  app/api/              deps, auth, classes, lectures, health, meetings
  app/schemas/          CamelModel + every request/response model
  app/models/           user, course, outputs (SQLAlchemy 2.0)
  app/services/         auth, course, lecture, serializers
  app/core/             config, security, logging, ids, email
  app/db/               base, session, init_db
  app/ml/               stt, transcript_io, classifier, extractors, notes, dates, stages,
                        text_utils, types, pipeline
  app/meeting/          policy.py — meeting-access policy/detection only (no joining, no bypass)
  scripts/             smoke_check.py (live HTTP), evaluate_classifier.py (dev-set metrics),
                       seed_demo.py (demo account via the real API)
  tests/                conftest + auth/access, university auth, lecture pipeline, meeting policy,
                        ML units, data/
  requirements.txt      core (no model downloads)   requirements-ml.txt   optional real models
```

---

## 10. Ground truth: what is and isn't implemented

This section is deliberately blunt so the project is never over-claimed.

**Working and verified**

- Real accounts: registration, login, PBKDF2-HMAC-SHA256 password hashing (260k iterations), JWT
  sessions, and per-student authorization on every class/lecture route.
- **University-email-only accounts with real verification.** The approved domain(s) come from
  `UNIVERSITY_EMAIL_DOMAINS` (nothing hardcoded), the check runs on the backend, a 6-digit code is
  issued and stored only as a hash, and the account stays **inactive until verified** — an unverified
  account can neither log in nor call any protected route. Personal domains (Gmail/Outlook) are refused.
  Password reset invalidates previously issued tokens. Verified by tests; delivery tested with the
  `console` backend only (see §6.1).
- Real upload → parse/transcribe → segment classification → extraction → notes/summary → persistence.
  Reproduced end-to-end over a real socket: 34 segments, 8 announcements, 4 questions, 6 action items
  from the sample lecture.
- The React app runs entirely against this backend (frontend-facing endpoints verified `200` through
  the Vite proxy).
- `pytest -q` → 46 passed.

**Not implemented / out of scope**

- **No joining of live meetings, and no attempt to bypass access controls.** Google Meet, Zoom, Teams and
  Webex are *not* connected, and this project will not knock its way past a waiting room, domain
  restriction, passcode or host approval, nor record without consent. What exists is
  `app/meeting/policy.py` plus `GET /api/meetings/policy`: it identifies the platform from the pasted
  link, lists the access controls that apply, states plainly that **application sign-in is not
  authorization to join a meeting**, and points to the permitted alternative — join with your official
  university account and upload the authorized recording/transcript. Every platform reports
  `automatedJoinSupported: false`, with a regression test guarding that. Live capture is Phase 8 and
  remains intentionally unimplemented.
- **No trained model.** The classifier/summarizer are pretrained/foundational or deterministic baselines.
  Nothing in this repo was fine-tuned, and no accuracy figure is claimed beyond the one measured dev-set
  score in §4.4 (which reports its method string alongside it).
- **Default run uses baselines**, labelled as such in the API. Real Whisper/Transformer output requires
  the opt-in install in §5.
- The frontend theme preference (Settings) is still a placeholder; only the dark theme exists.
- No n8n workflow (optional in the brief, not required).

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Run uvicorn **from `backend/`**, not the repo root. |
| Frontend gets 404 / `Failed to fetch` on every call | Backend isn't running, or you're not going through the Vite proxy. Start uvicorn on `127.0.0.1:8000` and reach the app at `http://localhost:5173` (not a `file://` build). |
| `Port 5173 is in use, trying another one…` | A stale Vite process is holding the port — the app on 5174 may not have the proxy. Find and stop it: `Get-NetTCPConnection -LocalPort 5173 -State Listen` → `Stop-Process -Id <pid> -Force`. |
| `/api/health` returns HTML instead of JSON | You're hitting the Vite server, not the API — usually because the proxy isn't in the running config. Restart Vite. |
| `PermissionError: [WinError 32] … test_app.db` | A previous test run left the SQLite file locked. Delete `backend/data/test_app.db` (and `-wal`/`-shm`) and re-run. |
| `vite.config.ts: Cannot find module 'path'` / `__dirname` | `@types/node` is missing. `npm install --save-dev @types/node`. |
| Tests fail identically after a source fix | Stale `__pycache__` — see §4.1. |
| Audio upload says transcription is unavailable | Expected without `requirements-ml.txt`. Upload a `.txt`/`.vtt`/`.srt` transcript instead, or install §5. |
| `/docs` fine but proxy smoke check skips it | Expected — the dev proxy only forwards `/api`. |
| Sign-in shows "Please login with university mail." | Expected — the address isn't on `UNIVERSITY_EMAIL_DOMAINS` (dev also accepts `DEV_ALLOWED_EMAIL_DOMAINS`). Add the domain to `backend/.env`. |
| Sign-in says the account isn't verified (`403 email_not_verified`) | The 6-digit code was never confirmed. Use *Resend code* on `/verify-email`, or with `EMAIL_BACKEND=console` read the code from the backend log. |
| No verification email arrives | `EMAIL_BACKEND` is still `console` (the default). The code is in the backend log, not an inbox — configure SMTP per §6.1 to send real mail. |

---

## 12. Roadmap status

| Phase | Scope | State |
|---|---|---|
| 1 | Audit of the existing frontend | Done |
| 2–4 | FastAPI backend: config, DB, models, schemas, auth, classes, lectures, uploads, processing jobs | Done |
| 5–7 | ML pipeline: transcript parsing, STT, segment classifier, extractors, notes/summary | Done (baseline path; real models opt-in) |
| 8 | Live meeting integration (staged A–G) | Meeting **access policy** implemented: platform detection + `GET /api/meetings/policy` + honest UI guidance, deliberately performing no joining and no access-control bypass. Live capture still not started |
| 9 | Frontend wired to the real backend | Done and verified end-to-end |
| 10 | Optional n8n automation | Not started (optional) |
| 11 | Classifier evaluation harness (`scripts/evaluate_classifier.py`) + broader testing | Evaluation harness done (§4.4); broader end-to-end tests pending |
| 12 | Final integration & demo | Demo seed script (§3.1) + walkthrough (§3.2) done; final verification pass run |
