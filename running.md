# Running the app locally

One-time setup:

​```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
​```

Configure weekly review API access:

```bash
cat > .env <<'EOF'
ANTHROPIC_API_KEY=your_real_key_here
EOF
```

Start the app:

```bash
python3 app.py
```