# Context: fix-2541-telegram-live-messskript (Issue #2541)

## Request Summary

PO-Auftrag (2026-10-08): Staging-Messläufe für `/e2e-verify` dürfen keinen Lesezugriff
des Agenten auf die Staging-`.env` brauchen. Ein geprüftes Mess-Skript im Repo liest die
Zugangsdaten selbst, gibt nur Ergebnisse zurück; der Nachweis entsteht weiter nur über
`staging_gate.py --write-verdict` nach echter Messung. Abgrenzung: keine Lockerung des
Klassifikators, keine breite sudo-Regel, Gate-Mechanik nicht aufweichen.

Stand 2026-11-27 (Intake-Kommentar): Mail-Befehlsweg ist gelöst (#2542
`staging_befehl_pruefen.py`, #2439 `staging_messlauf.py`). **Offen bleibt nur der
Telegram-Live-Test (`/e2e-verify` Schritt 3c).**

## Ist-Zustand Schritt 3c

`.claude/commands/e2e-verify.md:273-303`: Der Agent soll von Hand aufrufen
```
GZ_TELEGRAM_LIVE=1 GZ_TELEGRAM_TEST_CHAT_ID=<id> GZ_TELEGRAM_BOT_TOKEN=<token> \
  uv run pytest -m live tests/tdd/test_issue_686_telegram_functional_live.py -v
(dasselbe für tests/tdd/test_telegram_live_zweisprachig.py)
```
aus dem Staging-Checkout (`/home/hem/gregor_zwanzig_staging`, `e2e-verify.md:206-207`),
mit Werten aus dessen `.env` → genau dieser Lesezugriff wird vom Auto-Mode-Klassifikator gestoppt.

## Related Files

| Datei | Rolle |
|---|---|
| `.claude/commands/e2e-verify.md:273-303` | Rezeptur Schritt 3c (wird ersetzt) |
| `.claude/hooks/staging_gate.py:240-279` `_telegram_live_gate()` | Verdict-Gate: berührt HEAD~1..HEAD Telegram → `e2e_telegram_live.gate()` |
| `.claude/hooks/e2e_telegram_live.py:17-45` `gate()` | prüft NUR, ob `GZ_TELEGRAM_TEST_CHAT_ID` im Env gesetzt ist — kein Nachweis, dass der Live-Test lief/grün war |
| `tests/tdd/test_issue_686_telegram_functional_live.py` (582 Z.) | Live-Tests AC-3/AC-4 (Opt-in `GZ_TELEGRAM_LIVE=1`, Marker `live`, CWD-`data`) |
| `tests/tdd/test_telegram_live_zweisprachig.py` (109 Z.) | Live-Test hilfe EN/DE (#2681) |
| `tests/tdd/_telegram_live_fixture.py` | Test-Nutzer `tg-live-e2e`, Pipeline-Aufruf |
| `.claude/tools/staging_befehl_pruefen.py:537-548` `_lade_env()` | **Vorbild-Muster**: liest `/home/hem/gregor_zwanzig_staging/.env` selbst, `GZ_*` aus Env überschreibt |
| `.claude/tools/staging_messlauf.py` | Vorbild: Treiber gibt nur Ergebnis/Exit-Code zurück, Fortschritt nach stderr |
| `/home/hem/gregor_zwanzig_staging/.env` | `-rw-r-----+ hem:claude-gregor` (für hem lesbar; Hürde ist der Klassifikator, nicht die Dateirechte). Enthält u. a. `GZ_TELEGRAM_BOT_TOKEN`, `GZ_TELEGRAM_TEST_CHAT_ID`, `GZ_TELEGRAM_TEST_BOT_TOKEN` (Staging-Bot #1363) |
| `docs/reference/gates_und_ratschen.md:925` | Gate-Liste (Doku-Nachzug) |

## Existing Patterns

- Tools unter `.claude/tools/` lesen die Staging-`.env` direkt, geben keine Secrets aus,
  Exit 0/1/2 (bestanden / Befund / Umgebungsfehler).
- Live-Tests laufen per `uv run pytest -m live` aus dem Staging-Checkout (CWD-`data`).

## Existing Specs

- `docs/specs/modules/fix_2542_staging_befehl_pruefweg.md`
- `docs/specs/modules/feat_2439_staging_messtreiber.md`
- `docs/specs/modules/issue_686_telegram_functional_live_tests.md`

## Dependencies / Dependents

- Abhängig: Staging-Checkout, `uv`, Telegram-Bot-API, Staging-`.env`.
- Abhängige: `/e2e-verify`, `staging_gate.py --write-verdict` (Telegram-Gate), `/70-deploy`.

## Risks / offene Designfragen (für Analyse)

1. **Gate-Abstimmung:** Ohne Env-Variable beim Agenten verweigert `_telegram_live_gate()`
   das Verdict. Optionen: (a) Wrapper schreibt einen commit-gebundenen Ergebnis-Nachweis
   (nur PASSED-Zahlen, keine Secrets), Gate akzeptiert diesen statt nur der Env-Präsenz —
   das ist eine **Verschärfung** (heute reicht bloße Präsenz der Chat-ID); (b) Agent setzt
   nur einen Platzhalter — wäre Theater, verboten.
2. **Kein Secret-Leck:** pytest-Ausgabe (`-v`) könnte Chat-ID/Token in Fehlertexten zeigen
   → Ausgabe filtern/maskieren.
3. **SKIPPED ≠ grün:** Wrapper muss `0 selected`/SKIPPED als Befund (Exit 1) werten (#2813).
4. **Worktree vs. Staging-Checkout:** Tests müssen im Staging-Checkout laufen (CWD-data).
5. **Zwei Nutzer:** PO-Akzeptanz verlangt Test mit zwei verschiedenen Nutzern.
6. **Regel-Budget:** ersetzt die manuelle Rezeptur in Schritt 3c.

## Analysis

**Type:** Feature (Prüf-Werkzeug + Gate-Verschärfung), kein Produktcode.

### Kernbefunde
- `tests/tdd/_telegram_live_fixture.py:168-196` `load_staging_telegram_env()` liest
  `GZ_TELEGRAM_BOT_TOKEN`/`GZ_TELEGRAM_TEST_CHAT_ID` **bereits selbst** aus der Staging-`.env`
  (füllt nur fehlende Keys; abweichender Env-Wert → RuntimeError, Schutz gegen Prod-Creds).
  Die Handrezeptur in `e2e-verify.md:273-303` ist damit veraltet; nötig ist nur `GZ_TELEGRAM_LIVE=1`
  und eine von `GZ_TELEGRAM_*` bereinigte Umgebung.
- Rechte: `/home/hem/gregor_zwanzig_staging/data` hat ACL `user:hem:rwx`, `data/users/tg-live-e2e`
  gehört `hem` → **kein sudo nötig** (`_STAGING_RUN_COMMAND` mit sudo ist nur Beispieltext).
- Gate-Lücke: `staging_gate.py:240-279` → `e2e_telegram_live.gate()` prüft nur Env-Präsenz der
  Chat-ID, nicht ob der Live-Test lief/grün war. Mit dem Wrapper hat der Agent die Chat-ID nicht
  mehr → Gate würde blocken. Lösung = Verschärfung: Gate verlangt commit-gebundenen Ergebnis-Nachweis.
- Genutzt wird `GZ_TELEGRAM_BOT_TOKEN` (nicht `GZ_TELEGRAM_TEST_BOT_TOKEN`).

### Affected Files
| Datei | Change |
|---|---|
| `.claude/tools/staging_telegram_live.py` | CREATE (~170 LoC): pytest `-m live` beider Dateien im Staging-Checkout, `--junitxml`, Env ohne `GZ_TELEGRAM_*`, Auswertung, Maskierung, Nachweis |
| `.claude/hooks/e2e_telegram_live.py` | MODIFY: `gate()` prüft Nachweis-Datei (HEAD-gebunden, Sollnamen passed, skipped/failures/errors=0) statt Env-Präsenz |
| `.claude/hooks/staging_gate.py` | MODIFY: `_telegram_live_gate()` übergibt HEAD/Nachweis-Pfad |
| `.claude/commands/e2e-verify.md` | MODIFY: Schritt 3c = ein Aufruf (ersetzt Handrezeptur → Regel-Budget) |
| `tests/tdd/test_issue_686_telegram_functional_live.py` | MODIFY: AC-5-Gate-Tests auf Nachweis umstellen |
| `tests/tdd/test_staging_telegram_live.py` | CREATE: Auswertung, Maskierung, Gate, Zwei-Nutzer-Isolation |
| `docs/reference/gates_und_ratschen.md` | MODIFY: Telegram-Gate-Beschreibung |
| `.gitignore` / Nachweis-Transport (`scripts/e2e_nachweis_holen.py`) | prüfen, ggf. MODIFY |

### Scope / Risk
~6-8 Dateien, ~300 LoC inkl. Tests. Risiko mittel: Gate-Code (Adversary-Stufe hoch). Kein Produktcode.

### Technical Approach
1. Tool startet `uv run pytest -m live <686-Datei> <zweisprachig-Datei> -p no:cacheprovider --junitxml=<mktemp>`
   mit CWD Staging-Checkout, `GZ_TELEGRAM_LIVE=1`, alle `GZ_TELEGRAM_*` aus Env entfernt.
2. Grün nur, wenn alle Soll-Live-Tests (AC-3, AC-4 aus 686, `hilfe` EN→DE) `passed`, skipped=0,
   failures=0, errors=0 (inkl. Teardown-Wächter #2226). `0 selected`/SKIPPED = Exit 1 (#2813).
3. Ausgabe: nur Testnamen, Zähler, Fehlerklasse; keine pytest-Rohausgabe; Maskierung der .env-Werte
   und Token-Regex als zweite Schicht. Exit 0/1/2 wie Nachbar-Tools.
4. Nachweis bei Grün: eigener Ordner `.claude/e2e_telegram_live/<sha>.json` (nicht im Ordner der
   Staging-Attestationen, sonst räumt `prune_old_attestations` ihn mit ab); sha = HEAD des
   Staging-Checkouts; Inhalt: commit, Zähler, Testnamen, finished_at — keine Secrets.
5. Gate: Telegram-Scope → Nachweis für den verifizierten Commit Pflicht; Env-Chat-ID ist **kein**
   Ersatz mehr (sonst wäre die Verschärfung wirkungslos).
6. **Zwei Nutzer (Variante C + A, Tech-Lead-Entscheid):** Tool nimmt vor dem Lauf einen
   Fingerabdruck eines zweiten Test-Nutzers im Staging-`data` (legt ihn bei Bedarf an) und prüft
   nach dem Lauf Byte-Gleichheit → Lauf verändert nur `tg-live-e2e` (Mandantentrennung). Zusätzlich
   DE/EN über den vorhandenen zweisprachigen Test. Variante B (zweiter echter Chat) verworfen:
   bräuchte neue Secrets in der .env ohne zusätzliche Aussagekraft.

### Dependencies
Staging-Checkout auf dem zu prüfenden Commit (wie heute), Telegram-Bot-API, uv.

### Open Questions
Keine Produktfrage offen. Restrisiko (in Spec dokumentieren): Nachweis-Datei ist wie jede
Attestation theoretisch handschreibbar; HMAC-Härtung bewusst außerhalb des Scopes.

## Hinweise aus Phase 5 (RED) für /50-implement

- Die 686-Datei hat `pytestmark = pytest.mark.live`; `addopts` schließt `live` aus. Die AC-5-Tests dort laufen nur mit
  `uv run pytest tests/tdd/test_issue_686_telegram_functional_live.py -m live -k test_ac5_ -v -p no:cacheprovider` (ohne Netz). Für GREEN genauso wiederholen.
- Vertrag aus den Tests: `abschluss(exit_code, ordner, sha, ergebnis, geheimnisse)` → Datei nur bei 0, sonst None (vorhandener Nachweis bleibt byte-/mtime-gleich); `baue_befehl()[:3] == ["uv","run","pytest"]`; `gate(scope_touches_telegram=False)` ohne weitere Argumente aufrufbar; ungültiges XML ⇒ Exit 2; Umgebungsfehler-Meldungen nennen Checkout-Pfad, „uv“ bzw. „.env“ (auch `.env` als Verzeichnis); `fingerabdruck` ohne mtime; Testnamen mit Param-ID werden maskiert.
- AC-9: `gates_und_ratschen.md` braucht einen `##`/`###`-Abschnitt mit `e2e_telegram_live`, `staging_telegram_live.py`, „Nachweis“, „Restrisiko“; `e2e-verify.md` ohne `GZ_TELEGRAM_TEST_CHAT_ID=<` und `GZ_TELEGRAM_BOT_TOKEN=<`.
- Nebenbefund: `tests/tdd/test_telegram_live_zweisprachig.py:82` ruft `mod.gate(..., {})` positionell auf und erwartet 1 → Test auf `env={}` umstellen (oder Implementierung robust: kein gültiger Commit ⇒ 1).
