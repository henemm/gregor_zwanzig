---
entity_id: feat_3174_trip_sms_ohne_doppelpunkt
type: feature
created: 2026-11-19
updated: 2026-11-19
status: approved
version: "1.0"
workflow: feat-3174-trip-sms-ohne-doppelpunkt
tags: [trip, sms, premium-sms, telegram, kurzstil, token-zeile, kanal-paritaet]
---

# Trip-SMS ohne Doppelpunkt nach dem Etappen-Präfix (Issue #3174)

## Approval

- [x] Approved — PO-Auswahl 2026-11-19 in der Sitzung zu #3172 (Frage: „Soll die Trip-SMS den Doppelpunkt auch verlieren (`E3 N12 D17 …`)?“ — Antwort: **„Beide ohne“**, Begründung: „Jedes Zeichen ist kostbar!!!“), festgehalten im Issue #3174 und in ADR-0125 Nr. 2. Kein weiterer Fachinhalt offen: nur der Trenner nach dem Präfix entfällt.

## Purpose

Seit #3172 beginnt die Orte-SMS mit `O1 D-5/0 …` (ohne Doppelpunkt). Die Trip-SMS schreibt heute noch `E3: N12 D17 …`. Damit wieder genau eine Schreibweise gilt und ein Zeichen mehr für Werte bleibt, entfällt der Doppelpunkt nach dem Etappen-Präfix bzw. Namens-Präfix der Trip-SMS: `E3 N12 D17 R- PR53%@13 W21@13 G26@10(31@13) TH:- TH+:-`, `GR221 km0-11 N9 …`, `Ballone D16 …`.

## Source

- **File:** `src/output/tokens/render.py`
- **Identifier:** `_draw` (einzige Stelle, an der der Kopf `"{stage}: "` gebildet wird; `render_line`, `render_line_with_survivors` und die §6-Kürzung messen über `_draw`)
- **Nebenstellen (lesen die Trip-SMS):** `src/services/placements_view_service.py::_trip_sms_rumpf` (SMS-Beispiel und Werte der Karte „Was steht wo“), `tests/helpers/einstellung_auslieferung_orakel.py::_sms_treffer` (Prüforakel)

> **Schicht-Hinweis:** Python-Core. Kein Go-Code, kein Frontend-Code. Kürzel-Doppelpunkte (`TH:`, `TH+:`, `WD:`, `PT:`, `VR:`/`VT:`, `Z:`, `M:`) gehören zum Symbol und bleiben (sms_format.md §3.2a, #1824).

## Scope

Nur der Kopf der Trip-Kurznachricht: Trip-SMS, Premium-SMS des Trips (derselbe Text, Regel #3100 unverändert) und Telegram-Kurzstil des Trips (derselbe Text). Unverändert: Orte-SMS (schon ohne, #3172), Mail samt Betreff, Telegram-Normalstil, Alarm-SMS, Kürzel-Doppelpunkte, Kürzungsregel §6 (misst denselben Text, hat jetzt ein Zeichen mehr Platz).

## Estimated Scope

- **LoC:** ca. +10 / −8 Produktionscode, dazu Erwartungen in Goldens und Tests
- **Files:** 2 Produktionsdateien, 1 Testhilfe, ca. 40 Golden-/Testdateien, 3 Doku-Dateien
- **Effort:** low

## Design

1. `_draw(stage, tokens)` → `" ".join([stage, *_fuse(tokens)])` (wie `orte_sms.orte_ortsteil`). Ohne Token steht nur das Präfix (`E3`), ohne Leerzeichen am Ende.
2. Präfix-Bildung bleibt: `_sms_stage_prefix` (`Etappe N: …` → `E{N}`, sonst Name ASCII, max. 10 Zeichen) und `builder._sanitize_stage_name` (km-Bereich bleibt vollständig, `GR221 km0-11`). Ein Doppelpunkt am Namensende wird wie bisher abgeschnitten.
3. `_trip_sms_rumpf` trennt den Kopf `"{Präfix} "` ab (gebildet mit denselben zwei Funktionen wie im Versand). Passt der Kopf nicht, ist der Rumpf ab dem ersten Wort, das ein bekanntes Token ist — es wird nie am ersten `: ` getrennt, da Token selbst `:` tragen (`TH:-`).
4. Das Prüforakel trennt den Kopf ebenfalls ohne `: ` ab; es ordnet nur Wörter zu, die vollständig der Token-Grammatik entsprechen, das Präfix (`E3`, `GR221`, `km0-11`) ist keins.
5. Keine Altform-Weiche: Es gibt keinen Leser, der die Trip-SMS als Eingabe parst (Inbound-Befehle lesen Nutzertext, nicht die SMS).

## Acceptance Criteria

**AC-1:** Given ein Trip mit Etappe „Etappe 3: …“ und gewählten Metriken / When das Abend- bzw. Morgenbriefing über den echten Versandweg versendet wird / Then beginnt die SMS mit `E3 ` gefolgt vom ersten Token (z. B. `E3 N2 TF- …`), und an keiner Stelle steht `E3:`.

**AC-2:** Given derselbe Versand / When Premium-SMS und Telegram-Kurzstil desselben Trips gebaut werden / Then tragen beide denselben Text wie die SMS (Kopf ohne Doppelpunkt; Premium-SMS nach #3100 höchstens 153 Zeichen).

**AC-3:** Given ein Etappenname mit km-Bereich („GR221 Mallorca km0-11“) bzw. ein freier Name („Ballone“) / When die Token-Zeile gerendert wird / Then lautet der Kopf `GR221 km0-11 ` bzw. `Ballone ` ohne Doppelpunkt, und ein Name, der auf `:` endet, erzeugt keinen Doppelpunkt.

**AC-4:** Given eine Token-Zeile, deren Text ohne Kürzung genau 160 Zeichen hat, wenn der Kopf ohne Doppelpunkt geschrieben wird / When sie mit Grenze 160 gerendert wird / Then wird nicht gekürzt (das gesparte Zeichen steht für Werte zur Verfügung), und eine Zeile ohne Token ergibt nur das Präfix ohne Leerzeichen am Ende.

**AC-5:** Given ein Trip-Abo mit SMS-Haken bei mehreren Metriken / When die Karte „Was steht wo“ (Placements-Ansicht) gebaut wird / Then zeigt das SMS-Beispiel den Kopf ohne Doppelpunkt, und die Werte je Metrik werden weiterhin aus der SMS zugeordnet (keine Metrik verliert ihren Beispielwert durch das geänderte Präfix).

**AC-6:** Given Kürzel mit eigenem Doppelpunkt (`TH:`, `TH+:`, `WD:`, `PT:`, `VR:`/`VT:`) / When die Zeile gerendert wird / Then bleiben diese Doppelpunkte unverändert (`TH:-`, `WD:NW`).

## Tests

- Neu: `tests/tdd/test_3174_trip_sms_ohne_doppelpunkt.py` (AC-1 bis AC-6, echter Versandweg über `trip_briefing_aufbau` bzw. `render_line`, Placements-Ansicht über den Service, keine Mocks).
- Anzupassen: Trip-Goldens (`tests/golden/sms/`, `tests/golden/trip_briefing_aufbau/`, `tests/golden/scheduler_texte/`, `tests/fixtures/befehl_antwortzeit/golden_berichte.json`) und Testerwartungen mit `E\d+: ` bzw. `{Name}: `.

## Doku

- `docs/reference/sms_format.md` §2 (Header `{Name}`), §3.1, §5 Beispiele, §5b (Satz „Die Trip-SMS behält ihr `E3: `“), §7/§8 Pflicht-Token und Beispiele, Changelog.
- `docs/reference/premium_sms_format.md`, `docs/reference/telegram_format.md`: Beispiele, falls dort Trip-Köpfe stehen.
- ADR-0125 Nr. 2: Folge-Ticket #3174 als umgesetzt vermerken (keine neue Entscheidung, daher kein neues ADR).

## Changelog

- 2026-11-19: Erstfassung (PO-Auswahl „Beide ohne“).
