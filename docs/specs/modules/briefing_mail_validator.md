---
entity_id: briefing_mail_validator
type: module
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [validator, email, acceptance-gate, trip-briefing]
---

# Briefing-Mail-Validator (full + compact)

## Approval

- [ ] Approved

## Purpose

Kanonischer Acceptance-Validator für **Trip-Briefing-Mails**. Holt die zuletzt
zugestellte Mail aus dem Test-Postfach, erkennt anhand zweier Marker-Header
deterministisch Typ und Format, und prüft sie **format-spezifisch auf
Plausibilität** (nicht bloß String-Presence). Schließt die Coverage-Lücke aus
#732/#722: bisher deckt nur `email_spec_validator.py` die Orts-Vergleich-Mail ab.

## Source

- **File:** `.claude/hooks/briefing_mail_validator.py` (neu) — Validator (Vorbild: `email_spec_validator.py`)
- **File:** `src/outputs/email.py` — `build_mime_message()` + `EmailOutput.send()` (Marker-Header, Python-Backend)
- **File:** `src/services/trip_report_scheduler.py` — Briefing-Versand setzt `mail_type`/`mail_format`
- **File:** `src/app/cli.py` — Orts-Vergleich-Versand setzt `mail_type="compare"`
- **Identifier:** `build_mime_message`, `briefing_mail_validator.run_validation`

## Estimated Scope

- **LoC:** ~170 (Validator ~150, Header-Plumbing ~20)
- **Files:** 4 (+ CLAUDE.md-Doku-Regel)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `email_spec_validator.py` | Vorbild | IMAP-Fetch-Muster, Exit 0/1, YAML-Log (fail-soft) |
| `build_mime_message` (`src/outputs/email.py`) | upstream | Setzt die Marker-Header (genutzt von beiden Mail-Typen) |
| Stalwart Test-Postfach (`GZ_IMAP_*`) | upstream | Quelle der echten zugestellten Mail (kein Mock) |

## Implementation Details

### 1. Marker-Header (kleiner Hebel)

`build_mime_message()` bekommt zwei neue optionale Parameter mit Defaults
(Backward-Compat für Service-Error-Mail u.a.):

```
build_mime_message(..., mail_type: str | None = None, mail_format: str | None = None)
  → wenn gesetzt:  msg["X-GZ-Mail-Type"] = mail_type   # "trip-briefing" | "compare"
                   msg["X-GZ-Format"]    = mail_format  # "full" | "compact"
```

`EmailOutput.send()` reicht `mail_type`/`mail_format` durch.

- **Briefing-Versand** (`trip_report_scheduler.py`): full-Pfad → `("trip-briefing","full")`,
  compact-Pfad → `("trip-briefing","compact")`.
- **Orts-Vergleich-Versand** (`cli.py`): `("compare","full")`.

### 2. Validator dispatcht auf den Header

`briefing_mail_validator.py` (analog `email_spec_validator.py`):

- `fetch_latest_message()` → liefert das geparste `email.message.Message`-Objekt (nicht nur den HTML-Body), inkl. Header & alle MIME-Parts.
- Liest `X-GZ-Mail-Type`:
  - `compare` → **kein** struktureller Fehlversuch; Meldung „Keine Trip-Briefing-Mail (Typ=compare) — falscher Validator" und Exit 0 (sauberes No-Op, nicht Exit 1).
  - fehlend → Exit 1 mit klarer Meldung („Marker-Header fehlt — Mail nicht vom getaggten Renderer").
  - `trip-briefing` → dispatch auf `X-GZ-Format`:

**full:**
- `Content-Type` = `multipart/alternative`
- genau ein `text/html`-Part UND ein `text/plain`-Part vorhanden
- ≥1 Stunden-Tabelle (sequenzielle `HH:00`-Zeilen) im HTML-Part
- Werte plausibel: `temp_lo <= temp_hi`; Wind/Regen-Werte `>= 0`; **nicht** alle Metriken None/0; Stunden im Tagesfenster (06–22)
- Subject nicht leer

**compact:**
- single `text/plain` (kein multipart)
- `Content-Transfer-Encoding` 7bit, `isascii()` True
- Byte-Größe < 2 KB
- Kopf + Metriken-Überblick + Ausblick + Footer vorhanden
- **KEINE** sequenzielle Stunden-Tabelle

Plausibilitäts-Schwellen sind bewusst weit (gegen False-Positives, die Deploys
fälschlich blockieren): geprüft wird Selbst-Konsistenz der Werte, **nicht** ein
extern bekannter Soll-Zustand (Validator braucht keinen Trip-Kontext).

### 3. Verkabelung

CLAUDE.md-Doku-Regel analog zur `email_spec_validator`-Regel: für
Trip-Briefing-Mail-Änderungen ist `briefing_mail_validator.py` das Acceptance-Gate
(Exit 0/1), läuft gegen die Staging-Mail im Test-Postfach.

## Expected Behavior

- **Input:** zuletzt zugestellte Mail im Test-Postfach (`GZ_IMAP_*`); optional `--max-bytes` für die compact-Schwelle.
- **Output:** Exit 0 = alle format-spezifischen Checks bestanden (oder Mail ist `compare` → No-Op); Exit 1 = Spec-Verletzung mit konkreter Fehlerliste; Exit 2 = technischer Fehler (IMAP nicht erreichbar).
- **Side effects:** strukturiertes YAML-Log in `.claude/workflows/_log/` (fail-soft, wie Vorbild). Marker-Header in jeder ausgehenden Briefing-/Vergleich-Mail.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `email_format="full"`, When eine Briefing-Mail tatsächlich versendet und per IMAP aus dem Test-Postfach abgeholt wird, Then trägt die zugestellte Mail die Header `X-GZ-Mail-Type: trip-briefing` und `X-GZ-Format: full`.
  - Test: echter SMTP-Versand des full-Briefings → IMAP-Abruf → Header-Werte am zugestellten `email.message.Message` prüfen (kein Mock).

- **AC-2:** Given ein Trip mit `email_format="compact"`, When die Briefing-Mail versendet und per IMAP abgeholt wird, Then trägt die zugestellte Mail die Header `X-GZ-Mail-Type: trip-briefing` und `X-GZ-Format: compact`, und der Body ist single `text/plain`.
  - Test: echter SMTP-Versand des compact-Briefings → IMAP-Abruf → Header + `get_content_type()` am zugestellten Objekt prüfen.

- **AC-3:** Given die bestehende Orts-Vergleich-Mail, When sie versendet und abgeholt wird, Then trägt sie `X-GZ-Mail-Type: compare`, und `email_spec_validator.py` läuft gegen sie weiterhin mit Exit 0 (keine Regression durch die neuen Header).
  - Test: Vergleich-Mail versenden → IMAP → Header prüfen + `email_spec_validator` ausführen und Exit-Code 0 verifizieren.

- **AC-4:** Given eine zugestellte full-Briefing-Mail mit plausiblen Werten, When `briefing_mail_validator` gegen sie läuft, Then ist der Exit-Code 0 (multipart/alternative, HTML- und Plain-Part vorhanden, ≥1 Stundentabelle, Werte selbst-konsistent, Subject nicht leer).
  - Test: full-Mail zustellen → Validator-Subprozess → Exit 0 und „bestanden"-Ausgabe prüfen.

- **AC-5:** Given eine full-Briefing-Mail mit unplausiblen Daten (z.B. `temp_lo > temp_hi`, oder fehlender HTML-Part, oder leere Stundentabelle), When der Validator läuft, Then ist der Exit-Code 1 mit einer konkreten, die Verletzung benennenden Fehlermeldung.
  - Test: getaggte aber kaputte full-Mail (real konstruiertes MIME-Objekt) → Validator → Exit 1 + erwartete Fehlerzeile.

- **AC-6:** Given eine zugestellte compact-Briefing-Mail, When der Validator läuft, Then ist der Exit-Code 0 (single text/plain, 7bit, `isascii`, < 2 KB, Kopf+Metriken+Ausblick+Footer vorhanden, keine Stundentabelle); bei einer compact-Mail die multipart ist ODER eine Stundentabelle enthält ODER > 2 KB groß ist, ist der Exit-Code 1.
  - Test: gültige compact-Mail → Exit 0; manipulierte compact-Mail (multipart / mit Stundentabelle / zu groß) → Exit 1.

- **AC-7:** Given eine `compare`-getaggte Mail, When `briefing_mail_validator` läuft, Then klassifiziert er sie NICHT fälschlich als kaputtes Briefing, sondern meldet „falscher Validator / kein Trip-Briefing" und beendet mit Exit 0 (sauberes No-Op statt struktureller Fehlalarm).
  - Test: compare-Mail zustellen → briefing_mail_validator → Exit 0 + No-Op-Meldung (kein struktureller Fehler).

## Known Limitations

- Plausibilität prüft Selbst-Konsistenz, nicht meteorologische Korrektheit (kein externer Soll-Abgleich) — bewusst, um Trip-Kontext-Freiheit und False-Positive-Armut zu wahren.
- Alte Mails ohne Marker-Header (vor diesem Feature) führen zu Exit 1 mit klarer Meldung; im Acceptance-Lauf wird immer frisch getaggte Mail zugestellt.
- Stundentabellen-Erkennung über sequenzielle `HH:00`-Zeilen (gleiche Heuristik wie der etablierte #722-IMAP-MIME-Test).

## Changelog

- 2026-06-11: Initial spec created (#733, ausgegliedert aus #732, Quelle #722)
