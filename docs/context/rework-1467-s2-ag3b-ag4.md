# Context: rework-1467-s2-ag3b-ag4

**Issue:** #1467 Scheibe S2 — Arbeitsgänge **AG3b** (SMS-Ortsnummern) + **AG4**
(Telegram/SMS für Ortsvergleich-Änderungsalarme scharf schalten)
**Spec (bereits PO-freigegeben 2026-08-03):** `docs/specs/modules/rework_1467_s2_aenderungsalarm.md`
**ACs in dieser Scheibe:** AC-7 (AG3b) · AC-10, AC-11, AC-12, AC-13 (AG4)
**Track:** Standard (Intake-Score 3 — Umfang Medium / Wirkungsbereich High / Unsicherheit Low)
**PO-Zuschnittsentscheidung 2026-08-04:** AG3b wird in AG4 hineingenommen, statt AG4
allein auszuliefern.

## Warum die beiden zusammen laufen

AG4 ersetzt die fest verdrahtete Kanalliste `channels={"email"}`
(`src/services/compare_alert.py:272`) durch den Resolver aus AG1 — ab dann gehen
Ortsvergleich-Änderungsalarme erstmals auch per Telegram und SMS raus.

**Telegram ist vorbereitet (AG3a, live `476094b9`), SMS nicht.** Ohne AG3b würde AG4 eine
nachweislich unbrauchbare SMS scharf schalten:

- `_sms_token()` (`src/output/renderers/alert/render.py:585-588`) nutzt das per-Event
  gesetzte `location_label` **nicht** — die Messwert-Token tragen keine Ortszuordnung.
- `to_multi_point_alert_message()` (`src/output/renderers/alert/project.py:217-220`)
  schreibt `collective_label` in **beide** Felder `trip_short` UND `location_label`;
  `render_sms()` (`:604-616`) baut daraus `head = f"{trip} {location_label}: "` ⇒ die
  Ortsliste steht **zweimal** im Kopf.

Ergebnis heute bei drei Orten (Graz, Wien, Linz), gemessen an der Renderer-Logik:

```
Graz, Wien, Linz Graz, Wien, Li: +B72@14 -T8@15 +R12@16
```

32 von 140 Zeichen für eine doppelte Ortsliste, und kein Token ist einem Ort zuzuordnen.
Für ein Warnwerkzeug der schlechteste Fall — die Meldung kommt an, sagt aber nicht, wo.

AG3b allein hätte umgekehrt **keinen** sichtbaren Nutzen, weil bis AG4 gar keine SMS
rausgeht. Erst zusammen ergeben sie einen auslieferbaren Zustand.

## Gemessener Ist-Stand (HEAD `6b6ad80d`)

| Baustein | Zustand |
|---|---|
| `compare_alert.py:272` | `channels={"email"}` — **das Ziel von AG4** |
| `services/compare_alert_channels.py:20` `effective_compare_channels(preset, settings, user_id)` | ✅ da (AG1). E-Mail immer; Telegram bei `send_telegram` + `settings.can_send_telegram()`; SMS bei `send_sms` + `can_send_sms()` + `sms_allowed(user_id)` (Tarif-Gate) |
| Aufrufer des Resolvers heute | `compare_official_alert.py:257`, `scheduler_dispatch_service.py:288` — `compare_alert.py` wäre der **dritte** |
| Telegram je Ort | ✅ da (AG3a): `notification_service.py:544-552` reicht `telegram_groups` durch, `_dispatch_alert_message` `:1147` fächert auf |
| SMS-Ortsnummern | ❌ fehlt — **AG3b** |
| SMS-Renderaufruf | genau **eine** Stelle: `notification_service.py:1074` `render_alert_sms(alert_msg)` |

## Related Files

| Datei | Änderung | Zweck |
|---|---|---|
| `src/output/renderers/alert/render.py` | MODIFY (AG3b) | `_sms_token()` + `render_sms()` bekommen die optionale Orts-Positions-Zuordnung; doppelter Kopf entfällt im Mehr-Orte-Fall |
| `src/services/notification_service.py` | MODIFY (AG3b) | Positions-Zuordnung von `send_multi_location_deviation_alert()` bis `:1074` durchreichen |
| `src/services/compare_alert.py` | MODIFY (AG4) | `channels={"email"}` → Resolver; Positions-Zuordnung aus `preset["location_ids"]` bauen |
| `tests/tdd/test_issue_1169_compare_alert_consumer.py` | MODIFY (AG4) | **drei** Stellen, die E-Mail-only festschreiben: Modul-Docstring `:13-14`, Test-Docstring `:591-594`, Assertion `:645` |
| `tests/tdd/test_compare_alert_channel_delivery.py` | CREATE | Wirkungs-ACs AC-10..13 |

## Dependencies

- **Upstream:** `effective_compare_channels()` (AG1) · `to_multi_point_alert_message()` ·
  `sms_allowed()`/`user_tier` · `_dispatch_alert_message()`
- **Downstream:** alle vier Alarmarten laufen durch dasselbe `_dispatch_alert_message()`
  — die Positions-Zuordnung MUSS wie bei AG3a ein defaultierter Parameter sein, damit
  Trip-Δ, Trip-Radar und Compare-Radar **byte-identisch** bleiben
- **Kein Go, kein Frontend.** Die Bedienung existiert bereits: geteilter
  `AlertChannelPicker` (`AlarmeTab.svelte:295`), schreibt im `context === 'vergleich'`-Zweig
  auf `send_telegram`/`send_sms` (`:186-187`). S2 repariert einen vorhandenen,
  wirkungslosen Schalter — kein neuer Schalter

## Risks & Considerations

1. **🔴 Nutzerwirksamer Scharfschalter.** Ab AG4 gehen echte Telegram-/SMS-Nachrichten
   für Ortsvergleich-Alarme raus. Jeder Test in dieser Scheibe muss mit gesetzten Senken
   und ausdrücklich geleerten Telegram-/SMS-Feldern laufen (#1477).
2. **🔴 Renderer-Commit-Gate #811.** `src/output/renderers/alert/*.py` steht auf der
   Sperrliste: der Commit blockt, bis im aktiven Workflow **beide** frisch vorliegen —
   `tests/tdd/test_issue_811_mode_matrix.py` grün UND ein erfolgreicher
   `briefing_mail_validator.py`-Lauf gegen eine **echt zugestellte** Staging-Mail.
   Das ist der Preis des gewählten Zuschnitts, beim Abschluss einplanen.
3. **Der Bestandstest ist Live-Schicht** — `test_issue_1169_compare_alert_consumer.py`
   trägt `pytestmark = pytest.mark.email` (`:70`), nutzt echtes IMAP gegen
   `gregor-test@henemm.com` und einen echten lokalen Telegram-HTTP-Server. Seine drei
   E-Mail-only-Stellen werden umgeschrieben, nicht gelöscht: sie bewachen danach das
   **neue** Verhalten.
4. **Regression der drei anderen Alarmwege.** AG3a hat dafür bereits AC-26; AG3b braucht
   die gleiche Zusicherung für SMS — ohne Positions-Zuordnung muss der Text
   unverändert bleiben.
5. **Tarif-Gate bei SMS** (`sms_allowed`) ist Teil des Resolvers, nicht des Renderers —
   AC-12 prüft, dass ein Free-Tarif-Konto trotz `send_sms: true` keine SMS bekommt.
6. **Längenbudget SMS.** AC-7 verlangt ≤140 Zeichen bei zwei Orten mit je einer
   Änderung. Der Wegfall der doppelten Ortsliste schafft Platz; die Ziffern kosten
   wenig.

## Nicht in dieser Scheibe

- AG5 (Anker + Gedächtnis als geteilter Baustein) und AG6 (pausiert/archiviert schweigt)
- Nowcast- und amtlicher Pfad (S3/S4) — deren Telegram-/SMS-Verhalten bleibt unverändert
- Jede Änderung an der E-Mail: sie bleibt EINE gebündelte Mail (AC-9, #1170)
