---
entity_id: fix_997_validator_bundle
type: module
created: 2026-07-03
updated: 2026-07-03
status: draft
version: "1.0"
tags: [validator, gate, bugfix, bundle, formatter, frontend]
---

<!-- Issues #997 #921 #993 — Workflow fix-997-validator-bundle -->

# Fix Validator Bundle — #997/#921/#993

## Approval

- [ ] Approved

## Purpose

Den False-Positive-Parsing-Bug im Briefing-Mail-Validator beheben (#997), der
das Renderer-Commit-Gate (#811) strukturell blockiert; danach den dadurch in
`fix-alert-bundle-958ff` zurückgestellten #921-Rest (toter
`report_type='alert'`-Zweig in `TripReportFormatter.format_email`) einspielen;
zusätzlich den unabhängigen `allOff`-Einzeiler im Alerts-Tab korrigieren
(#993, Adversary-Finding F002 aus demselben Vorgänger-Bündel).

## Source

> **Schicht-Hinweis:** Dieses Bündel betrifft **Tooling/Gate**
> (`.claude/hooks/briefing_mail_validator.py` — kein Produktivcode, sondern
> das Commit-Gate-Werkzeug selbst), **Python-Backend**
> (`src/formatters/trip_report.py`) UND **Frontend**
> (`frontend/src/lib/components/alerts-tab/AlertsTab.svelte`). Kein Go-API-Code
> betroffen.

| # | File | Identifier |
|---|------|------------|
| #997 | `.claude/hooks/briefing_mail_validator.py:158-179` | `_column_values()` |
| #997 | `.claude/hooks/briefing_mail_validator.py:182-198` | `_column_hours_sum()` |
| #921 | `src/formatters/trip_report.py:619-620` | toter `report_type='alert'`-Sonderfall in `_email_subject()`-artigem Helper (Zeile 604ff, Methode um Zeile 595) |
| #993 | `frontend/src/lib/components/alerts-tab/AlertsTab.svelte:50` | `allOff`-Derived |

## Estimated Scope

- **LoC:** ~40-60 (deutlich unter dem Workflow-LoC-Limit von 250, kein
  Override nötig).
- **Files:** 3 (1 Gate-Tooling, 1 Backend-Formatter, 1 Frontend-Komponente)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Renderer-Commit-Gate `renderer_mail_gate.py` | intern | Blockiert jeden Commit, der `src/formatters/*.py` staged, bis Modus-Matrix-Vertragstest UND frischer grüner `briefing_mail_validator.py`-Lauf vorliegen — betrifft #921-Rest direkt |
| `tests/tdd/test_issue_811_mode_matrix.py` | intern | Modus-Matrix-Vertragstest, Pflicht-Nachweis vor dem #921-Commit |
| `tests/tdd/test_issue_733_briefing_mail_validator.py`, `tests/tdd/test_issue_833_gate.py` | intern | Bestehende Validator-Tests — müssen nach #997 unverändert grün bleiben (Regressionsschutz, siehe AC-3) |
| `activeAlertableMetrics()` (`frontend/src/lib/components/alerts-tab/alertMetricTable.ts`) | intern | Liefert seit #933 bei leerer Zuordnung `[]` statt aller 14 Metriken — Ursache, warum `displayMetrics` heute leer sein kann und `allOff` dadurch vacuously `true` wird |

## Implementation Details

### #997 — `_column_values()` / `_column_hours_sum()`: Zeilen nach Zellenzahl filtern

Diagnose (Live-Staging, 2026-07-03, 3× reproduziert): `_column_values()`
mappt den Spalten-Index über die `<th>`-Header-Reihe der 14-spaltigen
Stundentabelle, liest aber Zellen aus **allen** `<tbody>`-Zeilen im Dokument.
Die #863-Guard-Annahme „Trend-/Stats-Tabellen haben kein `tbody`" ist seit dem
Mail-Redesign (#898-901-Ära) falsch — die Trend-Tabelle hat inzwischen ein
eigenes `tbody` mit 9-Zellen-Zeilen. Bei `idx=6` (Spalte „Regen") liefert die
Trend-Zeile `['So','31°','37°','0.0','0%','16','35','–','']` an Index 6 den
Wert `35` (Böen-Spalte der Trend-Zeile) statt eines echten Regenwerts — die
„kein Regen"-Plausibilitätsregel schlägt fälschlich fehl.

```python
# VORHER (.claude/hooks/briefing_mail_validator.py:158-179):
def _column_values(html: str, header_de: str) -> list[float]:
    headers = _th_tokens(html)
    try:
        idx = headers.index(header_de)
    except ValueError:
        return []
    tbody_content = " ".join(m.group(1) for m in _TBODY_RE.finditer(html))
    values: list[float] = []
    for row_html in _ROW_RE.findall(tbody_content):
        cells = _TD_RE.findall(row_html)
        if idx >= len(cells):
            continue
        num = re.search(r"-?\d+(?:\.\d+)?", _strip_tags(cells[idx]))
        if num:
            values.append(float(num.group(0)))
    return values

# NACHHER — zusätzlicher Zellenzahl-Guard: eine Zeile gehört nur dann zur
# Spalten-Header-Reihe, wenn ihre <td>-Anzahl exakt zur Header-Anzahl passt.
# Fremd-Tabellen (Trend/Stats) mit abweichender Spaltenzahl werden dadurch
# übersprungen, OHNE die Werte-Extraktion für passende Zeilen zu ändern.
def _column_values(html: str, header_de: str) -> list[float]:
    headers = _th_tokens(html)
    try:
        idx = headers.index(header_de)
    except ValueError:
        return []
    tbody_content = " ".join(m.group(1) for m in _TBODY_RE.finditer(html))
    values: list[float] = []
    for row_html in _ROW_RE.findall(tbody_content):
        cells = _TD_RE.findall(row_html)
        if len(cells) != len(headers):
            continue
        num = re.search(r"-?\d+(?:\.\d+)?", _strip_tags(cells[idx]))
        if num:
            values.append(float(num.group(0)))
    return values
```

`_column_hours_sum()` (Zeile 182-198, Sonnen-Regel) iteriert dieselbe Art
Zeilenquelle (`_ROW_RE.findall(html)` — sogar über das gesamte Dokument, noch
ungeschützter als `_column_values`, da kein `tbody`-Filter vorgeschaltet
ist) und ist derselben Fremd-Zeilen-Kontamination ausgesetzt. Identischer
Guard:

```python
# VORHER (Zeile 190-193):
for row_html in _ROW_RE.findall(html):
    cells = _TD_RE.findall(row_html)
    if idx >= len(cells):
        continue

# NACHHER:
for row_html in _ROW_RE.findall(html):
    cells = _TD_RE.findall(row_html)
    if len(cells) != len(headers):
        continue
```

`_column_num_sum()` ruft intern `_column_values()` auf und ist damit ohne
eigene Änderung mitgefixt.

**Kein Aufweichen der Regel:** Die „kein Regen"- und Sonnen-Plausibilitäts-
Schwellen (`_SONNE_TOL_MIN`, `rain >= 0.1`) bleiben unverändert — es wird
ausschließlich die Zeilen-**Auswahl** korrigiert, nicht die Bewertungslogik.

### #921 — Toten `report_type='alert'`-Zweig entfernen

Fertiger Patch aus Issue-Kommentar (2026-07-03), `scratchpad/921_trip_report.patch`:

```diff
diff --git a/src/formatters/trip_report.py b/src/formatters/trip_report.py
index f511b6dc..d39c10af 100644
--- a/src/formatters/trip_report.py
+++ b/src/formatters/trip_report.py
@@ -616,8 +616,10 @@ class TripReportFormatter:
         from output.subject import build_email_subject
         from output.tokens.dto import TokenLine

-        # 'alert' wird auf 'update' gemappt — semantisch identisch (Wetteränderung).
-        rt = "update" if report_type == "alert" else report_type
+        # Issue #921: kein produktiver Aufrufer mit report_type='alert' mehr —
+        # Alert-Versand läuft über output/renderers/alert/render.py. Toter
+        # 'alert'→'update'-Sonderfall entfernt; report_type wird durchgereicht.
+        rt = report_type
         # Stage-Name = explizite Stage falls vorhanden, sonst Datum als Diskriminator.
         # Bug #397 (F002): Datums-Fallback in Ortszeit, nicht UTC — sonst springt
         # das Datum bei Segment-Start nahe UTC-Mitternacht auf den falschen Tag.
```

**Vorbedingung im Implementierungsschritt (PFLICHT, aus PO-Entscheidung
2026-06-30 und Issue-Kommentar):** `grep -rn "report_type=.alert" src/ api/
cmd/` ausführen und bestätigen, dass kein produktiver Aufrufer mehr
existiert, bevor der Zweig entfernt wird — sonst würde `rt = report_type`
für einen noch aktiven Aufrufer das Verhalten stillschweigend ändern (statt
`'update'` liefe dann `'alert'` durch nachgelagerte Logik, die das evtl.
nicht kennt).

**Renderer-Gate-Reihenfolge (zwingend, da Datei unter `src/formatters/`
liegt):** Dieser Commit staged `src/formatters/trip_report.py` → das
Renderer-Commit-Gate (#811) verlangt vor dem Commit einen frischen Lauf von
`tests/tdd/test_issue_811_mode_matrix.py` UND einen frischen grünen
`briefing_mail_validator.py`-Lauf gegen eine echte, frisch zugestellte
Staging-Mail — beides erst möglich, nachdem #997 gefixt und deployed ist
(daher die Bündel-Reihenfolge #997 → #921, siehe
`docs/context/fix-997-validator-bundle.md`).

### #993 — `allOff` bei leerer Metrik-Auswahl

```svelte
<!-- VORHER (AlertsTab.svelte:50) — vacuously true bei leerem Array: -->
let allOff = $derived(displayMetrics.every((m) => currentLevels[m] === 'off'));

<!-- NACHHER — leere Auswahl ist NICHT "alles aus": -->
let allOff = $derived(displayMetrics.length > 0 && displayMetrics.every((m) => currentLevels[m] === 'off'));
```

Wirkt sich auf `class:subdued={allOff}` (Zeile 106, `.extra-cards` mit
`AlertCooldownCard`/`AlertQuietHoursCard`) aus: Bei leerer `displayMetrics`
(seit #933 erreichbar, wenn keine alert-fähige Wetter-Metrik aktiv ist) bleibt
der Cooldown-/QuietHours-Bereich normal sichtbar statt fälschlich gedämpft.

## Expected Behavior

- **Input (#997):** HTML einer Briefing-Mail mit einer 14-spaltigen
  Stundentabelle (eigenes `tbody`) UND einer separaten Trend-/Stats-Tabelle
  mit abweichender Spaltenzahl (ebenfalls eigenes `tbody`, seit dem
  Mail-Redesign).
- **Output (#997):** `_column_values()`/`_column_hours_sum()` liefern nur
  Werte aus Zeilen, deren Zellenzahl exakt der Header-Anzahl entspricht;
  Fremd-Tabellen-Zeilen werden ignoriert, echte Verletzungen weiterhin erkannt.
- **Input (#921):** `TripReportFormatter.format_email(report_type=...)` für
  alle real genutzten `report_type`-Werte (u. a. `'update'`).
- **Output (#921):** Identisches Verhalten wie vor der Änderung für
  `report_type='update'`; kein Code-Pfad mehr, der `'alert'` in `'update'`
  umschreibt.
- **Input (#993):** `AlertsTab` mit `trip.display_config.metrics` so
  konfiguriert, dass `activeAlertableMetrics()` eine leere Liste liefert.
- **Output (#993):** `.extra-cards` bleibt ohne `.subdued`-Klasse.
- **Side effects:** Keine Persistenz-/Schema-Änderungen in diesem Bündel.

## Acceptance Criteria

- **AC-1 (#997):** Given eine synthetische Briefing-Mail mit einer
  14-spaltigen Stundentabelle (Regen-Spalte durchgehend `0.0`, eigenes
  `tbody`) und einer separaten Trend-Tabelle mit 9 Zellen pro Zeile
  (eigenes `tbody`, Zahlenwert an genau dem Spalten-Index, den die
  Stundentabelle für „Regen" nutzt) und dem Pill-Text „kein Regen" / When
  `briefing_mail_validator.validate_message()` bzw. `_check_metric_plausibility()`
  direkt aufgerufen wird / Then liefert der Aufruf **keine** „kein Regen
  widerspricht Tabellen-Summe"-Fehlermeldung (PASS).
  - Test: Synthetische MIME-Mail nach dem Muster von
    `tests/tdd/test_issue_733_briefing_mail_validator.py` bauen (echtes
    `email.message`-Objekt, kein Mock), `_check_metric_plausibility()` bzw.
    `validate_message()` aufrufen, `errors == []` für die Regen-Regel prüfen.

- **AC-2 (#997, Nicht-Aufweichungs-Beweis):** Given dieselbe Fixture wie
  AC-1, aber mit einer echten Verletzung in der Stundentabelle selbst (z. B.
  eine Stundenzeile mit `Regen=0.4` bei gleichzeitigem Pill „kein Regen") /
  When `_check_metric_plausibility()` aufgerufen wird / Then meldet der
  Validator weiterhin einen Fehler (FAIL) — der Fix filtert nur Fremd-Zeilen
  heraus, deaktiviert die Plausibilitätsregel nicht.
  - Test: Wie AC-1, aber Stundentabellen-Zeile mit Regen-Wert >= 0,1 mm,
    `errors` nicht-leer erwarten.

- **AC-3 (#997, Regressionsschutz):** Given den Bestand an Validator-Tests
  vor dieser Änderung / When `uv run pytest
  tests/tdd/test_issue_733_briefing_mail_validator.py
  tests/tdd/test_issue_833_gate.py` nach dem Fix ausgeführt wird / Then sind
  alle bisher grünen Tests weiterhin grün (keine Verhaltensänderung für
  Zeilen, deren Zellenzahl bereits zur Header-Anzahl passt).
  - Test: Testlauf-Exit-Code 0, keine neuen Fehlschläge gegenüber dem
    Vor-Fix-Stand.

- **AC-4 (#921):** Given den Stand nach Entfernung des
  `'alert'→'update'`-Sonderfalls / When im Produktivcode nach
  `report_type=.alert` gesucht wird (`grep -rn "report_type=.alert" src/ api/
  cmd/`) / Then existiert kein produktiver Aufrufer mehr, UND
  `TripReportFormatter.format_email(report_type='update', ...)` verhält sich
  exakt wie vor der Änderung, UND der Modus-Matrix-Vertragstest
  (`tests/tdd/test_issue_811_mode_matrix.py`) läuft grün.
  - Test: Grep-Nachweis im Implementierungsschritt dokumentieren; bestehende
    `update`-Pfad-Tests und der Modus-Matrix-Vertragstest bleiben grün.

- **AC-5 (#921, Gate-Nachweis):** Given den Commit, der
  `src/formatters/trip_report.py` staged / When das Renderer-Commit-Gate
  (#811) greift / Then liegt ein frischer grüner Lauf von
  `.claude/hooks/briefing_mail_validator.py` gegen eine echte, frisch
  ausgelöste Staging-Briefing-Mail vor (Exit 0, gebauter Nachweis NACH dem
  #997-Fix — vorher strukturell unmöglich).
  - Test: Echte Staging-Mail auslösen (Port-8001-Trigger,
    validator-issue110-Konto, Trip mit aktuellen Etappen-Daten), Validator
    gegen die zugestellte IMAP-Mail laufen lassen, Exit-Code 0 zeigen.

- **AC-6 (#993):** Given einen Trip, dessen `display_config.metrics` so
  konfiguriert ist, dass `activeAlertableMetrics()` eine leere Liste
  liefert / When der Alerts-Tab rendert / Then trägt `.extra-cards` (Cooldown-
  und QuietHours-Karten) NICHT die `subdued`-Klasse.
  - Test: Playwright gegen Staging als eingeloggter Nutzer — Wetter-Metriken
    so reduzieren, dass keine alert-fähige Metrik mehr aktiv ist, Alerts-Tab
    öffnen, computed style / Klassenliste von `.extra-cards` auf Abwesenheit
    von `subdued` prüfen (echter Klick-Pfad + UI-Zustand, kein DB-Read).

- **AC-7 (#993, Regressionsschutz):** Given einen Trip mit mindestens einer
  aktiven alert-fähigen Metrik, bei der ALLE Sensitivitätsstufen auf `off`
  stehen / When der Alerts-Tab rendert / Then trägt `.extra-cards` weiterhin
  die `subdued`-Klasse (bestehendes „alles aus"-Verhalten bleibt für den
  nicht-leeren Fall erhalten).
  - Test: Playwright — eine Metrik aktivieren, deren Stufe auf „off" setzen,
    Alerts-Tab öffnen, `subdued`-Klasse auf `.extra-cards` bestätigen.

## Erwartete Test-Brüche in Bestandstests

Voraussichtlich **keine**. Der Fix ist additiv: #997 verschärft nur die
Zeilen-Auswahl in zwei Helper-Funktionen (bestehende Zeilen mit korrekter
Zellenzahl sind unbetroffen, siehe AC-3), #921 entfernt einen laut Grep toten
Zweig ohne Wirkung auf den `update`-Pfad, #993 ändert eine Bedingung, die vor
#933 nie den leeren Fall erreichen konnte (kein bestehender Test deckt den
`displayMetrics.length === 0`-Fall mit der alten `allOff`-Logik ab, da dieser
Zustand vor #933 unerreichbar war).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine [no-adr]
- **Rationale:** Reiner Parsing-Bugfix am Gate-Tooling (#997), Entfernung
  eines bereits PO-entschiedenen toten Code-Zweigs (#921, Entscheidung vom
  2026-06-30) und ein Frontend-Bedingungsfix (#993) — keine der drei
  Änderungen trifft eine neue Richtungsentscheidung mit Tragweite über dieses
  Bündel hinaus.

## Offene PO-Fragen

Keine.

## Known Limitations

- AC-5 (#921-Gate-Nachweis) benötigt einen Staging-Trip mit aktuellen
  Etappen-Daten — laut Kontext-Dokument haben die meisten Trips im
  `validator-issue110`-Konto das Datum 2026-08-01 (leere Tabellen); ggf. muss
  im Implementierungsschritt ein neuer Kurz-Trip geseedet werden.
- Der `#863`-Kommentar in `_column_values()` („Trend-/Stats-Tabellen ohne
  tbody") bleibt nach dem Fix im Code stehen, ist aber überholt — sollte im
  Implementierungsschritt korrigiert oder entfernt werden, um künftige
  Verwirrung zu vermeiden (kein AC, aber Teil einer sauberen Umsetzung).

## Changelog

- 2026-07-03: Initial spec erstellt — Bündel #997/#921/#993
