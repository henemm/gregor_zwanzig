# Context: fix-3219-selftest-botmenue-timeout (Issue #3219)

## Request Summary
Der Prod-Selbsttest (`.claude/hooks/prod_selftest.py`) meldete am 2026-11-20 zweimal Verdict FAIL allein wegen
`Bot-Menü-Check: Fehler beim Abrufen: The read operation timed out`. Prod war intakt (zwei Folgeläufe Exit 0,
29 Befehle). Ein einzelner Netz-Wackler bei Telegram sperrt damit das Issue-Close-Tor. Soll: eigenes, großzügigeres
Zeitlimit + ein Wiederholversuch für den Menü-Abruf; Zeitüberschreitung als solche benennen statt als Regression.

## Related Files
- `.claude/hooks/prod_selftest.py`
  - Z. 61 `PROBE_TIMEOUT = 8` (gilt für alle Proben über `_http_get`)
  - Z. 165 `_http_get(url, follow_redirects)` — urllib, `opener.open(req, timeout=PROBE_TIMEOUT)`, kein eigener Timeout-Parameter
  - Z. 540 `check_bot_menu(token, expected, api_base)` — EIN Versuch; jede Exception → `FAIL`, Detail `Fehler beim Abrufen: {exc}`
  - Z. 817–824 `main`-Ablauf Phase 4: `menu_finding["status"] == "FAIL"` → `verdict = "FAIL"` → Exit 1
  - Z. ~520 Fazit-Text für `FAIL`: „FAIL: Regression in Produktion (Bot-Menü oder AC). Issue NICHT schließen.“
  - Z. 844 `_check_bot_menu_prod()` — Token aus Prod-`.env`, Erwartung per AST aus `src/output/channels/telegram.py`
- `tests/tdd/test_issue_685_selftest_menu_gate.py` — echter lokaler HTTP-Socket (`_menu_server`), kein Mock; AC-2 PASS, AC-3 FAIL bei Abweichung. Muster für neue Tests (verzögernder Handler).
- `tests/tdd/test_selftest_auth_redirect.py:235` — patcht `_check_bot_menu_prod` (Aufrufer muss kompatibel bleiben).

## Ursachen-Befund (Messung 2026-11-27)
- Fünf Python-Läufe `urlopen` auf `api.telegram.org` aus dieser Maschine: DNS 0,00 s, gesamt 0,05–0,07 s, IPv4+IPv6.
  Die Vermutung „Adressauflösung/Verbindungsaufbau in `_http_get` ist langsam“ bestätigt sich nicht.
- Die Fehlermeldung `The read operation timed out` stammt aus der SSL-Lesephase (Handshake-Timeouts heißen
  `The handshake operation timed out`, Connect-Timeouts `timed out` in `URLError`). Die Verbindung stand also; die
  Antwort blieb > 8 s aus → einzelner, vorübergehender Hänger auf Telegram-/Netzseite, kein Python-Problem.
- Folgerung: Abhilfe ist Wiederholversuch + großzügigeres eigenes Zeitlimit, nicht eine andere HTTP-Bibliothek.

## Existing Patterns
- Ehrliche Gates (Spec `docs/specs/modules/gate_honesty_mail_selftest.md`): nicht Nachweisbares ist kein PASS.
- Eigene Status statt FAIL für Nicht-Prüfbares: `SKIPPED_AUTH_REDIRECT`, `SKIPPED_AUTH` (#1353/#1367).
- Tests mit echtem Socket statt Mock (Test-Politik CLAUDE.md).

## Dependencies / Dependents
- Aufrufer: `/70-deploy` → `prod_selftest.py` → Exit-Code entscheidet Issue-Close.
- Keine Produktlaufzeit-Abhängigkeit (reines Werkzeug, Label `cloud`, kein Prod-Deploy des Dienstes nötig).

## Risks
- Wiederholversuch darf echte Abweichungen (falsches Menü) nicht verdecken: nur bei Zeitüberschreitung/Netzfehler wiederholen, nie bei inhaltlichem Mismatch.
- Bleibt Telegram auch nach Wiederholung stumm: weiterhin nicht PASS (Gate-Ehrlichkeit), aber anders benannt als Regression. Ob Exit 1 bleibt → Analyse/Spec.
- Gesamtlaufzeit: max. 2 × großzügiges Limit (z. B. 2 × 20 s) verlängert den Selbsttest im Störfall.

## Analysis

**Type:** Bug (Werkzeug/Deploy-Gate, keine Produktlaufzeit)

### Befund (Bug-Intake + Plan, 2026-11-27)
- Kein systematischer Python-Langsamkeitsgrund: kein Proxy-/IPv6-Code, Socket-Timeout 8 s gilt je Operation; 8,1 s = ein blockiertes `recv` → einmaliger Hänger auf Telegram-/Netzseite. Menü-Check läuft NACH dem Proben-ThreadPool (kein Parallel-Einfluss).
- Beobachtete Ausnahme `TimeoutError("The read operation timed out")` aus `resp.read()` (Z. 180), eine `OSError`. Connect/Handshake → `URLError`/`ssl.SSLError` (ebenfalls `OSError`).
- **Zweiter Defekt:** `check_bot_menu` ignoriert den HTTP-Status. 429/5xx kommen als `HTTPError` → `_http_get` gibt (Status, Body) zurück → Body ohne `result` → `live=[]` → falsches *inhaltliches* FAIL („live=[] expected=[…]“).
- `main` Z. ~817: nur Menü-`FAIL` setzt Verdict FAIL; Fazit Z. ~521 sagt dann „Regression in Produktion“. Exit 0 nur für PASS/SKIPPED_ALL/SKIPPED_AUTH_REDIRECT/SKIPPED_AUTH.

### Entscheidung (Tech Lead): Variante (b)
| Variante | Laufzeit Störfall | Sperrt Issue-Close | Ehrlichkeit |
|---|---|---|---|
| heute (1×8 s, FAIL) | 8 s | ja, zu Unrecht | falsch („Regression“) |
| (a) Retry, dann FAIL + neuer Text, Exit 1 | ~42 s | ja | Text gut, sperrt bei jedem Telegram-Aussetzer weiter |
| **(b) Retry, dann `UNREACHABLE`, Exit 0, eigene Fazit-Zeile** | ~42 s | nein | gut: eigener Status, nie PASS, sichtbare Zeile |
| (c) wie b nur wenn Rest PASS | ~42 s | nein | wie b, Zusatzlogik ohne Mehrwert |

Begründung: gleiches Muster wie `SKIPPED_AUTH` (#1353/#1367): nicht belegbar ⇒ eigener Status + eigener Fazit-Text, kein PASS, kein Blockieren wegen externer Ursache. Ein Telegram-Ausfall ist keine Deploy-Regression; (a) würde das Issue-Ziel verfehlen.

### Affected Files
- `.claude/hooks/prod_selftest.py` — MODIFY (~50–70 LoC)
  - `_http_get(url, follow_redirects=False, timeout=None)` → `None` fällt auf `PROBE_TIMEOUT` zurück (andere Aufrufer Z. ~313/~362 unverändert).
  - Konstanten `MENU_TIMEOUT = 12`, `MENU_ATTEMPTS = 3`, `MENU_RETRY_PAUSE = 2` (Pause verdoppelt: 2 s, 4 s); per monkeypatch testbar.
  - `check_bot_menu`: Schleife nur um den Abruf. Wiederholen bei `OSError` und HTTP 429/5xx. Nach letztem Versuch: Transportfehler/429/5xx → `UNREACHABLE` (Detail: Versuchszahl + letzte Ursache, Wort „nicht erreichbar“). 200 + abweichendes Menü → FAIL ohne Retry. 200 mit nicht parsebarem Body / `ok:false`, 401/404 → FAIL ohne Retry.
  - `main`: `UNREACHABLE` setzt Verdict nicht auf FAIL; Bericht-Abschnitt Bot-Menü zeigt den Status; zusätzliche Fazit-Zeile „Telegram nicht erreichbar (nach 3 Versuchen) – Bot-Menü nicht belegt, keine Regression belegt …“, unabhängig vom Verdict.
- `tests/tdd/test_selftest_bot_menu_retry.py` — CREATE, echter lokaler Socket-Server: (1) erster Abruf hängt > Timeout, zweiter ok → PASS, genau 2 Requests; (2) hängt immer → UNREACHABLE, Exit-Mapping 0, Fazit ohne „Regression“; (3) 503 dauerhaft → UNREACHABLE; 502 dann 200 → PASS; (4) 200 falsches Menü → FAIL, genau 1 Request; (5) 401 → FAIL, 1 Request.
- Bestehende Tests (`test_issue_685_selftest_menu_gate.py`, `test_selftest_auth_required.py`, `test_selftest_auth_redirect.py`, `test_issue_671_bot_menu_autoset.py`, `test_prod_selftest_1708c_dead_trips_guard.py`) müssen grün bleiben.

### Scope / Risk
1 Quelldatei + 1 Testdatei. Risiko niedrig–mittel (Deploy-Gate-Code ⇒ Adversary-Risiko „hoch“, 2 Runden). Restrisiko: echter Menü-Defekt bei gleichzeitigem Telegram-Ausfall unbemerkt → durch sichtbare UNREACHABLE-Zeile abgedeckt.

### Open Questions
Keine an den PO (Werkzeug-Entscheidung, Präzedenz SKIPPED_AUTH).

## Übergabe-Notiz Phase 5 (2026-11-27)
- Spec automatisch freigegeben (Ampel grün), Phase `phase5_tdd_red` gesetzt, noch KEINE Testdatei geschrieben.
- Testmuster: Menü-Server + `_load_prod_selftest()` aus `tests/tdd/test_issue_685_selftest_menu_gate.py` (Z. 25-105); Handler um Zähler/Script (hängen via `time.sleep`, Statuscodes, Müll-Body) erweitern.
- Fazit/Exit-Prüfung (AC-2, AC-4): voller Lauf über `mod.run_selftest(e2e_path, workflow_name, scope="backend")` wie in `tests/tdd/test_selftest_auth_redirect.py`, Klasse `TestAC5AllLoginRedirectsMustNotYieldPassVerdict` (Z. ~206-290): `_check_health` und `check_dead_trips_guard` per monkeypatch stubben, `PROD_BASE` auf lokalen Server, `_check_bot_menu_prod` durch Aufruf von `mod.check_bot_menu("tok", expected, api_base=<lokaler Menü-Server>)` ersetzen, Bericht unter `REPO_DIR/docs/artifacts/<wf>/prod-selftest.md` lesen und aufräumen.
- RED-Beleg nach `docs/artifacts/fix-3219-selftest-botmenue-timeout/test-red-output.txt`; Testlauf nur mit der benannten neuen Testdatei.
