---
entity_id: fix_1914_radar_telegram_style
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [radar, nowcast, alarm, telegram, telegram_style, trip, compare]
---

<!-- Issue #1914 -- Kontext-Grundlage: docs/context/fix-1914-radar-telegram-style.md
     (Analyse bereits abgeschlossen, Basis-Commit siehe Workflow-State
     fix-1914-radar-telegram-style). Formatvorbild:
     docs/specs/modules/fix_1752_radar_folgt_alarm_kanaelen.md (gleiches Thema:
     Radar-Alarm folgt trip-/preset-konfiguriertem Verhalten). -->

# Radar-Alarm folgt dem konfigurierten Telegram-Stil (Trip + Ortsvergleich)

## Approval

- [ ] Approved

## Purpose

Der Radar-/Starkregen-Nowcast-Alarm ignoriert den trip- bzw. preset-konfigurierten
`telegram_style` (z. B. `"kurzform"`) und rendert auf Telegram **immer** im reichen
Emoji-/Mehrzeilen-Format — sowohl im Trip-Pfad als auch im Ortsvergleich-Pfad. Abweichungs-
und amtlicher Alarm wenden den konfigurierten Stil bereits korrekt an; Radar ist die letzte
verbliebene Ausnahme unter den vier Alarmarten. Diese Spec schließt diese Lücke, indem der
Radar-Pfad dasselbe Muster übernimmt, das die drei Geschwistermethoden bereits nutzen.

## Bewusst nicht in dieser Spec

- **`send_location_deviation_alert`** (`notification_service.py:669-689`) hat dieselbe
  Fehlerklasse — reicht `telegram_style` beim Delegieren an
  `send_multi_location_deviation_alert` ebenfalls nicht durch. Hat aktuell **keinen
  produktiven Aufrufer** (kein Treffer außerhalb `notification_service.py`), daher kein
  akutes Nutzer-Symptom. Gehört bei Bedarf in das Sammel-Issue #1199, nicht in diesen Fix.
- **Ein neuer Auflöser für `telegram_style`.** Beide benötigten Auflöser existieren bereits
  und werden unverändert wiederverwendet: `_trip_telegram_style(trip)`
  (`trip_alert.py:108-118`) und `effective_compare_telegram_style(preset)`
  (`compare_alert_channels.py:49-58`).
- **#1916 (Alarm-Vergleichsbasis) und #1657 (Dedup-Anzeige-Granularität)** — Nachbar-Befunde
  derselben KHW-Analyse, aber andere Codepfade.

## Source

- **File:** `src/services/notification_service.py`
- **Identifier:** `NotificationService.send_radar_alert()`,
  `NotificationService.send_multi_location_radar_alert()`,
  `NotificationService._dispatch_alert_message()` (Zielsenke, unverändert)

Betroffene Stellen (Zeilen nachgemessen gegen den aktuellen Arbeitsstand):

| Datei | Zeile(n) | Heute | Nach dieser Spec |
|---|---|---|---|
| `src/services/notification_service.py` | `send_radar_alert()`, Signatur ~1263-1272 | kein `telegram_style`-Parameter | neuer Parameter `telegram_style: str = "rich"` |
| `src/services/notification_service.py` | `send_radar_alert()`, Aufruf `_dispatch_alert_message()` ~1295-1303 | `telegram_style` wird nicht übergeben — Default `"rich"` von `_dispatch_alert_message()` (Zeile 1316) greift immer | `telegram_style=telegram_style` wird durchgereicht |
| `src/services/notification_service.py` | `send_multi_location_radar_alert()`, Signatur ~749-758 | kein `telegram_style`-Parameter | neuer Parameter `telegram_style: str = "rich"` |
| `src/services/notification_service.py` | `send_multi_location_radar_alert()`, Aufruf `_dispatch_alert_message()` ~807-815 | `telegram_style` wird nicht übergeben | `telegram_style=telegram_style` wird durchgereicht |
| `src/services/trip_alert.py` | Aufrufstelle ~1208-1215 | `send_radar_alert(...)` ohne `telegram_style=` | `telegram_style=_trip_telegram_style(trip)` ergänzt |
| `src/services/compare_radar_alert.py` | Aufrufstelle ~204-207 | `send_multi_location_radar_alert(...)` ohne `telegram_style=` | `telegram_style=effective_compare_telegram_style(preset)` ergänzt |

`_dispatch_alert_message()` selbst (`notification_service.py:1305-1319`, Parameter
`telegram_style: str = "rich"` bereits vorhanden auf Zeile 1316) bleibt unverändert — sie ist
bereits die geteilte Zielsenke, an die alle vier Alarmarten denselben Parameter reichen.

> **Schicht-Hinweis:** Alle vier betroffenen Dateien liegen im Python-Core
> (`src/services/`) — kein Frontend-, kein Go-API-Code betroffen.

## Estimated Scope

- **LoC (Produktivcode):** ≈ 6-8 (2× Signatur-Parameter, 2× Durchreichen im Aufruf, 2×
  Übergabe an der Aufrufstelle).
- **LoC (Tests):** ≈ 50-70 (zwei neue oder erweiterte Testfälle an den Aufrufstellen, siehe
  Testplan).
- **Files:** 3 Produktivdateien (MODIFY), 2 Testdateien (CREATE/MODIFY).
- **Effort:** low. Additiver, optionaler Parameter mit Default `"rich"` — strukturell identisch
  zu vier bereits funktionierenden Geschwistermethoden in derselben Datei.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `NotificationService.send_deviation_alert()` (`notification_service.py:628-667`) | Vorbild, unverändert | Trip-Abweichungsalarm — identisches Muster: Parameter `telegram_style: str = "rich"`, durchgereicht an `_dispatch_alert_message()` |
| `NotificationService.send_official_alert()` (`notification_service.py:817ff`) | Vorbild, unverändert | Trip-amtlicher Alarm — identisches Muster |
| `NotificationService.send_multi_location_deviation_alert()` (`notification_service.py:691ff`) | Vorbild, unverändert | Compare-Abweichungsalarm — identisches Muster |
| `NotificationService.send_multi_location_official_alert()` → `_dispatch_compare_official_telegram` (`notification_service.py:1046ff`, `:1179ff`) | Vorbild, unverändert | Compare-amtlicher Alarm — identisches Muster |
| `TripAlertService._trip_telegram_style(trip)` (`trip_alert.py:108-118`) | bestehender Auflöser, unverändert wiederverwendet | Liest `trip.report_config.telegram_style`, Default `"rich"` |
| `effective_compare_telegram_style(preset)` (`compare_alert_channels.py:49-58`) | bestehender Auflöser, unverändert wiederverwendet | Liest `preset["display_config"]["telegram_style"]`, Default `"rich"` |
| `NotificationService._dispatch_alert_message()` (`notification_service.py:1305-1319`) | Zielsenke, unverändert | Steuert bereits den Kurzstil-/Rich-Renderzweig ab `telegram_style` (Kurzstil-Zweig ab ~1448) |
| ADR-0021 (geteilte Rendering/Versand-Engine Trip/Compare) | ADR, keine Änderung | Begründet, warum Trip- UND Compare-Pfad symmetrisch in einer Spec behoben werden |

## Implementation Details

Option A (Parameter durchreichen, analog den vier bestehenden Geschwistermethoden) statt
Option B (Style zentral aus `AlertMessage` ableiten). Option B würde die bewusste
Architekturtrennung aufweichen, wonach der geteilte Dispatcher `_dispatch_alert_message()`
Trip/Compare-agnostisch bleibt (`AlertMessage` kennt weder Trip noch Preset). Option A ist
minimal-invasiv und strikt konsistent mit dem bestehenden Muster.

```
# notification_service.py — send_radar_alert()
def send_radar_alert(
    self,
    trip: "Trip",
    *,
    request: RadarAlertRequest,
    source: str,
    cooldown_display: str,
    effective_channels: set[str],
    mail_sink: Optional[object] = None,
    telegram_style: str = "rich",          # NEU
) -> NotificationResult:
    ...
    return self._dispatch_alert_message(
        ...,
        telegram_style=telegram_style,      # NEU: durchgereicht statt Default
    )

# notification_service.py — send_multi_location_radar_alert()
def send_multi_location_radar_alert(
    self,
    entities: list[tuple[str, object, "NowcastResult"]],
    effective_channels: set[str],
    *,
    tz: Optional[ZoneInfo] = None,
    stand_at: Optional[str] = None,
    mail_sink: Optional[object] = None,
    cooldown_display: Optional[str] = None,
    telegram_style: str = "rich",           # NEU
) -> NotificationResult:
    ...
    return self._dispatch_alert_message(
        ...,
        telegram_style=telegram_style,       # NEU: durchgereicht statt Default
    )

# trip_alert.py — Aufrufstelle ~1208-1215
result = self._notification_service.send_radar_alert(
    trip=trip,
    request=_radar_request,
    source=radar_svc.source_label(result.source),
    cooldown_display=cooldown_display,
    effective_channels=_radar_allowed,
    mail_sink=self._mail_sink,
    telegram_style=_trip_telegram_style(trip),   # NEU
)

# compare_radar_alert.py — Aufrufstelle ~204-207
notif_result = notification_service.send_multi_location_radar_alert(
    entities=entities, effective_channels=allowed, mail_sink=self._mail_sink,
    cooldown_display=_format_cooldown_display(cooldown_minutes),
    telegram_style=effective_compare_telegram_style(preset),   # NEU
)
```

Reihenfolge: 1) Signatur + Durchreichen Trip-Radar (`send_radar_alert`), 2) Signatur +
Durchreichen Compare-Radar (`send_multi_location_radar_alert`), 3) Aufrufer `trip_alert.py`,
4) Aufrufer `compare_radar_alert.py` — TDD: erst Trip rot/grün, dann Compare rot/grün.

## Expected Behavior

- **Input:** Ein Trip hat `report_config.telegram_style` bzw. ein Ortsvergleich-Preset hat
  `display_config.telegram_style` auf `"kurzform"` gesetzt. Ein Regenradar-/Nowcast-Alarm wird
  ausgelöst (Trip-Pfad über `check_radar_alerts()`, Compare-Pfad über den Multi-Location-Radar-
  Versand).
- **Output:** Die Telegram-Nachricht des Radar-Alarms kommt im konfigurierten Stil an — im
  Kurzstil-Format bei `"kurzform"`, im reichen Format bei `"rich"`/Default — genau wie bei
  Abweichungs- und amtlichem Alarm bereits heute. Andere Kanäle (E-Mail, SMS, Premium-SMS)
  sind von `telegram_style` unberührt, da der Parameter ausschließlich den Telegram-Renderzweig
  in `_dispatch_alert_message()` steuert.
- **Side effects:** Keine. Rein additiver, optionaler Parameter mit Default `"rich"` — kein
  Schema-Wechsel, keine Migration, kein bestehender Test erwartet Rich-Verhalten als feste
  Assertion am Radar-Pfad.

## Acceptance Criteria

- **AC-1:** Given ein Trip hat `report_config.telegram_style` auf `"kurzform"` gesetzt / When
  für diesen Trip ein Radar-/Nowcast-Alarm ausgelöst wird / Then kommt die Telegram-Nachricht
  im Kurzstil-Format an, nicht im reichen Emoji-/Mehrzeilen-Format.
  - Prüfort: Aufrufstelle `trip_alert.py` (`check_radar_alerts()` bzw. `send_radar_alert()`
    aus dem Trip-Kontext heraus), nicht nur der `NotificationService`-Baustein isoliert — Lehre
    aus Issue #1467: ein Bausteintest allein beweist die Verdrahtung nicht.
  - Test: neuer/erweiterter Test in `tests/unit/` oder `tests/tdd/` am Trip-Radar-Alarmpfad.
  - Mutation: `telegram_style=_trip_telegram_style(trip)` wird an der Aufrufstelle wieder
    entfernt bzw. der Parameter in `send_radar_alert()` nicht an `_dispatch_alert_message()`
    durchgereicht — die Telegram-Nachricht bliebe trotz `"kurzform"` im reichen Format.

- **AC-2:** Given ein Trip hat `report_config.telegram_style` auf `"rich"` gesetzt (oder das
  Feld ist unbesetzt und der Default greift) / When für diesen Trip ein Radar-/Nowcast-Alarm
  ausgelöst wird / Then bleibt die Telegram-Nachricht im reichen Format — Regressionsschutz für
  den unveränderten Bestandsfall.
  - Prüfort: dieselbe Aufrufstelle wie AC-1 (Trip-Radar-Pfad), Gegenprobe zu AC-1.
  - Test: neuer/erweiterter Test in `tests/unit/` oder `tests/tdd/` am Trip-Radar-Alarmpfad.
  - Mutation: der neue Parameter bekommt fälschlich einen anderen Default als `"rich"` oder
    wird an der Aufrufstelle hart auf `"kurzform"` verdrahtet — Rich-Trips erhielten dann
    fälschlich Kurzstil.

- **AC-3:** Given ein Ortsvergleich-Preset hat `display_config.telegram_style` auf
  `"kurzform"` gesetzt / When für dieses Preset ein Multi-Location-Radar-Alarm ausgelöst wird
  / Then kommt die Telegram-Nachricht im Kurzstil-Format an.
  - Prüfort: Aufrufstelle `compare_radar_alert.py` (der Multi-Location-Radar-Versandpfad),
    nicht nur der `NotificationService`-Baustein isoliert — dieselbe Lehre aus #1467 wie bei
    AC-1.
  - Test: neuer/erweiterter Test in `tests/unit/` oder `tests/tdd/` am Compare-Radar-Alarmpfad.
  - Mutation: `telegram_style=effective_compare_telegram_style(preset)` wird an der Aufrufstelle
    wieder entfernt bzw. `send_multi_location_radar_alert()` reicht den Parameter nicht an
    `_dispatch_alert_message()` durch — die Telegram-Nachricht bliebe trotz `"kurzform"` im
    reichen Format.

- **AC-4:** Given ein Ortsvergleich-Preset hat `display_config.telegram_style` auf `"rich"`
  gesetzt (oder das Feld ist unbesetzt und der Default greift) / When für dieses Preset ein
  Multi-Location-Radar-Alarm ausgelöst wird / Then bleibt die Telegram-Nachricht im reichen
  Format — Regressionsschutz für den unveränderten Bestandsfall im Ortsvergleich.
  - Prüfort: dieselbe Aufrufstelle wie AC-3 (Compare-Radar-Pfad), Gegenprobe zu AC-3.
  - Test: neuer/erweiterter Test in `tests/unit/` oder `tests/tdd/` am Compare-Radar-Alarmpfad.
  - Mutation: der neue Parameter bekommt fälschlich einen anderen Default als `"rich"` oder
    wird an der Aufrufstelle hart auf `"kurzform"` verdrahtet — Rich-Presets erhielten dann
    fälschlich Kurzstil.

## Testplan

**Pflicht: Tests setzen an den Aufrufstellen an, nicht nur am Baustein.** Ein Test, der
ausschließlich `NotificationService.send_radar_alert()`/`send_multi_location_radar_alert()`
direkt mit `telegram_style=...` aufruft, beweist nur, dass der Parameter innerhalb der
Methode funktioniert — nicht, dass `trip_alert.py` bzw. `compare_radar_alert.py` ihn beim
tatsächlichen Alarmauslösen auch tatsächlich befüllen. Genau diese Verdrahtungslücke war die
Fehlerursache in #1467 (87 grüne Bausteintests ließen „buchen vor zustellen" durch, weil kein
Test die Aufrufstelle prüfte). Für AC-1/AC-2 muss der Test daher über den Trip-Alarmpfad
(`TripAlertService.check_radar_alerts()` oder eine äquivalente Stelle, die
`send_radar_alert()` produktiv aufruft) laufen; für AC-3/AC-4 über den Compare-Alarmpfad
(`compare_radar_alert.py`s Versandfunktion). Die tatsächlich gerenderte Telegram-Nachricht
(bzw. der an `_dispatch_alert_message()`/den Telegram-Transport übergebene `telegram_style`-
Wert) ist der beobachtbare Nachweis, nicht ein reiner Signatur-Check.

## Known Limitations

- **`send_location_deviation_alert` bleibt unbehoben** (siehe „Bewusst nicht in dieser
  Spec") — kein produktiver Aufrufer, daher kein Nutzer-Symptom; Nebenbefund-Kandidat für
  #1199.
- **Kein neuer Auflöser.** Beide Auflöser (`_trip_telegram_style`,
  `effective_compare_telegram_style`) sind bewusst unverändert — eine dritte, radar-eigene
  Ableitung wäre die Art von Doppelarbeit, die die Projektregel „Trip/Compare teilen Code"
  verbietet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Spec wendet ein bereits etabliertes Muster (Parameter-Durchreichen an
  die geteilte Zielsenke `_dispatch_alert_message()`, ADR-0021) symmetrisch auf die letzte noch
  abweichende Alarmart (Radar) an — keine neue Architekturentscheidung, keine Abweichung von
  einer bestehenden.

## Changelog

- 2026-08-16: Initial spec erstellt — Issue #1914 (Radar-Alarm folgt dem konfigurierten
  Telegram-Stil, Trip- und Ortsvergleich-Pfad).
