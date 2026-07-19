---
entity_id: thunder_night_at_destination_channels
type: bugfix
created: 2026-07-19
updated: 2026-07-19
status: superseded
superseded_by: Epic #1319 (einstellbares SMS-Tagesfenster, Scheibe A) — siehe docs/reference/sms_briefing_overview.md §5
version: "1.0"
tags: [gewitter, sms, compact_summary, telegram, email-pillen, adr-0025, issue-1317, superseded]
---

> **SUPERSEDED (2026-07-19):** Diese enge Lösung („nur die Nacht am Ziel ins Gewitter-Token") wurde in
> der PO-Diskussion durch das breitere Konzept **Epic #1319** ersetzt: ein einstellbares Tagesfenster
> (Default 04–19) für **alle** Wert-Token und **alle** Kurzformen. Maßgeblich ist jetzt
> `docs/reference/sms_briefing_overview.md` §5 und die Scheibe-A-Spec. Inhalt unten nur noch historisch.

# Gewitter nach Ankunft am Ziel — Kurzkanäle (SMS/Kurzzusammenfassung/Pillen/Telegram) einbeziehen

## Approval

- [ ] Approved

## Purpose

Ein Vorhersage-Gewitter, das erst **nach** der Wanderzeit einer Etappe auftritt (Datensatz
„Nacht am Ziel", Ankunft → 06:00 morgens), erscheint korrekt in der E-Mail-Detailtabelle, aber
strukturell **nie** in SMS-Token `TH:`, E-Mail-Kurzzusammenfassung, Metriken-Pillen im
E-Mail-Kopf oder der Telegram-Fußzeile — weil diese vier Kanäle Gewitter ausschließlich aus der
auf die Wanderzeit gefensterten Etappen-Zeitreihe ableiten und `night_weather` nie konsumieren.
Diese Spec erweitert das Gewitterfenster dieser vier Kanäle um die kommende Nacht am Ziel, ohne
die Ein-Quelle-Invariante aus ADR-0025 zu verletzen.

## Source

- **File:** `src/output/renderers/sms_trip.py`
- **Identifier:** `SMSTripFormatter.format_sms()` / `_segments_to_normalized_forecast()`

- **File:** `src/output/renderers/compact_summary.py`
- **Identifier:** `CompactSummaryFormatter.format_stage_summary()` / `_format_thunder()`

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `build_metrics_summary_pills()` (aufgerufen aus `email/compact.py:144`,
  `email/html.py:1317`, `email/plain.py:153`)

- **File:** `src/output/renderers/narrow.py`
- **Identifier:** `_tg_day_footer()` / `_windowed_thunder_severity()` (aufgerufen aus
  `render_telegram_bubbles()`)

- **File:** `src/output/renderers/trip_report.py`
- **Identifier:** `TripReportFormatter.format_email()` — Glue: hält bereits `night_weather`
  (Zeile 62/109-115) und `arrival_hour` (Zeile 112), muss beides an die vier Aufrufstellen oben
  durchreichen (Zeilen 126, 189-201, 224-233).

> Referenz für erwartetes Verhalten (darf nicht regressieren): `trip_report.py:280-323`
> (`_extract_night_rows`) — speist die Detailtabelle „Nacht am Ziel" korrekt aus `night_weather`.

## Estimated Scope

- **LoC:** ~150-220 (Produktivcode über 5 Dateien; Tests zusätzlich, zählen nicht gegen die
  Kern-Grenze). Risiko, die projektweite 250-LoC-Workflow-Grenze zu reißen — **kein
  eigenmächtiger Override**, bei Überschreitung PO-Permission einholen (CLAUDE.md).
- **Files:** 5 Produktivdateien (`sms_trip.py`, `compact_summary.py`, `email/helpers.py`,
  `narrow.py`, `trip_report.py`) + zugehörige Testdateien.
- **Effort:** high (sicherheitskritischer Pfad, vier Kanäle müssen synchron geändert werden,
  Konsistenz-Invariante aus ADR-0025 muss über alle Kanäle erhalten bleiben).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0025 (`docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`) | Architekturentscheidung | Definiert die Ein-Quelle-/Ein-Fenster-Invariante, die diese Spec novelliert (breiteres Fenster, gleiche Quelle) |
| `src/output/metric_format.py` (`thunder_label_value`, `thunder_ordinal`) | module | Kanonische Skalen — Render- vs. Sortier-Skala, dürfen nicht vermischt werden (ADR-0025 Entscheidung 3) |
| `src/services/trip_report_scheduler.py` (`_fetch_night_weather`, Zeile 833-835, 1177) | service | Liefert `night_weather` (Ankunft → 06:00 morgens); **seit #1313 für morning UND evening befüllt** (evening-Gate entfernt), gesteuert über `dc.show_night_block` — diese Spec ändert das Fetch-Gating **nicht** |
| `app.models.NormalizedTimeseries` | model | Datentyp von `night_weather`, enthält `ForecastDataPoint`-Liste mit `dp.thunder_level` |
| `trip_report.py:_extract_night_rows` | function | Referenzimplementierung des Ankunft→06:00-Fensters (Musterreferenz, nicht identisch aufzurufen) |

## Implementation Details

**Kernidee:** Die vier Kanäle erhalten künftig zusätzlich zur bestehenden, unveränderten
Wanderzeit-Fensterung eine zweite, gleich behandelte Quelle: die Stunden aus `night_weather`
zwischen Ankunft am Ziel (`arrival_hour`, Muster `trip_report.py:112`) und 06:00 des Folgetags,
**aber nur die Stunden, die zum Zeitpunkt der Report-Erzeugung noch in der Zukunft liegen**.
Beide Quellen liefern `dp.thunder_level`-Werte, die identisch über `thunder_label_value()`
(Render-Skala) bzw. den bestehenden `ThunderLevel != NONE`-Vergleich in einen Wahrheitswert
umgewandelt werden — **keine dritte Ableitung, kein neues Aggregat**.

Konkret pro Kanal:

- `TripReportFormatter.format_email()` (Glue) reicht `night_weather` und `arrival_hour` (statt
  sie wie bisher nur lokal für die Detailtabelle zu verwenden) zusätzlich an: den SMS-Aufruf
  (Zeile 224-233), den Compact-Summary-Aufruf (Zeile 126) und den Telegram-Bubbles-Aufruf
  (Zeile 189-201). Der bereits vorhandene `_sent_at`-Zeitstempel (Zeile 147,
  `datetime.now(timezone.utc)`) dient als Report-Erzeugungszeitpunkt für den
  Zukunfts-Cutoff und wird ebenfalls durchgereicht.
- `sms_trip.py` (`_segments_to_normalized_forecast` / `format_sms`): `thunder_samples` wird um
  die nach `report_time` liegenden `night_weather`-Stunden ergänzt, bevor der bestehende
  `_dedup_by_hour`-Schritt läuft — das bestehende `TH:`-Token (kein neues Token, siehe
  Design-Entscheidung unten) rendert das Ergebnis unverändert über `render_sms()`.
- `compact_summary.py` (`_format_thunder`): die übergebene `hourly`-Liste wird um die
  zukunftsrelevanten `night_weather`-Punkte ergänzt (analog zu `_collect_hourly_data`, das
  heute nur Segment-Fenster liefert), bevor `thunder_hours` ermittelt wird. Damit wechselt
  automatisch der Text von „kein Gewitter" auf „⚡ möglich HH:00–HH:00" bzw. „Gewitter möglich
  HH:00–HH:00".
- `email/helpers.py` (`build_metrics_summary_pills`): `all_dps` wird um die zukunftsrelevanten
  `night_weather`-Punkte ergänzt (dieselbe Erweiterung wie bei `_collect_hourly_data`), **bevor**
  die bestehende Pillen-Logik (`_pill_for_metric`) läuft — die Ergänzung gilt für die Thunder-Pille
  gleichermaßen wie für andere Metriken, damit keine neue Kanal-Divergenz zwischen Thunder-Pille
  und anderen Pillen entsteht. **Wichtig:** Diese Erweiterung hängt **nicht** an
  `dc.show_night_block` — das ist ein reiner Anzeige-Schalter für die Detailtabelle und darf die
  Gewitter-Konsistenz-Invariante nicht steuern.
- `narrow.py` (`_windowed_thunder_severity` / `_tg_day_footer`): analoge Ergänzung der
  betrachteten `dp.thunder_level`-Werte um die zukunftsrelevanten `night_weather`-Stunden.

**Zukunfts-Cutoff:** Eine `night_weather`-Stunde zählt nur, wenn ihr Zeitstempel `>= report_time`
ist (Report-Erzeugungszeitpunkt, s.o.). Das deckt sowohl den Fall ab, dass ein Report spät am
Abend erzeugt wird (ein Teil der „kommenden Nacht" liegt dann schon in der Vergangenheit), als
auch den Regressionsschutz für reine Wanderzeit-Fälle ohne Nacht-Gewitter.

**Kein neuer geteilter Helper wird in dieser Spec vorgeschrieben** — ob die vier Call-Sites eine
gemeinsame kleine Funktion (z. B. „liefere die zukunftsrelevanten Nacht-Stunden aus
`night_weather`") nutzen oder je Kanal identisch inline implementieren, ist Implementierungsdetail
der TDD/Implement-Phase. Bindend ist nur: alle vier Kanäle wenden **dieselbe** Fensterregel
(Wanderzeit + zukunftsrelevante Nacht bis 06:00) und **dieselbe** Rohdatenquelle
(`dp.thunder_level`) an — Konsistenz-Invariante aus ADR-0025.

### Design-Entscheidung: kein neues SMS-Token

`TH:` (Gewitter der berichteten Etappe) wird künftig aus dem erweiterten Fenster gespeist, es
entsteht **kein** neues Token. `TH+:` (Vorschau Folgetag, `thunder_forecast["+1"]`) bleibt
unverändert — das ist bereits eine andere Datenquelle (Trend-Kette) und nicht Teil dieses Fixes.
Begründung: Ein zusätzliches Token würde das 160-Zeichen-Budget weiter verknappen, ohne einen
fachlichen Zusatznutzen zu bieten — der Nutzer braucht die Aussage „gibt es auf dem Weg zur/nach
Ankunft an dieser Etappe ein Gewitter", nicht eine weitere Unterscheidung. Das hält ADR-0025
(eine Quelle, hier: ein breiteres, aber weiterhin einheitliches Fenster) intakt.

## Expected Behavior

- **Input:** `segments` (Etappen-Zeitreihe, unverändert) + `night_weather`
  (`NormalizedTimeseries`, Ankunft → 06:00 morgens; **seit #1313 für morning UND evening befüllt**,
  sofern `dc.show_night_block`) + Report-Erzeugungszeitpunkt.
- **Output:** SMS-`TH:`-Token, E-Mail-Kurzzusammenfassungssatz, Metriken-Pille (E-Mail-Kopf) und
  Telegram-Fußzeile zeigen ein Gewitter, sobald es entweder in der Wanderzeit **oder** in der
  zukunftsrelevanten kommenden Nacht am Ziel auftritt — konsistent mit der Detailtabelle „Nacht
  am Ziel".
- **Side effects:** keine. Reine Erweiterung der Eingabedaten-Windows in bestehenden
  Rendering-Pfaden; keine neuen Persistenz- oder Netzwerk-Zugriffe (kein neuer Fetch —
  `night_weather` existiert bereits).

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit Ankunft um 12:00 und einem Vorhersage-Gewitter um 14:00 in
  `night_weather` (nach Ankunft, vor Report-Erzeugungszeitpunkt am selben Abend erzeugt) / When
  `SMSTripFormatter.format_sms()` mit `segments` und `night_weather` aufgerufen wird / Then
  enthält die SMS ein `TH:`-Token mit Gewitter-Kennzeichnung (nicht mehr `TH:-`).
  - Test: echter Aufruf von `format_sms()` (nicht `render_sms()`/Token-Builder direkt) mit einer
    Zeitreihe, deren `dp.thunder_level` um 14:00 auf MED/HIGH steht — Assert auf den
    zurückgegebenen SMS-String.

- **AC-2:** Given denselben Fall wie AC-1 / When
  `CompactSummaryFormatter.format_stage_summary()` mit `segments` und `night_weather` aufgerufen
  wird / Then enthält der zurückgegebene Text „Gewitter möglich 14:00–15:00" (bzw. „⚡ möglich
  …" im friendly-Modus) statt „kein Gewitter"/keiner Gewitter-Erwähnung.
  - Test: echter Aufruf von `format_stage_summary()` (nicht `_format_thunder()` isoliert mit
    handgebauter `hourly`-Liste) mit derselben Zeitreihe wie AC-1.

- **AC-3:** Given denselben Fall wie AC-1 / When die E-Mail-Kopfzeile über
  `render_email()`/`build_metrics_summary_pills()` mit `segments` und `night_weather` erzeugt
  wird / Then zeigt die Thunder-Pille eine Gewitter-Aussage (nicht die grüne „kein
  Gewitter"-Pille) für die Etappe.
  - Test: echter Aufruf von `render_email()` (HTML- oder Plain-Pfad) — Assert auf Pillen-Text/Ton
    in der zurückgegebenen Ausgabe.

- **AC-4:** Given denselben Fall wie AC-1 / When `render_telegram_bubbles()` mit `segments` und
  `night_weather` aufgerufen wird / Then zeigt die Tages-Fußzeile „⚡ MED" oder „⚡ HIGH" statt
  „⚡ kein".
  - Test: echter Aufruf von `render_telegram_bubbles()` — Assert auf den Fußzeilen-Text der
    zurückgegebenen Bubble(s).

- **AC-5 (Konsistenz-Invariante):** Given denselben Fall wie AC-1 / When alle vier Kanäle
  (SMS, Kurzzusammenfassung, Pille, Telegram-Fußzeile) **und** die Detailtabelle „Nacht am Ziel"
  aus demselben `TripReportFormatter.format_email()`-Aufruf erzeugt werden / Then melden alle
  fünf Ausgaben übereinstimmend ein Gewitter für dieselbe Etappe (keiner widerspricht einem
  anderen) — Fortführung von ADR-0025 auf das erweiterte Fenster.
  - Test: ein einziger `format_email()`-Aufruf mit derselben Fixture, Assert über alle fünf
    Ausgabefelder des `TripReport` hinweg.

- **AC-6 (Zukunfts-Cutoff):** Given ein Gewitter in `night_weather`, dessen Zeitstempel **vor**
  dem Report-Erzeugungszeitpunkt liegt (bereits vergangene Nachtstunde) / When einer der vier
  Kanäle gerendert wird / Then löst diese vergangene Stunde **kein** Gewitter-Token/keine
  Gewitter-Pille aus (nur zukunftsrelevante Stunden zählen).
  - Test: Fixture mit `night_weather`-Zeitstempeln vor und nach einem fixierten
    Report-Erzeugungszeitpunkt; Assert, dass nur die zukünftige Stunde durchschlägt.

- **AC-7 (Regressionsschutz Wanderzeit):** Given eine Etappe ohne Gewitter in `night_weather`,
  aber mit unverändertem Wanderzeit-Verhalten wie vor diesem Fix / When alle vier Kanäle
  gerendert werden / Then bleibt das Ergebnis identisch zum Vorzustand, und die
  ADR-0025-Bestandstests (SMS-`TH:`/`TH+:`, Telegram-Fußzeile, Kopfzeile) bleiben grün.
  - Test: bestehende ADR-0025-Testsuiten (u. a. zu #1275) unverändert grün nach dem Fix.

- **AC-8 (kein neues SMS-Token):** Given den Fall aus AC-1 / When die SMS gerendert wird / Then
  bleibt die Token-Menge der SMS unverändert (`TH:` trägt die erweiterte Aussage, `TH+:` bleibt
  unverändert die Folgetag-Vorschau) und die SMS überschreitet weiterhin nicht 160 Zeichen.
  - Test: `format_sms()`-Aufruf mit `max_length=160`, Assert auf Zeichenlänge und Token-Anzahl.

- **AC-9 (fehlendes night_weather → fail-soft):** Given `night_weather is None` (z. B.
  `dc.show_night_block == False`, kein Zielsegment oder kein Nacht-Fetch) / When einer der vier
  Kanäle gerendert wird / Then verhält sich der Kanal exakt wie vor diesem Fix (reine
  Wanderzeit-Fensterung), ohne Fehler oder Absturz.
  - Test: `format_sms()`/`format_stage_summary()`/`build_metrics_summary_pills()`/
    `render_telegram_bubbles()` jeweils mit `night_weather=None` aufgerufen — Assert auf
    fail-soft-Verhalten (kein Exception, Ergebnis wie im Bestand).

- **AC-10 (gemeldeter Fall #1317 — MORGEN-Report):** Given ein **Morgen-Report** (Erzeugung
  ~07:00), dessen `night_weather` (Nacht nach der heutigen Ankunft, seit #1313 auch morgens
  befüllt) ein Gewitter um 14:00 enthält / When das komplette Briefing über
  `TripReportFormatter.format_email()` mit `report_type="morning"` erzeugt wird / Then zeigen
  SMS-`TH:`-Token, Kurzzusammenfassung, Metriken-Pille und Telegram-Fußzeile das Gewitter —
  übereinstimmend mit der Detailtabelle „Nacht am Ziel" (dies ist die exakte Reproduktion des
  gemeldeten Bugs: heute meldet die SMS `TH:-` und die Kurzzusammenfassung „kein Gewitter",
  obwohl die Tabelle das 14:00-Gewitter zeigt).
  - Test: ein `format_email(report_type="morning")`-Aufruf mit der Bug-Fixture; rot vor Fix
    (alle vier Kurzkanäle schweigen), grün nach Fix (alle zeigen das Gewitter).

## Known Limitations

- Amtliche Warnungen sind **nicht** Teil dieses Fixes — SMS/Kurzzusammenfassung konsumieren
  amtliche Warnungen weiterhin grundsätzlich nicht (eigener Folgeauftrag → Issue #1318).
- Es wird **kein neuer Datenstrom** eingeführt — ausschließlich das bereits vorhandene
  Vorhersage-`dp.thunder_level` aus dem bereits gefetchten `night_weather` wird zusätzlich
  konsumiert.
- `night_weather` ist **seit #1313 für morning UND evening** verfügbar (evening-Gate entfernt,
  gesteuert über `dc.show_night_block`) — dieser Fix greift daher in **beiden** Report-Typen.
  Der gemeldete Fall (#1317) war ein **Morgen-Report** (AC-10). Diese Spec ändert das
  Fetch-Gating selbst nicht.
- `TH+:` (SMS-Vorschau auf den Folgetag) bleibt unangetastet — andere Datenquelle
  (`thunder_forecast`), nicht Gegenstand dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025 (Novellierung: Fenster schließt kommende Nacht am Ziel ein)
- **Rationale:** ADR-0025 legt fest, dass alle Kanäle Gewitter aus derselben Rohdatenquelle
  (`dp.thunder_level`) und demselben Fenster ableiten, um Kanal-Widersprüche (#874, #1275)
  strukturell auszuschließen. Diese Spec ändert **nicht** die Quelle und **nicht** das Prinzip
  „ein Fenster für alle Kanäle" — sie erweitert lediglich die Definition des Fensters von
  „Wanderzeit der Etappe" auf „Wanderzeit der Etappe + zukunftsrelevante kommende Nacht am
  Ziel (bis 06:00 morgens)", weil die bisherige Definition eine strukturelle Lücke hatte: das
  bereits gefetchte `night_weather` floss in vier von fünf Kanälen (SMS, Kurzzusammenfassung,
  Pillen, Telegram-Fußzeile) nie ein, obwohl die Detailtabelle es korrekt zeigt. Die
  Konsistenz-Invariante (alle Kanäle stimmen überein) und die Skalen-Trennung
  (`thunder_ordinal()` vs. `thunder_label_value()`) bleiben vollständig erhalten — nur das
  Fenster wird für alle vier betroffenen Kanäle gleichzeitig breiter gezogen, nie für einzelne.

## Changelog

- 2026-07-19: Initial spec created for #1317 (Root-Cause-Analyse Phase 2: Strang 1,
  Vorhersage-Gewitter am Ziel; Strang 2 „amtliche Warnung" ausgegliedert nach #1318).
