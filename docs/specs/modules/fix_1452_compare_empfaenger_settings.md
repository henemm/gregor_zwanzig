---
entity_id: fix_1452_compare_empfaenger_settings
type: module
created: 2026-08-02
updated: 2026-08-02
status: draft
version: "1.0"
tags: [compare, alerts, notification, multi-user, cockpit]
---

<!-- Issue #1452 (umformuliert nach PO-Klärung 2026-08-02) -->

# Ortsvergleich-Versand: Empfänger-Override entfernen, Kanal-Anzeige reparieren

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich-Versand (Gewitter-Alarm, amtliche Warnungen, Radar-Alarm, regulärer
Compare-Versand) darf E-Mails künftig **ausschließlich** an die Konto-Settings des
jeweiligen Users senden — nie an ein preset-eigenes `empfaenger`-Override. Das bringt
den Vergleichs-Versand auf dasselbe Muster wie den Trip-Versand
(`trip_alert.py:125`, der bereits ohne jeden Preset-Override arbeitet). Zusätzlich wird
eine dabei gefundene kaputte Cockpit-Kanal-Anzeige repariert, die heute fälschlich
`preset.empfaenger` als Aktiv-Indikator für den E-Mail-Kanal liest und deshalb nie
korrekte Kanal-Chips zeigt.

Issue #1452 selbst (ursprüngliche Prämisse: „Empfänger lassen sich nirgends
einstellen") ist durch Recherche widerlegt und wird separat geschlossen/kommentiert —
**nicht** Teil dieser Spec.

## Source

- **File:** `src/services/compare_alert.py` — **Identifier:** `_notification_service_for()` (Zeilen 294-303)
- **File:** `src/services/compare_official_alert.py` — **Identifier:** analoge Methode (Zeilen 208-217)
- **File:** `src/services/compare_radar_alert.py` — **Identifier:** analoge Methode (Zeilen 169-179)
- **File:** `src/services/scheduler_dispatch_service.py` — **Identifier:** `send_one_compare_preset()`-Umfeld (Zeilen 332-339)
- **File:** `frontend/src/lib/components/compare/subscriptionHelpers.ts` — **Identifier:** `presetChannels()` (Zeile 251)
- **File:** `frontend/src/routes/_home/cockpitHelpers.ts` — Zeilen 225, 236
- **File:** `frontend/src/lib/components/molecules/CompareStatusRow.svelte` — Zeilen 63-64
- **File:** `frontend/src/lib/components/organisms/HomeHeroCompare.svelte` — Zeile 33

> Schicht-Check: vier Python-Dienste in `src/services/` (Python-Core, live verdrahtet
> über `api/routers/scheduler.py:73-105`), vier SvelteKit-Dateien in `frontend/src/`
> (produktive Cockpit-/Compare-Oberfläche). Keine Go-API-Änderung — `internal/model/compare_preset.go:34`
> bleibt unverändert, das Feld `Empfaenger` wird nur nicht mehr als Override gelesen.

## Estimated Scope

- **LoC:** ~140-240 (Kern-Fix ~60-90 LoC, überwiegend Löschung; Tests ~80-150 LoC)
- **Files:** 8 Kern-Dateien (4 Backend, 4 Frontend) + ca. 10-15 gezielte Testdateien
- **Effort:** medium (mechanische Änderung an vier synchron zu haltenden Diensten, aber Präzedenzmuster existiert bereits live)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Settings().with_user_profile(user_id)` | intern (Python-Core) | Liefert `mail_to`/`telegram_chat_id`/`sms_to` — bleibt einzige Empfänger-Quelle nach dem Fix |
| `NotificationService(settings, user_id)` | intern (Python-Core) | Versandobjekt, wird künftig ohne Override konstruiert — Vorbild `trip_alert.py:125` |
| `api/routers/scheduler.py:73-105` | intern (Python-Core) | Verdrahtet alle drei Alert-Services live in den Scheduler-Lauf — kein toter Code |
| `presetChannels()` (`subscriptionHelpers.ts`) | intern (Frontend) | Zentrale Kanal-Ableitung, wird von Cockpit-Konsumenten künftig wiederverwendet statt dupliziert |
| `docs/specs/modules/versand_tab_vergleich.md` (KL-6) | Spec | E-Mail-Checkbox-Persistenz bleibt bewusst unverändert — s. Known Limitations |

## Implementation Details

### Backend (vier Dienste, identisches Zielmuster)

```
# Vorher (alle vier Dienste, sinngemäß):
empfaenger = preset.get("empfaenger") or settings.mail_to
notification_service = NotificationService(settings_with_override(empfaenger), user_id)

# Nachher (analog trip_alert.py:125):
notification_service = NotificationService(self._settings, self._user_id)
```

- `compare_alert.py`, `compare_official_alert.py`, `compare_radar_alert.py`:
  `_notification_service_for()`-Äquivalent baut `NotificationService` ausschließlich aus
  `self._settings` (bereits via `with_user_profile(user_id)` aufgelöst). Kein Lesen von
  `preset["empfaenger"]` mehr für die Empfängerbestimmung. Zusätzlich: Wenn
  `settings.mail_to` leer/fehlend ist, wird ein `logger.warning(...)` mit User- und
  Preset-Bezug geloggt (bisher stiller Skip) — der Lauf selbst bricht **nicht** ab
  (kein Crash im Alarm-Lauf, da höchste Priorität).
- `scheduler_dispatch_service.py`: Override-Block entfernt, direkter
  `settings.mail_to`-Check. Wirft weiterhin `ValueError`, wenn `mail_to` fehlt
  (unverändertes Fehlerverhalten — bewusst nicht vereinheitlicht, s. Known Limitations).
  Der Rückgabewert für Logging/Response-Zählung darf weiterhin `empfaenger` im Payload
  führen (nur die Versand-Entscheidung ändert sich, nicht das Antwortformat).
- Telegram/SMS-Zweige in den drei Alert-Services lesen bereits direkt
  `self._settings.telegram_chat_id` / `self._settings.sms_to` — **keine Änderung dort**,
  das Override wirkte faktisch nur auf E-Mail.

### Frontend (vier Konsumenten der Kanal-Anzeige)

```
# subscriptionHelpers.ts:251 — Vorher:
const hasEmail = preset.empfaenger?.some(e => e.includes("@"));

# Nachher (KL-6-konform: E-Mail ist für Compare-Presets immer aktiv):
const hasEmail = true; // Compare-Presets haben kein send_email-Opt-out (KL-6)
```

- `subscriptionHelpers.ts` (`presetChannels()`): "@"-Heuristik auf `empfaenger`
  entfernt. E-Mail-Kanal wird für Compare-Presets unconditional als aktiv gemeldet.
  Telegram-/SMS-Zweige (`send_telegram`/`send_sms`) bleiben unverändert — die lesen
  bereits korrekt.
- `cockpitHelpers.ts:225,236`: `channels: preset.empfaenger` → `channels: presetChannels(preset)`
  (Import/Wiederverwendung statt eigener Duplikat-Logik).
- `CompareStatusRow.svelte:63-64`: Kanal-Chips werden aus `presetChannels(preset)`
  gerendert statt aus rohen `empfaenger`-Adressen. **Sichtbare Änderung:** Chip-Inhalt
  wechselt von „rohe Adresse" (z. B. `henning@henemm.com`) zu Kanal-Label
  (`Email`/`Telegram`/`SMS`) — explizit in AC-8 formuliert, keine stille Nebenwirkung.
- `HomeHeroCompare.svelte:33`: `preset.channels ?? preset.empfaenger ?? []` →
  `preset.channels ?? []` (Fallback auf das jetzt bedeutungslose Feld entfällt).

### Datenmodell — unverändert

`ComparePreset.empfaenger` bleibt als Feld erhalten in `src/app/models.py:919`,
`internal/model/compare_preset.go:34`, `frontend/src/lib/types.ts:573` — Read-Modify-Write-Pflicht
(CLAUDE.md „Daten-Schema-Reworks"). Bestandsdaten alter Presets werden weiterhin geladen
(`src/app/loader.py:256`), aber nirgends mehr für Versand- oder Anzeige-Entscheidungen
gelesen.

## Expected Behavior

- **Input:** Ein Compare-Preset mit beliebigem (auch nicht-leerem) `empfaenger`-Feld,
  ausgelöst durch Scheduler-Lauf (Gewitter/amtlich/Radar/regulär) oder Cockpit-Rendering.
- **Output:** Versand geht ausschließlich an `Settings().with_user_profile(user_id).mail_to`
  (bzw. `.telegram_chat_id`/`.sms_to`), unabhängig vom Inhalt des `empfaenger`-Feldes.
  Cockpit-Kanal-Chips zeigen Kanal-Label statt Rohadressen.
- **Side effects:** Bei fehlendem `mail_to` in den drei Alert-Services: `logger.warning`
  statt stillem Skip, Lauf läuft für andere User/Presets weiter. In
  `scheduler_dispatch_service.py`: unverändert `ValueError` bei fehlendem `mail_to`.

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset von User A mit gesetztem `empfaenger`-Feld
  (z. B. `["fremde-adresse@example.com"]`) und ein abweichendes `mail_to` in den
  Settings von User A / When der Gewitter-Alarm-Dienst (`compare_alert.py`) für dieses
  Preset einen Alarm auslöst / Then geht die Mail ausschließlich an `mail_to` aus den
  Settings von User A, niemals an die im Preset hinterlegte `empfaenger`-Adresse.
  - Test: Preset mit Fremd-Adresse in `empfaenger`, Versand-Ziel wird gegen `settings.mail_to` geprüft (nicht gegen Preset-Feld) — Kern-Suite, kein Live-Mailversand nötig.

- **AC-2:** Given dasselbe Szenario wie AC-1 / When der amtliche-Warnungen-Dienst
  (`compare_official_alert.py`) bzw. der Radar-Alarm-Dienst (`compare_radar_alert.py`)
  einen Alarm auslöst / Then gilt identisch: Versand ausschließlich an `settings.mail_to`,
  kein Lesen von `preset["empfaenger"]`.
  - Test: Je ein gezielter Test pro Dienst, analog AC-1 — beide Dienste unabhängig verifiziert.

- **AC-3:** Given ein Compare-Preset mit gesetztem `empfaenger`-Feld / When der reguläre
  Compare-Versand (`scheduler_dispatch_service.py`, `send_one_compare_preset`) läuft /
  Then geht die Mail ausschließlich an `settings.mail_to`; bei fehlendem `mail_to` wirft
  der Dienst weiterhin `ValueError` (unverändertes Fehlerverhalten).
  - Test: Zwei Fälle — `mail_to` gesetzt (Versand-Ziel = Settings, nicht Preset) und `mail_to` fehlt (ValueError wird weiterhin geworfen, kein stiller Erfolg).

- **AC-4:** Given ein Compare-Preset ohne `mail_to` in den Settings des Users /
  When einer der drei Alert-Services (`compare_alert.py`, `compare_official_alert.py`,
  `compare_radar_alert.py`) einen Alarm für dieses Preset verarbeitet / Then bricht der
  Lauf **nicht** ab (kein Crash, andere User/Presets im selben Lauf werden weiter
  verarbeitet), aber es wird ein `logger.warning` mit User- und Preset-Bezug geschrieben
  (nicht mehr stiller Skip wie vorher).
  - Test: Zwei Presets im selben Alarm-Lauf, eines ohne `mail_to` — Lauf beendet beide, Warning-Log für das fehlerhafte Preset ist nachweisbar, zweites Preset wird trotzdem zugestellt.

- **AC-5:** Given zwei Compare-Presets von zwei verschiedenen Usern (User A, User B)
  mit jeweils eigenem `mail_to` in den Settings / When derselbe Alarm-Lauf (z. B.
  Gewitter) beide Presets verarbeitet / Then erhält User A ausschließlich Mails an
  `settings_A.mail_to`, User B ausschließlich an `settings_B.mail_to` — kein
  Cross-User-Leck, unabhängig vom `empfaenger`-Feld in beiden Presets.
  - Test: Multi-User-Testfall mit zwei User-IDs, Versand-Ziel je Preset wird gegen das jeweils eigene `mail_to` geprüft (Pflicht laut CLAUDE.md Mandantentrennung).

- **AC-6:** Given die drei Alert-Services (`compare_alert.py`,
  `compare_official_alert.py`, `compare_radar_alert.py`) / When Telegram- oder
  SMS-Alarme ausgelöst werden / Then bleibt das Verhalten unverändert — Ziel ist weiterhin
  `self._settings.telegram_chat_id` bzw. `.sms_to`, keine Regression durch diesen Fix.
  - Test: Bestehender Telegram-/SMS-Testfall pro Dienst bleibt grün ohne Anpassung (Nicht-Veränderungs-Nachweis).

- **AC-7:** Given ein Compare-Preset im Cockpit mit `send_telegram: true`,
  `send_sms: false` und beliebigem `empfaenger`-Inhalt / When `presetChannels(preset)`
  aufgerufen wird / Then enthält das Ergebnis den E-Mail-Kanal (unconditional aktiv,
  KL-6) und den Telegram-Kanal, aber nicht SMS — unabhängig davon, ob `empfaenger`
  leer oder gefüllt ist.
  - Test: `presetChannels()` mit Preset-Fixtures (leeres `empfaenger`, gefülltes `empfaenger`) liefert in beiden Fällen identisches Kanal-Set, gesteuert nur durch `send_telegram`/`send_sms`.

- **AC-8:** Given ein Compare-Preset mit aktivem E-Mail-Kanal / When die
  Cockpit-Kanal-Chips gerendert werden (`CompareStatusRow.svelte`, Home-Hero via
  `cockpitHelpers.ts`) / Then zeigt der Chip das Kanal-Label „Email" (nicht die
  rohe `empfaenger`-Adresse) — sichtbare, gewollte Änderung der Chip-Darstellung.
  - Test: Playwright/Component-Test rendert `CompareStatusRow` mit einem Preset, das ein nicht-leeres `empfaenger`-Array aber keine Channel-Flags hat — Chip zeigt „Email", nicht die Adresse aus `empfaenger`.

- **AC-9:** Given ein Compare-Preset ohne jedes gesetzte `send_telegram`/`send_sms`-Flag
  und mit leerem `empfaenger` / When das Home-Hero (`HomeHeroCompare.svelte`) die
  Kanäle für dieses Preset ermittelt / Then wird ausschließlich `preset.channels ?? []`
  verwendet — kein Fallback mehr auf `preset.empfaenger`, auch wenn `channels` leer ist.
  - Test: Preset-Fixture mit gefülltem `empfaenger`, aber `channels: undefined` — Home-Hero zeigt leere Kanalliste, nicht die `empfaenger`-Länge.

## Known Limitations

- **KL-1:** `ComparePreset.empfaenger` bleibt im Datenmodell (Python/Go/TS) bestehen —
  bewusste Entwurfsentscheidung (Read-Modify-Write-Pflicht, Bestandsdaten-Kompatibilität).
  Das Feld ist nach diesem Fix vollständig inert (wird nirgends mehr gelesen), aber nicht
  entfernt. Eine volle Schema-Entfernung würde ~40-50 weitere Dateien (reines
  Fixture-Rauschen) berühren und wurde verworfen.
- **KL-2:** `docs/specs/modules/versand_tab_vergleich.md` KL-6 (E-Mail-Checkbox für
  Compare-Presets bewusst unpersistiert, kein Opt-out) bleibt **unverändert** und ist
  **nicht** Teil dieser Spec — diese Spec spiegelt das bestehende Verhalten in der
  Kanal-Anzeige nur korrekt wider, ändert es aber nicht.
- **KL-3:** Fehlerbehandlung wird bewusst NICHT vereinheitlicht:
  `scheduler_dispatch_service.py` wirft weiterhin `ValueError` bei fehlendem `mail_to`;
  die drei Alert-Services brechen bei fehlendem `mail_to` weiterhin nicht ab, loggen aber
  neu ein `logger.warning`. Eine Vereinheitlichung wäre ein eigenständiges Thema
  (Alarm-Läufe dürfen bei fehlendem `mail_to` nicht komplett abbrechen; der laute
  Scheduler-Pfad soll nicht stumm werden) — bei Bedarf eigenes Issue.
- **KL-4:** ~40-50 weitere Test-/Fixture-Dateien mit `empfaenger`-Vorkommen (reine
  Roundtrip-/Schema-Tests, die das Feld nur als leeres/beliebiges Array mitführen)
  werden nicht angefasst — das Feld bleibt im Schema gültig, nur die Auswertung als
  Override/Kanal-Indikator entfällt.
- **KL-5:** Issue #1452 selbst (ursprüngliche Prämisse „Empfänger nirgends einstellbar")
  wird separat geschlossen/kommentiert, nicht durch diese Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Architekturmuster — die Änderung bringt den Vergleichs-Versand
  auf ein bereits etabliertes, live genutztes Muster (`trip_alert.py:125`, Settings als
  einzige Empfänger-Quelle). Keine neue Entscheidungsfläche (Kanal, Provider, Datenmodell,
  Auth) im Sinne der ADR-Pflicht aus `docs/adr/README.md`.

## Changelog

- 2026-08-02: Initial spec created (aus Issue #1452 heraus, nach PO-Klärung 2026-08-02)
