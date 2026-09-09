# Context: feat-2176-luftmasse-statt-gewitteransage

**Issue:** #2176 · **Epic:** #1419 · **Track:** Full Process · **Stand:** `2234d037`
**Erstellt:** 2026-09-07

> ⚠️ Diese Datei existiert parallel als uncommittete Fassung in
> `/home/hem/gregor_zwanzig/docs/context/` (Hauptcheckout, dort belegt von einer anderen
> laufenden Session). Diese Worktree-Kopie ist die um §8 (Phase-2-Synthese) ergänzte Fassung.
> Vor dem Commit beide Stände abgleichen — nicht stillschweigend eine Fassung verwerfen.

## Request Summary

Die Gewitterstufe „leicht" (`ThunderLevel.LOW`) wird in allen vier Kanälen als **Gewitterereignis**
formuliert („Leichtes Gewitter möglich ab 14:00", „⚡ Gewitter möglich", `TH:L@14`), misst aber
nachweislich nur eine **labile Luftmasse**. Gesucht ist eine Ausgabe, die den zugrundeliegenden
Wert weiter zeigt, aber kein Ereignis behauptet.

---

## 1. Messgrundlage — selbst nachgemessen, nicht aus dem Ticket übernommen

Quelle: Vorhersage-Mitschnitt (#2030), `/var/lib/gregor/diagnostics/forecast_capture_*.jsonl`,
Trip KHW 403, Fenster 24.08.–05.09.2026, 1 582 Zeilen, Modell durchgängig ICON-D2.
(Das Ticket nennt 2 246 Zeilen — das ist derselbe Bestand ab 21.08., also inklusive der drei
Tage vor Tourbeginn.)

| Stufe | n | Ø CAPE | Ø Regenwahrsch. | Ø Niederschlag | CAPE ≥ 300 J/kg | ohne Regen |
|---|---|---|---|---|---|---|
| kein | 941 | 84 | 10 % | 0,1 mm | 1 % | 91 % |
| **leicht** | **405** | **587** | **25 %** | **0,2 mm** | **100 %** | **73 %** |
| mittel | 114 | 961 | 21 % | 0,2 mm | 98 % | 86 % |
| hoch | 122 | 850 | 43 % | 7,6 mm | 96 % | 23 % |

**Bestätigt:** Jede einzelne „leicht"-Messung lag über der unteren CAPE-Sprosse; drei Viertel
hatten null Niederschlag. Die Umkehrung stimmt ebenfalls — „mittel" hatte eine *niedrigere*
Regenwahrscheinlichkeit als „leicht".

### 🔴 Korrektur an der Erwartung des Epics

Das Epic nennt #2176 „den einzigen Hebel gegen die 13/13 Tage". Nachgemessen an der
**Tages-Höchststufe** je Etappentag:

| Tages-Höchststufe | Tage |
|---|---|
| hoch | 9 |
| mittel | 1 |
| **leicht** | **3** |
| kein | 0 |

Die Tagesaussage entsteht aus der Höchststufe (`trip_report_scheduler.py:3061-3077`,
`max(..., key=thunder_ordinal)`). Eine reine Umformulierung von „leicht" räumt die
Gewitteransage daher nur an **3 von 13 Tagen** aus der Tages-Schlagzeile.

Wo #2176 trotzdem stark wirkt:

- **Stundentabellen** — 405 von 1 582 Messungen (26 %) stehen auf „leicht" und tragen dort ⚡
  plus gelbe Ampel, auch an Tagen mit Höchststufe „hoch".
- **3-Tages-Ausblick** — `_trend_note` (`trip_report_scheduler.py:209-211`) schreibt
  „Gewitter möglich" bei **jeder** Stufe außer „kein".
- **Nacht-Zusatz** — „, nachts leichtes Gewitter ab 03:00" (`day_window.py:239-256`).

Die 10 Tage mit „mittel+" räumt erst **#2178** (CAPE-Leiter) ab. Das gehört in die Spec als
ausdrückliche Erwartungsgrenze, damit die Wirkung nicht überschätzt wird.

---

## 2. Was „leicht" heute auslöst — und was nicht

### 🔴 LOW ist heute schon eine reine Darstellungsstufe

`ORDINAL_LEVEL_BOUNDS` (`src/services/alert_preset.py:114-118`):

```python
"entspannt": (ThunderLevel.HIGH, ThunderLevel.NONE)
"standard":  (ThunderLevel.HIGH, ThunderLevel.HIGH)
"sensibel":  (ThunderLevel.MED,  ThunderLevel.HIGH)
```

Ausgewertet in `_ordinal_change_triggers` (`weather_change_detection.py:979-1003`): eine
Verschärfung meldet nur bei `new_value >= reach_min`. Der niedrigste `reach_min` ist `MED`.
**Kein Empfindlichkeits-Preset erreicht LOW** — „kein → leicht" und „leicht → kein" lösen bei
keiner Einstellung einen Sofortalarm aus.

Gegenprobe am Bestand: Der Trip KHW 403 fährt die Gewitterregel auf „sensibel"
(`alert_rules`, `metric: thunder_level`); unter den 37 versandten Alarmen (#2177-Auswertung)
steht kein einziger Übergang mit „leicht" als Endpunkt.

**Folge: #2176 ist eine reine Darstellungsänderung.** Kein Eingriff in die Alarm-Logik, kein
Risiko, eine Warnung zu verlieren.

### Was LOW sonst noch bewirkt

| Wirkung | Ort | Bemerkung |
|---|---|---|
| Gelbes Ampelband | `metric_format.py:309-313` → `helpers.py:773`, `html.py:854`, `compare_html.py:252`, `outlook.py:402` | eine Quelle, fünf Konsumenten |
| Risk-Engine-Eintrag | `risk_engine.py:126-140` → `RiskLevel.LOW` | Labels in `sms_trip.py:100`, `trip_report.py:912` sind **beide unerreichbar** (s. #1199) |
| 3-Tages-Trend-Hinweis | `trip_report_scheduler.py:209-211` | keine Differenzierung nach Stufe |
| CIN-Deckel | `metric_format.py:377-432` | bei unbekanntem CIN (strukturell bei AROME) wird der CAPE-Ast **auf LOW gedeckelt** |

🔴 **Der CIN-Deckel ist der wichtigste inhaltliche Fund:** „leicht" heißt an diesen Stellen nicht
„schwaches Gewitter", sondern „wir konnten nicht ausschließen, dass Energie da ist". Die Stufe
ist auch ein Auffangwert für Unwissen — was die Gewitterformulierung doppelt falsch macht.

### LOW entsteht aus vier möglichen Signalen

`_signal_levels()` / `thunder_level_from_signals()` (`metric_format.py:434-597`) fusioniert
`wettercode`, `blitzdichte`, `cape`, `blitzpotenzial` über `max_thunder()`.

**Wichtig für die Spec:** Die 100-%-CAPE-Aussage der Messung gilt für **diesen Trip mit diesem
Modell** (ICON-D2, AT/IT), nicht strukturell. LOW *kann* auch aus Wettercode, Blitzdichte oder
LPI entstehen — dann steht dahinter sehr wohl eine Gewitteraussage einer echten Quelle.
Eine Formulierungsänderung, die pauschal „Luftmasse" sagt, wäre in diesen Fällen ihrerseits
falsch. Die Herkunft ist bereits mitgeführt (`thunder_signal_carriers()`,
`THUNDER_SIGNAL_LABEL_DE` in `app/thunder_scale.py:99-104`) und im E-Mail-Text als Suffix
sichtbar („· CAPE", „· Blitzdichte, CAPE") — **nicht** in SMS/Premium-SMS.

---

## 3. Wortlaut-Karte: wo die Gewitter-Behauptung entsteht

### Geteilte Quellen (bereits vorhanden)

| Quelle | Datei | Was sie liefert |
|---|---|---|
| `THUNDER_LABEL_DE` | `output/metric_format.py:284-289` | Stufenwörter `kein/leicht/mittel/hoch` — **alle vier Kanäle** |
| `thunder_ampel_band()` | `output/metric_format.py:309-327` | Stufe → Ampelfarbe |
| `THUNDER_SIGNAL_LABEL_DE` | `app/thunder_scale.py:99-104` | Herkunfts-Suffix, nur E-Mail |
| `resolve_thunder_day_branch()` | `output/renderers/email/thunder_branch.py` | Zweigwähler 3-Tages-Vorschau, 4 kanaleigene Formatierer |
| `MetricDefinition id="thunder"` | `app/metric_catalog.py:429-449` | `label_de="Gewitter"`, `compact_label="⚡"`, `sms_code="TH"` |

### Die Sätze — sechs unabhängige Formulierungen

| Textbaustein (wörtlich) | Ort | Kanal |
|---|---|---|
| `"Leichtes Gewitter möglich ab {hh}:00"` | `trip_report_scheduler.py:2831-2841` **und** `:3070-3077` (wortgleich, zwei Bauwege) | E-Mail-Ausblick, SMS-Lückenmarker |
| `"Gewitter möglich"` | `trip_report_scheduler.py:209-211` (`_trend_note`) | 3-Tages-Trend |
| `"⚡ Gewitter möglich ab {zeit} (Segment X, >{elev}m)"` | `trip_report.py:758` (`_compute_highlights`) | E-Mail HTML+Klartext |
| `"Gewitter {stufe} ab {hh}:00 · stärkste {hh}:00{origin}{hail}"` | `email/helpers.py:1780-1792` | E-Mail (3 Formate), **nicht** SMS |
| `"⚡ möglich {h}:00–{h}:00"` / `"Gewitter möglich {h}:00–{h}:00"` | `trip_report.py:572-629` + `compact_summary.py:613-624` (identisch) | E-Mail-Klartext, Telegram |
| `", nachts leichtes Gewitter ab {hh}:00"` | `day_window.py:239-256` | E-Mail-Vorschau, Telegram |
| `"⚡leicht@14"` / `"leicht @14"` | `thunder_branch.py:168-214` | alle vier Formate |
| `"⚡ {wort}"` | `narrow.py:255-258` (`_tg_day_footer`) | Telegram-Bubble-Fußzeile |
| `TH:L@14` | `sms_trip.py:321-323` + `output/tokens/metrics.py` | SMS **und** Premium-SMS |
| `"Gewitter"` (Betreff) | `output/subject.py:27` | SMS-Betreff, nicht stufenabhängig |
| Stufenwort + Hagel/Herkunft | `email/compare_html.py:165-215`, `comparison.py:75` | Ortsvergleich |
| `_thunder_word()` | `output/renderers/alert/render.py:49-58` | Alarm-Renderer, alle vier Kanäle |

**Kernbefund:** Das Stufen*wort* hat bereits eine geteilte Quelle. Die **Deutung** („Gewitter",
„möglich", „⚡") bringt jeder Satz selbst mit — sechsfach getrennt formuliert. Genau deshalb
verlangt das Ticket einen Wächter-Test über alle vier Kanäle: ohne den fällt beim nächsten
Umbau eine der sechs Stellen zurück.

### Premium-SMS

Kein eigener Renderer. `output/channels/premium_sms.py` sendet `report.sms_text` unverändert
(Docstring Z. 19-21: „kein eigener Renderer, damit SMS und Premium-SMS inhaltlich nicht
auseinanderlaufen"). Premium-SMS teilt sich `sms_trip.py` vollständig mit SMS.
**Folge:** „alle vier Kanäle" heißt beim Bau faktisch **drei** Renderer-Familien —
E-Mail (HTML/Klartext/Kompakt), Telegram, SMS(+Premium-SMS).

### Wo der CAPE-Wert sichtbar bleibt

| Ort | Kanal | Text |
|---|---|---|
| `trip_report.py:841` | E-Mail | `"⚡ Hohe Gewitterenergie: CAPE {wert} J/kg"` — erst ab 1 000 J/kg |
| `email/helpers.py:835-841` | E-Mail-Stundentabelle | Spalte „CAPE", Ampel-Kreis oder nackte Zahl |
| `app/metric_catalog.py:451` | Katalog | `label_de="Gewitterenergie (CAPE)"`, `selectable=False` seit #1585 |

🔴 Der Ø-CAPE-Wert bei „leicht" ist **587 J/kg** — die Highlight-Schwelle liegt bei 1 000.
**Bei genau den Fällen, um die es in #2176 geht, ist der Zahlenwert heute also NICHT sichtbar**,
außer die Stundentabelle führt die CAPE-Spalte. Die AC „der zugrundeliegende Wert bleibt
einsehbar" ist damit **heute nicht erfüllt** und braucht eigene Arbeit.

---

## 4. Dependencies

- **Upstream:** `app/models.py` (`ThunderLevel`), `app/model_registry.py` (CAPE-/LPI-Leitern je
  Modell und Gebiet), `app/thunder_scale.py`, `providers/*` (Signalbeschaffung)
- **Downstream:** alle drei Renderer-Familien, Ortsvergleich (`compare_html.py`,
  `comparison.py`), Alarm-Renderer (`alert/render.py`), Frontend (`weatherUtils.ts`,
  `WIcon.svelte`, `Dot.svelte`, `alertMetricTable.ts` u. a.)

---

## 5. Existing Specs & ADRs

### 🔴 ADR-0048 widerspricht dem Code — Deckel aufgehoben, ADR nicht abgelöst

`docs/adr/0048-modellabhaengige-schwellen-statt-einer-zahl.md`, Status **Akzeptiert**, Z. 62-63:

> „Unberührt bleibt die Produktentscheidung aus feat_1474 AC-6: **CAPE misst Energie, kein
> Ereignis** und eskaliert nie über `LOW`. Die Schwelle wird variabel, die Deckelung bleibt."

Commit `937bba52` (#1679, „CAPE-Leiter gepaart mit Konvektionshemmung (CIN) statt
LOW-Deckelung") hat den Deckel entfernt. Der CAPE-Ast läuft seither über eine dreisprossige
Leiter (`_signal_levels`, `metric_format.py:466-473`; Sprossen aus
`model_registry.cape_ladder_thresholds_jkg()`) und kann MED und HIGH erreichen.

Die Änderung ist in `docs/specs/modules/feat_1679_cin_paarung_cape_leiter.md` sauber begründet
(„ersetzt die pauschale LOW-Deckelung durch das bereits PO-finalisierte Zielverfahren"), aber
**es gibt kein ablösendes ADR** — 0048 steht unverändert auf „Akzeptiert" und behauptet das
Gegenteil des Codes. Ebenso unberührt: `feat_1474_gewitter_befund_stufen.md` AC-6.

**Gemessene Folge** (ICON-D2, 24.08.–05.09., „welche Stufe hätte CAPE allein ergeben?"):

| gezeigte Stufe | n | CAPE allein hätte ergeben |
|---|---|---|
| kein | 1 187 | 100 % kein |
| leicht | 467 | 76 % leicht · 20 % mittel · 4 % hoch (CIN-gedämpft) |
| **mittel** | **114** | **91 % mittel** — die Stufe ist praktisch reines CAPE |
| hoch | 128 | 29 % hoch · 30 % mittel · **37 % nur leicht** — von anderen Signalen getragen |

„hoch" trägt; „mittel" ist der Eimer, den ADR-0048 verboten hatte.

### Weitere Bindungen

| Dokument | Zusicherung | Durch #2176 verletzt? |
|---|---|---|
| `docs/adr/0025-…` | eine Rohdaten-Quelle je Gewitter-Aussage | nein (Datenquelle, nicht Wortlaut) |
| `docs/adr/0043-…` | Empfindlichkeit als Niveau; Tabelle nennt noch 3 Stufen (vor #1474) | Doku veraltet, Mechanik stufenzahl-agnostisch |
| `docs/adr/0047-…`, `0057-…` | Beschaffung/Fallback, Fusionsort | nein |
| `feat_1474_gewitter_befund_stufen.md` | AC-11 „jeder Kanal zeigt ein erkennbares ‚leicht'"; AC-6 CAPE-Deckel | **ja** — Ursprungs-Spec |
| `fix_2010_2011_gewitter_stufenwoerter.md` | Telegram zeigt in jedem Pfad `kein/leicht/mittel/hoch` | **ja** |
| `fix_1491_gewitter_ampelkreis.md` | AC-7 bindet Wort **und** Hex `#fbeeb8` | **ja** |
| `fix_1488_sb_gewitter_mailwort.md` | AC-4 Bestandsschutz: `thunder_word` liefert bei LOW exakt „leicht" | **ja** |
| `fix_1948_s6_alarm_stufenwort.md` | AC-7 „deine Grenze leicht ist gerissen"; AC-6 „leicht" nie als Abstandseinheit | **ja**, zwei Rollen trennen |
| `fix_1474b_gewitterschwelle_cockpit.md` | Cockpit zeigt „leicht" als Gelb, Standard „ab leicht" | **ja** |
| `thunder_threshold_katalog.md` | genau drei wählbare Alarmschwellen `leicht/mittel/hoch` | **ja** |
| `fix_1592_s1_…`, `fix_1592_c2_…` | Deckelungs-Kette „bleibt bei leicht" | **ja**, gemeinsam mit 0048 revidieren |
| `fix_1760_cin_vorzeichen.md` | CIN-Dämpfungsbänder nennen „leicht" als Ziel | **ja** |
| `feat_1493_gewitter_onset_sichtbar.md` | Tests auf `endswith("⚡leicht")` | **ja** |
| `fix_2012_gewitter_stufen_migration.md` | Alt-3-Stufen bewusst NICHT auf LOW abgebildet | Begründung verliert Bezug bei Auflösung |
| `thunder_scale_guard.md` | AST-Wächter auf die Enum-Namen | wortlaut-unabhängig; bei Auflösung mit anfassen |

**Fachlicher Anknüpfungspunkt:** `docs/features/gewitter-gesamtkonzept.md` benennt selbst als
offene Weiterentwicklung, dass die frühere Notbremse „CAPE eskaliert nie über leicht" nur
existierte, weil die Gegengröße fehlte.

### Vokabular

Kein Treffer für „Luftmasse", „Labilität", „Konvektionspotenzial" im Repo. Etabliert ist
**„Gewitterenergie"** für CAPE selbst (`app/metric_catalog.py:451` als Register,
`fallback_notice.py:73`, `trip_report.py:841`, `frontend/.../alertMetricLabels.ts:35`).
Eine Luftmassen-Formulierung wäre ein **neuer** Begriff ohne Präzedenzfall.

## 6. Wächter-Tests

Rund **30 Tests** binden den String „leicht" oder die daraus gebauten Sätze hart und würden bei
einer Wortlaut-Änderung rot:

| Testdatei | Kanal | Bindung |
|---|---|---|
| `test_thunder_stage_words_from_canonical_source.py` | kanalneutral | **die SSoT selbst** — hier muss der neue Wortlaut zuerst definiert werden |
| `test_thunder_origin_outlook.py`, `test_thunder_origin_preview.py` | E-Mail HTML+Klartext, Telegram | exakte Strings `"leicht @16 · CAPE"`, `"⚡ Gewitter möglich ab …"` |
| `test_thunder_low_output_channels.py`, `test_thunder_low_risk_overview.py` | E-Mail, Telegram, SMS | `"leicht" in …` durchgängig |
| `test_thunder_column_ampel.py` | E-Mail + Ortsvergleich | Wort **und** Hex `#fdf4cd` |
| `test_outlook_day_night_thunder_split.py`, `test_kompaktmail_ausblick_tagesfenster.py` | E-Mail Kompakt/Outlook | `"leicht@5(hoch@15)"` |
| `test_thunder_forecast_day_window.py`, `test_thunder_night_addendum.py` | E-Mail Trend/Nacht | `"Leichtes Gewitter möglich ab HH:00"` |
| `test_telegram_thunder_low_level.py`, `test_telegram_thunder_window_konsistenz.py` | Telegram | `"leicht" in confirmation_body` |
| `test_sms_fidelity_preview.py:424` | SMS + Premium-SMS | Byte-Baseline `"TH:L@8(H@12)"` |
| `test_compare_metric_catalog_endpoint.py:222` | Compare-API | Literal `["kein","leicht","mittel","hoch"]` |
| `test_thunder_mail_prosa_low_binding.py`, `test_thunder_mention_threshold_shared.py` | E-Mail | `"Gewitter leicht ab"` |

**Bleibt grün** (nur Enum/Ordinal, aus der SSoT abgeleitet): `test_cape_*`-Familie,
`test_thunder_fusion_prefers_hourly_max.py`, `test_thunder_ladder_shared_across_signals.py`,
`test_compare_thunder_level_tie_break.py`, `test_thunder_scale_local_copy_guard.py`.

⚠️ **Wird das Enum-Member `ThunderLevel.LOW` selbst entfernt**, bricht auch diese Gruppe —
dann ist praktisch jeder Test betroffen, der `ThunderLevel.LOW` importiert.

⚠️ **Nicht verwechseln:** `TH:L` in `test_official_alert_sms_ortskopf.py` und
`test_official_alert_template_render.py` ist die **amtliche** MeteoAlarm-Stufe, nicht
`ThunderLevel.LOW`.

---

## 7. Risks & Considerations

1. **🔴 Widerspruch zu einer entschiedenen Grundsatzfrage.** #1419 Abschnitt 9 legt vier
   nutzersichtbare Stufen fest: `keine / möglich / wahrscheinlich / akut` (PO 2026-07-29).
   „möglich" für LOW bleibt eine Gewitteransage. Entweder LOW wird aus der Gewitterleiter
   **herausgelöst** (die vier Stufen beginnen dann bei „möglich") oder Grundsatzfrage 1 wird
   **neu beantwortet** (→ ADR). Ohne Entscheidung wird zweimal umbenannt.
2. **🔴 LOW ist nicht immer CAPE.** Eine pauschale Luftmassen-Formulierung wäre falsch, wenn LOW
   aus Wettercode/Blitzdichte/LPI stammt. Die Herkunft ist verfügbar, in SMS aber nicht
   ausgegeben — die Formulierung muss entweder herkunftsabhängig sein oder so neutral, dass sie
   in beiden Fällen stimmt.
3. **🔴 Die AC „Wert bleibt einsehbar" ist heute unerfüllt** (Highlight-Schwelle 1 000 J/kg vs.
   Ø 587 J/kg bei „leicht"). Eigene Arbeit, nicht nur Umformulierung.
4. **Wirkungsgrenze.** Nur 3 von 13 Tagen verlieren die Gewitter-Schlagzeile; die übrigen 10
   hängen an #2178. In der Spec ausdrücklich benennen.
5. **Der Ortsvergleich erbt mit.** `compare_html.py` und `comparison.py` lesen dieselben
   geteilten Quellen. Das ist keine Ortsvergleich-Arbeit im Sinne der Zurückstellung, sondern
   eine unvermeidliche Folge — aber die Compare-Mail muss mit validiert werden.
6. **⏳ Die Messgrundlage verfällt.** `forecast_capture.py` hält `AUFBEWAHRUNG_TAGE = 30`; die
   Datei vom 21.08. fällt um den 20.09. weg. Wer die Messung später belegen können will, muss
   eine Kopie als versionierte Fixture sichern.
7. **Sechs Formulierungsstellen, ein Wächter.** Ohne eine neue geteilte Quelle für die
   *Stufenaussage* (nicht nur das Stufenwort) bleibt die Änderung an sechs Orten dupliziert.
   Passt zur PO-Vorgabe „möglichst viel Code teilen".
8. **Zwei bedeutungsverschiedene `TH`-Kürzel** (`output/tokens/metrics.py` = unsere Stufe;
   `output/tokens/hazard_symbols.py:16` = amtliche Warnung). Beim Anfassen des SMS-Tokens nicht
   verwechseln.

---

## 8. Analysis (Phase 2 Synthese)

### Type

Feature (Wortlaut-/Darstellungsänderung, keine Alarm-Logik — s. §2 "LOW ist heute schon eine
reine Darstellungsstufe").

### Affected Files (with changes) — Schätzung, in der Spec zu präzisieren

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/metric_format.py` | MODIFY | `THUNDER_LABEL_DE`, `thunder_ampel_band()` — ggf. neue geteilte Quelle für die *Stufenaussage* (nicht nur das Wort) |
| `src/app/thunder_scale.py` | MODIFY | `THUNDER_SIGNAL_LABEL_DE`, Herkunfts-Suffix — muss die neue Formulierung herkunftsabhängig tragen können |
| `src/app/metric_catalog.py` | MODIFY | `MetricDefinition id="thunder"`, ggf. `label_de`/`compact_label` |
| `src/services/trip_report_scheduler.py` | MODIFY | Z. 209-218 (`_trend_note`), 2831-2841 + 3070-3077 (Lückenmarker, zwei Bauwege), 3061-3077 (Tages-Höchststufe) |
| `src/output/renderers/trip_report.py` | MODIFY | Z. 572-629 (`_compute_highlights`), 758, 841, 912 (unerreichbares Risk-Label) |
| `src/output/renderers/email/helpers.py` | MODIFY | Z. 773, 835-841 (CAPE-Spalte), 1780-1792 |
| `src/output/renderers/email/html.py` | MODIFY | Z. 854, 1361 |
| `src/output/renderers/email/plain.py` | MODIFY | Z. 330 |
| `src/output/renderers/email/thunder_branch.py` | MODIFY | Z. 168-214, Zweigwähler 3-Tages-Vorschau |
| `src/output/renderers/email/compare_html.py` | MODIFY | Z. 165-215, 252 (Ampelband Ortsvergleich) |
| `src/output/renderers/day_window.py` | MODIFY | Z. 239-256, Nacht-Zusatz (Kandidat — Pfad in Spec-Phase gegen `src/app/day_window.py` abgrenzen) |
| `src/output/renderers/compact_summary.py` | MODIFY | Z. 613-624 |
| `src/output/renderers/narrow.py` | MODIFY | Z. 255-258, Telegram-Bubble-Fußzeile |
| `src/output/renderers/sms_trip.py` | MODIFY | Z. 100, 321-323, SMS+Premium-SMS-Token |
| `src/output/renderers/comparison.py` | MODIFY | Z. 75 |
| `src/output/renderers/alert/render.py` | MODIFY | Z. 49-58, `_thunder_word()`, alle vier Kanäle |
| `src/output/subject.py` | MODIFY | Z. 27, SMS-Betreff |
| `frontend/src/lib/utils/weatherUtils.ts` u. a. Frontend-Konsumenten (Kandidaten, s. §4 Downstream) | MODIFY | Cockpit/Compare-Darstellung — Umfang erst in Spec-Phase klar |
| ~30 Testdateien (s. §6 Wächter-Tests) | MODIFY | Wortlaut-Anpassung, mind. 1 neuer Wächter-Test über alle vier Kanäle |
| ADR (neu oder Ergänzung zu 0048) | CREATE/MODIFY | Grundsatzfrage 1 (s. Open Questions) |

### Scope Assessment

- Files: ~17 Quelldateien + ~30 Testdateien + 1 ADR — deutlich über dem Standard-Zuschnitt
- Estimated LoC: grob +150/-100 (viele kleine Textbausteine, keine strukturelle Änderung) —
  **LoC-Limit 250/Workflow ist real gefährdet**, `loc_limit_override` in der Spec-Phase einplanen
- Risk Level: **LOW** für Alarm-/Versandlogik (§2: LOW löst bei keinem Preset einen Sofortalarm
  aus), **MEDIUM** für Umfang/Vollständigkeit (sechs unabhängige Formulierungsstellen, Gefahr
  einer sechsten übersehenen Stelle ohne geteilte Quelle)

### Technical Approach

Empfehlung: eine **neue geteilte Quelle für die Stufenaussage** (nicht nur das Stufenwort)
einführen, analog zu `THUNDER_LABEL_DE`/`THUNDER_SIGNAL_LABEL_DE` — die sechs Sätze aus §3 rufen
diese Quelle statt eigener String-Bausteine auf. Herkunftsabhängigkeit (§2 „LOW entsteht aus vier
möglichen Signalen") muss die Quelle selbst tragen, sonst wird die Luftmassen-Formulierung in den
Fällen falsch, in denen LOW aus Wettercode/Blitzdichte/LPI stammt. Der CAPE-Zahlenwert muss an
mindestens einer Stelle unterhalb der heutigen 1 000-J/kg-Highlight-Schwelle sichtbar werden,
sonst bleibt AC „Wert bleibt einsehbar" unerfüllt (§3, CAPE-Wert bei „leicht" liegt im Schnitt bei
587 J/kg). Blockiert bis zur Produktentscheidung unten — siehe Open Questions.

### Dependencies

Siehe §4 (Upstream/Downstream) und §5 (ADRs/Specs) — 13 bestehende Specs/ADRs sind durch eine
Wortlautänderung berührt, davon 0048 sachlich widersprüchlich zum Code (Deckel entfernt seit
#1679, ADR nicht abgelöst).

### Open Questions — Produktentscheidung, nicht technisch — PO-Entscheid 2026-09-08

- [x] **Grundsatzfrage 1 (Epic #1419, PO 2026-07-29):** **Entscheid (Henning, 2026-09-08): Weg
  (a) — LOW verlässt die Gewitterleiter.** „leicht" wird eine eigene, alarmlose
  Luftmassen-Größe außerhalb der vier Gewitterstufen `keine/möglich/wahrscheinlich/akut`; die
  vier Stufen beginnen künftig beim heutigen MED. Für die Spec-Phase folgt daraus: Grundsatzfrage
  1 aus #1419 braucht eine dokumentierte Anpassung (Stufe LOW ist kein Mitglied der Gewitterleiter
  mehr), ADR-0048 muss ohnehin sachlich nachgezogen werden (s. §5).
- [x] **Erwartungsgrenze bestätigen:** **Entscheid (Henning, 2026-09-08): jetzt einzeln
  umsetzen**, nicht mit #2178 bündeln. #2176 geht unabhängig vom Fortschritt bei #2178 in die
  Spec-Phase — korrigiert 3 von 13 Tagen und beseitigt eine sachlich falsche Aussage an den
  übrigen 10, auch wenn dort die Tages-Schlagzeile weiter „mittel"/„hoch" zeigt.
