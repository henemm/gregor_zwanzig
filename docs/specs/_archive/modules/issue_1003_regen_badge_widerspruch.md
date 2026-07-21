---
entity_id: issue_1003_regen_badge_widerspruch
type: bugfix
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
tags: [email, briefing, regen, badge, bugfix]
workflow: fix-1003-regen-badge-schwelle
---

# Regen-Badge widerspricht Stundentabelle (Issue #1003 / Duplikat #1126)

## Approval

- [ ] Approved

## Purpose

Das Metriken-Überblick-Badge im Trip-Briefing (E-Mail, HTML) zeigt für Etappen mit dünn über
mehrere Stunden verteiltem Regen (Tagessumme > 0, aber keine Einzelstunde erreicht die
SMS-Erwähnungsschwelle von 0,2 mm/h) pauschal „kein Regen" — obwohl die Stundentabelle derselben
Etappe eine Regensumme > 0 ausweist. Dieser Widerspruch verwirrt Leser bei tourenrelevanten
Wetterentscheidungen. Der Fix korrigiert ausschließlich den Fallback-Zweig, der die bereits
berechnete Tagessumme bisher verwirft.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `def _pill_for_metric(...)`, Zweig `if metric_id == "precipitation":` (Zeilen ca. 1173-1188)

Schicht: Python-Core / Domain-Backend (E-Mail-Renderer, `src/output/renderers/email/`).

## Estimated Scope

- **LoC:** ~10 (+8/-2)
- **Files:** 2 (1 Source + 1 Test)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_sms_mention_threshold()` (`helpers.py:967`) | uses | Liefert die Erwähnungsschwelle (0,2 mm/h) je Metrik-ID aus `builder.DEFAULTS`. Wird gelesen, NICHT verändert. |
| `builder.DEFAULTS["R"]` (`src/output/tokens/builder.py:59`) | reads | Quelle des Schwellenwerts 0,2 mm. |
| `_first_and_peak()` (`helpers.py:990-1004`) | uses | Findet erste Stunde mit `v >= threshold`; liefert `None` wenn keine Einzelstunde die Schwelle erreicht — Trigger für den Fallback-Zweig. |
| `ampel_stage_tone()` | uses | Liefert den Ton (Ampelfarbe) für das Badge, bleibt unverändert im Aufruf. |
| `briefing_mail_validator.py` | verifies | Plausibilitäts-Check (Renderer-Commit-Gate #811), der den Bug ursprünglich in #1003/#1126 gegen echt zugestellte Staging-Mails aufgedeckt hat. Muss nach dem Fix erneut grün laufen. |
| `tests/tdd/test_issue_795_briefing_quality.py` | reference | Bestehendes Testfixture-Muster für Regen-Testdaten (Zeile ~69-116), wiederverwendbar für die neuen RED-Tests. |

## Implementation Details

Im Fallback-Zweig von `_pill_for_metric()` (`precipitation`), der aktuell bei `fp is None`
unbedingt `return ("kein Regen", tone)` liefert, wird vor dem Fallback zusätzlich geprüft, ob die
bereits berechnete Tagessumme `total` nach Rundung auf eine Nachkommastelle größer als 0 ist:

- `round(total, 1) > 0` (NICHT `total > 0` — sonst entsteht der gleiche Widerspruch in
  umgekehrter Richtung bei Restwerten, die auf 0,0 runden, z. B. 0,04 mm).
  - Text: `f"Regen ges. {total_str} mm"`, wobei `total_str` mit demselben Format wie im
    bestehenden Threshold-Zweig gebildet wird: `f"{total:.1f}".rstrip("0").rstrip(".")`
    (siehe bestehende Zeile ~1186).
  - `tone` bleibt unverändert aus `ampel_stage_tone(peak_val, ...)` (bereits vor dem Fallback
    berechnet, Zeile ~1181).
- `round(total, 1) == 0`: weiterhin `return ("kein Regen", tone)` — echter Nullfall, kein
  Widerspruch zur Tabelle möglich, da diese ebenfalls mit `.1f` rundet.

Betroffen ist ausschließlich dieser eine Zweig (`precipitation`-Fallback). Die Erwähnungsschwelle
selbst (`_sms_mention_threshold`, geteilte Quelle mit dem SMS-Format, Issue #795/RC0) wird NICHT
verändert — reiner Fallback-Text-Fix, keine Schwellenanpassung.

## Expected Behavior

- **Input:** Segment-Stundenwerte (`all_dps`) einer Etappe mit `precip_1h_mm`-Werten, keine
  Einzelstunde erreicht die 0,2mm-Erwähnungsschwelle.
- **Output:**
  - Tagessumme > 0 (gerundet auf `.1f`): Badge-Text `"Regen ges. X mm"` statt `"kein Regen"`.
  - Tagessumme == 0 (gerundet auf `.1f`): unverändert `"kein Regen"`.
- **Side effects:** Keine. Nur der Rückgabetext des Fallback-Zweigs ändert sich; `tone`-Berechnung,
  Aufrufreihenfolge und alle anderen Metrik-Zweige (`wind`, `gust`, `rain_probability`) bleiben
  unangetastet.

## Acceptance Criteria

- **AC-1:** Given eine Etappe mit über mehrere Stunden dünn verteiltem Regen (Tagessumme > 0,
  z. B. 0,1 mm + 0,1 mm = 0,2 mm gesamt, aber keine Einzelstunde erreicht die 0,2mm-Schwelle
  einzeln, weil z. B. 0,1+0,1 als zwei separate Unter-Schwellen-Werte vorliegen oder eine
  Randwert-Kombination die Einzelstunden-Prüfung nicht auslöst) / When das Trip-Briefing als
  echte E-Mail an das Staging-Testpostfach zugestellt wird / Then zeigt das Metriken-Badge den
  Text „Regen ges. X mm" (X = gerundete Tagessumme) statt „kein Regen".
  - Test: Echte, an `gregor-test@henemm.com` zugestellte Trip-Briefing-Mail (Staging) für eine
    Testtour mit präparierten Regen-Rohdaten (Summe > 0, keine Einzelstunde ≥ 0,2 mm) wird per
    IMAP abgerufen und mit `briefing_mail_validator.py` sowie einer gezielten pytest-Prüfung des
    tatsächlich gerenderten Badge-Textinhalts verifiziert — kein reiner
    `assert 'text' in datei.read_text()`-Check, sondern Prüfung des über den echten Rendering-Pfad
    (`_pill_for_metric` innerhalb der vollständigen E-Mail-Erzeugung) erzeugten und zugestellten
    Inhalts.

- **AC-2:** Given eine Etappe ohne jeglichen Regen (kein einziger Datenpunkt mit
  `precip_1h_mm > 0`) / When das Trip-Briefing gerendert und als echte E-Mail zugestellt wird /
  Then zeigt das Metriken-Badge weiterhin „kein Regen" (kein Regress gegenüber dem bisherigen
  Verhalten).
  - Test: Echte, zugestellte Trip-Briefing-Mail (Staging, IMAP-Abruf) für eine Testtour mit
    durchgehend `precip_1h_mm == 0.0` wird geprüft; der Badge-Text muss unverändert „kein Regen"
    lauten. Kein Dateiinhalt-Check — Prüfung des tatsächlich zugestellten Mail-Inhalts.

- **AC-3:** Given eine Etappe, deren Regensumme exakt auf 0,0 rundet (z. B. mehrere Stunden mit
  minimalen Restwerten wie 0,02 mm + 0,02 mm = 0,04 mm gesamt, `round(0.04, 1) == 0.0`) / When das
  Trip-Briefing gerendert und zugestellt wird / Then zeigt das Badge weiterhin „kein Regen" (kein
  neuer Widerspruch in umgekehrter Richtung — Text und Tagessumme stimmen überein, da beide auf
  0,0 runden).
  - Test: Echte, zugestellte Trip-Briefing-Mail (Staging, IMAP-Abruf) für eine Testtour mit
    Regen-Restwerten, deren Summe exakt auf 0,0 rundet, wird geprüft; der Badge-Text muss „kein
    Regen" lauten, nicht „Regen ges. 0.0 mm". Kein Dateiinhalt-Check.

- **AC-4:** Given eine Etappe mit mindestens einer Einzelstunde ≥ 0,2 mm Regen (bestehender
  Threshold-Fall) / When das Trip-Briefing gerendert und zugestellt wird / Then zeigt das Badge
  unverändert das bestehende Format „Regen ab HH:00 · X mm" (Regressionsschutz — der Fix darf den
  bereits funktionierenden Threshold-Zweig nicht verändern).
  - Test: Echte, zugestellte Trip-Briefing-Mail (Staging, IMAP-Abruf) für eine Testtour mit einer
    Einzelstunde ≥ 0,2 mm wird geprüft; der Badge-Text muss weiterhin dem Format „Regen ab HH:00 ·
    X mm" entsprechen. Kein Dateiinhalt-Check.

## Known Limitations

- Die SMS-Erwähnungsschwelle (`_sms_mention_threshold`, aktuell 0,2 mm/h aus
  `builder.DEFAULTS["R"]`) bleibt unverändert — sie ist die geteilte Quelle für das SMS-Format
  (Issue #795/RC0) und wird bewusst nicht angetastet. Der Fix behebt ausschließlich den
  Text-Fallback, nicht die zugrundeliegende Erwähnungslogik.
- **Korrektur (Adversary-Finding F001):** Der Plain-Text-Renderer (`plain.py`) ruft
  `_pill_for_metric()` sehr wohl über `build_metrics_summary_pills()` auf — der Fix wirkt also
  identisch auf HTML- UND Plain-Text-Badge (kein Divergenz-Risiko zwischen den beiden Formaten,
  bestätigt durch `test_plain_shows_sum_not_kein_regen`). Ursprüngliche Analyse ging hier fälschlich
  von getrennten Codepfaden aus. Der SMS-Renderer (`sms_trip.py`) ist weiterhin NICHT betroffen —
  eigener, unabhängiger Codepfad ohne `_pill_for_metric()`-Aufruf, außerhalb dieses Scopes.
- Die Stundentabelle (`html.py`) ist bereits korrekt (zeigt Rohwerte ohne Schwellenlogik) und wird
  durch diesen Fix nicht verändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix am Fallback-Zweig einer bestehenden Funktion (`_pill_for_metric`,
  `precipitation`-Zweig). Es wird keine neue Architektur-Entscheidung getroffen, keine Schnittstelle
  geändert und keine neue Abhängigkeit eingeführt — die bereits vorhandene Tagessumme (`total`)
  wird lediglich im bisher verworfenen Fallback-Fall genutzt.

## Changelog

- 2026-07-08: Initial spec created
