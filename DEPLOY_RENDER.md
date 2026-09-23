# Deploy CareerHub on Render

## Important security note

CareerHub is an intentionally vulnerable cybersecurity training application.
Do not deploy an openly exploitable version to the public internet.

Use this deployment only for a sanitized portfolio/demo build. Keep the
vulnerability-testing workflows localhost-only whenever possible, and never
use real credentials or personal data.

## 1. Push the project to GitHub

Before pushing:

- Do not add `.env`.
- Do not add `careerhub.db`.
- Do not add local uploads.
- Do not add real passwords or API keys.

The included `.gitignore` is configured to exclude these local files.

## 2. Create a Render Web Service

In Render, create a new Web Service and connect your GitHub repository.

Render can use the included `render.yaml`, or you can enter:

Build Command:
    pip install -r requirements.txt

Start Command:
    gunicorn app:app

## 3. Add environment variables

Set unique demo-only passwords in Render's Environment settings:

- SECRET_KEY
- CAREERHUB_ADMIN_EMAIL
- CAREERHUB_ADMIN_PASSWORD
- CAREERHUB_ALICE_EMAIL
- CAREERHUB_ALICE_PASSWORD
- CAREERHUB_BOB_EMAIL
- CAREERHUB_BOB_PASSWORD

Never commit these values to GitHub.

## 4. Database note

The project uses SQLite. The database file is intentionally excluded from
GitHub. A cloud filesystem should not be treated as permanent database storage.
For a temporary portfolio demo, initialize/recreate the demo database as part
of the application startup. For persistent deployment, move the database layer
to a managed PostgreSQL database.

## 5. Test

After deployment, open the Render-provided URL and verify:

- Home page loads.
- Static files load.
- Login works with the demo credentials configured in Render.
- No real/personal data is present.

## Recommended portfolio approach

For your resume/GitHub:

GitHub repository -> source code + README + screenshots
Render demo -> sanitized application only
Local lab -> intentionally vulnerable testing workflows
