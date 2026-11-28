# Context: fix-2221-dpc-gueltigkeit

## Request Summary

Issue #2221 (aus #1199, Eintrag B2-60): `DpcSource` (italienischer Zivilschutz) erzeugt
`OfficialAlert`s ohne `valid_from`/`valid_to`. Folgen: Mail/Telegram zeigen keine
„Gültig:"-Zeile, das Melde-Gedächtnis (#1245/#1657) führt den Schlüssel mit `none|none`
und kann Warnungen verschiedener Bezugstage derselben Zone nicht trennen,
`filter_alerts_to_window` behält DPC-Warnungen immer (fail-safe statt Fensterabgleich).

## Related Files

| Datei | Rolle |
|---|---|
| `src/services/official_alerts/dpc.py:162-217` | `_select_day_records` (Bezugstag) und `_alerts_for_zone` (erzeugt Alerts ohne Fenster) — Fix-Ort |
| `src/services/official_alerts/models.py:28-29` | `OfficialAlert.valid_from/valid_to` (Optional, Hausnorm aware UTC, #1345) |
| `src/services/official_alerts/base.py:62-91` | `filter_alerts_to_window` — Alerts ohne Fenster bleiben immer |
| `src/output/renderers/alert/official_alerts.py:486-499` | `_warn_hour`: SMS-Stunde `@h`; bei 00:00–23:59 Ortszeit = ganztägig → `None` (bewusst kein Token) |
| `src/output/renderers/alert/official_alerts.py:1074-1091` | `_format_validity`: „Fr 31.07. · ganztägig" |
| `src/output/renderers/alert/official_alerts.py:545-560` | `official_alert_state_key` — Zeitraum Teil der Identität |
| `src/output/renderers/alert/official_alerts.py:590-760` | #1657 Berührung/Containment-Logik, greift nur mit Fenster |
| `tests/tdd/test_dpc_bulletin_source.py` | bestehende DPC-Tests, `_NOW_FN`-Uhrhaken, echte Fixtures |
| `tests/fixtures/dpc/*.zip` | echte Bulletins (`ruhetag_20260730_1511`, `unwettertag_20260118_1515`) |

## Existing Patterns

- Andere Quellen (vigilance, meteoalarm, geosphere, caaml) setzen `valid_from`/`valid_to` aus der Quelle.
- Ganztags-Konvention der Renderer: Ortszeit 00:00 bis 23:59 → „ganztägig", SMS ohne Stunde.
- **Behördenbeleg:** das `Cap_<ts>.xml` im DPC-Zip trägt für den Bezugstag
  `onset 2026-07-31T00:00:00+02:00`, `expires 2026-07-31T23:59:59+02:00` (Fixture
  `ruhetag_20260730_1511.zip`). Das Fenster ist also amtlich der ganze Bezugstag in
  italienischer Ortszeit (Europe/Rome).

## Dependencies / Dependents

- Upstream: `_select_day_records` liefert den Bezugstag (Ausgabetag bzw. +1 bei `tomorrow`).
- Downstream: Trip-Alarm (`trip_alert.py:3436ff`), Ortsvergleich-Alarm (`compare_official_alert.py:294ff`),
  Melde-Gedächtnis, Mail-/Telegram-„Gültig"-Zeile, SMS-Warnblock, `alert_log` (`event_at`/`event_end_at`).

## Existing Specs

- `docs/specs/modules/feat_1427_dpc_warn_fallback.md` (DPC-Quelle, Bezugstag AC-3)
- `docs/specs/modules/fix_1657_warnfenster_identitaet.md` (Fenster in der Identität)

## Risks

- **SMS-Zeit-Token:** Bei ganztägigem Fenster entfällt `@h` nach Hauskonvention bewusst.
  Das Issue nennt „SMS-Zeit-Token fehlt" — mit Fenster 00:00–23:59 Rome bleibt die SMS
  ohne Stunde (korrekt: ganztägig), Mail/Telegram zeigen „ganztägig" mit Datum.
  Für Orte mit anderer Zeitzone als Rome (Compare-Ort ohne tz → kein Stundenteil) unkritisch.
- **Bezugstag in UTC:** `_select_day_records` nutzt `_NOW_FN().date()` in UTC. Zwischen
  00:00 und 01:00/02:00 italienischer Zeit gilt noch der Vortag. Mit Fenster würde das
  Vortagsfenster dann in `filter_alerts_to_window` korrekt herausfallen bzw. als Vortag
  erscheinen. Ob der Bezugstag auf Rome-Datum umgestellt wird → Analyse-Entscheid.
- Bestandseinträge im Melde-Gedächtnis mit `none|none`-Schlüssel: nach dem Fix neuer
  Schlüssel → eine DPC-Warnung kann einmal erneut gemeldet werden (Übergang).

## Analysis

**Type:** Bug (nutzersichtbar: fehlender Gültigkeitszeitraum bei DPC-Warnungen)

**Root Cause (belegt):** `src/services/official_alerts/dpc.py:194-217` (`_alerts_for_zone`) baut
`OfficialAlert(...)` ohne `valid_from`/`valid_to`. Der Bezugstag ist in `fetch()` bekannt
(`_select_day_records`, dpc.py:162-172), wird aber nicht an die Alerts weitergereicht.
Nebenursache: `_select_day_records` vergleicht `_NOW_FN().date()` in **UTC** statt im
italienischen Kalendertag. Zwischen 00:00 und 01:00/02:00 Ortszeit wird so der Datensatz
des Vortags gewählt, mit Fenster würde die Warnung dann mit dem Datum von gestern erscheinen.

**Amtliches Fenster:** `Cap_<ts>.xml` im Zip: `onset <Bezugstag>T00:00:00+02:00`,
`expires <Bezugstag>T23:59:59+02:00` → ganzer Bezugstag Europe/Rome.

### Affected Files

| Datei | Change | Inhalt |
|---|---|---|
| `src/services/official_alerts/dpc.py` | MODIFY | Bezugstag aus Rome-Datum; `_alerts_for_zone(row, ref_day)` setzt `valid_from` = Bezugstag 00:00 Europe/Rome, `valid_to` = 23:59:59 Europe/Rome, beides als aware UTC (Hausnorm #1345) |
| `tests/tdd/test_dpc_bulletin_source.py` | MODIFY | neue Tests: Fenster bei today/tomorrow, Rome-Mitternachtsgrenze, Gültig-Zeile „ganztägig", Identität trennt zwei Bezugstage |
| `docs/specs/modules/fix_2221_dpc_gueltigkeit.md` | CREATE | Spec |

**Scope:** 1 Quell-Datei, ~20 LoC; Tests ~80 LoC. **Risiko:** Mittel-niedrig: nur die
DPC-Quelle ändert sich, die Downstream-Pfade (Fensterfilter, Gedächtnis, Renderer) sind
für andere Quellen längst mit Fenster in Betrieb.

### Technical Approach

1. `_select_day_records` liefert zusätzlich den Bezugstag (`date`), berechnet aus
   `_NOW_FN().astimezone(ZoneInfo("Europe/Rome")).date()`.
2. `_alerts_for_zone(row, ref_day)` setzt das Fenster; `fetch()` reicht `ref_day` durch.
3. Keine Renderer-Änderung: ganztägig (00:00–23:59 Ortszeit) → Mail/Telegram „<Datum> · ganztägig",
   SMS ohne `@h` (Hauskonvention `_warn_hour`, gilt für alle Quellen gleich).

### Folgen / Übergang

- SMS: zeigt bei ganztägigen DPC-Warnungen bewusst keine Stunde. Das Issue nennt „SMS-Zeit-Token fehlt";
  die Ursache dafür (kein Fenster) wird behoben, die Darstellung folgt der Hausregel für ganztägig.
- Melde-Gedächtnis: der Schlüssel enthält künftig das Fenster statt `none|none`. Eine am Deploy-Tag schon
  gemeldete DPC-Warnung kann einmal erneut gemeldet werden (einmaliger Übergang, akzeptiert wie bei #1245).
- `filter_alerts_to_window`: DPC-Warnungen werden jetzt mit dem Briefing-/Etappenfenster abgeglichen statt
  immer zu bleiben (gewollt).

### Open Questions

Keine: das Fenster ist amtlich belegt, die Darstellung folgt bestehender Konvention.
