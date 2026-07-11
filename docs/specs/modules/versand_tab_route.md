# Spec: VersandTab (route) — geteilter Versand-Organism im Trip-Editor

- **Workflow:** feat-1232-versand-tab-route
- **Issue:** #1232 (Phase 4 — Editor-Konsolidierung, Sub-Issue von Epic #1230) · Scheibe 1/3
- **created:** 2026-07-11
- **Typ:** Frontend-Refactor ohne Verhaltensänderung (eine bewusste UX-Verschiebung: notify-Zustellung zieht in den Versand-Tab)
- **Design-Quelle (1:1):** `claude-code-handoff/current/jsx/versand-tab.jsx` + `soll-29b-desktop-versand-route.png` + `soll-29b-mobile.png`

## Ziel

Der Trip-Editor-Tab „Briefings" wird durch den neuen geteilten Organism
`VersandTab` (`context="route"`) ersetzt. Er bündelt ALLES, was rausgeht:
Briefing-Kanäle, Briefing-Zeitplan, Laufzeit-Anzeige und die komplette
Alert-Zustellung (bisher im Alerts-Tab). Der Alerts-Tab wird dadurch auf die
Empfindlichkeits-/Level-Tabelle reduziert. Kein neues Datenmodell (C4).

## Dateien (geplant)

| Datei | Aktion |
|---|---|
| `frontend/src/lib/components/shared/VersandTab.svelte` | NEU — Organism, Sektionen 1–4, Prop `context` (Scheibe 1: nur `route` aktiv) |
| `frontend/src/lib/components/shared/versand-tab/*.svelte` | NEU — VT-Bausteine (BriefingChannels, SchedulePlan, LaufzeitRoute) 1:1 aus JSX |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | UM — mountet VersandTab statt EditReportConfigSection; Mail-Inhalt-Sektion bleibt darunter |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | UM — Mail-Inhalt-Teil als weiter nutzbare Sektion; Zeitplan/Kanäle-Teil entfällt zugunsten VersandTab |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte` | UM — Zustell-Controls (ChannelToggle×2, Cooldown, Stille Stunden, Beispiel) raus; Level-Tabelle + Onboarding bleiben |

Wiederverwendet (kein Neubau, testids unverändert): `ChannelToggle`,
`AlertCooldownCard`, `AlertQuietHoursCard`, `AlertPreviewCard`.

## Acceptance Criteria

**AC-1:** Given der Trip-Editor ist geöffnet / When ich den Tab „Briefings" wähle / Then sehe ich die vier Versand-Sektionen in Design-Reihenfolge: „Geplantes Briefing · Kanäle" → „Briefing-Zeitplan" → „Laufzeit" → Alert-Zustellung („Wann Warnungen rausgehen" + Beispiel-Warnung).

**AC-2:** Given der Briefings-Tab ist offen / When ich einen Briefing-Kanal (E-Mail, Telegram oder SMS) an- oder abschalte / Then wird das bestehende Feld `report_config.send_*` per Auto-Save persistiert und nach Reload korrekt wieder angezeigt.

**AC-3:** Given der Briefings-Tab ist offen und mindestens ein Kanal aktiv / When ich in der Karte „Morgen-Briefing" oder „Abend-Briefing" den Schalter oder die Uhrzeit (`<input type="time">`) ändere / Then werden `morning_enabled`/`evening_enabled` bzw. `morning_time`/`evening_time` persistiert; bei ausgeschalteter Karte ist das Uhrzeit-Feld deaktiviert.

**AC-4:** Given kein einziger Briefing-Kanal ist aktiv / When ich auf den Briefing-Zeitplan schaue / Then erscheint statt der Zeitplan-Karten die Warnbox „Kein Kanal aktiv" mit dem Hinweis, zuerst einen Kanal zu aktivieren.

**AC-5:** Given der Trip hat Etappen mit Datumsangaben / When ich die Sektion „Laufzeit" ansehe / Then zeigt sie read-only „Läuft mit der Tour · endet <Enddatum aus letzter Etappe>" und der Button „Etappen öffnen →" wechselt in den Etappen-Tab; es gibt dort KEIN editierbares Datumsfeld.

**AC-6:** Given der Trip-Editor ist geöffnet / When ich den Alerts-Tab öffne / Then enthält er nur noch Überschrift, Onboarding/Aktivierung und die Metrik-Level-Tabelle — Alert-Kanäle, Cooldown, Stille Stunden und Beispiel-Warnung erscheinen dort NICHT mehr, sondern vollständig und funktionsgleich im Briefings-Tab (Werte werden weiterhin persistiert wie bisher).

**AC-7:** Given die bestehenden Playwright-Selektoren / When die Seite gerendert ist / Then existieren die bisherigen `data-testid`s unverändert (u. a. `morning-master-switch`, `report-morning-time`, `evening-master-switch`, `report-evening-time`, `channel-email`, `channel-telegram`, `channel-sms`, `briefings-channel-empty`, `alerts-tab`, `report-mail-content`) — nur der Tab, unter dem die notify-Controls hängen, hat sich geändert.

**AC-8:** Given die Umsetzung ist fertig / When man Typen und API-Aufrufe vergleicht / Then sind `ReportConfig`, `AlertRule` und alle API-Endpunkte unverändert — kein neues Datenmodell, keine Backend-Änderung (rein `frontend/src`).

**AC-9:** Given der mobile Viewport (bestehender Mobile-Zugang des Trip-Editors) / When ich den Briefings-Tab nutze / Then sind alle vier Sektionen einspaltig bedienbar (dense-Layout analog `soll-29b-mobile.png`), ohne horizontales Scrollen.

**AC-10:** Given der Briefings-Tab ist offen / When ich unterhalb der Versand-Sektionen scrolle / Then ist die bisherige Mail-Inhalt-Sektion (`report-mail-content`: E-Mail-Format full/compact + Inhalts-Module) unverändert vorhanden und funktionsfähig.

## Known Limitations (Teil der Freigabe)

- **KL-1 · Karten-Kanal-Chips entfallen:** Das Design zeigt je Zeitplan-Karte eigene Kanal-Chips (E-Mail/Telegram je Briefing getrennt). Dafür existiert kein Backend-Feld (nur globale `send_*`). Scheibe 1 lässt die Chips weg — die globale Kanalwahl (Sektion 1) gilt für beide Briefings. Kein Fake-UI.
- **KL-2 · Mehrtages-Trend ohne eigene Uhrzeit:** Das Design zeigt eine dritte Karte „Mehrtages-Trend" mit eigener Uhrzeit. Das Datenmodell kennt nur `multi_day_trend_morning/evening` (Anhängsel an Morgen/Abend). Umsetzung: Trend-Karte mit zwei Anhänge-Schaltern „im Morgen-Briefing" / „im Abend-Briefing", ohne eigenes Uhrzeit-Feld.
- **KL-3 · `context="vergleich"` folgt in Scheibe 2:** Der Organism wird context-fähig angelegt, aber der Compare-Editor bleibt in Scheibe 1 unberührt.
- **KL-4 · LoC-Limit:** Die 1:1-Übersetzung überschreitet 250 LoC → Override auf 500 nötig (Bestandteil dieser Freigabe).

## Edge Cases

| Fall | Verhalten |
|---|---|
| Kein Kanal aktiv | Warnbox statt Zeitplan-Karten (AC-4) |
| Karte aus | Uhrzeit-Feld disabled, Wert bleibt erhalten |
| SMS aktiv | bisheriger Premium-/Längen-Hinweis bleibt (aus Kanal-Gating) |
| Trip ohne Etappen-Daten | Laufzeit zeigt „—" statt Datum, Button bleibt funktionsfähig |
| Testids doppelt im DOM (Mobile+Desktop) | Playwright nutzt `:visible` |

## Out of Scope

- LayoutTab (Scheibe 3), Compare-Editor/`vergleich` (Scheibe 2), `briefings[]`-Reshape (Scheibe 2), CorridorEditor (#1231), Backend/Go, Mail-Renderer.

## Test-Nachweis

- Kern: Verhaltens-Playwright-Spec (Tab-Klick-Pfad, `:visible`) gegen Staging in `/60-validate`; RED-Phase über mark-red-Mechanismus (FE-Test in RED blockiert per edit_gate).
- Fresh-Eyes gegen `soll-29b-desktop-versand-route.png` + `soll-29b-mobile.png`.
