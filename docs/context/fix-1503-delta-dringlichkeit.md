# Context: fix-1503-delta-dringlichkeit

**Issue:** #1503 — Wetter-Änderungsalarme tragen immer die Dringlichkeit `MODERATE`
**PO-Entscheid 2026-08-04:** Option (1) aus dem Ticket — Dringlichkeit wird aus dem
**Ausmaß der Änderung** abgeleitet. Bedienung bleibt unverändert (nur Empfindlichkeit wählbar).
**Track:** Standard (Intake-Summe 3: Umfang low, Auswirkung high, Unsicherheit medium)

## Request Summary

Der Δ-Detektor berechnet eine abgestufte Dringlichkeit (MINOR/MODERATE/MAJOR aus dem
Überschreitungsfaktor), erreicht diese Berechnung aber nie: ein Vorrang-Eintrag pro Metrik
überschreibt sie mit einem festen Wert. Ergebnis: jede Vorhersage-Änderung ist `MODERATE`.
Der Vorrang soll für Δ-Regeln entfallen, damit die vorhandene Abstufung wirkt.

## Der Pfad, gemessen (nicht vermutet)

```
metric_alert_levels (Nutzer-Empfindlichkeit je Metrik)
  → alert_preset.expand_per_metric_levels()          severity=WARNING hart gesetzt  ← Ursache 1
  → WeatherChangeDetectionService.from_alert_rules()  severity_overrides[field]=WARNING
  → detect_changes()                                  Override gewinnt vor          ← Ursache 2
                                                      _classify_severity()
  → WeatherChange.severity  (ChangeSeverity: MINOR|MODERATE|MAJOR)
```

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_preset.py:129`, `:210` | Setzt `severity=AlertSeverity.WARNING` hart in jede erzeugte Regel — für alle drei Empfindlichkeitsstufen und alle Metriken (Ursache 1) |
| `src/services/weather_change_detection.py:629-635` | Der Vorrang: liegt ein `_severity_overrides`-Eintrag vor, wird `_classify_severity()` nie aufgerufen (Ursache 2) |
| `src/services/weather_change_detection.py:787-810` | `_classify_severity(delta, threshold)` — die vorhandene, getestete Abstufung: `ratio = |delta|/threshold`, ≥2.0 → MAJOR, ≥1.5 → MODERATE, sonst MINOR |
| `src/services/weather_change_detection.py:472-550` | `from_alert_rules()` — befüllt `severity_overrides[field] = rule.severity` (nur im DELTA-Zweig, Zeile 536) |
| `src/services/weather_change_detection.py:215-219` | `_RULE_SEVERITY_TO_CHANGE_SEVERITY`: INFO→MINOR, WARNING→MODERATE, CRITICAL→MAJOR |
| `src/services/deviation_alert_engine.py:183-197` | `_select_detector()` — baut die Regeln **ausschließlich** aus `metric_alert_levels`; `trip.alert_rules[].severity` wird auf dem Alarmpfad nicht gelesen |
| `src/services/deviation_alert_engine.py:244-256` | `_highest_severity()` — MINOR/MODERATE/MAJOR → `LOW`/`MODERATE`/`HIGH` fürs Protokoll |
| `src/services/alert_urgency.py:47-51` | `urgency_from_changes()` (aus #1461 S3a) delegiert unverändert dorthin — **muss nicht angefasst werden** |
| `src/output/renderers/sms_trip.py:537-541` | Einziger Renderer, der `WeatherChange.severity` liest: Sortierreihenfolge der SMS-Kürzel |
| `frontend/src/routes/+page.svelte:399-405` | Cockpit-Punkt: `HIGH`→rot, `MODERATE`→gelb, sonst neutral |
| `src/services/validator_render_service.py:117-126` | Vorschau-Endpunkt baut `WeatherChange` aus einem Frontend-Payload (severity kommt von außen, wird nicht gerechnet) |
| `frontend/src/lib/components/alerts-tab/alertPreviewHelpers.ts:57-84` | Baut diesen Payload; `SEVERITY_MAP[rule.severity]` → immer `moderate` |

## Wer `WeatherChange.severity` tatsächlich liest — vollständig

Gemessen über `grep -rn "\.severity" src/` mit Aussortieren der Namensgleichen:

1. `deviation_alert_engine._highest_severity()` → Protokoll-Eintrag → **Cockpit-Punktfarbe**
2. `sms_trip.format_alert_sms()` → **Sortierung** der Kürzel in der Alarm-SMS
3. `validator_render_service` → Vorschau-Rendering (Wert kommt vom Frontend, nicht aus dem Detektor)

**Nicht** betroffen: die Alarm-Mail. `src/output/renderers/alert/model.py:111` hat eine
gleichnamige Funktion `severity(e)` — die berechnet aber die **numerische** Schwellüberschreitung
eines `AlertEvent` und hat mit `ChangeSeverity` nichts zu tun. Wer nach „severity" greppt, hält
die beiden leicht für dasselbe.

## Existing Patterns

- **Abstufung nach Überschreitungsfaktor** ist bereits die Hausform (`_classify_severity`) —
  es wird keine neue Rangfolge gebraucht (Wiederholungsklasse #1481).
- **Vokabular ist festgelegt** (#1459): `LOW`/`MODERATE`/`HIGH` im Protokoll,
  `minor`/`moderate`/`major` im Detektor. Keine vierte Stufe, keine zweite Zahlenreihe.
- **Konservativer Rückfall** (#1461 S3a, `hazard_symbols.LEVEL_LETTERS.get(level, "H")`):
  Unbekanntes wird als dringender behandelt, nie als stiller. Richtung übernehmen.
- **#1460**: Für Gefahrenstufen-Größen entscheidet das erreichte **Niveau**, nicht die
  Sprunggröße — dieselbe Unterscheidung greift hier wieder (s. Risiko 1).

## Dependencies

- **Upstream:** `metric_alert_levels` (Nutzer-Einstellung) → `expand_per_metric_levels()` →
  `from_alert_rules()`. Trip und Ortsvergleich nutzen **denselben** Weg
  (`compare_alert.py:324-331` ruft dieselbe Funktion) — ein Fix wirkt auf beiden Seiten.
- **Downstream:** Alarm-Protokoll (`alert_log.append_entry(severity=…)`) → Go-API →
  Cockpit-Punkt; SMS-Sortierung.

## Existing Specs / ADRs

- `docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md` — Vorgänger-Scheibe; benennt diesen
  Befund unter „Known Limitations" und lässt den Δ-Pfad ausdrücklich unverändert
- `docs/context/feat-1461-s3a-kanal-dringlichkeit.md` — Analyse zur Kanal-Schwelle (S3b)
- ADR-0009 / ADR-0013 — Δ bleibt Δ, keine absoluten Grenzen; wird von Option (1) eingehalten
- ADR-0043 / #1460 — keine generische Ordinal-Registry ohne zweiten Anwendungsfall

## Risks & Considerations

### 🔴 Risiko 1 — Gewitterstufe: der Überschreitungsfaktor ist dort das falsche Maß

`THUNDER_LEVEL` hat in allen drei Empfindlichkeitsstufen die Schwelle `1` und wird seit #1460
**nicht** über die Sprunggröße ausgelöst, sondern über das erreichte Niveau. Ohne Vorrang
liefe `abs(delta)/1` — also die Zahl der übersprungenen Stufen — in die Einstufung:

| Übergang | Stufen-Delta | ratio | Ergebnis |
|---|---|---|---|
| kein Gewitter → höchste Stufe | 3 | 3.0 | MAJOR ✅ |
| mittlere → höchste Stufe | 1 | 1.0 | **MINOR** ❌ |

Das Erreichen der höchsten Gewitterstufe würde als „gering" eingestuft. Das ist ein echter
Fehler, kein Randfall — die Spec muss für Niveau-Größen eine eigene Ableitung festlegen
(Vorschlag: aus dem **erreichten Niveau**, analog `urgency_from_radar`: konvektiv = HIGH).
Die Alternative wäre, Niveau-Größen bis auf Weiteres bei `MODERATE` zu belassen — dann bleibt
ausgerechnet die gefährlichste Größe unabgestuft.

### 🔴 Risiko 2 — die Severity-Falle aus #638 darf nicht zurückkommen

`trip_alert._filter_significant_changes()` (`:625-640`) gibt **alle** Änderungen zurück, mit
ausdrücklichem Kommentar: „severity is label only, not filter criterion". Der frühere
MODERATE/MAJOR-Filter hat Alarme still verschluckt. Heute filtert **nirgends** etwas nach
`ChangeSeverity` — deshalb kann dieser Fix für sich genommen keinen Alarm stumm schalten.
Das muss so bleiben und gehört als Invariante in die Spec (samt Test).
Ab S3b wird Dringlichkeit erstmals wieder filterwirksam — dann ist die Korrektheit dieser
Einstufung Voraussetzung, nicht Kosmetik.

### ⚠️ Risiko 3 — Division durch die Schwelle

`_classify_severity()` rechnet `abs(delta) / threshold` ohne Nullprüfung. Auf dem heutigen
Alarmpfad ist das gefahrlos (alle Schwellen in `_PRESET_TABLE` sind > 0, nachgesehen), aber
der Vorrang hat diese Stelle bisher zusätzlich abgeschirmt. Ein billiger Wächter gehört dazu.

### ✅ Risiko 4 — Alarm-Vorschau: nachgemessen, löst sich auf

Erste Vermutung: `alertPreviewHelpers.ts` erzeugt eine Beispiel-Änderung mit `threshold * 1.2`
(ratio 1.2 ⇒ real künftig **MINOR**) und schickt dazu fest `severity: 'moderate'` — die
Vorschau würde also eine Einstufung zeigen, die der echte Pfad nicht mehr liefert. Die
Vorschau ist auch **erreichbar** (`AlarmeTab.svelte:337`, geteilt von Trip und Ortsvergleich).

Nachgemessen ist dieses Feld auf dem Vorschau-Weg jedoch **wirkungslos**: die Alarm-Mail
druckt `ChangeSeverity` nirgends. `alert/render.py` sortiert ausschließlich über die
numerische Schwellüberschreitung aus `alert/model.py:111`. Der einzige Renderer, der
`ChangeSeverity` überhaupt liest, ist die **SMS** — und die ist nicht Teil der Vorschau.

⇒ **Kein Frontend-Anteil in dieser Arbeit.** Die Änderung bleibt reiner Python-Kern.

### ⚠️ Nebenbefund (kein Teil dieser Arbeit, Kandidat für #1199)

`AlertMetricRow.svelte:98-107` bietet je Metrik eine Auswahl **Info / Warnung / Kritisch**.
Diese Auswahl ist doppelt wirkungslos: (a) `AlertMetricTable.svelte` ist nirgends eingebunden
— der einzige Treffer ist ein Bauplan-Kommentar in `ListTable.svelte:10`; (b) selbst
gespeichert würde sie nicht gelesen, weil der Alarmpfad seit #946 nur `metric_alert_levels`
auswertet. Das ist zugleich die Antwort auf die Frage aus dem Ticket, **warum** der Vorrang
2026 (#222) eingeführt wurde: damals durfte man die Dringlichkeit je Regel selbst wählen, und
der Vorrang sollte diese Eingabe respektieren. Die Eingabe gibt es nicht mehr — geblieben ist
ein Vorrang für einen Wert, den niemand mehr setzt.

## Prüfung mit zwei Nutzern

Der Fix liegt in einer reinen Rechenfunktion ohne Nutzerbezug (`WeatherChangeDetectionService`
bekommt Schwellen übergeben, liest nichts aus `data/users/`). Die Mandantentrennung wird durch
diese Änderung weder berührt noch gelockert; die Protokoll-Schreibstellen
(`alert_log.append_entry(self._user_id, …)`) bleiben unverändert.
