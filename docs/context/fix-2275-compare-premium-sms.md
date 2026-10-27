# Context: fix-2275-compare-premium-sms

## Request Summary
Issue #2275: Der Premium-SMS-Schalter im Versand-Reiter des Ortsvergleichs hat keine Wirkung.
`premium_sms` landet in `effective_channels`, `send_compare_report` bedient den Kanal aber nicht
(stilles Übergehen). Entscheid (Tech Lead im PO-Mandat, 09.09.): **verdrahten**, AC-1..AC-3 gelten, AC-4 entfällt.
Vorbedingung #2279 ist seit 17.09. geschlossen.

## Related Files (Stand origin/main 92252757)
| File | Relevance |
|------|-----------|
| `src/services/notification_service.py:1231` `send_compare_report` | Hier fehlt der `premium_sms`-Zweig (Issue nennt `:1154` — veraltet). Hat nur email/telegram/sms; `NotificationResult` ohne `failed_channels` |
| `src/services/notification_service.py:642-660` | Trip-Briefing-Zweig Premium-SMS (Vorlage): `_sms_gate_reserve("premium_sms","briefing",…)`, `PremiumSmsOutput.send`, bei Fehler `release_reservation` + `blocked_channels` + `_record_block_reason_code` |
| `src/services/notification_service.py:1205-1222` | Alarm-Zweig des Vergleichs (Vorlage #1701): gleiche Bausteine, zusätzlich `failed_channels.append` |
| `src/services/notification_service.py:800-830` | dritte Kopie des Briefing-Zweigs (`send_premium_sms`-Parameter, #1676 S2a) — Kandidat für „eine gemeinsame Kanal-Schleife" |
| `src/services/compare_alert_channels.py:32-52` | `effective_compare_briefing_channels`: nimmt `premium_sms` auf bei `preset.send_premium_sms` UND `premium_sms_allowed(user_id)` |
| `src/services/scheduler_dispatch_service.py:413,630` | Aufrufer; reicht `sms_text=render_compare_sms(...)` durch. Wertet `send_result` nur über `.sent` aus |
| `src/output/renderers/comparison.py` | `render_compare_sms` — liefert die Vergleichs-Kurzform (Trip nimmt `report.sms_text or email_plain`) |
| `src/output/channels/premium_sms.py` | `PremiumSmsOutput` (Rückadresse-Pflicht, 30-Tage-Frist, Sperren) |
| `src/services/alert_channels.py:26`, `alert_log.py:85` | `_ALL_CHANNELS` inkl. `premium_sms` — Anknüpfungspunkt für den Vollständigkeits-Wächter (AC-3) |
| `internal/model/compare_preset.go:97`, `compareHubWizardBridge.ts:539`, `VTBriefingChannels.svelte:200` | Persistenz/Hydrierung/Schalter — Frontend bleibt unverändert (AC-4 entfällt) |
| `CLAUDE.md` (Zeile „Premium-SMS-Reichweite") | Aussage „Versandkanal nur im Trip-Briefing" muss mit der Lieferung korrigiert werden |

## Existing Patterns
- Premium-SMS-Zweig: Tageslimit reservieren → senden → bei Fehler Reservierung freigeben, Grund in `blocked_channels` + maschinenlesbare Kennung, Log-Zeile. Bewusst ohne `can_send_*()`-Frage (D2 #1701).
- Fail-soft je Kanal im Vergleichsversand; E-Mail propagiert Fehler (Bestandsverhalten).
- Transport-Naht per `*_sink` für deterministische Tests (kein Netz) — ein `premium_sms_sink` wäre analog nötig.

## Dependencies
- Upstream: `PremiumSmsOutput`, `sms_daily_limit`, `_sms_gate_reserve`, `premium_sms_allowed`, `render_compare_sms`.
- Downstream: `send_one_compare_preset` (Scheduler + Handversand `POST /api/scheduler/compare-presets/{id}/send`), Zustellbilanz/Status.

## Existing Specs
- `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` (Trip-Briefing; Abgrenzung nennt den Vergleich als Folgearbeit)
- `docs/context/rework-2279-alert-kanal-aufloesung.md`

## Existing Tests (Kandidaten zum Erweitern)
`tests/tdd/test_sms_tageslimit.py`, `test_compare_briefing_anchor_and_memory_reset.py`, `test_telegram_test_mode_guard.py`, `tests/test_success_status_guard.py` (Erfolgs-Ratsche — prüfen, ob `send_compare_report` betroffen ist)

## Risks & Considerations
- **Echter, kostenpflichtiger Versand + Tageslimit:** Tests nur mit Sink/Fake; Live-Nachweis über die zweite seven.io-Nummer (Staging, Test-Preset, nie Sammelversand).
- **Ergebnisfeld:** `send_compare_report` gibt kein `failed_channels` zurück — für AC-2 ergänzen; der Aufrufer muss es auswerten, sonst bleibt der Fehler unsichtbar.
- **Sperrgrund vs. Transportfehler:** Trip-Briefing bucht in `blocked_channels`, der Alarm zusätzlich in `failed_channels` — AC-2 verlangt `failed_channels`; einheitliche Semantik in der Spec festlegen.
- **Zielbild „nicht kopieren":** gemeinsame Kanal-Schleife statt vierter Kopie (#1412). Umfang gegen LoC-Limit 250 abwägen; kleinster Schnitt: ein Helfer für den Premium-Zweig, den Trip und Vergleich benutzen.
- **AC-3 Wächter:** Test, der für jeden Kanal aus den aufgelösten Kanälen prüft, dass der Versandpfad ihn bedient (Trip UND Vergleich).
- **Kurzform-Länge:** prüfen, ob `render_compare_sms` für das Garmin-Gerät passt (Länge/Zeichensatz).
- **Mandanten:** Test mit zwei Nutzern (`user_id` durchreichen, nie `default`).

## Analysis

### Type
Bug (Verdrahtungslücke): `premium_sms` wird im Vergleichs-Briefing aufgelöst (`effective_compare_briefing_channels`), aber `send_compare_report` hat keinen Zweig dafür — der Kanal wird still übergangen, Nutzer sieht einen aktiven Schalter ohne Wirkung. Entscheid „verdrahten" steht (Issue, 09.09.).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/notification_service.py` (`send_compare_report`, ab ~1231) | MODIFY | Neuer `premium_sms`-Zweig nach dem `sms`-Zweig: `_sms_gate_reserve("premium_sms","briefing",…)` → `PremiumSmsOutput.send` → bei Fehler `release_reservation` + `blocked_channels` + `_record_block_reason_code` + `failed_channels`; neuer Parameter `premium_sms_sink`; Ergebnisfeld `failed_channels` |
| `src/services/scheduler_dispatch_service.py` (~630) | MODIFY | `premium_sms_sink` durchreichen; `send_result.failed_channels`/`blocked_channels` auswerten (bisher nur `.sent`) |
| `tests/tdd/test_compare_premium_sms_versand.py` (Verhaltensname) | CREATE | AC-1 Versand, AC-2 Fehler sichtbar, AC-3 Vollständigkeits-Wächter Trip+Vergleich, Zwei-Nutzer-Test |
| `CLAUDE.md` (Zeile „Premium-SMS-Reichweite") | MODIFY (Doku) | „Versandkanal nur im Trip-Briefing" korrigieren |
| Frontend / Go / Persistenz | keine | Schalter, Persistenz und Hydrierung existieren bereits (AC-4 entfällt) |

### Scope Assessment
- Files: 3 Code/Test (+1 Doku)
- Estimated LoC: +90/-5 produktiv, +120 Test (unter 250-Limit, Tests zählen mit — ggf. knapp)
- Risk Level: MEDIUM — kostenpflichtiger Echtversand + Tageslimit; Fehlerpfad muss Reservierung freigeben. Änderung isoliert auf einen Kanal-Zweig.

### Technical Approach
1. **Kleinster Schnitt:** ein Helfer `_send_premium_sms_branch(...)` in `NotificationService`, den Trip-Briefing (Z. 642), Alarm (Z. 1201) und Vergleich benutzen könnten. Für diese Lieferung NUR den Vergleich auf den Helfer legen und die Trip-Kopien unangetastet lassen (LoC/Risiko); Konsolidierung der übrigen Kopien als Sammel-Eintrag #1199.
2. **Semantik einheitlich:** Sperrgrund UND Transportfehler → `blocked_channels`+`blocked_reason_codes`; zusätzlich `failed_channels.append("premium_sms")` bei Exception (wie Alarm-Zweig). Kanal wird erst bei Erfolg in `sent_channels` geführt (wie Trip-Briefing).
3. **Text:** `sms_text` des Vergleichs (`render_compare_sms`, Budget 153 Zeichen GSM-7) — passt für Garmin; kein eigener Renderer nötig.
4. **Kein `can_send_*()`** vor dem Zweig (D2 #1701); Rückadresse/30-Tage-Frist prüft `PremiumSmsOutput` selbst.
5. **Testnaht:** `premium_sms_sink` analog `sms_sink`; deterministisch, kein Netz. Bestehendes Fake-Muster in `tests/tdd/test_sms_tageslimit.py:123` (Patch auf `output.channels.premium_sms`) nutzbar.
6. **AC-3-Wächter:** parametrisiert über `alert_channels._ALL_CHANNELS`: für jeden aufgelösten Kanal muss der Vergleichs-Versandpfad ihn bedienen (Sink wird gerufen oder Sperrgrund gebucht).
7. **Live-Nachweis:** Staging, Test-Preset, zweite seven.io-Nummer als Empfangsgerät — nie Sammelversand.

### Dependencies
- Upstream: `PremiumSmsOutput`, `sms_daily_limit`, `_sms_gate_reserve`, `premium_sms_allowed`, `render_compare_sms`.
- Downstream: `send_one_compare_preset` (Scheduler + Handversand `POST /api/scheduler/compare-presets/{id}/send`), Zustellbilanz.
- Vorbedingung #2279 geschlossen.

### Befunde aus der Analyse
- Issue nennt `:1154` — veraltet, aktuell `:1231`.
- `send_compare_report` hat seit #2412 S4a bereits `blocked_channels`/`blocked_reason_codes`, aber KEIN `failed_channels`.
- Aufrufer wertet nur `.sent` aus → Fehler des neuen Kanals wären ohne Auswertung weiter unsichtbar.

### Open Questions
- [ ] Soll ein gescheiterter Premium-SMS-Versand den Preset-Versand als Ganzes als Fehler melden (wie E-Mail) oder nur sichtbar in `failed_channels` bleiben (wie Telegram/SMS)? Empfehlung: fail-soft + Status/Log sichtbar (Ortsvergleich hat keinen Nachhol-Mechanismus, ein Abbruch würde E-Mail-Erfolg entwerten).
- [ ] Argument-Hinweis: Aufruf lautete `#227` (geschlossenes, fachfremdes Issue, node:test-Import); ausgewertet wurde der aktive Workflow #2275.
