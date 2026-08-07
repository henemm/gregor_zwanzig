---
entity_id: fix_1575_mail_column_order
type: module
created: 2026-08-07
updated: 2026-08-07
status: draft
version: "1.0"
tags: [trip, output, email, weather-metrics, khw]
---

# Fix #1575 Scheibe 1 — Die eingestellte Metrik-Reihenfolge wirkt in der Briefing-Mail

## Approval

- [ ] Approved

## Purpose

Der Abschnitt „Reihenfolge" im Tab *Wetter-Metriken* verspricht wörtlich „links → rechts
in der Email-Tabelle", hat aber **keine Wirkung**: die Spaltenfolge der Briefing-Mail ist
für jeden Trip die Katalog-Reihenfolge. Diese Scheibe macht die Zusicherung für die
HTML-Briefing-Mail wahr — an der **einen** Stelle, an der die kanal-bewusste
Metrik-Auflösung ohnehin stattfindet.

## Messung (Ist-Stand, nicht vermutet)

Gemessen am 2026-08-07 gegen `9a932ef` über den echten Render-Pfad
(`TripReportFormatter.format_email`, Messskript im Session-Scratchpad):

| Fall | HTML-Spalten |
|---|---|
| `order` == Katalogreihenfolge | `Time, Temp, Feels, Wind, Gust, Rain, Thdr, SnowL, Cloud, Sun, TmpMin, Risk` |
| `order` rotiert (letzte Größe auf Position 1) | **identisch** — die Einstellung verpufft |
| `metrics`-Liste physisch nach `(bucket, order)` sortiert | `Time, **Sun**, Temp, Feels, …` — die Einstellung wirkt |

**Ursachenkette (Code gelesen und nachgemessen):**

1. Der Editor speichert die Drag-Position **nur** im Feld `order`; das `metrics`-Array
   selbst wird bewusst in Katalog-Reihenfolge serialisiert
   (`frontend/src/lib/components/trip-detail/metricsEditor.ts:329`, `:367-370`).
2. Der HTML-Renderer baut seine Spaltenfolge aus `dc.metrics` in **Array-Reihenfolge**
   und liest `mc.order` nie (`src/output/renderers/email/html.py:1018-1027`).
3. `get_metrics_for_channel()` (`src/app/models.py:700-732`) gibt die Liste unsortiert
   zurück — sie ist die einzige Stelle, die alle Kanäle durchlaufen.

Zum Vergleich: Telegram und Ortsvergleich sortieren nach `(bucket, order)`
(`src/output/renderers/channel_layout.py:89-94`) und zeigen die Einstellung korrekt.
Die Mail ist der einzige Kanal, der ausschert.

## Source

- **File:** `src/app/models.py`
- **Identifier:** `UnifiedWeatherDisplayConfig.get_metrics_for_channel`

Schicht: **Python-Core / Domain-Backend**. Bewusst **keine** Änderung an
`src/output/renderers/email/*.py` oder `trip_report.py` — siehe „Schnitt".

## Acceptance Criteria

**AC-1:** Given ein Trip, dessen Wettergrößen im Editor in eine vom Katalog abweichende
Reihenfolge gezogen wurden / When das Briefing als E-Mail gerendert wird / Then folgen
die Spalten der Stundentabelle im HTML-Teil genau dieser eingestellten Reihenfolge
(links → rechts), nicht der Katalog-Reihenfolge.

**AC-2:** Given zwei Größen im selben Bucket mit den Positionen 1 und 2 / When die beiden
Positionen im Editor getauscht werden / Then tauschen auch die zugehörigen Spalten der
Mail ihren Platz — die Wirkung ist an der Mail messbar, nicht nur am gespeicherten Wert.

**AC-3:** Given ein Bestands-Trip, dessen gespeicherte Größen alle `order = 0` tragen
(Altbestand vor der Reihenfolge-Funktion) / When das Briefing gerendert wird / Then ist
die Spaltenfolge **unverändert** gegenüber heute — die Sortierung ist stabil und erfindet
für Altbestand keine neue Reihenfolge.

**AC-4:** Given eine Konfiguration mit Größen in beiden Buckets (`primary`, `secondary`)
/ When die Mail gerendert wird / Then stehen alle `primary`-Größen (nach ihrer Position)
vor allen `secondary`-Größen — beide Buckets zählen ihre Positionen ab 0, eine Sortierung
allein nach `order` würde sie falsch verschränken.

**AC-5:** Given derselbe Trip / When Telegram-Kurzform und Ortsvergleich gerendert werden
/ Then ist deren Spalten-/Zeilenfolge unverändert gegenüber heute — diese Kanäle
sortieren bereits selbst; die neue Sortierung darf dort nichts verschieben.

**AC-6:** Given ein Trip mit kanal-eigenen Listen (`channel_layouts`, Altbestand aus
#429/#434) / When die Mail gerendert wird / Then bleibt die Auswahl (welche Größen)
unverändert; ausschließlich die Reihenfolge folgt der Einstellung.

## Nicht in dieser Scheibe (bewusst)

- **Plain-Text-Hälfte der Mail.** Gemessen: `plain.py` ordnet über
  `visible_cols(rows)` strikt nach Katalog und kennt den `col_order`-Mechanismus gar
  nicht — die Sortierung in `models.py` erreicht sie nicht. Der Fix erfordert eine
  Änderung an `src/output/renderers/email/plain.py`, und das ist eine geschützte
  Mail-Inhalts-Datei: `renderer_mail_gate.py` verlangt dafür einen frischen
  `briefing_mail_validator.py`-Lauf gegen eine **echt zugestellte Staging-Mail** per
  IMAP. Diese Session hat weder IMAP-Zugang noch Staging-Zugriff. → Folge-Scheibe für
  eine Session mit Staging-Zugang.
- **Divergenz HTML ↔ Plain (Zusatzbefund).** Schon heute unterscheiden sich beide
  Hälften: `TmpMin` steht im Plain-Teil an Position 2, im HTML-Teil an vorletzter
  Stelle. Ursache gemessen: `temperature_cold.selectable = False`, dadurch fällt die
  Größe in `html.py:1024` aus `_col_order` heraus und landet über den
  `remaining`-Zweig am Ende, während der Plain-Teil sie nach Katalog einsortiert. Das
  ist ein Trip-seitiges Geschwister von #1356 und gehört in dieselbe Folge-Scheibe.
- **Symptom B aus #1575 (Kanal-Trennung im Editor).** Eigene Spec, eigener Workflow —
  braucht eine PO-Entscheidung zum Bedienkonzept (pro Kanal eigene Auswahl vs. Reiter
  ehrlich als reine Vorschau beschriften).

## Estimated Scope

- **LoC:** ~15 Produktivcode + ~120 Test
- **Files:** 1 Produktivdatei (`src/app/models.py`), 1 Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig` | Datenmodell | trägt `bucket` + `order` je Größe |
| `channel_layout.render_for_channel` | Referenz | belegt die etablierte Sortier-Semantik `(bucket, order)` |
| `email/html.py` `_col_order` | Verbraucher | liest `dc.metrics` in Array-Reihenfolge (unverändert) |

## Implementation Details

```
UnifiedWeatherDisplayConfig.get_metrics_for_channel(channel, report_type):
    ... bestehende Dreistufen-Kaskade unverändert ...
    return _sorted_by_layout(<Ergebnis der jeweiligen Ebene>)

_sorted_by_layout(metrics):
    # primary vor secondary, innerhalb des Buckets nach order.
    # sorted() ist stabil -> Altbestand mit lauter order=0 behaelt
    # exakt seine bisherige Reihenfolge (AC-3).
    rank = {"primary": 0, "secondary": 1}
    return sorted(metrics, key=lambda m: (rank.get(m.bucket, 2), m.order))
```

Alle drei Kaskadenebenen laufen durch dieselbe Sortierung — sonst verhielte sich ein
Trip mit `channel_layouts` anders als einer ohne (AC-6).

## Testing

Kern-Schicht, deterministisch, ohne Netz. Nachweis am **Wirkort**: die gerenderte Mail
(`format_email`), nicht die Sortierfunktion isoliert — Lehre aus #1457 („ist die
Zusicherung dort geprüft, wo sie wirkt?").

| AC | Testart |
|---|---|
| AC-1, AC-2 | `format_email` mit permutiertem `order`, Spaltenfolge aus dem `<thead>` gelesen |
| AC-3 | Altbestand-Konfiguration (`order` überall 0) → Spaltenfolge identisch zum Ist-Stand |
| AC-4 | Konfiguration über beide Buckets → primary-Block vollständig vor secondary-Block |
| AC-5 | `render_for_channel("telegram", …)` und Compare-Pfad vor/nach identisch |
| AC-6 | Konfiguration mit `per_channel_layouts` → Auswahl unverändert, Reihenfolge sortiert |
