---
entity_id: security_haertung_2026_11_abruf_kontingent_interaktiv
type: module
created: 2026-11-13
updated: 2026-11-13
status: approved
version: "1.0"
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
Prioritaeten: user_briefing (nie gedrosselt) | alert_check (95 %) | polling (80 %)
              | user_interactive (neu)

reserve("user_interactive", n):
  global:   calls + n <= 0.70 * 9000 = 6300            sonst abgelehnt
  je Nutzer: interaktiv_heute + n <= max(6300 // N, 1500)  sonst abgelehnt
  gebucht:  calls, interactive_calls (global); calls, interactive (Nutzer)
  Ablehnung bucht nichts und wird im interaktiven Kontext vermerkt.
Fairness alert_check/polling (Stufe 1): Nutzerverbrauch OHNE interaktiven Anteil.

Route -> with interaktiver_abruf(): ...  (ContextVar; copy_context in Arbeiter)
Segment-Weg: priority = "user_interactive" im Kontext, sonst unveraendert.
```

**Zahlen (gemessen, `test_messung_einheiten_je_vergleich_und_etappenwetter`):**

| Abruf | Einheiten ohne Cache-Treffer |
|---|---|
| Vergleich mit 10 Orten | 10 (eine je Ort; Cache-Treffer 0) |
| Etappenwetter Referenz-Tour GR221 im Repo (4 Etappen, 16 Wegpunkte) | 16 (eine je Abschnitt; je Wegpunkt ein Abschnitt) |
| Go `/api/forecast` | 2 (Konstante im Core, ADR-0076) |
| Handversand Trip (nicht interaktiv) | Abschnitte der Etappe + 1 (Nacht) + Abschnitte der bis zu 3 Folgeetappen (Trend); typisch 4 + 1 + 12 = 17, theoretisch höchstens 500 + 1 + 3 × 500 bei der Wegpunktgrenze 500 |
| Handversand Ortsvergleich (nicht interaktiv) | Zahl der Orte, höchstens die Orte-Quote (10/50/200) |

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
- **AC-2:** Given viele aktive Nutzer, sodass der faire Anteil unter 1500 fällt / When ein Nutzer bis zum Sockel bucht / Then gelingt die Buchung bis genau 1500 Einheiten und danach nicht mehr; bei zwei Nutzern ist das Limit 3150.
  - Test: `test_ac2_sockel_gilt_wenn_fairer_anteil_kleiner_ist`, `test_ac2_fairer_anteil_ueber_dem_sockel_bei_wenigen_nutzern`
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
  - Test: `test_ac9_sms_vorschau_erschoepft_429`

## Known Limitations

- Antwortbefehle über Telegram, SMS und Premium-SMS bleiben bei ihrer bisherigen Priorität
  (unterwegs-Weg, ADR-0117 Konsequenzen).
- Die nutzerfreie Radar-Anreicherung im Anbieter bucht weiter unattributiert `user_briefing`.
- Der Handversand einer Tour mit extrem vielen Wegpunkten kann theoretisch rund 2000 Einheiten je
  Versand buchen; die Go-Bremse (20 je Stunde) und der 10-Minuten-Cache begrenzen das, ein eigenes
  Tageslimit für den Handversand gibt es bewusst nicht.
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
