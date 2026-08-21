---
entity_id: fix_1741_telegram_kappungshinweis
type: bugfix
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [telegram, channel_layout, kappungshinweis, dead-code]
---

# Telegram-Trip-Nachricht: Kappungshinweis + toten Detail-Pfad entfernen

## Approval

- [x] Approved (PO „go", 2026-08-21)

## Purpose

Wird eine Telegram-Trip-Auswahl auf mehr als 7 Wettergrößen konfiguriert, zeigt die
Segment-Tabelle nur die ersten 7 (stündlich); die überzähligen erscheinen weiterhin als
Tageswert in der Kurzübersicht-Bubble, verlieren aber ihre stündliche Auflösung — und die
Telegram-Nachricht selbst sagt nirgends, dass gekappt wurde. Wer unterwegs liest, ohne den
Editor offen zu haben, kann das nicht erkennen. Diese Spec schließt die Lücke über einen mit
dem Ortsvergleich geteilten Hinweisbaustein und entfernt gleichzeitig den seit 2026-07-03
toten `detail_metrics`/`_detail_lines()`-Pfad, der denselben Bug wiederholt vortäuschen
würde, solange er im Code steht.

## PO-Entscheide vom 2026-08-21 (bindend)

1. Die Telegram-Trip-Nachricht bekommt einen Kappungshinweis, inhaltlich analog zum
   Ortsvergleich, über einen geteilten Baustein.
2. Der tote Pfad `ChannelLayout.detail_metrics` + `_detail_lines()` wird ersatzlos entfernt.
3. **Die Detail-Zeile wird NICHT wieder gebaut.** Das widerspräche der PO-Entscheidung vom
   2026-06-06 („Kein '→ Detail'-Knopf, keine Detail-Zeile", `WeatherV2Reihenfolge.svelte:4`,
   Issue #587): Der `secondary`-Bucket im Editor ist seither immer leer
   (`WeatherMetricsTab.svelte:220`, erzwungen `:436`/`:682`). Der Wegfall von
   `_detail_lines()` in Commit `6b27798f` (#1001, 2026-07-03) hat diesen Entscheid
   umgesetzt — nur die zugehörige Spec (`feat_1001_telegram_redesign.md`) hat ihn nicht
   protokolliert, was #1741 als vermeintliche Regression erst erzeugt hat. Dieser Abschnitt
   holt die fehlende Dokumentation nach.
4. #1741 bleibt im Milestone „Tour KHW 2026-08" — unabhängig davon, dass der Tour-Trip
   `KHW 403` im `telegram_style=kurzform` fährt und den Bubble-Renderer damit auf der Tour
   selbst gar nicht durchläuft (siehe „Known Limitations").

## Source

- **File:** `src/output/renderers/narrow.py`
- **Identifier:** `render_telegram_bubbles()` (Kurzübersicht-Bubble-Aufbau)
- **File:** `src/output/renderers/channel_layout.py`
- **Identifier:** `ChannelLayout`, `render_for_channel()`
- **File:** `src/output/renderers/comparison.py`
- **Identifier:** `_telegram_metric_notice()` — Vorbild und Umzugsziel

## Estimated Scope

- **LoC:** ~+45 / −95 (Netto-Abbau durch Entfernen von `_detail_lines()` und
  `applyChannel()`/`ChannelLayout` im Frontend)
- **Files:** 3 Produktiv-Backend, 1 Produktiv-Frontend, 6 Test-Backend, 1 Test-Frontend
- **Effort:** low — additiver Hinweistext + Entfernen unerreichbaren Codes; kein neuer
  Berechnungspfad, `demoted_count` liegt bereits vor.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `channel_layout.render_for_channel()` | function | liefert `ChannelLayout.demoted_count`, unverändert wiederverwendet |
| `comparison._telegram_metric_notice()` | function | Vorbild-Wortlaut, wird zum geteilten Baustein `channel_layout.telegram_metric_notice()` |
| `trip_report.py:275-292` (`_dc_telegram`) | module | EINE kanal-kaskadierte Quelle für Tabelle + Kurzübersicht (#1719 S2 F004) — dieser Fix liest ausschließlich `layout.demoted_count`, keine neue Quelle |
| `_TG_PROSE_WIDTH` (`narrow.py:55`) | constant | Breitenbudget für den Hinweistext (Prosa, nicht Tabelle) |

## Implementation Details

### 1. Geteilter Baustein: `channel_layout.telegram_metric_notice()`

`_telegram_metric_notice()` (`comparison.py:854-869`) wandert unverändert im Verhalten,
aber umbenannt und parametrisiert nach `channel_layout.py` (dort liegt bereits die
`ChannelLayout`-Definition, und sowohl `narrow.py` als auch `comparison.py` importieren
schon von dort — kein neuer Modul-Kopplungspunkt):

```
def telegram_metric_notice(demoted_count: int, *, context: str) -> str:
    """context='vergleich' -> Ortsvergleich-Wortlaut (#1362, unveraendert).
    context='route' -> Trip-Wortlaut (#1741, neu). Leer, wenn nichts verdraengt wurde.

    Die beiden Wortlaute sind BEWUSST nicht ueber einen gemeinsamen Satzbau
    gebildet: im Ortsvergleich fehlen die verdraengten Groessen in der
    Telegram-Nachricht GANZ, im Trip stehen sie unmittelbar darueber in der
    Kurzuebersicht als Tageswert. Ein gemeinsamer Text waere fuer eine der
    beiden Flaechen sachlich falsch."""
    if demoted_count <= 0:
        return ""
    if context == "vergleich":
        return (
            f"… +{demoted_count} weitere Wettergrößen je Ort (Telegram-Limit) "
            "— vollständig per E-Mail"
        )
    return (
        f"… +{demoted_count} weitere Wettergrößen nur als Tageswert "
        "(Telegram-Limit)"
    )
```

`comparison.py` importiert die Funktion und ruft `telegram_metric_notice(layout.demoted_count,
context="vergleich")` — Wortlaut und Ausgabe bleiben für den Ortsvergleich bit-identisch zu
heute (Regressionsschutz, kein neuer Test nötig, vorhandener `test_compare_kanal_metriken.py`
bleibt grün).

### 2. Wortlaut für den Trip-Pfad

Der Ortsvergleich-Wortlaut „je Ort" ist für den Trip falsch — es gibt keine Orte, sondern
Etappen-/Ziel-Tabellen, die alle **dieselbe** Kappung erben (`layout` wird in
`render_telegram_bubbles()` EINMAL für den ganzen Trip berechnet, `narrow.py:700`, nicht je
Segment). Gewählter Wortlaut: **„… +N weitere Wettergrößen nur als Tageswert
(Telegram-Limit)"**. Begründung:

- **Benennt, was tatsächlich fehlt.** Die verdrängten Größen sind nicht verschwunden — die
  Kurzübersicht-Bubble zeigt jede aktive Telegram-Metrik als Tagesaussage
  (`narrow.py:780-807`). Verloren geht ausschließlich die **stündliche Auflösung** in den
  Etappentabellen. Ein Text, der die Größen als fehlend darstellt, wäre falsch.
- **Kein Verweis auf E-Mail** — anders als im Ortsvergleich. Dort fehlen die Größen ganz,
  dort trägt der Verweis. Beim Trip stünde er direkt unter den Werten, auf die er
  verweist. Zudem gilt projektweit, dass kein Kanal einen anderen ersetzt: E-Mail kann für
  diesen Trip abgeschaltet sein, dann ginge der Hinweis ins Leere.
- **Steht an der richtigen Stelle:** am Ende der Kurzübersicht, unmittelbar nach den
  Tageswerten, auf die sich „nur als Tageswert" bezieht.
- Bleibt ohne HTML/Markup (reiner Text) und passt mit typischen `demoted_count`-Werten
  (1-stellig) klar unter `_TG_PROSE_WIDTH = 56`.

### 3. Position in der Nachricht

Der Hinweis erscheint **einmal**, am Ende der **Kurzübersicht-Bubble**
(`render_telegram_bubbles()`, `narrow.py:759-845`) — NICHT in den Segment-Bubbles. Begründung:

- Segment-Bubbles wiederholen sich pro Etappe/Tag; `demoted_count` ist über den ganzen Trip
  identisch (eine `layout`-Berechnung, s.o.) — ein Hinweis pro Segment wäre reiner Lärm
  (mehrfach dieselbe Information).
- Die Kurzübersicht-Bubble ist die einzige Stelle, die bereits GANZ am Ende eigene
  Meta-Hinweiszeilen sammelt (Herkunfts-Vertretung `build_fallback_lines`, Vortags-Zeile
  `_tg_vortag_line`) — der Kappungshinweis reiht sich dort als letzter Block ein, direkt vor
  `bubbles.append(TelegramBubble(text="\n".join(overview_lines)))` (`narrow.py:845`), nach
  dem `vortag_line`-Block. Gleiche Bauart (Leerzeile + `_wrap(_esc(...), _TG_PROSE_WIDTH)`).
- Wer die Kurzübersicht liest, bekommt den Hinweis, BEVOR er auf die gekappten
  Segment-Tabellen trifft (Bubble-Reihenfolge: Kopf, Kurzübersicht, dann Segmente).

### 4. Datenquelle

`layout = render_for_channel("telegram", dc, report_type)` (`narrow.py:700`) wird bereits
berechnet; `layout.demoted_count` ist der einzige neue Lesezugriff. Keine neue Berechnung.

### 5. Toter Pfad entfernen

- `ChannelLayout.detail_metrics`-Feld (`channel_layout.py:86`) entfernen. `demoted_count`
  bleibt (wird weiterhin aus `len(overflow)` berechnet, `channel_layout.py:128`); die
  `overflow + secondary`-Zusammenstellung entfällt, weil niemand mehr liest.
- `_detail_lines()` (`narrow.py:111-138`) ersatzlos entfernen — 0 Aufrufstellen.

## Expected Behavior

- **Input:** Eine `UnifiedWeatherDisplayConfig` mit mehr als 7 aktiven `primary`-Telegram-
  Metriken (oder `secondary`-Metriken, die nie eine Tabellenspalte bekommen).
- **Output:** `render_telegram_bubbles()` liefert eine Kurzübersicht-Bubble, deren Text am
  Ende die Zeile „… +N weitere Wettergrößen nur als Tageswert (Telegram-Limit)"
  trägt, mit `N == layout.demoted_count`. Bei `demoted_count == 0`
  fehlt die Zeile vollständig (keine leere Zeile, kein „+0").
- **Side effects:** keine. Pure function, wie der gesamte Modul-Kontrakt (`narrow.py:10-12`).

## Acceptance Criteria

- **AC-1:** Given eine Telegram-Auswahl mit mehr als 7 aktiven primary-Metriken (z. B. 9),
  When `render_telegram_bubbles()` gerendert wird, Then enthält der Text der
  Kurzübersicht-Bubble die Zeile „… +N weitere Wettergrößen nur als Tageswert
  (Telegram-Limit)" mit korrektem `N`.
  - Test: `tests/tdd/test_telegram_metric_notice.py` — Assertion auf `bubbles[i].text`
    (Kurzübersicht-Bubble anhand des Präfix „Kurzübersicht" gefunden, nicht per festem
    Index), nicht auf `ChannelLayout`.

- **AC-2:** Given eine Telegram-Auswahl mit höchstens 7 aktiven primary-Metriken (kein
  Überlauf), When `render_telegram_bubbles()` gerendert wird, Then fehlt die
  Kappungshinweis-Zeile vollständig im Bubble-Text.
  - Test: umgebauter `tests/tdd/test_issue_887_report_inkonsistenz.py::
    test_ac5_telegram_no_detail_line_when_only_temp_and_wind` (Fixture hat bereits nur 2
    Metriken, also `demoted_count == 0`) — Assertion wechselt von „keine Detail-Zeile" auf
    „keine Kappungshinweis-Zeile".

- **AC-3:** Given eine Telegram-Auswahl mit Überlauf UND mehreren Segmenten/Etappen, When
  `render_telegram_bubbles()` gerendert wird, Then trägt GENAU EINE Bubble (die
  Kurzübersicht) den Hinweistext; keine der Segment-Bubbles enthält ihn.
  - Test: `tests/tdd/test_telegram_metric_notice.py` mit >=2 Segmenten — zählt Vorkommen
    des Hinweistext-Fragments über alle `bubbles[i].text` hinweg, erwartet genau 1.

- **AC-4:** Given `layout.demoted_count > 0` im Ortsvergleich-Pfad, When
  `render_compare_telegram()` gerendert wird, Then bleibt der Wortlaut „… +N weitere
  Wettergrößen je Ort (Telegram-Limit) — vollständig per E-Mail" unverändert gegenüber dem
  Stand vor diesem Fix.
  - Test: bestehender `tests/tdd/test_compare_kanal_metriken.py` bleibt ohne Änderung grün
    (Regressionsschutz für den Umzug von `_telegram_metric_notice()` nach
    `channel_layout.telegram_metric_notice()`).

- **AC-5:** Given der SMS-Versandpfad (`sms_trip.py`, `build_token_line`/`render_sms`),
  When ein Trip mit Telegram-Überlauf als SMS gerendert wird, Then enthält der SMS-Text
  keine Kappungshinweis-Zeile und keinen Verweis auf `channel_layout`.
  - Test: bestehende SMS-Tests bleiben unverändert grün (`sms_trip.py` importiert
    `channel_layout` nicht — struktureller Nachweis per fehlendem Import, kein neuer Test
    nötig).

- **AC-6:** Given der Produktivcode nach diesem Fix, When `ChannelLayout`
  (`channel_layout.py`) und das `narrow`-Modul (`narrow.py`) inspiziert werden, Then
  besitzt `ChannelLayout` kein Feld `detail_metrics` mehr und `narrow` kein Attribut
  `_detail_lines`.
  - Test: `tests/tdd/test_telegram_metric_notice.py` — `'detail_metrics' not in
    {f.name for f in dataclasses.fields(ChannelLayout)}` und
    `not hasattr(narrow, '_detail_lines')`. Verhindert, dass derselbe tote Pfad erneut als
    vermeintlicher Bug gemeldet wird (siehe Purpose).

## Known Limitations

- Der Kappungshinweis erreicht nur den `rich`-Telegram-Stil. Im `telegram_style=kurzform`
  verwirft `notification_service.py:469-486` die Bubbles und sendet stattdessen
  `report.sms_text`, das `render_telegram_bubbles()` gar nicht durchläuft. Der Tour-Trip
  `KHW 403` fährt `kurzform` — auf der Tour selbst bleibt der Editor-Hinweis (Chip,
  Schnittlinie, Warntext) die einzige Warnung vor dem Versand. Der PO hat #1741 trotzdem im
  Milestone belassen (Entscheid 4, s. o.).
- Der Hinweis nennt nur die Anzahl (`demoted_count`), nicht die betroffenen Metrik-IDs —
  identisch zum Ortsvergleich-Vorbild; eine Auflistung würde das Prosa-Breitenbudget
  (`_TG_PROSE_WIDTH = 56`) bei mehreren überzähligen Größen sprengen.

## Invarianten (dürfen sich NICHT ändern)

- Die 7-Spalten-Grenze der Segment-/Ziel-Tabelle bleibt unverändert
  (`CHANNEL_LIMITS["telegram"]["max_table_cols"] = 8`, `channel_layout.py:47`).
- Die Kurzübersicht-Bubble zeigt weiterhin ALLE aktiven Telegram-Metriken als Tagesaussage
  (`narrow.py:780-807`, unverändert) — dieser Fix ergänzt nur eine zusätzliche Zeile am
  Ende, entfernt keine bestehende.
- Der SMS-Pfad bleibt vollständig unberührt (`sms_trip.py` nutzt `channel_layout` nicht,
  s. AC-5).
- Der Ortsvergleich-Hinweistext bleibt wortgleich zu heute (s. AC-4).
- `buildBucketSummary`/`BucketSummary` (`metricsEditor.ts:407ff.`) bleiben unverändert —
  sie basieren auf `Buckets` (primary/secondary/off), nicht auf dem entfernten
  `applyChannel`/`ChannelLayout`, und werden produktiv von `SavePresetDialog.svelte`
  genutzt.

## Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `src/output/renderers/channel_layout.py` | MODIFY | `ChannelLayout.detail_metrics`-Feld entfernen; neue geteilte Funktion `telegram_metric_notice(demoted_count, *, context)` |
| `src/output/renderers/comparison.py` | MODIFY | lokale `_telegram_metric_notice()` entfernen, Import + Aufruf mit `context="vergleich"` |
| `src/output/renderers/narrow.py` | MODIFY | `_detail_lines()` entfernen (tot); Kappungshinweis am Ende der Kurzübersicht-Bubble einfügen (`context="route"`) |
| `tests/tdd/test_telegram_metric_notice.py` | CREATE | AC-1, AC-3, AC-6 — Nachweis an der Wirkstelle (gerenderte Bubbles), nicht am `ChannelLayout` |
| `tests/tdd/test_issue_887_report_inkonsistenz.py` | MODIFY | `test_ac5_telegram_no_detail_line_when_only_temp_and_wind` umgebaut auf AC-2 (kein Hinweis bei `demoted_count==0`) — bisherige Prämisse „keine Detail-Zeile" ist seit dem Wegfall trivial wahr |
| `tests/tdd/test_issue_360_channel_renderer.py` | MODIFY | `layout.detail_metrics`-Assertionen (Z. 151, 189, 209-210) entfernen; `demoted_count`-Assertionen bleiben/ersetzen den Inhalt (AC-4-Test dort: `demoted_count == 9` statt Listen-Inhalt) |
| `tests/tdd/test_issue_429_channel_layouts.py` | MODIFY | `layout.detail_metrics`-Assertionen (Z. 280, 306, 313, 318) entfernen/durch `demoted_count`-Prüfung ersetzen |
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | `_telegram_cells()`/`_kaskade_telegram_cells()`-Helfer (Z. 262-264, 871-873, genutzt u. a. Z. 1392-1397) von `table_columns + detail_metrics` auf die tatsächliche Kanal-Auswahl (`dc.get_metrics_for_channel("telegram", report_type)`, gefiltert auf `enabled`) umstellen — der Test prüft Kaskaden-Auswahl, nicht Sichtbarkeit (das hält der Kommentar Z. 798-807 bereits fest) |
| `tests/tdd/test_felt_night_catalog_exclusions.py` | MODIFY | `detail_metrics`-Hälfte der Assertion (Z. 122-126) entfernen; `table_columns`-Hälfte bleibt und beweist denselben Sachverhalt (Gate-Filter wirkt vor der Primary/Secondary-Aufteilung, `channel_layout.py:107`) |
| `tests/tdd/test_temp_tagesrichtung_aufloesung.py` | MODIFY | `detail_metrics`-Hälfte der Assertionen (Z. 396, 421-425) entfernen, gleiche Begründung |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | MODIFY | `applyChannel()` (Z. 393-405) und lokale `ChannelLayout`-Schnittstelle (Z. 379-383) entfernen — 0 Produktiv-Aufrufer (geprüft gegen `WeatherMetricsTab.svelte`-Importliste); `buildBucketSummary`/`BucketSummary` unverändert, produktiv genutzt |
| `frontend/src/lib/components/trip-detail/metricsEditor.test.ts` | MODIFY | AC-1/AC-2/AC-3-Testblöcke für `applyChannel` (Z. ~541-616) löschen; AC-4-Block (`buildBucketSummary`) unverändert |

## Known Non-Changes (bewusst nicht angefasst)

- `channel_layout.py:119-120` (SMS-Zweig `limit == 0`) bleibt strukturell unerreichbar
  (kein Renderer betritt ihn, `sms_trip.py` importiert das Modul nicht) — Aufräumen ist ein
  eigenes, kleineres Ticket, kein Bestandteil von #1741.
- `SavePresetDialog.svelte:205-213` zeigt weiterhin dauerhaft „0 Detail" (weil `secondary`
  seit 2026-06-06 immer leer ist) — das ist eine Folge des PO-Entscheids von #587, kein Bug
  dieses Tickets.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer Architektur-Entscheidungspunkt (Kanal, Provider, Datenmodell,
  Auth, Editor-Paradigma) — reiner Bugfix + Code-Sharing zwischen zwei bestehenden
  Renderern nach der bereits etablierten Trip/Compare-Teilungs-Vorgabe (`CLAUDE.md`).

## Changelog

- 2026-08-21: Initial spec created (Issue #1741)
