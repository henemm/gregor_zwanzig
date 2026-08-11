---
entity_id: fix_1703_s2_ausblick_matrix
type: module
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [metrics, outlook, compare, matrix-test, epic-1703, aggregation]
---

<!-- Epic #1703 (Folgearbeit aus #1514), Scheibe 2. Deckt Flaeche 2 aus
     docs/reference/metric_output_matrix.md §4.1. Voraussetzung Scheibe 3
     (PR #1710) erledigt; Scheibe 1 (PR #1732) erledigt. -->

# Ausblick-Tabelle × alle wählbaren Vergleichs-Metriken (#1703 Scheibe 2)

## Approval

- [ ] Approved — ACs auf Deutsch vorgelegt, PO-Freigabe ausstehend.
  Mitfreizugeben: (a) Zuschnitt **Compare-only** statt „Trip + Compare" (s. Purpose),
  (b) Produktivfix an `summarize_points()` in dieser Scheibe (s. AC-4/AC-5),
  (c) `loc_limit_override 600`.

## Purpose

Der 3-Tages-Ausblick des Ortsvergleichs ist datengetrieben: der Nutzer wählt aus **25**
Größe×Auswertung-Paaren, welche Spalten die Tabelle zeigt. Bewacht ist heute nur das
Auswahl-*Prinzip* — `tests/tdd/test_compare_outlook_metric_selection.py` prüft mit **zwei**
fest getippten Auswahlen, dass nur Gewähltes erscheint. Die **Katalog-Deckung** ist
unbewacht: 2 von 25 Paaren sind je durch den Renderer gelaufen.

Diese Scheibe hängt eine Matrix-Achse in den bestehenden, budgetierten Wächter
`tests/tdd/test_channel_metric_matrix.py` (#1677 B) — und repariert dabei einen gemessenen,
nutzersichtbaren Defekt: **fünf der 25 wählbaren Spalten sind dauerhaft leer.**

### Korrektur der Scheiben-Prämisse: Compare-only

Issue-Text und `metric_output_matrix.md:74/94` sagen, `outlook_columns()` speise „beide
Mail-Familien". **Gemessen ist das falsch.** Von den sechs Aufrufstellen des geteilten
Renderers übergeben die drei Trip-Stellen (`email/html.py:1357`, `email/plain.py:338`,
`trip_report_scheduler.py:1844`) **kein** `metrics`-Argument; sie laufen im festen
Legacy-Spaltenpfad. Nur der Ortsvergleich (`comparison.py:348`, `compare_html.py:1101`
und `:1175`) ist katalog-getrieben.

Der Trip-Ausblick hat also keine wählbaren Spalten und damit **keine Metrik×Kanal-Fläche**.
Ein Abdeckungs-Wächter dafür wäre zudem *schwächer* als der Bestand: `test_trip_outlook_parity.py`
vergleicht das gesamte Ausblick-HTML **und** den Klartext byte-genau gegen
`tests/fixtures/outlook_trip_parity/`. Jede stille Erweiterung oder Beschneidung ist dort
bereits rot. Eine zweite Prüfung desselben Sachverhalts wäre Regel-Zuwachs ohne Fang
(Regel-Budget). Deshalb: **Compare-only, mit Begründung, statt stillem Weglassen.**

## Source

- **File:** `src/output/renderers/compare_outlook_metric_ids.py` (Prüfling),
  `src/services/weather_metrics.py` (Fix), `tests/tdd/test_channel_metric_matrix.py` (Wächter)
- **Identifier:** `outlook_columns:78` · `format_outlook_value:117` ·
  `summarize_points:1071` · `compute_extended_metrics:752-771`

Schicht: **Python-Core** (`src/output/renderers/`, `src/services/`). Keine Go-, keine
Frontend-Berührung.

## Estimated Scope

- **LoC:** ~300 zählend (Test-Achse ~200, Helfer ~70, Produktivcode ~10, Anpassung roter
  Bestandstests ~20; `docs/` zählt nicht)
- **Files:** 5
- **Effort:** medium

> **LoC-Limit:** Die Schätzung liegt über 250. Bei Scheibe 1 lag sie um Faktor 2,75
> daneben; deshalb wird die Freigabe für `loc_limit_override 600` **vorab** zusammen mit
> dieser Spec eingeholt statt später als Prozess-Unterbrechung.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/output/renderers/compare_metric_catalog.py` | Katalog | `get_compare_metric_catalog()` — **die Soll-Mengen-Quelle** |
| `src/app/metric_catalog.py` | Katalog | `summary_field_for()` — zweite Auflösungsbedingung |
| `src/app/models.py` | Datentypen | `SegmentWeatherSummary`, `ThunderLevel`, `PrecipType` |
| `src/services/weather_metrics.py` | Produktivmodul | beide Tages-Aggregationspfade |
| `src/output/renderers/comparison.py` | Renderpfad | `render_compare_email()` — liefert HTML **und** Klartext |
| `tests/tdd/test_channel_metric_matrix.py` | Wächter (Bestand) | Zieldatei, wird erweitert |
| `tests/helpers/hourly_columns.py` | Vorbild | Muster „Soll rechnen, nicht tippen" + Vakuum-Schutz |
| `tests/tdd/test_compare_outlook_metric_selection.py` | Abgrenzung | prüft das Prinzip, nicht die Deckung |

## Implementation Details

### Die Soll-Menge (gemessen 2026-08-11, nicht getippt)

```
# Quelle: das Produktivmodul selbst, nicht der Test.
COMPARE_METRIC_CATALOG          -> 26 rohe Eintraege
get_compare_metric_catalog()    -> 25 ausgeliefert
Differenz                       -> cape_max_jkg (cape.selectable=False seit #1585)
```

Alle 25 Paare überstehen **beide** Auflösungsbedingungen (`key_for()` und
`summary_field_for()`); `resolve_outlook_metrics()` verwirft keines, `outlook_columns()`
liefert 25 Spalten. Formzweige: genau 1× `ordinal` (Gewitter), 1× `enum`
(Niederschlagsart), 23× `range`.

### Der gemessene Defekt (AC-4)

Echte Vergleichs-Mail mit allen 25 Paaren und reich besetzten Stundenpunkten:
**20 Zellen tragen einen Wert, 5 tragen das Fehlzeichen** — in HTML und Klartext, an
jedem der drei Ausblickstage:

| Spalte | Summary-Feld | im Stundenpunkt vorhanden |
|---|---|---|
| Schneehöhe | `snow_depth_cm` | `snow_depth_cm` |
| Neuschnee | `snow_new_sum_cm` | `snow_new_24h_cm` |
| Windrichtung | `wind_direction_avg_deg` | `wind_direction_deg` |
| Gefühlte Temperatur Minimum | `wind_chill_min_c` | `wind_chill_c` |
| Gefühlte Temperatur Maximum | `wind_chill_max_c` | `wind_chill_c` |

**Ursache:** `summarize_points()` (`weather_metrics.py:1071`) ist eine handgepflegte
Aufzählung — `compute_basis_metrics()` plus elf namentlich verdrahtete `_compute_*`-Regeln
(`:1097-1111`). Die fünf Regeln für obige Felder existieren
(`_compute_snow_depth:887`, `_compute_fresh_snow:964`, `_compute_wind_direction:969`,
`_compute_wind_chill:872`, `_compute_wind_chill_max:879`) und sind im **Trip**-Pfad
`compute_extended_metrics()` (`:752-760`) angeschlossen — im Vergleichspfad nie.

Gegengemessen, dass der Fix trägt: auf dem Compare-Eingang liefern alle fünf korrekte
Werte (30.0 · 16.0 · 210 · 5.0 · 23.0).

**Kein dokumentierter Vorsatz.** Der Kommentar `:763-765` hält die *spiegelbildliche*
Lücke fest (#1391: Schneefallgrenze fehlte im Trip-Pfad, obwohl der Vergleich sie setzte).
#1324 und #1392 sind weitere Flicken an derselben Naht — zwei Listen, die deckungsgleich
bleiben müssten und dreimal auseinandergelaufen sind. Deshalb AC-5.

### Die Fehlzeichen-Falle (AC-4)

Zwei verschiedene Striche, die im Terminal gleich aussehen:

| Zeichen | Bedeutung | Quelle |
|---|---|---|
| `–` (U+2013) | **Wert fehlt** | `format_outlook_value(None, …)` |
| `—` (U+2014) | Gewitterstufe „keine" / Niederschlagsart unbekannt | `_fmt_thunder`/`_fmt_precip_type` |

Ein Wächter, der auf „irgendein Strich" prüft, hielte eine gültige Gewitter-Zelle
fälschlich für einen Fehler — und ein Wächter, der beide gleichsetzt, übersähe den echten
Fehlwert. AC-4 unterscheidet sie ausdrücklich.

### Ausnahme-Muster

Keine Ausnahmeliste nötig: Die Soll-Menge kommt aus `get_compare_metric_catalog()`, das
nicht-wählbare Größen bereits selbst herausfiltert. Damit erbt der Wächter die
Katalog-Entscheidung, statt sie zu kopieren (Muster aus Scheibe 3: Ausnahmen nie zweimal
führen).

## Expected Behavior

Nach dieser Scheibe gilt: Wählt ein Nutzer eine beliebige der 25 Größen für den
3-Tages-Ausblick des Ortsvergleichs, erscheint eine Spalte mit eindeutigem Kopf, und die
Zelle zeigt den Tageswert, sobald die Stundendaten ihn hergeben — in HTML wie im Klartext.
Fällt künftig eine Größe aus einem der beiden Tages-Aggregationspfade heraus, wird das
bemerkt, statt still eine Strichspalte zu erzeugen.

## Acceptance Criteria

- **AC-1:** Gegeben ein Nutzer wählt alle im Vergleich wählbaren Ausblick-Größen, wenn die
  Vergleichs-Mail erzeugt wird, dann trägt der Ausblick für **jede** dieser Größen genau
  eine Spalte — in der HTML-Tabelle **und** in der Klartext-Fassung derselben Mail.
  - Test: Soll-Menge aus `get_compare_metric_catalog()` gerechnet; eine echte Mail über
    `render_compare_email()` (ein Aufruf liefert beide Formen); Kopfzeile aus dem HTML und
    die Klartext-Zeile werden gegen dieselbe Soll-Menge gehalten. Keine Größe darf im
    Klartext fehlen, die im HTML steht — und umgekehrt.

- **AC-2:** Gegeben der Wächter läuft, wenn die Menge der zu prüfenden Größen bestimmt
  wird, dann stammt sie ausschließlich aus dem Vergleichs-Katalog und ist niemals im Test
  aufgezählt.
  - Test: ein Plausibilitäts-Wächter schlägt fehl, wenn die Menge leer ist, unter 20
    Einträge fällt, oder die Rechnung „roh minus nicht-wählbar = ausgeliefert" nicht
    aufgeht (Vakuum-Schutz nach `hourly_columns.py:130-158`). Ein Wächter, der über eine
    leere Menge iteriert, ist immer grün und bewacht nichts.

- **AC-3:** Gegeben alle Größen sind gewählt, wenn die Spaltenköpfe erzeugt werden, dann
  trägt keine zwei Spalten dieselbe Beschriftung.
  - Test: die Köpfe der echten Mail werden auf Dubletten geprüft. Heute erfüllt, weil die
    Auswertung angehängt wird, sobald dieselbe Größe mehrfach vorkommt
    („Temperatur Maximum"/„Temperatur Minimum", „Gefühlte Temperatur Minimum"/„Maximum").
    Bricht diese Logik, entstünden zwei ununterscheidbare Spalten.

- **AC-4:** Gegeben die Stundendaten enthalten für eine gewählte Größe Werte, wenn der
  Ausblick erzeugt wird, dann zeigt die zugehörige Zelle einen Wert und **nicht** das
  Fehlzeichen — für jede der 25 Größen.
  - Test: ein Stundendatensatz, der jedes Quellfeld besetzt; jede Zelle jeder
    Ausblickszeile wird geprüft. Das Fehlzeichen `–` (U+2013) gilt als Verstoß; das
    inhaltliche `—` (U+2014) einer Gewitterstufe „keine" ausdrücklich **nicht** — die
    beiden Striche werden unterschieden, nicht gleichgesetzt.
  - **Heute rot für fünf Größen** (Schneehöhe, Neuschnee, Windrichtung, Gefühlte
    Temperatur Minimum und Maximum) — das ist der rote Anteil dieser Scheibe.

- **AC-5:** Gegeben die beiden Tages-Aggregationspfade des Produkts (Trip und Vergleich),
  wenn sie auf demselben Stundensatz gegeneinander gehalten werden, dann füllt der
  Vergleichspfad jedes Tagesfeld, das der Trip-Pfad füllt.
  - Test: beide Pfade laufen über denselben Stundensatz; die Feldmengen werden verglichen.
    Eine Abweichung ist nur zulässig, wenn sie im Wächter namentlich als bewusste Ausnahme
    geführt ist. Damit fällt die nächste Drift auf, statt erneut als Strichspalte beim
    Nutzer zu landen — dieselbe Bauart wie die Einheiten-Prüfung aus Scheibe 1.

- **AC-6:** Gegeben der Fix an der Vergleichs-Aggregation ist eingespielt, wenn Trip-Mail
  und die bereits heute gefüllten Ausblick-Zellen erzeugt werden, dann bleiben sie
  unverändert.
  - Test: der Trip-Paritäts-Golden bleibt grün (`test_trip_outlook_parity.py`), und die 20
    heute gefüllten Zellen behalten ihre Werte. Der Fix darf nicht über sein Ziel
    hinausschießen.

- **AC-7:** Gegeben jemand entfernt eine Größe aus dem Vergleichs-Katalog, wenn die Tests
  laufen, dann fällt das auf — und der Wächter benennt, worauf er sich dabei stützt.
  - Test: Die Mindestgröße aus AC-2 greift bei größeren Streichungen; die einzelne
    Streichung fängt der unabhängige, getippte Größenanker in
    `test_compare_metric_catalog_endpoint.py:519` (`== 25`). Diese Abhängigkeit wird im
    Docstring der neuen Achse vermerkt, damit der Anker bei einer künftigen Aufräumaktion
    nicht unbemerkt als „hartcodiert, unschön" verschwindet (Lehre aus Scheibe 1, F001).

- **AC-8:** Gegeben der Fix läuft auf Staging, wenn die Vergleichs-Mail-Vorschau im
  **echten Browser** für einen Vergleich geöffnet wird, in dem eine der fünf betroffenen
  Größen für den Ausblick gewählt ist, dann zeigt die Spalte einen Wert statt des
  Fehlzeichens — und die Browser-Konsole bleibt fehlerfrei.
  - Test: Playwright gegen Staging, angemeldete Ansicht, Vorschau-Iframe geladen
    (`frontend/src/lib/components/preview/EmailIframe.svelte` rendert das hier geänderte
    HTML), Konsolenfehler und `pageerror` eingesammelt, Screenshot als Beleg.
  - **Begründung, warum das trotz Backend-Scope hierher gehört:** Der Änderungssatz
    berührt keine Datei unter `frontend/**`, die Wirkung ist aber an der Oberfläche
    sichtbar. Ein reiner Backend-Nachweis (gerenderte Mail im Test) belegt nicht, dass der
    Nutzer den Wert auch in der Vorschau sieht. Deploy-Scope trotzdem `--scope backend`
    setzen — `docs-only` wäre fail-open.

## Known Limitations

- **Zuordnung bleibt unbewacht.** Ein Wächter, der sein Soll aus demselben Katalog liest
  wie der Prüfling, sieht Fehler *in* diesem Katalog nicht: Vertauschte man Einheit oder
  Auswertung zweier Einträge, bliebe diese Achse grün. „Rechnen statt tippen" gilt für die
  Soll-**Menge**, nicht für die Soll-**Zuordnung** (Scheibe 1, Finding F001).
- **`temperature` + `avg`** ist zentral auflösbar (`temp_avg_c`), im Vergleichs-Katalog
  aber nicht vertreten. Ohne Nutzerwirkung (nicht wählbar), daher hier nur vermerkt.
- **Der Fix wirkt über den Ausblick hinaus:** `summarize_points()` speist auch die
  Vergleichs-Übersichtstabelle (`compare_html.py:627`) und die Kompakt-Zusammenfassung
  (`compact_summary.py:651`). Dort erscheinen künftig Werte, wo Striche standen — gewollt,
  aber der Umfang roter Bestandstests wird in der RED-Phase gemessen, nicht geschätzt.
- **Telegram- und Kompakt-Ausblick bleiben außen vor:** `narrow.py:571` und
  `email/compact.py:227` haben eigene Ausblick-Implementierungen, die `outlook.py` nicht
  importieren. Sie gehören zu Scheibe 4.

## Prüfhinweis für den Adversary

- Die Mutations-Gegenprobe muss **außerhalb** des Testcodes ansetzen: eine der fünf neu
  verdrahteten Zeilen in `summarize_points()` entfernen — AC-4 muss rot werden.
- Zweite Pflicht-Mutation: eine Zeile aus `compute_extended_metrics()` entfernen — AC-5
  muss rot werden (sonst prüft AC-5 nur eine Richtung).
- Dritte: die Unterscheidung der beiden Striche in AC-4 auf „irgendein Strich" verkürzen —
  ein Gewitter-Tag ohne Gewitter muss dann fälschlich rot werden. Wird er es nicht, prüft
  AC-4 die Zellen nicht wirklich.
- Leitfrage: Ist die Zusicherung an der Stelle geprüft, an der sie **wirkt** — an der
  gerenderten Mail — oder nur dort, wo der Code steht?

## Definition of Done

- [ ] AC-1 bis AC-8 grün
- [ ] Adversary-Verdict VERIFIED, alle drei Pflicht-Mutationen gefangen
- [ ] Browser-Beleg zu AC-8 im Änderungssatz (Playwright gegen Staging, angemeldete
      Ansicht, Screenshot + Konsolenprotokoll)
- [ ] `docs/reference/metric_output_matrix.md`: Fläche 2 (§4.1) auf den neuen Wächter
      umgetragen, Scheibe 2 (§6) auf erledigt, Compare-only-Korrektur vermerkt
- [ ] Issue #1703 Scheiben-Checkbox gesetzt, Ergebnis kommentiert

## Changelog

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 2026-08-11 | Erstfassung, ACs zur Freigabe vorgelegt |
