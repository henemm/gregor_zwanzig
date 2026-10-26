# Context: fix-2439-prod-antwortzeit-nachweis

## Request Summary
Epic #2506, Rest von #2439: Der Live-Nachweis der Befehls-Antwortzeit ist auf Staging zu etwa zwei Dritteln erbracht (E-Mail/Telegram DE, AC-2/3/4/11/12/14). Offen sind die Punkte, die Staging strukturell nicht messen kann: Korsika `fr_direct` (AC-5), echte Premium-SMS (AC-1/AC-4) und Telegram-Wetterbefehle (AC-4). Dazu kommt ein Test-/Spec-Widerspruch bei AC-5.

## Stand (Messlauf 24.10., Treiber v1.1, PR #2600)
Messtest 13 PASS / 4 FAIL / 4 SKIP.
- PASS: AC-3, AC-4 (E-Mail, DE), AC-12, AC-14, AC-11, AC-2.
- Nicht auf Staging messbar:
  - AC-5 Korsika: `egress_guard` sperrt Météo-France (`fr_direct_fenster` nie kalt). Ersatzquelle `eu_direct`: HEUTE 17,4–17,9 s, MORGEN 12,9–13,2 s.
  - AC-1 SMS: `received_total 0`, die Herkunftssperre lässt auf Staging keine Premium-SMS zu.
  - AC-4 Premium-SMS/Telegram: `NOT_MEASURABLE_ON_STAGING`.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/e2e/test_push_eingang_befehle_staging.py:283-303` | `test_ac5_…korsika…` verlangt `fr_direct_fenster` und assertet hart. Auf Staging nie grün, obwohl die Spec (AC-5, v1.1 vom 22.10.) „NOT_MEASURABLE_ON_STAGING“ vorschreibt. Das erklärt vermutlich die 4 FAIL. |
| `tests/e2e/test_push_eingang_befehle_staging.py:185,252` | Vorbilder für korrektes `pytest.skip("NOT_MEASURABLE_ON_STAGING …")` bzw. Ausgabe. |
| `.claude/tools/befehl_antwortzeit.py` | Prod-Lese-Werkzeug (nur lesend): seven.io-Journal, Prod-Dauerzeilen aus `gregor-python`, Push-Status. Nutzt `--since`/`--kanal`. Behandelt bisher keine Quelle `fr_direct` und löst nichts aus. |
| `.claude/tools/befehl_messlogik.py` | Gemeinsame Messlogik: `kalt_laeufe(..., quellen=…)`. |
| `.claude/tools/staging_messlauf.py` | Staging-Treiber (v1.1), nicht für Prod gedacht. |
| `docs/specs/modules/feat_2439_befehle_antwortzeit.md` | Haupt-Spec. AC-5 (Z. 115): Korsika-Messung auf Produktion, Zielgröße < 60 s. |
| `docs/specs/modules/feat_2439_push_eingang_prod_scharf.md` | Prod-Messung = Lese-Werkzeug bzw. Statusabfrage; „Der PO wird nicht zum Tester gemacht“. |
| `docs/specs/modules/feat_2439_staging_messtreiber.md` | Spec des Treibers. |

## Existing Patterns
- `NOT_MEASURABLE_ON_STAGING` als `pytest.skip` mit Verweis auf den Prod-Messweg, nie als bestanden.
- Prod-Messung nur lesend, mit Journalzeilen `befehl=… kanal=… trip=… dauer_ms=…` und Quellenfeld der Gewitterquelle.
- Prod-Befehle dürfen nur an einen Test-Trip gehen (CLAUDE.md: kein Sammel-Versand über alle Trips). Die Trip-Konfiguration des PO bleibt unangetastet.

## Dependencies
- Upstream: `src/services/trip_command_processor.py` (Dauerzeile), `src/app/egress_guard.py` (Staging-Sperre Météo-France), Prod-Journal `gregor-python`, seven.io-API.
- Downstream: Epic #2506 (letzter inhaltlicher Rest neben #2327), das Schließen von #2439.

## Existing Specs
Siehe Tabelle oben. Alle drei #2439-Specs sind `implemented`. Der Rest braucht eine Delta-Spec zu AC-5 und zum Prod-Nachweis.

## Risks & Considerations
- Der AC-5-Test lässt sich nur so grün bekommen: auf Staging als `NOT_MEASURABLE` überspringen und die Prod-Messung getrennt führen. Eine Abschwächung der Grenze (< 60 s) ist ausgeschlossen.
- Der Prod-Messweg misst bisher nur Vorhandenes, er löst keinen Befehl aus. Ein kalter `fr_direct`-Lauf auf Prod braucht einen Korsika-Trip. Es ist offen, welcher Trip das ist und wie die Kaltheit hergestellt wird, ohne Prod-Daten oder Live-Server anzufassen (Prod-Neustart ist verboten).
- Echte SMS und Telegram auf Prod sind ein Versand an echte Empfänger. Sie gehen nur über einen Test-Trip mit Test-Empfängern bzw. die zweite seven.io-Nummer (Memory: Premium-SMS-Empfang prüft der Agent selbst).
- Die Sitzungen `2346-s2` und `majestic-dazzling-knuth` (#1412) arbeiten in anderen Strängen, kein Konflikt.

## Analysis

### Type
Bug (Test-/Spec-Widerspruch) + Nachweis-Lücke (Prod-Messung). Kein Produktcode-Defekt belegt.

### Befunde
1. **Test widerspricht der Spec.** Spec AC-5 (v1.1, 22.10.) sagt: auf Staging `NOT_MEASURABLE_ON_STAGING` für `fr_direct`, Test prüft nur „Antwort vorhanden + Quelle `eu_direct` ehrlich ausgewiesen“. `test_ac5_…korsika…` (tests/e2e/test_push_eingang_befehle_staging.py:282-302) verlangt weiter ≥3 kalte `fr_direct_fenster`-Läufe → auf Staging nie grün (`egress_guard` sperrt Météo-France). Erklärt 2 der 4 FAIL (HEUTE/MORGEN parametrisiert). Die übrigen 2 FAIL sind im Issue nicht benannt → in /30 per Test-Lauf `--collect-only`/Treiber-Ergebnis klären (nicht raten).
2. **Prod-Lese-Werkzeug `befehl_antwortzeit.py` kennt keine Gewitterquelle.** Die Dauerzeile `befehl=… kanal=… trip=… dauer_ms=…` trägt kein Quellenfeld; `fr_direct` und Kaltheit lassen sich nur über die Zeilen `fr_direct_fenster … downloads=N` im selben Fenster ableiten (`befehl_messlogik.kalt_laeufe(quellen=("fr_direct_fenster",))` kann das bereits). Das Werkzeug nutzt `kalt_laeufe` bisher nicht, gibt keine Kaltheit aus und bildet keine Zielgrößen-Prüfung (<60 s / Median <45 s).
3. **Kein Korsika-Trip im Prod-Bestand des Nutzers `default`** (Namens-Grep auf korsika/gr20/corse: 0 Treffer). Der Prod-Nachweis AC-5 braucht also einen Test-Trip (Anlage durch Agenten, Trip-Konfiguration des PO bleibt unberührt).
4. **Prod-Auslösung:** Echter Befehl nötig (E-Mail: Test-Absender mit Nutzerbindung; SMS: zweite seven.io-Nummer sendet an die Prod-Nummer; Telegram: Prod-Testchat). Kaltheit ohne Prod-Neustart: Datum, das nie abgerufen wurde (MORGEN+n bzw. Trip mit frischem Datum) – Neustart von `gregor-python` ist verboten.

### Affected Files
| File | Change | Beschreibung |
|------|--------|--------------|
| tests/e2e/test_push_eingang_befehle_staging.py | MODIFY | AC-5: auf Staging Antwort + Quelle `eu_direct` prüfen, `fr_direct`-Kaltlauf als `pytest.skip("NOT_MEASURABLE_ON_STAGING …")` |
| .claude/tools/befehl_antwortzeit.py | MODIFY | Prod: je Lauf Kaltheit/Quelle (`fr_direct_fenster`/`dwd_fenster`) ausgeben, Zielgrößenprüfung (max<60 s, Median<45 s), `--trip`-Filter |
| tests/test_befehl_antwortzeit*.py | MODIFY/CREATE | Kern-Test für neue Auswertung (aufgezeichnete Journalzeilen als Fixture) |
| docs/specs/modules/feat_2439_*.md | MODIFY (Delta) | Prod-Nachweis-Protokoll + AC-5-Testbeschreibung angleichen |

### Scope
Dateien: 3–4, ca. +120/-20 LoC. Risiko: **NIEDRIG** für Code (Test + Lese-Werkzeug, kein Produktpfad). Der Prod-Teil (echte Befehle) ist Betriebsarbeit; Risiko dort = Versand an echte Empfänger → nur Test-Trip/Test-Empfänger.

### Technischer Ansatz
- Scheibe A (Code, klein): AC-5-Test an die Spec angleichen; Prod-Werkzeug um Kaltheit/Quelle/Zielprüfung erweitern, Kern-Test mit realen Journalzeilen. Zielgrenze 60 s bleibt unverändert.
- Scheibe B (Nachweis, kein Code): Prod-Test-Trip Korsika anlegen, ≥3 kalte HEUTE/MORGEN über E-Mail (Pflicht), SMS (zweite seven.io-Nummer), Telegram (Prod-Testchat); mit Werkzeug messen; Einzelwerte ins Issue. Verfehlt `fr_direct` die 60 s ⇒ Befund im selben Ticket (Abrufpfad beschleunigen), keine Ausnahme. Danach Test-Trip entfernen, AC-15/AC-5-Antwortmail aus echtem Prod-Mailbefehl belegen, #2439 schließen.

### Offene Fragen
- [ ] Welche 2 weiteren Messtests waren die FAIL vom 24.10. (außer AC-5)?
- [ ] Prod-Telegram-Testchat vorhanden/gebunden? (Staging-Konto verwaist)
- [ ] Quellenfeld in der Dauerzeile ergänzen (Produktcode) oder weiter über Fensterzeilen ableiten (Empfehlung: ableiten, kein Produktcode-Eingriff)
