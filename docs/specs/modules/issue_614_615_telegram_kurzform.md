---
entity_id: issue_614_615_telegram_kurzform
type: module
created: 2026-06-06
updated: 2026-06-06
status: draft
version: "1.0"
tags: [output, telegram, sms, channel-renderer]
---

# Telegram Kurzform-Option (Tages-Max) — #614 / #615

## Approval

- [x] Approved (PO „go", 2026-06-06)

## Purpose

Telegram bekommt eine **konfigurierbare Option**, zusätzlich zur bestehenden Monospace-
Tabelle die kompakte **SMS-Kurzform** anzuhängen. Weil Telegram bis 4096 Zeichen erlaubt,
läuft die Kurzform **ohne Truncation** und trägt damit ALLE konfigurierten Metriken — auch
jene, die über dem 8-Spalten-Limit der Tabelle liegen (Funktion „Tages-Max"). Das SMS-
Wire-Format selbst bleibt unverändert (#615 erfordert keinen Format-Umbau).

## Source

- **File (Python):** `src/app/models.py` (`UnifiedWeatherDisplayConfig`), `src/formatters/trip_report.py`
- **File (Go-API):** `internal/model/*.go` — **keine Struct-Änderung**; Wert läuft durch
  `DisplayConfig map[string]interface{}` (additiver Map-Key, Merge bleibt erhalten)
- **File (Frontend):** Kanal-/Layout-Editor (Telegram-Bereich) — Toggle
- **Identifier:** `UnifiedWeatherDisplayConfig.telegram_kurzform`, Render-Anhang in `format_email()`

## Estimated Scope

- **LoC:** ~120–160 (Python Render + Model-Feld + Frontend-Toggle)
- **Files:** 3–5
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SMSTripFormatter.format_sms()` | reuse | erzeugt die Kurzform aus denselben `segments` |
| `render_narrow("telegram", …)` | existing | bestehende Telegram-Tabelle (unverändert) |
| `UnifiedWeatherDisplayConfig` | extend | neues additives Feld `telegram_kurzform` |
| `DisplayConfig` (Go-Map) | passthrough | persistiert den Toggle ohne Struct-Änderung |

## Implementation Details

```
# src/app/models.py — UnifiedWeatherDisplayConfig
telegram_kurzform: bool = False   # additiv, Default aus = heutiges Verhalten

# src/formatters/trip_report.py — nach telegram_text = render_narrow("telegram", …)
if dc.telegram_kurzform:
    kurzform = SMSTripFormatter().format_sms(
        segments,
        stage_name=stage_name or trip_name,
        report_type=report_type,
        tz=self._tz,
        max_length=KURZFORM_MAX,   # hoch (z.B. 4000) → keine §6-Truncation, alle Metriken
    )
    telegram_text = f"{telegram_text}\n\nTages-Max:\n{kurzform}"
```

Persistenz: Go-API liest/schreibt `display_config` als generische Map → Read-Modify-Write-
Merge bereits gegeben; `telegram_kurzform` round-trippt ohne Go-Code-Änderung.

## Acceptance Criteria

**AC-1:** Given ein Trip-DisplayConfig mit `telegram_kurzform = true`, When der Trip über die
Go-API gespeichert und erneut geladen wird, Then ist `display_config.telegram_kurzform`
weiterhin `true` UND alle übrigen `display_config`-Felder (metrics, per_channel_layouts etc.)
sind unverändert erhalten (Read-Modify-Write-Merge, kein Datenverlust).

**AC-2:** Given ein Trip mit `telegram_kurzform = true` und mehr aktiven Metriken als die
Telegram-Tabelle in 8 Spalten zeigen kann, When ein Telegram-Briefing gerendert wird, Then
enthält `telegram_text` zusätzlich zur Tabelle einen mit `Tages-Max:` eingeleiteten
SMS-Kurzform-Block, der ALLE aktiven Metriken als Kurzcodes enthält — auch jene über dem
8-Spalten-Limit — und KEINE Metrik wegen Truncation fehlt.

**AC-3:** Given ein Trip mit `telegram_kurzform = false` (Default), When ein Telegram-Briefing
gerendert wird, Then ist `telegram_text` byte-identisch zum bisherigen Verhalten (nur Tabelle,
kein Kurzform-Block angehängt).

**AC-4:** Given das bestehende SMS-Wire-Format (sms_format.md v2.0), When eine SMS für denselben
Trip gerendert wird, Then bleibt der SMS-Output bit-identisch zu den Golden-Mastern in
`tests/golden/sms/` (das SMS-Format wird durch dieses Feature NICHT verändert).

**AC-5:** Given der Kanal-/Layout-Editor eines Trips im Frontend, When der Nutzer den
Telegram-Bereich öffnet, den Schalter „Kurzform anhängen (Tages-Max)" aktiviert und speichert,
Then wird `telegram_kurzform = true` persistiert und ist nach Neuladen der Seite weiterhin
aktiviert.

## Out of Scope

- Umbau des SMS-Wire-Formats (TH%, Z:WATCH, ohne Peaks aus dem JSX-Entwurf) → Design-Request,
  da der getestete Golden-Master gewinnt; JSX-Kommentar sagt selbst „Beispiel im Spec-Format".
- Mehrteilige Folgetag-SMS (`+1`) — vom PO explizit verworfen.
- Optische Angleichung der Telegram-Tabelle an die Bubble (Segment-Kopf, feste Spaltenbreite).
