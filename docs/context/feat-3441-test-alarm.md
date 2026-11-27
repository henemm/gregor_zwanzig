# Kontext: feat-3441-test-alarm (#3441, S5b)

## Request Summary

Im Menü „Test schicken ▾“ (gebaut in #3440) kommt nach „Alle eingerichteten Kanäle“ und einem Trenner der Eintrag
**„Test-Alarm — Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle“** (PO-Entscheidung A14 in #2797). Er ersetzt die
Alarm-Vorschau („Vorschau laden“: Betreff, Mail, Telegram, SMS mit Zeichenzähler). Rückmeldung:
„Test-Alarm geschickt: {Kanal} ✓ · … · {hh:mm}“ bzw. „Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.“
Deckt den Radar-Regen-Alarm für Trips mit ab (Hinweis #2800). Umgeht den Schalter `radar_alert_enabled`, prüft nur den Kanal.
Gilt für Trip und Orte (ein Code, `context`), Desktop und Mobil, DE/EN, Test nur an die konfigurierten Empfänger dieses Nutzers.

Akzeptanz (Issue): Given Alarm-Kanäle eingerichtet, When „Test-Alarm“, Then auf jedem Alarm-Kanal kommt ein Beispiel-Alarm mit
echten Werten an (E2E über den echten Kanal), und die Rückmeldung nennt jeden Kanal mit Ergebnis.

## Soll (Mockup Fassung 4)

`docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`
- Z. 421: `<hr>` nach „Alle eingerichteten Kanäle“, dann `button[role=menuitem][data-send=alarm]` mit `<b>Test-Alarm</b>` und `<small>Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle</small>`.
- Z. 812: Ziel-Kanäle = Kanäle mit Alarm-Schalter an (`ch[k].a`) UND Konto bedienbar (`acc[k].ok`); Text „Test-Alarm geschickt: E-Mail ✓ · Telegram ✓ · 20:41“, leer ⇒ Fehlerton „Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.“
- Elementliste (`elementliste.json`): Abschnitt `test-menue`, Rollen `menuepunkt`, „Test-Alarm“ (ordnung 12) und „Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle“ (ordnung 13), je Kontext trip/orte und Reiter, derzeit `luecke: true`, `i18n_key: null`.

## Related Files

**Frontend (Bestand aus #3440)**
- `frontend/src/lib/components/molecules/TestSchickenMenue.svelte` — Menü-Baustein (Dropdown/Sheet), hat Erweiterungs-Slot nach Trenner (AC-19 #3440).
- `frontend/src/lib/components/molecules/testSchickenModell.ts` — Zeilenmodell, Rückmeldungstexte (Einzel/Alle).
- `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` — Knopf `subscription-hub-send`, `onTest({kanal, berichtsart})`.
- `frontend/src/routes/trips/[id]/+page.svelte`, `frontend/src/routes/compare/[id]/+page.svelte` — `handleTest`, Meldungen `test-schicken-ok`/`-fehler`, `RUECKMELDUNG_MS`.
- `frontend/src/lib/components/shared/subscriptionExec.ts`, `frontend/src/lib/utils/sendOutcome.ts` — Versandweg, Fehlerklassifikation.
- Katalog `frontend/src/lib/i18n/messages/{de,en}/test_schicken.json`.

**Frontend (zu entfernen: Alarm-Vorschau)**
- `frontend/src/lib/components/organisms/zustellung-tab/BeispielAlarm.svelte` (Abschnitt `beispiel-alarm`, letzter Abschnitt in `ZustellungTab.svelte:116`, Hub UND Anlegen).
- `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte` (220 Z.) + `alertPreviewHelpers.ts` (Payload-Bau aus Regeln mit Schwelle×1.2).
- `frontend/src/lib/components/shared/AlarmeTab.svelte:607-613` (Abschnitt `sample`), noch eingebunden in den Anlege-Editoren `TripNewEditor.svelte` / `CompareNewEditor.svelte` (createMode).
- `frontend/src/lib/api.ts:309-316` — `alert-preview`-Aufrufe, `ZEITLIMIT_ALARM_VORSCHAU_MS`.
- Bestandstests: `alertPreviewEmpty.test.ts`, `alertPreviewHelpers.test.ts`, `issue_850_alert_metrics_stale.test.ts`, Wächter `keine_hartkodierten_nutzertexte.test.ts:500` u. a.

**Backend Vorschau (Bauweise „echte Werte“)**
- `api/routers/validator.py:310-395` — `POST /api/trips/{id}/alert-preview`, `POST /api/briefings/{id}/alert-preview?kind=` (user-scoped).
- `src/services/validator_render_service.py:162` `render_alert_preview` — Trip: synthetische `changes` + echte Segmente des Bezugstags, mit Nutzer-ID echte Stundenreihe (Anker + frisch, #1737, `alert_preview_hours.trip_preview_series`), Ampel des Trips.
- `src/services/compare_alert_preview_service.py` — Vergleich: geteilter Baustein `alert_channel_texts.build_deviation_message` / `render_channel_texts` / `plan_telegram`, echte Stundenpunkte je Ort (`compare_preview_point`), Kurzstil Telegram; bewusst NICHT über `NotificationService.send_*` (SMS-Kontingent-Reservierung).
- Go: `internal/router/router.go:359,395` (Bremse `bremsen.Vorschau`), `internal/handler/briefing_preview.go`, `proxy.go:341`.

**Backend Versand**
- `src/services/alert_channels.py` — `effective_alert_channels(subscription, settings, user_id)`: die EINE Alarm-Kanal-Auflösung Trip/Vergleich (Override `alert_channels`, sonst geerbte Briefing-Kanäle, Tarif-Gates). Readiness (`can_send_*`) liegt in `notification_service`.
- `src/services/notification_service.py` — `send_deviation_alert` (Trip, 1177), `send_multi_location_deviation_alert` (Vergleich, 1269), `_dispatch_alert_message` (2022, liefert `NotificationResult` mit `sent_channels`, `failed_channels`, `blocked_channels`), `_sms_gate_reserve` (784, SMS-Tageskontingent).
- `api/routers/briefings_send.py` — Muster Handversand: Kontingent `manueller_abruf`, Fehler über `send_outcomes`, `sent_channels` in der Antwort; Go `internal/handler/briefing_send.go` + `bremsen.Versand`.
- `src/services/trip_alert.py`, `compare_alert.py`, `radar_alert_service.py`, `compare_radar_alert.py` — echte Alarmwege (Cooldown, stille Stunden, Tageslimit, Alarm-Zustand, Alarm-Protokoll); der Test darf deren Zustand nicht verändern.

## Existing Patterns

- Kanalwahl/Rückmeldung „Alle“ aus #3440 (`sent_channels` → „✓“, gesperrt → „übersprungen ({Grund})“).
- Vorschau-Renderer = Versand-Renderer (ADR-0011, #2986 geteilter Baustein) — Test-Alarm kann Nachricht wie die Vorschau bauen und über `_dispatch_alert_message` zustellen.
- Trip-Test-Briefing setzt `[TEST]`-Präfix (`TripReportSchedulerService.send_test_report_outcome`, `_apply_prefixes`).
- Kanalparität ADR-0095, Trip/Orte-Code-Teilung ADR-0097, DE/EN ADR-0104, Menüstruktur ADR-0109 Punkt 6, Bausteine ADR-0112, Knopf-Stil ADR-0118, Testmail nur an bestätigte Adresse ADR-0092, Kontingent ADR-0117.

## Dependencies / Dependents

- Abhängig von #3440 (Menü, geschlossen/ausgeliefert).
- Nachfolger: #3442 (Kebab-Rückfragen), #3443 (Entwurf aktivieren), Abnahme #3009 (Elementlisten-Abgleich `test-menue` muss die zwei Zeilen dann ohne Lücke finden).
- Mail-Validatoren der Alarmpfade: `radar_alert_mail_validator.py`, `official_alert_mail_validator.py` (`docs/reference/mail_validators.md`) — prüfen, ob ein Abweichungs-Alarm-Validator existiert bzw. welcher den Test-Alarm abdeckt.

## Existing Specs

- `docs/specs/modules/feat_3440_test_schicken_menue.md` (AC-19: Slot für Test-Alarm).
- `docs/specs/modules/shared_preview_tab.md` (Alarm-Vorschau, wird teilweise obsolet).
- `docs/specs/modules/rework_2279_s1_alert_kanal_aufloesung.md` (Kanal-Auflösung).
- `docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md` (BeispielAlarm im Zustellungs-Reiter, AC-7).

## Risks / offene Designfragen (für /20-analyse)

1. **Welcher Alarm-Typ ist das Beispiel?** Abweichungs-Alarm aus den aktiven Alarm-Metriken mit echten Segmenten/Orten und echter Stundenreihe (wie Vorschau) — Radar/amtlich nicht separat? „Deckt Radar mit ab“ = gleiche Kanalmenge.
2. **Ziel-Kanäle:** `effective_alert_channels` ∩ bedienbar (`can_send_*`), ohne `radar_alert_enabled`, ohne stille Stunden, Cooldown, Tageslimit; kein Schreiben von Alarm-Zustand/Anker; Alarm-Protokoll?
3. **Kennzeichnung:** `[TEST]`-Präfix im Betreff/Text wie beim Test-Briefing, damit kein echter Alarm vorgetäuscht wird (Nutzer unterwegs!).
4. **Kosten/Missbrauch:** Mengenbremse (`bremsen.Versand`), Kontingent `manueller_abruf`, SMS-Tageskontingent (`_sms_gate_reserve`) — Test-SMS zählt mit?
5. **Mandantentrennung:** `user_id` aus Auth, Zwei-Nutzer-Test, 404 bei fremder ID.
6. **Entfernen der Vorschau:** Frontend-Karte + Abschnitt; Backend-Endpunkte `alert-preview` werden noch von Validatoren/Tests genutzt (`api/routers/validator.py` = Validator-Router) — Backend bleibt vermutlich, nur UI raus.
7. **Rückmeldung/Fehler:** gleiche Mechanik wie #3440 (5 s, `test-schicken-ok`/`-fehler`), leere Kanalmenge ⇒ Fehlerton-Text.
8. **Trip ohne heutige Etappe / Vergleich ohne Orte / keine aktiven Metriken:** was ist dann das Beispiel?
9. **E2E:** Staging echter Versand E-Mail (Stalwart) + Telegram; SMS/Premium nur über Endpunkt-Test mit Transport-Fake an der Grenze (Kosten).

## Analysis

**Type:** Feature (Teil S5 #2797, Epic #2791; vor Abnahme #3009).

**Entscheidung Schnitt (Tech Lead, Variante B):** Dieses Issue baut den Test-Alarm samt Backend. Das Entfernen der
Alarm-Vorschau-UI (AlertPreviewCard, BeispielAlarm im Zustellungs-Reiter, AlarmeTab-Abschnitt `sample`, `api.ts`
alarmVorschau, ca. −400 LoC, ~8 Tests löschen, ~20 pflegen) läuft als eigenes Folge-Issue direkt danach, vor #3009
(in den Auftrag eingereiht). Grund: Review-Fläche und Scope-Limit; die Vorschau bleibt bis zum grünen Staging-E2E Rückfall.
Backend-Endpunkte `alert-preview` bleiben (Testwerkzeug, Spec `alarm_testeinspeisung.md`).

### Affected Files

| Datei | Change | Zweck |
|---|---|---|
| `src/services/alert_test_service.py` | CREATE | Beispiel-Changes serverseitig (Trip: aktive `alert_rules`; Vergleich: aktive Alarm-Metriken mit Standardschwelle; Regel Schwelle×1.2/×0.8 wie `alertPreviewHelpers.ts`), echte Segmente/Stundenreihe (`alert_preview_hours`), Kanalmenge, Versand |
| `src/services/notification_service.py` | MODIFY | `test`-Schalter in `send_deviation_alert` / `send_multi_location_deviation_alert` / `_dispatch_alert_message`: [TEST]-Präfix in Betreff, Telegram, SMS/Premium-SMS (SMS-Limit vorher kürzen) |
| `src/services/alert_channel_texts.py` | MODIFY (ggf.) | Präfix-Mechanik analog `sms_suffix` |
| `api/routers/briefings_test_alert.py` (oder in `briefings_send.py`) | CREATE/MODIFY | `POST /api/briefings/{id}/test-alert?kind=route|vergleich`, `manueller_abruf`, Fehler über `send_outcomes`, Antwort `sent_channels`, `skipped_channels` |
| `src/services/send_outcomes.py` | MODIFY | Code `keine_alarm_kanaele` (+ ggf. `test_alarm_ohne_etappe`), DE/EN |
| `internal/handler/briefing_test_alert.go` + `internal/router/router.go` | CREATE/MODIFY | Handler nach Muster `BriefingSendHandler`, `bremsen.Versand`, user_id aus Auth |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | `onErweiterung` durchreichen |
| `frontend/src/lib/components/molecules/testSchickenModell.ts` | MODIFY | Erweiterung `test-alarm`, Rückmeldungstexte |
| `frontend/src/routes/trips/[id]/+page.svelte`, `routes/compare/[id]/+page.svelte` | MODIFY | Handler ruft Endpunkt, Rückmeldung 5 s über `test-schicken-ok`/`-fehler` |
| `frontend/src/lib/components/shared/subscriptionExec.ts` / `lib/api.ts` | MODIFY | Aufruf test-alert |
| Katalog `test_schicken.json` DE/EN, Glossar | MODIFY | „Test-Alarm“, Untertitel, Rückmeldungen |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | Zeilen ordnung 12/13 `test-menue` mit `i18n_key`, `luecke:false`, `text_en` |

### Scope / Risk

Produktivcode ca. +370 (Backend ~265, Frontend ~105), Tests ca. 450–600 ⇒ Override `loc_limit_override 420`,
`test_loc_limit_override 650` (vertikaler Schnitt, Backend ohne Menüpunkt nicht abnehmbar). Risiko mittel–hoch:
echter Versand inkl. SMS-Kosten; Test darf keinen echten Alarm vortäuschen und keinen Alarm-Zustand verändern.

### Technical Approach

- Versand über bestehende `NotificationService.send_deviation_alert` / `send_multi_location_deviation_alert` (zustandslos;
  Zustand/Protokoll/Sperrzeit/Tageslimit schreiben nur `trip_alert.py`/`compare_alert.py`) — Renderer = Versand (ADR-0011).
- Kanäle = `effective_alert_channels` (inkl. Tarif-Gates) ∩ Zustellbarkeit (`can_send_*` im Dispatch). Kein Check von
  `radar_alert_enabled`, stillen Stunden, Sperrzeit, Tageslimit. Leere Menge ⇒ Fehlercode, Frontend-Text „Kein Alarm-Kanal…“.
- [TEST] sichtbar in Betreff, Telegram und SMS (Nutzer unterwegs darf Test nicht für echte Warnung halten).
- SMS-/Premium-SMS-Tageskontingent zählt unverändert (echte Kosten), `bremsen.Versand` + `manueller_abruf` je Klick.
- Randfälle: Trip ohne heutige Etappe ⇒ Bezugstag (`preview_reference_date`); ohne Segmente ⇒ 422; keine aktiven
  Alarm-Metriken ⇒ Beispiel-Metrik (Fallback); ohne Stundenreihe ⇒ Nachricht ohne Stundenzeilen; Vergleich ohne Orte ⇒ 422.
- Mandantentrennung: user_id aus Auth, Zwei-Nutzer-Test, 404 bei fremder ID.

### Open Questions

Keine Produktfrage offen (A14 entschieden). Abweichungs-Alarm-Mail-Validator fehlt (nur `briefing_mail_validator.py`
kennt `deviation-alert`): E2E prüft Eingang + [TEST]-Betreff + X-GZ-Mail-Type im Stalwart-Postfach; eigener Validator
nicht in diesem Umfang.
