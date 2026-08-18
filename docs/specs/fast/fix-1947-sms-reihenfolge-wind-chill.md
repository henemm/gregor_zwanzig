# Mini-Spec: SMS-Reihenfolge respektiert Nutzer-Position von "Gefühlte Temperatur" / "Temperatur"

Issue: #1947

**Korrektur 2026-08-18 (nach Adversary-artigem Befund des Developer-Agent):**
Ursprüngliche Root-Cause-Annahme (fehlende Position → Sortier-Fallback in
`output/tokens/builder.py`) war **falsch** — der erste Fix in `trip_report.py`
(Position von `wind_chill` per `setdefault` auf die Kind-IDs spiegeln) war ein
Blindgänger: eine Mutations-Gegenprobe (Fix testweise deaktiviert) blieb grün,
weil die Kind-IDs bereits VOR dem Fix eine (falsche) Position hatten. Diese
Version ersetzt die alte Analyse vollständig.

## Ist-Stand (belegt, korrigierte Analyse)

In der SMS-Kanal-Reihenfolge (`WeatherV2Reihenfolge.svelte`) steht "Gefühlte
Temperatur" (`metric_id="wind_chill"`) an Position 1 von 8 — vom Nutzer so
gezogen. In der ausgelieferten SMS landet das zugehörige Symbol (`FD`) aber
ganz am Ende: `E11: W- WD:SW G35@5(36@14) R- PR- TH:- TH+:- SU10 FD11/18`.

**Echter Root Cause** liegt in `src/app/loader.py`, Funktion
`_append_derived_metrics()` (Zeile 766–792) mit der Regel-Tabelle
`_DERIVED_METRIC_RULES` (Zeile 756–763):

```python
_DERIVED_METRIC_RULES: tuple[tuple[str, str, Optional[str]], ...] = (
    ("temperature_night", "temperature", None),
    ("wind_chill_night", "wind_chill", None),
    ("temperature_day_low", "temperature", None),
    ("temperature_day_high", "temperature", None),
    ("wind_chill_day_low", "wind_chill", None),
    ("wind_chill_day_high", "wind_chill", None),
)
```

Existiert ein Eltern-Eintrag (z.B. `wind_chill`, vom Nutzer ausgewählt) in
einer Metrik-Liste — auch in `per_channel_layouts["sms"]` (DEC-6b, Zeile
774–778: läuft explizit auch pro Kanal) — und fehlt das Kind
(`wind_chill_day_high` etc.) dort noch, hängt der Loader es **automatisch**
an:

```python
metrics.append(MetricConfig(
    metric_id=child_id, enabled=any(mc.enabled for mc in parents),
    bucket="secondary", derived=True,
))
```

`enabled` wird vom Eltern-Flag geerbt — das Kind erscheint also im SMS-Output,
OHNE dass der Nutzer es je einzeln gewählt hätte. Problem: `bucket="secondary"`
ist **hart codiert**, unabhängig vom Bucket/Position der Elterngröße.
`src/app/models.py::_sorted_by_layout()` (Zeile 750–769) sortiert zuerst nach
Bucket-Rang (`primary`=0 vor `secondary`=1), erst danach nach `order`. Ein
`secondary`-Kind landet dadurch **strukturell immer hinter allen
primary-Metriken** — unabhängig davon, dass die Elterngröße selbst an
Position 1 (primary) steht. Das erklärt exakt das gemeldete Symptom.

**Betrifft nicht nur `wind_chill`:** Dieselbe Regel-Tabelle enthält auch
`temperature_night`/`temperature_day_low`/`temperature_day_high` als Kinder
von `temperature` — identischer Mechanismus, bisher nicht gemeldet, aber
strukturell derselbe Fehler, sobald ein Nutzer "Temperatur" in der
SMS-Reihenfolge weit vorne positioniert. PO-Entscheid 2026-08-18: **beide
Familien in einem Fix beheben**, da identischer Codeort und identischer
Mechanismus.

## Was ändert sich

- `src/app/loader.py::_append_derived_metrics()`: das angehängte
  `MetricConfig` für ein Kind übernimmt **Bucket und Position der
  Elterngröße** (aus `parents[0]`) statt hartcodiert `bucket="secondary"`
  ohne Position. Betrifft alle sechs bestehenden Regeln in
  `_DERIVED_METRIC_RULES` einheitlich (`temperature_*` und `wind_chill_*`) —
  kein Sonderfall pro Größe, keine zweite Zuordnungstabelle.
- Kein neuer Code in `trip_report.py` nötig — die Positions-Vererbung passiert
  jetzt an der Quelle (Ladezeit), bevor `_sms_metrics_ordered`/
  `_sms_position_by_metric` überhaupt gebaut werden. Der bisherige (wirkungslose)
  `setdefault`-Versuch in `trip_report.py` wird entfernt.

## Was sich nicht ändern darf

- `_sorted_by_layout()` selbst (Bucket-Rang-Sortierung) bleibt unangetastet —
  nur die WERTE, die abgeleitete `MetricConfig`-Einträge für `bucket`/`order`
  mitbekommen, ändern sich.
- Kein Verhalten für Trips ohne SMS-Kanal-Reihenfolge (`_sms_cascade_source`
  nicht `per_report`/`per_channel`) — dort bleibt `_sms_position_by_metric`
  leer wie bisher.
- Keine Änderung an E-Mail/Telegram-Spaltenlogik über das hinaus, was die
  korrekte Bucket/Position-Vererbung ohnehin bewirkt (dort sollte eine
  Elterngröße in `primary` ihre Kinder nun ebenfalls als `primary` an
  passender Stelle zeigen — das ist die KORREKTE Konsequenz, nicht ein
  Nebenschaden, da die Kinder bisher fälschlich immer als `secondary`
  einsortiert wurden).
- Falls ein Kind bereits einen EIGENEN, expliziten Eintrag in der Liste hat
  (weil es je selbst wählbar wurde), greift `_append_derived_metrics()` ohnehin
  nicht (Zeile 782–784: `continue`, wenn Kind schon existiert) — unverändert.
- Kein Roundtrip-/Persistenz-Verhalten ändern: `derived=True` bleibt, Kinder
  werden weiterhin nicht zurückgeschrieben (Docstring-Garantie Zeile
  767–772).

## Acceptance Criteria

- **AC-1:** Given eine SMS-Kanal-Reihenfolge, die NUR "Gefühlte Temperatur"
  (`wind_chill`) an Position 0 vor anderen Metriken führt, When das
  Abend-Briefing gerendert wird, Then erscheinen die Symbole der real
  abgeleiteten Kind-Größen (FL/FD/FN) im SMS-Text vor den nachfolgend
  positionierten Metriken, nicht mehr strukturell am Ende.
- **AC-2:** Given dieselbe Konstellation mit "Temperatur" (`temperature`)
  statt "Gefühlte Temperatur", When das Abend-Briefing gerendert wird, Then
  erscheinen die Symbole der Kind-Größen (N/L/D) ebenfalls vor den
  nachfolgend positionierten Metriken — derselbe Mechanismus, dieselbe
  Korrektur, keine Sonderbehandlung pro Metrik-Familie.
- **AC-3:** Given ein Trip ohne SMS-Kanal-Reihenfolge (globaler Fallback,
  keine wind_chill/temperature-Familie beteiligt), When das Briefing
  gerendert wird, Then bleibt der SMS-Text byte-identisch zum Verhalten vor
  diesem Fix.
- **AC-4:** Given der Fix in `loader.py::_append_derived_metrics()` wird
  testweise auf die alte, hartcodierte `bucket="secondary"`-Zuweisung
  zurückgesetzt (Mutations-Gegenprobe), When dieselben Tests aus AC-1/AC-2
  laufen, Then werden genau diese Tests ROT — der Test beweist damit
  tatsächlich den Fix, nicht nur eine zufällig grüne Fassade.

## Manuelle Test-Schritte

1. Trip mit SMS-Kanal-Reihenfolge: "Gefühlte Temperatur" an Position 1,
   danach Wind/Regen/etc.
2. SMS-Vorschau (`GET /api/preview/{id}/sms`) prüfen: `FL`/`FD`/`FN`
   erscheinen jetzt vorne, nicht mehr am Ende.
3. Gleiche Probe mit "Temperatur" statt "Gefühlte Temperatur".

## Inline-Test (wird während Implementierung geschrieben)

- [ ] Test über den echten Produktionspfad (`TripReportFormatter().
  format_email()` → `report.sms_text`, Muster
  `tests/tdd/test_sms_user_metric_order.py`): SMS-Kanal-Reihenfolge enthält
  NUR die Elterngröße (`wind_chill`, NICHT die Kind-IDs literal!) an
  Position 0, mehrere andere Metriken danach — Assert, dass `FD`/`FL`/`FN`
  im `sms_text` VOR den nachfolgend positionierten Symbolen erscheinen.
  **Wichtig (Mutations-Lehre aus dem ersten Anlauf):** die Kind-IDs dürfen im
  Test NICHT selbst in die Kanal-Layout-Liste geschrieben werden — sonst
  bekommen sie unabhängig vom Fix bereits einen Eintrag und der Test wird
  blind für die eigentliche Ableitungs-Logik. Die Kinder müssen über
  `_append_derived_metrics()` real entstehen (also NICHT literal im Test
  konstruiert werden).
- [ ] Gleicher Test für `temperature` → `temperature_day_low`/`_day_high`/
  `_night` (K/D/N).
- [ ] Mutations-Gegenprobe (PFLICHT laut CLAUDE.md): Fix in `loader.py`
  testweise deaktivieren (Bucket/Position wieder hartcodiert) → beide Tests
  müssen dann ROT werden. Nachweis im Adversary-/Fix-Report dokumentieren.
- [ ] Regressions-Charakterisierung: ohne SMS-Kanal-Reihenfolge bleibt das
  Verhalten byte-identisch zum Bestand.
