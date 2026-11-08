# Validation record

Build date: 8 November 2026.

## Executed successfully

- Backend pytest suite: **27 passed, 1 skipped** using an isolated SQLite database. The skipped test requires PostgreSQL and is enabled by the PostgreSQL CI job.
- Python lint checks across API, worker, rendering, integrations, migrations and tests.
- Alembic initial migration, downgrade/upgrade round trip, and schema parity comparison against SQLAlchemy models (SQLite).
- Actual PDF validation/rendering and PNG import/rendering.
- Pinned rmapi source compiled successfully with the official Go 1.27.3 toolchain (archive checksum verified); offline CLI version command executed. No cloud credentials were used.
- CRDT page ordering, deleted-page exclusion and base-PDF page redirection tested against an archive fixture.
- Actual v6 `.rm` generation and SVG/Cairo/PDF/page-render pipeline, using a generated format fixture.
- Malformed-file rejection, archive path traversal rejection, compression-ratio limits, multipart body-size limits and revision deduplication.
- Authentication, unauthenticated private-route rejection, tampered sessions, same-origin checks and login rate limits.
- Durable queue deduplication, lease renewal, stale-lease recovery, hard attempt limits, terminal-lease expiry and retry creation.
- Extraction checkpoint reuse and idempotent completed generation.
- Notebook revision retention, latest-revision search, older-document source references, stale-document flags and notebook/revision ownership checks.
- Document generation/edit/review/export using deterministic test extraction/generation; immutable version history and optimistic conflict rejection.
- Citation validation rejects fabricated quotes, foreign page IDs and uncited factual claims.
- Real OpenAI SDK parsing against a mocked HTTP transport, including strict JSON Schema payload, image input and `store=false`.
- reMarkable subprocess command contract, non-interactive JSON listing, private token path, safe CLI error handling and incremental sync/rename logic with deterministic remote fixtures.
- Next.js production build and TypeScript checks.
- npm production dependency audit: **0 reported vulnerabilities** at validation time.
- Chromium browser workflow against the real running API, background worker and production frontend, using a separate **test-only Responses API server**. Verified login, import, extraction, automatic generation, original-source preview, page review, document edits, review state, version history, search, light/dark switching, mobile navigation and mobile overflow checks.
- Desktop library/document screenshots and mobile settings layout inspected during browser QA. Screenshots are ephemeral test evidence and are not included as user files.
- Docker Compose and GitHub Actions YAML parsing.

## Not executed / requires deployment validation

- A live reMarkable login, real cloud downloads, a real handwritten notebook, or a notebook modified on the user's tablet.
- A paid/live AI request. Tests establish API compatibility and control flow, not model accuracy, latency or provider quota availability.
- PostgreSQL execution and concurrent `SKIP LOCKED` claiming in this workspace. CI includes a dedicated PostgreSQL matrix job and concurrency test.
- Docker image builds, Compose startup or container health checks in this workspace: the Docker executable and daemon socket were unavailable.
- Coolify deployment, HTTPS proxy/cookie behaviour on the user's hostname, backup restoration on the user's server, or any Proxmox/Ubuntu changes.
- GitHub push or CI execution: no NoteForge repository existed in the connected account, and the available integration could not create a new repository. No unrelated repository was modified.
- Exact rendering fidelity for every tablet/firmware/pen/template, cropped/infinite page, typed-text layout or Paper Pro format.
- A formal security assessment, accessibility audit, load test or production reliability certification.

## Before relying on automation

Deploy to a test instance. Pair your own device, import a small known notebook, verify the original download byte-for-byte, compare each page render with the tablet, check the extracted text and citations, modify a page and confirm revision retention, interrupt/restart the worker, and restore a matched database/file backup into a separate instance.

All documents remain drafts until a user reviews them. Citation checks prove that a quote is present in the selected transcript; they do not prove that the transcription or interpretation is true.
