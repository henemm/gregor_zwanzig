---
entity_id: sms_format
type: reference
version: "2.29"
status: active
created: 2025-12-27
updated: 2026-08-17
tags: [sms, compact, tokens, single-source-of-truth]
---

## Approval

- [x] Approved (v2.0 am 2026-04-25)
- [x] Implementiert in SMS-Adapter via `src/output/renderers/sms/` (β3, 2026-04-28)

# SMS / Kompakt-Format Specification (v2.29)

**Single Source of Truth** für die kompakte Token-Zeile, die in allen Channels (SMS, Satellit, E-Mail-Header, Push) identisch verwendet wird. Alle anderen Repräsentationen (E-Mail-Body, Tabellen, Push-Titel) leiten sich aus dieser Token-Zeile ab.

> **Korrektur 2026-08-16 (Fix #1887 Scheibe A, v2.28):** Das Wintersport-Kürzel
> `WC` (gefühlte Tages-Einzeltemperatur) **entfällt ersatzlos** — es
> verdoppelte nachweislich den Wert von `FK` (s. §3.6/§9-Korrekturen unten,
> die diese Redundanz erstmals am 2026-08-11 nachwiesen). Alle Stellen
> unten, die `WC` noch als aktuelles Token zeigen, sind mit dieser Version
> bereinigt; die historische Korrespondenz zur früheren PO-Entscheidung
> „WC soll bleiben" (#1728 E3) bleibt als Nachweis stehen, gilt aber nicht
> mehr. Details: `docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md`.

> **Korrektur 2026-08-17 (Fix #1926, v2.29):** Drei Register-Kürzel wurden wegen
> PO-Konsistenzentscheid geändert — **`K` → `L`** (Tages-Tiefsttemperatur, Gehzeit),
> **`FK` → `FL`** (gefühlte Tages-Tiefsttemperatur, Gehzeit) sowie **`NL` → `FZ`**
> (Nullgradgrenze, Kollisionsvermeidung mit dem Schnee-/`SL`-Bereich). Alle Stellen
> unten, die diese drei Kürzel als **aktuellen** Ist-Zustand zeigen, sind mit dieser
> Version nachgezogen. Historische, datierte Korrektur-Absätze (z. B. §3.6, die
> WC/FK-Dublette vom 2026-08-11) bleiben mit dem damaligen Kürzel-Namen stehen — sie
> berichten über den Stand zum jeweiligen Zeitpunkt, nicht über den heutigen. Details:
> `docs/specs/modules/fix_1926_metrik_kuerzel_englisch.md`.

Diese Spec ersetzt v1.0 und integriert das Format aus dem Vorgänger-Projekt (`weather_email_autobot/requests/morning-evening-refactor.md`).

---

## 1. Prinzipien

- **Maximale Länge:** ≤160 Zeichen (GSM-7 normalisiert).
- **Zeichensatz:** ASCII / GSM-7. Umlaute werden ersetzt (ä→ae, ö→oe, ü→ue, ß→ss);
  darüber hinaus wird **jede** andere Schrift (Griechisch, Kyrillisch, Arabisch, …)
  auf ASCII transliteriert. Umsetzung einzig über `fold_ascii()` in
  `src/utils/ascii_fold.py` (ADR-0022) — Umlaut-Digraph-Map zuerst, danach
  `anyascii` zeichenweise. Buchstaben, die auch `anyascii` nicht falten kann,
  erscheinen als sichtbarer Platzhalter `?` statt lautlos zu verschwinden.
- **Zeitformat:** Lokale Zeit (CEST), nur Stunde (0–23, **ohne** führende Null). Beispiel: `@7`, nicht `@07`.
- **Tokens:** Kurze, möglichst englische/internationale Identifier.
- **Trennzeichen:** Einzelnes Leerzeichen zwischen Tokens. Ausnahmen siehe Risks-Block (3.3).
- **Werte-Rundung:** Temperaturen ganzzahlig gerundet; Niederschlag mit einer Nachkommastelle; Wind/Böen ganzzahlig.
- **Threshold = Max:** Wenn Threshold-Wert UND Threshold-Stunde exakt dem Tagesmaximum entsprechen, wird der Peak-Block `(max@h)` weggelassen (Details §5).
- **Priorität bei Truncation:** Thunderstorm > Wind/Gusts > Rain > Temperatur (siehe §6).

---

## 2. Token-Reihenfolge (fix)

```
{Name}: N L D FN FL FD R PR W G TH: TH+: HU DP WD: CP PT: CT CL CM CH VS SU UV HP FZ C HR:TH: !{Warn-Block} Z: M: [SD NS24+ SL AV] X? DBG
```

**Hinweis zu `L D` / `FL FD` (Issue #1824, 2026-08-14; Kürzel `K`→`L`/`FK`→`FL` seit Fix #1926, 2026-08-17):** Sind bei einer Temperatur-Metrik **beide** Auswertungen („Tiefstwert" UND „Höchstwert") gewählt, erscheinen die beiden Kürzel nicht getrennt, sondern als **ein Bereichs-Token** unter dem Höchstwert-Kürzel: `D{min}/{max}` statt `L{min} D{max}` (gefühlt: `FD{min}/{max}`). Ist nur eine der beiden Auswertungen gewählt, bleibt die bisherige Einzelform (`L13` bzw. `D27`) unverändert — `L`/`FL` bedeuten also weiterhin immer den Tiefstwert. `N`/`FN` (Nacht) sind davon nicht betroffen.

| Block | Tokens | Pflicht? |
|-------|--------|---------|
| Header | `{Name}:` | immer |
| Forecast (Nacht) | `N` | **nur Abendbriefing** (Issue #1319 Scheibe D) — im Morgenbriefing entfällt der Token komplett, nicht als `N-` — UND nur bei aktivierter Metrik „Nacht-Tiefsttemperatur“ (`temperature_night`, Issue #1484; bis dahin an „Temperatur“ gekoppelt, Issue #1415) |
| Forecast (Tiefst unterwegs) | `L` (bis 2026-08-17 `K`, Fix #1926) | Morgen + Abend (Issue #1410) — kälteste Gehzeit-Stunde, von `N` unterschieden — **seit 2026-08-15 nur bei aktivierter Metrik „Tages-Tiefsttemperatur (Gehzeit)“** (`temperature_day_low`, Issue #1728; bis dahin an die Auswertungswahl der Metrik „Temperatur“ gekoppelt, Issue #1415/#1824); ist zusätzlich „Tages-Höchsttemperatur (Gehzeit)“ (`temperature_day_high`) aktiviert, tragen die beiden Werte gemeinsam den Bereichs-Token `D{min}/{max}` (Issue #1824) |
| Forecast (gefühlt, Nacht) | `FN` | **nur Abendbriefing** UND nur bei aktivierter Metrik „Gefühlte Nacht-Tiefsttemperatur“ (`wind_chill_night`, Issue #1660; bis dahin an „Gefühlte Temperatur“ gekoppelt, Issue #1410) |
| Forecast (gefühlt) | `FL FD` (bis 2026-08-17 `FK FD`, Fix #1926) | Morgen + Abend — **seit 2026-08-15** hängt `FL` an der eigenen Metrik „Gefühlte Tages-Tiefsttemperatur (Gehzeit)“ (`wind_chill_day_low`), `FD` an „Gefühlte Tages-Höchsttemperatur (Gehzeit)“ (beide Issue #1728; bis dahin hingen beide gemeinsam an „Gefühlte Temperatur“ + deren Auswertungswahl, Issue #1660 A/#1824) — sind beide aktiviert, ein Bereichs-Token `FD{min}/{max}` (Issue #1824) |
| Forecast (Höchst) | `D` | Morgen + Abend, **seit 2026-08-15** nur bei aktivierter Metrik „Tages-Höchsttemperatur (Gehzeit)“ (`temperature_day_high`, Issue #1728; bis dahin an „Temperatur“ + deren Auswertungswahl gekoppelt, Issue #1415) — trägt bei zusätzlich aktiviertem `temperature_day_low` den Bereich `D{min}/{max}` (Issue #1824) |
| Forecast | `R PR W G TH:` | nur bei aktivierter Metrik (bei `-` als Null-Wert) |
| Forecast (Gewitter Folge-Etappe) | `TH+:` | nur bei aktivierter Metrik „Gewitter“ — seit Fix #1482 (2026-08-04) synchron mit `TH:` über dieselbe Metrik-Bindung (vorher Ist-Abweichung, s. Hinweis unter §2) |
| Forecast (14 erweiterte Metriken, Issue #1660 Scheibe B) | `HU DP WD: CP PT: CT CL CM CH VS SU UV HP FZ` (bis 2026-08-17 `NL`, Fix #1926) | Morgen + Abend, jeweils nur bei aktivierter Metrik — Details §3.2a. `WD:`/`PT:` tragen seit Issue #1824 den Grammatik-Doppelpunkt (Buchstaben-Wert, s. §3.2a) |
| Confidence | `C` | nur wenn Provider Konfidenz liefert (Issue #121, v2.1) |
| Risks (Vigilance) | `HR:TH:` (zusammenhängend, kein Leerzeichen zwischen den beiden) | nur bei FR-Provider |
| Amtliche Warnungen | `!{Kürzel}:{Stufe}[@{h}]` … (Warn-Block, Marker `!` genau einmal) | nur bei aktiver amtlicher Warnung ab der wirksamen Kanal-Schwelle — Ortsvergleich weiterhin fest ab ORANGE, Trips seit Issue #1461 S3b-2a je Kanal einstellbar, Startwert bereits ab GELB (§3.4c) |
| Fire-Zonen | `Z: M:` | nur Korsika, weglassen wenn leer |
| Wintersport | `SD NS24+ SL AV` | optional (Kürzel seit #1435 E3b aus dem Wetter-Register, vorher `SN SN24+ SFL`; `WC` mit Fix #1887 entfallen, verdoppelte `FK`) |
| Nicht abrufbar | `X?` | nur wenn ≥1 abdeckende amtliche Warn-Quelle beim Fetch ausgefallen ist (§3.4d, Issue #1349; Kürzel seit Epic #1703 Scheibe 6 `X?`, vormals `W?` — Kollision mit dem Wind-Datenausfall-Marker) |
| Debug | `DBG[...]` | nur Dry-Run / Debug-Modus |

**Hinweis zu `HR:TH:`** — Das sind zwei separate Tokens, die ohne Leerzeichen aneinandergeschrieben werden (z.B. `HR:M@17TH:H@17` oder `HR:-TH:-`). Siehe §3.3 und §3.4.

**Hinweis zu `N` (Issue #1319 Scheibe D, 2026-07-23):** Im Abendbriefing ist `N` das erste Forecast-Token wie oben dargestellt. Im Morgenbriefing entfällt `N` vollständig aus der Zeile (nicht `N-`) — die Reihenfolge rutscht entsprechend nach: `{Name}: L D FL FD R PR W G TH: TH+: ...`.

**Hinweis zu `L`/`FL`/`FD`/`FN` (Issue #1410, 2026-07-28; Kürzel-Bindung nachgezogen durch Issue #1660, 2026-08-09; erneut geändert durch Issue #1728, 2026-08-15; Kürzel `K`→`L`/`FK`→`FL` seit Fix #1926, 2026-08-17):** `L` ist die Tiefsttemperatur **unterwegs** (kälteste Gehzeit-Stunde) und steht unabhängig neben `N` (Nacht am Schlafplatz) — beide erscheinen abends gemeinsam (`N` seit Issue #1484 nur bei gewählter eigener Metrik „Nacht-Tiefsttemperatur“), morgens nur `L`. Das `F`-Präfix bezeichnet die **gefühlte** Temperatur (`FN`/`FL`/`FD` als Parität zu `N`/`L`/`D`). `FN` folgt seit Issue #1660 — wie `N` seit #1484 — der eigenen wählbaren Metrik „Gefühlte Nacht-Tiefsttemperatur“ (`wind_chill_night`), statt wie zuvor an „Gefühlte Temperatur“ zu hängen.

> **Korrektur 2026-08-15 (Issue #1728 Scheibe 1):** Bis hierhin stand: „`FK`/`FD` bleiben an ‚Gefühlte Temperatur' (`wind_chill`) gekoppelt und folgen seit #1660 zusätzlich der dortigen Auswertungswahl (#1357): nur bei gewähltem ‚Tiefstwert' erscheint `FK`, nur bei gewähltem ‚Höchstwert' `FD`. Für `K`/`D` bei der Metrik ‚Temperatur' gilt seither dieselbe Regel (min→`K`, max→`D`)." Das ist überholt. `K`, `D`, `FK`, `FD` hängen jetzt an je einer **eigenen, unabhängig wählbaren** Katalog-Größe (`temperature_day_low`/`temperature_day_high`/`wind_chill_day_low`/`wind_chill_day_high`) — exakt nach dem Muster von `temperature_night`/`wind_chill_night` — statt an der Auswertungswahl (`MetricConfig.aggregations`) der Elterngröße. `temperature`/`wind_chill` bleiben als Katalogeinträge bestehen, liefern aber nur noch den **Stundenwert** für Stundentabelle und Telegram-Zelle (`COMPACT_LABEL_EXCEPTIONS`). **Korrektur 2026-08-16 (Fix #1887):** `WC` ist entfallen — s. §3.6/§9.

**Grundregel „gewählt / nicht gewählt” (PO-Entscheidung 2026-08-03, Issue #1415):** Für **jedes** Vorhersage-Kürzel gilt: geprüft, aber nichts über der Schwelle bzw. kein Wert ⇒ Null-Form (`R-`, `K-`); Metrik im Trip **abgewählt** ⇒ das Kürzel entfällt vollständig, auch die Null-Form. Eine dritte Stufe „Wert nicht abrufbar / Datenlücke im Fenster ⇒ `R?`” (#1328) gibt es bei den Schwellwert-Kürzeln `R`/`PR`/`W`/`G`/`TH:`/`TH+:` (`TH+:` seit Fix #1482, 2026-08-04) **und** seit Fix #1483 (2026-08-05, s. „Bekannte Ist-Abweichungen”) auch bei den Temperatur-Kürzeln `N`/`K`/`D`/`FN`/`FK`/`FD` (s. §4). Es gibt damit **keine unbedingten Vorhersage-Token** mehr: `N`/`K`/`D` verhalten sich seit #1415 exakt wie `FN`/`FK`/`FD`, und `TH+:` verhält sich seit #1482 exakt wie `TH:`. Die Bindung Kürzel→Metrik liegt an genau einer Stelle: `SMS_MULTI_SYMBOLS_BY_METRIC` (mehrere Kürzel je Metrik) bzw. `SMS_SYMBOL_BY_METRIC` (1:1). **Korrektur 2026-08-15 (Issue #1728):** Die Klammer-Zuordnung „`N`/`K`/`D` (Metrik „Temperatur")" bzw. „`FN`/`FK`/`FD` (Metrik „Gefühlte Temperatur")" ist entfallen — jedes der sechs Kürzel hängt seither an einer eigenen Metrik (s. Korrektur-Absatz oben). **Ungeprüfte, vorbestehende Datei-Angabe:** ob `SMS_MULTI_SYMBOLS_BY_METRIC`/`SMS_SYMBOL_BY_METRIC` noch in `src/output/renderers/sms_trip.py` *definiert* sind oder dort nur re-exportiert werden (Katalog-Kommentar in `metric_catalog.py:656` deutet seit #1719 S4 auf Letzteres hin), wurde für diese Korrektur nicht nachgemessen, ausgewertet in `trip_report.py` (`disabled_specs` → `output/tokens/builder.py::_visible()`).

**Bekannte Ist-Abweichungen (Stand 2026-08-05):** aktuell keine — die letzte offene Abweichung (Temperatur-Kürzel ohne `?`-Form) wurde mit Fix #1483 behoben, s. Blockquote unten.

> **Fix #1482 (2026-08-04):** Bis hierhin galten zwei zusätzliche Ist-Abweichungen bei `TH+:` — beide behoben. (a) `TH+:` hing an keinem Eintrag der Metrik-Bindung und erschien deshalb auch bei abgewählter Metrik „Gewitter”; es folgt jetzt derselben Bindung wie `TH:` über `SMS_MULTI_SYMBOLS_BY_METRIC[“thunder”]` (s. Zeile „Forecast (Gewitter Folge-Etappe)” oben). (b) `TH+:` konnte bei einer echten Datenlücke der Folge-Etappe nie `?` werden und zeigte stattdessen fälschlich die Entwarnung `TH+:-`; es zeigt jetzt `TH+:?`, wenn die Folge-Etappe existiert, ihre Gewitterdaten aber nicht beschaffbar waren. Unverändert bleibt `TH+:-`, wenn schlicht kein Folgetag existiert (letzte Etappe des Trips) — diese beiden Fälle dürfen nicht verwechselt werden (s. §3.2 und §4). `TH+:` nutzt außerdem denselben konfigurierten Gewitter-Schwellwert wie `TH:` (vorher hartkodierter Default). Details: `docs/specs/modules/fix_1482_th_plus_metrik_luecke.md`.

> **Fix #1483 (2026-08-05):** Bis hierhin gab es die `?`-Form nur für die Schwellwert-Kürzel `R`/`PR`/`W`/`G`/`TH:`/`TH+:`. Die Temperatur-Kürzel `N`/`K`/`D`/`FN`/`FK`/`FD` durchliefen stattdessen `render_temperature()`, das ausschliesslich Zahl oder `-` lieferte — eine Datenlücke erschien dort folglich als `K-` und war von „geprüft, kein Wert” nicht unterscheidbar. Jetzt nutzen beide Pfade denselben gemeinsamen Helfer `_gap_or()` (`builder.py:120-130`): `_mk_metric()` (Zeile 150, Schwellwert-Kürzel) UND die Temperatur-Schleife in `build_token_line()` (Zeile 299). `_wintersport()` (Schneehöhe/Neuschnee/Schneefallgrenze/Lawinenstufe/Windchill) bleibt bewusst unverändert und zeigt weiterhin nie `?` — es ruft `render_int()` über einen eigenen Pfad auf, der mit `_gap_or()` nichts zu tun hat. Details: `docs/specs/modules/fix_1483_temp_gap_marker.md`.

> **Fix #1677 (2026-08-10, v2.23):** Die in §2 gezeigte Token-Reihenfolge ist ab jetzt der **Default** — sie gilt unverändert, solange für den Kanal `sms` keine kanal-eigene Kaskadenebene aktiv ist (weder `per_report_layouts[report_type].sms` noch `per_channel_layouts.sms`, geprüft über `UnifiedWeatherDisplayConfig.cascade_source_for_channel("sms", report_type)`). Ist eine dieser beiden Ebenen gesetzt, bestimmt die dort im SMS-Kanal-Tab des Trip-Editors per Drag&Drop gezogene Reihenfolge die Anzeigefolge der **Vorhersage-** (`R PR W G TH: TH+: HU DP WD CP PT CT CL CM CH VS SU UV HP NL K D FK FD N FN`) und **Wintersport-Token** (`SD NS24+ SL AV`) — jede Metrik ist dabei EIN Anker: bei Mehrfach-Symbol-Metriken (`temperature`→`K D`, `temperature_night`→`N`, `wind_chill`→`FK FD`, `wind_chill_night`→`FN`, `thunder`→`TH: TH+:`) erben alle zugehörigen Symbole dieselbe Nutzer-Position, ihre interne Reihenfolge (z.B. `K` vor `D`) bleibt fix. **Unverändert fix, unabhängig von jeder Nutzer-Reihenfolge:** die Vigilance-Adjazenz `HR:TH:` (§3.3, ohne Leerzeichen), der amtliche Warn-Block, Fire (`Z: M:`), `X?` und `DBG` — diese System-Blöcke stehen immer hinter dem sortierbaren Block, in ihrer bisherigen relativen Reihenfolge (sie sind nicht Teil der wählbaren Metrik-Kaskade). Die Kürzung bei Überlänge (§6) bleibt unverändert prioritätsbasiert — die Anzeige-Position beeinflusst NICHT, welches Token zuerst fällt. Details: `docs/specs/modules/fix_1677_sms_reihenfolge.md`.

---

## 3. Token-Definitionen

### 3.1 Header

| Token | Bedeutung | Beispiel |
|-------|-----------|----------|
| `{Name}:` | Etappen-/Location-Name (max 10 Zeichen, ASCII) oder mit km-Bereich | `Ballone:` oder `GR221 km0-11:` |

**Name-Truncation & km-Bereichs-Bewahrung (Issue #936):**
1. Falten **zuerst** — Umlaute ersetzen (ä→ae, ö→oe, ü→ue, ß→ss) und alle sonstigen
   Nicht-ASCII-Buchstaben transliterieren, siehe §1 und ADR-0022
   (`docs/adr/0022-ascii-faltung-via-anyascii.md`). Nicht faltbare Buchstaben werden
   zu `?`, nicht gelöscht. Erst danach kürzen (Issue #1253: „erst falten, dann
   kürzen" gilt durchgängig für alle Kanäle, nicht nur den Header).
2. Auf "km" prüfen im Namen. Wenn gefunden:
   - Prefix vor "km" auf **max. 10 Zeichen** kürzen.
   - **Kompletten km-Bereich** (z.B. `km0-11`) bewahren und anhängen.
   - Beispiel: `GR221 Mallorca km0-11` → `GR221 km0-11:` (Name gekürzt, km-Teil vollständig).
3. Wenn kein "km": Standard-Truncation auf 10 Zeichen.
4. Trailingde Leerzeichen und `:` entfernen.

**Implementierung:** `_sanitize_stage_name()` in `src/output/tokens/builder.py`.

### 3.2 Forecast-Tokens

| Token | Bedeutung | Quelle (DTO-Feld) | Beispiel |
|-------|-----------|-------------------|----------|
| `N{temp}` / `N-` (**nur Abendbriefing**, nur bei aktivierter Metrik „Nacht-Tiefsttemperatur“, Issue #1484) | Nacht-Tiefsttemperatur °C am Schlafplatz, ganzzahlig — Fenster Ankunft→06:00 Folgetag am Etappenziel, NICHT das Tagessegment-Minimum. Im Morgenbriefing entfällt der Token komplett (kein `N-`). | `night_temp_min_c()` aus `night_weather` (Fallback: Tagessegment-`temp_min_c`, wenn `night_weather` fehlt/leer) | `N9` |
| `L{temp}` / `L-` (bis 2026-08-17 `K`/`K-`, Fix #1926; nur bei aktivierter Metrik „Tages-Tiefsttemperatur (Gehzeit)“, `temperature_day_low`, Issue #1728, 2026-08-15; bis dahin an aktivierter Metrik „Temperatur“ + Auswertungswahl „nur Tiefstwert“ gekoppelt) | Tiefsttemperatur **unterwegs** °C, ganzzahlig — kälteste Stunde der Gehzeit. Erscheint in BEIDEN Report-Typen und ist von `N` (Nacht am Schlafplatz) zu unterscheiden. Ist zusätzlich `temperature_day_high` aktiviert, entsteht statt `L`+`D` der Bereichs-Token (Zeile darunter, Issue #1824). | `day_window.collect_hiking_window_points()` → `hiking_field_min_max("t2m_c")`, MIN (Issue #1417) | `L3` |
| `D{temp}` / `D-` (nur bei aktivierter Metrik „Tages-Höchsttemperatur (Gehzeit)“, `temperature_day_high`, Issue #1728, 2026-08-15; bis dahin an „Temperatur“ gekoppelt) | Tag-Max °C, ganzzahlig — genauer: Höchstwert **während der Gehzeit**, nicht der Kalendertag (s. Hinweis unter der Tabelle) | dieselbe Quelle wie `L`, MAX | `D24` |
| `D{min}/{max}` (Issue #1824, **nur** wenn `temperature_day_low` UND `temperature_day_high` aktiviert sind) | Temperatur-**Spanne** der Gehzeit in einem Token. Trennzeichen ist `/`, nicht `-`: bei Minusgraden wäre der Bindestrich zugleich Trenner und Vorzeichen (`D-12--4` ist nicht eindeutig parsbar). `/` ist GSM-7-sicher. Jede Hälfte kann unabhängig Wert, Null-Form (`-`) oder Lückenform (`?`) sein (§4). | dieselbe Quelle wie `L`/`D` — MIN und MAX desselben Fensters | `D13/27`, `D-12/-4`, `D13/-` |
| `FD{min}/{max}` (Issue #1824, **nur** wenn `wind_chill_day_low` UND `wind_chill_day_high` aktiviert sind) | Gefühltes Pendant zum Bereichs-Token, gleiche Regel. | dieselbe Quelle wie `FL`/`FD` | `FD10/20` |
| `FN{temp}` / `FN-` (**nur Abendbriefing**, nur bei aktivierter Metrik „Gefühlte Nacht-Tiefsttemperatur“, `wind_chill_night`, Issue #1660) | **Gefühlte** Nacht-Tiefsttemperatur °C am Schlafplatz — Parität zu `N`, gleiches Fenster Ankunft→06:00 Folgetag. | `night_wind_chill_min_c()` aus `night_weather` (Fallback: Gehzeit-`wind_chill_min_c`) | `FN6` |
| `FL{temp}` / `FL-` (bis 2026-08-17 `FK`/`FK-`, Fix #1926; nur bei aktivierter Metrik „Gefühlte Tages-Tiefsttemperatur (Gehzeit)“, `wind_chill_day_low`, Issue #1728, 2026-08-15; bis dahin an „Gefühlte Temperatur“ + Auswertungswahl gekoppelt, Issue #1660 A) | **Gefühlte** Tiefsttemperatur unterwegs °C — Parität zu `L`, identisches Gehzeit-Fenster. | dieselbe Quelle wie `L`, aber `hiking_field_min_max("wind_chill_c")`, MIN | `FL1` |
| `FD{temp}` / `FD-` (nur bei aktivierter Metrik „Gefühlte Tages-Höchsttemperatur (Gehzeit)“, `wind_chill_day_high`, Issue #1728, 2026-08-15; bis dahin an „Gefühlte Temperatur“ gekoppelt) | **Gefühlte** Höchsttemperatur während der Gehzeit °C — Parität zu `D`. | dieselbe Quelle wie `FL`, MAX | `FD18` |
| `R{mm}@{h}({max}@{h})` / `R-` | Regen Threshold@Stunde + Peak | Hourly `precip_1h_mm`, Threshold aus `config.rain_amount_threshold` | `R0.2@6(1.4@16)` |
| `PR{p}%@{h}({max}%@{h})` / `PR-` | Regenwahrscheinlichkeit Threshold + Peak (Issue #887: auch SMS via `pop_hourly` aus `agg.pop_max_pct` synthetisiert) | Hourly `pop_pct`, Threshold aus `config.rain_probability_threshold` | `PR20%@11(100%@17)` |
| `W{v}@{h}({max}@{h})` / `W-` | Wind km/h Threshold + Peak | Hourly `wind10m_kmh`, Threshold aus `config.wind_speed_threshold` | `W10@11(15@17)` |
| `G{v}@{h}({max}@{h})` / `G-` | Böen km/h Threshold + Peak | Hourly `gust_kmh`, Threshold aus `config.wind_gust_threshold` | `G20@11(30@17)` |
| `TH:{level}@{h}({max}@{h})` / `TH:-` | Gewitter der **berichteten** Etappe (L/M/H — seit Issue #1474 vierstufig, `L`="leicht" besetzt den vorher unerreichbaren Token-Platz, s. `docs/reference/decision_matrix.md`) | Hourly `dp.thunder_level` aus `seg.timeseries`, auf die Wanderzeit gefenstert | `TH:M@16(H@18)` (bzw. `TH:L@16` bei reinem „leicht") |
| `TH:…+HL` (Suffix am `TH:`- bzw. `TH+:`-Token) | **Hagel-Kennzeichen** der berichteten Etappe (Issue #1475 S5a, 2026-08-04; Kürzel seit der Nachbesserung 2026-08-05 `+HL` statt vormals `+H`+`G`). Rein deskriptiv, kein eigenes Kürzel und keine eigene Truncation-Priorität — der Suffix hängt am Gewitter-Token, das er beschreibt, und fällt mit ihm. Gilt gleichermaßen für den Folgetag (`TH+:`). Erscheint **ausschließlich** bei bestätigtem Hagel (`hail_flag is True`, WMO-Code 96/99); „unbekannt“ (jeder andere Code, auch 95) und „nein“ lassen die Zeile **zeichengleich** — es gibt bewusst KEINE Null-Form `TH:…-HL`, weil der WMO-Code Hagel nur bejahen, nie verneinen kann | `dp.hail_flag` aus derselben Tagesfensterung wie `TH:`, aggregiert über `metric_format.hail_priority()` (ja > unbekannt > nein) | `TH:M@16(H@18)+HL` |
| `TH+:{level}@{h}({max}@{h})` / `TH+:-` / `TH+:?` | Gewitter der Etappe **danach**. `?` seit Fix #1482 (2026-08-04) bei einer echten Datenlücke (Folge-Etappe existiert, ihre Daten sind nicht beschaffbar) — `-` bleibt unverändert reserviert für „kein Folgetag“ (letzte Etappe des Trips), diese beiden Fälle dürfen nicht verwechselt werden | Folge-Etappe via `thunder_forecast["+1"]` (Level **und** Stunde) | `TH+:M@14(H@17)` bzw. `TH+:?` |

**`N` ist report-type-abhängig (Issue #1319 Scheibe D, 2026-07-23):** anders als `D R PR W G TH: TH+:`
hat `N` keine feste Sichtbarkeit — es erscheint ausschließlich im Abendbriefing. Wert-Quelle ist die
echte kommende Nacht am Schlafplatz (`night_weather`, Ankunft→06:00 Folgetag), dieselbe Quelle wie
die große E-Mail-Tabelle „🌙 Nacht am Ziel" (die unverändert bleibt). Fällt `night_weather` aus, greift
fail-soft der alte Tagessegment-Minimum-Wert. Spec: `docs/specs/modules/night_temp_evening_only.md`.

**EINE Gehzeit-Berechnung fuer alle Kanaele (Issue #1417, 2026-07-29; Kürzel `K`→`L`/`FK`→`FL` seit Fix #1926, 2026-08-17):** `L`, `D`,
`FL` und `FD` stammen aus derselben Quelle wie die Mail-Kachelzeile, die
E-Mail-Kurzzusammenfassung und die Telegram-Kurzuebersicht:
`day_window.collect_hiking_window_points()`. Vorher existierten mehrere
Implementierungen desselben Fensters — die Mail zaehlte die Ankunftsstunde des
letzten Etappenteils mit (#1146), SMS und Telegram nicht (#806/#807) —, wodurch
dieselbe Etappe je nach Kanal verschiedene Werte zeigte (`13–17°C` in der Mail
gegen `L13 D16` in der Kurznachricht). Die geltende Regel: **Ankunftsstunde des
letzten verwertbaren Teils inklusiv, innere Segmentgrenzen genau einmal.**
Ausgefallene Etappenteile werden bei der Bestimmung des „letzten" Teils
uebersprungen.

**`D` ist NICHT das Tagesmaximum.** Trotz des Namens „Tag-Max" bezieht sich `D`
— wie `L`/`FL`/`FD` — ausschliesslich auf die **Gehzeit**. Die tatsaechliche
Tageshoechsttemperatur am Ziel kann deutlich hoeher liegen (belegtes Beispiel:
`D16` bei realen 18,8 °C um 15:00). Das ist so gewollt (ADR-0025: die Temperatur
zaehlt, was der Wanderer unterwegs erlebt); nur die Benennung ist historisch
irrefuehrend. Regen/Gewitter/Wind zaehlen dagegen zusaetzlich die Stunden nach
der Ankunft (Tagesfenster 04–19, s. `sms_daywindow_aggregation.md`).

**Report-relativ, nicht kalender-relativ (Issue #1275):** `TH:` und `TH+:` beziehen sich auf die
Etappe, über die der Report spricht — nicht auf „heute"/„morgen" im Kalendersinn. Im
**Morgen-Report** ist das heute (`TH:`) und morgen (`TH+:`), im **Abend-Report** morgen (`TH:`)
und übermorgen (`TH+:`). Die frühere absolute Lesart war falsch.

Levels für `TH`/`TH+`:
- `M` = med (Averses orageuses)
- `H` = high (Orages)
- `-` = none

> `LEVELS` (`src/output/tokens/metrics.py:14`) kennt zusätzlich `L`. Dieser Wert ist
> **unerreichbar**: `ThunderLevel` (`src/app/models.py:33-37`) hat kein LOW, und
> `openmeteo.py:524-538` liefert ausschließlich HIGH oder NONE (WMO 95/96/99). `L` bleibt nur
> aus Golden-Snapshot-Kompatibilität im Code stehen und ist kein Teil des Format-Vertrags.

**Threshold-Logik:** `R`, `PR`, `W`, `G`, `TH`, `TH+` zeigen den **ersten Zeitpunkt** im Tagesfenster, an dem der konfigurierte Threshold erreicht/überschritten wird, gefolgt vom **Tagesmaximum** in Klammern. Wenn kein Wert ≥ Threshold: Token ist `R-` / `W-` / etc.

**Threshold-Konfiguration (Issue #624):** Die Schwellwerte für `R`, `PR`, `W`, `G` sind pro Trip und Metrik im Trip-Editor (Wetter-Metriken-Tab) optional konfigurierbar über `MetricConfig.sms_threshold`. Leeres Feld → bisheriges fest eingebautes Standardverhalten (Fallback auf `DEFAULTS` in builder.py). E-Mail-Tabelle nutzt weiterhin das separate `display_thresholds`-Farbkonzept (nicht vereinheitlicht).

### 3.2a Erweiterte Metrik-Tokens (Issue #1660 Scheibe B)

14 vorher wählbare, aber wirkungslose Metriken tragen jetzt ein SMS-Kürzel — Position im Format: eigener Block direkt nach `TH+:`, vor `C`/Vigilance (§2). Alle 14 folgen der Grundregel „gewählt/nicht gewählt" (§2): abgewählt entfällt das Kürzel vollständig, gewählt aber ohne Wert zeigt die Null-Form, Datenlücke macht daraus `?` (`_gap_or()`, s. §4).

Drei Wertegrammatik-Klassen:

- **(a) Threshold-Peak** (wie `R`/`W`/`G`, ganzzahlig): `HU` (Luftfeuchtigkeit %), `DP` (Taupunkt °C), `CP` (CAPE J/kg), `UV` (UV-Index), `CT`/`CL`/`CM`/`CH` (Bewölkung gesamt/tief/mittel/hoch %). Beispiel: `HU88@14(92@17)`.
- **(b) Invers-Min** (wie `SL`, aber MIT Stunde und Null-Form statt Weglassen): `VS` (Sichtweite, angezeigt in km mit einer Dezimale, DTO-Feld ist Meter), `FZ` (Nullgradgrenze, m ganzzahlig; bis 2026-08-17 `NL`, wegen Kollisionsvermeidung mit dem Schnee-/`SL`-Bereich auf `FZ` umgestellt, Fix #1926). Zeigt den Tages-**Tiefst**wert; mit konfiguriertem Schwellwert nur, wenn der Tiefstwert die Schwelle unterschreitet (`min <= threshold`), sonst Null-Form. Beispiel: `VS0.6@11`.
- **(c) Tageswert ohne Stunde:** `WD:` (dominante 8-Sektor-Windrichtung N/NO/O/SO/S/SW/W/NW, Beispiel `WD:NW`), `PT:` (dominante Niederschlagsart, Rang `FREEZING_RAIN`>`SNOW`>`MIXED`>`RAIN`, Codes `G`/`S`/`M`/`R`, Beispiel `PT:S`), `SU` (Sonnenstunden, gerundet), `HP` (Luftdruck-Tagesmittel hPa, gerundet).

**Doppelpunkt bei Buchstaben-Werten (Issue #1824, 2026-08-14):** `WD` und `PT` sind die einzigen beiden Kürzel, deren Wert mit einem **Buchstaben** beginnt — ohne Trenner verschmolzen Kürzel und Wert zu einem Wort (`WDNW`, `PTS`) und waren nicht mehr auseinanderzulesen. Sie tragen jetzt denselben Doppelpunkt wie `TH:`/`HR:`: der Trenner gehört zum **Symbol**, nicht zum Wert, wodurch Null- und Lückenform ihn automatisch mitziehen (`WD:-`, `WD:?`, `PT:-`, `PT:?`). Für den Trip-Editor ändert sich nichts — `/api/sms-symbols` schneidet den Doppelpunkt ab, die Badge bleibt `WD`/`PT`. Unberührt bleiben `DBG[...]` (Wert beginnt mit `[`) und `CL` (amtliches `access_ban`-Flag ohne Wert, §3.4c).

Alle 14 erscheinen unverändert in Morgen- **und** Abendbriefing (kein Nacht-Sonderfall wie `N`/`FN`). Quelle je Metrik: `docs/specs/modules/fix_1660b_sms_token_wiring.md` §3/§6, Kürzel-Register unverändert `metric_catalog.sms_code`.

### 3.3 Risk-Tokens (Vigilance-Warnungen, nur Frankreich)

Die zwei Tokens bilden einen **zusammenhängenden Block** ohne Leerzeichen dazwischen:

| Token | Bedeutung | Quelle | Beispiel |
|-------|-----------|--------|----------|
| `HR:{level}@{h}` / `HR:-` | Heavy Rain Vigilance (Pluie-inondation) | Météo France `get_warning_full()` | `HR:M@17` |
| `TH:{level}@{h}` / `TH:-` | Thunderstorm Vigilance (Orages) | Météo France `get_warning_full()` | `TH:H@17` |

Levels:
- `L` = 1 (Gelb)
- `M` = 2 (Orange)
- `H` = 3 (Rot)
- `R` = 4 (Violett)
- `-` = keine Warnung

**Beispiel zusammen:** `HR:M@17TH:H@17` (kein Trennzeichen zwischen `HR:` und `TH:`) bzw. `HR:-TH:-` wenn keine Warnungen.

**Geographische Geltung:** Météo France Vigilance API funktioniert nur für Frankreich. Außerhalb FR werden beide Tokens **komplett weggelassen** (nicht als `-` ausgegeben).

### 3.4 Disambiguierung geteilter Kürzel

Dasselbe Kürzel kann in mehreren Blöcken vorkommen — ein Phänomen trägt überall dasselbe Kürzel, unterschieden wird der **Block**. Zwei Mechanismen, in dieser Reihenfolge:

1. **Marker** (ab v2.9): alles ab dem `!` gehört zum amtlichen Warn-Block (§3.4c). Vorhersage-Tokens tragen nie ein `!`.
2. **Position** (unverändert seit v2.0): innerhalb der markerfreien Tokens unterscheidet die Position Forecast- von Vigilance-`TH:`:

| Position | Bedeutung | Quelle |
|----------|-----------|--------|
| Zwischen `G` und `TH+:` | Forecast-Gewitter heute (Wettervorhersage) | Hourly Wetterdaten |
| Direkt nach `HR:` (kein Space) | Vigilance-Gewitterwarnung (offizielle Warnung) | Météo France Vigilance API |

Parser erkennen den Unterschied durch:
- Forecast-`TH:` ist von Leerzeichen umgeben
- Vigilance-`TH:` folgt **direkt** auf `HR:` ohne Leerzeichen
- Amtliches `TH:` steht im `!`-Block (§3.4c)

### 3.4c Amtliche Warn-Token (`!`-Block, v2.9, Issue #1318)

Amtliche Unwetterwarnungen (`official_alerts`-Dienst, alle Provider) erscheinen als eigener Block am Ende der Vorhersage-Tokens, eingeleitet durch **genau ein** `!` vor dem ersten Warn-Token (1 Zeichen, GSM-7-sicher, kein Emoji). Die weiteren Warn-Tokens folgen mit normalem Leerzeichen, **ohne** zweites `!`.

| hazard | Kürzel | Bedeutung |
|--------|--------|-----------|
| `thunderstorm` | `TH` | Gewitter |
| `rain` | `HR` | Starkregen |
| `wind_gust` | `W` | Sturm |
| `snow` | `SN` | Schneefall |
| `black_ice` | `IC` | Glatteis |
| `extreme_heat` | `HT` | Hitze |
| `extreme_cold` | `CD` | Kälte |
| `wildfire_risk` | `FR` | Waldbrand-Gefahr |
| `access_ban` | `CL` | Zugang gesperrt |

**Single Source of Truth der Kürzel:** `src/output/tokens/hazard_symbols.py` — derselbe Katalog speist die Trip-Briefing-SMS, die eigenständige amtliche-Warnung-SMS (`render_official_alert_sms`) **und** die Compare-SMS (`render_compare_sms` in `src/output/renderers/comparison.py`, Issue #1332). Zwei getrennte Listen sind ein Fehler.

**Stufe:** dieselbe `L/M/H`-Skala wie die Vorhersage-Tokens, abgebildet gelb(2)→`L`, orange(3)→`M`, rot(4)→`H`.

**Filter (sicherheitsrelevant), seit Issue #1461 S3b-2a (Trips) / S3b-2b (Ortsvergleiche) auf die Startschwelle „gering" umgestellt:** Ursprünglich (bis 2026-08-05) fest — nur Stufe **orange (3) und rot (4)** erschienen, Gelb (2) und Grün (1) wurden vor dem Rendern verworfen. Für **Trips** ist die Schwelle Teil der Kanal-Einstellung `Trip.alert_channel_thresholds` (Startwert **gering**). Für den **Ortsvergleich** gibt es (Stand S3b-2b) keinen eigenen Kanal-Parameter am Bericht — `comparison.py` ruft den geteilten Kern seither mit der Startschwelle „gering" statt des vormals festen `MIN_SMS_LEVEL` auf; beim Startwert erscheint bereits **Gelb (2)**, unabhängig von der Alarm-Kanal-Schwelle desselben Ortsvergleichs (die regelt nur den Alarm-**Versand**, nicht diesen Bericht). Die alte feste Grenze (nur orange/rot) gilt beim Trip nur noch, wenn der Nutzer die Schwelle für einen Kanal auf „mittel" oder höher stellt. `L` bleibt im Mapping strukturell vorhanden, ist unterhalb der jeweils wirksamen Schwelle aber weiterhin nie sichtbar (analog zur `L`-Fußnote in §3.2). Quelle: `official_alerts_to_sms_entries(min_level=…)` (`official_alerts.py`) — `sms_trip.py`/`narrow.py` (Trip) übergeben die Nutzereinstellung, `comparison.py` (Compare) übergibt seit S3b-2b `min_official_level_for_threshold("LOW")`. Details: ADR-0046, Spec `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md`.

**Stunde `@h`:** erscheint, wenn die Warnung zu einer bestimmten Stunde beginnt (Beginn-Stunde in Ortszeit). Bei ganztägiger Gültigkeit entfällt sie ersatzlos — `W:M`, nicht `W:M@0`.

**Sonderfall `access_ban` (`CL`):** eine Zugangssperre ist ein binärer Zustand ohne Schweregrad (analog zu den `Z:`/`M:`-Fire-Tokens) — sie erscheint als blankes `CL` ohne Doppelpunkt und ohne Stufe, nie als `CL:H`, und trägt nie eine Stunde.

**Sortierung:** Stufe absteigend (rot vor orange), bei Gleichstand die Katalog-Reihenfolge der Tabelle oben — deterministisch, unabhängig vom Gültigkeitsbeginn.

**Truncation:** der Warn-Block trägt die höchste Priorität (11, §6) und fällt beim Kürzen als **letztes** — nach `PR`, `D`, `N` und selbst nach `W`/`G`/`TH:`.

**Unbekannte Gefahrenart (Rückfall-Kürzel):** Steht ein `hazard`-Wert **nicht** in der Tabelle oben (neu hinzukommender Provider-Typ), wird die Warnung **niemals verworfen** — `sms_symbol_for()` (`hazard_symbols.py`) bildet ein Kürzel aus den ersten zwei ASCII-Großbuchstaben des `hazard`-Strings, ersatzweise `XX`. Der Stufenfilter (siehe „Filter" oben — seit #1461 S3b-2b bei beiden Entitäten die Startschwelle „gering", Trips zusätzlich je Kanal einstellbar) bleibt davon unberührt wirksam; gefiltert wird ausschließlich nach Schwere, nie nach „Typ unbekannt".

Würde dieses Rückfall-Kürzel mit einem der neun vergebenen Katalog-Kürzel kollidieren (z. B. `thunder_squall` → `TH` wie eine echte Gewitterwarnung), wird deterministisch auf **drei** Buchstaben verlängert (`THU`, `SNO`); notfalls wird `X` angehängt. Da alle Katalog-Kürzel ein bis zwei Zeichen lang sind, kann ein dreistelliges Kürzel strukturell nicht kollidieren.

Beides ist sicherheitsrelevant, nicht kosmetisch: eine amtliche Warnung, die still verschwindet, ist der Schaden, den dieser Block verhindern soll (Präzedenz: fehlendes `wildfire_risk`-Mapping, Issue #1239); eine Warnung, die sich als **andere** Gefahr ausgibt, ist Fehlinformation in einer Sicherheitsmeldung. Dass die Provider-Adapter unbekannte Quell-Codes heute bereits beim Einlesen wegfiltern, macht den Rückfall nicht überflüssig — er ist das Netz für den Tag, an dem ein neuer Typ dazukommt. Vertraglich abgesichert durch AC-16/AC-17 in `docs/specs/modules/sms_official_alert_tokens.md`.

**Beispiele:**

```
Nur Vorhersage:   GR20 E5: N9 D24 R0.2@6 W10@11 TH:M@16
Mit Warnung:      GR20 E5: N9 D24 R0.2@6 W10@11 TH:M@16 !TH:H@14 W:M
Brand + Sperrung: GR20 E5: N9 D28 R- W12@11 TH:- !FR:H CL
Nicht abrufbar:   GR20 E5: N9 D24 R0.2@6 W10@11 TH:M@16 X?
```

### 3.4d Nicht-abrufbar-Marker `X?` (Issue #1349, Folge von #1348; Kürzel seit Epic #1703 Scheibe 6)

Ein **eigenständiger** Marker `X?` (2 Zeichen, GSM-7-sicher) signalisiert: für mindestens ein Segment ist **mindestens eine abdeckende amtliche Warn-Quelle beim Fetch ausgefallen** — „keine Warnung" bedeutet dann **nicht** sicher „alles ruhig". Semantisch das Kurzform-Pendant zum E-Mail-/Telegram-Hinweis „amtliche Warnungen aktuell nicht abrufbar".

**Kürzel-Historie:** Ursprünglich `W?` — kollidierte bytegleich mit dem Wind-Datenausfall-Marker (Wind-Symbol `W` + Gap-Wert `?`, `_gap_or()`), der unabhängig von einem Warn-Ausfall auftreten kann. Epic #1703 Scheibe 6 (AC-S6-6) hat das auf `X?` geändert — `X` ist im gesamten Wetter-Kürzel-Alphabet unbenutzt und dafür reserviert.

- **Bedingung:** `any(SegmentWeatherData.official_alerts_unavailable)` — gesetzt am echten Fail-soft-Pfad (`get_official_alerts_with_status`, #1348). Strenge Regel: **eine** ausgefallene abdeckende Quelle genügt.
- **Kein Warn-Block-Token:** `X?` gehört zur eigenen Kategorie `unavailable`, trägt **nie** den `!`-Marker (§3.4c) und darf nicht als amtliche Warnung („`!X?`") gelesen werden. Es ist „nicht abrufbar", nicht „es liegt eine Warnung vor".
- **Position:** am Ende der Zeile (nach Wintersport-Block, vor `DBG`), analog zum Verlässlichkeits-Symbol `C`.
- **Truncation:** höchste Priorität (12, §6, noch über dem Warn-Block) und **nicht** in der Drop-Liste — der sicherheitsrelevante Marker fällt unter 160-Zeichen-Druck **strukturell nie** weg.
- **Kanäle:** In Telegram-Kurzform (die `sms_text` sendet) erscheint `X?` automatisch mit; das Telegram-„rich"-Briefing und die Compare-/Trip-Mail zeigen stattdessen die ausgeschriebene Hinweiszeile bzw. den Banner.

Quelle des Flags: `src/output/tokens/dto.py` (`NormalizedForecast.official_alerts_unavailable`), Emission in `src/output/tokens/builder.py`. Vertraglich abgesichert durch `docs/specs/modules/feat_1349_sms_unavailable.md`.

### 3.4b Confidence-Symbol `C` (v2.1, Issue #121)

Einzelnes Zeichen, das die tagesweise Worst-Case-Konfidenz der Wettervorhersage signalisiert. Position: **nach `TH+:`, vor `HR:`/Vigilance-Tokens**.

| Wert | Symbol | Bedeutung |
|------|--------|-----------|
| `confidence_pct_min >= 75` | `C+` | Sichere Vorhersage |
| `50 <= confidence_pct_min < 75` | `C~` | Mittlere Sicherheit |
| `confidence_pct_min < 50` | `C?` | Unsichere Vorhersage |
| `confidence_pct_min is None` | _(Token weggelassen)_ | Kein Provider-Support |

**GSM-7-konform** — `+`, `~`, `?` sind alle Standard-GSM-7-Zeichen.

Aggregation: `min()` der stündlichen `confidence_pct` über alle Segmente des Tages.

Beispiel mit niedriger Konfidenz: `Etappe: N12 D22 R0.5 W15 G25 C?`

### 3.5 Fire-Risk-Tokens (Korsika-spezifisch)

Optional, nur für Trips in Korsika ausgegeben. Quelle: `risque-prevention-incendie.fr` (täglicher JSON-Feed).

| Token | Bedeutung | Beispiel |
|-------|-----------|----------|
| `Z:HIGH{ids}` | Fire-Zone Risk Level 2 (HIGH) | `Z:HIGH208,217` |
| `MAX{ids}` | Fire-Zone Risk Level 3 (MAX) | `MAX209` |
| `M:{ids}` | Restricted Massifs (Zugangsbeschränkungen) | `M:3,5,9` |

Der vollständige Block wird als zusammenhängender Abschnitt nach den Vigilance-Tokens platziert:

```
Z:HIGH208,217 MAX209 M:3,5,9
```

Wenn keine relevanten Zonen/Massifs aktiv sind: **Block komplett weglassen** (kein `Z:-`).

**Geographische Geltung:** Nur ausgeben wenn `trip.country == "FR"` und mindestens eine GR20-Zone betroffen ist.

### 3.6 Wintersport-Tokens (optional)

| Token | Bedeutung | Quelle |
|-------|-----------|--------|
| `SD{cm}` | Schneehöhe gesamt | `snow_depth_cm` |
| `NS24+{cm}` | Neuschnee 24h | `snow_new_24h_cm` |
| `SL{m}` | Schneefallgrenze | `snowfall_limit_m` |
| `AV{1-5}` | Lawinenstufe | `AvalancheReport.danger.level` |

> **Kürzel-Umstellung 2026-08-01 (#1435 E3b).** Schneehöhe hieß bis dahin `SN`,
> Neuschnee `SN24+`, Schneefallgrenze `SFL`. Die drei Kürzel stammen jetzt aus
> dem zentralen Wetter-Register (`metric_catalog.sms_code`: `SD`/`NS`/`SL`);
> das `24+`-Suffix beim Neuschnee bleibt Grammatik (24-Stunden-Fenster). Grund:
> `SN` bezeichnet in derselben Zeile die **amtliche Schneewarnung** (§3.4c,
> `hazard_symbols.py`) — diese bleibt unverändert `SN`, und kein Vorhersage-Token
> beginnt mehr so. Spec: `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md`.

Nur ausgeben wenn der Trip als Wintersport markiert ist (`trip.profile == "wintersport"`). Details siehe `docs/specs/wintersport_extension.md`.

> 🔴 **KORREKTUR 2026-08-11: `WC` IST im Produktivpfad erreichbar — und ist eine
> Wert-Dublette von `FK`.** Hier stand bis dahin das Gegenteil („im Produktivpfad
> nicht erreichbar … seit Einführung faktisch tot", Klarstellung v2.12, Issue
> #1410 §4). Das war zum Zeitpunkt der Formulierung richtig und ist seit
> **#1660 B** (2026-08-10) überholt: `SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"]
> = ("FK", "FD", "WC")` (`sms_trip.py:183`) erzeugt alle drei Symbole, sobald
> die Metrik `wind_chill` gewählt ist — unabhängig von `profile`.
>
> **Zweimal am laufenden Code gemessen** (2026-08-11): die reale Briefing-SMS
> des Trips KHW enthielt `FK10 … WC10`, eine Gegenprobe über
> `TripReportFormatter().format_email(...).sms_text` lieferte `FK1 … WC1`.
> **Beide Male trägt `WC` denselben Wert wie `FK`** (Quelle `day.wind_chill_c`,
> `builder.py:259`) — in einer auf 160 Zeichen gekürzten Nachricht verbraucht
> derselbe Messwert also zweimal Platz.
>
> **Korrektur 2026-08-15 (Issue #1728 Scheibe 1):** Die hier angekündigte
> Entscheidung „`WC` fällt mit #1728 ersatzlos weg" ist **nicht** eingetreten.
> PO-Entscheidung E3 (`docs/specs/modules/feat_1728_s1_temp_aufloesung.md`
> DEC-3): „WC soll bleiben" — `SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"] =
> ("WC",)` bleibt unverändert bestehen, zur Vermeidung von Regression #1450.
> Die Wert-Dublette zu `FK` bleibt damit ebenfalls unverändert bestehen. Eine
> als Entscheidung formulierte Ankündigung ist keine Zusicherung über
> künftigen Code — verwandt mit, aber nicht dieselbe Fehlerklasse wie im
> Absatz unten: dort überholte eine spätere Änderung eine zuvor wahre
> Aussage, hier erwies sich eine bereits zum Zeitpunkt des Schreibens
> geplante Änderung beim Umsetzen als nicht vollzogen.
>
> Unverändert richtig bleibt: `WC` ist **nicht** die gefühlte Temperatur des
> Trip-Briefings im Sinne der Auswahl — dafür stehen `FN`/`FK`/`FD` (§3.2).
>
> **Fehlerklasse, zur Warnung:** eine Aussage über den eigenen Code, die stimmte,
> dann durch eine Änderung überholt wurde und die niemand prüft. Dieselbe Klasse
> traf am selben Tag den Editor-Hinweis „SMS kennt keine Spalten-Reihenfolge"
> (seit #1677 falsch). Kein Test hält Dokumentationstexte gegen das tatsächliche
> Verhalten.
>
> **Korrektur 2026-08-16 (Fix #1887 Scheibe A):** `WC` entfällt jetzt
> ersatzlos — die oben zweimal am laufenden Code nachgewiesene Wert-Dublette
> zu `FK` war der Auslöser. Die PO-Freigabe zu #1887 legt die frühere Regel
> „verschieden von `FD` ⇒ bleibt" dem Sinn nach aus: die gemessene
> Redundanz betrifft `FK` (identisches Feld, Fenster und Aggregation), nicht
> `FD`. Damit ist auch die zuvor unter #1728 E3 getroffene Entscheidung „WC
> soll bleiben" abgelöst. Spec: `fix_1887_e6a_sms_kuerzel_register.md`.

### 3.7 Debug-Token

| Token | Bedeutung | Beispiel |
|-------|-----------|----------|
| `DBG[{provider} {confidence}]` | Provider-Auswahl + Konfidenz | `DBG[MET MED]` |

Nur in Dry-Run / Debug-Modus angehängt, ansonsten weggelassen.

---

## 4. Null-Repräsentation

| Token | Null-Form | Anmerkung |
|-------|-----------|-----------|
| `N` (nur Abend) | `N-` | Bei fehlender Nacht-Temperatur — **nur im Abendbriefing**; im Morgenbriefing fehlt der Token komplett (kein `N-`). **Nur** bei aktivierter Metrik „Nacht-Tiefsttemperatur“ (Issue #1484, vorher „Temperatur“ per #1415) — zur zusätzlichen `?`-Form bei Datenlücke s. Hinweis unten |
| `L` (bis 2026-08-17 `K`, Fix #1926) | `L-` | Bei fehlender Gehzeit-Tiefsttemperatur — **nur** bei aktivierter Metrik „Tages-Tiefsttemperatur (Gehzeit)“ (`temperature_day_low`, Issue #1728, 2026-08-15; bis dahin an aktivierter Metrik „Temperatur“ (Issue #1415) + Auswertungswahl „nur Tiefstwert“ gekoppelt) — zur zusätzlichen `?`-Form bei Datenlücke s. Hinweis unten |
| `D` | `D-` | Bei fehlender Tag-Temperatur — **nur** bei aktivierter Metrik „Tages-Höchsttemperatur (Gehzeit)“ (`temperature_day_high`, Issue #1728, 2026-08-15; bis dahin an „Temperatur“, Issue #1415, gekoppelt) — zur zusätzlichen `?`-Form bei Datenlücke s. Hinweis unten |
| `D{min}/{max}` bzw. `FD{min}/{max}` (Bereich, Issue #1824) | je Hälfte einzeln: `D13/-`, `D-/27`, `D-/-`, `D13/?`, `D?/?` | Jede Hälfte trägt unabhängig Wert, Null-Form oder Lückenform. Weil die `-`/`?`-Wahl heute an EINEM tagesweiten Lücken-Flag hängt, sind die gemischten Formen `D-/?` und `D?/-` praktisch nicht erreichbar — syntaktisch erlaubt sind sie dennoch |
| `FN` | `FN-` | **Nur** bei aktivierter Metrik „Gefühlte Nacht-Tiefsttemperatur“ (`wind_chill_night`, Issue #1660; vorher „Gefühlte Temperatur“, Issue #1410), wenn lediglich die Daten fehlen. Ist die Metrik nicht gewählt, erscheint gar nichts — auch keine Null-Form — zur zusätzlichen `?`-Form bei Datenlücke s. Hinweis unten |
| `FL` / `FD` (bis 2026-08-17 `FK`, Fix #1926) | `FL-` / `FD-` | **Nur** bei aktivierter Metrik „Gefühlte Tages-Tiefsttemperatur (Gehzeit)“ bzw. „Gefühlte Tages-Höchsttemperatur (Gehzeit)“ (`wind_chill_day_low`/`wind_chill_day_high`, Issue #1728, 2026-08-15; bis dahin gemeinsam an „Gefühlte Temperatur“ + Auswertungswahl gekoppelt, Issue #1660), wenn lediglich die Daten fehlen. Ist die jeweilige Metrik nicht gewählt, erscheint gar nichts — auch keine Null-Form (Issue #1410) — zur zusätzlichen `?`-Form bei Datenlücke s. Hinweis unten |
| `R` / `PR` | `R-` / `PR-` | Bei fehlendem oder Sub-Threshold-Niederschlag |
| `W` / `G` | `W-` / `G-` | Bei fehlendem oder Sub-Threshold-Wind |
| `TH` / `TH+` | `TH:-` / `TH+:-` | Bei fehlendem oder Sub-Threshold-Gewitter — zur zusätzlichen `?`-Form bei Datenlücke s. Hinweis unten |
| `HU`/`DP`/`CP`/`UV`/`CT`/`CL`/`CM`/`CH` | `HU-` usw. | Klasse (a), bei fehlendem oder Sub-Threshold-Wert — Issue #1660 Scheibe B, zusätzliche `?`-Form bei Datenlücke s. Hinweis unten |
| `VS` / `FZ` (bis 2026-08-17 `NL`, Fix #1926) | `VS-` / `FZ-` | Klasse (b), bei fehlenden Stundenwerten ODER wenn der Tiefstwert eine konfigurierte Schwelle NICHT unterschreitet (Invers-Gate) |
| `WD:` / `PT:` / `SU` / `HP` | `WD:-` / `PT:-` / `SU-` / `HP-` | Klasse (c), bei fehlendem Tageswert — anders als bei den Wintersport-Token (unten) gibt es hier eine Null-Form, kein komplettes Weglassen (DEC-3, `fix_1660b_sms_token_wiring.md`). Der Doppelpunkt bei `WD:`/`PT:` gehört zum Symbol und steht deshalb auch in Null- und Lückenform (Issue #1824, Muster `TH:-`) |
| `HR` / `TH` (Vigilance) | `HR:-TH:-` | Bei keiner Vigilance-Warnung; immer paarweise |
| `Z` / `M` (Fire) | komplett weglassen | Kein `Z:-`, einfach Block entfernen |
| `SD`/`NS24+`/`SL`/`AV` | komplett weglassen | Wintersport-Tokens nicht zwingend |
| `DBG` | komplett weglassen | Nur Debug-Modus |

**Zur `?`-Form (Issue #1328, erweitert um `TH+:` durch Fix #1482, um die Temperatur-Kürzel durch Fix #1483 (2026-08-04/05) und um die 14 erweiterten Metrik-Kürzel durch Issue #1660 Scheibe B, 2026-08-10; Kürzel `K`→`L`/`FK`→`FL`/`NL`→`FZ` seit Fix #1926, 2026-08-17):** Bei einer Datenlücke im ausgewerteten Fenster wird die Null-Form `-` zu `?` („unbekannt”) — das gilt für die Schwellwert-Kürzel `R`/`PR`/`W`/`G`/`TH:` des berichteten Tages sowie für `TH+:` der Folge-Etappe, wenn diese existiert, ihre Daten aber weder über den Trend-Pfad noch den Fallback-Fetch beschaffbar waren. Dieselbe Regel gilt für alle 14 Kürzel aus §3.2a (`HU`/`DP`/`WD`/`CP`/`PT`/`CT`/`CL`/`CM`/`CH`/`VS`/`SU`/`UV`/`HP`/`FZ`) — auch die vier Tageswert-Kürzel ohne Stunde (`WD`/`PT`/`SU`/`HP`) zeigen bei Datenlücke `?` statt `-`. Existiert schlicht kein Folgetag (letzte Etappe des Trips), bleibt es unverändert bei `TH+:-`, nie `TH+:?`. Seit Fix #1483 gilt dieselbe Regel auch für die Temperatur-Kürzel `N`/`L`/`D`/`FN`/`FL`/`FD` — eine Datenlücke im Fenster zeigt jetzt `N?`/`L?`/… statt `N-`/`L-`/…; fehlt lediglich der Wert ohne Datenlücke, bleibt es bei `-`. Beide Kürzel-Gruppen laufen über denselben gemeinsamen Helfer `_gap_or()` (`builder.py:120-130`), aufgerufen aus `_mk_metric()` (Zeile 150) bzw. der Temperatur-Schleife in `build_token_line()` (Zeile 299).

---

## 5. Werte-Formate

### Temperaturen
- Ganzzahlig gerundet (z.B. 9.1 → `9`, 9.7 → `10`).
- Negative Vorzeichen erlaubt: `N-12`, `D-5`.

### Niederschlag (mm)
- **Eine Nachkommastelle**, auch wenn die zweite `0` ist (z.B. `0.2`, `1.4`).
- Bei `0` Niederschlag: Token ist `R-` (nicht `R0.0`).

### Wind / Böen (km/h)
- Ganzzahlig.

### Wahrscheinlichkeit (%)
- Ganzzahlig (kein Dezimalzeichen).

### Stunden
- 0–23, ohne führende Null.

### Threshold == Max-Optimierung
- Wenn der Threshold-Wert exakt dem Tagesmaximum entspricht und beide am gleichen Zeitpunkt liegen, wird **nur der Threshold ausgegeben**, der `(max@h)`-Block entfällt. Beispiel: `W15@14` statt `W15@14(15@14)`.

---

## 6. Truncation-Strategie

Wenn die zusammengesetzte Token-Zeile >160 Zeichen ist, werden Tokens in dieser **Reihenfolge** entfernt:

1. `DBG[...]`
2. Die 14 erweiterten Metrik-Tokens aus §3.2a (`HU DP WD: CP PT: CT CL CM CH VS SU UV HP FZ`, Issue #1660 Scheibe B; `NL`→`FZ` seit Fix #1926) — fallen als erste Fachtoken, noch VOR den Wintersport-Größen
3. Wintersport-Tokens (`AV`, `SL`, `NS24+`, `SD`)
4. Fire-Block komplett (`Z:HIGH...`, `MAX...`, `M:...`)
5. Peak-Werte `(max@h)` (Threshold-Werte bleiben erhalten)
6. `FN`, `FL`, `FD` (gefühlte Temperaturen — Komfortangabe, fällt VOR den sicherheitsrelevanten Planungsgrössen, Issue #1410; `FK`→`FL` seit Fix #1926)
7. `PR` (Regenwahrscheinlichkeit)
8. `L`, `D`, `N` (gemessene Temperaturen — `L` zuerst, `N` zuletzt; bis 2026-08-17 `K`, Fix #1926). Ein Bereichs-Token `D{min}/{max}` (Issue #1824) fällt **als Ganzes** in einem Schritt: es gibt keinen Zwischenzustand, in dem nur der Tiefst- oder nur der Höchstwert übrig bleibt. Die Kürzung verliert dadurch im „beide gewählt"-Fall eine Granularitätsstufe gegenüber früher (bewusste Nebenwirkung)
9. Last Resort: verbleibende Forecast-/Vigilance-/Warn-Token nach aufsteigender `PRIORITY`, bis nur noch eines übrig ist (amtliche Warnungen fallen als allerletzte). Dieser Schritt existiert im Code seit jeher, fehlte aber bis v2.12 in dieser Aufzählung.

`{Name}:` plus mindestens **ein** Risk- oder Wert-Token ist Pflicht. Wenn nach allen Truncation-Schritten immer noch >160 Zeichen: ValueError.

---

## 7. Pflicht-Tokens

- `{Name}:` ist immer im Output.
- Mindestens **ein** Wert-/Risk-Token ist Pflicht (z.B. `TH:M@14`, `W22@14`, `R0.2@6` oder `HR:M@17`).
- Reine Null-Zeilen sind erlaubt und zeigen "alles ruhig" — Abendbriefing (alle
  gezeigten Metriken gewählt): `Ballone: N- D- R- PR- W- G- TH:- TH+:-`;
  Morgenbriefing (ohne `N`, Issue #1319): `Ballone: D- R- PR- W- G- TH:- TH+:-`.
- **Kein Vorhersage-Kürzel ist unbedingt** (Issue #1415): Jedes Kürzel setzt die
  zugehörige Metrik im Trip voraus; abgewählt entfällt es samt Null-Form. Wählt
  ein Nutzer gar keine Metrik, bleibt nur der Header — dann ist die
  „mindestens ein Token"-Regel oben nicht erfüllbar und auch nicht gemeint.

---

## 8. Beispiele

Alle Beispiele sind ≤160 Zeichen. Seit Issue #1319 Scheibe D (2026-07-23) fehlt `N` in
Morning-Report-Beispielen komplett (nicht `N-`); Beispiele ohne explizite Report-Typ-Kennzeichnung,
die `N` zeigen, sind als Abendbriefing zu lesen.

### 8.1 Morning Report (Forecast, kein Risiko)
```
Ballone: D16 R- PR10%@14(20%@17) W- G- TH:- TH+:-
```
**Länge:** 49 Zeichen. (Kein `N`-Token — Morgenbriefing.)

### 8.2 Morning Report (mit Schwellenwerten)
```
Paliri: D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17)
```
**Länge:** 102 Zeichen. (Kein `N`-Token — Morgenbriefing.)

### 8.3 Evening Report mit Vigilance + Fire-Block (Korsika)
```
Paliri: N8 D24 R0.2@6(1.4@16) PR20%@11(100%@17) W10@11(15@17) G20@11(30@17) TH:M@16(H@18) TH+:M@14(H@17) HR:M@17TH:H@17 Z:HIGH208 M:24
```
**Länge:** 134 Zeichen.

### 8.4 Update Report (nur kritische Werte)
```
Paliri: D24 G35@14(58@17) TH:H@15 HR:-TH:H@15
```
**Länge:** 46 Zeichen.

### 8.5 Wintersport
```
Arlberg: N-12 D-5 SD180 NS24+25 SL1800 AV3 W45@12 G78@14(85@16)
```
**Länge:** 63 Zeichen. (Bis Fix #1887 stand hier zusätzlich `WC-22` am Ende —
entfallen, verdoppelte den Wert von `FK`, s. §3.6/§9.)

### 8.6 Mit Debug
```
Monte: N15 D25 R- PR20%@14 W22@14(28@16) G35@14(48@17) TH:M@14 TH+:- DBG[MET MED]
```
**Länge:** 81 Zeichen.

### 8.7 Alles ruhig (alle Null)
```
Ballone: N9 D16 R- PR- W- G- TH:- TH+:-
```
**Länge:** 38 Zeichen.

---

## 9. Datenquellen-Mapping

| Token | Quelle | Aggregation | Status (gregor_zwanzig) |
|-------|--------|-------------|--------------------------|
| `N` (nur Abend, Issue #1319) | `night_weather` (Ankunft→06:00 Folgetag am Etappenziel) via `night_temp_min_c()`; Fallback `SegmentWeatherSummary.temp_min_c` wenn `night_weather` fehlt | MIN über `t2m_c` im Nachtfenster; im Morgenbriefing entfällt der Token komplett | ✅ vorhanden |
| `D` | `SegmentWeatherSummary.temp_max_c` (Tag-Segment) | MAX über alle Geo-Punkte | ✅ vorhanden |
| `R` | `precip_1h_mm` hourly | Threshold + MAX | ✅ vorhanden |
| `PR` | `pop_pct` hourly | Threshold + MAX | ✅ vorhanden |
| `W` | `wind10m_kmh` hourly | Threshold + MAX | ✅ vorhanden |
| `G` | `gust_kmh` hourly | Threshold + MAX | ✅ vorhanden |
| `TH` | `thunder_level` hourly | Threshold + MAX (NONE<LOW<MED<HIGH, seit Issue #1474 vierstufig) | ✅ vorhanden |
| `TH+` | Folgetag `thunder_level` | wie TH, aber +1 Tag | ✅ vorhanden |
| `HR` (Vigilance) | Météo France `get_warning_full()` | offizielle Warnung | ⚠️ Provider TODO |
| `TH` (Vigilance) | Météo France `get_warning_full()` | offizielle Warnung | ⚠️ Provider TODO |
| `!`-Warn-Block (§3.4c) | `SegmentWeatherData.official_alerts` (`official_alerts`-Dienst, alle Provider, 9 hazards) | Dedup (`dedupe_official_alerts`) + Filter Stufe ≥ Startschwelle „gering" (seit #1461 S3b-2a/S3b-2b, s. §2), Kürzel aus `hazard_symbols.py` | ✅ vorhanden (Issue #1318) — **andere Quelle** als die beiden Vigilance-Zeilen darüber, die weiterhin am alten `get_warning_full()`-Pfad hängen |
| `Z`/`M` | `risque-prevention-incendie.fr` | tagesaktueller JSON | ⚠️ Provider TODO |
| `SD`/`NS24+`/`SL` | GeoSphere/SLF | siehe Wintersport-Spec | ⚠️ teilweise vorhanden |
| `AV` | `AvalancheReport.danger.level` | aus Lawinenbericht | ⚠️ Provider TODO |
| `FN` / `FL` / `FD` (bis 2026-08-17 `FK`, Fix #1926) | `night_wind_chill_min_c` / `wind_chill_min_c` / `wind_chill_max_c` | Open-Meteo `apparent_temperature`, GeoSphere | ✅ vorhanden (Issue #1410) — `FL`/`FD` seit #1728 (2026-08-15) über die eigenen Metriken `wind_chill_day_low`/`wind_chill_day_high` gegated (s. §2) |
| `L` (bis 2026-08-17 `K`, Fix #1926) | `temp_min_c` (Gehzeit-Fenster) | Provider | ✅ vorhanden (Issue #1410) — seit #1728 (2026-08-15) nur bei aktivierter Metrik „Tages-Tiefsttemperatur (Gehzeit)“ (`temperature_day_low`); bis dahin hing das Kürzel an der Auswertungswahl „nur Tiefstwert“ von „Temperatur“. Ist zusätzlich `temperature_day_high` aktiv, trägt `D{min}/{max}` denselben Wert in der ersten Hälfte (Issue #1824) |
| `HU` | `humidity_pct` hourly | Threshold + MAX (Klasse a) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `DP` | `dewpoint_c` hourly | Threshold + MAX (Klasse a, nur `> 0`, s. Known Limitations) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `CP` | `cape_jkg` hourly | Threshold + MAX (Klasse a) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `UV` | `uv_index` hourly | Threshold + MAX (Klasse a) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `CT`/`CL`/`CM`/`CH` | `cloud_total_pct`/`cloud_low_pct`/`cloud_mid_pct`/`cloud_high_pct` hourly | Threshold + MAX (Klasse a) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `VS` | `visibility_m` hourly | Tages-MIN + Stunde, Anzeige in km (Klasse b, Invers-Gate) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `FZ` (bis 2026-08-17 `NL`, Fix #1926) | `freezing_level_m` hourly | Tages-MIN + Stunde (Klasse b, Invers-Gate) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `WD:` | `wind_direction_deg` hourly | dominanter 8-Sektor, Gleichstand → Sektor des Wind-Peaks (Klasse c) | ✅ vorhanden (Issue #1660 Scheibe B; Doppelpunkt seit #1824) |
| `PT:` | `precip_type` hourly | dominanter Typ, Gleichstand → Rang `FREEZING_RAIN`>`SNOW`>`MIXED`>`RAIN` (Klasse c) | ✅ vorhanden (Issue #1660 Scheibe B; Doppelpunkt seit #1824) |
| `SU` | Fensterpunkte via `WeatherMetricsService.calculate_sunny_hours()` | DNI-Interpolation, Fallback proportional bewölkt (Klasse c) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `HP` | `pressure_msl_hpa` hourly | arithmetisches Tagesmittel (Klasse c) | ✅ vorhanden (Issue #1660 Scheibe B) |
| `DBG` | `source.chosen`, `source.confidence` | aus DebugBuffer | ✅ vorhanden |

Markierte TODOs sind separate Issues, nicht Teil dieser Spec.

---

## 10. Geographische Einschränkungen

| Token-Block | Geltung | Verhalten außerhalb |
|-------------|---------|--------------------|
| Forecast (N…TH+) | global | immer ausgeben, **soweit die Metrik gewählt ist** (§2, Issue #1415) |
| Vigilance (`HR`/`TH`) | nur Frankreich | komplett weglassen (kein `-`) |
| Fire (`Z`/`M`) | nur Korsika (FR) | komplett weglassen |
| Wintersport (SD…AV) | AT/CH/Tirol/Südtirol/Trentino | komplett weglassen, wenn Provider fehlt |

---

## 11. Single Source of Truth

Diese Token-Zeile ist die **einzige verbindliche Repräsentation** der Wetterzusammenfassung. Alle anderen Formate leiten sich daraus ab:

| Channel | Verwendung |
|---------|-----------|
| SMS / Satellit | 1:1 die Token-Zeile (≤160 Zeichen) |
| E-Mail Subject | Auszug: `{Etappe} – {ReportType} – {MainRisk} – D{val} W{val} G{val} TH:{level}` |
| E-Mail Body | Token-Zeile als erstes, danach human-readable Summary + Tabellen |
| Push-Notification | Auszug der Token-Zeile (Titel) + Long-Form (Body) |
| Debug-Log | Token-Zeile + DebugBuffer-Inhalt |

Implementationen, die SMS-Text und E-Mail-Subject getrennt erzeugen, sind als **Bug** zu betrachten.

---

## 12. Versionierung & Quellen

| Version | Datum | Änderung |
|---------|-------|----------|
| 1.0 | 2025-12-27 | Initiale Spec mit N, D, R, PR, W, G, TH, TH+, DBG |
| 2.0 | 2026-04-25 | Vigilance-Block (HR/TH), Fire-Block (Z/M), Wintersport-Sektion, Disambiguierungs-Regel, vollständiges Datenquellen-Mapping |
| 2.1 | 2026-05-15 | Confidence-Symbol `C` (Issue #121) — GSM-7-konformes `+`/`~`/`?` nach `TH+:` |
| 2.2 | 2026-05-31 | WL-Token für Großwetterlage (Issue #122) — `+`/`~`/`-` nach `C`, vor `HR:`; Truncation NACH `C` aber VOR `PR` |
| 2.3 | 2026-05-31 | WL-Token aus SMS entfernt (Issue #479) — `C+/C~/C?` deckt den Stabilitäts-Use-Case ab; WL-Block bleibt nur in der E-Mail erhalten, jetzt aus `min(confidence_pct_min)` der Folge-Etappen abgeleitet statt aus Z500-Ensemble-API |
| 2.4 | 2026-06-06 | Konfigurierbare Threshold pro Metrik (Issue #624) — `MetricConfig.sms_threshold` optional per Metrik in `display_config` (Trip-Editor), Fallback auf `DEFAULTS`; E-Mail-Tabelle bleibt separate Logik |
| 2.5 | 2026-06-26 | SMS PR-Token-Befüllung (Issue #887) — `_segments_to_normalized_forecast()` in `sms_trip.py` erzeugt synthetisches `pop_hourly` aus `agg.pop_max_pct`, damit SMS-Token `PR{p}%` nicht mehr leer bleibt |
| 2.6 | 2026-07-01 | km-Bereichs-Bewahrung in Header (Issue #936) — `_sanitize_stage_name()` erkennt `km`-Marker und bewahrt vollständigen km-Bereich (z.B. `km0-11`) statt ihn nach 10 Zeichen abzuschneiden; Prefix gekürzt, km-Teil vollständig |
| 2.7 | 2026-07-13 | Faltungs-Konvention auf alle Schriften erweitert (Issue #1253) — bisher nur Umlaute; einzige Quelle jetzt `fold_ascii()` in `src/utils/ascii_fold.py` (ADR-0022: `anyascii` + deutsche Digraph-Map + zeichenweiser `?`-Guard gegen stille Buchstaben-Löschung), gilt jetzt durchgängig „erst falten, dann kürzen" auch im SMS-Titelzeilen-Pfad (`_sms_stage_prefix`) |
| 2.8 | 2026-07-16 | `TH+`-Datenquelle korrigiert (Issue #1275) — aggregiert jetzt über ALLE Segmente der tatsächlichen Folge-Etappe (statt nur das letzte Segment der heutigen Etappe zu prüfen) und nutzt dieselbe Fetch-/Aggregations-Kette wie die E-Mail-Outlook-Tabelle (`_build_stage_trend()`); stimmt dadurch garantiert mit deren Wert überein |

| 2.9 | 2026-07-20 | Amtlicher Warn-Block `!` in der Trip-Briefing-SMS (Issue #1318) — 9 internationale Gefahren-Kürzel aus dem einzigen Katalog `src/output/tokens/hazard_symbols.py` (§3.4c), Filter ab Stufe ORANGE, `@h` nur bei nicht-ganztägigem Beginn, `CL` ohne Stufe, höchste Truncation-Priorität; §3.4 von positions- auf marker-basierte Disambiguierung verallgemeinert; die eigenständige amtliche-Warnung-SMS nutzt denselben Katalog (alte deutsch abgeleitete Kürzel `HZ`/`ST`/`RR`/`GL`/`ZG`/`WB`/`KL` entfallen ersatzlos) |
| 2.10 | 2026-07-23 | Compare-SMS zeigt jetzt denselben `!`-Warn-Block (Issue #1332, Bugfix) — `render_compare_sms` (`src/output/renderers/comparison.py`) nutzt `official_alerts_to_sms_entries`/`sms_symbol_for` aus demselben Katalog wie die Trip-Briefing-SMS; vorher zeigte die Compare-SMS gar keine amtlichen Warnungen |
| 2.11 | 2026-07-23 | `N` (Nacht-Tiefsttemperatur) nur noch im Abendbriefing (Issue #1319 Scheibe D) — Morgenbriefing lässt den Token komplett weg (kein `N-`); Wert-Quelle wechselt abends von `SegmentWeatherSummary.temp_min_c` (Tagessegment) auf `night_weather` (Ankunft→06:00 Folgetag am Ziel), Fallback aufs alte Verhalten wenn `night_weather` fehlt; große E-Mail-Tabelle „🌙 Nacht am Ziel" bleibt unverändert. Spec: `docs/specs/modules/night_temp_evening_only.md` |
| 2.12 | 2026-07-28 | Tiefsttemperatur unterwegs + gefühlte Temperatur in der SMS (Issue #1410, Epic #1372) — neue Token `K` (kälteste Gehzeit-Stunde, immer, neben `N`) sowie `FN`/`FK`/`FD` (gefühlte Parität zu `N`/`K`/`D`, nur bei aktivierter Metrik `wind_chill`); `N` liest jetzt das eigene DTO-Feld `night_temp_min_c` statt `temp_min_c` in-place zu überschreiben (`K` bleibt dadurch abends erhalten); Kürzungsreihenfolge um den Felt-Schritt VOR `PR` erweitert und der im Code seit jeher vorhandene Last-Resort-Schritt nachgetragen (Doku-Drift §6); `WC` als Legacy-CLI-only gekennzeichnet (§3.6/§9). Löst DEC-2 aus `night_temp_evening_only.md` ab (morgens jetzt Spanne statt Einzelwert). Spec: `docs/specs/modules/trip_min_temp_and_felt_shortforms.md` |
| 2.13 | 2026-07-29 | EINE Gehzeit-Berechnung fuer alle Kanaele (Issue #1417) — `K`/`D`/`FK`/`FD` stammen jetzt aus `day_window.collect_hiking_window_points()`, derselben Quelle wie Mail-Kachelzeile, E-Mail-Kurzzusammenfassung und Telegram-Kurzuebersicht. Vorher unterschiedliche Fenster je Kanal (Ankunftsstunde in der Mail inklusiv, in SMS/Telegram nicht) — dieselbe Etappe zeigte je nach Kanal verschiedene Werte. Geltende Regel: Ankunftsstunde des letzten VERWERTBAREN Teils inklusiv, innere Grenzen genau einmal; ausgefallene Teile werden uebersprungen. Quellenspalten in §3.2 entsprechend praezisiert; Klarstellung ergaenzt, dass `D` trotz des Namens „Tag-Max" die Gehzeit meint und nicht den Kalendertag. Spec: `docs/specs/modules/hiking_window_single_source.md` |

| 2.14 | 2026-08-01 | Schnee-Kürzel folgen dem Wetter-Register (Issue #1435 Etappe E3b) — Schneehöhe `SN`→`SD`, Neuschnee `SN24+`→`NS24+`, Schneefallgrenze `SFL`→`SL` (`metric_catalog.sms_code`). Grund: `SN` bezeichnete in derselben Zeile zugleich die **amtliche Schneewarnung** (§3.4c, `hazard_symbols.py`) — diese bleibt unverändert `SN`, kein Vorhersage-Token beginnt mehr so. Position im Format, Kürzungs-Rangfolge (§6) und die inverse Schwellwertlogik der Schneefallgrenze (#873) unverändert; gespeicherte Nutzereinstellungen liegen als `metric_id` vor und bleiben wirksam. `TH:` (Grammatik) und `WC`/`FN`/`FK`/`FD` bleiben bewusste Ausnahmen. Spec: `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md` |

| 2.15 | 2026-08-03 | Gemessene Temperatur folgt der Metrik-Auswahl (Issue #1415, PO-Entscheidung) — `N`/`K`/`D` waren die letzten unbedingten Vorhersage-Token und erschienen auch bei abgewählter Metrik „Temperatur“ (Beleg aus einer echt zugestellten SMS: `E3: K13 D16 FK13 FD16 R12.2@20 …` mit ausgeschalteter Temperatur). Jetzt gilt für **jedes** Kürzel dieselbe Zweiteilung: geprüft, aber kein Wert ⇒ Null-Form (`K-`), abgewählt ⇒ Kürzel entfällt vollständig. Die dritte Stufe „nicht abrufbar ⇒ `R?`“ (#1328) gibt es unverändert nur bei den Schwellwert-Kürzeln; für die Temperatur-Kürzel existiert sie nicht (`render_temperature()` kennt nur Zahl oder `-`) — als bekannte Ist-Abweichung in §2 vermerkt, Entscheidung offen. Umsetzung über denselben Weg wie `FN`/`FK`/`FD` (#1410): die Mehrfach-Tabelle in `sms_trip.py`, umbenannt von `SMS_FELT_SYMBOLS_BY_METRIC` zu `SMS_MULTI_SYMBOLS_BY_METRIC` und um `"temperature": ("N", "K", "D")` ergänzt — kein zweiter Bindungsweg. §2 (Pflicht-Spalte), §3.2, §4 (Null-Formen), §7 (Pflicht-Token) und §10 entsprechend nachgezogen; die verbliebene Ist-Abweichung `TH+:` ist unter §2 ausdrücklich vermerkt. |
| 2.16 | 2026-08-04 | Doku-Nachtrag (Issue #1474, ohne Codeänderung an dieser Datei) — `TH:`/`TH+:` sind seit der bereits gemergten Vorgänger-Scheibe (`860a3baf`, 2026-08-03) vierstufig: `L`("leicht") besetzt den vorher unerreichbaren Token-Platz neben `M`/`H` (`NONE<LOW<MED<HIGH`). §3.2 und §9 zeigten bis hierhin noch die alte Dreistufigkeit — nachgetragen im Zuge der Folge-Scheibe `fix-1474-gewitterschwelle-cockpit`, die dieselbe Ordinalskala für die Erwähnungsschwelle nutzt. Details: `docs/reference/decision_matrix.md` Abschnitt „Gewitter-Stufen“. |
| 2.17 | 2026-08-04 | `TH+:` folgt jetzt exakt derselben Grundregel wie `TH:` (Fix #1482) — löst die beiden in v2.15 unter §2 vermerkten Ist-Abweichungen auf: (1) `TH+:` hängt jetzt an der Metrik-Bindung „Gewitter“ (`SMS_MULTI_SYMBOLS_BY_METRIC["thunder"]`) und verschwindet bei abgewählter Metrik, statt wie bisher immer zu erscheinen; (2) `TH+:` kann jetzt `TH+:?` zeigen, wenn die Folge-Etappe existiert, ihre Gewitterdaten aber nicht beschaffbar waren — vorher zeigte dieser Fall fälschlich die Entwarnung `TH+:-`. Unverändert: `TH+:-` bleibt reserviert für „kein Folgetag“ (letzte Etappe des Trips). Zusätzlich (PO-bestätigt bei Spec-Freigabe): `TH+:` nutzt jetzt denselben im Trip-Editor konfigurierten Gewitter-Schwellwert wie `TH:` statt eines hartkodierten Defaults. Betrifft §2 (Token-Tabelle, Grundregel-Absatz, Bekannte Ist-Abweichungen), §3.2 (`TH+:`-Zeile), §4 (Null-Repräsentation, `?`-Form-Hinweis). Spec: `docs/specs/modules/fix_1482_th_plus_metrik_luecke.md`. |
| 2.18 | 2026-08-05 | Temperatur-Kürzel zeigen jetzt `?` bei Datenlücke (Fix #1483) — löst die in v2.15 unter §2 vermerkte Ist-Abweichung auf: `N`/`K`/`D`/`FN`/`FK`/`FD` zeigten bei einer Datenlücke im ausgewerteten Fenster bislang fälschlich `-` statt `?`, obwohl die Schwellwert-Kürzel `R`/`PR`/`W`/`G`/`TH:`/`TH+:` diesen Fall längst über dieselbe Regel signalisierten. Umsetzung: neuer gemeinsamer Helfer `_gap_or()` (`builder.py:120-130`), extrahiert aus der bisherigen Inline-Zeile in `_mk_metric()` (Zeile 150) und zusätzlich von der Temperatur-Schleife in `build_token_line()` (Zeile 299) genutzt — reines Verhaltens-Angleichen, keine neue Bedingung. `_wintersport()` bleibt bewusst unverändert und zeigt weiterhin nie `?` (kein gemeinsamer Aufrufpfad mit `_gap_or()`). Betrifft §2 (Grundregel-Absatz, Bekannte Ist-Abweichungen), §4 (Null-Repräsentation, `?`-Form-Hinweis). Spec: `docs/specs/modules/fix_1483_temp_gap_marker.md`. |
| 2.19 | 2026-08-05 | Der `!`-Warn-Block-Filter (§3.4c) ist für **Trips** keine feste Grenze mehr — Issue #1461 S3b-2a lässt die bisher fest verdrahtete `MIN_SMS_LEVEL`-Schwelle (orange) in der neuen, je Alarm-Kanal einstellbaren Kanal-Schwelle (`Trip.alert_channel_thresholds`) aufgehen. Startwert **gering** je Kanal ⇒ der Trip-Briefing-SMS-/Telegram-Text zeigt künftig auch **gelbe** (Stufe 2) amtliche Warnungen, die vorher nie erschienen; die alte feste Grenze bleibt nur erhalten, wenn der Nutzer die Schwelle bewusst auf „mittel“ oder höher setzt. Der Alarm-**Versand** (`render_official_alert_sms`) war schon vorher ungefiltert und bleibt unverändert. Der **Ortsvergleich** (`comparison.py`) behält den festen Vorgabewert, bis Folgescheibe S3b-2b ihn nachzieht. §2 (Token-Tabelle) und §3.4c entsprechend präzisiert. ADR-0046, Spec: `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md`. |
| 2.20 | 2026-08-06 | Folgescheibe S3b-2b: der `!`-Warn-Block-Filter des **Ortsvergleichs** (`comparison.py`) geht ebenfalls auf die Startschwelle „gering" über — `render_compare_sms`/`render_compare_telegram` rufen den geteilten Kern jetzt mit `min_official_level_for_threshold("LOW")` statt des vormals festen `MIN_SMS_LEVEL` (orange). Der Compare-SMS-/Telegram-Bericht zeigt künftig auch **gelbe** (Stufe 2) amtliche Warnungen, die vorher nie erschienen. Anders als beim Trip gibt es dafür keinen eigenen, je Kanal einstellbaren Bericht-Parameter — die neue Alarm-Kanal-Schwelle des Ortsvergleichs (`ComparePreset.alert_channel_thresholds`) regelt ausschließlich den Alarm-**Versand**, nicht diesen Bericht (derselbe Zielkonflikt wie beim Trip, gleiche Auflösung). §2 (Token-Tabelle) und §3.4c entsprechend präzisiert. ADR-0046, Spec: `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md`. |
| 2.21 | 2026-08-09 | Temperatur-Trennung Scheibe A (Issue #1660): (1) `FN` hängt nicht mehr an „Gefühlte Temperatur" (`wind_chill`), sondern an der neuen eigenen wählbaren Metrik „Gefühlte Nacht-Tiefsttemperatur" (`wind_chill_night`) — exakt analog zu `N`/`temperature_night` seit #1484; `FK`/`FD`/`WC` bleiben bei `wind_chill`. (2) Die seit #1357 vorhandene Auswertungswahl (Spanne/Tiefstwert/Höchstwert/Mittelwert je Metrik) wirkt jetzt auch in der SMS: `K` nur bei gewähltem „Tiefstwert", `D` nur bei „Höchstwert" (Metrik „Temperatur"); `FK`/`FD` analog bei „Gefühlte Temperatur"; „Nur Mittelwert" entfernt beide Token der jeweiligen Größe ersatzlos, kein Rückfall auf die Spanne. `N`/`FN` sind von der Auswertungswahl unberührt (eigene Metriken ohne Auswertungswahl). Betrifft §2 (Token-Reihenfolge-Tabelle, Hinweis zu `K`/`FK`/`FD`/`FN`), §3.2 (`FN`-Zeile), §4 (Null-Repräsentation). Spec: `docs/specs/modules/fix_1660a_temp_trennung.md`. |
| 2.22 | 2026-08-10 | SMS-Token-Verdrahtung Scheibe B (Issue #1660): 14 bisher wählbare, aber wirkungslose Metriken bekommen ein Kürzel — `HU`/`DP`/`WD`/`CP`/`PT`/`CT`/`CL`/`CM`/`CH`/`VS`/`SU`/`UV`/`HP`/`NL` (Kürzel unverändert `metric_catalog.sms_code`, kein neuer Katalogeintrag). Drei Wertegrammatik-Klassen: Threshold-Peak (HU/DP/CP/UV/CT/CL/CM/CH, wie `R`/`W`/`G`), Invers-Min mit Stunde (VS/NL, wie `SL` aber mit `{min}@{h}` statt reinem Tageswert und Null-Form statt Weglassen), Tageswert ohne Stunde (WD/PT/SU/HP). Position: eigener Block nach `TH+:`, vor `C`/Vigilance (§2); Kürzungsrang direkt nach `DBG`, vor den Wintersport-Token (§6, DROP_ORDER). Erscheinen in Morgen- und Abendbriefing gleich (kein Nacht-Sonderfall). Betrifft §2, neuer §3.2a, §4, §6, §9. Spec: `docs/specs/modules/fix_1660b_sms_token_wiring.md`. |

| 2.24 | 2026-08-11 | 🔴 **Korrektur einer Falschaussage, keine Formatänderung.** §3.6 und §9 behaupteten, `WC` sei „im Produktivpfad nie erreichbar" und „seit Einführung faktisch tot" (v2.12, #1410 §4). Das stimmte damals und ist seit **#1660 B** (2026-08-10) überholt: `SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"] = ("FK","FD","WC")` erzeugt alle drei Symbole, sobald `wind_chill` gewählt ist — unabhängig von `profile`. Zweimal am laufenden Code gemessen (reale KHW-Briefing-SMS `FK10 … WC10`; Gegenprobe über `format_email(...).sms_text` → `FK1 … WC1`): **`WC` trägt denselben Wert wie `FK`**, verbraucht in der 160-Zeichen-Grenze also doppelt Platz. `WC` fällt mit **#1728** ersatzlos weg. Fehlerklasse: eine Aussage über den eigenen Code, die durch eine spätere Änderung überholt wurde und die kein Test gegen das Verhalten hält — dieselbe Klasse traf am selben Tag den Editor-Hinweis „SMS kennt keine Spalten-Reihenfolge" (seit #1677 falsch, →#1719 S3). **[Korrektur 2026-08-15, s. v2.27: die angekündigte Entfernung von `WC` ist NICHT eingetreten — PO-Entscheid #1728 E3 „WC soll bleiben", s. §3.6/§9.]** |
| 2.25 | 2026-08-13 | Präzisierung zu §1 (Zeichensatz), keine Formatänderung. `fold_ascii()` bleibt die einzige Quelle für **Buchstaben**-Transliteration, deckt aber die GSM-7-**Extension-Tabelle** (Form-Feed, `^{}\[~]\|€`) nicht ab — diese Zeichen sind bereits ASCII/kein Buchstabe und liefen bei amtlichen Alarm-SMS (§ „Amtliche Warnungen") unverändert durch, was die SMS-Kodierung still auf UCS-2 umschaltet (67 statt 153 Zeichen je Teil). Fix in `alert/render.py::_ascii()`: feste Ersetzungstabelle `_ASCII_EXTENSION_REPLACEMENTS`, angewendet vor `fold_ascii()`. Betrifft nur den amtlichen-Alarm-SMS-/Premium-SMS-Pfad (`render_official_alert_sms`), nicht das Trip-Briefing (`sms_trip.py`, dort bislang kein Fund). Issue #1796, Spec: `docs/specs/modules/fix_1796_official_alert_gsm7_extension.md`. |

| 2.26 | 2026-08-14 | **Zwei Formatänderungen aus der Lektüre eines echten KHW-Briefings (Issue #1824).** (A) **Bereichs-Token:** Sind bei „Temperatur“ bzw. „Gefühlte Temperatur“ BEIDE Auswertungen gewählt, stehen Tiefst- und Höchstwert nicht mehr als zwei Token (`K13 D27`), sondern als einer: `D13/27` (gefühlt `FD10/20`). Trennzeichen ist `/`, nicht `-` — bei Minusgraden wäre der Bindestrich zugleich Trenner und Vorzeichen (`D-12--4`), `/` ist GSM-7-sicher und im Format sonst unbenutzt. `K`/`FK` bleiben eigenständige Kürzel und bedeuten weiterhin **immer** den Tiefstwert (PO-Entscheid 2026-08-13: ein `D13` mit tatsächlichem Tiefstwert wäre auf einem tourenentscheidungs-relevanten Kanal Falschinformation); bei „nur Tiefstwert“ bzw. „nur Höchstwert“ ändert sich nichts. `N`/`FN`/`WC` unberührt. Der Bereich fällt beim Kürzen als eine Einheit (§6). (B) **Trenner bei Buchstaben-Werten:** `WD`→`WD:`, `PT`→`PT:` — die einzigen zwei Kürzel mit buchstabenbeginnendem Wert bekommen denselben Doppelpunkt wie `TH:`/`HR:`; der Trenner gehört zum Symbol, weshalb Null- und Lückenform ihn mitziehen (`WD:-`, `WD:?`). `/api/sms-symbols` schneidet ihn wieder ab — die Editor-Badge bleibt `WD`/`PT`. Netto-Zeichenwirkung an einer echten Briefing-Zeile: −3 (A) +2 (B) = **−1**. Betrifft §2, §3.2, §3.2a, §4, §6, §9; löst AC-6/AC-7 aus `fix_1660b_sms_token_wiring.md` ab. Spec: `docs/specs/modules/feat_1824_sms_range_und_trenner.md`. |
| 2.27 | 2026-08-15 | **Temperatur-Auflösung Scheibe 1 (Issue #1728) — die Auswertungswahl steuert `K`/`D`/`FK`/`FD` nicht mehr.** Vier neue, eigenständig wählbare Katalog-Größen (`temperature_day_low`/`temperature_day_high`/`wind_chill_day_low`/`wind_chill_day_high`) übernehmen die Sichtbarkeits-Gates dieser vier Kürzel von der bisherigen Auswertungswahl (`MetricConfig.aggregations`) der Elterngrößen „Temperatur"/„Gefühlte Temperatur" — exakt nach dem Muster von `temperature_night`/`wind_chill_night` (#1484/#1660 A). `temperature`/`wind_chill` bleiben als Katalogeinträge bestehen und liefern weiterhin den Stundenwert für Stundentabelle und Telegram-Zelle; `WC` bleibt unverändert an `wind_chill` gebunden (PO E3, „WC soll bleiben" — **löst die in v2.24 angekündigte, nie umgesetzte Entfernung ab**, s. §3.6/§9-Korrekturen). Das Bereichs-Token-Verhalten aus v2.26 ist unverändert, greift jetzt aber, wenn **beide** neuen Tagesrichtungs-Größen aktiviert sind, statt bei „beide Auswertungen gewählt". Betrifft §2, den Hinweis zu `K`/`FK`/`FD`/`FN`, §3.2, §3.6, §4, §9. Reine Backend-Scheibe — der Trip-Editor zeigt bis Scheibe 2 weiterhin die (jetzt wirkungslose) alte Auswertungswahl für „Temperatur"/„Gefühlte Temperatur" an. Spec: `docs/specs/modules/feat_1728_s1_temp_aufloesung.md`. |
| 2.28 | 2026-08-16 | **`WC` entfällt ersatzlos (Fix #1887 Scheibe A).** Löst die in v2.27 (PO E3, #1728) getroffene Entscheidung „WC soll bleiben" ab — die PO-Freigabe zu #1887 legt die Regel „verschieden von `FD` ⇒ bleibt" dem Sinn nach aus: die nachgewiesene Wert-Dublette betrifft `FK`, nicht `FD`. Die sechs Trip-SMS-Mehrfach-Kürzel `K`/`D`/`N`/`FK`/`FD`/`FN` kommen jetzt aus dem neuen Register-Feld `MetricDefinition.sms_multi_symbols` statt aus einer handgetippten Nebentabelle (`SMS_MULTI_SYMBOLS_BY_METRIC` wird zur reinen Ableitung). Die zwei toten `sms_code`-Werte `TD` (`temperature_day_high`) und `TN` (`temperature_night`) sind auf `""` gesetzt — kein Leser erreichte sie je; `temperature`/`temperature_cold`/`wind_chill` behalten unverändert `D`/`N`/`TF`. Betrifft §2 (Format-Zeile, Token-Tabelle, `K D`/`FK FD`-Hinweis, Fix-#1677-Absatz), §3.6 (Token-Tabelle, Korrektur-Block), §4 (Null-Repräsentation), §5 (Beispielwerte), §6 (Truncation-Reihenfolge), §8.5 (Beispiel), §9 (Datenquellen-Mapping), §10 (Geltungsbereich). Spec: `docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md`. |
| 2.29 | 2026-08-17 | **Drei Register-Kürzel geändert (Fix #1926, PO-Konsistenzentscheid).** `K`→`L` (Tages-Tiefsttemperatur, Gehzeit) und `FK`→`FL` (gefühlte Tages-Tiefsttemperatur, Gehzeit) — reine Konsistenz-Fixes ohne Sprachbezug (ADR-0042 Klasse 1 bleibt von Sprachfragen ausgenommen). `NL`→`FZ` (Nullgradgrenze) zur Kollisionsvermeidung mit dem Schnee-/`SL`-Bereich. Alle drei neuen Werte kollisionsfrei gegen alle 32 Katalog-Einträge geprüft. Betrifft §2 (Format-Zeile, Token-Tabelle, `L D`/`FL FD`-Hinweis), §3.2 (Token-Tabelle, Gehzeit-Berechnung-Absatz), §3.2a (Invers-Min-Klasse), §4 (Null-Repräsentation), §6 (Truncation-Reihenfolge), §9 (Datenquellen-Mapping). Historische, datierte Korrektur-Absätze (§3.6, die WC/FK-Dublette vom 2026-08-11 ff.) bleiben mit dem damaligen Kürzel-Namen stehen. Spec: `docs/specs/modules/fix_1926_metrik_kuerzel_englisch.md`. |

**Quellen für v2.0:**
- Vorgänger-Repo `henemm/weather_email_autobot`:
  - `requests/morning-evening-refactor.md` (HR + Vigilance-TH)
  - `src/utils/risk_block_formatter.py` (Z + M)
  - `src/fire/risk_block_formatter.py` (HIGH/MAX-Logik)
- Bestehende gregor-Specs:
  - `docs/specs/wintersport_extension.md` §5 (Wintersport-Tokens)
  - `docs/reference/renderer_email_spec.md` §2 (Token line is single source of truth)
