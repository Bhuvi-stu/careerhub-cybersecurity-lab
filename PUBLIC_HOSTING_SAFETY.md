# Public Hosting Safety Checklist

CareerHub was created as an intentionally vulnerable security lab.

Before making a public deployment:

- [ ] No real passwords
- [ ] No API keys or tokens
- [ ] No personal data
- [ ] No careerhub.db committed
- [ ] No .env committed
- [ ] No production credentials
- [ ] No unrestricted file upload to a public filesystem
- [ ] No public-facing exploit demonstrations unless deliberately isolated
- [ ] Use the public deployment as a sanitized portfolio/demo build

Keep the full intentionally vulnerable lab on localhost for hands-on testing.
