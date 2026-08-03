# Context: feat-1467-ag3-kurznachrichten

**Issue:** #1467 Scheibe S2, Arbeitsgang **AG3** (von sechs), Epic #1458
**Spec:** `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — freigegeben, AG3 = **AC-7, AC-8, AC-9**
**Vorgänger live:** AG1 `09754b79`, AG2 `4483f2c4` (Prod 2026-08-03 13:12 UTC)

## Request Summary

Bei einem gebündelten Ortsvergleich-Änderungsalarm für mehrere Orte fehlt in Telegram und SMS
die Zuordnung Wert→Ort; in der SMS steht die Ortsliste zusätzlich doppelt im Kopf. PO-Vorgabe:
**SMS führt Orte als Zahl** (Platz), **Telegram bekommt eine Sprechblase je Ort**. Die E-Mail
bleibt unverändert eine einzige Mail mit allen Orten.

## Der Befund, der den Zuschnitt ändert

**Die Renderer sind zwischen vier Alarm-Pfaden geteilt** (`notification_service.py:1055-1058`):
Trip-Δ (`:482`), Compare-Δ (`:544`), Compare-Radar (`:612`), Trip-Radar (`:1016`) laufen alle
durch dieselbe `_dispatch_alert_message()`. Es gibt **kein Feld, das „Ortsvergleich" markiert** —
Compare-Δ setzt `source=None` genau wie Trip-Δ (`project.py:219`). Jede Änderung an
`render_sms`/`render_telegram` trifft daher automatisch alle vier.

Daraus folgt eine natürliche Teilung:

| Teil | Weg | Renderer angefasst? | Gate |
|---|---|---|---|
| **AG3a — Telegram je Ort** | `to_multi_point_alert_message()` je Ort mit **einer** Gruppe aufrufen: `multi=False` ⇒ `location_label=None` je Event, `trip_short`/`location_label` = der eine Ortsname (`project.py:202/215/219/221`). Das ergibt die gewünschte Sprechblase **ohne** Renderer-Änderung — nur `notification_service.py` | **nein** | keins |
| **AG3b — SMS-Ortsnummern** | `_sms_token()` (`render.py:585-588`) trägt keinen Ortsbezug; Kopfzeile `render.py:612-617` zeigt den Ortsstring doppelt (`trip_short[:16]` + `location_label[:24]`, beide derselbe `collective_label`) | **ja** (`render.py`) | **Renderer-Gate #811** |

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/notification_service.py` | `send_multi_location_deviation_alert()` `:516-552` (einziger produktiver Aufrufer: `compare_alert.py:197`); `_dispatch_alert_message()` `:1026-1154`; Telegram-Zweig `:1122-1141`; Ergebnis `:1151-1154` |
| `src/output/renderers/alert/project.py` | `to_multi_point_alert_message()` `:179-221` — `multi = len(groups) > 1` `:202`, `location_label` je Event `:215`, `collective_label` `:217` in **beide** Felder `:219`/`:221` |
| `src/output/renderers/alert/render.py` | `render_telegram()` `:549-582` (liest `e.location_label` **nirgends**, Ort nur einmal im Kopf über `_km_str` `:102-103`); `render_sms()` `:604-637`, Kopf `:612-617`, 140-Grenze `:604`/`:628`/`:637`; `_sms_token()` `:585-588` |
| `src/output/renderers/alert/model.py` | `AlertEvent` `:11-27` (`location_label` `:27`), `AlertMessage` `:64-81` (`location_label` `:76`) |
| `src/services/compare_preview_service.py` | **`order_locations_by_ids()` `:232-244`** — der eine Ordnungs-Kern |
| `src/output/renderers/email/compare_html.py` | `location_render_order()` `:1324-1337` — Spaltenreihenfolge der Vergleichs-Mail |
| `src/output/channels/telegram.py` | `_reserve_send_slot()` `:254-323` — 18 Nachrichten je 60 s je Chat; `_post()` reserviert je POST `:353`; Überschreitung ⇒ `OutputError` `:314-322` |
| `.claude/hooks/renderer_mail_gate.py` | `_MAIL_PATTERNS` `:42-49` (enthält `renderers/alert/**`), `_RADAR_PATTERNS` `:51-57` |

## Existing Patterns

- **Reihenfolge ist bereits durchgängig:** `preset["location_ids"]` (`models.py:925`) →
  `order_locations_by_ids()` → Vergleichs-Mail-Spalten (`compare_html.py:1337`). Der Alarm-Pfad
  iteriert über dieselbe Liste (`compare_alert.py:233`), `entities` bleibt reihenfolgetreu
  (`compare_alert.py:196`) und kommt so als `groups` an (`notification_service.py:539-542`).
  **Die Position im `groups`-Tupel entspricht schon heute der Spaltenposition** — sie wird nur
  nirgends beschriftet. Die SMS-Ortsnummer muss also nicht neu erfunden, nur sichtbar gemacht werden.
- **Teilzustellung je Kanal ist bereits gelöst:** `telegram_fully_sent`
  (`notification_service.py:103`) plus die Bubble-Schleife in `send_trip_report()` `:359-382`
  (aus #1370): Fehler **zählen statt abbrechen**, `sent_channels.append("telegram")` nur bei
  vollständiger Zustellung, Hinweis an den Nutzer über `_send_telegram_incomplete_hint()` `:395`.
  Genau dieses Muster ist für den Fan-out zu übernehmen.
- **Einzel-Ort-Invariante:** `to_point_alert_message()` delegiert an
  `to_multi_point_alert_message()` (`project.py:333-335`) — bei einer Gruppe ist das Ergebnis
  byte-identisch. Der Fan-out je Ort erzeugt also exakt die heute schon erprobte Einzel-Form.

## Dependencies

- **Upstream:** `to_multi_point_alert_message`, `render_alert_{subject,email,telegram,sms}`,
  `TelegramOutput.send`, `order_locations_by_ids`
- **Downstream:** `compare_alert.py:197` (einziger Aufrufer von
  `send_multi_location_deviation_alert`), Alarm-Protokoll über `notif_result.delivered_channels`
  (`compare_alert.py:205-215`)

## Existing Specs

- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — AG3 = AC-7/8/9
- `docs/specs/modules/issue_1170_compare_alert_config.md` bzw. #1170 — Bündelung in EINE
  Nachricht; AG3 weicht davon **kanalspezifisch** ab (nur Telegram)

## PO-Entscheidungen (2026-08-03)

**E-AG3-1 — Obergrenze für Einzelnachrichten: KEINE.** Vorgelegt wurde eine Rückfall-Bündelung
ab 5 bzw. 8 Orten wegen des Telegram-Kontingents (18 Nachrichten je 60 s je Chat,
`telegram.py:276-277`). PO-Entscheidung: **immer eine Sprechblase je Ort, ohne Grenze.**
Das Risiko ist benannt und angenommen; es wird durch E-AG3-2 abgefedert — der Versandweg
**wartet** bei Überlast (`_reserve_send_slot()` `telegram.py:254-323`) statt zu verwerfen, und
was am Ende doch scheitert, wird dem Nutzer gemeldet statt still verschluckt.

**E-AG3-2 — Teilzustellung: restliche senden UND Hinweis.** Eine gescheiterte Nachricht darf
die folgenden nicht stoppen; der Nutzer bekommt eine kurze Notiz, dass etwas fehlte; das
Alarm-Protokoll weist „teilweise zugestellt" aus statt „zugestellt". Muster liegt vor:
`telegram_fully_sent` + Bubble-Schleife `notification_service.py:359-382` +
`_send_telegram_incomplete_hint()` `:395` (aus #1370).

## Risks & Considerations

1. **Die drei anderen Alarm-Pfade dürfen sich nicht ändern.** Trip-Δ, Trip-Radar und
   Compare-Radar laufen durch dieselben Renderer und dieselbe `_dispatch_alert_message()`.
   Der Fan-out muss über einen **neuen, defaultierten Parameter** laufen, gesetzt
   ausschließlich in `send_multi_location_deviation_alert()` (`:544-552`).
2. **Teilzustellung:** Bei drei Telegram-Nachrichten und zwei Erfolgen kennt
   `_dispatch_alert_message` heute nur „Kanal ok/nicht ok" (`:1151-1154`, `telegram_fully_sent`
   wird dort nie gesetzt). Ohne Behandlung meldet das Alarm-Protokoll (`compare_alert.py:205-215`)
   eine Zustellung, die nur teilweise stattfand.
3. **Telegram-Kontingent:** 18 Nachrichten je 60 s je Chat (`telegram.py:276-277`). Drei Orte
   kosten drei Slots statt einem. Bei mehreren Presets im selben 15-Minuten-Lauf kann das Fenster
   kippen — dann bis zu eine Fensterlänge Wartezeit je Nachricht, im Extremfall `OutputError`
   (`telegram.py:314-322`). Ein Ortsvergleich mit sehr vielen Orten braucht eine Obergrenze
   oder muss ab einer Zahl X wieder bündeln.
4. **SMS-Länge:** 140 Zeichen bleiben die harte Grenze (`render.py:604/628/637`). Die
   Zahlenkodierung soll Platz **sparen**; der Test muss die Grenze prüfen, nicht nur die Form.
5. **Was bedeutet die Zahl für den Nutzer?** Ohne Legende ist „1" nicht auflösbar. Die Spec
   legt fest: Position in der konfigurierten Ortsliste = Spaltenposition der Vergleichs-Mail,
   damit lernbar und stabil. Ändert der Nutzer die Ortsliste, verschiebt sich die Nummer —
   wie heute schon die Spalten.
6. **Renderer-Gate #811 (nur AG3b):** `render.py` matcht `_RADAR_PATTERNS` (`:51-57`).
   Verlangt wird deshalb **nicht** der Briefing-Validator, sondern der **Radar-Alarm-Validator**
   (`radar_alert_mail_validator.py`) gegen eine **echt zugestellte Radar-Alarm-Mail**, mit
   `validated_at` neuer als die mtime von `render.py`. Matrix-Test und Golden-Mail-Tests
   entfallen bei einer Alert-only-Änderung (`renderer_mail_gate.py:391-393`, `:409-410`).
7. **Testnetz:** Für `render_sms`/`render_telegram` gibt es **keine Golden-Dateien** — alle
   Prüfungen sind struktur-/substringbasiert (`test_issue_917_alert_renderer.py` u. a.). Das
   erleichtert den Umbau. Engster Regressionsanker für die Bündelung:
   `test_issue_1170_compare_alert_config.py:272` (`test_ac7_multiple_locations_bundled_into_single_mail`)
   — prüft **eine** Mail, betrifft also E-Mail und bleibt gültig.
8. **Abgrenzung:** Radar-Onset (S3) und amtliche Warnungen (S4) bleiben gebündelt. Der amtliche
   Pfad nutzt ohnehin eigene Renderer (`official_alerts.py`) und ein eigenes Dispatch
   (`notification_service.py:882-906`) — er ist von AG3 strukturell nicht erreichbar.
