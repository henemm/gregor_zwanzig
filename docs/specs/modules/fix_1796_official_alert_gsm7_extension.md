---
entity_id: fix_1796_official_alert_gsm7_extension
type: bugfix
created: 2026-08-13
updated: 2026-08-13
status: draft
version: "1.0"
tags: [sms, gsm7, alert, bugfix]
---

# GSM-7-Extension-Zeichen im Trip-Namen für amtliche Alarm-SMS filtern

## Approval

- [ ] Approved

## Purpose

GSM-7-Extension-Zeichen (`^{}[]~|\€` sowie Form-Feed `\x0c`) im Trip-Namen
werden von `_ascii()` nicht gefiltert und lösen bei amtlichen Alarm-SMS und
Premium-SMS eine stille UCS-2-Kostenverdopplung aus (67 statt 153 Zeichen je
SMS-Teil), weil diese Zeichen zwar GSM-7-kodierbar sind, aber je zwei Septets
statt eines kosten und die Budget-Herleitung von genau einem Septet pro
Zeichen ausgeht.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `def _ascii(text: str) -> str` (Zeilen 709-714)

## Betroffene Kanäle

`_ascii()` wird ausschließlich über `render_official_alert_sms()`
(`src/output/renderers/alert/official_alerts.py:1971-2054`) verwendet, die
von drei Stellen in `src/services/notification_service.py` aufgerufen wird:

| Zeile | Kanal | Auswirkung des Bugs |
|-------|-------|----------------------|
| 873 | Telegram-Kurzform | Nutzt denselben Renderer, GSM-7/SMS-Budget dort fachlich irrelevant, aber gleicher Codepfad |
| 892 | amtliche SMS | Stille UCS-2-Kostenverdopplung |
| 911 | Premium-SMS | Stille UCS-2-Kostenverdopplung |

Mail- und Telegram-Volltext-Pfade nutzen andere Formatierungsfunktionen und
sind von diesem Bug nicht betroffen (siehe Known Limitations).

## Estimated Scope

- **LoC:** ~15-20
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `tests/tdd/_gsm7_charset.py::GSM7_EXTENDED_TWO_SEPTET_CHARS` | Test-Konstante | Quelle der Wahrheit für die 9 zu behandelnden Zeichen — Produktionscode dupliziert die Liste (kein Import aus `tests/`), mit Kommentar-Verweis auf diese Datei |
| `src/output/renderers/comparison.py::_SMS_GSM7_UNSAFE_REPLACEMENTS` / `_sms_gsm7_safe()` (Zeilen 592-624) | Vorbild-Muster | Analoges, bereits produktives Ersetzungsmuster für den Compare-SMS-Pfad |
| `src/utils/ascii_fold.py::fold_ascii()` | Upstream, unverändert | Faltet nur Buchstaben (NFKD, Kategorien Ll/Lu/Lt/Lo/Lm) — Extension-Zeichen sind keine Buchstaben, strukturell nicht durch `fold_ascii()` erreichbar |
| Renderer-Commit-Gate #811 (`.claude/hooks/renderer_mail_gate.py`) | Gate | `alert/render.py` liegt unter `src/output/renderers/alert/*.py` — Commit erst möglich, wenn `tests/tdd/test_issue_811_mode_matrix.py` grün ist UND ein frischer erfolgreicher `briefing_mail_validator.py`-Lauf gegen Staging vorliegt |

## Implementation Details

In `_ascii()` (`alert/render.py:709-714`) wird vor oder nach `fold_ascii()`
eine feste Ersetzungstabelle für die 9 GSM-7-Extension-Zeichen ergänzt,
analog zum bestehenden Muster `_SMS_GSM7_UNSAFE_REPLACEMENTS` /
`_sms_gsm7_safe()` in `comparison.py:592-624`:

```
# GSM-7-Extension-Tabelle (Form-Feed, ^ { } \ [ ~ ] | €) ist zwar
# GSM-7-kodierbar, kostet aber ZWEI Septets je Zeichen (ESC-Fluchtsequenz,
# GSM 03.38) -- eine stille Budget-Verletzung. Zeichenliste dupliziert aus
# tests/tdd/_gsm7_charset.py::GSM7_EXTENDED_TWO_SEPTET_CHARS (Quelle der
# Wahrheit fuer die Test-Verifikation), Issue #1796.
_ASCII_EXTENSION_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("[", "("),
    ("]", ")"),
    ("{", "("),
    ("}", ")"),
    ("\\", "/"),
    ("|", "-"),
    ("~", "-"),
    ("^", ""),
    ("€", "EUR"),
    ("\x0c", ""),
)
```

Ersetzungsschleife analog `_sms_gsm7_safe()`, angewendet innerhalb von
`_ascii()`:

```
def _ascii(text: str) -> str:
    text = (
        text.replace("–", "-").replace("−", "-").replace("°", "")
        .replace("↑", "+").replace("↓", "-")
    )
    for bad, good in _ASCII_EXTENSION_REPLACEMENTS:
        text = text.replace(bad, good)
    return fold_ascii(text)
```

Reihenfolge relativ zu den bestehenden Einzelersetzungen und zu
`fold_ascii()` ist unkritisch, da keine Überschneidung der Zeichenmengen
besteht (Extension-Zeichen sind keine Buchstaben und keines der bereits
behandelten Zeichen `– − ° ↑ ↓`).

`tests/tdd/test_trip_sms_gsm7_charset.py:230` trägt den Platzhalter-Kommentar
„AC-3 (Extension-Zeichen aus dem Trip-Namen) entfernt, s. Issue #1796.“ —
dort wird der reaktivierte, parametrisierte Test ergänzt (alle 9 Zeichen aus
`GSM7_EXTENDED_TWO_SEPTET_CHARS`, nicht nur die 3 Issue-Beispiele).

## Expected Behavior

- **Input:** Trip-Name mit mindestens einem GSM-7-Extension-Zeichen (z.B.
  `"KHW [Test]"`, `"Tour~Nord"`, `"Weg|Nord"`), als `sms_prefix` an
  `render_official_alert_sms()` übergeben.
- **Output:** Gerenderte SMS enthält ausschließlich Zeichen aus dem
  GSM-7-Basisalphabet (GSM 03.38), geprüft über `assert_gsm7_clean()`
  (`tests/tdd/_gsm7_charset.py`) — kein Extension-Zeichen mehr im Text.
- **Side effects:** Keine. Reine Text-Transformation innerhalb von
  `_ascii()`, keine Änderung an Aufrufer-Signaturen oder Datenmodellen.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Name enthält eines der 9 GSM-7-Extension-Zeichen
  (`^ { } [ ] ~ | \ €` oder Form-Feed `\x0c`) / When
  `render_official_alert_sms()` mit diesem Namen als `sms_prefix` gerendert
  wird / Then enthält das Ergebnis die jeweilige Ersatz-Sequenz statt des
  Extension-Zeichens und besteht `assert_gsm7_clean()`.
  - Test: Parametrisierter Test über alle 9 Zeichen aus
    `GSM7_EXTENDED_TWO_SEPTET_CHARS`, der je Zeichen einen Trip-Namen mit
    diesem Zeichen rendert und `assert_gsm7_clean()` auf das Ergebnis
    anwendet — kein Dateiinhalt-Check.

- **AC-2 (Regression):** Given ein Trip-Name mit bereits gefalteten Umlauten
  und Diakritika (`"Höhenweg Świnica"`) / When derselbe amtliche Alarm wie
  bisher gerendert wird / Then bleibt das Ergebnis byte-identisch zum
  bisherigen Verhalten.
  - Test: Bestehender Test
    `tests/tdd/test_trip_sms_gsm7_charset.py::test_official_alert_sms_stays_gsm7_clean_for_every_hazard_and_umlaut_trip_name`
    bleibt unverändert grün (keine Anpassung nötig).

- **AC-3 (Bug-Nachweis aus dem Issue):** Given die drei im Issue #1796
  genannten Beispiel-Trip-Namen (`"KHW [Test]"`, `"Tour~Nord"`,
  `"Weg|Nord"`) / When jeweils eine amtliche Alarm-SMS gerendert wird / Then
  ist das Ergebnis GSM-7-sauber (`assert_gsm7_clean()` besteht für alle
  drei).
  - Test: Parametrisierter Test über exakt diese drei Trip-Namen, direkt aus
    dem Issue übernommen — reproduziert den ursprünglich gemeldeten Fund vor
    dem Fix (rot) und bestätigt ihn behoben (grün) danach.

## Known Limitations

- Der Fix wirkt ausschließlich auf den SMS-Renderpfad (`_ascii()` in
  `alert/render.py`), nicht auf Mail- oder Telegram-Volltext-Pfade — diese
  nutzen andere Formatierungsfunktionen und sind von der GSM-7-Problematik
  nicht betroffen. Die Telegram-Kurzform (`notification_service.py:873`)
  läuft über denselben Renderer und profitiert damit vom Fix, obwohl dort
  kein echtes SMS-Kostenproblem besteht.
- Renderer-Commit-Gate #811 (`renderer_mail_gate.py`) ist un-überspringbar:
  `alert/render.py` liegt unter `src/output/renderers/alert/*.py` — der
  Commit ist erst möglich, wenn `tests/tdd/test_issue_811_mode_matrix.py`
  grün ist UND ein frischer erfolgreicher `briefing_mail_validator.py`-Lauf
  gegen Staging vorliegt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Bugfix in einem bereits etablierten, produktiven Muster
  (analog `comparison.py::_SMS_GSM7_UNSAFE_REPLACEMENTS`/`_sms_gsm7_safe()`),
  keine Architekturänderung, keine neue Entscheidungsfläche.

## Changelog

- 2026-08-13: Initial spec created
- 2026-08-13 (RED-Phase, echter Fund): `^` fehlte in der ursprünglichen
  Ersetzungstabelle (9 statt 10 Zeichen aus `GSM7_EXTENDED_TWO_SEPTET_CHARS`)
  — durch den ueber ALLE 10 Zeichen parametrisierten AC-1-Test aufgedeckt,
  ergaenzt. Ausserdem verifiziert: `€` wird bereits heute durch die
  bestehende `fold_ascii()`-Kette (`anyascii`-Bibliothek) korrekt zu `EUR`
  transliteriert — der `€`-Testfall ist schon VOR dem Fix gruen. Die
  explizite Tabellen-Ersetzung fuer `€` bleibt trotzdem bestehen
  (Eigenstaendigkeit statt stille Abhaengigkeit von `anyascii`-Verhalten).
