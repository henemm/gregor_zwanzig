---
entity_id: feat_1493_gewitter_onset_sichtbar
type: feature
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.0"
tags: [thunder, trip, email, onset, issue-1493, issue-1419]
---

<!-- Issue #1493 ("Gewitter S7: Onset"), aus Epic #1419 Abschnitt 6 / S7.
     Grundlage: PFLICHTLEKTUERE docs/context/feat-1493-gewitter-onset.md,
     Abschnitt "ENTSCHEIDUNG (PO, 2026-08-17)" ist maßgeblich für den Zuschnitt
     dieser Spec — der ursprüngliche Ticket-Vorschlag (neuer Prosa-Satz-Block)
     ist verworfen. -->

# Gewitter-Stufe im Klartext sichtbar + Onset-Stunde im Ausblick (#1493)

## Approval

- [x] Approved — PO-Freigabe 2026-08-18 („go")

## Purpose

Die Gewitter-Metrik-Pille (`Gewitter ab 14:00 · stärkste 18:00 · CAPE`) nennt
heute in **allen drei** E-Mail-Renderern (HTML, Klartext, Kompakt) zwar Beginn-
und Spitzenstunde des Gewitters der Etappe dieses Briefings — die **Stufe**
(leicht/mittel/hoch) steckt dabei aber ausschließlich in der Ampelfarbe. Im
Klartext, wo Farbe nicht ankommt, ist die Stufe faktisch unsichtbar. Diese
Spec macht das Stufenwort zum Text-Bestandteil der Pille.

Zusätzlich fehlt im **mehrtägigen Ausblick** ("Nächste Etappen") die
Onset-Stunde im Klartext- und im Kompakt-Format — beide zeigen nur das
Stufenwort (`⚡mittel`), während die HTML-Ausblickstabelle sie längst führt
(`mittel @14`). Diese Uneinheitlichkeit ist aus Nutzersicht nicht erklärbar
und wird hier behoben.

Kein neuer Prosa-Block: Ein ursprünglich für dieses Ticket vorgesehener Satz
"Gewitter wahrscheinlich ab 14:00" entfällt, weil die Aussage in der Pille
bereits existiert — ein zweiter Block wäre die Dopplung, die der PO
ausdrücklich ausschließt (siehe „PO-Entscheid" unten).

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core
> (`src/output/renderers/email/`). Kein Frontend, keine Go-Beteiligung, keine
> neuen Endpoints, keine neuen Persistenz-Felder. Telegram
> (`renderers/narrow.py`) und SMS (`tokens/builder.py`) werden **nicht**
> angefasst — sie führen die Onset-Stunde bereits.

- **File:** `src/output/renderers/email/helpers.py`
  - **Identifier:** `_pill_for_metric()`, Zweig `metric_id == "thunder"`
    (Zeile ~1766–1780) — Rückgabe-String bekommt das Stufenwort vor
    `ab {first_hh:02d}:00`.
- **File:** `src/output/renderers/email/outlook.py`
  - **Identifier:** `render_outlook_plain()` / `_outlook_lines()`, Zeile
    ~370–378 — `thunder_word = f"⚡{_dm[0]}{_dm[2]}"` liest künftig zusätzlich
    `_dm[1]` (die von `_thunder_token_parts()` bereits gelieferte, aber bisher
    verworfene Onset-Stunde).
- **File:** `src/output/renderers/email/compact.py`
  - **Identifier:** `_compact_thunder_field()`, Zeile ~101–103 — dieselbe
    Ergänzung für den Tagesteil der Kompakt-Ausblickzeile.

## Estimated Scope

- **LoC:** ~+40/-10 produktiv, plus Tests (weit unter dem Workflow-Limit 250)
- **Files:** 3 Produktivdateien, 1 Bestandstest, 1 Golden-Fixture, 1 neue
  TDD-Datei, 2 Fremd-Specs (Ablöse-Vermerk, zählt nicht als Code-LoC)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `THUNDER_LABEL_DE` (`src/output/metric_format.py:246-251`) | dict (SSoT) | Deutsche Stufenwörter kein/leicht/mittel/hoch — **einzige** erlaubte Quelle für das neue Stufenwort in der Pille (#1480: keine lokale Kopie) |
| `_TREND_THUNDER_LABELS` (`helpers.py:989`) | dict | Dieselben Wörter, bereits im Klartext-Ausblick über `format_trend_tokens()` genutzt — Referenz für Konsistenz, nicht direkt aufgerufen |
| `_thunder_token_parts()` (`thunder_branch.py:30-51`) | Funktion | Liefert bereits `(Wort, Stunde-als-String, Peak-Zusatz)` für Klartext/Kompakt-Ausblick — Element 1 (Stunde) wird ab dieser Spec verbaut statt verworfen |
| `resolve_thunder_day_branch()` (`thunder_branch.py:54-79`) | Funktion | Geteilte Zweigwahl Tag/Nacht — unverändert, nur der Formatierungs-Aufruf danach ändert sich |
| `thunder_ampel_band()` | Funktion | Liefert die Ampelfarbe der Pille — unverändert, bleibt Ton-Träger zusätzlich zum neuen Wort |
| `format_trend_tokens()` (`helpers.py:994-1015`) | Funktion | **Wird NICHT angefasst** — geteilt mit Ortsvergleich, SMS und Telegram; jede Änderung dort würde diese Kanäle mitverändern. Diese Spec ändert ausschließlich die beiden Verbraucher, die die von dort gelieferte Stunde bisher wegwerfen |

## Implementation Details

**1. Stufenwort in der Pille** (`helpers.py`, Zweig `thunder`): Der bestehende
Rückgabe-String

```
f"Gewitter ab {first_hh:02d}:00 · stärkste {peak_hh:02d}:00{_origin_suffix}{_hail_suffix}"
```

bekommt das Stufenwort aus `THUNDER_LABEL_DE[max_lvl]` vor `ab {first_hh:02d}:00`
eingefügt (z. B. `Gewitter mittel ab 14:00 · stärkste 18:00 · CAPE`). Diese
Funktion beliefert alle drei E-Mail-Renderer (`plain.py:205`, `html.py:1432`,
`compact.py:176`) — eine Änderung hier wirkt automatisch auf HTML **und**
Klartext-Pille, ohne dass die drei Aufrufer selbst angefasst werden müssen.
Damit wird zugleich die CLAUDE.md-Leitlinie erfüllt: „was in HTML durch Farbe
getragen wird, muss im Klartext als Wort dastehen" (Design-Leitprinzipien,
PO-bestätigt 2026-05-25).

**2. Onset-Stunde im Klartext-Ausblick** (`outlook.py:372`): minimaler Diff

```
thunder_word = f"⚡{_dm[0]}{_dm[2]}"        # vorher
thunder_word = f"⚡{_dm[0]}@{_dm[1]}{_dm[2]}"  # nachher
```

`_dm[1]` ist bereits vorhanden (von `_thunder_token_parts()` geliefert), wird
aktuell nur nicht gelesen. Der Kommentar „der Klartext führt wie bisher keine
Tagesuhrzeit (AC-2)" bei dieser Zeile entfällt — siehe Abschnitt „Abzulösende
Zusicherungen".

**3. Onset-Stunde im Kompakt-Ausblick** (`compact.py:103`): analoge Änderung
im Tagesteil von `_compact_thunder_field()`:

```
field = f"⚡{_d[0]}{_d[2]}"        # vorher
field = f"⚡{_d[0]}@{_d[1]}{_d[2]}"  # nachher
```

Der Nachtteil (`_n[0]`/`_n[1]`) trägt die Uhrzeit bereits heute
(`f" · nachts {_n[0]} @{_n[1]}{_n[2]}"`) — nach dieser Änderung führen Tag-
und Nachtteil erstmals dieselbe Grammatik.

**Kein Prosa-Block:** `plain.py`, `html.py` und `compact.py` werden an ihren
Einhänge-Stellen **nicht** verändert — es entsteht keine neue Funktion
`build_thunder_onset_hint()` und keine neue Aufruf-Stelle.

## Expected Behavior

- **Input:** Trip-Briefing mit ausgewählter Metrik „Gewitter" (Pille) bzw.
  eine oder mehrere künftige Etappen mit Stundenreihe (Ausblick); Stufe je
  Stunde bereits über `thunder_level_from_signals()` berechnet.
- **Output:** Metrik-Pille (HTML + Klartext) nennt Stufe **und** Beginn-/
  Spitzenstunde als Text. Klartext- und Kompakt-Ausblickzeile nennen
  Stufenwort **und** Onset-Stunde (`⚡mittel@14`), analog zur bereits
  bestehenden HTML-Ausblickszelle (`mittel @14`).
- **Side effects:** Golden-Fixtures für den mehrtägigen Klartext-Ausblick
  ändern sich (erwartet, siehe „Known Limitations"). Telegram- und
  SMS-Ausgabe bleiben zeichengleich zum Vor-#1493-Stand.

## Abzulösende Zusicherungen (PFLICHT)

Zwei bestehende, freigegebene Specs enthalten Acceptance Criteria, die durch
diese Änderung wörtlich falsch werden. Beide Dateien bekommen im Zuge der
Implementierung (docs-only, zählt nicht gegen das LoC-Limit) einen
Ablöse-Vermerk nach dem in `docs/specs/modules/fix_1660b_sms_token_wiring.md`
Zeile 398 etablierten Muster (`⚠️ Abgelöst durch #NNNN … Ursprünglicher
Wortlaut zur Historie: „…"`), nicht durch stilles Überschreiben:

1. **`docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md`**
   - **AC-2** (Zeile 118-121): „… der Klartext führt wie bisher keine
     Tagesuhrzeit" — wird durch #1493 abgelöst. Der Herkunfts-Zusatz
     (`· CAPE`) bleibt unverändert bestehen, ausschließlich die Aussage „ohne
     Tagesuhrzeit" fällt weg.
   - **AC-13** (Kompakt-Ausblick bleibt zeichengleich zur HTML-Zelle ohne
     Uhrzeit) — dieselbe Ablösung, für den Kompakt-Kanal.
2. **`docs/specs/modules/fix_1671_kompaktmail_ausblick_tagesfenster.md`**
   - Abschnitt „Vom PO entschieden (2026-08-14)", Punkt 1 (Zeile 156-168):
     hält ausdrücklich fest, dass AC-13 aus `feat_1680_s5a` „bewusst NICHT
     abgeloest" wird und „eine Ablösung von AC-13 wäre ein eigenes Ticket"
     wäre. #1493 **ist** dieses Ticket — der Vermerk muss auf „abgelöst durch
     #1493" umgestellt werden, nicht stillschweigend widersprochen bleiben.

Der bestehende Wächter `tests/tdd/test_thunder_origin_outlook.py::test_ac13_kompaktmail_bleibt_zeichengleich`
(referenziert in `fix_1671`) prüft nur die **Herkunfts-Abwesenheit**
(`· CAPE`/`· Wind` etc. fehlt im Kompakt-Ausblick) — das bleibt unverändert
bestehen und wird von #1493 **nicht** berührt; nur die Uhrzeit-Aussage in der
Prosa der Spec ändert sich.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Briefing im Format „full" mit ausgewählter Metrik
  „Gewitter" und einer Etappe, deren höchste Gewitterstufe im Tagesfenster
  „mittel" mit Beginn 14:00 Uhr und Spitze 18:00 Uhr ist / When der Empfänger
  die HTML-E-Mail öffnet / Then liest er in der Gewitter-Kachel das Wort
  „mittel" ausgeschrieben (z. B. „Gewitter mittel ab 14:00 · stärkste
  18:00 · CAPE"), nicht nur eine farbige Kachel ohne Stufenwort.
  - Test: Briefing mit Fixture-Etappe (definierte Stufenfolge) rendern,
    Kachel-Text aus dem HTML-Teil extrahieren, auf das Stufenwort prüfen —
    Verhalten aus Empfängersicht, nicht Dateiinhalt-Grep.

- **AC-2:** Given dasselbe Briefing wie AC-1 / When der Empfänger stattdessen
  die Klartext-Ansicht der Mail liest (z. B. Screenreader oder
  Plaintext-Client) / Then liest er dieselbe Stufenaussage „mittel" in der
  Gewitter-Zeile — die Information ist dort nicht mehr ausschließlich über
  Farbe codiert, die im Klartext gar nicht ankommt.
  - Test: dasselbe Briefing, Klartext-Teil der Mail prüfen, Stufenwort muss
    vorkommen (Regressionsschutz gegen „nur HTML gefixt").

- **AC-3:** Given eine künftige Etappe im mehrtägigen Ausblick mit
  Tagesgewitter ab Stunde 14 Uhr / When der Empfänger den Klartext-Ausblick
  „Nächste Etappen" liest / Then sieht er in der Gewitterspalte dieser Zeile
  die Uhrzeit direkt neben dem Stufenwort (`⚡mittel@14`), nicht nur das Wort
  ohne jede Zeitangabe.
  - Test: Mehrtages-Fixture mit Etappe X (Onset 14 Uhr) rendern, Ausblickzeile
    im Klartext-Teil auf das Muster `⚡mittel@14` prüfen.

- **AC-4:** Given dieselbe Etappe wie AC-3 / When der Empfänger die
  Kompakt-Mail liest (`X-GZ-Format: compact`) / Then sieht er dieselbe
  Onset-Stunde in der Gewitterspalte der Ausblickzeile, im selben Format wie
  im Klartext-Ausblick.
  - Test: Kompakt-Briefing derselben Fixture rendern, Ausblickzeile auf
    `⚡mittel@14` prüfen.

- **AC-5:** Given ein Trip mit derselben Etappenfolge wie AC-1/AC-3 / When
  Telegram-Trendblock und SMS-Trip-Briefing für dieselbe Etappe erzeugt
  werden / Then bleibt deren Text zeichengleich zum Stand vor #1493
  (`⚡mittel@14(hoch@18)` bzw. `TH:M@14(H@18)`) — kein Kanal, der die
  Onset-Stunde bereits führte, ändert sich sichtbar.
  - Test: Bestehender Telegram-/SMS-Regressionstest bleibt ohne Anpassung
    grün — expliziter Diff-Vergleich Vorher/Nachher auf denselben Fixtures.

- **AC-6:** Given eine Etappe ohne jedes Gewitter im Tagesfenster / When der
  Empfänger Pille und Ausblick derselben Mail liest / Then zeigen beide
  weiterhin „kein Gewitter" — ohne erfundenes Stufenwort und ohne eine
  Uhrzeit, die es mangels Ereignis nicht geben kann.
  - Test: Fixture ohne Gewitterstunden rendern, Pille und Ausblickzeile auf
    exakt „kein Gewitter" (kein `@`, kein Stufenwort außer „kein") prüfen.

- **AC-7:** Given eine Zieletappe mit Datenlücke zwischen Ankunft und 19 Uhr
  (`has_gap=True`, Ziel-Beobachtungslücke #1331) / When der Empfänger die
  Pille liest / Then zeigt sie weiterhin „Gewitter ?" — die Datenlücke wird
  nicht durch das neue Stufenwort in eine positive Entwarnung verwandelt.
  - Test: Fixture mit `has_gap=True` und leerer Zielstundenreihe rendern,
    Pillentext auf „Gewitter ?" prüfen (keine Stufe, kein `ab HH:00`).

- **AC-8:** Given ein reales Trip-Briefing wird über den Produktionspfad
  (Staging, `X-GZ-Mail-Type: trip-briefing`) tatsächlich per E-Mail versendet
  / When die Mail per IMAP aus dem Staging-Test-Postfach abgeholt und
  geöffnet wird / Then enthält sowohl die Pille als auch die Ausblickzeile
  die unter AC-1/AC-3 beschriebenen Inhalte — der Nachweis entsteht am
  fertigen, tatsächlich zugestellten Produkt, nicht nur am isolierten
  Renderer-Baustein.
  - Test: `uv run python3 .claude/hooks/briefing_mail_validator.py` gegen
    echte, zugestellte Staging-Mail (`gregor-test@henemm.com`, `GZ_IMAP_*`)
    — Exit 0 UND manuelle/skriptgestützte Sichtprüfung von Stufenwort und
    Onset-Stunde im abgeholten Klartext-Teil.

## Known Limitations / Risks

- **Renderer-Commit-Gate #811** (`.claude/hooks/renderer_mail_gate.py:42-48`):
  erfasst alle `src/output/renderers/email/*.py`; `helpers.py` fällt
  zusätzlich unter `_SHARED_HELPER_PATTERNS` und verlangt formal auch den
  Compare-Nachweis. Verifiziert (Grep, 2026-08-17): `compare_html.py` ruft
  `_pill_for_metric()` **nicht** auf (nur `build_origin_footer`/
  `render_origin_footer_html` aus `helpers.py`) — der Ortsvergleich ist von
  dieser Änderung inhaltlich nicht betroffen. Der Compare-Nachweis im Gate
  ist trotzdem Pflicht, weil das Gate dateibasiert und nicht aufrufbasiert
  greift; die Erwartung ist ein unveränderter Compare-Mail-Output.
- **`briefing_mail_validator.py`-Heuristik:** `_check_plausibility()`
  (Zeile 484-505) reklamiert `HH:00`-Stunden außerhalb 06–22 im HTML-Teil.
  Das Tagesfenster der Metrik-Pillen ist aber 04–19 (ADR-0025) — ein sehr
  früher Onset (04:00/05:00) könnte in der Pille (die bereits heute
  `ab HH:00` im `HH:00`-Format schreibt) einen Fehlalarm auslösen. Die neue
  Ausblick-Notation `@HH` (ohne `:00`) trifft das Muster `_HOUR_RE`
  voraussichtlich nicht, ist aber nicht auf Nummer sicher geprüft. Muss in
  der Implementierungsphase mit einer 04-/05-Uhr-Fixture gegen den Validator
  gemessen werden, bevor „E2E bestanden" behauptet wird.
- **Anzupassender Bestandstest:**
  `tests/tdd/test_thunder_origin_outlook.py::test_ac2_klartext_ausblick_traegt_denselben_zusatz`
  (Zeile 325-334) assertiert wörtlich „ohne Tagesuhrzeit, wie bisher" — muss
  auf die neue Erwartung (`⚡leicht@16 · CAPE`) umgestellt werden, nicht
  stillschweigend grün bleiben.
- **Golden-Fixture:** `tests/golden/email/outlook-thunder-day-night.txt`
  Zeilen 5-7 zeigen aktuell `⚡mittel · nachts hoch @0` bzw.
  `⚡hoch · nachts mittel @22` ohne Tagesuhrzeit. Regeneration ausschließlich
  über `tests/golden/email/regenerate.py`, **erst nach** inhaltlicher Prüfung
  der neuen Zeilen (z. B. `⚡mittel@14 · nachts hoch @0`) — nie blind
  committen.
- **Kein Frontend-/Go-Bezug:** weder `internal/` noch `frontend/` parsen den
  Gewitter-Text oder das Token-Format; keine Migration nötig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Ausgabe-Text-Erweiterung innerhalb einer bereits
  etablierten, geteilten Zerlegungsfunktion (`_thunder_token_parts()`,
  #1671/#1653) und einer bereits etablierten Wortliste (`THUNDER_LABEL_DE`,
  #1474). Keine neue Datenquelle, kein neuer Kanal, kein neues Datenmodell,
  kein Provider-Wechsel — keine der in CLAUDE.md genannten
  Entscheidungsflächen ist betroffen.

## Changelog

- 2026-08-17: Initial spec created
