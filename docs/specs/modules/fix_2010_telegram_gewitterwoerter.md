---
entity_id: fix_2010_telegram_gewitterwoerter
type: bugfix
created: 2026-08-22
updated: 2026-08-22
status: draft
version: "1.0"
tags: [telegram, thunder, output, ssot]
---

# Telegram nennt Gewitterstufen wie der Rest: "mittel" statt "mäßig", "kein" statt "keins" (#2010)

## Approval

- [ ] Approved

## Purpose

Der Telegram-Kanal beschriftet zwei der vier Gewitterstufen mit anderen
Wörtern als die kanonische Quelle `THUNDER_LABEL_DE`: `MED` heißt dort
"mäßig" statt "mittel", `NONE` heißt "keins" statt "kein". Wer dieselbe Lage
über zwei Kanäle liest (auf dem Pass Telegram, im Tal die E-Mail), sieht zwei
verschiedene Wörter für denselben Zustand. Ursache sind drei unabhängig
gepflegte lokale Kopien der Stufenskala in `trip_command_processor.py`, von
denen keine `THUNDER_LABEL_DE` liest.

Diese Spec saniert diese drei Kopien: das **Wort** kommt künftig
ausschließlich aus `THUNDER_LABEL_DE`; die Telegram-eigene Kreis-Darstellung
(Emoji) bleibt unverändert lokal, weil sie keine Wortskala ist.

## Source

- **File:** `src/services/trip_command_processor.py` (Python-Core)
- **Identifier:** `_THUNDER_LABEL` (:139), `_thunder_fmt` mit `_MAP_EMOJI`/`_MAP_PLAIN` (:215-232),
  `_handle_hours_drilldown` (:808-817)
- **Kanonische Quelle:** `THUNDER_LABEL_DE` in `src/output/metric_format.py:283-288`

## Estimated Scope

- **LoC:** ~40 (Quelle) + Tests
- **Files:** 2 produktiv (`trip_command_processor.py`, `tests/tdd/test_thunder_scale_local_copy_guard.py`
  — dort nur Streichung von vier Basislinien-Zeilen) + 1 neue Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.metric_format.THUNDER_LABEL_DE` | Modul-Konstante | Einzige Wortquelle der Stufenskala |
| `app.thunder_scale.ThunderLevel` | Enum | Stufen NONE/LOW/MED/HIGH |
| `tests/tdd/test_thunder_scale_local_copy_guard.py` | Wächter (#1480) | Führt die vier Fundstellen als `Altlast` mit `tracking="#2010"` |

## Implementation Details

```
Eine Anzeige-Karte statt drei Kopien. Wort delegiert, Emoji lokal:

    _THUNDER_ANZEIGE = {
        "NONE": ("⚪", THUNDER_LABEL_DE[ThunderLevel.NONE]),
        "LOW":  ("🟢", THUNDER_LABEL_DE[ThunderLevel.LOW]),
        "MED":  ("🟡", THUNDER_LABEL_DE[ThunderLevel.MED]),
        "HIGH": ("🔴", THUNDER_LABEL_DE[ThunderLevel.HIGH]),
    }

- `_thunder_fmt(value, with_emoji=...)` liest daraus: mit Emoji
  "<emoji> <wort>", ohne Emoji nur "<wort>". Fallback für None/unbekannt
  bleibt wörtlich "· keine Daten".
- Die drei `_THUNDER_LABEL.get(...)`-Aufrufe (Tagesglance, Drilldown-Kopf,
  Timeline) ziehen das Wort aus derselben Karte; Fallback bleibt "?".
- `_handle_hours_drilldown` verliert seine if/elif-Kette auf rohe
  Stufen-Strings und liest ebenfalls die Karte: NONE bleibt "—",
  sonst Emoji (Telegram) bzw. Wort (E-Mail/SMS).

Warum das keine vierte Kopie ist: jeder Wert der Karte enthält einen
`THUNDER_LABEL_DE[...]`-Zugriff. Ändert sich die Quelle, ändert sich die
Telegram-Ausgabe mit — nachgewiesen per Laufzeit-Mutation (AC-4), nicht per
Dateiinhalt-Check.
```

## Expected Behavior

- **Input:** `ThunderLevel`-Wert (Enum oder String nach JSON-Roundtrip) in
  Telegram-Kommandos `/heute`, `/morgen`, Gewitter-Drilldown, Stundentabelle.
- **Output:** deutsches Stufenwort aus `THUNDER_LABEL_DE`
  (kein/leicht/mittel/hoch), für Telegram mit vorangestelltem Kreis-Emoji.
- **Side effects:** keine — reine Beschriftung.

## Abgrenzung

- **Emoji-Zuordnung bleibt wie sie ist** (`⚪`/`🟢`/`🟡`/`🔴`). Dass sie nicht
  dem Ampelband aus `thunder_ampel_band()` folgt (dort ist NONE grün, LOW
  gelb), ist eine eigene Frage und **nicht** Teil dieses Issues — eine
  Angleichung wäre eine sichtbare Änderung über die Wortdrift hinaus.
- `weather_metrics.format_wind_strength` / `format_precip_intensity` behalten
  "mäßig" — dort beschreibt das Wort **Wind-/Niederschlagsstärke**, nicht die
  Gewitterskala. Nicht anfassen.
- Der Wächter aus #1480 wird nicht erweitert; er verliert nur seine vier
  `#2010`-Basislinien-Zeilen.

## Acceptance Criteria

- **AC-1:** Given eine Telegram-Ausgabe mit Gewitterstufe `MED` / When der
  Nutzer sie über `/heute`, den Gewitter-Drilldown oder die Stundentabelle
  (Kanal E-Mail/SMS, also Wort statt Emoji) abruft / Then steht dort das Wort
  `THUNDER_LABEL_DE[ThunderLevel.MED]` ("mittel") und nirgends "mäßig".
  - Test: Kommando-Verarbeitung mit echtem `MED`-Wetterdatensatz aufrufen,
    `confirmation_body` prüfen — Sollwort aus `THUNDER_LABEL_DE` gezogen.

- **AC-2:** Given eine Telegram-Ausgabe mit Gewitterstufe `NONE` / When der
  Nutzer sie abruft / Then steht dort `THUNDER_LABEL_DE[ThunderLevel.NONE]`
  ("kein") und nirgends "keins".
  - Test: wie AC-1 mit `NONE`; zusätzlich `_thunder_fmt` mit und ohne Emoji.

- **AC-3:** Given dieselbe Gewitterstufe / When sie einmal über Telegram und
  einmal über den E-Mail-Pfad beschriftet wird / Then ist das **Wort**
  identisch — für alle vier Stufen NONE/LOW/MED/HIGH.
  - Test: parametrisiert über alle vier `ThunderLevel`; verglichen wird gegen
    `THUNDER_LABEL_DE`, nicht gegen eingetippte Literale.

- **AC-4:** Given `THUNDER_LABEL_DE` wird zur Laufzeit auf einen
  Marker-Wert gesetzt / When die Telegram-Ausgabe erzeugt wird / Then trägt
  sie den Marker — die Telegram-Seite leitet ihre Wörter also wirklich ab und
  hält keine eigene Kopie.
  - Test: Mutations-Gegenprobe wie `test_alert_stufenwort.py:356-396`
    (Dict-Inhalt in place mutieren, im `finally` zurücksetzen).

- **AC-5:** Given Telegram als Kanal / When eine Ausgabe mit Emoji erzeugt
  wird / Then bleiben Kreis-Emojis und ihre Zuordnung unverändert
  (`NONE ⚪`, `LOW 🟢`, `MED 🟡`, `HIGH 🔴`), und die Stundentabelle zeigt für
  `NONE` weiterhin "—" statt eines Kreises.
  - Test: `_thunder_fmt(..., with_emoji=True)` je Stufe + Stundentabelle mit
    `NONE`-Stunde.

- **AC-6:** Given der Wächter-Test aus #1480 / When er nach der Sanierung
  läuft / Then ist er grün, ohne dass ein neuer `Altlast`-Eintrag entstanden
  ist — die vier Einträge mit `tracking="#2010"` sind gestrichen.
  - Test: `tests/tdd/test_thunder_scale_local_copy_guard.py` (bestehend,
    Mengengleichheit über beide Richtungen).

- **AC-7:** Given ein fehlender oder unbekannter Gewitterwert / When die
  Ausgabe erzeugt wird / Then bleiben die bisherigen Fehlanzeigen unverändert
  ("· keine Daten" in `_thunder_fmt`, "?" an den drei Label-Abrufen).
  - Test: `None` und ein unbekannter String je Pfad.

## Known Limitations

- Bestandsnachrichten, die Nutzer bereits im Telegram-Verlauf haben, tragen
  weiter die alten Wörter — Telegram-Nachrichten werden nicht rückwirkend
  bearbeitet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein Entscheidungswechsel — die Regel "eine Wortquelle für
  die Gewitterskala" steht seit #1474/#1480 fest; diese Spec zieht drei
  Nachzügler nach.

## Changelog

- 2026-08-22: Initial spec created (#2010)
