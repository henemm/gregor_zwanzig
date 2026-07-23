---
entity_id: warn_unavailable_hint
type: feature
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [official-alerts, email, safety, issue-1348]
---

# Briefing-Hinweis: amtliche Warnungen nicht abrufbar

## Approval

- [ ] Approved

## Purpose

Wenn amtliche Warn-Dienste ausfallen (429/Block/Exception), liefert
`get_official_alerts_for_location()` heute fail-soft `[]` zurück — im
Trip-Briefing sieht das aus wie "keine Warnungen = alles ruhig". Für ein
Wander-Sicherheits-Werkzeug ist diese Verwechslung gefährlich. Dieses Modul
unterscheidet "nicht abrufbar" von "keine Warnungen vorhanden" und macht den
Unterschied im E-Mail-Trip-Briefing (full + compact) sichtbar.

## Source

- **File:** `src/services/official_alerts/base.py`
- **Identifier:** `def get_official_alerts_with_status` (neu), `def get_official_alerts_for_location` (Wrapper, unveraendert im Vertrag)
- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** Fetch-Stelle amtliche Warnungen, ~Zeile 780-807
- **File:** `src/app/models.py`
- **Identifier:** `class SegmentWeatherData`, neues Feld `official_alerts_unavailable`
- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** neue Helfer `any_official_alerts_unavailable`, `render_official_alerts_unavailable_html`, `render_official_alerts_unavailable_plain`
- **File:** `src/output/renderers/email/html.py`, `src/output/renderers/email/plain.py`, `src/output/renderers/email/compact.py`
- **Identifier:** Integration der Helfer im bestehenden "amtliche Warnungen"-Baustein je Renderer

## Estimated Scope

- **LoC:** ~90-140
- **Files:** 6 (Produktivcode) + 1 neue Testdatei
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.official_alerts.base.OfficialAlertSource` | Protocol | Quellen-Interface (`covers`, `fetch`, `name`) — Basis fuer die neue Status-Berechnung |
| `services.official_alerts.base._REGISTERED_SOURCES` | module-state | Registry aller amtlichen Quellen, wird iteriert |
| `services.trip_report_scheduler.TripReportScheduler` | service | Fetch-Stelle, setzt das neue Flag je Segment |
| `app.models.SegmentWeatherData` | dataclass | traegt das neue Feld additiv weiter bis zum Renderer |
| `output.renderers.alert.official_alerts` | module | geteilter Renderer-Baustein (Epic #1073 Punkt 6: EIN Renderer statt Kopien je Format) |
| `tests/tdd/test_issue_811_mode_matrix.py` | test | Renderer-Commit-Gate #811 — MUSS gruen bleiben |
| `.claude/hooks/briefing_mail_validator.py` | validator | Pflicht-Lauf gegen echte Staging-Mail vor "E2E bestanden" |

## Implementation Details

**1. Status-Erhebung (`base.py`):** neue Funktion
`get_official_alerts_with_status(lat, lon, window_start=None, window_end=None,
now=None) -> tuple[list[OfficialAlert], bool]`. Uebernimmt den kompletten
Fetch-/Filter-/Dedup-Koerper der heutigen `get_official_alerts_for_location`,
trennt aber je Quelle ZWEI try/except-Bloecke statt einem:

```
covering, failed = 0, 0
for source in _REGISTERED_SOURCES:
    try:
        does_cover = source.covers(lat, lon)
    except Exception:
        logger.warning(...); continue   # faellt-sicher: KEIN Coverage-Nachweis
    if not does_cover:
        continue
    covering += 1
    try:
        results.extend(source.fetch(lat, lon))
    except Exception:
        logger.warning(...); failed += 1
unavailable = covering > 0 and failed >= 1   # PO-Entscheid 2026-07-23: STRENG —
# schon EINE ausgefallene abdeckende Quelle genügt (eine ausgefallene Quelle
# hätte eine Warnung tragen können, die die anderen nicht abdecken).
```

`get_official_alerts_for_location()` wird zum duennen Wrapper
(`alerts, _ = get_official_alerts_with_status(...); return alerts`) — Vertrag
und Rueckgabetyp fuer alle 37 Bestandsaufrufer (u.a. `trip_alert.py`,
`compare_official_alert.py`, `comparison_engine.py`) bleiben unveraendert.

**2. Modell (`app/models.py`):** `SegmentWeatherData` bekommt
`official_alerts_unavailable: bool = False` (additiv, Default `False` —
bestehende Konstruktions-Aufrufe ohne dieses Feld bleiben gueltig).

**3. Scheduler-Wiring (`trip_report_scheduler.py:~797`):** ersetzt den
Aufruf durch `get_official_alerts_with_status(...)`, setzt
`sw.official_alerts, sw.official_alerts_unavailable = alerts, unavailable`.
Der bestehende äussere `except Exception`-Zweig (Import-/Unerwarteter Fehler)
setzt zusaetzlich `sw.official_alerts_unavailable = True` — im
Zweifelsfall sicherheitsseitig warnen statt schweigen.

**4. Geteilter Renderer-Baustein (`output/renderers/alert/official_alerts.py`):**
`any_official_alerts_unavailable(segments) -> bool` prueft
`any(getattr(seg, "official_alerts_unavailable", False) for seg in segments)`.
`render_official_alerts_unavailable_html()` liefert einen hochkontrastigen Box-
Baustein nach dem bestehenden Vorbild "Segment X: Wetterdaten nicht
verfuegbar" (`html.py:919`, `G_BOX_DANGER_BG`/`G_DANGER` — explizit KEIN
`G_INK_FAINT`). `render_official_alerts_unavailable_plain(*, ascii_safe=False)`
liefert die Textzeile (mit "⚠️" fuer `plain.py`, ASCII-Praefix "!!" fuer
`compact.py`, analog `_AMPEL_ASCII_SEVERITY`).

**5. Renderer-Integration:** `html.py` (~Zeile 1305, direkt bei
`warn_block_html`), `plain.py` (~Zeile 207-213, im "amtliche Warnungen"-Block)
und `compact.py` (~Zeile 160-165, im "== Warnungen =="-Block) rufen die neuen
Helfer zusaetzlich zum bestehenden Alert-Rendering auf. Der Hinweis erscheint
UNABHAENGIG davon, ob `_alert_entries`/`_deduped` leer sind oder nicht (beide
Bedingungen sind orthogonal: "unavailable" heisst per Definition, dass fuer
mindestens einen Ort keine echten Alert-Daten vorlagen).

## Expected Behavior

- **Input:** `TripSegment`-Liste mit Segment-Startpunkten; amtliche
  Warn-Quellen-Registry (`_REGISTERED_SOURCES`), je Quelle `covers()`/`fetch()`.
- **Output:** E-Mail-Trip-Briefing (full-HTML, full-Plain, compact) zeigt einen
  sichtbaren Hinweis "amtliche Warnungen aktuell nicht abrufbar", wenn fuer
  mindestens ein Segment MINDESTENS EINE abdeckende Quelle beim Fetch
  fehlgeschlagen ist (PO-Entscheid: streng). Fehlt Coverage ganz oder liefern
  ALLE abdeckenden Quellen erfolgreich (auch leer), erscheint KEIN Hinweis —
  Verhalten bleibt wie bisher.
- **Side effects:** keine; reine Zusatz-Anzeige, keine Aenderung an
  Alarm-/Dispatch-/Scheduler-Erfolgslogik (das ist Scope von #1346, nicht
  dieser Spec).

## Test Plan

**Kern (deterministisch, kein Live-Netz):** neue Datei
`tests/tdd/test_official_alerts_unavailable_hint.py`, Test-Doubles nach dem
etablierten Muster aus `test_issue_1034_official_alerts_foundation.py`
(`_REGISTERED_SOURCES` per `backup/clear/restore` in try/finally isolieren,
echte Objekte statt Mock/patch):

- `_AllCoveringFailSource` (covers=True, fetch wirft) → `unavailable=True`
- `_SuccessEmptySource` (covers=True, fetch liefert `[]`) → `unavailable=False`
- `_NonCoveringSource` (covers=False) → `unavailable=False`
- Mischfall (STRENG, PO-Entscheid): eine deckende Quelle wirft, eine deckende
  Quelle liefert `[]` → `unavailable=True` (schon eine ausgefallene Quelle genügt)
- `get_official_alerts_for_location()` liefert bei gleicher Fixture-Lage
  dieselbe Alert-Liste wie bisher (Rueckwaertskompatibilitaets-Test)
- Renderer-Ebene: `segment_weather` mit `official_alerts_unavailable=True` auf
  einem Segment → `render_email(...)` (full HTML/Plain) und `render_compact(...)`
  enthalten den Hinweistext; ohne das Flag (Bestandsfixtures) bleibt die
  Ausgabe byte-identisch zum Stand vor dieser Aenderung (Renderer-Gate #811).

**Pflicht vor Abschluss (Renderer-Mail-Gate #811, un-ueberspringbar):**
1. `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` gruen
2. `uv run python3 .claude/hooks/briefing_mail_validator.py` gegen eine echt
   zugestellte Staging-Mail (Marker `X-GZ-Mail-Type: trip-briefing` +
   `X-GZ-Format: full|compact`), Exit 0

## Acceptance Criteria

- **AC-1:** Given fuer den Ort eines Trip-Segments wirft MINDESTENS EINE
  abdeckende amtliche Quelle beim Fetch (PO-Entscheid: streng) / When das Trip-Briefing als volle HTML-Mail
  gerendert wird / Then zeigt die Mail einen sichtbaren, hochkontrastigen
  Hinweis "amtliche Warnungen aktuell nicht abrufbar" (Farb-Token
  `G_DANGER`/`G_BOX_DANGER_BG`, NIE `G_INK_FAINT`).
  - Test: echter `render_email(...)`-Aufruf mit einem Segment,
    `official_alerts_unavailable=True`; Assertion auf sichtbaren Hinweistext
    im HTML-Output (kein Dateiinhalt-Check auf Quellcode, sondern auf
    gerendertes Ergebnis).

- **AC-2:** Given dieselbe Ausfallsituation wie AC-1 / When das
  Compact-Text-Briefing gerendert wird / Then enthaelt der ASCII-Text einen
  Hinweis auf die Nicht-Abrufbarkeit, unabhaengig davon ob zusaetzlich echte
  Warnungen fuer andere Segmente vorliegen.
  - Test: echter `render_compact(...)`-Aufruf, Mischfall (ein Segment
    `unavailable=True`, ein anderes mit echtem Alert) — beide Informationen
    erscheinen im Output.

- **AC-3:** Given ALLE abdeckenden Quellen liefern erfolgreich ein Ergebnis
  (auch ein leeres) — KEINE abdeckende Quelle ist ausgefallen / When das Briefing
  (alle drei Formate) gerendert wird / Then erscheint KEIN Nicht-abrufbar-Hinweis
  — ein leeres Ergebnis gilt weiterhin als "keine Warnungen, alles ruhig".
  - Test: Fixture mit ausschliesslich erfolgreichen Quellen ohne Treffer;
    Hinweistext fehlt in HTML/Plain/Compact. Zusaetzlich Mischfall-Test (eine
    Quelle wirft, eine liefert leer) → Hinweis ERSCHEINT (streng).

- **AC-4:** Given fuer den Ort ist keine amtliche Quelle zustaendig
  (`covers()` liefert bei allen registrierten Quellen `False`) / When das
  Briefing gerendert wird / Then erscheint KEIN Nicht-abrufbar-Hinweis (kein
  Coverage-Bereich rechtfertigt keinen Fehlalarm).
  - Test: Fixture ohne deckende Quelle; `unavailable=False`, kein
    Hinweistext in keinem der drei Formate.

- **AC-5:** Given Bestandsaufrufer nutzen weiterhin
  `get_official_alerts_for_location()` (z.B. `trip_alert.py`,
  `compare_official_alert.py`, `comparison_engine.py`) / When dieselbe
  Fixture-Lage wie vor dieser Aenderung durchlaeuft / Then bleibt die
  zurueckgegebene Alert-Liste unveraendert (reine Liste, kein Tuple) — kein
  Bestandsaufrufer muss angepasst werden.
  - Test: bestehender bzw. neuer Aufruf von
    `get_official_alerts_for_location()` mit derselben Test-Quelle wie in
    `test_issue_1034_official_alerts_foundation.py`, Ergebnis unveraendert.

- **AC-6:** Given der Fall "keine Warnungen vorhanden UND alle Quellen
  erfolgreich" (Bestandsverhalten, `official_alerts_unavailable=False` auf
  allen Segmenten) / When html.py/plain.py/compact.py vor und nach dieser
  Aenderung gerendert werden / Then ist die Ausgabe byte-identisch
  (Regressionsschutz, erzwungen durch `test_issue_811_mode_matrix.py`).
  - Test: bestehende Mode-Matrix-Tests bleiben gruen ohne Anpassung ihrer
    Erwartungswerte.

## Known Limitations

- **Nur E-Mail-Trip-Briefing (full + compact) in dieser Scheibe.** SMS-Token
  (analog `C+/C~/C?`) und Telegram sind ausdrueckliche Folge-Scheiben — SMS
  hat ein hartes Char-Limit (160 Byte), das eine eigene Kompressions-
  Entscheidung braucht.
- **Orts-Vergleich (Compare-Mail) ist NICHT Teil dieser Scheibe.**
  `PointWeatherData`/`compare_html.py`/`comparison.py` bekommen das
  `unavailable`-Flag hier nicht — Folge-Issue, falls PO das priorisiert.
- **Partial-Failure gilt als "unavailable" (PO-Entscheid 2026-07-23, STRENG):**
  schon EINE ausgefallene abdeckende Quelle löst den Hinweis aus — auch wenn
  eine andere abdeckende Quelle für denselben Ort gleichzeitig erfolgreich
  (auch leer) antwortet. Begründung: die ausgefallene Quelle hätte eine
  Warnung tragen können, die die andere nicht abdeckt; „konnten wir nicht
  prüfen" ist die sichere Aussage. Nur wenn ALLE abdeckenden Quellen erfolgreich
  antworten, erscheint kein Hinweis.
- **Segment-Dedup-Verhalten unveraendert:** `trip_report_scheduler.py` fetcht
  amtliche Warnungen nur einmal je eindeutiger Segment-Koordinate
  (`seen_coords`); das neue Flag wird nur auf dem zuerst gefetchten Segment
  dieser Koordinate gesetzt. Der Trip-weite Hinweis (`any(...)` ueber alle
  Segmente) faengt das ab, ohne die bestehende Fetch-Dedup-Logik anzutasten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweitert eine bestehende Fail-soft-Registry (Issue #1034)
  um eine Status-Rueckgabe und einen zusaetzlichen Anzeige-Baustein im
  bereits etablierten geteilten Renderer (Epic #1073 Punkt 6). Beruehrt keine
  der in `docs/adr/README.md` gelisteten Entscheidungsflaechen (Kanaele,
  Provider, Datenmodell/Persistenz, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie) — additive Feld-/Funktionserweiterung, keine
  Grundsatzentscheidung.

## Changelog

- 2026-07-23: Initial spec created
