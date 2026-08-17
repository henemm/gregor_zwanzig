# Context: fix-1935-1779-alarm-nachricht-klarheit

Issues: **#1935** (Alarm Message: Formulierung unklar) + **#1779** (E-Mail zur Alarm-Schwelle
schwer verständlich) — dieselbe Beanstandung des PO, fünf Tage auseinander, #1935 mit
konkreteren Belegen.

## Request Summary

Der Text eines Abweichungs-Alarms ist für den Empfänger nicht entzifferbar: die E-Mail-Zeile
„Alarm-Schwelle 1000 m · jetzt darüber ✗" liest sich als Aussage über den **Messwert**,
gemeint ist aber die **Änderungshöhe**. Zusätzlich benennen E-Mail, Alarm-SMS und
Briefing-SMS denselben Ort/Abschnitt jeweils anders (Segmentname vs. Kilometerspanne vs.
Etappenkürzel ohne Trip).

## Der beobachtete Fall (aus #1935)

| Kanal | Ist-Ausgabe |
|---|---|
| E-Mail Verdict-Chip | `↓ -80 % · Änderung über deiner Alarm-Schwelle (1000 m)` |
| E-Mail Datenzeile 1 | `Sichtweite · m` → `1400 m ↓ 280 m -80 %` |
| E-Mail Datenzeile 2 | `Alarm-Schwelle 1000 m` → `jetzt darüber ✗` |
| E-Mail Datenzeile 3 | `Wo & wann` → `🏁 Ziel` |
| Alarm-SMS | `KHW 403 km12-12: -VS280` |
| Briefing-SMS (anderer Pfad) | `E10: …` |

## Root Cause (Kandidat, in Phase 2 zu härten)

`threshold` ist per ADR-0013 / #958 **immer** eine Δ-Auslöseschwelle, nie ein Absolutwert:

```python
# src/output/renderers/alert/model.py:116-121
def over_thr(e: AlertEvent) -> bool:
    return abs(e.value_to - e.value_from) >= e.threshold
```

`|1400 − 280| = 1120 ≥ 1000` → Alarm. Die Datenzeile formuliert diese Tatsache aber zweimal
so, dass sie auf den **Wert** zeigt statt auf die **Änderung**:

- **Label** `Alarm-Schwelle 1000 m` — `_val()` hängt die Metrik-Einheit an, wodurch die Zahl
  wie eine Sichtweiten-Grenze aussieht statt wie ein Änderungsbetrag.
- **Wert** `jetzt darüber ✗` — „jetzt" zeigt zeitlich auf den aktuellen Messwert (280 m), der
  aber **unter** 1000 liegt. Der Leser sieht 280, liest „jetzt darüber" und findet den
  Widerspruch.

Der Verdict-Chip direkt darüber sagt es korrekt („**Änderung** über deiner Alarm-Schwelle").
Chip und Datenzeile widersprechen sich also innerhalb derselben Mail.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py:403-428` (`_datablock_single`) | Erzeugt die drei Datenzeilen inkl. `jetzt darüber ✗` (Z. 417-420) |
| `src/output/renderers/alert/render.py:389-400` (`_verdict_single`, `_SIDE_ADVERB`) | Verdict-Chip; Ergebnis des Vorgänger-Fixes #1865 |
| `src/output/renderers/alert/render.py:527-575` | Mehr-Ereignis-Zweig — eigene, abweichende Wortlaut-Bauform (`Schwelle N` / `über`) |
| `src/output/renderers/alert/render.py:687-760` (`render_sms`) | SMS-Kopf `{trip} km{a}-{b}: `; ruft die gemeinsame Ortsauflösung **nie** auf |
| `src/output/renderers/alert/render.py:655-671` (`_sms_token`) | Token `-VS280`: Vorzeichen + Kürzel + `value_to`; kein Von-Wert, keine Schwelle |
| `src/output/renderers/alert/model.py:105-145` | `over_thr`/`side_label`/`delta_pct`/`km_span` — Kernsemantik, #958 |
| `src/output/renderers/alert/segments.py` | „Eine Ortssprache für alle Alarme" (`format_alert_location`) — von E-Mail/Betreff/Telegram genutzt, von SMS nicht |
| `src/output/renderers/sms_trip.py:47-55, 690` (`_sms_stage_prefix`) | Briefing-SMS-Präfix `E10:` — **anderer** Renderer, anderes Wire-Format |
| `src/output/channels/premium_sms.py:19` | Premium-SMS übernimmt `sms_text` unverändert — kein eigener Text |

## Existing Patterns

- **ADR-0011:** genau *ein* Backend-Renderer je Alarm, vier Kanal-Ausgaben daraus. Eine
  Wortlaut-Änderung an einer Stelle wirkt daher auf alle vier Kanäle — das ist der Hebel.
- Premium-SMS ist kein eigener Textpfad, sondern derselbe String über einen anderen Transport.
- Ortsauflösung ist bereits vereinheitlicht (`segments.py`) — **außer** in `render_sms`.

## Dependencies

- **Upstream:** `AlertEvent`/`AlertMessage` (`alert/model.py`), Metrik-Register (`get_metric`
  für Einheit und Kürzel), `reference_at` aus #1916.
- **Downstream:** `notification_service.py`, `radar_alert_service.py`, Compare-Alarm-Pfad
  (`project.py`), Premium-SMS-Kanal.

## Existing Specs / ADRs

| Dokument | Was es festlegt |
|---|---|
| `docs/adr/0013-alert-threshold-ist-delta-sensitivitaet.md` | `threshold` = Δ-Empfindlichkeit, **kein** Absolut-Referenzwert |
| `docs/adr/0011-alert-render-single-backend-renderer.md` | Ein Backend-Renderer, Registry als Single Source |
| `docs/specs/modules/fix_1861_1865_alarm_mail_klarheit.md` | Vorgänger-Fix genau dieser Zeile (aus „Änderung über ✗" wurde „jetzt darüber ✗") |
| `docs/specs/modules/fix_1744_alarm_format_angleichen.md` AC-5 | Kurznachricht nennt „**keinen** Ortsbezug", ≤140 Zeichen — PO-Entscheid 2026-08-04 |
| `docs/reference/sms_format.md` (v2.28) | Token-Zeile und Kürzel-Register, `{Name}:`-Präfix-Regel |
| `docs/specs/modules/sms_trip_formatter.md` | Briefing-SMS: eine Nachricht je Etappe, Trip-Name im Format nicht vorgesehen |

## Analysis

### Type
Bug (nutzersichtbare Fehlinformation im Wortlaut) mit Feature-Anteil (Kurznachricht wird um
Angaben erweitert, die es heute nicht gibt).

### Gemessene Ist-Ausgabe (Fall A: Sicht 1.400 → 280 m, Schwelle 1.000, Ziel-Etappe)

```
Betreff:  [KHW 403] 🏁 Ziel · ↓ Sicht: 1.400 m→280 m
E-Mail:   Sicht -80% seit dem Briefing
          ↓ -80 % · Änderung über deiner Alarm-Schwelle (1.000 m)
          Sicht · m:              1.400 m ↓ 280 m -80 %
          Alarm-Schwelle 1.000 m: jetzt darüber ✗
          Wo & wann:              🏁 Ziel
Telegram: KHW 403 · 🏁 Ziel · ↓ Sicht
          Sicht · Schwelle 1.000 m · 1.400 m ↓ 280 m · Änderung über
SMS:      KHW 403 km12-12: -VS280            (23 von 140 Zeichen)
```

### Bestätigter Root Cause

Die Zeile `Alarm-Schwelle 1.000 m: jetzt darüber ✗` behauptet zwei Dinge, die beide auf den
**Messwert** zeigen — Einheit „m" am Schwellwert und das Zeitwort „jetzt" —, während die
Tatsache dahinter die **Änderungshöhe** ist (`|1400−280| = 1120 ≥ 1000`). Der Leser sieht in
derselben Mail den aktuellen Wert 280 und die Aussage „jetzt darüber", was einander
widerspricht. Der Verdict-Chip eine Zeile höher formuliert es korrekt („**Änderung** über").

### Weiterer Befund (nicht gemeldet, aus der Messung)

Betreff und Telegram lassen im Mehr-Ereignis-Fall die **Einheit** weg (`Böen 80`,
`Sicht 280`), die E-Mail führt sie mit (`80 km/h`, `280 m`). Ursache: `render.py:358-361` und
`643-648` hängen die Einheit nur an, wenn sie `%` ist, `543-544` hängt sie immer an. „Böen 80"
ist ohne die E-Mail nicht interpretierbar — dieselbe Klasse von Verständlichkeitslücke.

### SMS-Längenbudget

Fall A nutzt **23 von 140 Zeichen**; 117 sind frei. Die Kürze der Kurznachricht ist also
keine Budget-Folge. Achtung: der Segmenttext wird für SMS ASCII-gefaltet — `🏁 Ziel` würde
naiv zu `:checkered_flag: Ziel` (21 Zeichen). Emoji muss **entfernt**, nicht transliteriert
werden.

### Was der Wortlaut heute bindet

| Datei | Bindung |
|---|---|
| `tests/tdd/test_issue_1169_compare_alert_consumer.py::test_ac7_trip_alert_rendering_unchanged` | **byte-genauer** Vergleich der ganzen Plain-Mail — härtester Treffer |
| `tests/tdd/test_alert_bundle_958ff.py` | `test_ac2_…` (Verdict + „jetzt darüber ✗"), `test_ac10_…` (Mehr-Ereignis-Zeile) |
| `tests/tdd/test_978_deviation_line_readability.py` | 4 Tests binden `„· Schwelle N"` und `„20 ↑ 80 km/h"` |
| `tests/tdd/test_957_alert_mail_literal_structure.py` | `✓`/`✗` in der Schwellen-Zeile, `„2 über Schwelle"` |
| `tests/tdd/test_alert_sms_location_positions.py` (3×), `tests/tdd/test_multi_location_onset_alert.py` (1×) | binden den SMS-Kopf `{trip} km{a}-{b}: ` — **gemeinsam für Trip-Δ, Trip-Radar, Compare-Radar und Onset** |

**Keine** Hook-/Gate-Prüfung erzwingt den Alarm-Wortlaut (`renderer_mail_gate.py` verlangt nur
einen frischen Nachweis, die Mail-Validatoren sind für `deviation-alert` No-Op). **Keine**
Duplikate im Frontend (Abwesenheit per `grep` **und** `awk` positiv abgesichert).

### Technical Approach (Empfehlung)

1. **E-Mail-Datenzeile 2 auf die Änderung umstellen** — Label nennt den Änderungsbetrag, der
   Wert stellt ihn der Schwelle gegenüber:
   `Änderung 1.120 m` → `über Alarm-Schwelle 1.000 m ✗` (bzw. `unter … ✓`).
   Damit verschwindet „jetzt" und die Einheit sitzt an der Zahl, für die sie gilt.
2. **Mehr-Ereignis-Zweig analog**: `… · Änderung 50 · Schwelle 40` statt `… · Schwelle 40`.
3. **Alarm-SMS**: Kopf bekommt denselben Ortstext wie die E-Mail (emoji-frei gefaltet), Token
   bekommt den Von-Wert: `KHW 403 Ziel: -VS1400>280`. Der Kopf-Bauer wird dabei **nur** im
   Δ-Pfad geändert, nicht im gemeinsamen Radar-/Onset-Zweig — sonst brechen vier Testfamilien
   ohne fachlichen Grund.
4. Der Trip-Name im Briefing-SMS (`E10:`) bleibt außen vor — anderer Renderer, anderes
   Wire-Format, eigenes Längenbudget.

### Scope Assessment
- Produktivcode: 1–2 Dateien (`alert/render.py`, ggf. `alert/segments.py`)
- Tests: 6 bestehende Dateien anzupassen, 1 neue Verhaltens-Testdatei
- Geschätzt: +180 / −60 LoC (Tests dominieren) → **LoC-Limit 250 wird knapp**, Anhebung auf 500 einplanen
- Risk Level: **MEDIUM** — Wortlaut ist breit gebunden, aber kein Gate und kein Frontend hängt daran

### Dependencies
Upstream `alert/model.py` (`over_thr`, ADR-0013), Metrik-Register (Einheit/Kürzel).
Downstream `notification_service.py`, `radar_alert_service.py`, Compare-Alarm (`project.py`),
Premium-SMS (übernimmt `sms_text` unverändert).

### Open Questions (PO)
- [ ] Neue Formulierung der Schwellen-Zeile bestätigen
- [ ] Darf die Alarm-SMS die Etappe nennen (kippt #1744 AC-5 / PO-Entscheid 04.08.)?
- [ ] Soll die Alarm-SMS den Von-Wert tragen?
- [ ] `E10:`-Thema und Einheiten-Fund: eigene Tickets oder mit hinein?

## Risks & Considerations

1. **Widerspruch zu einer freigegebenen PO-Entscheidung.** #1744 AC-5 hält fest, dass die
   Alarm-SMS keinen Ortsbezug trägt. Faktisch trägt sie `km12-12`, also *doch* einen — nur
   den unbrauchbarsten. „Keinen Ortsbezug" meinte offenbar „keinen Segmentnamen". Wenn die
   SMS künftig die Etappe nennen soll, ist das eine **Rücknahme** dieser Festlegung und
   gehört ausdrücklich in die Spec, nicht still in den Code.
2. **Der PO-Vorschlag aus #1935 („Schwelle war 1.000 m, daher der Alert") ist fachlich
   nicht deckungsgleich** mit ADR-0013: 1000 ist kein Sichtweiten-Grenzwert, sondern der
   Änderungsbetrag, ab dem gemeldet wird. Ein Fix, der die Zahl als Grenzwert darstellt,
   wäre falsch — der Text muss die Δ-Bedeutung *sichtbar machen*, nicht ihr folgen.
3. **Längenbudget SMS:** 140 Zeichen sind hart. Etappenname + Von-Wert + Schwelle passen
   nicht alle zusätzlich hinein; es braucht eine Priorisierung, keine Addition.
4. **Zwei Renderer, zwei Formate.** Das `E10:`-Thema (Briefing-SMS ohne Trip-Namen) liegt in
   einem anderen Wire-Format mit eigenem Längenbudget. Kandidat für eine eigene Scheibe.
5. **Golden-Tests binden den Wortlaut.** Mindestens `test_alert_bundle_958ff.py`,
   `test_957_alert_mail_literal_structure.py`, `test_978_deviation_line_readability.py`,
   `test_alert_location_vocabulary.py`, `test_alert_sms_location_positions.py` fixieren
   Formulierung bzw. Ortssprache und ziehen mit.
6. **Commit-Gates:** `renderer_mail_gate.py` + Mail-Validatoren laufen bei jeder Änderung an
   `src/output/renderers/alert/*.py`.
7. **Regression-Gefahr Ortsvergleich:** derselbe Renderer bedient den Compare-Alarm
   (`location_positions`-Pfad, #1467 S2 AG3b). Änderungen am SMS-Kopf dürfen den
   kopflosen Compare-Zweig nicht zurückbringen.
