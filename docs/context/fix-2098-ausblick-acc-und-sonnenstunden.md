# Context: fix-2098-ausblick-acc-und-sonnenstunden

Issue: [#2098](https://github.com/henemm/gregor_zwanzig/issues/2098) · `type:bug` · `priority:high`
· Milestone „Tour KHW 2026-08"

## Request Summary

In der 3-Tages-Vorschau („AUSBLICK · NÄCHSTE 3 TAGE") der Trip-Briefing-E-Mail sind zwei
Fehler sichtbar: die Spalte **Sonnenstunden** zeigt in allen drei Zeilen `–`, und die Spalte
**ACC** (Prognose-Genauigkeit / `confidence_pct`) ist ganz verschwunden. Der PO verlangt: ACC
muss **immer** erscheinen, unabhängig von der Frontend-Metrik-Auswahl. Für die Sonnenstunden
ist zu klären, ob die Größe überhaupt verfügbar ist — und ob **weitere Metriken** dasselbe
Problem haben.

## Beleg aus dem Issue (zwei Screenshots)

| Stand | Kopfzeile der Vorschau | ACC | Sonnenstunden |
|---|---|---|---|
| Fr 07:04 | `Tag · N · D · R · PR · Wind · Böen · Gew · ACC` (Kurzform) | ✅ Farbpunkt je Zeile | nicht vorhanden |
| So 07:05 | `Tag · Gefühlte Temperatur · Wind · Böen · Niederschlag · Regenwahrscheinlichkeit · Gewitter · Sonnenstunden` (Langform) | ❌ fehlt | vorhanden, aber `–` in allen 3 Zeilen |

Die Kopfzeile wechselt zwischen den beiden Ständen von der **festen Kurzform-Liste** auf die
**Langform der konfigurierten Trip-Metriken**. Beide Befunde entstehen an diesem Wechsel.

## Auslösende Änderungen (zwischen den Screenshots nach `main` gegangen)

| Commit | Titel |
|---|---|
| `f66a5457` | feat(#1848 A2): Backend liest und schreibt Ausblick-Kennungen |
| `2ff3fb44` | feat(#2049): Roh/Einfach-Umschaltung je Ausblick-Metrik |

## Gemeinsame Wurzel (Hypothese für Phase 2)

`render_outlook_table()` hat **zwei Zweige**:

1. **Altform-Zweig** (`metrics is None`) — die sieben festen Spalten, `outlook.py:165-177`
   (Kopf) und `:231` (Datenzelle). **Nur hier existiert `show_acc`.**
2. **Konfigurierbarer Zweig** (`metrics is not None`) — `outlook.py:129-163`. Die Kopfzeile
   entsteht ausschließlich aus `outlook_columns(metrics)`, die Werte ausschließlich aus
   `stage["cells"]`. **Dieser Zweig kennt ACC überhaupt nicht.**

Der Docstring von `render_outlook_table` bezeichnet `metrics` ausdrücklich als
„#1361/#1368, **nur Compare**". Seit #1848 A2 fährt aber auch der **Trip** über diesen Zweig.
Damit erbt der Trip zwei Compare-Eigenschaften, die für ihn falsch sind:

- **ACC:** Der Ortsvergleich ruft bewusst mit `show_acc=False` auf (`compare_html.py:1257`).
  Der Trip ruft weiterhin mit `show_acc=True` auf (`html.py:1403`) — der Schalter läuft im
  konfigurierbaren Zweig aber ins Leere, weil dort keine ACC-Zelle gebaut wird.
- **Sonnenstunden:** Die Zellen entstehen datengetrieben über
  `MetricDefinition.summary_fields` als `getattr(summary, col["field"])`. Für `sunshine` ist
  das `summary_fields={"sum": "sunny_hours"}` (`metric_catalog.py:604`), also
  `SegmentWeatherSummary.sunny_hours` (`models.py:497`). Dieses Feld wird gefüllt von
  `summarize_points()` (`weather_metrics.py:554`) und vom Ortsvergleich
  (`comparison_engine.py:261/356/560`) — der Trip-Ausblick nutzt jedoch `aggregate_stage()`
  (`weather_metrics.py:1352`), das sein Ergebnis **allein aus `aggregation_config`** aufbaut
  (`models.py:531`). Trägt `sunny_hours` dort keine Aggregationsregel, fällt der auf
  Segment-Ebene vorhandene Wert auf Etappen-Ebene weg → `None` → `–`.

**Konsequenz für die PO-Frage „gibt es sie nicht in einem größeren Zeitfenster?":** Wenn sich
das bestätigt, sind die Sonnenstunden **vorhanden** und gehen nur auf der Aggregationsstufe
verloren. Die vom PO erwogene Alternative — die Metrik aus dem Angebot nehmen — wäre dann
nicht die richtige Antwort.

**Konsequenz für „trifft das weitere Metriken?":** Die Verdachtsliste ist bestimmbar statt
geraten — alle Metriken, deren `summary_fields`-Zielfeld in `aggregate_stage`s
`aggregation_config` fehlt. Das ist in Phase 2 mechanisch abzählbar.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/outlook.py:45` | `render_outlook_table()` — beide Zweige, `show_acc` nur im Altform-Zweig |
| `src/output/renderers/email/outlook.py:103-121` | `_acc_dot()` — 4-stufiger Farbpunkt aus `confidence_pct` |
| `src/output/renderers/email/outlook.py:129-163` | konfigurierbarer Zweig: Kopf aus `outlook_columns()`, Werte aus `stage["cells"]` |
| `src/output/renderers/email/outlook.py:263` | `render_outlook_plain()` — Klartext-Fassung, muss mitziehen (HTML=Normalfassung, keine Dopplung) |
| `src/output/renderers/email/outlook.py:432` | `build_outlook_row()` — baut `cells`, geteilte Naht Trip+Compare |
| `src/output/renderers/email/outlook.py:634-690` | `cells`-Schleife: `format_outlook_range_cell()` / `format_outlook_value()` |
| `src/output/renderers/compare_outlook_metric_ids.py:48` | `derived_aggregations()` — Kennung → Auswertungen |
| `src/output/renderers/compare_outlook_metric_ids.py:194` | `resolve_trip_outlook_metrics()` — Trip-Auflösung |
| `src/output/renderers/compare_outlook_metric_ids.py:298` | `outlook_columns()` — Spaltenbeschreibung, Quelle der Kopfzeile |
| `src/app/metric_catalog.py:593-605` | `sunshine`-Definition: `summary_fields={"sum": "sunny_hours"}`, `dp_field="dni_wm2"` |
| `src/app/metric_catalog.py:999` | `OUTLOOK_FRIENDLY_CAPABLE` — enthält `sunshine` |
| `src/app/models.py:444/497/531` | `SegmentWeatherSummary`, Feld `sunny_hours`, `aggregation_config` |
| `src/services/weather_metrics.py:350` | `calculate_sunny_hours()` — DNI-Interpolation |
| `src/services/weather_metrics.py:534-554` | `summarize_points()` — füllt `sunny_hours` auf Segment-Ebene |
| `src/services/weather_metrics.py:1352` | `aggregate_stage()` — Etappen-Aggregation über `aggregation_config` |
| `src/services/trip_report_scheduler.py:2465` | Aufruf `build_outlook_row()` mit Trip-Konfiguration |
| `src/output/renderers/email/html.py:1403` | Trip: `render_outlook_table(..., show_acc=True)` |
| `src/output/renderers/email/compare_html.py:1257` | Compare: `render_outlook_table(..., show_acc=False)` |

## Existing Specs

| Spec | Bezug |
|---|---|
| `docs/specs/modules/feat_1848_a2_ausblick_kennungen.md` | Auslöser: Ausblick-Kennungen im Backend |
| `docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md` | Trip erbt die Grundauswahl |
| `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` | Trip-Ausblick-Metriken |
| `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` | Ursprung des konfigurierbaren Zweigs (Compare) |
| `docs/specs/modules/fix_2049_ausblick_darstellungsform.md` | Roh/Einfach je Ausblick-Metrik |
| `docs/specs/modules/feat_1406a_ausblick_geteiltes_element.md` | Ausblick als geteiltes Element Trip/Compare |
| `docs/specs/modules/outlook_gehzeit_und_spanne.md` | Gehzeit-Fenster und Spannen im Ausblick |
| `docs/reference/renderer_email_spec.md` | Mail-Renderer-Referenz |

## Dependencies

- **Upstream:** `metric_catalog` (Metrik-Definitionen, `summary_fields`) · `weather_metrics`
  (`summarize_points`, `aggregate_stage`, `calculate_sunny_hours`) · `SegmentWeatherSummary`
  · `trip_report_scheduler` (reicht `display_config` durch)
- **Downstream:** vier Ausgabeorte teilen sich `build_outlook_row()` — Trip-HTML,
  Trip-Klartext, Compare-HTML, Compare-Klartext. Eine Änderung an den Zellen wirkt überall.

## Risks & Considerations

- **Trip/Compare-Teilungs-Invariante (CLAUDE.md):** `build_outlook_row()` und
  `render_outlook_table()` sind bewusst geteilt. Ein Fix darf keine Trip-eigene Kopie
  erzeugen. ACC ist bereits sauber parametrisiert (`show_acc`) — der Weg ist, diesen
  Parameter im konfigurierbaren Zweig **wirksam** zu machen, nicht ihn zu umgehen.
- **#710 (Confidence nicht wählbar):** ACC darf **nicht** als wählbare Metrik in die Auswahl
  wandern. Der E-Mail-Textblock ist einer der drei erlaubten Orte — die Spalte muss also
  **neben** der Auswahl stehen, fest angehängt, nicht als Katalog-Eintrag.
- **HTML=Normalfassung, keine Dopplung:** der Farbpunkt im HTML braucht im Klartext ein
  **Wort**, keinen Punkt. `render_outlook_plain()` muss mitgeführt werden.
- **Reihenfolge-Kopplung:** Kopfzeile und Wertzeilen entstehen aus **zwei getrennten**
  `outlook_columns()`-Aufrufen und sind nur über den Listenindex verbunden
  (`compare_outlook_metric_ids.py:64-68`). Eine fest angehängte ACC-Spalte muss an **beiden**
  Enden gleich angehängt werden, sonst verschieben sich Werte gegen Beschriftungen — still.
- **Renderer-Commit-Gate:** Änderungen an Mail-Inhalts-Dateien blocken den Commit, bis
  Modus-Matrix-Test und `briefing_mail_validator.py` frisch grün sind.
- **Nachweis-Pfad:** Trip-Briefing ⇒ `briefing_mail_validator.py` (nicht
  `email_spec_validator.py`), gegen echt zugestellte Staging-Mail.
- **Tour läuft ab heute (2026-08-23).** Normal ausliefern, nicht abkürzen und nicht
  aufschieben.
- **Fehlender Wert verschluckt still:** Bei `texte = [cells[i] if i < len(cells) else "–"]`
  erzeugt sowohl eine zu kurze `cells`-Liste als auch ein echter `None`-Wert dasselbe `–`.
  Tests müssen den **Wert** prüfen, nicht die Form — ein plausibel falscher Wert als
  Gegenprobe, nicht `None`.

---

## Analysis (Phase 2 — zwei parallele Ermittler, beide mit Beleg)

### Type
**Bug** (zwei Befunde, gemeinsame Wurzel: der Trip fährt seit #1848 A2/A3 über den
konfigurierbaren Ausblick-Zweig, der für den Ortsvergleich gebaut wurde).

### Befund 1 — Sonnenstunden: bestätigt, Ursache exakt lokalisiert

`aggregate_stage()` (`weather_metrics.py:1384`) baut das Etappen-Summary **ausschließlich** aus
Feldern, die in `summaries[0].aggregation_config` eine Regel tragen (Schleife ab `:1385`).
`sunny_hours` wird zwar gesetzt (`weather_metrics.py:534,554`) und im Extended-Merge mitkopiert
(`:1002`), trägt aber **weder im Basis-Dict (`:553-569`) noch im Extended-Merge (`:1032-1061`)
eine Aggregationsregel**. Damit wird es nie iteriert, landet nicht in `result_fields` und bleibt
auf dem Dataclass-Default `None`.

Zellwert: `outlook.py:401` `return getattr(summary, field, None)` → `None` → `–`.

**Gegenprobe ausgeführt** (nicht nur gelesen): drei Segment-Summaries mit
`sunny_hours = 2.0 / 3.5 / 4.0` und einer `aggregation_config` ohne `sunny_hours`-Regel durch
`aggregate_stage()`:

```
sunny_hours im Ergebnis: None
temp_min_c im Ergebnis: 10.0     # Feld MIT Regel überlebt
```

**Sonderfall mit Testrelevanz:** `compact_summary.py:265-268` ruft `aggregate_stage()` nur bei
**mehr als einem** Segment; bei Einzelsegment-Etappen wird `valid[0].aggregated` unbeschädigt
durchgereicht und der Wert erscheint. Der Fehler trifft also **nur Mehrsegment-Etappen** — ein
Test mit einer Einzelsegment-Etappe wäre falsch grün.

### Audit „trifft das weitere Metriken?" — abschließend beantwortet: NEIN

Alle 26 `MetricDefinition`s mit `summary_fields` geprüft (inkl. aller 9
`OUTLOOK_FRIENDLY_CAPABLE` und aller Grundauswahl-Templates ab `metric_catalog.py:1100`), die
vollständige Feldliste von `SegmentWeatherSummary` (`models.py:444-531`) gegen die Vereinigung
beider `aggregation_config`-Dicts abgeglichen: **`sunny_hours` ist das einzige Zielfeld ohne
Regel.** Alle übrigen (Temperatur, Wind, Böen, Niederschlag, Regenwahrscheinlichkeit, Gewitter,
CAPE, Bewölkung, Sicht, UV, Druck, Nullgradgrenze, Schneehöhe, Neuschnee …) tragen eine Regel.

`compare_alert.py:61` („`sunny_hours_h`, `uv_index_max`, `snow_depth_cm` bewusst KEIN Mapping")
betrifft eine **andere** Tabelle (`_SUMMARY_KEY_TO_CATALOG_ID`, Alarm-Zuordnung im
Ortsvergleich) und hat mit diesem Bug nichts zu tun. UV-Index und Schneehöhe sind im
Trip-Ausblick nachweislich in Ordnung.

⇒ **Die vom PO erwogene Alternative („Metrik aus dem Angebot nehmen") ist widerlegt** — die
Daten existieren, sie gehen eine Stufe vor der Anzeige verloren.

**Reichweite:** nur Trip. `aggregate_stage()` wird ausschließlich vom Trip-Pfad gerufen
(`compact_summary.py:268`, `stage_weather.py:113`, `trip_report_scheduler.py:2422`); der
Ortsvergleich nutzt `summarize_points()`/`comparison_engine.py` ohne den
`aggregation_config`-Rebuild und ist strukturell nicht betroffen.

### Befund 2 — ACC: strukturell, nicht zufällig

`show_acc` ist an allen vier Aufrufstellen korrekt gesetzt (Trip `True`, Compare `False`), wird
aber vom **konfigurierbaren Zweig beider Renderer nicht gelesen** — dieser kehrt vorher zurück
(Tabelle) bzw. macht `continue` (Klartext). Seit #1848 A3 liefert
`resolve_trip_outlook_metrics()` für den Trip fast nie mehr `None`, sondern die volle
Grundauswahl ⇒ der Trip läuft **praktisch immer** über den Zweig ohne ACC.

**ACC kann nie eine wählbare Metrik-Spalte werden:** `confidence` ist `selectable=False`
(`metric_catalog.py:418-423`, ADR-0005/#710), `derived_aggregations("confidence")` liefert
darum immer `[]`. Die Wiederherstellung muss **außerhalb** des Metrik-Systems erfolgen — fest
angehängt neben der Auswahl, exakt wie im Altform-Zweig.

**Der Wert ist vorhanden:** `confidence_pct` wird in `build_outlook_row()` (`outlook.py:586-587,
:599`) **vor** dem `if metrics is not None:`-Block (`:621`) ins Row-Dict geschrieben, Quelle
`summary.confidence_pct_min` (gesetzt in `trip_report_scheduler.py:2299,2322`). Die
wiederhergestellte Spalte trägt also sofort echte Werte.

### Reihenfolge-Kopplung — entwarnt

Die Warnung in `compare_outlook_metric_ids.py:64-68` (Kopf und Werte nur über den Listenindex
verbunden) betrifft eine fest angehängte ACC-Spalte **nicht**, sofern sie am
`outlook_columns()`/`cells`-Mechanismus vorbei angehängt wird:

- `render_outlook_table()`: Kopf (`:133-135`) und Zellen (`:140-156`) entstehen bereits aus
  **einem** `outlook_columns(metrics)`-Aufruf. Zwei Editierstellen in derselben Funktion, beide
  lesen denselben `show_acc` und dasselbe `stage.get("confidence_pct")` — kein Indexrisiko.
- `render_outlook_plain()`: Label und Wert entstehen pro Spalte in **einer**
  `"  ".join(...)`-Zeile (`:301-303`) — eine Editierstelle, ein Auseinanderlaufen ist
  strukturell unmöglich.

⇒ `show_acc` ist die bereits vorhandene, nur ungenutzte Naht. Kein neuer Kopplungspunkt.

### 🔴 Der Test verankert das Gegenteil

`tests/tdd/test_trip_outlook_dispatch_mail.py:533-558`, Zeile 552, prüft ausdrücklich
`kopf[1:] != ["N","D","R","PR","Wind","Böen","Gew","ACC"]` mit Kommentar „#1848 A3, AC-3" und
Verweis auf **„PO-Freigabe 2026-08-21"**. Das Verschwinden von ACC im Trip-Normalfall war eine
akzeptierte, testverankerte Nebenfolge — keine unbeachtete Lücke. #2098 dreht diese Entscheidung
zurück; der Test muss mit angepasst werden, sonst blockiert er die eigene Behebung.

**Warum kein Test gefangen hat:** alle ACC-Wächter rufen ohne `metrics=` auf und landen im
inzwischen toten Altform-Zweig — `test_shared_outlook_renderer.py:132-156` (AC-1) und
`:163-199` (AC-2), `test_trip_outlook_parity.py:94-122`.

**Zu wahren:** `test_trip_outlook_metric_selection.py:310-325` und `:328-355` (AC-10 a/b)
bewachen, dass `confidence` nie als **wählbare** Spalte erscheint (#710). Eine strukturell fest
angehängte ACC-Spalte lässt diese Invariante unberührt — und muss das auch.

### Klartext-ACC: Neuanforderung, keine Wiederherstellung

`render_outlook_plain()` hat ACC **nie** ausgegeben — auch nicht im Altform-Zweig
(`outlook.py:273-275` Docstring; verifiziert gegen
`tests/fixtures/outlook_trip_parity/trip_outlook_show_acc_true.txt`, kein ACC-Token). Die
Projektregel „Farbe im HTML ⇒ WORT im Klartext" ist dort bereits vorbestehend unerfüllt. Im HTML
ist ACC ein reiner Farbpunkt (`_acc_dot()`, `:103-121`, vier Stufen ≥80 / ≥60 / ≥40 / <40) — die
Farbe ist der **einzige** Informationsträger, für Klartext-Leser also unsichtbar. Aufnahme
vorgeschlagen, als Erweiterung ausgewiesen.

### Affected Files

| Datei | Change | Beschreibung |
|---|---|---|
| `src/services/weather_metrics.py` | MODIFY | `"sunny_hours": "sum"` in `aggregation_config` (`:553-569`) |
| `src/output/renderers/email/outlook.py` | MODIFY | `show_acc` im konfigurierbaren Zweig von `render_outlook_table()` (`:129-163`) und `render_outlook_plain()` (`:289-314`) wirksam machen; Klartext-Wort für ACC |
| `tests/tdd/test_trip_outlook_dispatch_mail.py` | MODIFY | `:552` — verankert das Gegenteil, muss angepasst werden |
| `tests/…` | CREATE | Wächter: Mehrsegment-Etappe mit Sonnenstunden-Wert; ACC im konfigurierbaren Zweig; #710-Invariante bleibt |
| `docs/reference/renderer_email_spec.md` | MODIFY | Ausblick-Spaltenbild richtigstellen |

### Scope Assessment
- Dateien: 5–6 · geschätzt +80/-10 LoC (unter dem 250er-Limit)
- Risk: **MEDIUM** — kleiner Eingriff, aber im Trip-Briefing (kritischer Ausgabepfad,
  Renderer-Commit-Gate) und mit einem Test, der die Gegenrichtung festschreibt

### Technical Approach
1. **Sonnenstunden:** Aggregationsregel `"sunny_hours": "sum"` ergänzen — analog zur
   Katalog-Regel `summary_fields={"sum": "sunny_hours"}` (`metric_catalog.py:604`). Der
   Extended-Merge übernimmt sie automatisch über `**basis_summary.aggregation_config` (`:1033`).
2. **ACC:** `show_acc` im konfigurierbaren Zweig beider Renderer lesen und die Spalte **hinter**
   den gewählten Metriken anhängen — außerhalb von `outlook_columns()`/`cells`, damit die
   #710-Invariante unberührt bleibt.
3. **Klartext:** vierstufiges Wort statt Farbpunkt.
4. **Test `:552` anpassen** und die Lücke schließen, die ihn entstehen ließ: Wächter, die den
   **produktiven** Zweig (`metrics=` gesetzt) prüfen, nicht den toten Altform-Zweig.

### Open Questions
- [x] Trifft das weitere Metriken? → **Nein**, `sunny_hours` ist die einzige Lücke (abgezählt).
- [x] Gibt es die Sonnenstunden in einem größeren Zeitfenster? → **Ja**, sie existieren; die
      Metrik gehört nicht aus dem Angebot genommen.
- [ ] Klartext-ACC aufnehmen? → als Erweiterung vorgeschlagen, PO entscheidet bei der
      Spec-Freigabe.
