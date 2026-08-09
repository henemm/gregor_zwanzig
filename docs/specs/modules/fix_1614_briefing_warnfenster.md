---
entity_id: fix_1614_briefing_warnfenster
type: bugfix
created: 2026-08-08
updated: 2026-08-08
status: draft
workflow: fix-1614-briefing-warnfenster
---

# Fix #1614: Amtliche Warnungen im Trip-Briefing — Doppelversand-Schutz, GELB-Kontrast, Kanal-Schwelle- und SMS-Kennzeichnungs-Verifikation

## Approval

- [ ] Approved

## Purpose

Vier PO-bestätigte Teilthemen rund um amtliche Warnungen im Trip-Briefing (2026-08-08,
nach Forensik-Korrektur der ursprünglichen Fenster-Theorie — siehe
`docs/context/fix-1614-briefing-warnfenster.md`). **Wichtiger Befund dieser Spec-Phase:**
von den vier Teilen sind nur **Teil 1** (Doppelversand) und **Teil 2** (GELB-Kontrast)
tatsächlich offene Produktivcode-Arbeit. Teil 3 (Kanal-Schwelle) und Teil 4
(„!"-Kennzeichnung) sind **bereits vollständig implementiert** (Issues #1318, #1461
S3a/S3b-2a/S3b-2b, alle live/geschlossen) — belegt per direkter Code-Lesung unten. Diese
Spec führt Teil 3/4 trotzdem mit eigenen ACs, aber als **Regressionsschutz für bereits
bestehendes Verhalten**, nicht als neue Wiring-Arbeit. Siehe „🔴 Kritischer Befund"
weiter unten für die Details und Belegstellen.

1. **Doppelversand (Teil 1, echte Arbeit):** Eine amtliche Warnung, die bereits korrekt
   im Trip-Briefing erscheint, wird bis zu 15 Minuten später vom unabhängigen
   15-Minuten-Alarm-Checker NOCHMAL als eigene, redundante Nachricht verschickt — weil
   der Briefing-Pfad das Melde-Gedächtnis nie beschreibt.
2. **GELB-Kontrast in der E-Mail (Teil 2, echte Arbeit):** `G_ALERT_L2` hat 4,11:1
   Kontrast auf `G_PAPER` — unter der CLAUDE.md-Mindestgrenze WCAG-AA (4,5:1).
3. **Kanal-Schwellen-Verdrahtung (Teil 3, bereits erledigt):** Trip-SMS
   (`trip_report.py:337-357`) und Trip-Telegram (`narrow.py:414-421`) lesen bereits
   `trip.alert_channel_thresholds` und rufen `alert_urgency.min_official_level_for_threshold()`
   auf (#1461 S3b-2a). Der Ortsvergleichs-Bericht hält die Schwelle bewusst konstant auf
   „gering" (#1461 S3b-2b, PO-dokumentiert als „Zwei Wirkungsorte" — Bericht und
   Alarm-Versand sind absichtlich getrennt). Beides zusammen erfüllt bereits exakt das
   im Issue gewünschte Verhalten: GELB erreicht SMS/Telegram, solange der Nutzer die
   Schwelle nicht selbst hochsetzt.
4. **„!"-Kennzeichnung (Teil 4, bereits erledigt):** Trip-SMS setzt bereits ein
   führendes „!" vor den amtlichen Warnblock (`output/tokens/render.py:21-26`, Issue
   #1318). Compare-SMS hat denselben Marker bereits über eine eigene Funktion
   (`comparison.py:835-855`, Issue #1332). Telegram hat bewusst KEIN „!" (Emoji-
   Kennzeichnung stattdessen) — das entspricht bereits der im Issue gewünschten
   Abgrenzung.

## 🔴 Kritischer Befund (Spec-Phase, 2026-08-08) — Teil 3/4 sind kein offener Umfang

Der Auftrag für diese Spec beschrieb Teil 3 als fehlende Verdrahtung im
Trip-Briefing-Scheduler und Teil 4 als „existiert nirgends im Code". Beide Aussagen
stützten sich auf einen `grep` ausschließlich gegen `trip_report_scheduler.py` bzw.
gegen `official_alerts.py`/`sms_trip.py` — nicht gegen die tatsächlichen Renderer, die
der Scheduler über `notification_service.py` aufruft. Direkte Code-Lesung in dieser
Spec-Phase zeigt:

| Behauptung im Auftrag | Tatsächlicher Code-Stand |
|---|---|
| „Trip-Briefing-Scheduler ruft `min_official_level_for_threshold` nirgends auf" | Wahr für `trip_report_scheduler.py` selbst, falsch für den Renderer-Pfad: `trip_report.py:337-342` (SMS) und `narrow.py:414-415` (Telegram) lesen `trip.alert_channel_thresholds` und rufen die Funktion bereits auf — Kommentar dort verweist explizit auf „#1461 S3b-2a". Der Scheduler baut die `TripReport`-Instanz über `notification_service.send_trip_report()`, das intern `TripReportFormatter` (= `trip_report.py`) nutzt; der fehlende Treffer im Scheduler selbst ist deshalb kein Gap. |
| „!"-Kennzeichnung existiert nirgends im Code" | Falsch: `output/tokens/render.py:15-26` (`_fuse()`) setzt bereits `prefix = "!" if warn_marker_pending else ""` für Tokens der Kategorie `official_alert` — Kommentar „Issue #1318: der `!`-Marker leitet den Warn-Block genau einmal ein." Compare hat einen eigenen, aber ebenfalls bereits fertigen Marker: `comparison.py:835-855` (`_official_alert_sms_marker`), verwendet in `_sms_location_part` (`:910-914`), Issue #1332. |
| „Compare-Pendant S3b-2b noch offen" | Falsch: `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md` ist **approved, v1.3, PO-„go" 2026-08-06**, Memory bestätigt „✅ LIVE seit 2026-08-06, #1461 vollständig geschlossen", PR #1543, Prod-Commit `7469126b`. |

**Wie sich Compare vom Trip unterscheidet (bewusst, dokumentiert, kein Fix-Bedarf):**
Compare hält den Berichts-Schwellenwert für SMS/Telegram bewusst konstant auf
`alert_urgency.min_official_level_for_threshold("LOW")` — unabhängig davon, was der
Nutzer als Alarm-Kanal-Schwelle eingestellt hat (`comparison.py:734-740`,
Kommentar: „Kein Compare-Kanal-Schwellenparameter hier: der Bericht bleibt beim
Startwert, unabhängig von einer je Kanal eingestellten Alarm-Schwelle (Spec 'Zwei
Wirkungsorte' — Bericht und Alarm-Versand sind getrennt)."). Der Trip-Bericht liest
dagegen die tatsächlich konfigurierte Schwelle. Diese Asymmetrie ist eine bereits in
`feat_1461_s3b2b_compare_kanal_schwelle.md` (Abschnitt „Zwei Wirkungsorte") getroffene,
PO-genehmigte Architekturentscheidung — **kein Nebenbefund dieser Spec, keine
Trip/Compare-Teilungsverletzung** (der Compare-Bericht ist bewusst permissiver, nicht
weniger fähig). Diese Spec ändert daran nichts.

**Konsequenz für diese Spec:** Teil 3 und Teil 4 werden unten mit eigenen ACs geführt,
aber ausschließlich als **Regressionstests, die den bereits bestehenden, korrekten
Zustand festnageln** — kein neuer Produktivcode. Sollte die Implementierungsphase einen
echten, hier nicht erfassten Gap finden (z.B. einen dritten Aufrufpfad ohne
Schwellen-Verdrahtung), ist das eine Abweichung von dieser Spec und braucht vor der
Umsetzung eine kurze Rückmeldung an den Orchestrator/PO statt stillschweigender
Scope-Erweiterung.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportSchedulerService._send_trip_report_outcome` (Teil 1, nahe
  Zeile 958/1028); `src/output/renderers/email/design_tokens.py` (Teil 2, Zeile 32);
  `src/output/renderers/trip_report.py:337-357` + `src/output/renderers/narrow.py:387-433`
  (Teil 3, bereits implementiert); `src/output/tokens/render.py:15-37` +
  `src/output/renderers/comparison.py:835-914` (Teil 4, bereits implementiert)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.alert_state.AlertStateService` | class | Melde-Gedächtnis (Datei je Nutzer/Trip), Namensraum `official_alert:` überlebt den Briefing-Reset bereits (#1460 P2) — Teil 1 |
| `services.alert_briefing_anchor` | module | Geteilter Baustein (#1467 S2 AG5) für Anker+Reset zwischen Trip und Ortsvergleich; Ort der neuen `record_official_alerts_reported()`-Funktion — Teil 1 |
| `services.trip_alert.TripAlertService._record_official_alert_state` | method | Wird zum Wrapper um die neue geteilte Funktion — Teil 1 |
| `output.renderers.alert.official_alerts.official_alert_state_key` | function | Kanonische Schlüsselbildung fürs Melde-Gedächtnis; MUSS von jeder neuen State-Schreibung verwendet werden — Teil 1 |
| `output.renderers.email.design_tokens.G_ALERT_L2` | constant | Wird auf `#8a6300` angehoben — Teil 2 |
| `services.alert_urgency.min_official_level_for_threshold` | function | Bereits fertig und bereits an allen relevanten Stellen verdrahtet (Trip-SMS, Trip-Telegram, Compare-SMS, Compare-Telegram) — Teil 3, nur Verifikation |
| `output.tokens.render._fuse` | function | Bereits bestehender „!"-Marker-Mechanismus für Trip-SMS — Teil 4, nur Verifikation |
| `output.renderers.comparison._official_alert_sms_marker` | function | Bereits bestehender „!"-Marker für Compare-SMS — Teil 4, nur Verifikation |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/alert_briefing_anchor.py` | MODIFY (neue Funktion) | `record_official_alerts_reported(*, user_id, entity_id, alerts)` — State-Schreib-Body aus `trip_alert.py:1153-1167` übernommen (Teil 1) |
| `src/services/trip_alert.py` (~1153-1167, `_record_official_alert_state`) | MODIFY (Refactor) | Wird dünner Wrapper um die neue geteilte Funktion, Verhalten unverändert (Teil 1) |
| `src/services/trip_report_scheduler.py` (nahe Zeile 958-996, vor dem `write_anchor_and_reset_memory`-Aufruf bei ~1028) | MODIFY | Nach `result = self._notification_service.send_trip_report(request)`, wenn `result.sent and not on_demand`: gesammelte `sw.official_alerts` über die neue Funktion als „gemeldet" vermerken (Teil 1) |
| `src/output/renderers/email/design_tokens.py:32` | MODIFY | `G_ALERT_L2` von `'#9a6f00'` auf `'#8a6300'` (Teil 2) |
| `tests/tdd/test_alert_state_briefing_reset.py` | MODIFY | Erweitert um Doppelversand-Regressionsfälle (Teil 1) |
| Neue/erweiterte Kontrast-Testdatei (Namensregel: nach Verhalten, z.B. `tests/tdd/test_official_alert_color_contrast.py`) | CREATE/MODIFY | Kontrast-Nachweis für `G_ALERT_L2` gegen `G_PAPER`/`G_CARD` (Teil 2) |
| `tests/tdd/test_official_alert_channel_threshold.py` (neu, Regressionsschutz) oder Erweiterung einer Nachbardatei | CREATE | Pin des bereits bestehenden Schwellen-Verhaltens Trip-SMS/Telegram + Compare-SMS/Telegram (Teil 3, **kein Produktivcode**) |
| `tests/tdd/test_official_alert_sms_marker.py` (neu, Regressionsschutz) oder Erweiterung einer Nachbardatei | CREATE | Pin des bereits bestehenden „!"-Markers Trip-SMS + Compare-SMS, Nicht-Ziel-Nachweis Telegram (Teil 4, **kein Produktivcode**) |

**Kein Compare-Pendant für Teil 1:** `comparison_engine.py:302-303` übergibt kein
Zeitfenster an `get_official_alerts_with_status` — hat das Doppelversand-Problem
strukturell nicht (in der Analyse-Phase bereits geprüft und ausgeschlossen).

### Estimated Changes

- Files: 4 Produktivdateien (Teil 1: 3, Teil 2: 1), 4 Testdateien (2 neu/erweitert je
  Teil 1/2, 2 neu als reiner Regressionsschutz für Teil 3/4)
- LoC: +45/-10 Produktivcode (Teil 1) + 1 Zeile (Teil 2) = ~+46/-10 Produktivcode
  gesamt; +250/-0 Tests (deutlich mehr Tests als Produktivcode, weil Teil 3/4
  ausschließlich aus Regressionstests ohne begleitende Produktivänderung bestehen)

## Implementation Details

### Teil 1 — Doppelversand-Schutz

Neue Funktion in `src/services/alert_briefing_anchor.py` (Vorbild `reset_alert_memory()`
in derselben Datei):

```python
def record_official_alerts_reported(
    *, user_id: str, entity_id: str, alerts: list,
) -> None:
    """Vermerkt amtliche Warnungen als 'im Briefing gemeldet' — DIE geteilte
    Schreib-Logik fürs Melde-Gedächtnis (official_alert:-Namensraum)."""
```

Übernimmt den State-Schreib-Body aus `trip_alert.py:1153-1167`
(`_record_official_alert_state`): `AlertStateService(user_id=...).load(entity_id)`, je
Alert `official_alert_state_key(a)` als Schlüssel mit
`{"last_reported_value": float(a.level), "reported_at": now_iso}` setzen,
`state_svc.save(entity_id, state)`. Fail-soft bei leerer `alerts`-Liste (No-Op).

`TripAlertService._record_official_alert_state()` wird zum Wrapper, der an
`record_official_alerts_reported()` delegiert (`alerts=[a for a, _seg_ids in
official_notices]`) — Verhalten unverändert, siehe Test 6/AC-5.

Im Scheduler wird nach `result = self._notification_service.send_trip_report(request)`
(Zeile ~958) und VOR dem bestehenden `write_anchor_and_reset_memory`-Aufruf (Zeile
~1028) folgende Bedingung ergänzt:

```python
if result.sent and not on_demand:
    all_official_alerts = [a for sw in segment_weather for a in (sw.official_alerts or [])]
    if all_official_alerts:
        from services.alert_briefing_anchor import record_official_alerts_reported
        record_official_alerts_reported(
            user_id=self._user_id, entity_id=trip.id, alerts=all_official_alerts,
        )
```

Reihenfolge bewusst VOR `write_anchor_and_reset_memory`, damit ein Exception-Pfad dort
das Record nicht verschluckt. `on_demand`-Gate ist zwingend — Ad-hoc-Abruf (#1007)
bleibt read-only gegenüber dem Melde-Gedächtnis. `result.sent` ist zwingend, damit ein
fehlgeschlagener oder kanalloser Versand keine Warnung fälschlich als „gemeldet"
markiert (sonst würde eine Warnung, die NIE zugestellt wurde, trotzdem vom
Alarm-Checker unterdrückt).

### Teil 2 — GELB-Kontrast

`design_tokens.py:32`: `G_ALERT_L2` von `'#9a6f00'` (4,11:1 auf `G_PAPER`) auf
`'#8a6300'` ändern. Nachgerechnet in dieser Spec-Phase (WCAG-2.1-relative-Luminanz):

- gegen `G_PAPER` (`#f6f4ee`): **4,94:1** (≥ 4,5:1 ✅)
- gegen `G_CARD` (`#ffffff`): **5,43:1** (≥ 4,5:1 ✅)
- gegen den Compare-Badge-Hintergrund `compare_html.py:107` (`#f2e4b0`): **~4,27:1**
  (< 4,5:1 ❌ — siehe „Known Limitations", nicht Teil dieses Fixes)

Reiner Token-Wert-Wechsel, keine Konsumenten-Logik ändert sich — alle Verwender
(`official_alerts.py:1330,1335,1408,207,1222`) beziehen den Wert bereits zentral aus
`design_tokens.py`.

### Teil 3 — Kanal-Schwellen-Verdrahtung (bereits implementiert, nur verifizieren)

**Kein Produktivcode-Änderung.** Bereits vorhanden:

- Trip-SMS: `trip_report.py:337-342` liest `trip.alert_channel_thresholds.get("sms")`,
  ruft `alert_urgency.min_official_level_for_threshold(_sms_threshold or "LOW")` auf,
  übergibt das Ergebnis als `sms_alert_min_level` an `SMSTripFormatter.format_sms()`
  (`:357`).
- Trip-Telegram: `narrow.py:414-415` (`_official_alert_bubble`) liest
  `trip.alert_channel_thresholds.get("telegram")`, ruft dieselbe Funktion auf, filtert
  Segmente danach (`:417-422`).
- Compare-SMS/Telegram: `comparison.py:740` und `:912` rufen
  `alert_urgency.min_official_level_for_threshold("LOW")` — bewusst konstant „gering",
  siehe „🔴 Kritischer Befund" oben.

Diese Spec verlangt für Teil 3 ausschließlich neue Regressionstests, die dieses bereits
korrekte Verhalten aus Nutzersicht (erzeugte SMS-/Telegram-Texte, nicht interne
Funktionsaufrufe) festnageln.

### Teil 4 — „!"-Kennzeichnung (bereits implementiert, nur verifizieren)

**Kein Produktivcode-Änderung.** Bereits vorhanden:

- Trip-SMS: `output/tokens/render.py:15-26` (`_fuse()`) — für den ersten Token der
  Kategorie `official_alert` in der TokenLine wird `"!"` vorangestellt
  (`warn_marker_pending`-Flag, genau einmal pro Warnblock, Issue #1318).
- Compare-SMS: `comparison.py:835-855` (`_official_alert_sms_marker`), verwendet in
  `_sms_location_part()` (`:910-914`), Issue #1332.
- Telegram (Trip UND Compare): bewusst KEIN „!" — beide nutzen stattdessen die
  bestehende Emoji-Kennzeichnung pro Warnstufe
  (`render_official_alert_telegram`/`_LEVEL_WORDS` in `official_alerts.py`); die
  Compare-Telegram-Fassung hatte laut Code-Kommentar (`comparison.py:723-725`) sogar
  explizit einen früheren „!"-Marker per PO-Korrektur 2026-07-23 wieder entfernt
  bekommen, um Redundanz mit dem Emoji zu vermeiden — diese Spec bestätigt diesen
  Zustand als gewollt, ändert nichts daran.

Diese Spec verlangt für Teil 4 ausschließlich neue Regressionstests, die den
bestehenden Marker (Position, genau einmal pro Block) und die Telegram-Abwesenheit aus
Nutzersicht (erzeugter Text) festnageln.

## Test Plan

### Test-Schicht

Kern-Schicht (deterministisch): kein Netz, keine Live-Dienste. `AlertStateService`,
`design_tokens`-Werte und die Renderer-Funktionen sind reine Dateizugriffe/reine
Funktionen. Kein Mock-Theater, kein Dateiinhalt-Check als alleiniger
Verhaltensnachweis (Ausnahme: Teil-2-Kontrasttest rechnet direkt gegen die
Hex-Konstanten, das ist reine Mathematik, kein String-Match-Ersatz für Verhalten).
Testdatei-Namensregel: nach Verhalten benennen (`test_naming_gate.py` blockt
`test_issue_1614_*.py`).

### Renderer-Commit-Gate #811

`design_tokens.py` gehört zu den Mail-Inhalts-Dateien des Gates — vor Commit müssen
`uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün UND ein erfolgreicher
`uv run python3 .claude/hooks/briefing_mail_validator.py`-Lauf vorliegen. Teil 3/4
berühren `sms_trip.py`/`official_alerts.py`/`comparison.py` nur, falls die
Regressionstests dort neue Test-Imports/Fixtures brauchen, die selbst Produktivdateien
NICHT verändern — der Gate-Trigger ist Staging der Datei, nicht des Diffs; im Zweifel
Gate-Lauf einplanen.

### Automated Tests (TDD RED)

- [ ] **Test 1** (`test_alert_state_briefing_reset.py`, Teil 1): GIVEN ein
  Trip-Briefing wurde erfolgreich mit einer amtlichen Warnung X versendet (echter
  `_send_trip_report_outcome()`-Aufrufpfad), WHEN danach
  `TripAlertService.check_official_alert_triggers()` für denselben Trip mit
  unveränderter Warnung X (gleiches Level) läuft, THEN liefert der Checker X NICHT als
  neu/eskaliert zurück (kein Doppelversand — heutiges Verhalten: X wird erneut
  gemeldet).

- [ ] **Test 2** (Eskalations-Gegenprobe, Teil 1): GIVEN dasselbe Vorbriefing wie Test
  1, WHEN die Warnung X danach auf ein höheres Level eskaliert, THEN meldet
  `check_official_alert_triggers()` die eskalierte Warnung weiterhin.

- [ ] **Test 3** (Ad-hoc-Ausnahme, Teil 1): GIVEN ein On-Demand-Abruf
  (`on_demand=True`, #1007) liefert dieselbe amtliche Warnung, WHEN der Abruf
  abgeschlossen ist, THEN bleibt das Melde-Gedächtnis unverändert.

- [ ] **Test 4** (Fehlgeschlagener Versand, Teil 1, neuer Fall gegenüber dem
  Vorgänger-Entwurf): GIVEN `result.sent` ist `False` (z.B. kein Kanal erreichbar),
  WHEN `_send_trip_report_outcome()` durchläuft, THEN wird die neue Record-Funktion
  NICHT aufgerufen — eine nie zugestellte Warnung darf den Alarm-Checker nicht stumm
  schalten.

- [ ] **Test 5** (Wrapper-Regression, Teil 1): GIVEN dieselben Eingaben (`trip_id`,
  `official_notices`) wie vor dem Refactor, WHEN
  `TripAlertService._record_official_alert_state()` nach dem Umbau zum Wrapper
  aufgerufen wird, THEN entsteht exakt derselbe State-Eintrag wie vorher.

- [ ] **Test 6** (Kaltstart, Teil 1): GIVEN ein Trip ohne jeden vorherigen
  `official_alert:`-State-Eintrag, WHEN das Briefing mit einer amtlichen Warnung
  versendet wird, THEN läuft `record_official_alerts_reported()` fehlerfrei durch.

- [ ] **Test 7** (Mandantentrennung, CLAUDE.md-Pflicht, Teil 1): GIVEN zwei
  verschiedene `user_id`s mit je einem Trip und je einer identischen amtlichen
  Warnung, WHEN für Nutzer A das Briefing versendet wird, THEN bleibt das
  Melde-Gedächtnis von Nutzer B unverändert.

- [ ] **Test 8** (Kontrast, Teil 2): GIVEN der neue `G_ALERT_L2`-Wert `#8a6300`, WHEN
  der Kontrast gegen `G_PAPER` (`#f6f4ee`) und `G_CARD` (`#ffffff`) berechnet wird
  (echte WCAG-2.1-Formel, kein String-Vergleich), THEN liegt beides bei ≥ 4,5:1.

- [ ] **Test 9** (Renderer-Durchgriff, Teil 2): GIVEN eine amtliche Warnung Stufe 2
  (GELB) wird gerendert (E-Mail-HTML), WHEN der Renderer läuft, THEN enthält die
  erzeugte Ausgabe den neuen Hex-Wert `#8a6300` statt des alten `#9a6f00` — belegt,
  dass der Token-Wechsel tatsächlich bis zur Ausgabe durchschlägt (nicht nur die
  Konstante geändert wurde).

- [ ] **Test 10** (Regressionsschutz Trip-SMS-Schwelle, Teil 3, bereits bestehendes
  Verhalten): GIVEN ein Trip hat für den SMS-Kanal keine eigene Schwelle gesetzt
  (Startwert „gering"), WHEN die Trip-SMS für eine amtliche Warnung Stufe 2 (GELB)
  erzeugt wird, THEN enthält der SMS-Text die Warnung.

- [ ] **Test 11** (Regressionsschutz Trip-SMS-Schwelle hochgesetzt, Teil 3): GIVEN
  derselbe Trip hat für den SMS-Kanal die Schwelle explizit auf „hoch" gesetzt, WHEN
  dieselbe GELB-Warnung gerendert wird, THEN fehlt sie im SMS-Text.

- [ ] **Test 12** (Regressionsschutz Trip-Telegram-Schwelle, Teil 3, analog Test
  10/11 für den Telegram-Kanal): GIVEN Trip-Telegram-Schwelle „gering" bzw. „hoch",
  WHEN die Telegram-Bubble für dieselbe GELB-Warnung gerendert wird, THEN erscheint
  sie im ersten Fall und fehlt im zweiten.

- [ ] **Test 13** (Regressionsschutz Compare-Bericht, Teil 3): GIVEN ein
  Ortsvergleich hat für einen Kanal eine erhöhte Alarm-Kanal-Schwelle gesetzt, WHEN
  der reguläre Kurznachrichten-Bericht (SMS und Telegram) für eine GELB-Warnung
  erzeugt wird, THEN erscheint die Warnung trotzdem (Bericht bleibt bewusst
  unabhängig von der Alarm-Schwelle, „Zwei Wirkungsorte").

- [ ] **Test 14** (Regressionsschutz „!"-Marker Trip-SMS, Teil 4): GIVEN eine
  amtliche Warnung erreicht den SMS-Kanal, WHEN die Trip-SMS-Kurzform erzeugt wird,
  THEN steht genau ein führendes „!" unmittelbar vor dem ersten Token des amtlichen
  Warnblocks, kein weiteres „!" vor folgenden Tokens desselben Blocks.

- [ ] **Test 15** (Regressionsschutz „!"-Marker Compare-SMS, Teil 4): GIVEN dieselbe
  Ausgangslage für einen Ortsvergleichs-Ort, WHEN die Compare-SMS-Kurzform erzeugt
  wird, THEN trägt der Ortsblock denselben „!"-Marker.

- [ ] **Test 16** (Nicht-Ziel-Nachweis Telegram, Teil 4): GIVEN dieselbe amtliche
  Warnung erreicht Trip-Telegram bzw. Compare-Telegram, WHEN die jeweilige Bubble
  gerendert wird, THEN enthält der Text KEIN „!"-Präfix vor der Warnung (stattdessen
  die bestehende Emoji-Kennzeichnung).

## Acceptance Criteria

- **AC-1:** Given dieselbe Warnung wurde bereits erfolgreich im Trip-Briefing gemeldet (Melde-Gedächtnis geschrieben), When der unabhängige 15-Minuten-Alarm-Checker danach mit unverändertem Level läuft, Then meldet der Checker diese Warnung NICHT erneut als separate Nachricht.
  - Test: Test 1 — Kern-Regressionsschutz gegen den forensisch belegten Doppelversand (Mail-Paar `86918bc7`/`7d0bbfd6`).

- **AC-2:** Given dieselbe Ausgangslage wie AC-1, When die Warnung nach dem Briefing tatsächlich auf ein höheres Level eskaliert, Then meldet der Alarm-Checker die eskalierte Warnung weiterhin als neuen Trigger.
  - Test: Test 2 — verhindert stille Unterdrückung echter Verschärfung durch den neuen Doppelversand-Schutz.

- **AC-3:** Given ein Ad-hoc-/On-Demand-Abruf (`on_demand=True`, #1007) liefert dieselbe amtliche Warnung, When der Abruf abgeschlossen ist, Then bleibt das Melde-Gedächtnis unverändert — kein neuer Eintrag im `official_alert:`-Namensraum.
  - Test: Test 3 — bestehende Read-only-Garantie darf durch die neue Schreiblogik nicht verletzt werden.

- **AC-4:** Given der Versand eines Trip-Briefings ist fehlgeschlagen oder kein Kanal war erreichbar (`result.sent` ist falsch), When `_send_trip_report_outcome()` durchläuft, Then wird keine Warnung als „gemeldet" vermerkt — eine nie zugestellte Warnung bleibt für den Alarm-Checker weiterhin meldepflichtig.
  - Test: Test 4 — verhindert einen neuen, subtileren Bug (stumme Warnung nach fehlgeschlagenem Versand).

- **AC-5:** Given identische Eingaben vor und nach dem Wrapper-Refactor von `_record_official_alert_state`, When die Methode aufgerufen wird, Then entsteht in beiden Fällen exakt derselbe State-Eintrag (gleicher Schlüssel, gleiches Level, Zeitstempel-Feld vorhanden).
  - Test: Test 5 — verhindert Verhaltensänderung durch das Refactoring selbst.

- **AC-6:** Given ein Trip ohne jeden vorherigen `official_alert:`-Eintrag (Kaltstart, erstes Briefing), When das Briefing mit einer amtlichen Warnung erfolgreich versendet wird, Then läuft die neue Record-Funktion fehlerfrei durch und legt einen gültigen Eintrag an.
  - Test: Test 6 — verhindert Absturz bei Bestandsnutzern ohne Historie.

- **AC-7:** Given zwei verschiedene Nutzer mit je einem Trip und je einer identischen amtlichen Warnung, When für Nutzer A das Briefing versendet wird, Then bleibt das Melde-Gedächtnis von Nutzer B davon unberührt.
  - Test: Test 7 — Mandantentrennung, CLAUDE.md-Pflicht bei jedem nutzerbezogenen Datenpfad.

- **AC-8:** Given der neue Farbwert `#8a6300` für `G_ALERT_L2`, When der Kontrast gegen die Hintergründe `G_PAPER` (`#f6f4ee`) und `G_CARD` (`#ffffff`) nach WCAG-2.1 berechnet wird, Then liegt beides bei mindestens 4,5:1 (WCAG-AA).
  - Test: Test 8 — direkte Umsetzung der CLAUDE.md-Kontrastregel.

- **AC-9:** Given eine amtliche Warnung der Stufe 2 (GELB) wird als E-Mail-HTML gerendert, When die Ausgabe erzeugt wird, Then enthält sie den neuen Farbwert `#8a6300`, nicht mehr den alten `#9a6f00`.
  - Test: Test 9 — Nachweis, dass der Token-Wechsel bis zur tatsächlichen Ausgabe durchschlägt.

- **AC-10:** Given ein Trip hat für den SMS-Kanal keine eigene Schwelle gesetzt (Startwert „gering"), When eine amtliche Warnung der Stufe 2 (GELB) im Trip-SMS-Text erzeugt wird, Then erscheint sie dort — bereits bestehendes Verhalten seit #1461 S3b-2a, hier als Regressionsschutz gepinnt.
  - Test: Test 10.

- **AC-11:** Given derselbe Trip hat die SMS-Kanal-Schwelle explizit auf „hoch" gesetzt, When dieselbe GELB-Warnung gerendert wird, Then fehlt sie im SMS-Text.
  - Test: Test 11 — Gegenprobe zu AC-10, verhindert Regress auf „immer alles anzeigen".

- **AC-12:** Given ein Trip hat für den Telegram-Kanal keine eigene Schwelle bzw. eine hochgesetzte Schwelle, When die Telegram-Bubble für eine GELB-Warnung gerendert wird, Then verhält sie sich analog AC-10/AC-11 für den Telegram-Kanal.
  - Test: Test 12.

- **AC-13:** Given ein Ortsvergleich hat für einen Kanal eine erhöhte Alarm-Kanal-Schwelle gesetzt, When der reguläre Kurznachrichten-Bericht (SMS und Telegram) für eine GELB-Warnung erzeugt wird, Then erscheint die Warnung trotzdem — der Bericht bleibt bewusst unabhängig von der Alarm-Schwelle (dokumentierte PO-Entscheidung „Zwei Wirkungsorte", #1461 S3b-2b).
  - Test: Test 13 — pin des bewusst abweichenden Compare-Verhaltens gegenüber Trip.

- **AC-14:** Given eine amtliche Warnung erreicht den SMS-Kanal (Trip oder Ortsvergleich), When die jeweilige SMS-Kurzform erzeugt wird, Then steht genau ein führendes „!" unmittelbar vor dem ersten Token des amtlichen Warnblocks, kein zusätzliches „!" vor folgenden Tokens desselben Blocks.
  - Test: Test 14/15 — bereits bestehendes Verhalten (#1318 Trip, #1332 Compare), hier als Regressionsschutz gepinnt.

- **AC-15:** Given dieselbe amtliche Warnung erreicht Trip-Telegram oder Compare-Telegram, When die jeweilige Bubble gerendert wird, Then enthält der Text KEIN „!"-Präfix — Telegram nutzt stattdessen ausschließlich die bestehende Emoji-Kennzeichnung.
  - Test: Test 16 — explizite Nicht-Ziel-Absicherung, verhindert versehentliche Telegram-Änderung in der Implementierungsphase.

## Known Limitations

- **Compare-Badge-Kontrast bleibt unter 4,5:1.** Der neue `G_ALERT_L2`-Wert (`#8a6300`)
  erreicht auf dem Compare-Badge-Hintergrund `compare_html.py:107` (`#f2e4b0`) nur
  **~4,27:1** (in dieser Spec-Phase nachgerechnet) — unter der WCAG-AA-Grenze. Der
  Auftrag für diese Spec begrenzt Teil 2 explizit auf `design_tokens.py`; eine Behebung
  des Compare-Badge-Kontrasts bräuchte einen eigenen Hintergrund-Ton oder eine eigene
  Farbe für diese eine Kombination und ist eigene Arbeit, kein Teil dieses Fixes.
- **Teil 3/4 sind Regressionstests ohne Produktivcode.** Sollte eine spätere Prüfung
  (Adversary, manuelle Staging-Verifikation) einen ECHTEN, hier nicht erfassten Gap
  finden — z.B. einen dritten Aufrufpfad, der die Schwelle nicht liest — ist das eine
  Abweichung von dieser Spec, kein stiller Nacharbeits-Auftrag; vor Erweiterung des
  Umfangs ist eine kurze Rückmeldung fällig.
- **Compare-Bericht bleibt bewusst unabhängig von der Alarm-Kanal-Schwelle.** Das ist
  eine bereits getroffene, dokumentierte PO-Entscheidung (`feat_1461_s3b2b_compare_
  kanal_schwelle.md`, Abschnitt „Zwei Wirkungsorte") — keine Inkonsistenz, die diese
  Spec beheben soll.
- **Kein Compare-Pendant für Teil 1.** `comparison_engine.py` hat das
  Doppelversand-Problem strukturell nicht (kein Zeitfenster-Parameter an der
  betroffenen Stelle).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Teil 1 ist ein chirurgischer Bugfix innerhalb bestehender, bereits
  dokumentierter Architektur (#1460 P2 Zwei-Namensräume-Melde-Gedächtnis, #1467 S2 AG5
  geteilter Baustein-Ansatz). Teil 2 ist ein reiner Token-Wert-Wechsel. Teil 3/4
  ändern per Befund dieser Spec-Phase keinen Produktivcode, sondern pinnen bereits
  über ADR-0046 (Alarm-Kanal-Schwelle) und die #1318/#1332-Historie abgedecktes
  Verhalten fest — keine neue Grundsatzentscheidung, kein neues ADR.

## Changelog

- 2026-08-08: Initial spec created (Fenster-Theorie, inzwischen widerlegt).
- 2026-08-08: Vollständige Neufassung (v2) nach PO-bestätigtem Vier-Teile-Zuschnitt und
  direkter Code-Verifikation in der Spec-Phase. Fenster-Theorie entfernt (Doppelversand
  statt fehlender Warnung, Resend-Forensik-Beleg). Kritischer Befund ergänzt: Teil 3
  (Kanal-Schwelle) und Teil 4 („!"-Kennzeichnung) sind bereits vollständig implementiert
  (#1318, #1461 S3a/S3b-2a/S3b-2b) — beide werden nur noch mit Regressionstests geführt,
  kein neuer Produktivcode. Neuer Kontrast-Nachrechnung für Teil 2 inkl. Known-Limitation
  zum Compare-Badge-Hintergrund.
