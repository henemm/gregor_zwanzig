# Context: fix-1452-compare-empfaenger

## Request Summary

Issue #1452 behauptete, der Ortsvergleich könne Empfänger nirgends einstellen und der Nutzer erfahre nicht, wohin gesendet wird. Recherche zeigt: Beides stimmt so nicht (mehr) — die Zieladresse wird bereits im Versand-Reiter angezeigt, und der Versand geht faktisch immer an die Konto-Adresse. PO-Entscheidung (2026-08-02): Ortsvergleich soll **strukturell** immer an die Konto-Settings des Users gehen (E-Mail/Telegram/SMS), für beide Dienste (Trip und Vergleich) identisch. Der eigentliche Auftrag ist daher:

1. Das serverseitige `empfaenger`-Override entfernen — kein Feld darf mehr von den Konto-Settings abweichen können.
2. Die Cockpit-Kanal-Anzeige reparieren, die heute fälschlich `preset.empfaenger` als Kanal-Aktiv-Indikator liest (immer leer, zeigt daher nie Kanal-Chips).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/scheduler_dispatch_service.py:332-339` | Empfänger-Override-Fallback (regulärer Compare-Versand) |
| `src/services/compare_official_alert.py:209-215` | Empfänger-Override-Fallback (amtliche Warnungen) |
| `src/services/compare_alert.py:295-301` | Empfänger-Override-Fallback (Gewitter/Schwellen-Alarm) |
| `src/services/compare_radar_alert.py:170-177` | Empfänger-Override-Fallback (Radar-Alarm) |
| `src/app/models.py:919` | `ComparePreset.empfaenger: List[str]` — Datenmodell-Feld |
| `src/app/loader.py:256` | Lädt `empfaenger` aus JSON (Bestandsdaten-Kompatibilität) |
| `internal/model/compare_preset.go:34` | Go-SSoT-Feld `Empfaenger []string` |
| `internal/handler/compare_preset.go:139` | Format-Validierung je Eintrag (E-Mail-Regex) |
| `frontend/src/lib/components/compare/compareEditorSave.ts:317` | Setzt `empfaenger: []` beim Anlegen |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:251` | Fehlerhafte "@"-Ableitung als E-Mail-Kanal-Indikator |
| `frontend/src/routes/_home/cockpitHelpers.ts:225,236` | `channels: preset.empfaenger` |
| `frontend/src/lib/components/organisms/HomeHeroCompare.svelte:33` | `preset.channels ?? preset.empfaenger ?? []` |
| `frontend/src/lib/components/molecules/CompareStatusRow.svelte:63-64` | Kanal-Chips, rendert nur wenn `empfaenger` nicht leer |
| `frontend/src/routes/+page.svelte:526` | Iteriert `compareHero.empfaenger` |
| `frontend/src/routes/compare/+page.svelte:339` | Bestätigungsdialog-Text nutzt `empfaenger.length` |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte:107-121` | Zeigt Ziel-Adresse bereits an (E-Mail/Telegram/SMS je `profile.*`) — funktioniert bereits, unverändert |

## Existing Patterns

- **Referenzmuster `send_telegram`/`send_sms`:** `compareWizardState.svelte.ts` (`$state`) → `compareEditorSave.ts:293-294` (Payload) → `internal/model/compare_preset.go:91-92` (`*bool`-Feld) → Python `Optional[bool]`. Zeigt, wie ein persistiertes Kanal-Flag korrekt durch den Stack läuft — als Vorlage für die Reparatur der Kanal-Anzeige (die künftig auf echte Flags statt `empfaenger` zeigen soll).
- **E-Mail ist für Compare-Presets bewusst immer aktiv**, kein Opt-out: `scheduler_dispatch_service.py:275-292` (`_effective_compare_channels`, `channels = {"email"}` unbedingt). Dokumentierte Alt-Entscheidung `docs/specs/modules/versand_tab_vergleich.md:382` (KL-6): E-Mail-Checkbox bleibt bewusst unpersistiert — **kein Bestandteil dieses Fixes**, nicht anfassen.
- **Read-Modify-Write-Pflicht** (CLAUDE.md „Daten-Schema-Reworks"): `empfaenger` als Feld selbst NICHT aus dem Datenmodell entfernen (Bestandsdaten alter Presets bleiben erhalten), nur die Override-Auswertung in den vier Diensten entfernen.

## Dependencies

- Upstream: `Settings().with_user_profile(user_id)` liefert `mail_to`/`telegram_chat_id`/`sms_to` — bleibt einzige Quelle nach dem Fix.
- Downstream: Vier Alarm-/Versanddienste (scheduler_dispatch, official_alert, alert, radar_alert) müssen synchron umgestellt werden — inkonsistente Teilumstellung würde die Dienste auseinanderlaufen lassen.

## Existing Specs

- `docs/specs/modules/versand_tab_vergleich.md` — KL-6 (E-Mail-Checkbox unpersistiert, bewusst) bleibt gültig und unberührt.

## Risks & Considerations

- **Vier Dienste, ein Muster** — alle vier müssen identisch umgestellt werden, sonst entsteht neue Inkonsistenz zwischen Alarmkanälen.
- **Bestehende Tests testen das Override aktiv** (siehe unten) — werden bei Entfernung absichtlich rot, müssen umgeschrieben werden (Verhaltensänderung, kein Regressionsfehler).
- **Sicherheitsrelevante Pfade:** amtliche Warnungen, Gewitter- und Radar-Alarm sind alarmauslösende, zeitkritische Kanäle (vgl. Memory „Gewitter/SMS: HÖCHSTE Prio") — Umstellung braucht sorgfältige Tests je Dienst.
- **Bekannte Tests, die rot werden:** `tests/tdd/test_compare_preset_send.py:51-68`, `tests/tdd/test_issue_461_compare_preset_dispatch.py:138-156`, `tests/tdd/test_compare_dispatch_mail_marker.py:61`, `tests/test_compare_official_alert.py:81-94`, `tests/test_compare_radar_alert.py:74-94`. Frontend: `compare_preset_channels.test.ts:44`, `compareEditorSave.test.ts:38-203`, `compare_save_deprecated_fields_roundtrip.test.ts:43,111`, `issue_571_home_cockpit_hero.test.ts:48`.
- **Keine aktiven Produktiv-Nutzer** (Memory: „KEINE Produktiv-User") — reduziert das Risiko, dass ein echter Nutzer heute `empfaenger` bewusst zum Override nutzt.

## Analysis

### Type
Bug/Tech-Debt-Fix (aus Issue #1452 heraus reformuliert nach PO-Klärung 2026-08-02)

### Entwurfsentscheidung: Feld behalten, nur Override-Nutzung entfernen (Option B)

Drei unabhängige Recherchen (2x Explore, 1x Plan) bestätigen übereinstimmend: `ComparePreset.empfaenger` bleibt im Datenmodell (Python/Go/TS) bestehen — analog zu den bereits bestehenden deprecated Feldern im selben Modell (`schedule`, `previous_schedule`, `weekday`, `hour_from/to`, `forecast_hours`, laut Docstring „werden unnormalisiert getragen"). Nur die **Lese-Stellen**, die es als Empfänger-Override bzw. Kanal-Indikator missbrauchen, werden umgestellt. Begründung: Read-Modify-Write-Pflicht (CLAUDE.md), lebender Präzedenzfall `trip_alert.py:125` (baut `NotificationService` bereits ohne jeden Preset-Override), Frontend schreibt beim Speichern ohnehin schon immer `empfaenger: []` — das Feld ist im Schreibpfad längst inert. Eine volle Schema-Entfernung (Go-Model/Store/Handler) hätte ~40-50 Dateien berührt (fast nur Test-Fixture-Rauschen ohne inhaltlichen Nutzen) und wurde verworfen.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/compare_alert.py:294-303` | MODIFY | `_notification_service_for()` → `NotificationService(self._settings, self._user_id)` ohne Override, analog `trip_alert.py:125` |
| `src/services/compare_official_alert.py:208-217` | MODIFY | identisch zu compare_alert.py |
| `src/services/compare_radar_alert.py:169-179` | MODIFY | identisch zu compare_alert.py |
| `src/services/scheduler_dispatch_service.py:332-339` | MODIFY | Override-Block raus, direkter `settings.mail_to`-Check; Rückgabewert `empfaenger` bleibt (Logging/Response-Count) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:251` | MODIFY | „@"-Heuristik raus, E-Mail-Kanal für Compare-Presets unconditional aktiv (KL-6-konform) |
| `frontend/src/routes/_home/cockpitHelpers.ts:225,236` | MODIFY | `preset.empfaenger` → `presetChannels(preset)` (Wiederverwendung statt Duplikat) |
| `frontend/src/lib/components/molecules/CompareStatusRow.svelte:63-64` | MODIFY | Kanal-Chips aus `presetChannels(preset)` statt rohen `empfaenger`-Adressen — Chip-Inhalt ändert sich von Adresse zu Kanal-Label |
| `frontend/src/lib/components/organisms/HomeHeroCompare.svelte:33` | MODIFY | Fallback auf `empfaenger` raus (`preset.channels ?? []`) |
| ~10-15 gezielte Testdateien (Backend: Override-Verhalten von `_notification_service_for`/`send_one_compare_preset`; Frontend: `compare_preset_channels.test.ts`, `channel_names_label.test.ts`, ggf. `hub_versand_inline.test.ts`) | MODIFY | Testen künftig „immer Settings", nicht mehr „Override wirkt" |
| ~40-50 weitere Dateien mit `empfaenger`-Vorkommen (Fixtures/Roundtrip-Tests) | KEINE ÄNDERUNG | reines Rauschen, Feld bleibt im Schema gültig |

### Scope Assessment
- Kern-Fix: 8 Dateien, ca. 60-90 LoC (überwiegend Löschung)
- Tests: ca. 10-15 Dateien, ca. 80-150 LoC
- Risk Level: MEDIUM (berührt Gewitter-/amtliche-/Radar-Alarmpfad — höchste Prio-Kanal des Projekts — aber Änderung ist mechanisch, Präzedenzfall existiert bereits live)

### Technical Approach
Bestätigt: Option B (Feld behalten, Lesestellen umstellen). Reihenfolge: TDD-RED zuerst je Datei (Backend vor Frontend, `compare_alert.py` zuerst wegen Priorität) → Backend-Kern-Fix (compare_alert.py zuerst isoliert verifizieren, dann die zwei Analog-Services, dann scheduler_dispatch_service.py) → Frontend-Kern-Fix (subscriptionHelpers.ts zuerst als zentrale Quelle, dann Konsumenten) → volle Testsuite, Fixture-Rauschen nicht anfassen.

**Wichtig für die Spec:** Die Frontend-„E-Mail immer aktiv"-Änderung in `subscriptionHelpers.ts` ist keine reine Quellen-Umstellung, sondern eine bewusste Verhaltensänderung (muss als eigenes AC formuliert werden, nicht implizit im Refactor untergehen).

### Dependencies
- Telegram/SMS in den drei Alert-Services lesen `self._settings.telegram_chat_id`/`.sms_to` bereits direkt (Override betraf faktisch nur E-Mail) — kein Änderungsbedarf dort.
- Alle drei Alert-Services sind live verdrahtet über `api/routers/scheduler.py:73-105` (nicht toter Code, wie eine erste Recherche fälschlich vermutete).

### Fehlerbehandlung — bewusst NICHT vereinheitlicht
`scheduler_dispatch_service.py` wirft weiterhin `ValueError` bei fehlendem `mail_to`; die drei Alert-Services bleiben beim stillen Fallback (nur ergänzt um `logger.warning`, wenn `mail_to` fehlt). Vereinheitlichung würde entweder Alarm-Läufe bei fehlendem `mail_to` abbrechen lassen (Schaden > Nutzen bei höchster Priorität) oder den lauten Scheduler-Pfad stumm schalten (Regressionsrisiko im UI-Fehlerverhalten) — beides ein eigenständiges Thema, kein Bestandteil dieses Fixes. Bei Bedarf eigenes Issue.

### Open Questions
- [x] Feld behalten oder entfernen? → Behalten (Option B), s.o.
- [x] Fehlerbehandlung vereinheitlichen? → Nein, separates Thema falls gewünscht
- [ ] Chip-Darstellung im Cockpit ändert sich sichtbar (Adresse → Kanal-Label „Email"/„Telegram"/„SMS") — PO-Bestätigung bei Spec-Freigabe einholen, ob das gewünscht ist oder die Chips ganz entfernt werden sollen, wenn keine echten Empfänger mehr angezeigt werden.
