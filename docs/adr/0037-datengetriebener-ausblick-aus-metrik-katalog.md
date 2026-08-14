# ADR-0037: 3-Tages-Ausblick der Vergleichs-Mail datengetrieben aus dem Metrik-Katalog

- **Status:** Akzeptiert — **Punkt 2 abgelöst durch ADR-0055** (2026-08-14)
- **Datum:** 2026-07-27
- **Bezug:** GitHub-Issue #1361 (Befund 2), #1368, Epic #1372 (Etappe S3 Scheibe A), Dach
  #1374, Spec `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md`

> **Teil-Ablösung (2026-08-14, ADR-0055, Issue #1720 Scheibe 1):** Punkt 2 der
> Entscheidung unten sichert zu, der Trip rufe „weiterhin ohne `metrics` auf —
> die Trip-Mail ändert sich in keinem Byte". Das gilt **nicht mehr**: Der
> Trip-Ausblick hat seit #1720 eine eigene Spaltenauswahl. Ohne Bedienung der
> neuen Fläche bleibt die Trip-Mail byte-identisch, mit Bedienung ändert sie
> sich. Die Punkte 1, 3 und 4 gelten unverändert; das Datenformat und die
> Drei-Werte-Semantik (`None` / `[]` / gefüllt) hat ADR-0055 übernommen statt
> ein zweites Vokabular einzuführen.
>
> Die damalige Formulierung war für ihre Lieferung richtig — sie hielt den Trip
> aus einer Compare-Scheibe heraus. Sie wurde später jedoch als dauerhafte
> Festlegung gelesen („der Trip bekommt bewusst keine Ausblick-Auswahlfläche",
> `weatherMetricsTabSections.ts:54-55`). ADR-0055 benennt diese Fehlerklasse
> ausdrücklich: eine Zuschnittgrenze wird beim Weiterreichen zur Festlegung.

## Kontext

Der 3-Tages-Ausblick der Ortsvergleichs-Mail zeigte bis zu diesem Fix unveränderlich
dieselben sieben Größen (Temp min/max, Regen, Regen-Wahrscheinlichkeit, Wind, Böen,
Gewitter) mit kryptischen Kürzeln (`N`/`D`/`R`/`PR`) als Spaltenköpfe, ohne eigene
Überschrift im HTML, mit der Trip-Formulierung „Nächste Etappen" im Klartext, und
begann am selben Kalendertag, den die Stundentabelle bereits im Detail zeigte — an
einer echt zugestellten Staging-Mail belegt (Kontext-Dokument
`docs/context/fix-1361-1368-ausblick-konfigurierbar.md`, Beleg-Tabelle).

Der zugrundeliegende Baustein `build_outlook_row`/`render_outlook_table`/
`render_outlook_plain` (`src/output/renderers/email/outlook.py`) ist seit jeher
**vollständig geteilt** zwischen Trip-Briefing und Ortsvergleich — Trip reichert
danach lediglich Etappenname/-datum an. Übersichtstabelle (#1373) und
Stundenverlauf hatten im selben Epic bereits den Wechsel von festen Spalten auf
den zentralen Metrik-Katalog (`src/app/metric_catalog.py`, 24 wählbare Größen mit
`summary_fields`) vollzogen; der Ausblick war die letzte der drei
Compare-Ausgabeflächen mit fest verdrahteten Spalten. `SegmentWeatherSummary`
trägt bereits alle 24 Tagesauswertungen — der Umbau war eine Frage der
Darstellung/Auswahl, kein zusätzlicher Datenabruf.

## Entscheidung

1. **Die Ausblick-Spalten kommen datengetrieben aus dem zentralen Metrik-Katalog**,
   nicht mehr aus einer fest verdrahteten Sieben-Spalten-Liste. Auswahl liegt als
   `display_config.outlook_metrics` im **Neuformat**
   `[{"metric_id": ..., "aggregation": ...}]` — demselben Vokabular wie
   `active_metrics` seit #1373, kein viertes Vokabular. Aufgelöst über
   `compare_metric_catalog.key_for()` (Existenz-/Gültigkeitsprüfung) und
   `metric_catalog._METRICS` (`summary_fields[aggregation]` → Feldname auf
   `SegmentWeatherSummary`). Spaltenköpfe kommen aus `compare_metric_catalog.label`
   (deutsch, eindeutig), nicht aus `metric_catalog.col_label` (liefert für mehrere
   Temperatur-Auswertungen identisch „Temp").
2. **`build_outlook_row(..., metrics=None)` bleibt byte-identisch.** Der neue
   `metrics`-Parameter ist rein additiv: `None` (Trip-Aufruf, unverändert) liefert
   exakt das bisherige feste Dict. Der Trip ruft weiterhin ohne `metrics` auf — die
   Trip-Mail ändert sich in keinem Byte, abgesichert durch die
   Byte-Identitäts-Tests in `tests/tdd/test_shared_outlook_renderer.py`.
3. **Fehlt die Auswahl (`None`), zeigt der Ausblick unverändert die bisherigen
   sieben Größen** — kein stiller Verhaltenswechsel für Bestandsnutzer. Eine
   bewusst geleerte Auswahl (`[]`) lässt den Ausblick-Block vollständig entfallen
   (Überschrift und Tabelle), analog zur bestehenden Kopplung von
   `hourly_metrics=[]` an `hourly_enabled=False`.
4. **Der Ausblick begint erst nach dem letzten von der Stundentabelle berührten
   Kalendertag** — bei normalem Tagesfenster der Tag nach `target_date`, bei einem
   Mitternachts-Fenster (ADR-0035) der Tag nach `target_date + 1`. Der im Detail
   gezeigte Tag darf nie im Ausblick vorkommen (PO-Vorgabe V1).
5. **Der Ausblick bekommt eine eigene, erkennbare Überschrift** „3-Tages-Ausblick"
   in HTML (mit demselben Zeitzonen-Kürzel-Mechanismus wie der Stundenblock,
   #1378) und Klartext (statt der bisherigen Trip-Formulierung „Nächste Etappen")
   — unabhängig davon, ob eine Auswahl gesetzt ist, weil die Beschriftung ein
   eigenständiger Fehler war, kein an die Auswahl gekoppeltes Verhalten.
6. **`outlook_enabled` bekommt eine vollständige Bedienfläche.** Das Feld existierte
   bereits top-level, war aber im Go-Struct nicht abgebildet — ein Client, der es
   über die Go-API schrieb, verlor es beim Decode still. `OutlookEnabled *bool`
   (`internal/model/compare_preset.go`) mit nil-Preserve-Block im Handler
   (Muster `HourlyEnabled`) schließt diese Lücke; `outlook_metrics` selbst
   braucht keinen Go-Eingriff, da `display_config` generisch gemergt wird.

## Verworfene Alternativen

- **Ein Compare-eigener Ausblick-Renderer mit voller Auswahl.** Schneller zu
  bauen, weil der Trip-Pfad dabei unangetastet bliebe — verworfen, weil das ein
  Verstoß gegen die Trip/Compare-Teilungs-Invariante wäre (CLAUDE.md-Abschnitt
  „Trip/Ortsvergleich-Code-Teilung", Anti-Pattern-Referenz #1170). Der Ausblick
  ist heute vollständig geteilter Code; eine zweite Implementierung nur für
  Compare hätte künftig zwei divergierende Ausblicks-Wahrheiten geschaffen.
- **Auswahl nur aus den bisherigen sieben Größen** (kleinerer Umbau, kein Eingriff
  in `build_outlook_row`). Verworfen: Der PO hat sich auf Vorlage der Trade-offs
  ausdrücklich für den vollen Katalog (24 Größen) entschieden (V4,
  Kontext-Dokument) — konsistent mit der bereits für Übersichtstabelle und
  Stundenverlauf getroffenen Entscheidung „eine Größe, mehrere Auswertungen"
  (Epic #1372).
- **Spaltenköpfe aus `metric_catalog.col_label`.** Verworfen: liefert für
  `temperature` min/max/avg identisch „Temp" — zwei gewählte
  Temperatur-Auswertungen ergäben zwei gleich beschriftete Spalten; außerdem sind
  die bisherigen Kürzel englisch. `compare_metric_catalog.label` ist deutsch und
  je Metrik+Aggregation eindeutig.

## Konsequenzen

- **Positiv:** Alle drei Compare-Ausgabeflächen des Ortsvergleichs (Übersicht,
  Stundenverlauf, Ausblick) setzen jetzt auf denselben Metrik-Katalog auf — ein
  Vokabular statt drei divergierender. Der Nutzer wählt für den Ausblick aus
  denselben 24 Größen wie für die anderen Ausgabeflächen. Die Trip-Mail bleibt
  unangetastet, der geteilte Baustein bleibt geteilt.
- **Negativ / Preis:** `outlook.py` ist jetzt spürbar komplexer (fester UND
  datengetriebener Pfad im selben Baustein); jede künftige Änderung am Ausblick
  trifft strukturell beide Pfade (Trip und Compare) und muss den
  Byte-Identitäts-Wächter grün halten. Die generische Zellenformatierung für
  Größen außerhalb der bisherigen sieben (Enum-/Ordinal-Werte wie
  `precip_type_dominant`) ist neuer, weniger erprobter Code als die bisherige
  handgeschriebene Sieben-Spalten-Formatierung.
- **Folgepflichten:** Diese Entscheidung ist schwer umkehrbar — ein Rückbau auf
  feste Spalten würde wieder drei divergierende Compare-Vokabulare einführen.
  `tests/tdd/test_shared_outlook_renderer.py` ist die Regressionsgrenze für die
  Trip-Byte-Parität und muss bei jeder Änderung an `outlook.py` grün bleiben.
  Neue wählbare Ausgabeflächen des Ortsvergleichs orientieren sich an demselben
  Katalog-Muster (`compare_metric_catalog.key_for()`), statt ein weiteres eigenes
  Vokabular einzuführen.
