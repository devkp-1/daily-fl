# Operational Notes

- Create and activate a local virtual environment before running app/tests:
  - `python3 -m venv .venv`
  - `. .venv/bin/activate`
- Install dependencies in the venv:
  - `python3 -m pip install flask anthropic python-dotenv`
- Configure weekly review key in `.env` before using "Run weekly review":
  - `ANTHROPIC_API_KEY=your_real_key_here`
- Run the app:
  - `python3 app.py`
- Run the current targeted test:
  - `python3 -m unittest tests/test_bootstrap.py`
