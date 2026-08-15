# Context: #1680 Scheibe 5 — Herkunft der Gewitterstufe im Mehrtages-Ausblick und in der Gewitter-Vorschau

**Erstellt:** 2026-08-13 · **Workflow:** `feat-1680-s5-ausblick-vorschau-herkunft` · **Track:** Full Process
**Basis:** `origin/main` @ `2d96b346` (S4 `b6daae3e` enthalten)

## Request Summary

Die letzten beiden Ausgabeorte aus #1680 sollen die tragende Zutat der
Gewitterstufe nennen: der **Mehrtages-Ausblick** (`⚡leicht · nachts leicht @20`)
und die **Gewitter-Vorschau** (`↳ Gewitter möglich`). Beide wurden in den
Scheiben 1–4 viermal ausgeklammert mit der Begründung, sie seien "strukturell
blockiert" durch `HourlyValue` (nur `hour`/`value`) und den unangeschlossenen
`aggregate_stage()`.

## 🔴 Die übernommene Begründung hält der Messung nur zur Hälfte stand

Das ist zum dritten Mal dieselbe Lehre (S1 AC-12, S2 "übernommene Notiz"): eine
von Scheibe zu Scheibe weitergereichte Behauptung über den eigenen Code wurde
nie nachgemessen.

| Behauptung aus S1–S4 | Messung (2026-08-13) |
|---|---|
| "Der Mehrtages-Ausblick ist der **erste echte Verbraucher** von `aggregate_stage()`" | **Halb falsch.** `aggregate_stage()` läuft dort zwar (`trip_report_scheduler.py:2026`), aber die **angezeigte** Gewitterstufe kommt NICHT aus `agg.thunder_level_max`, sondern aus den Stundenproben `hourly_thunder` (`outlook.py:234-243`, `helpers.py:1007-1020`). `agg` speist nur `row["thunder"]`, das seinerseits **nur als Fail-soft** dient, wenn keine Stundenprobe im Fenster liegt (`outlook.py:239-243`, `trip_report_scheduler.py:2284-2291`). |
| "Die Träger gehen strukturell verloren, weil `HourlyValue` nur `hour`/`value` hat" | **Zutreffend für den Transportweg, aber die Quelle liegt vor der Verengung.** `build_outlook_row(summary, points, …)` (`outlook.py:420ff`) bekommt die **rohen `ForecastDataPoint`s** als `points` übergeben (`trip_report_scheduler.py:2046-2049`) und baut die `HourlyValue`-Tupel erst selbst (`outlook.py:463-477`). `ForecastDataPoint.thunder_level_signals` ist dort verfügbar (gesetzt in `providers/thunder_enrichment.py:151`). Die Träger sind also **in der Hand des Row-Builders** — die Verengung ist selbstgemacht und umgehbar, ohne `HourlyValue` anzufassen. |

**Folge:** Der Weg über `agg.thunder_level_max_signals` wäre der **falsche** — er
verletzte die AC-12-Regel aus Scheibe 1 ("passt die Herkunft nicht zur gezeigten
Stufe, erscheint keine"), weil `agg` das **Kalendertags-Maximum** trägt, die
angezeigte Stufe aber das **Tagesfenster-Maximum** ist. Beide können
auseinanderfallen — genau der Fehler, den #1498 Fall 2 und #1653 bereits
repariert haben.

## 🔴 Ein latenter Fehler, der heute schon erreichbar ist

`weather_metrics.py:478` deklariert seit Scheibe 1:
```python
"thunder_level_max_signals": "union_of_max_carriers",
```
`aggregate_stage()` (`weather_metrics.py:1168-1266`) hat aber **keinen Zweig**
für diese Regel — sie fällt in den generischen `else`: `values[0]`
(`weather_metrics.py:1265-1266`). Bei einer Etappe mit mehreren Segmenten
liefert das die Trägerliste des **ersten** Segments, auch wenn ein anderes
Segment die Höchststufe trägt.

Das ist **kein rein theoretischer Pfad**: `aggregate_stage()` läuft im
Ausblick-Pfad (`trip_report_scheduler.py:2026`). Der Fehler ist heute nur
unsichtbar, weil niemand `thunder_level_max_signals` aus `agg` liest. Known
Limitation 7 (S1) / 3 (S4) ist damit **fällig**, unabhängig davon, welchen Weg
die Anzeige nimmt.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `src/output/renderers/email/outlook.py:420-490` | `build_outlook_row()` — hat `points` (rohe `ForecastDataPoint`s) UND baut die `HourlyValue`-Tupel. **Die Naht, an der die Träger heute verloren gehen.** Geteilt Trip↔Compare. |
| `src/output/renderers/email/outlook.py:234-258` / `:372-390` | Gewitter-Zelle HTML / Klartext; `_thunder_token_parts()` (`:43-59`), Wortlaut-Map `_THUNDER_LEVEL_LABEL` (`:195-198`) |
| `src/output/renderers/email/helpers.py:897-1020` | `format_trend_tokens(stage: dict)` — **einzige Quelle der Trend-Semantik** für HTML, Klartext, Telegram, SMS. Erzeugt `thunder_day_token` / `thunder_night_token` getrennt nach Tagesfenster. |
| `src/services/trip_report_scheduler.py:1956-2101` | `_build_multi_day_trend()` — `aggregate_stage()` (`:2026`), `_flat_points` (`:2046-2049`), `build_outlook_row()` (`:2069`), `row["date"]` (`:2079`, #1275) |
| `src/services/trip_report_scheduler.py:2103-2192` | `_build_thunder_forecast_from_trend_or_fetch()` — **Primärpfad** der Vorschau, wiederverwendet die Ausblick-Zeilen |
| `src/services/trip_report_scheduler.py:2216-2310` | `_thunder_entry_from_trend_row()` — leitet Level/Stunde aus `row["hourly_thunder"]` **im Fenster** ab; `row["thunder"]` nur Fail-soft (`:2284-2291`) |
| `src/services/trip_report_scheduler.py:2407-2555` | `_build_thunder_forecast()` — **Fallback-Pfad** der Vorschau, aggregiert `ForecastDataPoint`s direkt (`:2494-2504`); Träger dort **vollständig sichtbar** |
| `src/output/renderers/email/plain.py:307-332` | Vorschau-Block Klartext; `outlook_active`-Unterdrückung (#1313 E1) |
| `src/output/renderers/email/html.py:1307-1329` | Vorschau-Block HTML, wortgleiche Unterdrückung |
| `src/services/weather_metrics.py:468-483` | `aggregation_config` — Regel `union_of_max_carriers` deklariert (`:478`) |
| `src/services/weather_metrics.py:1168-1266` | `aggregate_stage()` — **fehlender Dispatch-Zweig**, `else: values[0]` |
| `src/output/metric_format.py:559-609` | `union_of_max_carriers()` — geteilter Baustein aus S2, Rückgabe bewusst `list` (nicht `set`, #1405) |
| `src/output/metric_format.py:448-484` | `thunder_signal_carriers()` — erzeugt die Trägerliste |
| `src/output/metric_format.py:374-379` | `THUNDER_SIGNAL_LABEL_DE` — **vier** Zutaten: Wettercode, Blitzdichte, CAPE, Blitzpotenzial |
| `src/app/models.py:425-430` | `SegmentWeatherSummary.thunder_level_max` / `.thunder_level_max_signals` |
| `src/providers/thunder_enrichment.py:151` | setzt `dp.thunder_level_signals` auf dem `ForecastDataPoint` |
| `src/output/tokens/dto.py:15-18` | `HourlyValue` (frozen, `hour`+`value`) — die verengte Zwischenform |

### Die drei weiteren Ausblick-Implementierungen

`outlook.py` ist **nicht** der einzige Ausblick. Alle drei lesen dasselbe
`stage`-dict über `format_trend_tokens()`:

| Ort | Datei:Zeile | Kanal |
|---|---|---|
| Trip-Mail HTML + Klartext | `email/outlook.py:208` / `:353` | E-Mail |
| Telegram-Trendblock | `narrow.py:575` `_outlook_lines()` | Telegram |
| Kompakt-Mail "Nächste Etappen" | `email/compact.py:230` | E-Mail (compact) |

Ein Feld im `row`-dict bzw. ein neuer Token aus `format_trend_tokens()` wird von
**allen dreien** strukturell geerbt — wie in S4 bei Telegram-rich. Das ist eine
Produktentscheidung für die Spec, kein Implementierungsdetail.

## Existing Patterns

- **`union_of_max_carriers()`** (S2) — der geteilte Baustein liegt fertig vor;
  Aufrufer u.a. `compact_summary.py:584,628`, `trip_report.py:650-651`,
  `helpers.py:1752,1771`, `day_window.py:58,79`, `trip_command_processor.py:841`.
- **`hail_flag` / `hail_priority` (#1475 S5a)** ist das **Vorbild** für einen
  Dispatch-Zweig in `aggregate_stage()`: Sonderfall **vor** dem generischen
  `is not None`-Vorfilter (`weather_metrics.py:1205-1217`), weil die Regel die
  vollständige Werteliste braucht. `union_of_max_carriers` braucht zusätzlich
  die **gepaarte** Stufe — es aggregiert `(level, signals)`-Paare, nicht eine
  Werteliste. Das ist der eine Punkt, an dem das Vorbild nicht 1:1 trägt.
- **S4-Muster** (`_dp_to_row`): Träger direkt aus `ForecastDataPoint`s
  fenstergerecht berechnen, statt sie durch eine verengte Zwischenform zu ziehen.
- **Abwesenheits-ACs brauchen eine Gegenprobe** an derselben Fixture (S1/S2/S3),
  sonst sind sie vakuum-grün.

## Dependencies

- **Upstream:** `thunder_signal_carriers()` → `dp.thunder_level_signals` →
  `_flat_points` → `build_outlook_row()`; `aggregate_stage()` → `agg`
- **Downstream:** `format_trend_tokens()` → **drei** Ausblick-Renderer;
  `row` → `_thunder_entry_from_trend_row()` → Vorschau (E-Mail/SMS/Telegram);
  `outlook.py` → **Compare-Ausblick** (geteilte Naht)

## Existing Specs

- `docs/specs/modules/feat_1680_s1_gewitter_herkunft_ortsvergleich.md` — AC-12-Regel
- `docs/specs/modules/feat_1680_s2_gewitter_herkunft_trip.md` — `union_of_max_carriers()`, F001
- `docs/specs/modules/feat_1680_s3_gewitter_herkunft_vier_orte.md` — roher Durchgriff ohne Garantie
- `docs/specs/modules/feat_1680_s4_gewitter_herkunft_trip_stundentabelle.md` — Known Limitations 3/4
- `docs/reference/metric_output_matrix.md:89-90,113` — Ausblick-Zeilen, Rest-Scope
- `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` — AC-11 Paritätswächter
- ADR-0025 (Vorschau=Versand), #1498 Fall 2, #1651/#1653 (Tag/Nacht-Fenster), #1275 (Row-Reuse), #1313 E1 (Unterdrückung)

## Risks & Considerations

1. **🔴 Byte-Golden-Paritätswächter.** `tests/tdd/test_trip_outlook_parity.py`
   vergleicht die **gesamte** Trip-Mail (HTML + Klartext) gegen aufgezeichnete
   Golden-Dateien in `tests/fixtures/outlook_trip_parity/`. Jede sichtbare
   Änderung am Ausblick macht ihn rot. Er ist **bewusst** so gebaut ("die
   Golden-Dateien sind der Beweis, sie werden NICHT neu erzeugt"). Er muss —
   wie die zwei Bestandstests in S3 — **begründet mitgezogen** werden, samt
   Nachtrag in `tests/fixtures/outlook_trip_parity/README.md`. Das Aufweichen
   des Wächters wäre ein Regelverstoß.
2. **🔴 Tag- und Nachtstufe sind getrennt.** `thunder_day_token` und
   `thunder_night_token` entstehen aus **verschiedenen** Stundenmengen
   (`helpers.py:1005-1020`). Eine einzige Trägerliste für beide würde
   Nacht-Träger an die Tagesstufe heften — der AC-12-Fehler aus S1 in neuer
   Gestalt. Die Träger müssen **je Fenster** berechnet werden.
3. **🔴 `aggregate_stage()`s fehlender Zweig ist ein echter latenter Fehler**,
   nicht nur eine Lücke (s.o.). Er ist heute erreichbar, aber unbenutzt.
4. **Geteilte Naht Trip↔Compare.** `build_outlook_row()` und
   `render_outlook_table()` bedienen beide Flächen. Ob der **Compare-Ausblick**
   die Herkunft mitbekommen soll, ist eine Produktentscheidung (Compare hat sie
   seit S1/S3 in anderen Ausgabeorten). Ein `include_origin`-Parameter existiert
   dort bereits als Muster.
5. **Drei Ausblick-Kanäle erben strukturell** (E-Mail, Telegram, Kompakt-Mail) —
   s.o. In S4 war genau das eine bewusst dokumentierte Known Limitation.
6. **Die Vorschau erscheint nur, wenn der Ausblick NICHT aktiv ist** (#1313 E1,
   `plain.py:309`, `html.py:1309`). Im Abend-Default mit Ausblick entfällt sie.
   Sichtbar wird sie u.a., wenn der Nutzer den Ausblick abgeschaltet hat
   (`show_outlook=False`) — dann greift trotzdem der **Primärpfad** über die
   Trend-Zeilen, sofern `multi_day_trend` gefüllt ist. **Beide Vorschau-Pfade
   (Primär `_thunder_entry_from_trend_row`, Fallback `_build_thunder_forecast`)
   müssen dieselbe Herkunft liefern**, sonst hängt die Aussage davon ab, ob der
   Trend zufällig vorlag — eine Wiederholung von #1555 (Tier-Lücke).
7. **Der Vorschau-Text trägt bereits zwei Zusätze** (Hagel `· Hagel: ja`,
   Nacht-Halbsatz `, nachts … ab 02:00`). Ein dritter Zusatz muss sich in diese
   Reihenfolge einfügen, ohne den Nacht-Halbsatz zu zerschneiden.
8. **`ForecastDataPoint.thunder_level_signals` muss auf dem Ausblick-Pfad
   tatsächlich gefüllt sein.** Der Ausblick holt Wetter über `_fetch_weather()`
   für **künftige** Etappen — ob die Anreicherung (`thunder_enrichment.py`) dort
   ebenso läuft wie im Hauptpfad, ist **zu messen**, nicht anzunehmen. Wenn
   nicht, wäre die ganze Scheibe wirkungslos (Prüfort ≠ Wirkort).
9. **SMS/Premium-SMS bleiben ohne Herkunft** (PO-Entscheid seit S1). Der
   Ausblick speist auch SMS-Token (`thunder_sms`) — die Dichtheit ist erneut
   nachzuweisen, per Sonde statt Wortsuche (S3-Muster).
10. **Serialisierung:** neue Felder als `list[str]`, nie `set` — ein
    `json.dumps`-Fehler kostet den **gesamten** Wetter-Schnappschuss lautlos
    (#1405, `weather_snapshot.py:83-86`).

---

# Analysis

## Type
**Feature** (Fortsetzung Epic #1419 Rang 4 / #1680, Scheibe 5)

## 🔴 Zwei Funde, die den Plan tragen — beide nachgemessen

**Fund A: Der Scheduler darf `union_of_max_carriers` NICHT importieren.**
`tests/unit/test_notification_service.py:183-192` ist eine Architektur-Wache,
die in `src/services/trip_report_scheduler.py` **zeilengenau einen** Import aus
der Darstellungsschicht erlaubt:
```python
_ALLOWED_SHARED_IMPORT = "from output.renderers.email.outlook import build_outlook_row"
```
Der naheliegende Ansatz „`union_of_max_carriers()` einfach im Scheduler
aufrufen" ist damit gesperrt. Die Berechnung muss in `build_outlook_row()`
(Darstellungsschicht) oder über `services.weather_metrics` laufen.

**Fund B: Der Fallback-Pfad der Vorschau bekommt die Herkunft geschenkt.**
`_build_thunder_forecast()` baut für das Hagel-Kennzeichen bereits
`summarize_points(thunder_dps)` (`trip_report_scheduler.py:2552`).
`summarize_points()` (`weather_metrics.py:1108-1133`) ruft
`compute_basis_metrics()`, und das setzt `thunder_level_max_signals` schon
heute über `union_of_max_carriers` (`weather_metrics.py:438,462`) — für
**dieselbe** Punktmenge, die auch `level`/`hour` liefert. Es genügt, das
vorhandene Aggregat in eine Variable zu heben und ein zweites Feld zu lesen.
**Null neue Aggregationslogik, kein zusätzlicher Datenzugriff.**

Das Vorbild dafür steht direkt daneben: `_thunder_entry_from_trend_row()` liest
bereits `"hail": row.get("hail")` (`trip_report_scheduler.py:2335`) — Fix #1475
löste dort **exakt dasselbe** Zwei-Pfade-Problem, das Risiko 6 oben für die
Herkunft befürchtet. Das Muster ist wortgleich übertragbar.

## Weitere Messungen, die Annahmen korrigierten

| Annahme | Messung |
|---|---|
| „Telegram hat 32 Zeichen Breite" (aus S4 übernommen) | **Falsch für den Ausblick.** `_outlook_lines()` nutzt `_TG_PROSE_WIDTH = 56` mit Wort-Umbruch (`narrow.py:53`), nicht `_TG_TABLE_WIDTH`. Die 32 gelten der Stundentabelle aus S4. |
| „SMS-Dichtheit muss nachgewiesen werden" | **Strukturell gegeben.** SMS/Premium-SMS bauen ihren Text über `SMSTripFormatter` und sehen `multi_day_trend` nie. `thunder_sms` aus `format_trend_tokens()` wird **nirgends gelesen** — toter Token. |
| „Die Kompakt-Mail erbt mit" | **Nein.** Sie liest nur `thunder_plain` (`compact.py:234`) und faltet nach ASCII (`_ascii()`), was `·` ohnehin zerstörte. |
| „Ein neuer Schlüssel bricht den Zeilenbau-Test" | Nur bei bedingungslosem Setzen. `build_outlook_row()` filtert optionale Felder bereits über `row.update({k: v for k, v in optional.items() if v is not None})` (`outlook.py:517`), und `union_of_max_carriers()` liefert selbst `None` statt `[]` (`metric_format.py:597-600`). |

## Affected Files

### Scheibe 5a — Mehrtages-Ausblick

| Datei | Change | Beschreibung |
|------|--------|--------------|
| `src/output/renderers/email/outlook.py` | MODIFY | `build_outlook_row()`: Träger je Fenster aus `points` berechnen → optionaler Schlüssel; Gewitter-Zelle HTML (`:234-258`) + Klartext (`:369-390`) um Herkunft ergänzen |
| `src/output/renderers/narrow.py` | MODIFY | Telegram-Trendblock (`:588-597`) — strukturelles Erbe, eigener Zweig nötig |
| `tests/tdd/test_trip_outlook_parity.py` | UNVERÄNDERT | bleibt grün (Fixture ohne Träger) — **Beleg** für „ohne Träger zeichengleich" |
| `tests/golden/email/test_outlook_thunder_day_night_golden.py` | UNVERÄNDERT | dito |
| `tests/tdd/test_thunder_origin_outlook.py` | CREATE | neue Suite |

### Scheibe 5b — Gewitter-Vorschau

| Datei | Change | Beschreibung |
|------|--------|--------------|
| `src/services/trip_report_scheduler.py` | MODIFY | `_thunder_entry_from_trend_row()` +1 Zeile (Primär); `_build_thunder_forecast()` Aggregat in Variable heben (Fallback) |
| `src/output/renderers/email/plain.py` | MODIFY | Vorschau-Block (`:317-328`) |
| `src/output/renderers/email/html.py` | MODIFY | Vorschau-Block (`:1313-1323`) |
| `tests/tdd/test_thunder_origin_preview.py` | CREATE | neue Suite |

## Scope Assessment

| | Dateien | Produktiv-LoC | Risiko |
|---|---|---|---|
| **S5a Ausblick** | 2 + 1 Test | ~45–60 | MEDIUM (geteilte Naht Trip↔Compare, Golden-Wächter) |
| **S5b Vorschau** | 3 + 1 Test | ~20–25 | LOW (zwei vorhandene Call-Sites, Muster #1475) |

Tests dominieren wie in allen Vorgängerscheiben (S4: 437 Testzeilen zu 14
Produktivzeilen). `loc_limit_override` wird voraussichtlich nötig — wie in S1–S3.

## Technical Approach (Entscheidungen)

**1. Schnitt: zwei Scheiben, S5a vor S5b.** Jede Vorgängerscheibe deckte genau
einen Ausgabeort. S5a liefert den `row`-Vertrag, S5b konsumiert ihn — echte
Vorgänger/Nachfolger-Beziehung statt künstlicher Trennung.

**2. Wortlaut: Herkunft nur am Tagesteil, unmittelbar hinter der Uhrzeit.**
```
nur Tag:            leicht @16 · CAPE
Tag + Nacht:        leicht @16 · CAPE · nachts hoch @0
Tag+Nacht+Hagel:    leicht @16 · CAPE · nachts hoch @0 · Hagel: ja
zwei Zutaten:       leicht @16 · CAPE, Blitzdichte
```
Begründung: Übernimmt den seit S1 an sechs Fundstellen etablierten
`" · "`-Wortlaut unverändert und begrenzt den Zuwachs auf **ein** zusätzliches
`·`. Eine eigene Nachtherkunft brächte bis zu vier `·` mit drei Bedeutungen in
eine Zelle — Lesbarkeit unter Zeitdruck schlägt Vollständigkeit
(CLAUDE.md Design-Leitprinzip).

**3. Nur der Tagesteil trägt Herkunft** — deckungsgleich mit der bestehenden
Asymmetrie: die Vorschau liefert `level`/`hour` ohnehin nur für das Tagesfenster
(ADR-0025), der Nacht-Halbsatz trägt schon heute keine eigenen Strukturdaten.
Folge: reine Nachtgewitter-Tage zeigen **nie** eine Herkunft — bewusster
Verzicht, als AC festzuhalten, damit ihn kein späterer Adversary „repariert".

**4. Neuer Schlüssel nur bei vorhandenen Trägern** (Option a) — fügt sich in das
vorhandene `optional`-Filtermuster ein und lässt beide Golden-Wächter
unangetastet grün.

**5. Compare-Ausblick erbt mit, ohne Unterdrückung.** `build_outlook_row()` ist
die geteilte Naht (`compare_html.py:1167`); Compare zeigt die Herkunft seit
S1/S3 an anderen Stellen. Ein `include_origin`-Schalter zum Abschalten wäre
Zusatzkomplexität für negativen Produktwert.

**6. Beide Vorschau-Pfade** — eine Regel an zwei vorhandenen Call-Sites, nicht
zwei Implementierungen. Sonst hinge die Aussage davon ab, ob der Trend zufällig
vorlag (Wiederholung von #1555).

## Open Questions (für die Spec-Phase zu messen)

- [ ] **🔴 Ist der Fallback-Zweig `outlook.py:238-243` im Betrieb erreichbar?**
      Er zeigt die Aggregat-Stufe, wenn **keine** Stundenreihe vorliegt
      (Kommentar: „Alt-Fixtures"). Davon hängt ab, ob der fehlende
      `aggregate_stage()`-Dispatch-Zweig in dieser Scheibe einen **Wirkort**
      hat. Ist er unerreichbar, wäre der Fix Code ohne Verbraucher — genau der
      Fehler, den S2 vermieden hat. Ist er erreichbar, gehört der Fix in S5a und
      Known Limitation 7 fällt endlich. **Messen, nicht raten** — diese Frage
      entscheidet, ob `aggregate_stage()` zum fünften Mal vertagt wird.
- [ ] **Trägt `LocationResult.outlook_hourly_data` (Compare) die Signale ebenso
      zuverlässig?** Andere Punktliste als der Trip-Ausblick-Fetch
      (`comparison_engine.py:177`). Risiko 8 gilt hier ein zweites Mal.
- [ ] **Fenster-Konsistenz:** `build_outlook_row()` und `format_trend_tokens()`
      lösen das Tagesfenster **zweimal unabhängig** auf. Ein Test mit einem von
      4/19 **abweichenden** Fenster ist Pflicht — sonst bleibt die
      gefährlichste Annahme der Scheibe unbewiesen.
