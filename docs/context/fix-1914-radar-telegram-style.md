# Context: fix-1914-radar-telegram-style

## Request Summary
Der Radar-/Starkregen-Nowcast-Alarm ignoriert den trip- bzw. preset-konfigurierten `telegram_style` (z. B. `"kurzform"`) und rendert auf Telegram immer im reichen Format — sowohl im Trip-Pfad als auch im Ortsvergleich-Pfad, während Abweichungs- und amtlicher Alarm den Stil korrekt anwenden.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/notification_service.py:1263-1272` | `send_radar_alert()` (Trip) — Signatur hat **keinen** `telegram_style`-Parameter |
| `src/services/notification_service.py:1295-1303` | Aufruf von `_dispatch_alert_message()` innerhalb `send_radar_alert()` — `telegram_style` wird nicht übergeben, Default `"rich"` (Zeile 1316) greift |
| `src/services/notification_service.py:749-758` | `send_multi_location_radar_alert()` (Compare) — Signatur hat **keinen** `telegram_style`-Parameter |
| `src/services/notification_service.py:807-815` | Aufruf von `_dispatch_alert_message()` innerhalb `send_multi_location_radar_alert()` — `telegram_style` wird nicht übergeben |
| `src/services/notification_service.py:1305-1319` | `_dispatch_alert_message()` — zentraler Dispatcher, Parameter `telegram_style: str = "rich"` (Zeile 1316), Kurzstil-Zweig ab Zeile ~1448 |
| `src/services/trip_alert.py:1208-1215` | Aufrufstelle Trip-Radar — `send_radar_alert(...)` ohne `telegram_style=` |
| `src/services/trip_alert.py:108-118` | `_trip_telegram_style(trip)` — bestehender Auflöser, Default `"rich"` |
| `src/services/compare_radar_alert.py:204-207` | Aufrufstelle Compare-Radar — `send_multi_location_radar_alert(...)` ohne `telegram_style=`; lokale Variable heißt `preset` (dict, Zeile 184 `notification_service_for(preset)`) |
| `src/services/compare_alert_channels.py:49-58` | `effective_compare_telegram_style(preset)` — bestehender Auflöser für Compare, liest `preset["display_config"]["telegram_style"]`, Default `"rich"` |
| `src/services/compare_official_alert.py:56-65` | `_effective_telegram_style()` — dünner Wrapper auf obigen Auflöser (ADR-0021) |

## Existing Patterns

Vier funktionierende Vorbilder in derselben Datei zeigen exakt das benötigte Muster (Parameter in Signatur + Durchreichen an `_dispatch_alert_message()` + Übergabe an der Aufrufstelle):

- **Trip-Abweichung:** `notification_service.py:628-667` `send_deviation_alert()` — Parameter `telegram_style: str = "rich"` (Zeile 636), durchgereicht Zeile 666. Aufrufer `trip_alert.py:~1372-1381`, `telegram_style=_trip_telegram_style(trip)` auf ~1379.
- **Trip-amtlich:** `send_official_alert()` (`notification_service.py:817ff`, Param ~824). Aufrufer `trip_alert.py:~1614-1620`, `telegram_style=` auf ~1619.
- **Compare-Abweichung:** `send_multi_location_deviation_alert()` (`notification_service.py:691ff`, Param ~697). Aufrufer `compare_alert.py:~279-289`, `telegram_style = effective_compare_telegram_style(preset)` auf ~232, übergeben auf ~288.
- **Compare-amtlich:** `send_multi_location_official_alert()` (`notification_service.py:1046ff`, Param ~1052) → `_dispatch_compare_official_telegram` (~1179, Param ~1182). Aufrufer `compare_official_alert.py:~192-198`, `_effective_telegram_style(preset)` als 5. Positionsargument auf ~195.

Der Fix für den Radar-Pfad folgt strukturell demselben Muster — kein neuer Auflöser nötig, beide (`_trip_telegram_style`, `effective_compare_telegram_style`) existieren bereits.

## Dependencies

- **Upstream:** `ReportConfig.telegram_style` (Trip, `src/app/models.py:1084`, Default `"rich"`) bzw. `preset["display_config"]["telegram_style"]` (Compare) — beide bereits persistiert und im Frontend editierbar (`VTBriefingChannels.svelte`, `AlarmeTab.svelte`).
- **Downstream:** `_dispatch_alert_message()` steuert damit den Telegram-Renderzweig (Kurzstil vs. reich, ab `notification_service.py:~1448`).

## Existing Specs
Keine dedizierte Spec zu `telegram_style` selbst; Ursprung ist Issue #1260 S3 (Feature-Einführung `kurzform`). ADR-0021 legt fest, dass Rendering/Versand zwischen Trip und Ortsvergleich geteilt bleiben — das begründet, warum beide Pfade (Trip UND Compare) in einem Fix behoben werden.

## Risks & Considerations

- **Zuschnitt muss beide Flächen umfassen:** Trip- und Compare-Radar-Pfad haben symmetrisch dieselbe Lücke. Nur einen zu fixen erzeugt eine neue, gegen die Projektregel „Trip/Compare teilen Code" verstoßende Asymmetrie.
- **Testlücke:** Kein bestehender Test prüft `telegram_style` am Radar-Pfad (weder Trip noch Compare) — Tests müssen an der Aufrufstelle (`trip_alert.py`/`compare_radar_alert.py`) ansetzen, nicht nur am `NotificationService`-Baustein (Lehre aus #1467: Bausteintests allein beweisen die Verdrahtung nicht).
- **Bewusst ausgeklammerter Nebenbefund:** `send_location_deviation_alert` (`notification_service.py:669-689`) reicht `telegram_style` beim Delegieren an `send_multi_location_deviation_alert` ebenfalls nicht durch — hat aktuell keinen produktiven Aufrufer (kein Treffer außerhalb `notification_service.py`), daher kein akutes Nutzer-Symptom. Gehört bei Bedarf in Sammel-Issue #1199, nicht in diesen Fix.
- **Nicht Teil dieses Fixes:** #1916 (Alarm-Vergleichsbasis) und #1657 (Dedup-Anzeige-Granularität) sind Nachbar-Befunde derselben KHW-Analyse, aber andere Codepfade.

## Analysis

### Type
Bug

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/notification_service.py` | MODIFY | `telegram_style: str = "rich"` zu `send_radar_alert()` (~1263) und `send_multi_location_radar_alert()` (~749) ergänzen, an `_dispatch_alert_message()` durchreichen (~1295, ~807) |
| `src/services/trip_alert.py` | MODIFY | Aufrufstelle ~1208-1215: `telegram_style=_trip_telegram_style(trip)` ergänzen |
| `src/services/compare_radar_alert.py` | MODIFY | Aufrufstelle ~204-207: `telegram_style=effective_compare_telegram_style(preset)` ergänzen |
| `tests/tdd/test_compare_radar_alert.py` bzw. neue Testdatei | CREATE/MODIFY | Test an der Aufrufstelle (nicht nur Baustein), der die Verdrahtung Trip-Radar → Kurzstil beweist |
| `tests/tdd/test_compare_alert_telegram_per_location.py` bzw. Compare-Pendant | MODIFY | Analoger Test für Compare-Radar → Kurzstil |

### Scope Assessment
- Files: 3 Produktivdateien, 2 Testdateien (neu oder erweitert)
- Estimated LoC: Produktiv ~6-8 LoC (2× Signatur, 2× Durchreichen, 2× Aufrufer); Test ~50-70 LoC
- Risk Level: LOW — additiver optionaler Parameter mit Default `"rich"`, kein bestehender Test erwartet Rich-Verhalten als Assertion am Radar-Pfad (geprüft: `test_compare_radar_alert.py`, `test_multi_location_onset_alert.py`, `test_compare_alert_telegram_per_location.py`, `test_alert_sms_location_positions.py` — keine `assert_called_with`-Signaturbindung)

### Technical Approach
Option A (Parameter durchreichen, analog den vier bestehenden Geschwistermethoden) statt Option B (Style zentral aus `AlertMessage` ableiten) — Option B würde die bewusste Architekturtrennung aufweichen, wonach der geteilte Dispatcher `_dispatch_alert_message()` Trip/Compare-agnostisch bleibt (`AlertMessage` kennt weder Trip noch Preset). Option A ist minimal-invasiv und strikt konsistent mit dem bestehenden Muster. Reihenfolge: 1) Signatur+Durchreichen Trip-Radar, 2) Signatur+Durchreichen Compare-Radar, 3) Aufrufer `trip_alert.py`, 4) Aufrufer `compare_radar_alert.py` — TDD: erst Trip rot/grün, dann Compare rot/grün.

### Dependencies
Keine neuen Abhängigkeiten. Beide Auflöser (`_trip_telegram_style`, `effective_compare_telegram_style`) existieren bereits und werden unverändert wiederverwendet.

### Open Questions
Keine offenen Fragen — Ansatz ist eindeutig durch vier funktionierende Vorbilder in derselben Datei vorgegeben.
