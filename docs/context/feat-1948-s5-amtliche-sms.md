# Context: #1948 Scheibe S5 — Zielbild amtliche Warnungen (Zweig b)

Workflow: `feat-1948-s5-amtliche-sms` · Issue #1948 · erstellt 2026-08-20

## Request Summary

Die Standalone-SMS für amtliche Wetterwarnungen trägt heute ein Sonderformat
(`KHW403 AMT GELB1/3: TH Fr06-20 Ziel`). Sie soll auf dieselbe Grammatik
umgestellt werden, die Briefing-SMS und (seit S4) Nowcast-Alarm bereits
sprechen: Ortskopf über die gemeinsame Auflösung, Gefahren-Kürzel mit
Stufenbuchstaben, Zeitfenster ohne Wochentag wenn heute — Zielbild
`Ziel: TH:H 13-22` (Konzept `docs/analysis/alarm-format-konzept-2026-08.md`,
Abschnitt 1, Zeile „b — amtlich").

## PO-Entscheide, die bereits feststehen

| Nr | Entscheid | Quelle |
|---|---|---|
| 1 | Format folgt dem **Phänomen**, nicht der Quelle — das `AMT`-Sonderformat verschwindet aus Nutzersicht | Konzept Leitsatz |
| 2 | Kein Trip-Name in der Alarm-SMS — der `sms_prefix` entfällt | Konzept Regel 1 |
| 3 | Wochentag nur, wenn die Gültigkeit **nicht heute** beginnt | Konzept Regel 2 |
| 4 | Ortskopf aus `format_alert_location`/`_km_str` als einzige Quelle | Konzept Regel 3 |
| 5 | Warnstufen-Mapping **Option 1**: GRÜN→`-`, GELB→`L`, ORANGE→`M`, ROT→`H`, für alle Gefahrenarten | Konzept Abschnitt 4 |
| 6 | Führende Null der Stunde: SMS/Premium-SMS **ohne**, E-Mail/Telegram **mit** | `issuecomment-5345456988` |
| 7 | #1929 läuft zuerst — erfüllt, seit 2026-08-18 geschlossen | Konzept Abschnitt 6 |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/official_alerts.py:2038-2124` | `render_official_alert_sms` — der umzubauende Renderer |
| `src/output/renderers/alert/official_alerts.py:1896-1937` | `_tag_hour`/`_tag_time` — Zeitfenster-Token, **nur** von der SMS genutzt |
| `src/output/renderers/alert/official_alerts.py:1940-2035` | `_sms_pack`, `_sms_leading_variants`, `_sms_pack_with_fallback` — Zeichenbudget-Kette, nur SMS |
| `src/output/renderers/alert/official_alerts.py:2139-2199` | `build_official_alert_notices` — baut `sms_scope` (eigene Ortssprache, `S1`, `ges.Route`, `nur …`) |
| `src/output/renderers/alert/official_alerts.py:2201-2257` | `build_compare_official_alert_notices` — Compare-Pendant (`alleOrte`, `nur Toulon`, `A+B`) |
| `src/output/renderers/alert/official_alerts.py:344-381` | `official_alerts_to_sms_entries` — **lebendes Vorbild**: baut heute schon `(Kürzel, Stufenbuchstabe, Stunde)` für den Briefing-Warnblock |
| `src/output/tokens/hazard_symbols.py:15-73` | `HAZARD_SMS_SYMBOLS` (10 Kürzel), `HAZARD_ORDER`, `LEVEL_LETTERS`, `MIN_SMS_LEVEL`, `LEVELLESS_HAZARDS` |
| `src/output/renderers/alert/segments.py:91-111` | `format_alert_location` — Rückfallkette Ortsname → Segment → km |
| `src/output/renderers/alert/render.py:427-432` | `_sms_onset_time` — S4-Hilfsfunktion für die führende Null |
| `src/output/renderers/alert/render.py:1014-1018` | `_ascii_alert_location` — Pictogramm-Strip **vor** ASCII-Faltung (sonst `:checkered_flag:`) |
| `src/services/notification_service.py:910,931,950,1206,1241,1264` | die sechs Produktivaufrufer (Trip + Compare, je Telegram-Kurzform/SMS/Premium-SMS) |
| `src/services/validator_render_service.py:163-214` | Preview-Pfad Zweig b (`_render_official_preview`) |
| `api/routers/validator.py:226-234,237-250` | `OnsetPayload` (ohne Segment-Feld) vs. `OfficialAlertPayload` (mit `segment_ids`) |

## Existing Patterns

- **Die Zielgrammatik existiert bereits produktiv.** `official_alerts_to_sms_entries`
  (`official_alerts.py:344`) erzeugt für den Briefing-Warnblock schon
  `TH:H@14` aus genau den Bausteinen, die S5 braucht — `sms_symbol_for` +
  `LEVEL_LETTERS` + Beginn-Stunde. `LEVEL_LETTERS` ist bereits in
  `official_alerts.py:24` importiert. **S5 verdrahtet vorhandene Bauteile,
  es entsteht kein neues Vokabular.**
- **Kopf-Muster aus S4:** `f"{head}: {token}"` — Ortskopf, Doppelpunkt,
  Leerzeichen, Token (`render.py:463`); identisch im Trip-Δ-Zweig
  (`render.py:941`).
- **Zeichenbudget:** ganze Tokens fallen vom schwächsten Ende weg (`+N`), die
  schwerste Warnung bleibt über eine Rückfallkette immer erhalten
  (`_sms_pack_with_fallback`).

## Dependencies

**Upstream (was der Renderer nutzt):** `OfficialAlertNotice`-DTO
(`official_alerts.py:138-165`) mit `alert`, `scope_label`, `sms_scope`,
`scope_kind`, `scope_ids`; `_tag_time` für den Zeitraum; `_ascii` für die
GSM-7-Faltung.

**Downstream (was den Renderer nutzt):** die sechs Dispatch-Stellen in
`notification_service.py` und der Preview in `validator_render_service.py:210`.
`compare_official_alert.py` ruft **nicht** selbst — es delegiert an
`notification_service.send_multi_location_official_alert` (Z. 257).

## Risks & Considerations

1. **🔴 Der Telegram-Kurzstil liest denselben Text.**
   `notification_service.py:910` und `:1206` rufen `render_official_alert_sms`
   für den Telegram-**Kurzstil** auf; `tests/tdd/test_telegram_kurzstil_trip_alert.py:357`
   und `test_telegram_kurzstil_compare_official_alert.py:207` fordern
   `telegram_body == sms_text`. Anders als in S4 kann die Zusage „Telegram
   bleibt unverändert" hier **nicht** gelten — die Kurzform zieht zwingend mit.
   Die rich-Telegram-Variante (`render_official_alert_telegram`, Z. 1875-1890)
   bleibt unberührt.
2. **🔴 Geteilte Bausteine sind tabu.** `_LEVEL_WORDS` (auch extern importiert
   von `email/compare_html.py:58`), `_LEVEL_POSITION`, `_hazard_display`,
   `_sort_notices`, `_uniform_scope` speisen Betreff, E-Mail-HTML,
   Klartext-Mail und rich-Telegram. Eine Änderung dort zöge alle Kanäle mit.
   Gefahrlos änderbar: `_tag_time`, `_tag_hour`, `_sms_pack*`,
   `_sms_leading_variants` und der Rumpf von `render_official_alert_sms`.
3. **Snapshot-Fixture muss neu erzeugt werden.**
   `tests/unit/test_official_alert_output_unchanged.py` prüft alle vier Kanäle
   byte-identisch gegen `tests/fixtures/official_alert_render_snapshot_1944.json`
   (`trip_sms`, `compare_sms` enthalten das AMT-Format wörtlich).
4. **🔴 Merge-Konflikt-Risiko `tests/test_output_timezone_guard.py`.** Die Datei
   führt eine ordinal-indizierte Ausnahmeliste mit Einträgen für
   `official_alerts.py::_tag_time::0/1/2` und `::render_official_alert_sms::0`
   (Z. 570-578). Wer `.astimezone()`-Aufrufe in `_tag_time` verschiebt, muss
   die Ordinale nachziehen. **Parallel-Sitzung `#1727 S5g` schreibt genau diese
   Liste gerade strukturell um** (34 → 26 Einträge, Kategorie-Präfixe) —
   vor einem Eingriff dort abstimmen.
5. **Ortssprache divergiert.** Der amtliche Zweig hat eine eigene
   Kurz-Ortssprache (`S1`, `ges.Route`, `nur Toulon`, `A+B`), gebaut per
   String-Ersetzung in den beiden Buildern. Der Umstieg auf
   `format_alert_location` muss klären, was aus `sms_scope` wird — besonders
   bei Warnungen mit **unterschiedlichem** Umfang (`_uniform_scope` false),
   wo heute jedes Token seinen eigenen Ort trägt. Bestandstests binden das
   fest: `test_ascii_folding.py:534-566,678-684` (`"nur "`-Präfix),
   `test_official_alert_channel_scope.py:270,282,657` (drei Volltext-Gleichheiten).
6. **Amtliche S1-Mitschnitte sind nicht 1:1 einspeisbar.** 50 Dateien liegen auf
   Prod unter `/var/lib/gregor/debug/alert_input/official_alert/` (42
   `geosphere_warn`, 8 `meteoalarm_feed:AT`, Retention 50). `payload.body` ist
   die **rohe Anbieter-Antwort** (GeoJSON mit `properties.warnings[]`), nicht
   `OfficialAlertPayload`. Für die Verifikation über
   `POST /api/trips/{id}/alert-preview` müssen die Rohdaten auf
   `source/hazard/level/label/valid_from/valid_to/segment_ids` abgebildet
   werden. Anders als bei S4 sind echte Aufzeichnungen aber **vorhanden**
   (Stichprobe 2026-08-20: Hitzewarnungen `warntypid 6`, ganztägig 00:00-23:59).
7. **Vorbedingung aus S4 (`issuecomment-5351380856`):** `OnsetPayload` fehlt
   das Segment-Feld; zu ergänzen an vier Stellen (`validator.py:234`,
   `validator_render_service.py:117`, `:253`, `NowcastFramesPayload`).
   S5 spürt die Lücke selbst nicht — sie muss bewusst in die Spec.
8. **Nebenbefund:** `validator_render_service.py:210` übergibt
   `sms_prefix=trip_obj.name` **ohne** `.replace(" ", "")`, der Produktivpfad
   mit — der Preview konnte einen anderen Kopf zeigen als der echte Versand.
   Löst sich auf, wenn der Prefix entfällt.
9. **Doku-Zonen:** `official_alerts.py:1896-2104` ist in mehreren Dokumenten als
   „#1929-Sperrzone" markiert (`alarm_testeinspeisung.md:48,181,335`,
   `feat_1944_warn_mitschnitt_herkunft.md:284`, `api_contract.md:3390`).
   #1929 ist geschlossen — die Notizen sind mit aufzulösen.

## Existing Specs

- `docs/analysis/alarm-format-konzept-2026-08.md` — das Gesamtkonzept, Zielbild
  Zweig b in Abschnitt 1, Scheiben-Tabelle in Abschnitt 8
- `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` — Spec-Vorbild (S4)
- `docs/specs/modules/alarm_testeinspeisung.md` — S2, Preview-Endpunkt
- `docs/specs/modules/sms_official_alert_tokens.md` — Kürzel-Katalog Abschnitt 1/1b
- `docs/reference/sms_format.md` §3.4c — Wire-Doku der Warn-Kürzel (listet nur
  9 statt 10 Kürzel; `flood`/`FL` fehlt — Doku-Lücke)

## Offene Fragen für die Analyse-Phase

1. **Mehrere Warnungen in einer SMS:** Das Zielbild nennt nur den Einzelfall
   (`Ziel: TH:H 13-22`). Wie sieht die Verkettung bei zwei Warnungen aus, und
   was passiert, wenn sie **verschiedene** Segmente betreffen?
2. **Zeitangabe:** Zielbild Zweig b zeigt ein Fenster (`13-22`), Regel 5 nennt
   `@` als Beginn-Marker. Fenster oder Beginn? Und mit welcher Stellenzahl
   (`6-20` vs. `06-20`, PO-Entscheid Nr. 6)?
3. **Gefahren-Kürzel:** Konzept Abschnitt 5 empfiehlt Option 3 (nur `TH`
   bereinigen, übrige Register-Kollisionen stehen lassen) — als Empfehlung
   ohne PO-Bindung.

---

# Analysis (Phase 2, 2026-08-20)

## Type

Feature (Format-Umbau eines bestehenden Renderers), Full Process.

## Ist-Basislinie aus ECHTEN Aufzeichnungen

50 Mitschnitte von Prod (2026-08-20, Kärnten/KHW), geparst mit den
Produktivparsern `geosphere_warn._extract_alerts` (`:107`) und
`meteoalarm_feed._alerts_for_zone` (`:218`), gerendert über
`build_official_alert_notices` → `render_official_alert_sms` mit dem echten
Trip „KHW 403". Alle Texte unten sind tatsächliche Renderer-Ausgaben.

| # | Fall | Ist-SMS | Zeichen |
|---|---|---|---|
| 1 | Gewitter, Stundenfenster | `KHW403 AMT GELB1/3: TH Do12-22, ges.Route` | 41 |
| 2 | Hitze, ganztägig | `KHW403 AMT GELB1/3: HT Do20.08., ges.Route` | 42 |
| 3 | Bündel aus einer Antwort, 3 Warnungen | `KHW403 AMT GELB1/3: HT Do20.08. + TH Do02-03 + TH Do12-22, ges.Route` | 68 |
| 5 | 3× Gewitter, verschiedene Fenster | `KHW403 AMT GELB1/3: TH So13-22 + TH Mo09-19 + TH Do12-22, ges.Route` | 67 |
| 6 | Hitze + Gewitter | `KHW403 AMT GELB1/3: HT Do20.08. + TH Do12-22, ges.Route` | 55 |
| 7 | Tagesübergang | `KHW403 AMT GELB1/3: TH Do16-Fr00, ges.Route` | 43 |

**Inventur:** 27 eindeutige Warnungen, ausschließlich `thunderstorm` und
`extreme_heat`, **ausschließlich Stufe 2 (gelb)**. Zeitraum-Muster: 17
Stundenfenster, 9 ganztägig, 1 Tagesübergang.

**Zeichenbudget:** Minimum 41, Median 42,5, Maximum 68 von 140 Zeichen. Kein
einziges Token wurde je gedroppt (`+N` kam nie vor). Das Budget ist im realen
Betrieb zu **maximal 49 %** ausgelastet — die Zeichenersparnis ist damit
**kein** treibendes Argument für Formatentscheidungen.

**Nicht in den echten Daten vorhanden** (nicht erfunden, sondern als Lücke
markiert): gemischte Warnstufen, Stufe 3/4, `access_ban`, Warnungen mit
unterschiedlichem Segment-Umfang. Der mixed-level-Zweig des Renderers ist
gegen echte Daten **nicht** belegbar.

## Gemessene Korrekturen an Annahmen

1. **🔴 `MIN_SMS_LEVEL = 3` filtert den Standalone-Alarm NICHT.** Es ist der
   Vorgabewert des Briefing-Warnblocks (`official_alerts_to_sms_entries`,
   `official_alerts.py:346`). Der Standalone-Pfad
   (`trip_alert.py:_send_official_alert_only`, ab :1671) kennt Ruhezeit,
   Tageslimit, Identitäts-Gate und `split_by_threshold` — **keinen
   Stufenfilter**. `split_by_threshold` fällt ohne gesetzten Wert auf `LOW`
   zurück (`alert_channel_threshold.py:25,30`), und
   `min_official_level_for_threshold("LOW")` ergibt **2** (gemessen).
   ⇒ **Gelbe Warnungen erreichen SMS und Premium-SMS bei Standardeinstellung.**
   Der Stufenbuchstabe `L` ist die *häufigste* reale Ausprägung, kein toter
   Zweig — der Kommentar `hazard_symbols.py:32-33` („durch MIN_SMS_LEVEL nie
   sichtbar") gilt nur fürs Briefing und ist für den Alarm irreführend.
2. **🔴 `LEVEL_LETTERS` darf NICHT um GRÜN→`-` ergänzt werden.** Gemessen:
   `LEVEL_LETTERS[1] = "-"` lässt `alert_urgency.urgency_from_official_level(1)`
   mit `KeyError: '-'` abstürzen (`alert_urgency.py:29`,
   `_LETTER_TO_URGENCY[letter]` kennt nur `L`/`M`/`H`) — mitten im
   Alarm-Auslösepfad. Die Tabelle ist eine **Dringlichkeits**-Abbildung mit
   zweitem Konsumenten, keine Darstellungstabelle.
   ⇒ Die vierstufige Darstellungsleiter gehört in eine eigene Funktion im
   SMS-Renderer (`{1:"-", 2:"L", 3:"M", 4:"H"}`), getrennt von `LEVEL_LETTERS`.
   Damit ist PO-Entscheid „Option 1" vollständig erfüllt, ohne die
   Dringlichkeits-Ableitung anzufassen.

## Technischer Ansatz

Ein Bau-Pfad statt zwei. Der heutige Renderer verzweigt in „einheitliche
Stufe" (gemeinsamer `AMT {WORT}{Pos}/3`-Kopf) und „gemischte Stufen"
(Stufenwort je Token). Da im Zielformat **jedes Token seinen Stufenbuchstaben
selbst trägt** (`TH:H`), verliert diese Weiche ihren Zweck für die
Token-Darstellung. Sie bleibt allein für die **Kopf-Frage** relevant:
gemeinsamer Ortskopf nur, wenn alle Warnungen denselben Umfang haben
(`_uniform_scope`, identitätsbasiert über `scope_ids`); sonst trägt jedes
Token seinen eigenen Ortszusatz — genau wie heute schon im mixed-Zweig.

Die Zeichenbudget-Kette (`_sms_pack`, `_sms_leading_variants`,
`_sms_pack_with_fallback`) ist rein textbasiert und bleibt unverändert
nutzbar. Der `suffix`-Mechanismus (Ort am Ende) wird für den einheitlichen
Fall überflüssig, weil der Kopf die Ortsfunktion übernimmt.

`sms_prefix` entfällt aus der Ausgabe — das ändert die Signatur und trifft
sieben Aufrufer (sechs in `notification_service.py`, einer in
`validator_render_service.py:210`).

## Entscheidungen für die Spec

| Frage | Entscheidung | Begründung |
|---|---|---|
| Mehrere Warnungen | Tokens mit ` + ` verkettet wie heute; gemeinsamer Ortskopf nur bei einheitlichem Umfang, sonst Ort je Token | kleinste Änderung an bewährter Logik; ein einzelner Kopf würde bei verschiedenen Segmenten suggerieren, alle Warnungen gälten für denselben Ort |
| Zeitangabe | **Fenster behalten** (`13-22`), nicht auf `@Beginn` umstellen | bei einer amtlichen Warnung ist das Ende sicherheitsrelevant; das Budget ist mit max. 49 % ohnehin nicht knapp; entspricht dem PO-finalisierten Zielbild |
| Führende Null | Stunde ohne (`6-20`), Minuten zweistellig (`15:20-21:40`) | PO-Entscheid; Muster von `_sms_onset_time` (S4) |
| Stufenleiter GRÜN→`-` | eigene Darstellungsfunktion im Renderer, `LEVEL_LETTERS` unangetastet | sonst Absturz, s. gemessene Korrektur 2 |
| `access_ban` (stufenlos) | Kürzel **ohne** Stufenbuchstaben (`CL`), wie im Briefing-Warnblock (`official_alerts.py:373-374`) | eine binäre Zugangssperre hat keine Warnstufe; `CL:H` wäre eine erfundene Schwere |
| Unbekannte Gefahrenart | Fallback-Kürzel aus `sms_symbol_for` **mit** Stufenbuchstaben | die Stufe ist bekannt, auch wenn die Art es nicht ist |
| Fehlender Zeitraum | Zeit-Token entfällt ersatzlos (`Ziel: TH:H`) | bestehende Konvention, `_tag_time` liefert `""` |
| Telegram-Kurzstil | zieht mit, byte-gleich zur SMS | der Kurzstil ist definitionsgemäß der SMS-Text (per Test erzwungen); PO-Entscheid „Telegram mit führender Null" betrifft die ausführliche Variante |
| Trip + Ortsvergleich | eine Scheibe | es ist **eine** Funktion, die beide Zweige bedienen; ein Split hieße Renderer-Kopie und verstößt gegen die Teilungs-Invariante |

## Scope Assessment

- Produktivdateien: **3** (`official_alerts.py` Kernumbau, `notification_service.py`
  6 Aufrufer, `validator_render_service.py` 1 Aufrufer) + Vorbedingung
  `api/routers/validator.py` (Segment-Feld Onset)
- Geschätzte LoC: **~120–150** Produktivcode
- Testdateien mit echtem Anpassungsbedarf: **8–10** von 14 betroffenen
- Risk Level: **HIGH** (nutzersichtbarer Alarmpfad, alle Kanäle des amtlichen
  Zweigs, Snapshot-Fixture)
