---
entity_id: security_haertung_2026_11_abruf_kontingent_interaktiv
type: module
created: 2026-11-13
updated: 2026-11-13
status: approved
version: "1.1"
tags: [security, forecast-budget, open-meteo, rate-limit, python-core, go-api, issue-2961]
---

# Sicherheits-Härtung: Abruf-Kontingent für interaktive Auslöser (Review 2026-11, Welle 2)

## Approval

- [x] Approved — Auftrag des PO (Issue #2961): alle Befunde des Reviews 2026-11 ohne Rückfrage
  beheben; dieser Auftrag ist die Freigabe. Grundsatzentscheidungen in ADR-0117.

## Purpose

Interaktive Wege (Sofortvergleich, Etappenwetter, Vorschauen) buchten das gemeinsame
Open-Meteo-Tageskontingent mit der nie gedrosselten Priorität der Zeitplan-Briefings. Ein einzelnes
Konto konnte so das Kontingent aller aufbrauchen und Alarm-Prüfungen für alle sperren. Diese Spec
gibt interaktiven Abrufen ein eigenes, faires Kontingent je Nutzer, hält eine Reserve für Briefings
und Alarme frei und begrenzt die Eingaben.

## Source

- **Python-Core:** `src/services/forecast_budget.py` (Priorität `user_interactive`,
  `interaktiver_abruf()`, Snapshot-Felder), `src/services/segment_weather.py` (wirksame Priorität),
  `src/services/comparison_engine.py` (Hinweis je Ort, `error_code`),
  `src/services/comparison_parallel.py` und `src/services/stage_weather.py` (Kontext in die
  Arbeiter, Etappen-Status), `src/app/user.py` (`LocationResult.error_code`), `api/fehler.py`
  (`kontingent_erschoepft`), `api/routers/compare.py`, `api/routers/internal.py`,
  `api/routers/preview.py`, `api/routers/validator.py`, Katalog `src/i18n/messages/{de,en}/`.
- **Go-API:** `internal/handler/forecast.go` (Priorität), `internal/handler/vergleich_orte_grenze.go`
  (neu), `internal/handler/proxy.go` (`Retry-After` beim Etappenwetter),
  `internal/handler/admin_users.go`, `internal/scheduler/forecast_budget_health.go`,
  `internal/router/router.go` (nur `/api/compare`), Katalog `internal/i18n/messages/{de,en}/fach.json`.
- **Nachtrag (Fix-Runde):** `src/services/manuelles_kontingent.py` (neu, Obergrenzen),
  `api/routers/briefings_send.py`, `src/services/trip_command_processor.py` (nur Buchungs-
  priorität und Ablehnungsantwort), `src/services/trip_report_scheduler.py` und
  `scheduler_dispatch_service.py` (Abbruch vor Zustellung), `src/services/send_outcomes.py`,
  `src/services/radar_service.py` (Zurechnung), `internal/handler/nutzer_mengenbremse.go`
  (Vorhersage-Bremse).
- **Frontend:** `frontend/src/lib/components/trip-detail/StageList.svelte` (Hinweis),
  `frontend/src/lib/types.ts`.
- **Mandantentrennung:** jede Buchung trägt die `user_id` aus dem Auth-Kontext; Tests mit zwei
  Nutzern (A verbraucht, B bleibt arbeitsfähig). Trip/Ortsvergleich-Teilung: keine neue
  Komponente mit Pendant. Kanäle: Briefing- und Alarminhalte unverändert.

## Estimated Scope

- **LoC:** ~450 Produktcode/Doku, ~650 Tests
- **Files:** 25
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ForecastBudgetGate` | Python-Klasse | Tagestopf, fairer Anteil (ADR-0075) |
| `/api/_internal/forecast-budget/reserve` | Core-Endpunkt | Go dockt an (ADR-0076) |
| `NutzerBremsen` | Go | Geschwindigkeit je Nutzer (ADR-0114) |
| `userQuota` | Go | Orte-Quote je Tarif (Issue #2482) |

## Implementation Details

```
Prioritaeten: user_briefing (nur Zeitplan, nie gedrosselt) | alert_check (95 %)
              | polling (80 %) | user_interactive (neu) | user_manual (neu, Nachtrag)

reserve("user_interactive", n):
  global:   calls + n <= 0.70 * 9000 = 6300            sonst abgelehnt
  je Nutzer: interaktiv_heute + n <= 1500 (fest, Nachtrag)  sonst abgelehnt
  gebucht:  calls, interactive_calls (global); calls, interactive (Nutzer)
  Ablehnung bucht nichts und wird im interaktiven Kontext vermerkt.
reserve("user_manual", n):
  global:   calls + n <= 0.90 * 9000 = 8100;  je Nutzer: manuell_heute + n <= 1500
  im Kontext manueller_abruf(uid, schaetzung): erster Abruf bucht die ganze
  Schaetzung; passt sie nicht -> Versand abgelehnt, kein weiterer Abruf, keine
  Zustellung; Rest nach dem Versand erstattet.
Fairness alert_check/polling (Stufe 1): Nutzerverbrauch OHNE interaktiven und
manuellen Anteil.
Anreicherung (Radar/Gewitter) im markierten Kontext: Nutzer + Prioritaet des
Kontexts; Ablehnung = "ohne Anreicherung" (throttled).

Route -> with interaktiver_abruf(): ...  (ContextVar; copy_context in Arbeiter)
Segment-Weg: priority = "user_interactive" im Kontext, sonst unveraendert.
```

**Zahlen (gemessen, `test_messung_einheiten_je_vergleich_und_etappenwetter`):**

| Abruf | Einheiten ohne Cache-Treffer |
|---|---|
| Vergleich mit 10 Orten | 10 (eine je Ort; Cache-Treffer 0) |
| Etappenwetter Referenz-Tour GR221 im Repo (4 Etappen, 16 Wegpunkte) | 16 (eine je Abschnitt; je Wegpunkt ein Abschnitt) |
| Go `/api/forecast` | 2 (Konstante im Core, ADR-0076) |
| Handversand/Befehl Trip (`user_manual`) | Abschnitte der Etappe + 1 (Nacht) + bis zu 3 Folgeetappen (Trend); typisch 4 + 1 + 12 = 17 ⇒ 1500 / 17 ≈ 88 Versände bzw. Antworten je Tag. Vorab gebuchte Obergrenze: vier größte Etappen + 1 + (größte Etappe + 1) Anreicherung = 22 bei vier Abschnitten je Etappe, mindestens 7 |
| Handversand/Befehl Ortsvergleich (`user_manual`) | eine Einheit je Ort; Obergrenze 2 je Ort (mit Anreicherung), mindestens 7 |

**Sockel:** 30 Vergleiche × 10 + 50 Etappenwetter × 16 = 1100 Einheiten für die Referenz-Tour;
1500 deckt 50 Etappenwetter-Abrufe einer Tour mit bis zu 24 Abschnitten (z. B. 6 Etappen à 4) plus
30 Vergleiche ab, jeweils ohne einen einzigen Cache-Treffer (Cache 10 Minuten).

**Globale Reserve:** 70 % = 6300 Einheiten; bis zur Polling-Schwelle (80 %) bleiben 900, bis zur
Alarm-Schwelle (95 %) 2250 Einheiten, die interaktiv nie verbraucht werden.

## Expected Behavior

- **Input:** interaktiver Aufruf eines angemeldeten Nutzers.
- **Output:** Daten wie bisher; bei erschöpftem Kontingent Cache-Daten plus Hinweis je Ort bzw.
  Etappe, 429 mit `Retry-After`, wenn nichts geliefert werden kann; 422 bei ungültigen Eingaben.
- **Side effects:** Buchung im globalen und im eigenen Zähler (`interactive_calls`/`interactive`),
  einmal je Tag eine Warnzeile, wenn ein Nutzer mehr als die Hälfte stellt.

## Acceptance Criteria

- **AC-1:** Given Nutzer A hat sein interaktives Tageskontingent aufgebraucht und Nutzer B nicht / When beide interaktiv buchen und A zusätzlich Zeitplan-Briefing, Alarm-Prüfung und Polling bucht / Then wird nur As interaktive Buchung abgelehnt, alle übrigen Buchungen gelingen.
  - Test: `test_ac1_interaktiv_erschoepft_trifft_nur_a_und_nie_briefing_alarm`
- **AC-2:** Given ein Nutzer hat 1499 interaktive Einheiten gebucht, auch als einziger aktiver Nutzer des Tages / When er zweimal bucht / Then gelingt die erste Buchung und die zweite nicht (feste Grenze 1500, Nachtrag); ohne Kennung wird nie interaktiv gebucht; `reserve()` mit `units <= 0` wirft `ValueError` und bucht nichts.
  - Test: `test_ac2_sockel_gilt_wenn_fairer_anteil_kleiner_ist`, `test_ac2_erster_nutzer_des_tages_bekommt_nicht_den_ganzen_topf`, `test_ac2_ohne_kennung_nie_interaktiv`, `test_kleinteil_reserve_lehnt_nicht_positive_einheiten_ab`
- **AC-3:** Given der Tageszähler steht eine Einheit unter 70 % / When interaktiv zwei bzw. eine Einheit gebucht werden und danach Briefing und Alarm-Prüfung buchen / Then werden zwei Einheiten abgelehnt, eine angenommen, danach nichts Interaktives mehr, Briefing und Alarm gelingen; ein Nutzer, der nur interaktiv über seinem fairen Anteil liegt, behält bei 81 % sein Polling.
  - Test: `test_ac3_interaktiv_nie_ueber_die_globale_grenze`, `test_ac3_interaktiver_verbrauch_zaehlt_nicht_gegen_alarm_fairness`
- **AC-4:** Given A ist erschöpft, ein Ort liegt im Cache, ein anderer nicht / When A den Sofortvergleich über die API aufruft / Then liefert der gecachte Ort Daten, der andere `error_code` `abruf_kontingent_erschoepft` mit übersetztem Text, ohne Anbieter-Abruf; nur der ungecachte Ort ergibt 429 mit `Retry-After`; B bekommt Daten; der Versandweg für A bleibt ungedrosselt; ein normaler Vergleich bucht interaktiv.
  - Test: `test_ac4_vergleich_a_erschoepft_cache_bleibt_b_arbeitet`, `test_ac4_vergleich_bucht_als_interaktiv`, `test_ac4_zeitplan_und_handversand_pfad_bleibt_ungedrosselt`
- **AC-5:** Given A ist erschöpft / When A das Etappenwetter abruft / Then antwortet die API mit 429 ohne Anbieter-Abruf, B bekommt Daten; kommt eine Etappe aus dem Cache und eine nicht, liefert die API 200 mit der gecachten Etappe, `null` für die andere, `gedrosselt` und übersetztem `hinweis`.
  - Test: `test_ac5_etappenwetter_a_erschoepft_429_b_arbeitet`, `test_ac5_etappenwetter_teilweise_aus_cache_mit_hinweis`
- **AC-6:** Given ein Sofortvergleich mit `forecast_hours` außerhalb 1–96, einer Stunde außerhalb 0–23 oder einem ungültigen Datum / When er aufgerufen wird / Then antwortet die API mit 422 `vergleich_parameter_ungueltig` und Katalogtext, ohne Anbieter-Abruf; mehr Orte als die Orte-Quote des Tarifs ergeben in Go 422 `limit_exceeded` (Admins frei).
  - Test: `test_ac6_eingabegrenzen_422_mit_katalogtext`, `test_ac6_obergrenze_96_stunden_bleibt_erlaubt`, `TestVergleichOrteGrenze_*`
- **AC-7:** Given A hat noch drei Einheiten / When A denselben Ort fünfmal um 0,0001 Grad verschoben vergleicht / Then entstehen genau drei Anbieter-Abrufe, die übrigen zwei Orte tragen den Kontingent-Hinweis, und B kann weiter buchen.
  - Test: `test_ac7_verschieben_um_meter_kostet_eigenes_kontingent`
- **AC-8:** Given ein Nutzer stellt mehr als die Hälfte des interaktiven Tagesverbrauchs / When er erneut interaktiv bucht / Then steht genau eine Warnzeile mit maskierter Kennung im Log; Snapshot, Betriebsstatus und Admin-Liste weisen den interaktiven Verbrauch getrennt aus; der interne Reserve-Endpunkt kennt `user_interactive`.
  - Test: `test_ac8_*`, `TestForecastBudgetStatus_Interaktiv*`, `TestUserForecastUsage_InteraktiverAnteilJeNutzer`, `TestForecastHandler_ReserveTraegtEchteUserIDUndInteraktivePriority`
- **AC-9:** Given A ist erschöpft / When A die SMS-Vorschau abruft / Then antwortet die API mit 429 statt einer still unvollständigen Vorschau.
  - Test: `test_ac9_sms_vorschau_erschoepft_429`, `test_ac9_alarm_vorschau_erschoepft_429`, `test_f4_vergleich_alarm_vorschau_bucht_interaktiv`
- **AC-10:** Given Nutzer A hat sein manuelles Tageskontingent (1500) aufgebraucht, Nutzer B nicht / When A und B einen Handversand oder Befehl buchen und A zusätzlich Zeitplan-Briefing, Alarm-Prüfung, Polling und interaktiv bucht / Then wird nur As manuelle Buchung abgelehnt.
  - Test: `test_manuell_erschoepft_trifft_nur_a_briefing_und_alarm_bleiben`, `test_zeitplan_versand_von_a_bleibt_ungedrosselt`
- **AC-11:** Given der Tageszähler steht eine Einheit unter 90 % / When manuell zwei bzw. eine Einheit gebucht werden / Then werden zwei abgelehnt, eine angenommen, der Zähler überschreitet 90 % nie, Alarm-Prüfung und Briefing gelingen weiter.
  - Test: `test_manuell_global_nie_ueber_90_prozent_alarme_bleiben_offen`
- **AC-12:** Given ein Versand mit Obergrenze 10 Einheiten / When er zwei Abrufe macht / Then sind am Ende genau zwei Einheiten gebucht (Vorab-Buchung, Erstattung des Rests); Given der Rest des Nutzers ist kleiner als die Obergrenze / When der Versand den ersten Abruf versucht / Then wird nichts gebucht und jeder weitere Abruf abgelehnt.
  - Test: `test_manuell_vorab_buchung_und_erstattung`, `test_manuell_zu_grosser_versand_wird_vor_dem_ersten_abruf_abgelehnt`
- **AC-13:** Given A ist erschöpft bzw. sein Rest reicht für den Ortsvergleich nicht / When A per Web von Hand einen Trip oder Ortsvergleich versendet / Then antwortet die API mit 429 `kontingent_erschoepft`, Katalogtext und `Retry-After`, ohne Anbieter-Abruf und ohne jede Zustellung (auch kein Ausfall-Hinweis); B versendet normal und bucht `user_manual`, der ungenutzte Rest wird erstattet.
  - Test: `test_handversand_trip_a_erschoepft_429_b_versendet`, `test_handversand_vergleich_zu_gross_vor_dem_ersten_abruf_abgelehnt`
- **AC-14:** Given A ist erschöpft / When A einen Antwort-Befehl über Telegram, E-Mail, SMS oder Premium-SMS schickt / Then antwortet der Dienst kurz „Tageskontingent für Abrufe erschöpft, automatische Briefings und Alarme laufen weiter" (Kurzform-Kanäle englisch, höchstens 160 Zeichen) ohne Anbieter-Abruf; B bekommt die normale Antwort und bucht `user_manual`.
  - Test: `test_befehl_a_erschoepft_kurze_antwort_b_arbeitet`
- **AC-15:** Given ein Radar-/Gewitter-Abruf / When er außerhalb bzw. innerhalb einer markierten Anfrage läuft / Then bucht er außerhalb nutzerfrei, innerhalb beim auslösenden Nutzer; bei erschöpftem Kontingent entfällt nur die Anreicherung (`throttled`), ohne die Anfrage ungültig zu machen.
  - Test: `test_anreicherung_wird_im_kontext_dem_nutzer_zugerechnet`
- **AC-16:** Given ein Abschnitt einer Etappe liegt im Cache, der andere wird abgelehnt / When das Etappenwetter abgerufen wird / Then wird die Etappe nicht aus dem einen Abschnitt bewertet (429, da keine Etappe lieferbar). `GET /api/forecast` ist je Nutzer auf 60 je Minute gebremst; die Orte-Grenze des Vergleichs ist im echten Router verdrahtet; der Betriebsstatus weist `user_manual` getrennt aus.
  - Test: `test_f5_etappe_mit_gedrosseltem_abschnitt_wird_nicht_aus_teildaten_bewertet`, `TestAbrufKontingent_*`, `TestForecastBudgetStatus_ManuellGetrenntAusgewiesen`

## Known Limitations

- Eine Tour, deren Obergrenze über 1500 liegt (Etappen mit Hunderten Wegpunkten), lässt sich
  nicht mehr von Hand versenden; der Zeitplan-Versand bleibt davon unberührt.
- Die Obergrenze ist eine Schätzung: übersteigt ein Versand sie doch, wird nachgebucht; scheitert
  das, bricht der Versand vor der Zustellung ab (kein Teil-Briefing), die bis dahin gebuchten
  Einheiten bleiben gebucht.
- Mehrere abgestimmte Konten können den interaktiven (ab 5 Konten) bzw. manuellen Topf (ab 6)
  füllen; Briefings und Alarme bleiben unberührt (ADR-0117 Nachtrag Punkt 2).
- Die Nutzer-Grenze wird unter der globalen Sperre gegen einen nicht gesperrten Lesestand des
  Nutzer-Topfs geprüft; parallele Anfragen desselben Nutzers können seinen Anteil um höchstens die
  Parallelität (wenige Einheiten) überschreiten. Die globale Grenze ist strikt.
- Die Admin-Oberfläche zeigt den interaktiven Anteil noch nicht als eigene Spalte (Feld in der API
  vorhanden).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0117
- **Rationale:** neue Priorität und neue Grenzen im Kontingent-Modell aus ADR-0075/0076.

## Changelog

- 2026-11-13: v1.0 — erste Fassung (Issue #2961, Welle 2).
- 2026-11-13: v1.1 — Fix-Runde nach Gegenprüfung: `user_manual`, feste Grenze je Nutzer,
  Anreicherung zugerechnet, Vorhersage-Bremse, AC-10 bis AC-16.
