---
entity_id: feat_1848_c_waechter_gehzeit_trip_exklusiv
type: module
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [metrik-register, ortsvergleich, waechter, 1848]
---

# #1848 Scheibe C — Die vier Gehzeit-Größen bleiben trip-exklusiv (Wächter)

## Approval

- [x] Approved — PO (Henning), 2026-08-19, „freigabe"

## Purpose

Der PO hat am 2026-08-19 entschieden, dass die vier Gehzeit-Größen dem Trip vorbehalten bleiben und
im Ortsvergleich **nie** angeboten werden. Diese Scheibe macht den Entscheid maschinell haltbar:
Heute hält die Unterscheidung nur, weil niemand sie verletzt hat — kein Test bewacht sie. Zusätzlich
werden drei Aussagen im Code richtiggestellt, die durch den Entscheid überholt oder schon vorher
falsch waren.

Betroffene Kennungen: `temperature_day_low`, `temperature_day_high`, `wind_chill_day_low`,
`wind_chill_day_high`.

## Warum das nötig ist — die gemessene Lücke

`tests/unit/test_compare_catalog_derives_from_central_catalog.py` führt die vier Kennungen in der
Ausnahmeliste `CENTRAL_METRICS_COVERED_ELSEWHERE` (`:44-82`). Diese Liste wird an **genau einer**
Stelle verwendet — sie wird von der Prüfmenge **abgezogen** (`:130`).

Für diese vier ist die Zusicherung „hat keinen Ortsvergleich-Eintrag" damit **trivial wahr**: sie
sind aus der Prüfung herausgenommen. Bekäme eine der vier morgen einen Ortsvergleich-Eintrag, würde
**kein Test rot**; die Ausnahme würde stillschweigend zur Lüge, und die fachliche Unterscheidung
zwischen Gehzeit-Fensterung und konfiguriertem Tagesfenster wäre still verloren.

**Beleg, dass hier wirklich etwas fehlt (Asymmetrie):** Die Schwesterliste
`AGGREGATION_CHECK_EXEMPTIONS` in derselben Datei wird sehr wohl bewacht —
`test_aggregation_exemptions_only_shrink` (`:317`) prüft auf veraltete und auf behobene Einträge,
`test_aggregation_check_exemptions_empty_after_1391_1392_fix` (`:305`) nagelt fest, dass sie leer
ist. Für `CENTRAL_METRICS_COVERED_ELSEWHERE` existiert nichts davon.

## Ist-Stand vor der Arbeit (nachgemessen, nicht angenommen)

| Prüfung | Ergebnis |
|---|---|
| Kommen die vier im Ortsvergleich-Katalog vor? | **Nein** — 0 Treffer in `compare_metric_catalog.py`, `compare_metric_ids.py`, `compare_outlook_metric_ids.py` |
| Positivkontrolle desselben Suchmusters | `temp_min_c` wird gefunden ⇒ der Suchweg trägt |
| Tragen alle vier „(Gehzeit)" im `label_de`? | **Ja** — `metric_catalog.py:173,190,260,271` |
| Stundenverlauf-Ausschluss vorhanden? | **Ja** — `compare_hourly_metric_ids.py:59-64` |

**Die Invariante hält heute. Der Wächter ist vorbeugend, nicht korrigierend.** Das ist ausdrücklich
so vermerkt, damit niemand die Scheibe später als Fehlerbehebung liest.

## Source

- **File:** `tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py` (neu)
- **Identifier:** Wächter-Modul, keine Produktivschnittstelle

Schicht: **Python-Core** (`src/app`, `src/output/renderers`, `api/`) plus Kern-Testschicht.
Kein Frontend-Anteil, kein Go-Anteil — nachgemessen, siehe „Abgrenzung".

## Estimated Scope

- **LoC:** ~+200 / −15 (davon ~180 Test)
- **Files:** 4 (1 neu, 3 geändert)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `src/app/metric_catalog.py` | liest | Quelle der vier Kennungen samt `label_de` |
| `src/output/renderers/compare_metric_catalog.py` | liest | `get_compare_metric_catalog()` — Tür 1 |
| `src/output/renderers/compare_hourly_metric_ids.py` | liest | `HOURLY_EXCLUDED_METRIC_IDS` — Tür 2 |
| `src/output/renderers/compare_outlook_metric_ids.py` | liest | 3-Tages-Ausblick — Tür 3 |
| #1468 (`feat-1468-onset-verschiebung`) | Reihenfolge | Geht **zuerst**; fügt additiv zwei Register-Einträge hinzu |

## Implementation Details

```
Der Wächter zielt auf VIER NAMENTLICH GENANNTE Kennungen — nie auf ein Namensmuster
(kein "alles mit _day_"). Grund: #1468 fügt additiv Register-Eintraege hinzu; ein
Musterwaechter wuerde davon rot, ein Namenswaechter nicht.

Tuer 1  get_compare_metric_catalog()      -> keine der vier als metric_id
Tuer 2  HOURLY_EXCLUDED_METRIC_IDS        -> alle vier ENTHALTEN (Ausschluss ist Soll)
Tuer 3  Ausblick-Kennungen                -> keine der vier waehlbar

Positivkontrolle je Tuer: derselbe Suchweg muss eine Kennung finden, die dort
vorkommen MUSS (Tuer 1: temperature ueber temp_min_c). Ohne sie waere der Test
auch gruen, wenn er am falschen Ort sucht.

Mutations-Gegenprobe im Test selbst (Muster des bestehenden Drift-Waechters,
:428/:463): eine KOPIE des Katalogs bekommt kuenstlich einen Eintrag mit
metric_id="temperature_day_low"; der Waechter MUSS darauf anschlagen. Nie werden
die echten Katalog-Listen veraendert.
```

## Expected Behavior

- **Input:** keiner — reiner Kern-Test ohne Netz, ohne Mock, ohne Datei-I/O am Prüfling
- **Output:** grün, solange die vier Kennungen trip-exklusiv bleiben
- **Side effects:** keine. **Kein Produktivcode-Verhalten ändert sich** — die drei Änderungen an
  `src/`/`api/` sind ausschließlich Kommentare und Docstrings. Erwartete Wirkung auf jede Ausgabe
  (Mail, SMS, Telegram, Premium-SMS, Oberfläche): **keine**.

## Acceptance Criteria

- **AC-1:** Given der Ortsvergleich-Katalog wird geladen / When geprüft wird, ob eine der vier
  Gehzeit-Kennungen als `metric_id` eines Eintrags vorkommt / Then trägt kein einziger Eintrag eine
  von ihnen, und der Wächter benennt bei Verstoß die betroffene Kennung im Fehlertext.
  - Test: Gegenprobe an einer **Kopie** des Katalogs, der künstlich ein Eintrag mit
    `metric_id="temperature_day_low"` hinzugefügt wird — der Wächter muss anschlagen und den Namen
    nennen. Ohne diese Gegenprobe wäre nicht bewiesen, dass er überhaupt etwas prüft.

- **AC-2:** Given derselbe Suchweg, mit dem AC-1 die Abwesenheit feststellt / When er auf eine
  Kennung angewendet wird, die im Ortsvergleich vorkommen MUSS (`temperature` über den Eintrag
  `temp_min_c`) / Then findet er sie.
  - Test: Positivkontrolle im selben Testlauf. Sie ist der Beweis, dass das Grün von AC-1 aus
    Abwesenheit stammt und nicht daraus, dass am falschen Ort gesucht wurde.

- **AC-3:** Given es gibt drei Wege, auf denen eine Kennung in die Ortsvergleich-Auswahl gerät
  (Katalog, Stundenverlauf, 3-Tages-Ausblick) / When der Wächter läuft / Then deckt er alle drei ab,
  und für den Stundenverlauf sichert er zu, dass die vier in `HOURLY_EXCLUDED_METRIC_IDS`
  **enthalten** sind.
  - Test: je Tür eine eigene Zusicherung mit eigener Gegenprobe. Ein Wächter, der nur den Katalog
    prüft, ließe zwei Türen offen.

- **AC-4:** Given der Zusatz „(Gehzeit)" ist laut PO-Entscheid tragend und nicht kosmetisch / When
  eine der vier Registerdefinitionen ihren `label_de` verliert oder den Zusatz einbüßt / Then wird
  der Wächter rot.
  - Test: Zusicherung gegen `MetricDefinition.label_de` — also gegen **Daten**, nicht gegen
    Fließtext. Gegenprobe an einer Kopie mit entferntem Zusatz.

- **AC-5:** Given Kommentare in `src/app/metric_catalog.py` nennen Funktionsnamen / When ein
  genannter Name im Code nicht auflösbar ist / Then wird der Wächter rot und nennt den toten Namen.
  - Test: Der heutige Bestand enthält genau so einen Fall — `_collect_hiking_window_dps()` existiert
    nicht, die Funktion heißt `collect_hiking_window_points()`
    (`src/output/renderers/day_window.py:186`). Der Wächter muss ihn **vor** der Korrektur melden
    und danach schweigen. **Dieser Test ist ein Doku-Konformitätstest und wird als
    `# doc-compliance-test` markiert** — er liest Quelltext und ist ausdrücklich kein
    Verhaltensnachweis. Auflösung laufzeitbasiert nach Muster #1466
    (`tests/test_guard_findings_survive_line_shifts.py`), **nicht** über feste Zeilennummern.

- **AC-6:** Given drei Aussagen im Bestand sind überholt / When sie nach dieser Scheibe gelesen
  werden / Then geben sie den Stand vom 2026-08-19 wieder:
  (a) der Rückbaupfad-Blockkommentar
  (`test_compare_catalog_derives_from_central_catalog.py:72-78`) sagt nicht mehr, die vier Zeilen
  fielen mit #1848 ersatzlos weg, sondern dass sie trip-exklusiv bleiben;
  (b) die vier Einzelvermerke `Rueckbau mit #1848` (`:79-82`) ebenso — der Blockkommentar allein
  genügt nicht;
  (c) der Docstring von `GET /api/compare/metrics` (`api/routers/compare.py:13-19`) behauptet nicht
  mehr, das Frontend konsumiere den Endpoint nicht.
  - Test: für (c) reicht der Auflösungs-Wächter aus AC-5 nicht; hier genügt die Sichtprüfung im
    Review, weil die Aussage keine maschinell prüfbare Zusicherung trägt. **Als solche benannt statt
    mit einem Scheinwächter überdeckt.**

- **AC-7:** Given #1468 fügt dem Register additiv zwei neue Einträge und eine Aggregationsart
  `onset` hinzu / When dieser Wächter auf dem Stand nach #1468 läuft / Then bleibt er grün.
  - Test: Der Wächter nennt die vier Kennungen namentlich und leitet nichts aus einem Namensmuster
    ab. Nachweis: ein künstlich hinzugefügter Register-Eintrag mit `_day_` im Namen macht den
    Wächter **nicht** rot.

## Known Limitations

- Der Wächter schützt gegen **Hinzufügen** der vier Kennungen zum Ortsvergleich. Er schützt nicht
  gegen eine Umbenennung der Kennungen selbst — dann zielt er ins Leere. Bewusst nicht adressiert,
  weil eine Umbenennung ohnehin breit rot wird.
- AC-5 prüft Namen, die wie Funktionsaufrufe geschrieben sind (`name()`). Ein Kommentar, der eine
  Funktion in Prosa ohne Klammern nennt, wird nicht erfasst.
- AC-6 (c) ist nicht maschinell bewacht (siehe dort).
- **Tür 3 (3-Tages-Ausblick) ist nur als Nebeneffekt geschützt.** Die vier Kennungen sind dort
  unauflösbar, weil sie keine `summary_fields` tragen — nicht, weil der Ausblick sie namentlich
  ausschlösse. Der Wächter sichert diesen Zusammenhang nicht zu: entfernt jemand die Katalogprüfung
  im Ausblick, bleibt er grün. Adversary-Befund vom 2026-08-19, Stufe LOW.
  **Nachtrag Adversary-Runde 2:** Die Grenze ist **weiter** als hier zunächst beschrieben — der
  Schutz steht auf zwei Beinen (Katalogprüfung **und** `_summary_field`-Prüfung), und **jedes von
  beiden ist einzeln entfernbar**, ohne dass ein Test rot wird. Der ursprüngliche Wortlaut nannte
  nur das Katalog-Bein und hat damit untertrieben.
- **Die Ableitung bewacht sich nicht selbst.** Die erwartete Menge wird aus dem Register abgeleitet
  (alle `label_de` mit `(Gehzeit)`) und gegen das Literal im Wächter geprüft — das fängt jede
  *einseitige* Änderung. Wer jedoch **drei Stellen im Einklang** ändert (Zusatz aus einem `label_de`
  entfernen, Literal schrumpfen, Erwartungsliste der Gegenprobe mitziehen), macht eine Kennung
  unbewacht, ohne dass etwas rot wird. Bewusst als Grenze benannt, nicht als Fehler behandelt: drei
  abgestimmte Änderungen sind ein gewollter Rückbau, kein Versehen. Adversary-Runde 2 vom
  2026-08-19, Stufe LOW.
- **Eine Umgehung im Frontend-Code selbst fällt nicht auf.** Der Wächter deckt die Python-Seite ab
  (Katalog, Register, Endpoint-Antwort). Eine Gehzeit-Größe, die fest in `buildCompareMetricDefs()`
  (`frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts`) eingetragen
  wird, erreicht die Bedienfläche am geprüften Weg vorbei. Adversary-Befund vom 2026-08-19,
  Stufe LOW.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der fachliche Entscheid (Gehzeit-Größen bleiben trip-exklusiv) ist im Issue #1848
  dokumentiert und PO-bestätigt; diese Scheibe setzt ihn nur durch und trifft keine eigene
  Richtungsentscheidung. Kein neues Vokabular, kein neues Datenformat, keine Kanal- oder
  Persistenz-Änderung.

## Abgrenzung

- **Nicht enthalten:** die Auditfrage aus dem Issue-Kommentar vom 2026-08-15 („welche weiteren ‚Am
  Code gemessen'-Feststellungen hängen an aufgehobenen Voraussetzungen?"). Gemessener Umfang: 18
  Spec-Dateien nennen `metrics=None`, 4 tragen eine „compare-exklusiv"-Zusage. Offenes Ergebnis,
  kann PO-Entscheide auslösen — eigene Scheibe, beim Intake am 2026-08-19 abgetrennt.
- **Kein eigener Frontend-Wächter nötig:** nachgemessen, dass die Auswahl-Oberfläche den
  Python-Katalog über den Endpoint bezieht
  (`frontend/.../corridor-editor/compareMetricCatalogLoader.ts:101` →
  `GET /api/compare/metrics` → `get_compare_metric_catalog()`).

## Changelog

- 2026-08-19: Initial spec created (#1848 Scheibe C)
