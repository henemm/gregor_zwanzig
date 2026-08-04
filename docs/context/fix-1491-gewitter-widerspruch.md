# Context: fix-1491-gewitter-widerspruch

Issue: [#1491](https://github.com/henemm/gregor_zwanzig/issues/1491) · Track: Full Process ·
Stand bei Aufnahme: `a75a5ae5`

## Request Summary

Dieselbe Briefing-Mail sagt für dieselbe Stunde an zwei Stellen „Gewitter" und an einer
dritten „keins": Kurzfassung und Prosa-Pille melden „⚡ möglich 13:00–14:00" bzw.
„Gewitter ab 13:00", die Stundentabelle zeigt in der Spalte `Thdr` für 13 und 14 einen
Strich. Der Widerspruch soll verschwinden — und zwar an der Wurzel, nicht durch
Nachziehen der Tabelle auf gut Glück.

## Befund der Kontext-Recherche: die Ursache ist eine dritte, im Issue nicht genannte

Das Issue nennt zwei Hypothesen (Fusion läuft nicht / verschiedene Datenpunkte). Beide
sind nach der Aktenlage **unwahrscheinlich**, weil alle drei Textstellen **dasselbe Feld
am selben Datenpunkt** lesen:

| Stelle in der Mail | liest | Verhalten bei Stufe „leicht" (`LOW`) |
|---|---|---|
| Kurzfassung (Etappenzeile) | `dp.thunder_level != NONE` (`compact_summary.py:548`) | meldet „⚡ möglich" ✅ |
| Prosa-Pille | `dp.thunder_level` + `thunder_ordinal()` (`email/helpers.py:1577`) | meldet „Gewitter ab …" ✅ |
| **Stundentabelle, Spalte `Thdr`** | `dp.thunder_level` → `fmt_val()` (`email/helpers.py:618`) | **Strich bzw. „kein"** ❌ |

Gemessen am Code dieses Stands (direkter Aufruf, keine Behauptung):

```
ThunderLevel.NONE   Symbol='–'        Roh-Modus='kein'
ThunderLevel.LOW    Symbol='–'        Roh-Modus='kein'     <-- identisch zu NONE
ThunderLevel.MED    Symbol='⚡ mögl.'  Roh-Modus='mögl.'
ThunderLevel.HIGH   Symbol='⚡⚡'      Roh-Modus='hoch'
```

`fmt_val()` kennt im `thunder`-Zweig nur `HIGH` und `MED` und fällt für alles Übrige auf
`"–"` (Symbol-Modus) bzw. `"kein"` (Roh-Modus) durch. Die mit #1474 eingeführte Stufe
`LOW` wurde dort **nicht ergänzt** — an allen anderen Stellen sehr wohl (`outlook.py:170`,
`compare_html.py:166`, `_THUNDER_MAP` `helpers.py:744`, `_TREND_THUNDER_LABELS`
`helpers.py:864`, `risk_engine.py:130`, `trip_report_scheduler.py:1557/1722`).

Der Roh-Modus ist dabei der schlimmere Fall: die Tabelle sagt dann nicht nur nichts,
sondern behauptet aktiv **„kein"**.

Bestätigend: Wäre die Fusion (Hypothese 1) nicht gelaufen, wäre `dp.thunder_level` leer
und **auch die Pille hätte geschwiegen**. Sie hat gesprochen — also lag `LOW` am
Datenpunkt an. Bleibt als Restzweifel nur, ob Pille und Tabelle wirklich dieselbe Reihe
sehen; das ist der erste Messpunkt der Analyse-Phase.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/helpers.py:578-635` | **`fmt_val()` — der Ursachen-Kandidat.** Zellformatierer, `thunder`-Zweig ohne `LOW` |
| `src/output/renderers/email/helpers.py:93-121` | `dp_to_row()` — legt den Rohwert `dp.thunder_level` in die Zeile |
| `src/output/renderers/email/helpers.py:124-139` | `extract_hourly_rows()` — Stundenzeilen im Segmentfenster |
| `src/output/renderers/email/helpers.py:1568-1600` | Prosa-Pille „Gewitter ab HH:00 · stärkste HH:00" |
| `src/output/renderers/email/html.py:725-800` | HTML-Tabelle: ruft `fmt_val`, färbt die Zelle über `_thunder_risk_level` (kennt `LOW` ✅) |
| `src/output/renderers/email/plain.py:56,71` | Klartext-Teil der Mail — **derselbe** `fmt_val` |
| `src/output/renderers/narrow.py:76,440` | Schmale Darstellung — **derselbe** `fmt_val` |
| `src/output/renderers/compact_summary.py:539-561` | Kurzfassung „⚡ möglich HH:00–HH:00" |
| `src/output/metric_format.py:217-353` | Skala, Ordnung, `THUNDER_LABEL_DE`, `thunder_level_from_signals()` |
| `src/providers/thunder_enrichment.py` | Der eine gemeinsame Anschluss; `_fuse_thunder_levels()` schreibt `dp.thunder_level` |
| `src/app/metric_catalog.py:279-296` | Katalogeintrag `thunder`: `col_key="thdr"`, `default_format_mode="symbol"`, `format_modes=("raw","symbol")` |

## Existing Patterns

- **Eine geteilte Wortquelle:** `metric_format.THUNDER_LABEL_DE` (`kein/leicht/mittel/hoch`).
  #1474 hat `outlook.py` und `compare_html.py` bewusst darauf umgestellt statt Wörter zu
  kopieren. `fmt_val()` führt bis heute **eigene, hartcodierte** Wörter/Symbole.
- **Skala nie über rohe Zahlen ansprechen** — `thunder_ordinal()` / `thunder_label_value()`
  sind die kanonischen Zugänge (`metric_format.py:232/255`).
- **Fail-soft in der Anreicherung:** fehlender Wert bleibt `None`, wird nie `0`
  („keine Aussage" ≠ „keine Gefahr").

## Dependencies

- **Upstream:** `thunder_enrichment.enrich_thunder()` (nur Open-Meteo-Pfad,
  `openmeteo.py:1023,1143`) → `thunder_level_from_signals()` → `dp.thunder_level`.
  CAPE ≥ 1000 J/kg allein ergibt `LOW`; CAPE ist bei `LOW` gedeckelt.
- **Downstream von `fmt_val()`:** HTML-Mail, Klartext-Mail, schmale Darstellung.
  Eine Korrektur dort wirkt in allen dreien gleichzeitig — das ist gewollt und der
  Grund, warum es genau **eine** Stelle sein muss.

## Existing Specs

- `docs/specs/modules/feat_1474_gewitter_befund_stufen.md` — führt Stufe „leicht" ein
- `docs/specs/modules/fix_1474b_gewitterschwelle_cockpit.md` — EIN Erwähnungs-Regler
- `docs/specs/modules/feat_1457_s2a_blitzdichte_meteofrance.md`, `…_s2b_gewitter_dwd_alpen.md`
- `docs/specs/modules/fix_1418_gewitter_risikopunkt.md` — Risikopunkt + Zellfärbung
- `docs/adr/` — ADR-0025 (kein ungefenstertes Aggregat als Tor für Kanal-Aussagen)

## Risks & Considerations

1. **Wortwahl ist eine Produktentscheidung, keine technische.** Was in der Zelle stehen
   soll, wenn „leicht" vorliegt, muss der PO festlegen (Symbol-Modus und Roh-Modus
   getrennt). Frei erfinden wäre der Fehler aus #1453.
2. **Zwei Achsen nie vermischen:** „leicht/mittel/hoch" ist **Stärke**;
   „möglich/wahrscheinlich/akut" ist **Sicherheit** (#1419). Die Kurzfassung sagt heute
   „möglich" für eine Stärke-Stufe — beim Formulieren der Zelle nicht nachahmen, ohne es
   bewusst zu entscheiden.
3. **`fmt_val()` ist von drei Renderern geteilt.** Jede Änderung wirkt auf HTML-Mail,
   Klartext und schmale Darstellung. Kein Sonderweg je Renderer.
4. **Renderer-Mail-Gate #811** greift bei `email/helpers.py`: Modus-Matrix-Test **und**
   `briefing_mail_validator.py` müssen auf dem finalen Dateistand frisch laufen.
5. **Mutations-Gegenprobe:** ein Test, der nur `fmt_val` direkt aufruft, beweist wenig.
   Die Zusicherung wirkt in der **gerenderten Mail** — dort muss sie geprüft werden
   (Leitfrage aus #1457: an der Stelle prüfen, wo es wirkt, nicht wo der Code steht).
6. **Restzweifel offen halten:** dass Pille und Tabelle dieselben Datenpunkte sehen, ist
   plausibel, aber noch nicht gemessen. Trifft es nicht zu, gibt es einen **zweiten**
   Fehler zusätzlich zum Formatierer.
7. **Nicht mitreparieren:** #1488 (Beschriftungen im Frontend) berührt dieselbe
   Ordinal-Verschiebung, ist aber ein eigenes Ticket.

---

## Analysis (Phase 2, gemessen 2026-08-04)

### Type

**Bug.** Eine Ursache, gesichert.

### Messergebnis

Eine vollständige Briefing-Mail wurde über den echten Renderer-Pfad
(`TripReportFormatter.format_email()`) mit einem synthetischen Datenpunkt
`thunder_level = LOW`, CAPE 1310 J/kg gerendert — ohne Netz, ohne Versand:

| Stelle | Ausgabe |
|---|---|
| Kurzfassung | `… ⚡ möglich 13:00–14:00` ✅ |
| Prosa-Pille | `Gewitter ab 13:00 · stärkste 13:00` ✅ |
| Stundentabelle HTML, Zeile 13 | `<td style="…background:#fad6b8;…" data-label="Thdr">–</td>` ❌ |
| Stundentabelle Klartext, Zeile 13 | `… 0.0    –      –       ⛅ …` ❌ |

**Der aussagekräftigste Einzelbefund:** die Zelle ist **bereits orange eingefärbt**
(`#fad6b8` = Warnstufe „watch"). Die Färbung kennt `LOW` also korrekt
(`html.py:155` `_thunder_risk_level`) — nur der **Zellinhalt** ist leer. Eine orange
Warnzelle mit einem Strich darin ist der Widerspruch in Reinform.

- **M2 (offene Frage aus dem Issue geklärt):** Prosa-Pille und Stundentabelle sehen für
  13:00 per Objektidentität (`id()`-Vergleich) **dasselbe Datenpunkt-Objekt**.
  ⇒ Hypothese 1 und 2 des Issues sind **ausgeschlossen**. **Eine** Ursache.
  *Einschränkung:* gemessen an einem Segment ohne Nachtblock und ohne
  Mitternachtsgrenze. Die beiden Fenster-Funktionen sind strukturell unabhängig und
  könnten an Segmentgrenzen divergieren — hier taten sie es nicht.
- **M3 (Vollständigkeit):** systematischer Durchgang aller `ThunderLevel`-Fundstellen in
  `src/`. **Kein zweiter blinder Fleck.** Kurzfassung, Prosa-Pille, Zellfarbe,
  Mehrtages-Trend (`outlook.py`, `compare_html.py`), Telegram-Fußzeile und -Ausblick
  (`narrow.py`), Telegram-Inbound (`trip_command_processor.py`), SMS-Token
  (`tokens/metrics.py` `{0:"-",1:"L",2:"M",3:"H"}`), Risiko-Engine, Korridor-Markierung
  und Compare-Katalog kennen `LOW` bereits alle korrekt.
- **M4 (Bestandsschutz):** `tests/tdd/test_issue_811_mode_matrix.py` prüft den
  `thunder`-Zweig über echtes Rendern — aber nur für `MED`, `HIGH`, `NONE`.
  **Kein einziger Test im Repo prüft `LOW` an dieser Stelle.** Genau deshalb ist die
  Lücke durch #1474 gekommen. Ein Fix macht keinen bestehenden Test rot.

### Affected Files

| Datei | Änderungsart | Beschreibung |
|---|---|---|
| `src/output/renderers/email/helpers.py` (`fmt_val`, Zweig `thunder`) | MODIFY | `LOW` ergänzen; Wörter aus der geteilten Quelle statt hartcodiert |
| `tests/tdd/test_issue_811_mode_matrix.py` | MODIFY | `LOW`-Fälle ergänzen (Symbol- und Roh-Modus) |
| Verhaltenstest (neu, Name nach Verhalten) | CREATE | Widerspruchsfreiheit **an der gerenderten Mail** prüfen |

### Scope Assessment

- Dateien: 2–3 · geschätzt +40/−10 LoC · Risiko: **LOW–MEDIUM**
- Risiko-Treiber: `fmt_val()` ist von HTML-Mail, Klartext-Mail und schmaler Darstellung
  geteilt; Renderer-Mail-Gate #811 greift bei `email/helpers.py`.

### Technical Approach

Eine Stelle, ein Fix: `fmt_val()` bekommt den fehlenden `LOW`-Zweig. Weil dieselbe
Funktion drei Renderer bedient, wirkt die Korrektur überall gleichzeitig — kein
Sonderweg je Renderer.

**Der Test muss an der Wirkstelle prüfen, nicht an der Funktion.** Ein Test, der nur
`fmt_val("thunder", LOW)` aufruft, hätte diesen Bug ebenfalls nicht gefunden, wenn er
neben `test_811` gestanden hätte. Die Zusicherung lautet: *in einer gerenderten Mail
darf keine Stelle Gewitter melden, während die Stundentabelle für dieselbe Stunde
schweigt.* Genau das gehört geprüft.

### PO-Entscheidungen (2026-08-04, eingeholt am Ende der Analyse)

Der PO hat den Zuschnitt erweitert: **die Gewitter-Spalte bekommt in der einfachen
Ansicht den farbigen Ampel-Kreis wie jede andere Metrik — kein Blitz-Emoji mehr.**

1. **Einfache Ansicht (HTML) = Ampel-Kreis.** Vier Stufen ↔ vier Ampel-Farben, 1:1:
   `kein → grün · leicht → gelb · mittel → orange · hoch → rot`.
   Das Blitzsymbol (`⚡` / `⚡⚡`) und das achsenfremde Wort „mögl." entfallen dort.
2. **Ruhige Stunde zeigt einen grünen Kreis**, keinen Strich — genau wie Wind und Regen.
   Begründung des PO-Votums: ein Strich könnte auch „keine Daten" heißen; der grüne Kreis
   sagt „geprüft und ruhig".
3. **Text-Fassung der Mail (kein HTML) = das Wort:** `kein / leicht / mittel / hoch` —
   dieselben vier Wörter, die der Rest der Mail über `THUNDER_LABEL_DE` bereits benutzt.
   Damit verschwindet „mögl." auch dort.
4. **Zell-Tönung muss auf dieselbe Quelle wie der Kreis.** Heute kommt sie aus
   `_thunder_risk_level` (`html.py:155`), das nur zwei Warnstufen kennt und „leicht" wie
   „mittel" orange färbt. Bliebe das so, widerspräche ein **gelber** Kreis dem **orangen**
   Hintergrund — der nächste Widerspruch in derselben Zelle. Regel aus #888: Punkt und
   Tönung stammen aus einer Quelle.

### Konsequenz für den Zuschnitt

Aus „ein fehlender Zweig" wird „die Gewitter-Spalte wird eine reguläre Ampel-Metrik".
Betroffen ist zusätzlich zu `fmt_val()`:

| Datei | Änderungsart | Beschreibung |
|---|---|---|
| `src/output/renderers/email/helpers.py` | MODIFY | `fmt_val`-Zweig `thunder`: Ampel-Kreis (HTML) bzw. Wort (Text); Wörter aus `THUNDER_LABEL_DE` |
| `src/output/renderers/email/html.py` | MODIFY | Zell-Tönung auf die vierstufige Quelle ziehen (`_thunder_risk_level` kennt nur zwei) |
| ggf. `src/app/metric_catalog.py` | MODIFY | Gewitter aus der Ampel-Ausnahme entlassen — Stufen→Farbe braucht eine Abbildung, `display_thresholds` passt auf Zahlen nicht |

Die Ampel-Kreis-Bausteine existieren bereits (`_ampel_dot_css`, `_AMPEL_DOT_COLORS`,
`severity_for`) — sie erwarten heute aber eine **Zahl** und Katalog-Schwellen. Gewitter
liefert eine **Stufe**. Der saubere Weg ist eine Stufe→Ampelband-Abbildung an der
kanonischen Stelle (`metric_format.py`, dort wohnt die Skala, ADR-0025) statt einer
Sonderlogik im Renderer. Neu geschätzt: **3–4 Dateien, ~+70/−25 LoC**.
