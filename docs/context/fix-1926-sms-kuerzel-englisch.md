# Context: fix-1926-sms-kuerzel-englisch

## Request Summary

Issue #1926: Sechs `col_label`-Werte im Wetter-Register (`src/app/metric_catalog.py`) sind
deutsch, obwohl ADR-0042 für diese Feldklasse ausdrücklich Englisch vorschreibt. Alle sechs
wurden **nach** dem ADR-Beschluss (2026-08-02) eingeführt. Ursprünglicher Anlass war eine
Nutzerfrage zu `FK` (`sms_code`/`compact_label`) — dieser Teil ist nach Nachmessung an
ADR-0042 **kein** Regelverstoß (Klasse 1 „Protokoll-Token", explizit von Sprachfragen
ausgenommen) und bleibt außerhalb des Zuschnitts.

## Betroffene Register-Einträge (`src/app/metric_catalog.py`)

| col_key | col_label (Ist, deutsch) | id | Commit | Datum |
|---|---|---|---|---|
| `temp_night` | `Nacht` (Zeile 150) | `temperature_night` | `b09e1ec9` (#1484) | 2026-08-06 |
| `felt_night` | `NachtF` (Zeile 239) | `wind_chill_night` | `94a38b18` (#1660 A) | 2026-08-09 |
| `temp_day_low` | `TagMin` (Zeile 176) | `temperature_day_low` | `c18f8eb7` (#1728 S1) | 2026-08-15 |
| `temp_day_high` | `TagMax` (Zeile 193) | `temperature_day_high` | `c18f8eb7` (#1728 S1) | 2026-08-15 |
| `felt_day_low` | `TagMinF` (Zeile 263) | `wind_chill_day_low` | `c18f8eb7` (#1728 S1) | 2026-08-15 |
| `felt_day_high` | `TagMaxF` (Zeile 274) | `wind_chill_day_high` | `c18f8eb7` (#1728 S1) | 2026-08-15 |

Alle 26 übrigen `col_label`-Werte im Register sind bereits englisch (`Temp`, `TmpMin`,
`Feels`, `Humid`, `Dew`, `Wind`, `Gust`, `WDir`, `Rain`, `Rain%`, `Conf`, `Thdr`, `CAPE`,
`SnowL`, `PType`, `Cloud`, `CldLow`, `CldMid`, `CldHi`, `Visib`, `Sun`, `UV`, `Press`,
`0°Line`, `SnowH`, `NewSn`) — Nachmessung per `grep -n "col_label=" src/app/metric_catalog.py`.

## ADR-0042 — die verletzte Regel

`docs/adr/0042-namensform-folgt-der-platzgrenze.md`:
- Klasse 2, Zeile „Kurzform … ≤6 Zeichen je Wort … **englisch** (`col_label`)".
- Bestätigt `#862`/`#849`: „Spaltenköpfe bleiben bewusst englisch (PO-Entscheidung)".
- Klasse 1 (`sms_code`, `compact_label`): „von Sprachfragen ausgenommen" — **deckt** `K`/`FK`,
  keine Handlungspflicht dort.

## Downstream-Verwendung von `col_label`

| Datei:Zeile | Rolle |
|---|---|
| `src/output/metric_format.py:204-212` | `style="col_label"` löst auf `metric.col_label` |
| `src/output/renderers/trip_report.py:708,716` | Stundentabellen-Spaltenkopf, Einheiten-Gruppierung |
| `src/output/renderers/email/helpers.py:548-577` | Trip-Mail-Spaltenköpfe + Legenden-Zeile (löst `col_label` gegen `label_de` auf, Nachtrag #1472) |
| `src/output/renderers/email/compare_html.py:479-521` | Ortsvergleich, `form="short"` |
| `src/app/models.py:649` | Kommentar referenziert `col_label` als Beispiel |

Legenden-Zeile unter der Stundentabelle (ADR-0042 Nachtrag #1472) löst jedes sichtbare
`col_label` gegen `label_de` auf — d. h. auch `Nacht`/`TagMin` etc. werden heute schon
"aufgelöst" angezeigt, aber der Spaltenkopf selbst bleibt deutsch, was die Regel verletzt
(die Auflösungspflicht ersetzt nicht die Sprachregel).

## Bestehende Ratschen

`tests/unit/test_sms_token_symbol_register_ratchet.py` (E7, #1856): rein strukturell
(Kollisionsfreiheit, Konsistenz der Kürzel-Tabellen) — **keine** Sprachprüfung für
`col_label`. Kein anderer Test erzwingt "col_label muss englisch sein".

## Risiken & Überlegungen

- `col_label` ist nutzersichtbar in Stundentabellen-Spaltenköpfen (Trip- und
  Vergleichs-Mail) UND in der Legenden-Zeile darunter — Änderung betrifft echte,
  ausgehende Mails. Golden-File-/Snapshot-Tests für die Mail-Ausgabe müssen nachgezogen
  werden.
- Neue englische Werte brauchen ≤6 Zeichen (ADR-0042-Grenze) und müssen sich von den
  bereits vergebenen 26 Werten unterscheiden (Kollisionsfreiheit, wie beim
  E7-Wächter-Muster).
- PO-Entscheid nötig für die konkreten neuen Wörter (Vorschlag in der Spec).
- Wächter-Erweiterung (Punkt 2 aus dem Ticket) muss False Positives bei Fachbegriffen wie
  `CAPE`, `UV` vermeiden — diese sind laut ADR-0042 explizit unübersetzt zulässig.

## Analysis

**Hinweis:** Diese Section wurde zunächst ohne die vom Skill vorgeschriebenen Subagenten
(bug-intake, Plan/Sonnet) erstellt — PO-Korrektur 2026-08-17 ("Nutze die Slash-Commands vom
Workflow"). Nachfolgend die per unabhängiger Agenten-Gegenprobe verifizierte, korrigierte
Fassung. Der Scope ist gegenüber der ersten Fassung gewachsen (echte SMS-Token-Änderung statt
reiner Label-Änderung bei zwei Metriken), PO-bestätigt 2026-08-17.

### Type
Bug (Regelverstoß gegen ADR-0042 bei `col_label`, PO-Konsistenzentscheid bei `compact_label`/`sms_code`).

### Kritischer Fund (Plan/Sonnet-Agent, nicht in der ersten Fassung enthalten)

`compact_label` wird beim Laden des Registers **automatisch aus `sms_code`/`sms_multi_symbols`
abgeleitet** (`metric_catalog.py` ~Zeile 813-855, Feature #1719 S4, PO-Regel „ein Kürzel, nicht
zwei"), außer eine ID steht in `COMPACT_LABEL_EXCEPTIONS` (aktuell nur `temperature`/`wind_chill`).
Konsequenzen:

- **`cape` (`CE`) und `snowfall_limit` (`SG`) sind bereits heute tote Literale** — die Ableitung
  liefert zur Laufzeit schon `CP`/`SL`. Reiner Aufräumer, kein Nutzer-Fehler.
- **`freezing_level`**: realer Fix ist `sms_code` `NL`→`FZ` (Zeile 639); `compact_label="0G"`
  (Zeile 632) ist ebenfalls schon tot, wird aus Lesbarkeit mitgezogen.
- **`temperature_day_low`/`wind_chill_day_low` (K→L, FK→FL) sind der einzige Fall mit echtem
  Implementierungsrisiko**: `sms_multi_symbols=("K",)`/`("FK",)` ist die Ableitungsquelle. Ein
  reiner Edit der `compact_label`-Literalzeile würde beim nächsten Laden automatisch wieder auf
  `K`/`FK` zurücküberschrieben — stiller No-Op. **PO-Entscheid 2026-08-17:** `sms_code`/
  `sms_multi_symbols` selbst ändern (echter SMS-Wire-Format-Token wird `L`/`FL`), keine
  `COMPACT_LABEL_EXCEPTIONS`-Ausnahme — entspricht der bestehenden #1719-S4-Architektur, kein
  neuer Mechanismus nötig.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/metric_catalog.py` | MODIFY | 6 `col_label`-Werte (Zeilen 150/176/193/239/263/274); `sms_code`/`sms_multi_symbols` `temperature_day_low` K→L, `wind_chill_day_low` FK→FL; `sms_code` `freezing_level` NL→FZ; tote Literale `compact_label` bei `cape`(CE→CP)/`snowfall_limit`(SG→SL)/`freezing_level`(0G→FZ) bereinigt |
| `tests/unit/test_trip_report_formatter_v2.py` | MODIFY | Zeile 238-239: `"Nacht" in evening/morning.email_html` → neuer `col_label`-Wert |
| `tests/unit/test_telegram_kuerzel_folgt_register.py` (#1719 S4) | PRÜFEN/MODIFY | aktiver Wächter, rechnet `compact_label` gegen `SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC` — muss nach `sms_code`-Änderung weiter grün sein, da beide Seiten gemeinsam wandern |
| `tests/unit/test_sms_token_symbol_register_ratchet.py:555` | MODIFY | `_AC9_ERWARTUNG`-Tabelle pinnt `"temperature_day_low": "K"` als Mutations-Gegenprobe explizit — muss auf `"L"` umgestellt werden; **plus Erweiterung**: neue Prüfung `col_label` gegen deutsche Wortbestandteile |
| ~10+ SMS-Testdateien (`test_sms_temperature_follows_metric_selection.py`, `test_night_temp_own_metric_selection.py`, `test_channel_metric_matrix.py`, `test_sms_snow_symbols.py`, `_hiking_window_fixtures.py`, u. a.) | MODIFY | verwenden `K`/`FK` als reale SMS-Symbole, wandern mit der `sms_code`-Änderung |
| `tests/tdd/test_trip_outlook_metric_selection.py`, `tests/tdd/test_night_temp_own_metric_selection.py` (label-Assertion), `tests/tdd/test_felt_night_catalog_exclusions.py`, `tests/unit/test_renderers_email.py` | KEIN CHANGE erwartet | prüfen `label_de`/anderen „Nacht"-Block, verifiziert unabhängig |
| `docs/adr/0042-namensform-folgt-der-platzgrenze.md` | KEIN CHANGE | Regel bleibt unverändert gültig |

### Scope Assessment
- Files: **5-8** bei nur `col_label`+`freezing_level`, **15+** inklusive aller SMS-Testdateien für K→L/FK→FL (gewählte Variante)
- Estimated LoC: ~60-100 (Register ~15-20 Zeilen + Wächter-Erweiterung + ~10+ Testdatei-Anpassungen, meist 1-Zeilen-Ersetzungen)
- Risk Level: MEDIUM — `col_label` und die toten Literale sind risikolos; die `sms_code`-Änderung bei K/FK berührt den echten SMS-Wire-Format-Text, den Endnutzer empfangen — sorgfältige RED-Phase nötig, um alle Pinning-Stellen zu finden

### Technical Approach
1. `col_label`-Fixes (6 Zeilen) + `test_trip_report_formatter_v2.py` — unabhängig vom Rest, risikolos.
2. `freezing_level` `sms_code` `NL`→`FZ` + tote Literale (`cape`/`snowfall_limit`/`freezing_level`) bereinigen.
3. `temperature_day_low`/`wind_chill_day_low`: `sms_code`/`sms_multi_symbols` `K`→`L`, `FK`→`FL` ändern — `compact_label` folgt automatisch über die bestehende Ableitung, **keine** `COMPACT_LABEL_EXCEPTIONS`-Ausnahme.
4. Wächter-Erweiterung (`col_label`-Sprachregel) **separat**: eine pauschale `compact_label==sms_code`-Regel würde bestehende, bewusst begründete Divergenzen brechen (`CT`≠`C`, `VS`≠`V`, `HP`≠`P`, `SU`≠`☀`) — Erweiterung muss auf der bestehenden Ableitungslogik/`COMPACT_LABEL_EXCEPTIONS` aufsetzen, keine neue Parallelregel einführen.

### Dependencies
- Upstream: keine — reine Registeränderung
- Downstream: `metric_format.py`, `trip_report.py`, `email/helpers.py`, `email/compare_html.py`, `narrow.py` (Telegram `compact_label`), `sms_trip.py` (SMS `sms_code` + Alarm-Änderungstexte)

### Open Questions
- [x] Konkrete englische Ersetzungswerte — PO-freigegeben (siehe Tabelle oben)
- [x] K/FK: echter SMS-Token-Fix vs. Anzeige-only — PO-Entscheid 2026-08-17: echter Token-Fix
- [ ] Wächter-Erweiterung: Negativliste deutscher Wortbestandteile für `col_label` (Positivliste bräuchte laufende Pflege pro neuem Fachbegriff) — Empfehlung aus erster Analyse bleibt gültig

## Bezug

Issue #1926 (dieses Ticket, korrigierter Scope), Epic #1435 (E6/E7), ADR-0042, `#862`/`#849`
(Ursprungsentscheidung Spaltenköpfe englisch).
