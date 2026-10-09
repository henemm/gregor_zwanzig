# E2E-Verifikation (Post-Push auf Staging)

Sichere Acceptance-Stage-Verifikation, dass der neue Code auf der **Staging**-Umgebung
tatsaechlich funktioniert. Sie ersetzt die fruehere lokale Prod-Verifikation
(Issue #339): kein Eingriff in den Live-Server, keine Mails an echte Nutzer.

## Wann ausfuehren

NACHDEM der PR gemergt ist (PR-Liefer-Workflow, PO-go 2026-08-05 — Direkt-Push
auf `main` ist abgeschafft) und VOR `deploy-gregor-prod.sh`.

**KEIN passives Warten!** Staging könnte bereits aktuell sein — sofort prüfen.
Der Poll-Loop in Schritt 1 läuft so lang wie nötig (0 bis 150 Sek), kein manuelles "5 Minuten warten".

Ablauf:
1. Branch pushen → PR mit grüner CI-Ampel mergen (`gh pr create --fill` … `gh pr merge --merge`)
2. Sofort `/e2e-verify` starten — Schritt 1 prüft Staging-Status und wartet aktiv
3. `deploy-gregor-prod.sh`

## Ziel-Umgebung

- **Basis-URL:** `https://staging.gregor20.henemm.com`
- **Override:** `GZ_SVELTE_BASE` bzw. `GZ_VALIDATION_URL` (z. B. fuer einen anderen
  Staging-Host). Niemals auf die Live-Produktions-URL umstellen.

## Schritt 1: Staging-Aktualität sicherstellen + Smoke

**Keine Ankündigung "ich warte X Minuten". Sofort ausführen:**

```bash
BASE="${GZ_SVELTE_BASE:-https://staging.gregor20.henemm.com}"
EXPECTED=$(git rev-parse HEAD)
STAGING=$(curl -s "$BASE/api/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commit','?'))" 2>/dev/null)
echo "Staging: ${STAGING:0:7} | Erwartet: ${EXPECTED:0:7}"
if [ "${STAGING:0:7}" != "${EXPECTED:0:7}" ]; then
  echo "→ Deploy triggern..."
  bash /home/hem/henemm-infra/scripts/auto-deploy-gregor-staging.sh
  for i in 1 2 3 4 5; do
    sleep 30
    STAGING=$(curl -s "$BASE/api/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('commit','?'))" 2>/dev/null)
    echo "Versuch $i: ${STAGING:0:7}"
    [ "${STAGING:0:7}" = "${EXPECTED:0:7}" ] && break
  done
fi
echo "Staging-Status: ${STAGING:0:7}"
curl -s -o /dev/null -w "ROOT %{http_code}\n" "$BASE/"
curl -s -o /dev/null -w "HEALTH %{http_code}\n" "$BASE/api/health"
```

**STOP wenn:** ROOT nicht `200`/`302` oder HEALTH nicht `200` oder Staging-Commit nach 5 Versuchen falsch.

## Schritt 2: Scope bestimmen

Die zu pruefende Tiefe haengt vom Aenderungs-Scope ab (Logik aus `e2e_commit_gate.py::detect_scope`,
Issue #86):

- **frontend-only** → nur visuelle Pruefung auf Staging, KEIN Mailversand.
- **backend** / **full-stack** → Test-Trip auf Staging anlegen + Briefing
  ausschliesslich an diesen Test-Trip senden, danach IMAP-Pruefung.

```bash
python3 .claude/hooks/e2e_commit_gate.py <<< '{"tool_input":{"command":"git commit"}}' 2>&1 || true
```

(Der Aufruf gibt nur den erkannten Scope als Hinweis aus — er blockt nichts.)

## Schritt 3a: frontend-only — visuelle Pruefung

**Alternativ (empfohlen):** `staging-validator` Agent via `/5-implement` Step 9 — loggt sich automatisch in Staging ein, prüft alle ACs aus der Spec via Playwright und schreibt `.claude/e2e_verified/<sha>.json` mit `verified_commit` (aktueller HEAD-SHA). Voraussetzung: aktiver Workflow mit genehmigter Spec mit AC-Format `**AC-N:** Given.../When.../Then...`.

Manuell (Fallback):

Playwright/Screenshot gegen Staging. Die Basis-URL kommt aus `GZ_SVELTE_BASE`:

```bash
GZ_SVELTE_BASE="${GZ_SVELTE_BASE:-https://staging.gregor20.henemm.com}" \
  uv run python3 .claude/hooks/e2e_browser_test.py browser --check "Feature" --url "/"
```

Screenshot visuell pruefen: ist die Aenderung auf Staging sichtbar und korrekt?
KEINE Mail in diesem Scope.

## Schritt 3b: backend / full-stack — Test-Trip + Test-Mail

1. **Test-Trip auf Staging anlegen** (via Staging-API), niemals einen Produktiv-Trip
   (GR221 etc.) verwenden. Der Trip bekommt als einzigen Empfaenger die Test-Adresse
   `gregor-test@henemm.com`.
2. **Briefing ausschliesslich an diesen einen Test-Trip** ausloesen — niemals einen
   Sammel-Versand ueber alle aktiven Touren. Nur dieser eine Test-Trip darf eine Mail
   erhalten.
3. **IMAP-Pruefung gegen Stalwart:** Posteingang von `gregor-test@henemm.com` auf
   `mail.henemm.com` abrufen (Credentials aus den Settings, nicht im Klartext hier).
   Pruefen: Subject mit Trip-Name + Report-Typ, HTML-Body nicht leer, Wetter-Tabelle
   vorhanden, Werte plausibel, Timestamp NACH dem Versand.

Inhaltliche Tiefe via Spec-Validator (liest dieselbe Test-Mail):

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

**STOP wenn:** Validator nicht Exit 0.

### Rezept: Befehl per echtem Mail-Eingang auf Staging

Fuer Aenderungen an E-Mail-Befehlen (`status`, `heute`, Ruhetag, Startdatum;
`trip_command_processor.py`, `inbound_email_reader.py`) prueft dieses Werkzeug den
ECHTEN Zustellweg. Testmails ueber die angemeldete Einlieferung (Port 587) tragen nie den
Absender-Echtheitsvermerk und werden vom Eingang zu Recht verworfen (#2143). Das Werkzeug
liefert deshalb anonym ueber Port 25 ein (der eigene Server ist fuer `henemm.com`
sendeberechtigt), legt einen Wegwerf-Nutzer `gregor-test+<tag>@henemm.com` samt Trips an,
stoesst den Poll ueber den Kern (Port 8001, `X-GZ-Core-Auth`) an und liest die Antwortmail
per IMAP (nur `BODY.PEEK`, nur eigene Plus-Adresse). Im `finally` wird alles geloescht.
Voraussetzung: ein bestaetigtes Helfer-Konto (`GZ_AUTH_USER`/`GZ_AUTH_PASS` in
`/home/hem/gregor_zwanzig_staging/.env`) holt das Bestaetigungs-Token des neuen Nutzers
(Henne-Ei, #2271); es wird nie veraendert oder geloescht. Fehlen die Werte: Exit 2 vor jeder Registrierung.

```bash
python3 .claude/tools/staging_befehl_pruefen.py --szenario status        # eine status-Mail (Trip B)
python3 .claude/tools/staging_befehl_pruefen.py --szenario heute         # status + heute (Trip A)
python3 .claude/tools/staging_befehl_pruefen.py --szenario verschiebung  # Ruhetag + Startdatum (D, D2)
python3 .claude/tools/staging_befehl_pruefen.py --szenario alle          # A, B, C, D, D2
```

- **Exit 0:** alle gewaehlten Szenarien bestanden (je Szenario eine `PASS`-Zeile).
- **Exit 1:** Antwort ausgeblieben (Mail vermutlich verworfen) oder Inhalt falsch.
- **Exit 2:** Aufruf-/Umgebungsfehler (Relay-Sperre, fehlende Zugangsdaten, Registrierung
  abgelehnt oder 429 — 5 Versuche pro IP und Stunde, Lauf nahe Mitternacht Ortszeit).
- **Erfolg = Antwortmail, nicht count:** Hat der Cron die Mail schon verarbeitet, meldet der
  Poll `count=0`, obwohl alles funktioniert. `count` ist nur Diagnose; eine ausbleibende
  Antwortmail ist immer ein Fehler (der Eingang markiert verworfene Mails still als gelesen).
- Scheitert das Aufraeumen, steht die Kennung des uebrig gebliebenen Nutzers in der Ausgabe.
- **Nicht abgedeckt:** SMS, Premium-SMS und Telegram (#2441 AC-6, AC-7) laufen NICHT ueber
  dieses Werkzeug, sondern ueber Kern-Tests mit echtem Eingang, die Staging-Vorschau und
  den Handy-Nachtest nach dem Prod-Deploy.

## Schritt 3c: Telegram-Scope — funktionaler Live-Test

Wenn der Change den Telegram-Pfad berührt (geänderte Dateien mit `telegram` /
`inbound_telegram` / `trip_command_processor` im Pfad), MUSS mit gesetzter
`GZ_TELEGRAM_TEST_CHAT_ID` (+ `GZ_TELEGRAM_BOT_TOKEN`) UND explizitem
`GZ_TELEGRAM_LIVE=1` (Opt-in-Gate, Issue #1014) der funktionale Live-Test
laufen — AC-3/AC-4 dürfen NICHT skippen:

```bash
GZ_TELEGRAM_LIVE=1 GZ_TELEGRAM_TEST_CHAT_ID=<test-chat-id> GZ_TELEGRAM_BOT_TOKEN=<staging-bot-token> \
  uv run pytest tests/tdd/test_issue_686_telegram_functional_live.py -v
```

Ein SKIPPED Telegram-Live-Test zählt **nicht** als grün. Das
`staging_gate.py --write-verdict`-Gate erzwingt das automatisch: berührt der
committete Scope (HEAD~1..HEAD) Telegram und `GZ_TELEGRAM_TEST_CHAT_ID` fehlt,
verweigert es das Verdict (Exit ≠ 0) und blockiert damit das Issue-Close-Gate
(Issue #686, AC-5).

## Schritt 4: Test-Trip aufraeumen

Den auf Staging angelegten Test-Trip wieder loeschen, damit Staging sauber bleibt.

## Schritt 5: Nachweis schreiben

NUR wenn alle relevanten Schritte erfolgreich waren — als Nachweis fuer den
Pre-Prod-Schritt. Die Datei MUSS die Felder `verified_commit`, `staging_verdict` und strukturierte `findings` enthalten (Issue #521):

Die Attestation wird **commit-getaggt** unter `.claude/e2e_verified/<HEAD>.json`
abgelegt (Issue #662) — so überschreiben parallele Sessions sich nicht mehr. Den
Pfad löst `staging_gate.py` selbst aus dem aktuellen HEAD ab; kein dupliziertes
Pfad-Wissen mehr.

```bash
# Findings als JSON-Array vorbereiten (was auf Staging geprüft wurde):
cat > /tmp/e2e_findings.json <<'EOF'
[
  {"ac": "AC-1", "status": "PASS", "url": "/", "evidence": "HIER BESCHREIBEN WAS GEPRÜFT WURDE"}
]
EOF

# Attestation commit-getaggt schreiben (.claude/e2e_verified/<HEAD>.json):
python3 .claude/hooks/staging_gate.py \
  --write-verdict "VERIFIED: <kurze Begründung>" \
  --findings-json /tmp/e2e_findings.json
```

⚠️ **Die Findings-Datei muss eine JSON-LISTE sein, jedes Element ein Objekt** — die
äußeren eckigen Klammern oben sind Pflicht, nicht Verzierung. Seit #1689 weist
`--write-verdict` jede andere Form **hart** ab: Exit ≠ 0, kein Artefakt, und die
Meldung nennt den vorgefundenen Typ (`gefunden: dict statt list`) bzw. Index und Typ
des ersten unbrauchbaren Elements. Abhilfe: Datei korrigieren, Aufruf wiederholen.

**Exit ≠ 0 heißt also zweierlei** — entweder das Verdict war BROKEN, oder die
Findings-Datei hatte die falsche Form. Die Meldung lesen, bevor man auf BROKEN
schließt. Vor #1689 lief der zweite Fall **still** durch: Wer ein JSON-Objekt statt
einer Liste übergab, dessen Schlüssel landeten als nackte Zeichenketten im Nachweis
(Exit 0, keine Meldung), und der Pflicht-Selftest stürzte Stunden später daran ab —
zweimal am 2026-08-10 (#1653, #1677).

## VERBOTEN

- Den lokalen Produktiv-API-Port (8090) beenden oder beschiessen.
- Die Go-API lokal als eigenen Prozess hochfahren, um gegen `localhost` zu testen.
- Einen Sammel-Versand ueber alle aktiven Touren ausloesen — nur der eine Test-Trip
  darf eine Mail erhalten, Empfaenger ausschliesslich `gregor-test@henemm.com`.
- IMAP gegen ein Gmail-Postfach pruefen — Stalwart (`mail.henemm.com`) ist die Quelle.
- In einen laufenden Systemd-Prozess von Live oder Staging eingreifen
  (stoppen/starten/neu starten).
- Produktiv-Trips fuer den Test verwenden.
- Den Nachweis schreiben, ohne die relevanten Schritte tatsaechlich durchlaufen zu haben.
