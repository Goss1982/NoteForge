# Ubuntu, GitHub and Coolify

## Source repository

The source is maintained in [Goss1982/NoteForge](https://github.com/Goss1982/NoteForge), on the `main` branch. Clone it on your Ubuntu VM, or connect the repository directly to Coolify:

```bash
git clone https://github.com/Goss1982/NoteForge.git
cd NoteForge
```

Completed `.env` files, notebooks, SQLite databases, installed packages and test results are ignored. Only `.env.example` is committed; configure real credentials on your server or in Coolify.

## Coolify application

1. Add the GitHub repository as a new application using **Docker Compose**.
2. Set its Compose path to `/compose.yaml` and base directory to `/`.
3. Enter the required environment variables listed below. Generate independent random values locally, for example with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
4. Assign your HTTPS hostname to the **web** service, target port **3000**. Keep the API, DB, worker and migration service private.
5. Deploy. The migration service must finish before the API/worker start; the web service waits for API health.
6. Open the hostname, sign in and check Settings shows an online worker. Import a small PDF and verify its original download and extraction.
7. Pair rmapi through the Ubuntu shell in the same deployment project, or through a terminal on the running API container using `rmapi`. It must use that deployment's persistent `/data` mount.
8. Confirm the first cloud sync against a small notebook. Compare the rendered page with the tablet. Modify a page, sync again and confirm a second source revision appears while the first remains downloadable.

When using Coolify's proxy, remove the `web.ports` stanza if you do not need a direct host port. The compose default binds it to loopback only; Coolify's proxy should route over its application network to port 3000. If the host port is in use, choose an unused `WEB_PORT` or remove that mapping. Do not assign the same public hostname to the API.

Coolify may provide an environment-variable editor instead of reading a local `.env`. Set values there, including empty strings for deliberately disabled optional features. No special Coolify API integration is required by the application.

## Variables

| Variable | Required / default | Notes |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | Required | Long URL-safe random value; no URL-reserved characters unless encoded |
| `ADMIN_PASSWORD` | Required | At least 12 characters; used to access the single workspace |
| `SECRET_KEY` | Required | At least 32 random characters; independent of other credentials |
| `PUBLIC_URL` | Required for correct browser origin | Exact scheme/hostname/port, e.g. `https://notes.example.com`; no path |
| `COOKIE_SECURE` | `true` in Compose | `true` for HTTPS; `false` only for local HTTP |
| `OPENAI_API_KEY` | Required for extraction/generation | May remain empty during initial setup |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Must support images and Responses API strict structured outputs |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Server-controlled; no arbitrary URL supplied through the UI |
| `SYNC_INTERVAL_SECONDS` | `300` | Minimum 60 seconds |
| `AUTO_DOCUMENT_TYPE` | `meeting_minutes` | Empty disables automatic generation; also `brief`, `report`, `action_plan` |
| `MAX_UPLOAD_MB` | `40` | Valid range 1–100 |
| `MAX_PAGES` | `100` | Valid range 1–500 |
| `WEB_BIND` | `127.0.0.1` | Use `0.0.0.0` for intentional direct LAN access |
| `WEB_PORT` | `3000` | Direct host port; not needed with proxy-only routing |

API/worker-specific values `DATABASE_URL`, `DATA_DIR` and `RMAPI_CONFIG` are set internally by Compose. Both API and worker need the same environment and mounted files. Changing a provider key requires redeployment of **both**.

The frontend proxies `/api` to the internal service name `api:8000`, baked in at Docker build time. Local frontend builds default to `127.0.0.1:8000`. If you change the internal hostname, change `API_INTERNAL_URL` in the frontend build stage and rebuild; setting only a runtime variable is insufficient.

## Persistence and process model

- `postgres-data` contains application state, source metadata, extractions, job state, review records, document histories and audit logs.
- `notebook-data` contains raw sources, page renders and the reMarkable credential file.
- API and worker run as UID 10001, with dropped capabilities and a private file-creation umask.
- PostgreSQL is never exposed on a host port by the supplied Compose file.
- Only one worker and one API process are supported. Do not enable automatic replica scaling.
- No migrations run inside API/worker startup. The separate one-shot `migrate` service performs schema upgrades.
- Health checks report database/API availability and worker freshness; they do not certify cloud pairing or provider credentials are still valid.

The pinned rmapi commit is `aa60dac8a8dbb1b4eb6a25f2caf2f3daea573373`. To update after an upstream cloud change, review upstream changes and update `RMAPI_COMMIT` in the Dockerfile/build arguments, rebuild, then test against a small notebook before resuming bulk sync.

## Back up

Run these from the deployment's Compose directory, or use equivalent Coolify volume/database backups. Pause API and worker writes so the database and source volume represent one consistent application state.

```bash
mkdir -p backups
docker compose stop web api worker
docker compose exec -T db pg_dump -U noteforge -d noteforge -Fc > backups/noteforge.dump
docker compose run --rm -T --no-deps --entrypoint tar api -C /data -czf - . > backups/noteforge-data.tar.gz
docker compose start api worker web
```

Keep the matching `.env` or Coolify secrets separately. The data archive includes your reMarkable tokens and original notes. Store backups somewhere independent of the VM and protect them accordingly. Verify the dump and tar files are nonempty before treating the backup as complete.

## Restore

Use a fresh deployment with the same version of the code. Start only PostgreSQL, restore the matching database and file backup, then start the application:

```bash
docker compose up -d db
docker compose exec -T db pg_restore --clean --if-exists -U noteforge -d noteforge < backups/noteforge.dump
docker compose run --rm -T --no-deps --entrypoint tar api -C /data -xzf - < backups/noteforge-data.tar.gz
docker compose up -d
```

Do not restore over a running application. Restoring into a fresh data volume avoids retaining unrelated files. If upgrading from the restored version, back up first and let the migration service upgrade the schema. A stopped worker's unexpired job lease can delay recovery for up to 10 minutes; it will then be retried within the bounded attempt limit.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Sign-in appears successful but returns to login | HTTP URL with `COOKIE_SECURE=true`; use HTTPS or explicitly disable secure cookies for local HTTP |
| Browser mutations return 403 | `PUBLIC_URL` must match the exact browser origin, including the direct port |
| Web returns 502 / API unavailable | `docker compose ps`, migration logs, API health and internal service name `api` |
| Worker offline | Worker logs, shared database URL, migration completion and database connectivity |
| Original imported, OCR not complete | Activity shows job progress/error; check AI key, model, quota and outbound access; retry failed job after fixing configuration |
| Cloud marked paired but sync fails | The file's presence only establishes local pairing state. It does not validate a token; re-pair rmapi or update its pinned client after upstream protocol changes |
| Archive conversion fails or differs from tablet | Download the original, export PDF from the official reMarkable app and import that PDF |
| Document says newer source available | It intentionally stays tied to its original revision; generate a fresh document from the latest notebook revision |
| Search finds nothing | Only latest extracted transcripts are searched; use an exact phrase of at least two characters and wait for processing |
| Old edit fails with 409 | A newer document version exists. Reload, compare changes and apply your edit to that version |
| Pairing file permission error | Confirm the data volume is writable by UID 10001; named volumes initialise with the image's directory ownership, custom bind mounts may need host setup |

For debugging, inspect `docker compose logs --tail 100 api worker migrate`. The application avoids returning raw SDK/CLI exception payloads because these can contain private content or credentials.
