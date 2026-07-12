# Kontext: fix-1233-compare-official-alert

**Issue:** #1233 — E-Mail: Amtliche Warnung — Uhrzeit, Inhalt
**Workflow:** fix-1233-compare-official-alert
**Track:** Full Process (Bug-Investigation → 3-teiliger Fix inkl. Renderer-Redesign)

## Symptom (aus Nutzersicht)

Eine amtliche-Warnung-Mail ging um **00:00 Uhr** an das eigene Postfach:
- Betreff: `[Zillertal] nur Geisbergalm (Zillertal Arena) · GELB Hitze (Sa) + Hitze (Sa) + Hitze (Sa) + Hitze (Sa)`
- Body: „4 amtliche Warnungen", je Block eine `Route:`-Zeile im Durchstreich-Format
- `Stand: heute 00:00`
- Der zugrundeliegende Ortsvergleich **war deaktiviert** und hätte nichts senden dürfen.

## Ursachen (belegt, drei getrennt)

### #1 — Versand um 0:00 (fehlende Quiet Hours)
`src/services/compare_official_alert.py::_check_one_preset` (Zeilen 66–99) prüft **keine Ruhezeiten**.
Alle Schwester-Pfade tun es:
- Trip-Standalone: `src/services/trip_alert.py:952` (`self._is_quiet_hours(trip, now)`)
- Compare-Δ: `src/services/compare_alert.py:200-201` (`alert_quiet_from`/`alert_quiet_to`)
- Compare-Radar-Onset: `src/services/compare_radar_alert.py:103-109` (`DeviationAlertEngine.is_quiet_hours(...)`)

Reuse-Vorbild (exakt): `compare_radar_alert.py:103-109`:
```python
if DeviationAlertEngine.is_quiet_hours(
    datetime.now(timezone.utc),
    preset.get("alert_quiet_from"),
    preset.get("alert_quiet_to"),
):
    return False
```
`DeviationAlertEngine.is_quiet_hours` (`src/services/deviation_alert_engine.py:72`) behandelt Mitternachts-Wrap. Preset-Felder `alert_quiet_from`/`alert_quiet_to` existieren (`internal/model/compare_preset.go:59-60`, Python liest sie via `preset.get(...)`).

Wichtig: Der frühe Return **vor** `_record_state`/`increment` — d.h. keine State-Aufzeichnung bei Unterdrückung → nach Ende der Ruhezeit wird dieselbe (noch neue) Warnung zugestellt. Genau das Trip-/Radar-Verhalten.

Der 15-Minuten-Scheduler (`internal/scheduler/scheduler.go:102`, `*/15 * * * *`) feuert auch um 00:00 → ohne Quiet-Hours-Gate geht die Mail nachts raus.

### #2 — Deaktivierter Ortsvergleich sendet trotzdem
Der Nutzer deaktiviert einen Ortsvergleich, indem er `schedule` auf `"manual"` setzt (`previous_schedule: "daily"`). Der amtliche-Warnungs-Pfad **ignoriert `schedule` komplett** — er prüft nur `official_alert_triggers_enabled` (Default `True`; auf dem alten Preset nie gesetzt → sendet).
- Fehlstelle: `compare_official_alert.py:71` (nur Flag-Check), `_load_presets` (168–177) lädt alle Presets ungefiltert.
- Vorbild für Skip: `src/services/scheduler_dispatch_service.py:47-56` (Report-Pfad überspringt `manual`).
- Betroffenes Preset: `data/users/henning/compare_presets.json` → `id: "zillertal"`, `schedule: "manual"`, `previous_schedule: "daily"`, `empfaenger: []` (Fallback auf `settings.mail_to`).

PO-Entscheidung: „deaktivierter Ortsvergleich" = keinerlei automatischer Versand. Also skip bei `schedule == "manual"` (und bei gesetztem `archived_at`).

### #3 — Format veraltet (Renderer-Redesign, geteilt Trip+Ortsvergleich)
Standalone-Alarm-Mails (Trip via `notification_service.py:511` UND Ortsvergleich via `notification_service.py:608`) nutzen `render_warn_block(variant="standalone")` → den alten `render_official_alert_html` (`src/output/renderers/alert/official_alerts.py:402-459`). Dieser ist bewusst als „Bestandsschutz" alt gehalten (Docstring `official_alerts.py:640-643`).

**SOLL-Design:** `docs/design-requests/issue_1233_alert_amtliche_warnung/Gregor 20 - Alert Amtliche Warnung.html` (+ `tokens.css`).
Der Renderer soll auf dieses Design gehoben werden — **geteilt** von Trip (Chips = Segmente) und Ortsvergleich (Chips = Orte). Beide rufen bereits denselben `variant="standalone"` auf; wir werten diesen einen Renderer auf.

SOLL-Bausteine (Email-Body, in Reihenfolge):
1. `.verdict`-Pill (rounded, farbiger bg + `.dot`): „N amtliche Warnung(en)"; bei gemischten Stufen `· höchste Stufe {WORT}`.
2. `.body-h1` prosaische Headline, deterministisch aus Warn-Typen + Scope (z.B. „Hitze und Gewitter für deine Route gemeldet."). — Deterministische Regel, KEIN LLM.
3. `.stufe-line` (nur bei **uniformer** Stufe): `.stufe-cap` „Warnstufe" + Leiter GELB/ORANGE/ROT (aktive Stufe `on`) + `.stufe-hint` („niedrigste/höchste von drei" je nach Position).
4. `.warns`-Box, je Warnung `.warn` grid [130px `.type` | `.facts`]; `.facts` mit „Gültig:" (`.mono`) + „Route:" Chips (`.seg`, frei = `.seg.off` durchgestrichen). Bei nur-Teilstrecke zusätzlich `.route-note`.
5. Bei **gemischten** Stufen: `.warn.stacked` mit `.whead` (`.meter` Bars je Stufe + `.type`), KEINE gemeinsame Leiter.
6. `.src`-Box (linker Rand `--g-info`): „Quelle: …" + prosaischer Scope-Satz.
7. `.body-foot`: „Stand: heute {HH:MM} · abgerufen bei {Quelle}".

Telegram/SMS-Angleichung analog der Vorlage (fette erste Zeile Telegram; GSM-7-Tokens SMS — bereits weitgehend vorhanden via `render_official_alert_telegram`/SMS-Renderer; Abweichungen zur Vorlage angleichen).

Farb-Tokens: Bestands-Tokens `G_ALERT_L2/L3/L4` / `--g-*` (PO 2026-07-11), NICHT die Design-Vorlage-Hex hart im Output (analog embedded WarnBlock AC-8 in derselben Datei).

**Nebenbefund (in #3 mitnehmen):** Betreff zeigt Wochentag aus `valid_from` via `_typ_tag` („(Sa)"), Body via `_format_validity` („So 12.07."). Diskrepanz Sa/So im selben Versand → einheitliche Zeit-/Wochentags-Quelle prüfen und angleichen.

## Betroffene Dateien
- `src/services/compare_official_alert.py` — #1 Quiet-Hours-Gate, #2 schedule/archived-Skip
- `src/output/renderers/alert/official_alerts.py` — #3 `render_official_alert_html` Redesign (+ ggf. Betreff `_typ_tag` Nebenbefund)
- Ggf. `src/services/notification_service.py` — nur falls Renderer-Signatur (Scope-Prosa/Headline) neue Parameter braucht; sonst unberührt
- Tests: `tests/tdd/` (Repro #1+#2), Golden-Mail-Tests (`tests/golden/email/`), Fidelity-Harness gegen die Design-HTML

## Gates / Constraints
- **Renderer-Commit-Gate #811** (`renderer_mail_gate.py`): `official_alerts.py` = Radar/Alert-Pfad → Mail-Validator-Lauf + Test grün vor Commit.
- **LoC-Budget 250** wird überschritten (Renderer-Rewrite) → PO-Erlaubnis für `loc_limit_override` bei Freigabe.
- Kein Mock-Theater; Repro-Tests aus Nutzersicht (rot vor Fix, grün nach Fix).
- Mandantenfähigkeit: `user_id` durchreichen, nie `"default"`-Fallback.

## Vorschlag Implementierungs-Slices (eine Ausgabe, ein Issue)
- **Slice A (Sicherheit):** #1 Quiet-Hours + #2 schedule/archived-Skip in `compare_official_alert.py` + Repro-Tests.
- **Slice B (Format):** #3 geteilter Renderer-Redesign + Fidelity + Golden-Update + Betreff-Nebenbefund.
Beide unter #1233, zusammen ausgeliefert.
