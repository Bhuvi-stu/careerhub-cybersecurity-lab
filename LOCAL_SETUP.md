# Local setup

1. Create and activate a virtual environment:
   `python -m venv .venv`
   `.\.venv\Scripts\Activate.ps1`

2. Install dependencies:
   `pip install -r requirements.txt`

3. Copy `.env.example` to `.env` and set your own local passwords.

4. Start:
   `python app.py`

5. Open:
   `http://127.0.0.1:5000`

The application creates `careerhub.db` locally. That database is intentionally ignored by Git.
