# NoteForge

**From ink to insight.** A self-hosted notebook intelligence application for reMarkable, built with Next.js, TypeScript, Tailwind, shadcn-style UI primitives, FastAPI, SQLAlchemy, Alembic and PostgreSQL.

This is working application source, not a static demonstration. The production app contains no seeded notebooks, simulated OCR, fake integrations or sample documents. Test fixtures are isolated under `backend/tests` and are never included in the API container.

Your supplied brief ended at “Alembic d”. The defaults below complete the architecture without assuming missing requirements.

## What it does

| Capability | Implementation |
| --- | --- |
| reMarkable Cloud | Read-only integration through maintained `ddvk/rmapi`, pinned to a source commit; periodically lists cloud metadata and downloads changed notebooks |
| Manual imports | Validated PDF, PNG, JPEG and RMDOC; configurable file/page limits |
| Original preservation | Immutable SHA-256 addressed source files, notebook revision history, authenticated original download |
| Handwriting and structure | Vision model extracts transcript, lists, tables, diagrams and annotations using strict structured output |
| Classification | Page content category and likely purpose; notebook category derived from latest revision |
| Knowledge | Search across the latest page transcripts; extracted actions, decisions, questions, dates and responsibilities |
| Documents | Automatic meeting minutes by default, plus on-demand executive briefs, reports and action plans |
| Evidence | Facts and interpretations require citations to an exact transcript quote on a page in the selected source revision |
| Review | Source previews, verification/correction flags, review notes; editable document paragraphs, titles and missing-information lists |
| History | Immutable document versions; optimistic locking prevents an old tab overwriting a new edit; newer-source warnings |
| Exports | Markdown and structured JSON with source references and review status |
| Operations | Durable database job queue, page checkpoints, bounded backoff, expired-lease recovery, job retries, audit trail and health checks |
| Access | One private admin workspace, signed HTTP-only sessions, same-origin mutation checks, slow password comparison and login rate limiting |
| Interface | Responsive notebook library, page reader, document editor, search, insights, activity and settings; light/dark themes |

## Start on Ubuntu Server

Docker Engine and the Docker Compose v2 plugin must already be installed. These commands run **inside your Ubuntu VM**, not the Proxmox host.

1. Extract this project and enter its directory.
2. Create private settings, replacing the example IP with the Ubuntu VM's LAN IP:

   ```bash
   python3 scripts/configure.py --url http://192.168.1.50:3000 --http --bind 0.0.0.0
   ```

   The script creates `.env` with unique credentials and refuses to overwrite an existing file. Open it locally to read `ADMIN_PASSWORD` and add `OPENAI_API_KEY`. Never commit this file or paste its contents into a chat.

3. Start the application:

   ```bash
   docker compose up -d --build
   docker compose ps
   ```

4. Open the exact `PUBLIC_URL` you configured and sign in with `ADMIN_PASSWORD`. Import a PDF to check the initial workflow.
5. Pair reMarkable using the instructions below. Cloud sync then starts automatically.

Use the **Ubuntu VM's IP**, which may differ from the Proxmox IP. DNS maps a name to an IP; use `:3000` for this direct HTTP setup. With Coolify's HTTPS proxy, use the hostname without that port.

The initial build compiles rmapi and builds Next.js; it can take several minutes. A practical starting allocation is 2–4 vCPUs, 4 GB RAM and enough persistent disk for original notebooks and page renders. The AI model is hosted externally, so the VM does not need a GPU. Allow additional build memory if your Next.js build is killed.

## Pair reMarkable

Open https://my.remarkable.com/device/desktop/connect in your browser and obtain a one-time connection code. Then, in the project directory on the server:

```bash
docker compose run --rm -it api rmapi
```

Enter the code at rmapi's prompt. Once its shell opens, exit with Ctrl+D. The credential file stays in the private persistent `/data/remarkable/rmapi.conf` volume; the container entrypoint sets a private umask. The worker detects pairing on its next tick. Click **Sync now**, or wait for the automatic interval.

NoteForge only invokes rmapi's `find` and `get` commands. It never uploads to, renames or deletes cloud notebooks. Deleting a notebook in the cloud does not delete preserved local originals. Re-pairing and cloud protocol changes may require server maintenance.

## Deploy through Coolify

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the GitHub and Coolify procedure, persistent volumes, environment variables, troubleshooting and backup/restore commands.

Only the `web` service should receive a browser-facing domain. The API, PostgreSQL and worker communicate over Docker networking and have no published host ports. Use HTTPS for a public domain and set `COOKIE_SECURE=true`.

## AI configuration and data handling

Set these in `.env` or Coolify:

```dotenv
OPENAI_API_KEY=your-provider-key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

The model must support **vision input and strict structured outputs through the Responses API**. Changing only the base URL does not make a Chat Completions-only service compatible. There is no fake or local OCR fallback. If the key is missing, the original and rendered pages are retained, and the processing job reports the configuration error.

Rendered PNG page images are sent for extraction. Transcripts and structured extractions are sent for document generation. `store=false` disables OpenAI response storage; this does not override your provider's other retention or account policies. Provider keys remain server-side.

- `AUTO_DOCUMENT_TYPE=meeting_minutes` automatically drafts a document after extraction.
- Supported alternatives: `brief`, `report`, `action_plan`.
- Set `AUTO_DOCUMENT_TYPE=` to disable automatic document generation.
- Default sync interval: 300 seconds; minimum 60.
- Default limits: 40 MB per original, 100 pages per notebook, 25 million pixels per imported image.
- Rendering bounds each page to at most 1800 × 2400 pixels.
- Generation rejects notebooks with more than 240,000 characters of serialized source context; split those notebooks rather than silently truncating them.
- Retries may incur additional provider charges if a request completed remotely but its response was lost.

## Evidence and accuracy

The app rejects invented page IDs, citations from another source revision, quotes absent from the selected transcript, and factual or interpretive paragraphs without citations. Extracted owners and dates must appear verbatim in their evidence quote. Unknown owners and dates remain null; the UI shows “Not specified”.

These checks establish **traceability**, not factual certainty. A vision model can misread handwriting, and a claim can misinterpret a real quote. All generated documents start as unverified drafts. Facts, interpretations and recommendations are visibly distinguished. Review against the original before marking a document reviewed. A user's edits are retained in version history; edited assertions can still be incorrect.

Page review notes are a separate human review record. They do not overwrite the original extraction or silently enter generation. Correct the document itself for final outputs. The classification and “likely purpose” are AI interpretations. Confidence scores are uncalibrated model estimates.

## Rendering boundaries

Raw RMDOC archives are always retained. The built-in converter supports v6 `.rm` strokes, legacy `.content.pages` ordering, and `.content.cPages` entries. For imported PDF notebooks it overlays rendered strokes onto the corresponding base PDF page. Plain PDF and image imports bypass the archive converter.

Community rendering can differ from the tablet, especially for templates, typed text boxes, cropped/rotated/infinite pages, colour and newer device/firmware formats. A warning is shown for archive renders. Unsupported stroke versions and unknown page ordering fail explicitly and remain available as original downloads. Export a PDF from the official reMarkable app and import it when exact rendering is required. Native v5 strokes, EPUB conversion and guaranteed Paper Pro/new-firmware fidelity are not implemented.

## Development and tests

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.lock
pip install --no-deps -e backend
cd backend
pytest -q
ruff check app tests alembic
cd ../frontend
npm ci
npm run build
```

The backend tests use disposable SQLite files by default. To exercise PostgreSQL locks and migrations, set `NOTEFORGE_TEST_DATABASE_URL` to a **dedicated disposable test database** before running pytest. Tests drop the database's application tables. Never point this variable at a real deployment database.

Run the complete isolated browser workflow after building the frontend:

```bash
cd frontend
npx playwright install --with-deps chromium
cd ..
.venv/bin/python backend/tests/browser/run_e2e.py
```

The runner starts the real API, worker and production frontend against a disposable database and a **test-only Responses API fixture server**. It checks sign-in, import, page processing, automatic generation, source preview, review, document editing, version history, search and mobile navigation. Ports 3000, 8000 and 9901 must be unused. It never connects to your cloud account or a paid provider. To use a separately installed Chromium binary, set `BROWSER_EXECUTABLE_PATH`.

GitHub Actions includes SQLite and PostgreSQL backend tests, a frontend build/browser workflow, and Docker Compose build/start checks. See [docs/VALIDATION.md](docs/VALIDATION.md) for exactly what was executed during this build and what still requires live validation.

## Scope of this release

This is a functional single-user initial release. It has genuine integration code, persistent state and tested workflows; it has not been validated against your personal reMarkable account, your provider key or your Ubuntu/Coolify installation. Configure and verify those connections before relying on automated processing.

Search is literal text search over latest notebook transcripts, not semantic/vector search. It does not yet search generated documents. Imports create new notebooks; cloud sync updates existing notebooks by remote ID. Deleted originals, multi-user permissions, SSO, local models, email distribution, Word/PDF exports, arbitrary custom templates and cross-notebook document generation are not part of this release.

Run **one API process and one worker replica**. The queue supports PostgreSQL row locking, but the single-workspace scheduler, login limit and page processing are not designed as a horizontally scaled deployment. Preserve the database and file volume together. There is no retention cleanup or deletion UI yet.

## Source and third-party software

The source repository is [Goss1982/NoteForge](https://github.com/Goss1982/NoteForge). It includes automated backend, browser and container checks in GitHub Actions. See the deployment guide to connect it to Coolify.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for upstream components and licences. No licence has been selected for NoteForge's own source.
