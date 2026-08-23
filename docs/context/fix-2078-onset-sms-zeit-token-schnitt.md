# Context: Onset-Kurznachricht — harter Zeichen-Schnitt zerschneidet das Zeit-Token (#2078)

## Request Summary
`_render_sms_onset` baut den Kopf (Ortsname) ohne Längenbegrenzung und schneidet danach
den fertigen Text stur bei `limit` (Default 140) ab. Bei ausreichend langem Ortsnamen trifft
der Schnitt mitten ins Zeit-Token am Ende — die Kurznachricht (SMS/Premium-SMS/
Telegram-Kurzstil) trägt dann eine **inhaltlich falsche** statt einer fehlenden Uhrzeit
(`Sa0:40` → `Sa0:4`). Fix: Kopf vor dem Zusammensetzen kappen, analog zu den Nachbarzweigen.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/render.py:895-964` | `_render_sms_onset` — Fundstelle des Bugs. Kopf (`head`, Zeilen 957-962) wird ungekappt gebaut, `body[:limit]` (Zeile 964) schneidet hart am Ende. |
| `src/output/renderers/alert/render.py:466-471` | `_render_sms_onset_shift_only` — **identisches Muster** (ungekappter Kopf + harter Endschnitt), gleicher Bug, nicht Teil der Issue-Meldung. |
| `src/output/renderers/alert/render.py:1420-1438` | `_render_sms_corridor_only` — Referenzmuster: `trip[:16]`, `location_label[:24]`/`where[:24]` werden VOR dem Zusammensetzen gekappt. |
| `src/output/renderers/alert/render.py:1472-1533` | `_render_sms_body` — Dispatcher zu allen SMS-Zweigen; eigener Fallback-Kopf-Zweig (Zeile 1530, `_km_str(msg)`) ist ebenfalls ungekappt, aber `_km_str` liefert typischerweise kurze km-Spannen/Segmentnamen, kein frei langer Ortsname. |
| `src/output/renderers/alert/render.py:1611-1621` | `_ascii_alert_location` — Piktogramm-Entfernung + ASCII/GSM-7-Faltung + `"Segment " → "Seg "`; erzeugt den `head`-Text in `_render_sms_onset`. |
| `src/services/notification_service.py:1487-1492` | Einziger Produktivaufruf für den Alarm-Pfad: `render_alert_sms(alert_msg, location_positions=...)` — kein `limit`-Override, also Default 140. |
| `src/services/notification_service.py:1598,1666,1680` | Dieselbe `sms_body`-Variable geht unverändert an SMS, Premium-SMS **und** Telegram-Kurzstil (Zeile 1598) — ein Fix am Renderer wirkt automatisch auf alle drei Kanäle. |
| `tests/tdd/test_alert_sms_segment_head.py` | Bestehende Kopf-Tests (AC-5 bis AC-8, AC-12 aus #1935/#1779) — Referenzmuster für Testaufbau (echte `AlertEvent`/`OnsetEvent`/`AlertMessage`, kein Mock). |
| `tests/tdd/test_alert_sms_onset_zeitpunkt.py` | Bestehende Tests zu `_render_sms_onset` (#1948 S4) — hier laufen die neuen Regressionstests am wahrscheinlichsten mit. |

## Existing Patterns
- **Kopf-Kappung vor dem Zusammensetzen ist der etablierte Standard**, nicht die Ausnahme:
  `_render_sms_corridor_only` kappt `trip[:16]` und `location_label[:24]`, `_render_sms_body`
  kappt `trip[:16]` und `location_label[:24]` in fast allen Zweigen. `_render_sms_onset` und
  `_render_sms_onset_shift_only` sind die beiden Ausreißer ohne Kappung.
- **Harter Endschnitt (`body[:limit]`) bleibt als Sicherheitsnetz überall bestehen** — auch
  nach Kopf-Kappung ist er nicht überflüssig (z.B. wenn `_ascii_alert_location` durch
  GSM-7-Ersatzsequenzen wieder wächst), aber er soll im Normalfall nicht mehr greifen.
- **`_ascii_alert_location`** ist bereits der gemeinsame Ort für Piktogramm-Entfernung +
  ASCII-Faltung + Segment-Kürzung — eine Längenkappung gehört der bestehenden Konvention nach
  an die Aufrufstelle (wie bei `corridor_only`), nicht in die Funktion selbst, da sie an
  verschiedenen Stellen mit verschiedenen Limits (16/24) verwendet wird.

## Dependencies
- **Upstream:** `OnsetEvent.location_label` / `msg.trip_short` / `_location_of(...)` liefern den
  Rohtext für den Kopf — deren Länge ist nutzergesteuert (Ortsname im Trip/Ortsvergleich) und
  nicht durch das System begrenzt.
- **Downstream:** `render_sms()` → `_render_sms_body()` → `_render_sms_onset()` wird von
  `notification_service.py` für SMS, Premium-SMS und Telegram-Kurzstil konsumiert (gleicher
  Text, drei Kanäle). Kein weiterer Aufrufer im Baum.

## Existing Specs
- `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` — Ursprungs-Spec von
  `_render_sms_onset`. **Known Limitations (Zeile 272-278)** benennt das Risiko bereits
  ausdrücklich als "geerbtes Risiko" und stuft das Längenbudget zum damaligen Zeitpunkt als
  „insgesamt unkritisch" ein (nur EIN Zeit-Token, Endschnitt hätte selten getroffen).
- `docs/specs/modules/fix_2051_s1_ende_und_dauer.md` (referenziert in Issue #2078) — führte das
  **zweite** Zeit-Token (Ende-Suffix) ein, wodurch der Kopf-Endschnitt-Konflikt real wurde.
- `docs/specs/modules/fix_1935_1779_alarm_nachricht_klarheit.md` — legt die Kopf-Kappung
  `[:24]` als Konvention für den Nachbarzweig fest (Referenzmuster für diesen Fix).

## Risks & Considerations
- **Scope-Frage aus der Issue:** ob auch `_render_sms_onset_shift_only` (identisches Muster,
  nicht in der Issue erwähnt) und der `_render_sms_body`-Fallback-Kopf (Zeile 1530, geringeres
  Risiko) in dieser Scheibe mitgehen. Empfehlung: **`_render_sms_onset` UND
  `_render_sms_onset_shift_only`** in dieser Scheibe (identischer Bug, identischer Fix,
  ein Testaufwand), `_render_sms_body`-Fallback als Sammel-Eintrag (#1199) — dort ist die
  Kopfquelle (`_km_str`) strukturell kurz, kein konkreter Fehlerfall belegt.
- **Verlustärmere Richtung laut Issue:** Kopf vorher kappen (analog `[:24]`) statt am
  Token-Ende zu schneiden — bei Kopf-Kappung bleibt die Zeit-Aussage vollständig, nur der
  Ortsname wird ggf. kürzer. Das ist die im Ticket bereits vorgezeichnete Richtung, keine
  offene Designfrage mehr.
- **Messgrundlage statt Schätzung** (PO-Vorgabe im Ticket): längster real vorkommender
  `location_label`/Segmentname aus Prod-Daten (`/var/lib/gregor`, nur mit sudo) erheben, um
  ein sauberes Golden-Beispiel für den Testfall zu haben — nicht raten.
- **140 ist dreifach als Default dupliziert** (`_render_sms_onset`, `render_sms`,
  `_render_sms_body`) ohne zentrale Konstante — nicht Teil dieser Scheibe (kosmetisch,
  Sammel-Eintrag #1199 falls überhaupt).
- **KHW-Tour startet heute (2026-08-23)** — Milestone „Tour KHW 2026-08" ist bereits fällig
  (2026-08-22). Dieser Fix hat direkte Auswirkung auf die Hütten-Situation (nur Premium-SMS
  erreicht dort, siehe Produktkontext in `CLAUDE.md`).
