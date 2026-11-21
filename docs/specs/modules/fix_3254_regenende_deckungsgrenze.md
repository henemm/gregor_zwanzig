---
entity_id: fix_3254_regenende_deckungsgrenze
type: module
created: 2026-11-21
updated: 2026-11-21
status: approved
version: "1.0"
tags: [radar, nowcast, alarm, kurzform]
---

# Fix #3254: Regen-Ende = Ende des letzten nassen Zeitabschnitts

## Approval

- [x] Approved (PO-Freigabe 2026-11-21, „Freigegeben“; Zeichen `?` bleibt, PO-Entscheid 2026-11-21)

## Purpose

Der Radar-Alarm nennt bei kurzen Schauern ein Ende, das gleich dem Beginn ist
(`Aabenraa: R@16:45@16:45`, E-Mail „ab 16:45 · letzter Regen gegen 16:45“).
Ursache: Das Ende ist der **Anfang** des letzten nassen 15-Minuten-Abschnitts,
nicht dessen Ende. Künftig nennt jede Ende-Angabe das Ende dieses Abschnitts.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `_derive_wet_block_end()` (Trockenframe-Zweig und Rest-Rückgabe)

Python-Core; keine Änderung an Go-API oder Frontend.

## Estimated Scope

- **LoC:** ~10 Quellcode, ~80 Tests
- **Files:** 1 Quelle, 1 neue Testdatei, ggf. Anpassung bestehender Erwartungswerte
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_2051_s1_dauer_und_ende.md` | Spec | Definiert Ende/Untergrenze; dieser Fix vereinheitlicht die Ende-Konvention |
| `fix_2075_ende_am_radar_horizont.md` | Spec | Horizont-Zweig bleibt unverändert |
| `alert/project.py::event_end_display` | function | liest `event_end_minutes`, unverändert |

## Implementation Details

Heute drei Konventionen für „Ende“ in `_derive_wet_block_end()`:

| Zweig | heute | künftig |
|---|---|---|
| nächster Frame trocken | Zeitstempel des letzten nassen Frames (Abschnitts-**Anfang**) | Deckungsende des letzten nassen Frames: `min(ts + _MAX_FRAME_COVERAGE, nächster Frame, horizon)` |
| Lücke > Deckung | Deckungsende | unverändert |
| Horizont / Reihe abgeschnitten | Deckungsende bzw. Horizont, `ongoing=True` | unverändert |
| Rest-Rückgabe (kein nasser Frame) | `onset_ts` | Deckungsende des Beginn-Frames |

Damit gilt eine einzige Konvention (dieselbe wie Laufend-Zweig #2050 S2b und
Untergrenzen-Form #2051 S1): Ende = Deckungsgrenze des letzten nassen Frames.
Keine neue Toleranzzahl. Die Rendering-Grammatik (`@HH:MM`, ` >@HH:MM`, `?`)
bleibt unverändert.

Folge: Alle Ende-Angaben verschieben sich gegenüber heute um die Deckung des
letzten nassen Frames (in der Regel +15 Min). Das ist die Korrektur, nicht
ein Nebeneffekt: Ein nasser Abschnitt 16:45–17:00 endet um 17:00.

## Expected Behavior

- **Input:** Frame-Reihe mit nassem Block, gefolgt von einem Trockenframe
- **Output:** `event_end_minutes` zeigt auf das Ende des letzten nassen Abschnitts
- **Side effects:** Güte-Marker `?` kann in Grenzfällen häufiger erscheinen, weil das Ende bis zu 15 Min später liegt (gewollt, die Grenze wird korrekt angewendet)

## Acceptance Criteria

- **AC-1:** Given ein Regenereignis, das nur aus einem einzigen nassen 15-Minuten-Abschnitt besteht (16:45 nass, 17:00 trocken) / When der Radar-Alarm in Kurzform erzeugt wird / Then lautet der Text `R@16:45@17:00` und nie `R@16:45@16:45`.
  - Test: Nowcast aus Frames bis zur Kurznachricht (`render_sms`), Textvergleich.
- **AC-2:** Given dasselbe Ein-Abschnitt-Ereignis / When E-Mail und Telegram (ausführlich) erzeugt werden / Then steht dort „letzter Regen gegen 17:00“, also eine spätere Uhrzeit als der Beginn.
  - Test: Rendern beider Kanäle aus demselben Nowcast.
- **AC-3:** Given ein Ereignis über mehrere nasse Abschnitte (16:45, 17:00, 17:15 nass, 17:30 trocken) / When das Ende bestimmt wird / Then ist das Ende 17:30.
  - Test: `event_end_minutes` aus `_derive_result` gegen erwartete Minuten.
- **AC-4:** Given für beliebige Ereignisse, deren Ende bekannt ist / When die Kurzform erzeugt wird / Then liegt das Ende stets nach dem Beginn; Beginn und Ende sind nie dieselbe Uhrzeit.
  - Test: Eigenschaftstest über mehrere erzeugte Frame-Reihen (Einzelabschnitt, Mehrfachabschnitt, Lücke, Horizont).
- **AC-5:** Given ein Ereignis, das bis an den Rand der Radarvorhersage reicht / When die Kurzform erzeugt wird / Then bleibt die Form „mindestens bis“ (` >@HH:MM`) unverändert erhalten.
  - Test: bestehender Horizont-Fall (#2075) bleibt grün, zusätzlich Textvergleich.
- **AC-6:** Given ein Ortsvergleich mit mehreren Orten, an denen kurze Schauer auslösen / When die Mehrort-Kurzform erzeugt wird / Then trägt jeder Ort ein Ende nach seinem Beginn (`1:R@16:45@17:00`).
  - Test: Mehrort-Kurzform aus zwei Nowcasts.

## Known Limitations

- Die Auflösung bleibt 15 Minuten; ein Schauer von 5 Minuten erscheint als 15-Minuten-Abschnitt.
- Lesbarkeit der Kurzform-Zeichen (`>`, `?`) ist nicht Gegenstand dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fehlerkorrektur innerhalb der freigegebenen #2051-S1-Konvention (Deckungsgrenze), keine neue Entscheidung.

## Changelog

- 2026-11-21 v1.0: Entwurf, vom PO freigegeben.
