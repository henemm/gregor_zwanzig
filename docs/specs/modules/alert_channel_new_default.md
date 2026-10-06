---
entity_id: alert_channel_new_default
type: module
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "1.0"
tags: [alerts, onboarding, trip, compare, issue-2518]
---

# Alarm-Kanal-Vorbelegung bei Neuanlage: E-Mail an

## Approval

- [ ] Approved

## Purpose

Ein neu angelegter Trip oder Ortsvergleich stellt Alarme standardmäßig per **E-Mail** zu. Heute ist E-Mail bei Neuanlage aus; ein Free-Nutzer ohne Telegram bekommt dadurch gar keine Alarme (Issue #2518).

## Source

- **File:** `frontend/src/lib/components/shared/alarme-tab/alertChannelState.ts`
- **Identifier:** `NEW_ENTITY_DEFAULT`, `resolveAlertChannels`
- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts`
- **Identifier:** Create-Body-Rückfall `alert_channels` (Z. ~463)

Schicht: nur Frontend. Go/Python bleiben unverändert (Tier-Gate in `src/services/alert_channels.py:89-92` wirkt weiter).

## Estimated Scope

- **LoC:** ~20 Produktivcode + Tests
- **Files:** 2 Produktiv, 2–3 Tests
- **Effort:** low

## Ist-Zustand (belegt)

| Fläche | Angezeigt im Alarme-Reiter | Gespeichert |
|---|---|---|
| Trip neu (`tripNewLogic.ts:157`) | Telegram + SMS | Telegram + SMS |
| Ortsvergleich neu, Reiter unberührt | Telegram + SMS (`resolveAlertChannels(undefined)`) | E-Mail + Briefing-Flags (`compareEditorSave.ts:463`) |

- Free-Level: SMS fällt serverseitig weg → effektiv nur Telegram → ohne Verknüpfung **nichts**.
- Ortsvergleich: Anzeige und Speicherung weichen voneinander ab, wenn der Nutzer den Reiter nicht anfasst.

## Design-Entscheidungen

1. **Neuer Default:** `email: true, telegram: true, sms: false, premium_sms: false`.
   - E-Mail an: Hauptkanal (PO 2026-10-06).
   - Telegram an: kostenlos; ohne Verknüpfung stellt der Server nichts zu, nach späterer Verknüpfung laufen Alarme ohne Nachbearbeitung jedes Trips an.
   - SMS aus: Kostenkanal, für Free nicht verfügbar und wird nicht beworben (PO 2026-10-06). Premium-SMS bleibt aus (#1745).
2. **Eine Quelle:** Der Ortsvergleichs-Rückfall beim Anlegen nutzt denselben Default wie der Reiter — Angezeigtes = Gespeichertes.
3. **Bestand unverändert:** Nur Neuanlagen. Gespeicherte `alert_channels` werden weder migriert noch beim Laden umgedeutet (`resolveAlertChannels(existing)` mit Bestand bleibt wie heute).
4. **Nicht im Umfang:** Hinweis „effektiv kein Kanal erreichbar“ unter Berücksichtigung von Level und Verknüpfung → Onboarding #2521.

## Acceptance Criteria

**AC-1:** Given ein Nutzer legt einen neuen Trip an und öffnet den Alarme-Reiter nicht / ändert dort nichts, When er speichert, Then enthält der gespeicherte Trip `alert_channels` = `{email: true, telegram: true, sms: false, premium_sms: false}`.

**AC-2:** Given ein Nutzer legt einen neuen Ortsvergleich an und ändert im Alarme-Reiter nichts, When er speichert, Then enthält das gespeicherte Preset `alert_channels` = `{email: true, telegram: true, sms: false, premium_sms: false}` — unabhängig von den Briefing-Kanal-Schaltern im Versand-Reiter.

**AC-3:** Given der Alarme-Reiter einer Neuanlage (Trip oder Ortsvergleich) ohne Bestand, When er angezeigt wird, Then sind E-Mail und Telegram angehakt und SMS sowie Premium-SMS nicht — identisch zu dem, was AC-1/AC-2 speichern.

**AC-4:** Given ein bestehender Trip oder Ortsvergleich mit gespeicherten `alert_channels` (z. B. `{telegram: true, sms: true, email: false}`), When er geladen und unverändert gespeichert wird, Then bleiben die gespeicherten Werte exakt erhalten (keine Migration auf den neuen Default).

**AC-5:** Given ein Free-Nutzer ohne Telegram-Verknüpfung mit einem nach dieser Änderung angelegten Trip, When die serverseitige Kanal-Auflösung (`resolve_alert_channels`) läuft, Then enthält die effektive Kanalmenge `email`.

## Test-Plan

- Kern (deterministisch, Frontend-Unit): AC-1 über `buildCreateTripPayload`/`initialCreateTripAlarmState`, AC-2 über den Create-Body aus `compareEditorSave.ts`, AC-3 über `resolveAlertChannels(undefined)`, AC-4 über `resolveAlertChannels(existing)` und den Ortsvergleichs-Create-Pfad mit gesetzten Kanälen.
- Kern (Python): AC-5 mit Trip-Dict `alert_channels` = neuer Default und Free-Nutzer → `email` in der effektiven Menge.
- Bestehende Tests, die den alten Default (Telegram + SMS) festschreiben, werden auf den neuen Default umgestellt (veraltetes Verhalten).

## Changelog

- 2026-10-06: Erstfassung (Issue #2518).
