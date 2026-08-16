---
entity_id: fix_1861_1865_alarm_mail_klarheit
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: draft
workflow: fix-1861-1865-alarm-mail-klarheit
---

# Abweichungs-Alarm-Mail: unterscheidbare Mehrfach-Ereignisse + verständlicher Datenblock-Text

## Approval

- [x] Approved

## Purpose

Zwei PO-Bug-Reports (2026-08-15) zur Abweichungs-Alarm-Mail (`deviation-alert`):
**#1861** — bei mehreren Ereignissen DERSELBEN Metrik (z. B. drei Gewitter-Treffer für
unterschiedliche Etappen/Zeitfenster) sind die Datenblock-Zeilen in `render_email()`s
Multi-Event-Zweig ununterscheidbar ("Gewitter · Schwelle 1" dreimal identisch), obwohl
`AlertEvent` bereits `segment_id`/`occurred_at` je Ereignis trägt. **#1865** — die
Einzel-Event-Datenblock-Zeile "Alarm-Schwelle 1" / "Änderung über ✗" ist ein
unverständliches Textfragment statt eines vollständigen Satzes. Beide Bugs sitzen in
derselben Quelldatei und derselben fachlichen Fläche (Alarm-Mail-Datenblock) — ein
Slice, ein Commit.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `render_email` (Multi-Event-Zweig, #1861), `render_telegram`
  (Multi-Event-Zweig, #1861, Kanalkonsistenz), `_datablock_single` (#1865), neu:
  `_where_when`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.alert.model.AlertEvent` (`segment_id`, `km_from`/`km_to`, `occurred_at`) | Datenmodell | Bereits vorhandene Differenzierungs-Felder für #1861 — keine Modelländerung nötig |
| `output.renderers.alert.model.over_thr` / `side_label` | Funktion | #958-Kernsemantik — bleibt UNVERÄNDERT, nur der Text um ihre Rückgabewerte ändert sich (#1865) |
| `output.renderers.alert.render._location_of` / `output.renderers.alert.segments.format_alert_location` | Funktion | Bestehende Ortssprache (Issue #1744) — Basis für den neuen `_where_when()`-Helper, wird NICHT verändert |
| `tests/tdd/test_alert_bundle_958ff.py` (AC-2) | Test | Fixiert aktuell exakt den zu ändernden #1865-Wortlaut — muss mitgezogen werden |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` (Zeile ~747-766) | Test | Fixiert denselben Wortlaut für den Compare-Alarm-Pfad — muss mitgezogen werden |
| `tests/tdd/test_issue_1170_compare_alert_config.py` (AC-7) | Test | Regressionsschutz: Compare-Bündel-Pfad (kein `segment_id`) darf durch den #1861-Differenzierer NICHT verändert werden — bleibt unverändert grün |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/render.py` | MODIFY | Neuer Helper `_where_when(e)` (Segment-/km-Referenz + Uhrzeit, extrahiert aus der bestehenden "Wo & wann"-Logik in `_datablock_single`); Einsatz im Multi-Event-Zweig von `render_email` (Zeile ~504-519) UND `render_telegram` (Zeile ~592-601), NUR wenn `e.segment_id` gesetzt ist (Trip-Pfad); Wortlaut-Fix in `_datablock_single` Zeile 388-391 (#1865) — `over_thr()`/`side_label()`-Aufrufe unverändert, nur der gebaute Satz ändert sich |
| `tests/tdd/test_alert_bundle_958ff.py` | MODIFY | AC-2 (Zeile ~127-150): neuer Wortlaut statt `"Änderung über ✗"`, Docstring/Assertion-Text angepasst |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` | MODIFY | Zeile ~747-766: identischer String-Block für den Compare-Einzel-Event-Pfad nachgezogen |
| `tests/tdd/test_alert_multi_event_where_when.py` | CREATE | Neue Tests für #1861 (Differenzierung Multi-Event-E-Mail + Telegram bei gleicher Metrik) — Namensregel: nach Verhalten benannt, nicht nach Issue-Nummer |
| `tests/tdd/test_issue_1170_compare_alert_config.py` | MODIFY | Nachtrag 2026-08-16 (Adversary F002): EINE zusätzliche Assertion in `test_ac7_single_location_two_metrics_no_per_row_location_prefix` (`"km 0" not in plain`), die die #1861-Abgrenzung zum Compare-Bündelpfad tatsächlich bewacht — Zusicherung verschärft, nicht gelockert |

**Grep-Nachweis (vollständige Erfassung, Kontext-Dokument-Auflage):** `grep -rn "Änderung über\|Änderung unter" tests/` liefert 6 Treffer in 6 Dateien; geprüft wurden alle. `test_change_detection.py`, `test_official_alert_channel_threshold.py`, `test_issue_1004_startzeit_ssot.py`, `test_bug_alert_ignores_weather_tab_disable.py` nutzen den String "Alarm-Schwelle" nur als allgemeinen Begriff (Docstrings/Kommentare, Kaskaden-/Persistenz-/Sichtbarkeits-Tests) — sie prüfen NICHT den gerenderten Zeilentext und sind von diesem Fix nicht betroffen. Nur `test_alert_bundle_958ff.py` und `test_issue_1169_compare_alert_consumer.py` fixieren den tatsächlich gerenderten String.

### Estimated Changes
- Files: 4 (1 modifiziert im Renderer, 2 modifizierte Testdateien, 1 neue Testdatei)
- LoC: ca. +40/-15 in `render.py` (Helper-Extraktion, zwei Einsatzstellen, Wortlaut-Fix); Test-LoC zusätzlich, zählt gegen das separate 500er-Test-Budget (CLAUDE.md, Workflow-Tools v3), nicht gegen die 250 Prod-LoC

## Implementation Details

**1. `#1865` — vollständiger Satz statt Fragment (`_datablock_single`, Zeile 388-391):**
`over_thr()`/`side_label()` bleiben BYTE-IDENTISCH in ihrer Logik. Nur der gebaute Satz
ändert sich, z. B. über eine lokale Zuordnung `{"über": "darüber", "unter": "darunter"}`,
angewendet auf den (unveränderten) Rückgabewert von `side_label(e)`:
```
mark = "✓" if not over_thr(e) else "✗"
row2 = (f"Alarm-Schwelle {_val(e, e.threshold)}", f"jetzt {ADVERB[side_label(e)]} {mark}")
```
Ergebnis (Plain, Label:Wert): `"Alarm-Schwelle 10,0 mm: jetzt darüber ✗"` /
`"... jetzt darunter ✓"` — orientiert an der Design-Vorlage
(`docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html`,
Gut-Fall `"jetzt darunter ✓"`), symmetrisch auf den Schlecht-Fall übertragen. Der exakte
Wortlaut ist Teil der ACs unten und wird dem PO wörtlich vorgelegt.

**2. `#1861` — Differenzierer im Multi-Event-Zweig, neuer Helper `_where_when`:**
Extrahiert aus der bestehenden Zeile-3-Logik von `_datablock_single`
(`_location_of((e,), location_label) + " · " + occurred_at`), OHNE `location_label`-
Parameter (der wird im Multi-Zweig nicht gebraucht, s. Punkt 3):
```
def _where_when(e: AlertEvent) -> str:
    when = _location_of((e,), None)
    if e.occurred_at:
        when += f" · {e.occurred_at}"
    return when
```
`_datablock_single` Zeile 396-398 wird auf diesen Helper umgestellt (mit dem bisherigen
`location_label`-Argument weiterhin durchgereicht — dafür bleibt der Helper-Aufruf dort
`_location_of((e,), location_label)` direkt, NICHT über `_where_when`, da `_where_when`
bewusst ohne `location_label`-Parameter gebaut ist, s. u.). Byte-identisches Verhalten
für den Single-Event-Pfad ist Regressionsvoraussetzung (AC-4).

Im Multi-Event-Zweig von `render_email` und `render_telegram` wird der Zusatz **nur
ergänzt, wenn `e.segment_id` gesetzt ist** (Trip-Pfad, Issue #1744). Begründung: der
Compare-Bündelpfad (`to_multi_point_alert_message`) setzt `segment_id` NIE und `km_from`/
`km_to` konstant auf `0.0` (project.py Zeile ~220) — ein ungefilterter Einsatz von
`_where_when()` würde dort sinnlose Zusätze wie `"km 0–0"` in jede Zeile schreiben und
die #1170-Regressions-Invariante (AC-7, `test_issue_1170_compare_alert_config.py`)
gefährden. Die Bedingung `e.segment_id is not None` trifft exakt den PO-Bug-Report-Fall
(Trip-Pfad, KHW Segment 4-6) und lässt den Compare-Pfad unangetastet.

`render_email` (über-Schwelle-Zeile, analog unter-Schwelle):
```
where_when = f" · {_where_when(e)}" if e.segment_id else ""
label = f"{loc_prefix}{_label(e)}{where_when} · Schwelle {_num(e, e.threshold)}{threshold_suffix}"
```
`render_telegram` (Kanalkonsistenz, Issue #978-Präzedenz):
```
where_when = f" {_where_when(e)}" if e.segment_id else ""
# in der metric_line-Zusammenstellung je Event ergänzt
```

**Betreff (`render_subject`) ist NICHT Teil dieser Scheibe** — siehe Known Limitations.

## Expected Behavior

- **Input:** `AlertMessage` mit ≥2 `AlertEvent`s derselben `metric_id`, `segment_id`
  gesetzt (Trip-Pfad), unterschiedlichen `segment_id`- und/oder `occurred_at`-Werten.
- **Output:** `render_email()`/`render_telegram()` liefern für jedes Event eine
  eigenständige, vom PO lesbare Zeile mit Segment-/Zeit-Bezug statt identischer Zeilen;
  `_datablock_single()`s "Alarm-Schwelle"-Zeile ist ein vollständiger Satz.
- **Side effects:** keine — reines Text-Templating, kein Zustand, kein I/O.

## Acceptance Criteria

- **AC-1:** Given eine `deviation-alert`-E-Mail mit drei `AlertEvent`s derselben Metrik
  (`metric_id="thunder"`), `segment_id` gesetzt auf `"4"`, `"5"`, `"6"` (Trip-Pfad,
  Reproduktion des PO-Bug-Reports "3x Gewitter Segment 4-6") / When `render_email()` den
  Multi-Event-Datenblock rendert / Then sind die drei resultierenden Zeilen paarweise
  UNTERSCHIEDLICHE Strings UND jede Zeile enthält den Segment-Bezug ihres jeweiligen
  Events (z. B. "Segment 4"/"Segment 5"/"Segment 6").
  - Test: `tests/tdd/test_alert_multi_event_where_when.py` — `AlertMessage` mit den drei
    o. g. Events bauen, `render_email()` aufrufen, Plain-Text-Zeilen extrahieren und
    paarweise auf Ungleichheit prüfen (kein reiner Dateiinhalt-Check der Quelle, sondern
    der tatsächlich gerenderten Ausgabe). Zweite Sub-Prüfung: zwei Events mit
    IDENTISCHEM `segment_id`, aber unterschiedlichem `occurred_at` — auch hier müssen die
    Zeilen sich unterscheiden (Uhrzeit als Differenzierer bei gleicher Etappe).

- **AC-2:** Given dieselbe Fixture wie AC-1 / When `render_telegram()` die Multi-Event-
  Metrik-Zeile rendert / Then enthält die Zeile für jedes Event denselben Segment-/Zeit-
  Bezug wie in der E-Mail (Kanalkonsistenz, Issue #978-Präzedenz) UND die drei
  Teilangaben sind paarweise unterscheidbar.
  - Test: `tests/tdd/test_alert_multi_event_where_when.py` — gleiche Fixture,
    `render_telegram()` aufrufen, `metric_line` auf die drei Segment-Referenzen prüfen.

- **AC-3:** Given ein einzelnes `AlertEvent` (Bug-Report-Werte aus #958/#1865,
  `threshold=400.0`, `value_from=2855.0`, `value_to=3285.0`, `cmp="unter"`) / When
  `render_email()` den Einzel-Event-Datenblock rendert / Then zeigt die "Alarm-Schwelle"-
  Zeile den vollständigen, verständlichen Text `"jetzt darüber ✗"` statt des Fragments
  `"Änderung über ✗"` — sowohl in html als auch in plain.
  - Test: `tests/tdd/test_alert_bundle_958ff.py::test_ac2_render_email_change_wording_and_datablock`
    (angepasst) — Assertion auf den neuen Wortlaut in beiden Repräsentationen; ergänzend
    `tests/tdd/test_issue_1169_compare_alert_consumer.py` (Compare-Einzel-Event-Pfad,
    Zeile ~747-766) auf denselben neuen Wortlaut nachgezogen — diese Datei läuft NUR mit
    `-m "email"` (Marker, s. AC-6), sonst wird sie still deselektiert.

- **AC-4 (Regressionsschutz #958):** Given dieselben Events wie im bestehenden
  `over_thr()`-Test (steigende UND fallende Richtung, gleicher Betrag) / When
  `over_thr()`/`side_label()` unverändert aufgerufen werden / Then liefern beide exakt
  dieselben Rückgabewerte wie vor diesem Fix — die #1865-Textänderung darf NUR die
  Formulierung um diese Werte herum betreffen, nicht ihre Berechnung.
  - Test: bestehender Test in `test_alert_bundle_958ff.py` (Δ-Semantik, steigend/fallend)
    bleibt UNVERÄNDERT und grün; zusätzlich neue Assertion in
    `tests/tdd/test_alert_multi_event_where_when.py`, dass `over_thr()`/`side_label()`
    für die AC-1/AC-2-Fixture-Events dieselben Werte liefern wie vor der Änderung
    (Funktionsaufruf, kein Text-Vergleich).

- **AC-5 (Regressionsschutz #1170):** Given den bestehenden Compare-Bündel-Fall (ein
  einzelner Vergleichs-Ort, zwei Metriken, `segment_id` nie gesetzt) / When
  `render_email()` den Multi-Event-Datenblock rendert / Then bleibt die Ausgabe
  UNVERÄNDERT (kein `"km 0–0"`- oder sonstiger neuer Zusatz) — der #1861-Differenzierer
  greift nur bei gesetztem `segment_id` (Trip-Pfad).
  - Test: `tests/tdd/test_issue_1170_compare_alert_config.py::test_ac7_single_location_two_metrics_no_per_row_location_prefix`
    bleibt grün. **Nachtrag 2026-08-16 (Adversary-Finding F002):** der Test wurde um EINE
    Assertion ERWEITERT (`"km 0" not in plain`) — die Zusicherung wird dadurch nicht
    gelockert, sondern erst wirksam bewacht. Bis dahin prüfte er nur den alten
    Ortsname-Präfix; eine Mutation, die `render._per_event_where_when()` bedingungslos
    `True` liefern lässt, schrieb `"km 0–0"` in jede Compare-Zeile und ließ ihn trotzdem
    grün. Gegenprobe nachgemessen: mit der Assertion ist die Mutation rot.

- **AC-6 (gebundene Tests grün):** Given den vollständigen geänderten Renderer / When die
  ZWEI folgenden Aufrufe ausgeführt werden / Then sind alle fünf Dateien grün
  (Renderer-Commit-Gate #811-Vorbedingung):
  1. `uv run pytest tests/tdd/test_alert_bundle_958ff.py tests/tdd/test_issue_1170_compare_alert_config.py tests/tdd/test_alert_multi_event_where_when.py tests/tdd/test_issue_811_mode_matrix.py`
  2. `uv run pytest tests/tdd/test_issue_1169_compare_alert_consumer.py -m "email" --disable-socket --allow-hosts=127.0.0.1,::1`
  - Test: die o. g. `pytest`-Aufrufe selbst (benannte Dateien, keine Volllauf-Sperre
    betroffen).
  - **Warum ZWEI Aufrufe (Adversary-Finding F001):** `test_issue_1169_compare_alert_consumer.py`
    trägt `pytestmark = pytest.mark.email` (Zeile 73) und wird vom Default-`addopts`
    (`pyproject.toml:65`) STILL deselektiert — im ersten Aufruf mitgelistet, liefe sie mit
    **0 gesammelten Tests** durch und der AC-6-Nachweis für diese Datei wäre vakuos. Sie
    braucht deshalb ihren eigenen Aufruf MIT `-m "email"`; ein gemeinsamer Aufruf mit
    `-m "email"` scheidet aus, weil dann umgekehrt die vier ungemarkerten Dateien
    deselektiert würden. `--disable-socket --allow-hosts=127.0.0.1,::1` hält den Lauf
    offline (Egress-Wächter, #1755). Von den 6 Tests der Datei sind 5 (AC-1/2/3/4/6)
    **vorbestehend rot** — am unveränderten `render.py` gegengemessen; für AC-6 gebunden
    ist nur `test_ac7_trip_alert_rendering_unchanged` (Golden-Master der Plain-Mail).

## Known Limitations

- **SMS bewusst ausgeklammert.** `_sms_token()` hängt bereits `@HH` an und unterliegt
  einem harten GSM-7-Zeichenlimit — ein Segment-Zusatz würde eine eigene
  Token-Format-Erweiterung erfordern (größerer Eingriff). Eigenes Ticket bei Bedarf.
- **`render_subject()` (Betreff) bewusst ausgeklammert.** Der Multi-Event-Betreff
  (`top3`-Auswahl in `render_subject`, Zeile ~335-339) zeigt bereits unterschiedliche
  WERTE je Event (z. B. "Gewitter 1, Gewitter 0"), aber keinen Segment-/Zeit-Bezug — bei
  IDENTISCHEN Werten (z. B. zwei Events mit `value_to=0`) bleibt der Betreff weiterhin
  ununterscheidbar. Aus dieser Spec ausgeklammert, weil der PO-Bug-Report sich primär auf
  den Mailkörper bezieht und der Betreff einer Längenbegrenzung durch die
  Top-3-Auswahl unterliegt (eigene Format-Entscheidung nötig). Eigenes Ticket bei Bedarf.
- **Zwei Events mit IDENTISCHEM `segment_id` UND IDENTISCHEM `occurred_at`** (echte
  Zeitgleichheit) bleiben weiterhin ununterscheidbar — das ist eine seltene
  Datenkonstellation (eher ein Dedup-Thema auf einer vorgelagerten Stufe) und kein
  bekannter PO-Bug-Report-Fall.
- **Compare-Bündel-Multi-Point-Pfad (`location_label` je Event) bleibt unverändert.**
  Auch dort könnten zwei Events derselben Metrik an verschiedenen Orten mit identischem
  Wert theoretisch ununterscheidbar sein — aus dieser Spec ausgeklammert (kein
  PO-Bug-Report dafür, Risiko einer #1170-Regression bei ungeprüfter Erweiterung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Text-/Templating-Korrektur innerhalb eines bestehenden Renderers,
  keine der in `docs/adr/README.md` genannten Entscheidungsflächen (Kanal/Provider,
  Datenmodell/Persistenz, Auth, Editor-Paradigma, Test-/Deploy-Strategie). `AlertEvent`/
  `AlertMessage` (ADR-0011, kanonisches Modell) bleiben unverändert; `over_thr()`/
  `side_label()` (ADR-0013-Kontext, #958) bleiben in ihrer Semantik unverändert.

## Changelog

- 2026-08-15: Initial spec created
