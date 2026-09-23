# CareerHub local security lab

CareerHub is an intentionally vulnerable Flask and SQLite training application. It is for
local learning only: run it only on `127.0.0.1` / `localhost` and do not send its requests
to any external host.

HOST WEBSITE: https://careerhub-cybersecurity-lab.onrender.com/    **SQL INJECTION IS NOT APPLICABLE IN THIS HOST WEBSITE IT SHOWS * 403 - Forbidden *
SQL request was blocked by this site's web application firewall (WAF). TOOL I USE FOR HOST IS RESTRICT THIS REQUEST**

YOU RUN THIS PROJECT USING LOCALHOST AND PRACTICE ALL VULNERABILITIES

## Public repository safety

This repository contains an intentionally vulnerable security-training application.
The public version does **not** include the local SQLite database or local passwords.

- Keep credentials in `.env`, which is ignored by Git.
- Keep `careerhub.db` and other local database files out of Git.
- Use only synthetic local data.
- Run the lab on `127.0.0.1` / `localhost`.
- Do not deploy this intentionally vulnerable application to the public Internet.

## Run locally

```powershell
python app.py
```

The application binds to `127.0.0.1:5000`.

### Local demo credentials

Credentials are intentionally **not stored in this repository**. Before starting the lab,
copy `.env.example` to `.env` and set your own local demo passwords.

The seed account emails are synthetic local addresses:

- `admin@careerhub.local`


Never commit `.env`, local databases, or exported session/database files.

## Burp Suite Community Edition workflow

CareerHub uses ordinary browser GET and POST requests only. It works with Burp Suite
Community Edition's Proxy, HTTP history, and Repeater; no Professional features, scanner,
extensions, Intruder, or external services are needed.

1. Start CareerHub locally.
2. Configure a browser to use the Burp Proxy listener, then browse to
   `http://127.0.0.1:5000`.
3. Keep requests limited to `127.0.0.1` or `localhost`.
4. In **Proxy > HTTP history**, select a normal CareerHub request.
5. Use **Send to Repeater** when a request below calls for changing a local parameter.
6. Compare the request and response in Repeater. Do not use automated attacks.

The normal request flow is:

```text
Browser -> Burp Proxy -> CareerHub (127.0.0.1) -> Flask -> SQLite
```

| # | Vulnerability | Location | Burp Feature |
|---|---|---|---|
| 1 | SQL Injection | `/jobs?search=` | Repeater |
| 2 | Insufficient Session Expiration | Login/session pages | Proxy |
| 3 | Stored XSS | `/profile` | Proxy/Repeater |
| 4 | IDOR / BOLA | `/application/<id>` | Repeater |
| 5 | Broken Access Control | `/admin` | Repeater |
| 6 | Missing/Improper Cache-Control | `/dashboard` | Proxy |
| 7 | Path Traversal | `/download?file=` | Repeater |
| 8 | Unrestricted File Upload | `/upload` | Proxy |
| 9 | Missing Account Lockout | `/login` | Proxy |
| 10 | Information Disclosure | Local error behavior | Proxy/Repeater |
| 11 | Security Misconfiguration | HTTP responses/config | Proxy |

## Local Burp verification guide

### 1. SQL Injection   

- **Endpoint and normal function:** `GET /jobs?search=python` searches the local job listings.
- **Request/parameter:** Capture the search form request; the relevant parameter is `search`.
- **Capture:** Search for `python`, locate `GET /jobs?search=python` in HTTP history, and send it to Repeater.
- **Inspect:** Change only `search` to a harmless local SQL-condition test such as `%' OR 1=1 --` (URL-encode it if editing the URL directly).
- **Vulnerable indication:** The response displays all seeded jobs instead of only matching jobs.
- **Impact:** User text can alter the local database query's intended filtering.
- **Secure remediation:** Use SQLite parameter placeholders for every search value.
- **Verify the fix:** Repeat the request after remediation; the test text is treated literally and does not expand the results.

### 2. Insufficient Session Expiration

- **Endpoint and normal function:** `POST /login` authenticates a user; `GET /logout` should end that session.
- **Request/parameter:** Inspect the session cookie on login, logout, and an authenticated request such as `GET /dashboard`.
- **Capture:** Log in as Alice, capture the requests in Proxy history, then capture `/logout` and `/dashboard`.
- **Inspect:** Compare whether the session cookie remains accepted after logout and whether it has a long-lived expiry.
- **Vulnerable indication:** `/dashboard` still succeeds after the local logout request.
- **Impact:** A shared browser session can remain usable longer than intended.
- **Secure remediation:** Use short absolute and inactivity expirations, rotate the session on authentication, and invalidate it on logout.
- **Verify the fix:** After logout, resend the captured dashboard request in Repeater; it should redirect to login or return unauthorized.

### 3. Stored XSS

- **Endpoint and normal function:** `POST /profile` saves profile fields, including `professional_summary`.
- **Request/parameter:** The relevant form field is `professional_summary`.
- **Capture:** Save a normal profile bio and locate the resulting POST request in Proxy history; send it to Repeater if desired.
- **Inspect:** Use harmless markup such as `<strong>Local preview</strong>` as the bio, then request `GET /profile`.
- **Vulnerable indication:** The profile preview renders the markup rather than displaying the characters as text.
- **Impact:** Stored user-provided markup is treated as trusted page content.
- **Secure remediation:** Keep template autoescaping enabled and do not apply a `safe` rendering filter to user content.
- **Verify the fix:** Save the same text and confirm it appears as literal characters, not formatted markup.

### 4. IDOR / BOLA

- **Endpoint and normal function:** `GET /application/<id>` shows an application record.
- **Request/parameter:** The application ID in the URL path.
- **Capture:** Create or identify an Alice application, log in as Bob, capture Bob's application-details request, and send it to Repeater.
- **Inspect:** Replace only the numeric ID with Alice's synthetic local application ID.
- **Vulnerable indication:** Bob receives Alice's application information.
- **Impact:** An authenticated user can access another local user's object by changing an identifier.
- **Secure remediation:** Before rendering, require `application.user_id == current_user.id`, except for an authorized admin.
- **Verify the fix:** Repeater should return forbidden/not found for Bob's request to Alice's application.

### 5. Broken Access Control

- **Endpoint and normal function:** `GET /admin` displays administrative data.
- **Request/parameter:** The authenticated candidate session cookie; there is no special form parameter.
- **Capture:** Log in as Alice and browse to `/admin`; inspect the GET request in HTTP history or send it to Repeater.
- **Inspect:** Confirm the request is authenticated as a candidate, not the seeded admin.
- **Vulnerable indication:** The response returns the admin dashboard and its local data.
- **Impact:** Any authenticated candidate can access admin-only functionality.
- **Secure remediation:** Require both an authenticated user and `role == 'admin'` on the server.
- **Verify the fix:** Alice's captured `/admin` request should receive forbidden or redirect away; the admin session should still work.

### 6. Missing / Improper Cache-Control

- **Endpoint and normal function:** `GET /dashboard`, `GET /profile`, and `GET /applications` return authenticated user-specific pages.
- **Request/parameter:** Response headers, especially `Cache-Control` and `Pragma`.
- **Capture:** While logged in, browse to each page and open its response in Proxy history.
- **Inspect:** Look for `Cache-Control: public, max-age=300` on dashboard and weak cache settings on profile/applications; note the lack of `Pragma: no-cache`.
- **Vulnerable indication:** Personal responses may be stored by a browser or intermediary cache.
- **Impact:** User-specific content could remain accessible in a shared browsing environment.
- **Secure remediation:** Send `Cache-Control: no-store, no-cache, must-revalidate, private` and `Pragma: no-cache` for authenticated content.
- **Verify the fix:** Capture the same requests again and confirm the secure headers are present.

### 7. Path Traversal

- **Endpoint and normal function:** `GET /download?file=test.pdf` downloads a local upload.
- **Request/parameter:** The `file` query parameter.
- **Capture:** Visit `/download?file=sample.txt` after uploading a harmless local sample, then send the request to Repeater.
- **Inspect:** Change `file` to `../../app.py`; the app deliberately limits reads to harmless files inside the CareerHub project.
- **Vulnerable indication:** The response downloads `app.py`, which is outside `static/uploads`.
- **Impact:** A trusted path parameter can access unintended project files.
- **Secure remediation:** Canonicalize with `pathlib`, require the resolved path to remain in the allowed upload directory, and allowlist filenames.
- **Verify the fix:** The `../../app.py` Repeater request is rejected, while an allowlisted upload still downloads.

### 8. Unrestricted File Upload

- **Endpoint and normal function:** `POST /upload` stores a user-selected document in `static/uploads/`.
- **Request/parameter:** Multipart form field `file`.
- **Capture:** Upload a harmless local text file and inspect the multipart POST in Proxy history.
- **Inspect:** Observe that the server accepts an arbitrary harmless extension/content without a file-type, size, or content check. Uploaded files are never executed by this lab.
- **Vulnerable indication:** The upload succeeds despite insufficient validation.
- **Impact:** In a real application, unvalidated uploads can create content-handling and storage risks.
- **Secure remediation:** Enforce an extension allowlist, content validation, a maximum size, randomized names, and non-executable storage outside the static web root.
- **Verify the fix:** A permitted document uploads; a disallowed harmless test type receives a validation error.

### 9. Missing Account Lockout

- **Endpoint and normal function:** `POST /login` authenticates a local account.
- **Request/parameter:** `email` and `password` form fields.
- **Capture:** Submit a normal failed login once and inspect the POST in Proxy history.
- **Inspect:** Manually repeat only a small number of failed requests in the browser; then submit the valid local password. Do not automate attempts.
- **Vulnerable indication:** The application provides neither a meaningful delay nor temporary protection, and valid login continues immediately.
- **Impact:** Repeated guesses are not meaningfully slowed or monitored.
- **Secure remediation:** Add rate limiting, progressive delays, temporary account protection, monitoring, and generic login errors.
- **Verify the fix:** Repeated failures trigger the configured protection while a valid login works after the protection expires or is safely reset.

### 10. Information Disclosure

- **Endpoint and normal function:** `GET /debug` intentionally produces a controlled local error response for the logged-in user.
- **Request/parameter:** The authenticated GET request; no special parameter is needed.
- **Capture:** Browse to `/debug`, inspect the 500 response in Proxy history, and optionally send it to Repeater.
- **Inspect:** The response includes a local database path and SQLite error detail, but no real credentials, API keys, OS secrets, or external data.
- **Vulnerable indication:** Internal implementation details are returned to the browser.
- **Impact:** Error details can help an attacker understand an application's internals.
- **Secure remediation:** Return generic user-facing errors and log diagnostic details only on the server; never return stack traces or database errors.
- **Verify the fix:** The request returns a generic error, while server logs retain only the diagnostic detail.

### 11. Security Misconfiguration

- **Endpoint and normal function:** Any normal HTTP response, such as `GET /`, returns the CareerHub page.
- **Request/parameter:** Response headers and local Flask configuration.
- **Capture:** Browse to `/` and inspect its response in Proxy history.
- **Inspect:** Note missing `X-Content-Type-Options`, Content-Security-Policy, Referrer-Policy, and Permissions-Policy headers, and the development-oriented configuration.
- **Vulnerable indication:** Expected browser hardening headers are absent.
- **Impact:** Browser behavior is less constrained than a production application should require.
- **Secure remediation:** Disable debug behavior in production and add the appropriate security headers. Strict-Transport-Security must only be used after HTTPS is enabled; it does not protect this HTTP-only localhost lab.
- **Verify the fix:** Capture a fresh response and confirm the applicable headers are present; only verify HSTS on an HTTPS deployment.

## SQLite persistence verification

Use the normal UI to register a new local user, then verify persistence:

```text
Register new user
  -> Check careerhub.db
  -> Logout
  -> Restart Flask
  -> Login again
```

Open the local `careerhub.db` with a SQLite client and run:

```sql
SELECT id, name, email, role, created_at FROM users;
```

The newly registered account should appear in the result and should still authenticate after the local Flask server restarts.

## Error handling and security boundary

CareerHub provides branded `403`, `404`, and `500` pages for normal errors. They return a
clear user-facing message without stack traces or implementation details. The intentionally
controlled local diagnostic behavior remains limited to the documented `/debug` route.

The server is bound only to `127.0.0.1:5000` with Flask debug mode disabled. Use synthetic
local users, jobs, applications, profiles, and resumes only. Do not bind the application to
`0.0.0.0`, a public IP, the public Internet, cloud hosting, or production infrastructure.
Uploaded files are stored as data and are never executed.
