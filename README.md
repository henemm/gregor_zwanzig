# Gregor Zwanzig

## Setup
```bash
pip install uv
uv sync
```

## Run tests
```bash
uv run pytest
```

## Environment
- Copy `.env.example` to `.env` and fill in values.

## Git Workflow
- `git add -A && git commit -m "feat: initial commit"`
- `git push origin main`

# Demo Python Project

## Setup

### Option 1: Modern (empfohlen) – mit uv
Installiere uv (sehr schnell, Lockfile, zukunftssicher):

macOS / Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

oder (macOS, Homebrew):
```bash
brew install uv
```

Dann:
```bash
uv sync
```

### Option 2: Klassisch – mit pip/venv
Falls `uv` nicht verfügbar ist oder du maximale Standard-Kompatibilität willst:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

*(Hinweis: Für diese Option müsste ein `requirements.txt` erzeugt werden, z. B. über `uv export > requirements.txt`.)*

---

## Run tests
```bash
uv run pytest   # oder: pytest
```

## Environment
- Kopiere `.env.example` zu `.env` und fülle die Werte aus.

## Git Workflow
```bash
git add -A && git commit -m "feat: initial commit"
git push origin main
```

---

### Hinweise
- **Default:** Nutzung von `uv`.  
- **Fallback:** pip/venv möglich – sollte aber nur genutzt werden, wenn uv nicht installiert werden kann.  
- Für produktiven Betrieb ist **uv** die bevorzugte Lösung (schneller, stabiler, reproduzierbarer).


## CLI Usage

python -m src.app.cli -h
python -m src.app.cli
python -m src.app.cli --report morning --channel none --debug verbose
python -m src.app.cli --report alert --dry-run

Konfigurations-Priorität: CLI > ENV > config.ini  
Debug-Konsistenz: E-Mail-Debug ist identisch zum Console-Debug-Subset.
