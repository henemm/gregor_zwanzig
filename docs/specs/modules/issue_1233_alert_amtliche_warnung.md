---
entity_id: issue_1233_alert_amtliche_warnung
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [alert, official-warning, compare, renderer, quiet-hours]
---

# #1233 — Amtliche Warnung: Versand-Gating + geteilter Renderer-Redesign

## Approval

- [x] Approved (PO „Go" 2026-07-12; inkl. LoC-Override auf 500)

## Purpose

Behebt drei Defekte des mit #1216 gebauten amtliche-Warnungs-Pfads, die zusammen dazu führten, dass für einen **deaktivierten** Ortsvergleich um **00:00 Uhr** eine Mail im **veralteten Format** verschickt wurde:
1. Der Ortsvergleich-Standalone-Alarm unterdrückt keine **Ruhezeiten** (Quiet Hours).
2. Er ignoriert die **Deaktivierung** eines Ortsvergleichs (`schedule == "manual"` / archiviert) und sendet trotzdem.
3. Standalone-Alarm-Mails nutzen einen **veralteten Renderer**; sie sollen auf die freigegebene Design-Vorlage „Alert · Amtliche Warnung" gehoben werden — als **von Trip und Ortsvergleich geteilter** Renderer.

## Source

- **File:** `src/services/compare_official_alert.py` — **Identifier:** `CompareOfficialAlertService._check_one_preset` (#1, #2)
- **File:** `src/output/renderers/alert/official_alerts.py` — **Identifier:** `render_official_alert_html` (#3), `_typ_tag`/`render_official_alert_subject` (Nebenbefund Wochentag)
- **Design-SOLL:** `docs/design-requests/issue_1233_alert_amtliche_warnung/Gregor 20 - Alert Amtliche Warnung.html` (+ `tokens.css`)

Schicht: **Python-Core / Domain-Backend** (`src/services/`, `src/output/renderers/`). Der 15-Min-Trigger liegt in Go (`internal/scheduler/scheduler.go:102`) und bleibt **unverändert** — das Gating gehört in den Python-Service, den der Scheduler aufruft.

## Estimated Scope

- **LoC:** ~300–380 (Renderer-Rewrite dominiert; #1/#2 ~25 LoC) → **überschreitet 250-LoC-Standardbudget**, `loc_limit_override` nötig (PO-Erlaubnis bei Freigabe).
- **Files:** 2 Quell-Dateien + Tests + Golden-Mail-Updates
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `DeviationAlertEngine.is_quiet_hours` (`src/services/deviation_alert_engine.py:72`) | Reuse | Quiet-Hours-Prüfung inkl. Mitternachts-Wrap (#1) |
| `scheduler_dispatch_service.py:47-56` | Vorbild | `schedule == "manual"`-Skip-Muster (#2) |
| `render_warn_block(variant="standalone")` (`official_alerts.py:621`) | Anschluss | Einstiegspunkt beider Pfade (Trip + Compare) für #3 |
| `notification_service.send_official_alert` / `send_multi_location_official_alert` | Konsument | Rufen den geteilten Renderer auf |
| Design-Tokens `G_ALERT_L2/L3/L4`, `--g-*` (`design_tokens.py`, `tokens.css`) | Reuse | Farben (keine hart kodierten Vorlage-Hex im Output) |

## Implementation Details

### Slice A — Versand-Gating (`compare_official_alert.py::_check_one_preset`)

Reihenfolge der Gates (früher Return, **kein** State-Record / **kein** `increment` bei Unterdrückung):

```
1. preset_id + location_ids vorhanden           (bestehend)
2. schedule == "manual"  → return False          (NEU #2)
3. archived_at gesetzt   → return False          (NEU #2)
4. official_alert_triggers_enabled == False → return False   (bestehend)
5. is_quiet_hours(now, alert_quiet_from, alert_quiet_to) → return False   (NEU #1)
6. _detect(...)  → keine neuen/eskalierten Treffer → return False   (bestehend)
7. alert_daily_limit.is_allowed(...) → sonst return False   (bestehend)
8. send → bei Erfolg: _record_state + increment   (bestehend)
```

`is_quiet_hours` = `DeviationAlertEngine.is_quiet_hours(datetime.now(timezone.utc), preset.get("alert_quiet_from"), preset.get("alert_quiet_to"))`.

### Slice B — Geteilter Renderer-Redesign (`render_official_alert_html`)

`render_official_alert_html` wird auf das SOLL-Design gehoben. Der Renderer bleibt **chip-agnostisch**: er rendert `affected_chips` (normal) + `free_chips` (durchgestrichen), egal ob diese Segmente (Trip) oder Orte (Compare) sind.

**Verbindliche Arbeitsweise (PO):**
- **1:1 übernehmen, nicht nachbauen:** Die HTML-Struktur, Klassennamen und Inline-CSS-Werte werden **direkt aus der SOLL-Vorlage** (`Gregor 20 - Alert Amtliche Warnung.html`) übernommen und nur dort angepasst, wo Werte dynamisch sind (`.verdict`, `.stufe`/`.stufe .on`, `.stufe-hint`, `.warns`/`.warn`/`.warn.stacked`, `.type`, `.facts .k`/`.mono`/`.seg`/`.seg.off`, `.route-note`, `.meter .bars i`/`.lvl`, `.src`, `.body-foot`). Keine frei erfundene Struktur.
- **Kein Duplikat, Code teilen:** Es gibt **genau einen** Standalone-Renderer. Trip (`send_official_alert`) und Ortsvergleich (`send_multi_location_official_alert`) rufen weiterhin **denselben** `render_warn_block(variant="standalone")` → `render_official_alert_html` auf. Es entsteht **keine** compare-eigene oder trip-eigene Renderer-Kopie. Gemeinsame Teilbausteine (Chip, Meter, Leiter, Validity) werden als geteilte Helfer faktoriert, nicht kopiert.

Body-Reihenfolge:

1. **Verdict-Pill** `.verdict` (rounded, farbiger bg + `.dot` in Leitstufen-Farbe): `„{N} amtliche Warnung(en)"`; bei gemischten Stufen `„ · höchste Stufe {WORT}"`.
2. **Headline** `.body-h1`, **deterministisch** aus den Warn-Typen + Scope-Wort: `„{Typen-Aufzählung} für {scope} gemeldet."` (Typen: `„A"`, `„A und B"`, `„A, B und C"`; scope aus vorhandenem `scope_label`, z.B. „deine Route" / „nur Geisbergalm (Zillertal Arena)"). Kein LLM, reine Template-Logik.
3. **Warnstufen-Leiter** `.stufe-line` **nur bei uniformer Stufe**: `.stufe-cap` „Warnstufe" + Leiter GELB/ORANGE/ROT (aktive = `on`) + `.stufe-hint` (Position: „niedrigste/mittlere/höchste von drei").
4. **Warn-Block** `.warns`: je Warnung `.warn` grid `[130px .type | .facts]`; `.facts` = „Gültig: {`.mono` Validity}" + „Route: {Chips}". Freie Chips `.seg.off` durchgestrichen. Sind freie Chips vorhanden, zusätzlich `.route-note` („übrige Strecke/Orte frei …").
5. **Gemischte Stufen**: `.warn.stacked` mit `.whead` (`.meter` Bars je Stufe + Stufenwort `{WORT} · {pos}/3` + `.type`), **keine** gemeinsame Leiter; höchste Stufe zuerst.
6. **Quelle-Box** `.src` (linker Rand `--g-info`): „Quelle: {Quelle}" + prosaischer Scope-Satz.
7. **Footer** `.body-foot`: „Stand: heute {HH:MM} · abgerufen bei {Quelle}".

Farben ausschließlich Bestands-Tokens (`G_ALERT_L2/L3/L4`, `--g-*`); Vorlage-Hex tauchen nicht hart im Output auf (Ausnahme: Dot-/Meter-Punktfarbe, wo der Token dieselbe Farbe trägt — analog embedded WarnBlock AC-8 in derselben Datei).

Telegram/SMS: an die Vorlagen-Form angleichen (Telegram fette erste Zeile; SMS GSM-7-Tokens) — Abweichungen des Bestands-Renderers zur Vorlage korrigieren.

### Nebenbefund — Betreff/Body-Wochentag konsistent

`render_official_alert_subject`/`_typ_tag` (Wochentag aus `valid_from`) und `_format_validity` (Body) müssen denselben Wochentag/dieselbe Zeitzone verwenden (aktuell „(Sa)" vs. „So 12.07."). Ursache prüfen (tz-naiv vs. tz-aware `valid_from`) und angleichen.

## Expected Behavior

- **Input:** Compare-Preset (`schedule`, `archived_at`, `alert_quiet_from/to`, `official_alert_triggers_enabled`, `location_ids`) + amtliche Warnungen je Ort; bzw. Warn-DTOs für den Renderer.
- **Output:** Mail-Versand nur, wenn Preset aktiv (nicht manual/archiviert), außerhalb Ruhezeit, Tageslimit frei; Mail-Body im SOLL-Design; Betreff/Body-Wochentag konsistent.
- **Side effects:** State-Record + Tageslimit-Increment **nur** bei tatsächlichem Versand.

## Acceptance Criteria

- **AC-1:** Given ein aktives Compare-Preset mit `alert_quiet_from`/`alert_quiet_to`, das die aktuelle Uhrzeit einschließt, und eine neue amtliche Warnung / When `_check_one_preset` läuft / Then wird **keine** Mail versendet, **kein** State aufgezeichnet und das Tageslimit **nicht** erhöht.
  - Test: Service mit Preset (quiet 22:00–06:00), gefaktem `now=00:00`, neuer Warnung; `mail_sink` bleibt leer; AlertState unverändert.

- **AC-2:** Given dieselbe (noch neue) Warnung, aber `now` **außerhalb** der Ruhezeit / When `_check_one_preset` läuft / Then wird die Mail zugestellt — die Nacht-Unterdrückung darf die Warnung nicht dauerhaft verschlucken.
  - Test: gleicher State wie AC-1, `now=09:00`; `mail_sink` erhält genau eine Mail.

- **AC-3:** Given ein Compare-Preset mit `schedule == "manual"` und einer neuen amtlichen Warnung / When `_check_one_preset` läuft / Then wird **keine** Mail versendet.
  - Test: Preset `schedule="manual"`, neue Warnung, außerhalb Ruhezeit; `mail_sink` bleibt leer.

- **AC-4:** Given ein Compare-Preset mit gesetztem `archived_at` / When `_check_one_preset` läuft / Then wird **keine** Mail versendet.
  - Test: Preset mit `archived_at`; `mail_sink` bleibt leer.

- **AC-5:** Given ein Preset mit `schedule == "daily"` (bzw. `"weekly"`), außerhalb Ruhezeit, mit neuer Warnung / When `_check_one_preset` läuft / Then wird die Mail versendet (keine Regression durch die neuen Gates).
  - Test: aktives Preset; `mail_sink` erhält eine Mail.

- **AC-6:** Given eine amtliche Warnung / When die Standalone-Mail gerendert wird / Then enthält der Body eine Verdict-Pill mit farbigem `.dot` und dem Text „{N} amtliche Warnung(en)" (bei gemischten Stufen mit „ · höchste Stufe {WORT}").
  - Test: HTML-Parse: genau eine `.verdict` mit `.dot`; Textinhalt entspricht Anzahl/Stufe.

- **AC-7:** Given Warnungen der Typen T1..Tn und ein Scope-Label / When gerendert / Then erscheint eine `.body-h1`-Headline nach fester Regel „{Typen} für {scope} gemeldet." — deterministisch, gleiche Eingabe ⇒ gleicher Text.
  - Test: zwei identische Renderläufe liefern byte-identische Headline; bekannte Eingabe ⇒ erwarteter Satz.

- **AC-8:** Given mehrere Warnungen **gleicher** Stufe / When gerendert / Then zeigt der Body die „Warnstufe"-Leiter mit der aktiven Stufe (`on`) plus Positions-Hinweis und **kein** per-Warnung-Meter.
  - Test: HTML enthält `.stufe .on` an korrekter Position; kein `.meter`.

- **AC-9:** Given Warnungen **unterschiedlicher** Stufen / When gerendert / Then trägt jede Warnung ein eigenes Eskalations-Meter (`.meter` Bars + Stufenwort), es gibt **keine** gemeinsame Leiter, und die höchste Stufe steht zuerst.
  - Test: HTML enthält je Warnung ein `.meter`; keine `.stufe`-Leiter; Reihenfolge nach Stufe absteigend.

- **AC-10:** Given eine Warnung, die nur einen Teil der Chips betrifft / When gerendert / Then stehen betroffene Chips normal und nicht betroffene Chips durchgestrichen (`.seg.off`), plus `.route-note`.
  - Test: HTML: betroffene Chips ohne `off`, freie mit `off`; `.route-note` vorhanden.

- **AC-11:** Given identische Warn-DTOs / When einmal über den Trip-Pfad (`send_official_alert`) und einmal über den Compare-Pfad (`send_multi_location_official_alert`) gerendert / Then erzeugen beide **dieselbe** Body-Struktur (ein und derselbe Renderer); der einzige Unterschied sind die Chip-Beschriftungen (Segmente vs. Orte).
  - Test: beide Pfade rendern denselben DTO-Satz → strukturgleiches HTML (gleiche Klassen/Reihenfolge).

- **AC-12:** Given eine Warnung mit `valid_from` an Tag X / When Betreff und Body gerendert werden / Then nennen beide **denselben** Wochentag (kein „(Sa)" im Betreff bei „So" im Body).
  - Test: Betreff-Wochentagskürzel == Body-Wochentag für dieselbe Warnung.

- **AC-13:** Given der gerenderte Standalone-Body / When auf hart kodierte Design-Vorlage-Hex geprüft / Then trägt die Farbgebung die Bestands-Tokens (`G_ALERT_L2/L3/L4`); Vorlage-Hex erscheinen nicht als eigenständige Text-/Flächenfarbe (nur als Dot-/Meter-Punkt, wo Token = Hex).
  - Test: Renderer nutzt Token-Konstanten (Import-/Wert-Nachweis über das gerenderte Ergebnis, nicht Quelltext-grep).

- **AC-14:** Given die gerenderte „Nachher · Email"-Standalone-Mail / When mit dem `.mail-body`-Ausschnitt der Design-Vorlage über den Fidelity-Harness verglichen / Then liegt die Abweichung unter der etablierten Pixel-/Struktur-Schwelle.
  - Test: Fidelity-Harness gegen `Gregor 20 - Alert Amtliche Warnung.html` (Sektionen „Nachher · Email", Teilstrecke, gemischte Stufen).

## Known Limitations

- Die `.body-h1`-Headline und der `.src`-Scope-Satz sind **deterministische Template-Sätze**, keine frei formulierte Prosa (kein LLM). Bei ungewöhnlichen Hazard-Kombinationen kann der Satz mechanisch klingen — akzeptiert.
- Der Go-Scheduler-Takt (`*/15`) bleibt unverändert; die Nacht-Unterdrückung passiert im Python-Service (der Scheduler feuert weiter, sendet aber nichts).
- `official_alert_triggers_enabled` bleibt als zusätzlicher, unabhängiger Opt-out bestehen; #2 ergänzt nur den `schedule`/`archived_at`-Skip (deaktivierter Vergleich).
- SMS-Fidelity wird gegen die Vorlagen-Tokenform geprüft, nicht Pixel (SMS ist Text).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reuse bestehender Muster (Quiet-Hours-Engine, Manual-Skip, geteilter `variant="standalone"`-Renderer). Keine neue Architektur; ein Renderer wird inhaltlich modernisiert, Konsumenten unverändert.

## Changelog

- 2026-07-12: Initial spec created (aus Bug-Investigation #1233, PO-Entscheidung „alle drei zusammen", Design-Import „Alert · Amtliche Warnung").
