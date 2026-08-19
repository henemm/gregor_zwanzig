# Context: #1948 Scheibe S4 — Zweig-c-Zielbild (Nowcast/Onset-SMS)

**Workflow:** `fix-1948-s4-nowcast-sms` · **Issue:** #1948 · **Track:** Full Process (Score 4)
**Erstellt:** 2026-08-19

## Request Summary

Die Nowcast-/Onset-Kurznachricht (Zweig c) soll auf das einheitliche Alarm-Format nachziehen:
Kopf über die gemeinsame Ortsauflösung statt selbstgebautem `km{a}-{b}:`, und Token von
`TH!{onset_minutes}` (Countdown) auf `TH@{onset_time}` (konkrete Uhrzeit). PO-Zielbild aus
Konzept v3 Abschnitt 1: **`Ziel: TH@15:40`** — heute lautet dieselbe Nachricht `km8-8: TH!8`.

## Ist-Zustand (belegt)

`src/output/renderers/alert/render.py:422-438` (`_render_sms_onset`) nutzt **weder** `_km_str`
**noch** `_km_str_onset` **noch** `format_alert_location` — der Kopf ist hand-verdrahtet:

```python
token = f"TH!{e.onset_minutes}" if e.is_convective else f"R!{e.onset_minutes}"
a, b = int(round(e.km_from)), int(round(e.km_to))
if getattr(e, "location_label", None):
    body = f"{trip} km{a}-{b}: {token}"     # Compare, >1 Ort
else:
    body = f"km{a}-{b}: {token}"            # Trip UND Compare mit genau 1 Ort
```

Schreibweise weicht vom gemeinsamen Kopf ab: `km8-8` (kein Leerzeichen, ASCII-Bindestrich) vs.
`km 8–8` (Leerzeichen, En-Dash) aus `format_alert_location` (`segments.py:101`).

Vorbild für den Zielzustand ist der Trip-Δ-Kopf in `render_sms` (`render.py:910-916`):
`head = f"{_ascii_alert_location(_km_str(msg))}: "`.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py:422` | `_render_sms_onset` — **die** zu ändernde Funktion |
| `src/output/renderers/alert/render.py:129-170` | `_location_of`, `_km_str`, `_km_str_onset` — die Kopf-Bausteine |
| `src/output/renderers/alert/segments.py:91` | `format_alert_location` — Auflösungsreihenfolge label → Segment → km |
| `src/output/renderers/alert/model.py:36-51` | `OnsetEvent` — `onset_time` (`str`, nie `None`), `onset_minutes`, `segment_id`, `location_label` |
| `src/output/renderers/alert/project.py:319-398` | `to_multi_location_onset_alert_message` — setzt `location_label` nur bei >1 Ort |
| `src/services/notification_service.py:1373` | einziger Produktiv-Aufruf `render_sms`, Ergebnis geht an SMS **und** Premium-SMS |
| `src/services/validator_render_service.py:217-259` | `_render_nowcast_replay` — S2-Einspeiseweg, nutzt echtes `_derive_result` |

## Dependencies

- **Upstream:** `OnsetEvent.onset_time` wird lokal-ortszeitlich als `"HH:MM"` befüllt
  (`trip_alert.py:1274`, `project.py:382`), Typ `str`, kein `None`-Fall im Produktivcode.
- **Downstream:** ein einziges Rendering bedient **beide** Kurzkanäle — `limit=140` gilt für
  SMS und Premium-SMS gemeinsam (`notification_service.py:1543/1558`), kein eigener Grenzwert
  für Premium-SMS. Kürzung ist ein harter Endschnitt `body[:limit]`, keine Token-Priorisierung.

## Existing Specs

- `docs/specs/modules/fix_1948_s3_sms_sofortfix.md` — direkte Vorlage (Zweig a). Dessen **AC-7**
  sichert ausdrücklich zu, dass `_render_sms_onset` byte-identisch bleibt; genau diese Zusicherung
  läuft mit S4 planmäßig aus.
- `docs/specs/modules/alarm_testeinspeisung.md` — S2-Einspeiseweg (`nowcast_frames`-Payload)
- `docs/specs/modules/alarm_eingangsprotokoll.md` — S1-Mitschnitt

## 🔴 Zielkonflikt — muss die Spec entscheiden

`tests/tdd/test_alert_location_vocabulary.py:573-585`
(`test_kurznachricht_des_nowcasts_nennt_keinen_ort`) fordert heute wörtlich das **Gegenteil** des
Zielbilds: `"Segment" not in sms`, `"Ziel" not in sms`, `"🏁" not in sms`, und `re.search(r"km\d", sms)`
**muss** matchen. Docstring: *„der Betreff wechselt auf '🏁 Ziel', die Kurznachricht bleibt bei 'km8-8'."*

Das PO-Zielbild `Ziel: TH@15:40` ist genau die Segment-Sprache, die dieser Test verbietet. Sobald
`_render_sms_onset` über `format_alert_location` geht und das Event eine `segment_id` trägt, löst
der Kopf zu `🏁 Ziel` auf statt zu `km 8–8`. Entweder wird der Test bewusst abgelöst (Präzedenz:
S3 hat #1744 AC-5 für Zweig a genauso abgelöst) — oder das Zielbild ist so nicht umsetzbar.

## Offene Entscheidungsfragen für die Spec

1. **Zieht der Regen-Zweig mit?** Konzept nennt nur `TH@15:40`. Ob `R!{min}` ebenfalls auf
   `R@{onset_time}` wechselt, ist nirgends entschieden. Bestimmt, wie viele Tests rot werden.
2. **Compare-Onset mit genau EINEM Ort nennt den Ort heute gar nicht.** `location_label` bleibt
   per Invariante `None` (`project.py:378`), `km_from=km_to=0.0` → SMS lautet `km0-0: R!25`; der
   Ortsname steht ungenutzt in `msg.trip_short`. Heilt S4 das mit (`format_alert_location` Stufe 1),
   oder bleibt der Ortsvergleich byte-identisch?
3. **Doppelpunkt-Form:** Leitsatz sagt „ein Gewitter heißt in allen drei Zweigen `TH:`", das
   Zielbild für Zweig c schreibt `TH@15:40` ohne Doppelpunkt. Bei c folgt kein Stufenwert.

## Risks & Considerations

- **7 bestehende Tests werden rot** und müssen fortgeschrieben werden (nicht gelöscht):
  `test_multi_location_onset_alert.py:262` (Goldstring `km5-18: R!12`) ·
  `test_issue_919_radar_alert_canonical.py:143-165` (`R!12`/`TH!8`) ·
  `test_952_onset_alert_fidelity.py:336` (Regex `km(\d+)-(\d+)` bricht am Leerzeichen) ·
  `test_alert_sms_segment_head.py:194-227` (AC-12, **zugleich Pendant-Wächter**) ·
  `test_alert_sms_location_positions.py:934/960` (2× Versandpfad, Marker `live`) ·
  `test_alert_preview_nowcast_replay.py:105` (Regex `R!(\d+)` + Minuten-Semantik) ·
  `test_alert_location_vocabulary.py:573` (der Zielkonflikt oben).
- **Pendant-Wächter erhalten:** `test_ac12_...` vergleicht Trip- und Compare-Ergebnis
  gegeneinander. Er darf auf das neue Format umgestellt werden, aber die Differenzlogik
  (Compare behält den Namen, Trip nicht) muss als Vergleich bestehen bleiben.
- **Leitplanke #1599 ist präventiv, nicht scharf** (Korrektur zur Intake-Annahme): Der
  Alarm-Renderer importiert `app.day_window` **nicht**; `display_end_time()` liegt außerhalb der
  Aufrufkette, und `onset_time` entsteht als reine Uhrzeit-Arithmetik in `radar_service.py:274`.
  Die Regel bleibt trotzdem als Nicht-Berührungs-Nachweis in der Spec stehen.
- **AC-4-Bedenken entschärft** (Korrektur zur Intake-Annahme): Der Kommentar an `_km_str_onset`
  nennt nur „AC-4", nicht #1170/#1467, und betrifft den **Telegram**-Pfad. `_km_str_onset` nimmt
  `location_label` gar nicht entgegen — eine Wiederverwendung im SMS-Kopf bricht die Zusicherung
  nicht. Das reale Risiko liegt bei `segment_id` (Zielkonflikt oben).
- **AC-10 (#1935/#1779) hat keinen eigenen Test** — nur indirekt über die Regressionstests
  mitgeprüft. Lückenbefund, gehört nach #1196/#1199, nicht in diese Scheibe.

## Verifikation nach Konzept-Leitprinzip — Grenze belegt

Echte S1-Zweig-c-Mitschnitte existieren auf dem Server (nicht im Repo, `data/` ist ungetrackt):

| Ablage | Aufzeichnungen | mit Regen ≥0,1 mm/h | mit konvektivem Frame | Maximum |
|---|---|---|---|---|
| Prod `/var/lib/gregor/debug/alert_input/nowcast/` | 50 (INCA, 46.5641/13.4792 = KHW) | 14 | **0** | 2,8 mm/h |
| Staging `/var/lib/gregor-staging/…` | 6 (AROME-FR, INCA, radar) | 3 | **0** | 9,2 mm/h |

**Folge:** Der Regen-Pfad ist mit echten Meldungen verifizierbar. Der Gewitter-Pfad — also genau
das Zielbild `TH@15:40` — ist es **nicht**, weil in keiner der 56 Aufzeichnungen ein konvektiver
Frame steckt. Für Gewitter bleibt eine abgeleitete Variante (echte Frames, `is_convective` gesetzt)
plus Unit-Test. Das gehört als Grenze in die Spec, statt später als „mit echten Daten verifiziert"
verbucht zu werden.

Einspeiseweg (S2), erprobt und deterministisch im Kern-Testlauf:
`POST /api/trips/{trip_id}/alert-preview?user_id=…` mit `{"nowcast_frames": {source, frames[], km_from, km_to}}`
→ Antwort trägt `onset_detected` und das gerenderte `sms`. Der Replay nutzt dasselbe
`_derive_result` wie der Live-Pfad, keinen Test-Sonderweg.
