# Autonomous Social Poster

Local automation for posting persona photos to Reddit/X with Ollama captions.

Secrets and browser sessions stay out of git (see `.gitignore` and `SECURITY.md`).

```bash
pip install -r requirements.txt
playwright install chromium
python scripts/login_accounts.py
python main.py --once
```
