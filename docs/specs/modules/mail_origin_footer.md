---
entity_id: mail_origin_footer
type: module
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [email, renderer, footer, mime, observability]
---

<!-- Issues #1241 (Herkunfts-Footer) + #1247 (Date-Header), gebündelt -->

# Mail-Herkunft-Footer + Date-Header

## Approval

- [x] Approved (PO „freigabe" 2026-07-15 — inkl. Label-Wording-Tabelle)

## Purpose

Jede versendete Gregor-Mail bekommt eine dezente, zweizeilige Herkunfts-Fußzeile
(Zeile 1 = Mail-Art in Klartext, Zeile 2 = erzeugender Renderer + Commit-Stand)
aus einem einzigen geteilten Baustein `build_origin_footer(...)` in
`src/output/renderers/email/helpers.py` — damit ist bei jedem eingehenden
Support-Fall sofort erkennbar, welcher Renderer und welcher Code-Stand die
Mail erzeugt hat (#1241). Zusätzlich bekommt jede versendete Mail einen
RFC-2822-`Date`-Header im MIME-Envelope, der heute fehlt (#1247).

## Source

- **File:** `src/output/renderers/email/helpers.py` — NEU: `build_origin_footer()`, `OriginFooter`, `render_origin_footer_html()`, `render_origin_footer_text()`, `_deployed_commit()`, `_MAIL_TYPE_LABELS`-Mapping
- **File:** `src/output/renderers/email/html.py:383` `_render_footer` — Aufruf des Helpers, HTML-Variante
- **File:** `src/output/renderers/email/plain.py:282` `render_plain` — Aufruf des Helpers, Text-Variante
- **File:** `src/output/renderers/email/compact.py:193` `render_compact` — Aufruf des Helpers VOR dem `_ascii(body)`-Call (`:199`)
- **File:** `src/output/renderers/email/compare_html.py:748` `_render_app_footer` — Aufruf des Helpers, Label „Ortsvergleich"
- **File:** `src/output/renderers/alert/render.py` (`:156`, `:211`, `:386`, `:426`) — Aufruf für Radar-/Deviation-Alarm
- **File:** `src/output/renderers/alert/official_alerts.py:1048` `render_official_alert_html` (+Plain `:213`) — Aufruf mit `context_label`-Parameter; `_render_warn_block_embedded` (`:1138`/`:1291`) bekommt **keine** eigene Footer-Zeile
- **File:** `src/services/notification_service.py:530,641` — 2 Aufrufer von `render_warn_block`, threaden `context_label` durch (Trip-Name bzw. „Ortsvergleich")
- **File:** `src/output/channels/email.py:237` `build_mime_message` — `Date`-Header via `email.utils.formatdate(localtime=True)` in beiden Zweigen (HTML `:262-273`, Plain `:287-298`)

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen im Python-Core
> (`src/output/...`, `src/services/...`), keine Go-API/Frontend-Berührung.

## Estimated Scope

- **LoC:** ~155–260 (Code) + ~40–80 (Tests), Gesamt-Workflow potenziell >250 → LoC-Limit-Override erforderlich (siehe Reihenfolge unten)
- **Files:** 9 MODIFY (kein CREATE) + Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `format_units_legend` (`email/helpers.py:338`) | intern, Vorbild-Muster | Zeigt das etablierte SSoT-Helper-Muster: eine Funktion, von mehreren Renderern aufgerufen |
| `profile_signature.py:95` | intern, Vorbild-Muster (falscher Ort) | Geteilter Baustein für Branding — Muster tauglich, aber Herkunft ist inhaltlich getrennt vom Profil-Branding |
| `email.utils.formatdate` | stdlib | RFC-2822-konformer `Date`-Header (`localtime=True`) |
| `subprocess` + `git rev-parse --short HEAD` | stdlib + Git | Commit-Stand für Zeile 2, einmalig beim Modul-Import gecached |
| `.claude/hooks/briefing_mail_validator.py` | Downstream-Gate | ASCII-Check (`:449-450`), Byte-Limit 2048 (`:454-456`) für compact — MUSS grün bleiben |
| `.claude/hooks/email_spec_validator.py` | Downstream-Gate | HTML-Tabellen/Score-Regex — MUSS grün bleiben |
| `.claude/hooks/official_alert_mail_validator.py` | Downstream-Gate | `Gültig:`/`Stand: heute`-Regex — MUSS grün bleiben |
| `.claude/hooks/renderer_mail_gate.py` (#811) | Downstream-Gate | Zieht Briefing- UND Alert-Kategorie, da sowohl `channels/email.py` als auch `renderers/alert/*.py` geändert werden |
| `notification_service.py` (2 Aufrufer :530, :641) | intern, Caller | Liefert `X-GZ-Mail-Type`-Werte, aus denen Footer-Labels konsistent abgeleitet werden, plus `context_label` für official-alert |

## Implementation Details

### 1. Geteilter Helper (`email/helpers.py`)

```python
@dataclass(frozen=True)
class OriginFooter:
    line1: str  # Mail-Art in Klartext, ggf. mit Kontext-Prefix
    line2: str  # "<renderer_datei>.py (<variante>) · <commit>"

def build_origin_footer(
    mail_type: str,
    mail_format: str | None = None,
    *,
    renderer_name: str,
    context_label: str | None = None,
) -> OriginFooter: ...

def render_origin_footer_html(footer: OriginFooter) -> str: ...   # Design-Tokens, dezent
def render_origin_footer_text(footer: OriginFooter) -> str: ...  # " · "-Join für plain/compact
```

`_MAIL_TYPE_LABELS: dict[tuple[str, str | None], str]` bildet `(mail_type,
mail_format)` auf Klartext ab (siehe Label-Tabelle unten). `official-alert`
ist der einzige Typ, der zusätzlich `context_label` konsumiert
(„{context_label} · Amtliche Warnung").

`_deployed_commit()` ruft `git rev-parse --short HEAD` per `subprocess.run`
einmal beim Modul-Import auf, Ergebnis wird modulweit gecached (kein
wiederholter Subprozess-Aufruf pro Mail). `try/except` → `"unknown"` bei
fehlendem `.git`-Verzeichnis oder Git-Fehler.

### Label-Tabelle (Vorschlag, PO-Freigabe ausstehend)

| mail_type | mail_format | Klartext (Zeile 1, Typ-Teil) |
|---|---|---|
| trip-briefing | full | Etappen-Briefing · Vollversion |
| trip-briefing | compact | Etappen-Briefing · Kompakt |
| compare | – | Ortsvergleich |
| official-alert | – | {context_label} · Amtliche Warnung (context_label = Trip-Name oder „Ortsvergleich") |
| radar-alert | – | Regen-/Gewitter-Alarm |
| deviation-alert | – | Abweichungs-Alarm |

### 2. Compact-Renderer — ASCII-Reihenfolge (`compact.py:193`)

Footer-Zeilen werden VOR `body = "\n".join(lines)` (`compact.py:199`) und
damit vor dem finalen `return _ascii(body)` (`compact.py:83`) angehängt. Der
bestehende `_ascii()`-Übersetzer (`compact.py:36-48`) faltet `·` automatisch
zu `-` — keine Sonderbehandlung im Helper nötig, ABER: Footer-Text kurz
halten, da das bestehende Byte-Limit 2048 (`briefing_mail_validator.py:454-456`)
sonst durch die zusätzliche Zeile verletzt werden kann.

### 3. `context_label`-Plumbing (official-alert)

```
notification_service.py:530 (Trip-Aufrufer)     → context_label=trip.name
notification_service.py:641 (Compare-Aufrufer)  → context_label="Ortsvergleich"
                ↓
render_warn_block(context_label=...)  (official_alerts.py:1148)
                ↓
render_official_alert_html(...)  (official_alerts.py:1048)
                ↓
build_origin_footer(mail_type="official-alert", context_label=...)
```

Embedded Warn-Block (`_render_warn_block_embedded`, `:1138`/`:1291`) ruft den
Helper NICHT auf — die Wirts-Mail (Trip-Briefing oder Compare) trägt bereits
ihre eigene Herkunftszeile.

### 4. `Date`-Header (`channels/email.py:237`)

In `build_mime_message`, in beiden Zweigen (`html=True` nach `msg["To"]`
Zeile `:265`; `html=False` nach `msg["To"]` Zeile `:290`):

```python
msg["Date"] = email.utils.formatdate(localtime=True)
```

## Expected Behavior

- **Input:** Renderer-Aufruf mit `mail_type`, optional `mail_format`/`context_label`, Renderer-Name; MIME-Aufbau mit Subject/Body/Adressen wie bisher.
- **Output:** Gerenderte Mail (HTML/Plain/Compact) enthält am Ende zusätzlich zwei Footer-Zeilen (Klartext-Mail-Art, Renderer+Commit). Versendete MIME-Message enthält einen `Date`-Header im RFC-2822-Format.
- **Side effects:** Ein `subprocess`-Aufruf (`git rev-parse --short HEAD`) beim ersten Modulimport von `helpers.py`, danach reiner Cache-Zugriff — kein Aufruf pro Mail.

## Acceptance Criteria

- **AC-1:** Given ein Trip-Briefing im Vollversion-Modus (`mail_type=trip-briefing`, `mail_format=full`) wird gerendert / When die HTML- und Plain-Ausgabe erzeugt werden / Then enthält beide Ausgaben am Ende zwei Footer-Zeilen mit Klartext „Etappen-Briefing · Vollversion" und Renderer+Commit-Stand.
  - Test: Golden-Email-Test rendert eine Full-Trip-Mail und prüft String-Vorkommen der Footer-Zeilen im HTML- und Plain-Output.

- **AC-2:** Given ein Trip-Briefing im Kompakt-Modus (`mail_format=compact`) wird gerendert / When `render_compact` aufgerufen wird / Then enthält der Output die Footer-Zeilen, bleibt vollständig ASCII (`str.isascii() == True`) und unterschreitet das Byte-Limit von 2048 Bytes.
  - Test: Unit-Test rendert eine Compact-Mail, prüft `output.isascii()`, prüft `len(output.encode("utf-8")) < 2048`, prüft dass kein `·` (U+00B7) im Output vorkommt.

- **AC-3:** Given eine Ortsvergleichs-Mail wird gerendert / When `render_compare_html`/`_render_app_footer` aufgerufen werden / Then zeigt der Footer „Ortsvergleich" als Zeile 1 und Renderer+Commit als Zeile 2.
  - Test: Golden-Email-Test für Compare-HTML prüft Footer-String-Vorkommen.

- **AC-4:** Given ein Abweichungs-Alarm (`mail_type=deviation-alert`) wird gerendert / When `alert/render.py` `render_email` aufgerufen wird / Then enthält die Mail die Footer-Zeile „Abweichungs-Alarm" plus Renderer+Commit.
  - Test: Unit-Test rendert einen Deviation-Alert und prüft Footer-Vorkommen in HTML und Plain.

- **AC-5:** Given ein Regen-/Gewitter-Alarm (`mail_type=radar-alert`) wird gerendert / When `alert/render.py` aufgerufen wird / Then enthält die Mail die Footer-Zeile „Regen-/Gewitter-Alarm" plus Renderer+Commit.
  - Test: Unit-Test rendert einen Radar-Alert und prüft Footer-Vorkommen.

- **AC-6:** Given eine amtliche Warnung wird standalone aus Trip-Kontext versendet (`notification_service.py:530`) / When der Footer gerendert wird / Then zeigt Zeile 1 den Trip-Namen als Kontext, z.B. „<Trip-Name> · Amtliche Warnung".
  - Test: Unit-Test ruft `render_official_alert_html(context_label=trip.name)` und prüft, dass der Trip-Name im Footer-Text erscheint.

- **AC-7:** Given eine amtliche Warnung wird standalone aus Compare-Kontext versendet (`notification_service.py:641`) / When der Footer gerendert wird / Then zeigt Zeile 1 „Ortsvergleich · Amtliche Warnung" statt eines Trip-Namens.
  - Test: Unit-Test ruft `render_official_alert_html(context_label="Ortsvergleich")` und prüft den Footer-Text.

- **AC-8:** Given ein embedded Warn-Block wird innerhalb einer Trip- oder Compare-Mail gerendert / When `_render_warn_block_embedded` aufgerufen wird / Then erscheint KEINE zusätzliche Herkunfts-Footer-Zeile innerhalb des Warn-Blocks (nur die Wirts-Mail trägt den Footer).
  - Test: Unit-Test rendert eine Mail mit eingebettetem Warn-Block und prüft, dass der Footer-Text genau einmal (nicht doppelt) in der Gesamtausgabe vorkommt.

- **AC-9:** Given `.git` ist im Laufzeit-Verzeichnis vorhanden / When `_deployed_commit()` beim Modulimport ausgeführt wird / Then liefert Zeile 2 den kurzen Commit-Hash (mindestens 7 Hex-Zeichen, aus `git rev-parse --short HEAD`); Given kein `.git` vorhanden oder Git-Fehler / When `_deployed_commit()` läuft / Then liefert Zeile 2 den Fallback-Wert „unknown" statt einer Exception.
  - Test: Unit-Test mit echtem Git-Repo prüft Hash-Format (`re.match(r"^[0-9a-f]{7,}$", ...)`); zweiter Unit-Test simuliert fehlendes `.git` (temp dir ohne Git) und prüft Fallback „unknown".

- **AC-10:** Given eine beliebige versendete Mail (HTML- oder Plain-Zweig) / When `build_mime_message` aufgerufen wird / Then enthält die zurückgegebene MIME-Message einen `Date`-Header, der als RFC-2822-Datum parsbar ist (`email.utils.parsedate_to_datetime`).
  - Test: Unit-Test ruft `build_mime_message` in beiden Zweigen (`html=True`/`html=False`) auf und prüft `msg["Date"]` ist gesetzt und parsbar.

- **AC-11 (Nicht-Regression):** Given die drei bestehenden Mail-Validatoren (`briefing_mail_validator.py`, `email_spec_validator.py`, `official_alert_mail_validator.py`) und die bestehenden Golden-Email-Tests / When sie nach Einführung des Footers erneut ausgeführt werden / Then bleiben alle drei Validatoren sowie alle Golden-Email-Tests grün (kein neuer Fehlschlag durch die Footer-Änderung).
  - Test: Live-E2E — Test-Mail an `gregor-test@henemm.com` senden, alle drei Validatoren gegen die zugestellte Mail laufen lassen (Exit 0 erforderlich), zusätzlich `uv run pytest` auf die Golden-Email-Suite (Kern).

## Known Limitations

- Test-Mails (via `preview_service.py`) bekommen kein eigenes „Test"-Label im Footer — sie erben Footer und Label des zugrundeliegenden Render-Pfads unverändert (Scope-Entscheidung aus der Analyse, explizit ausgeklammert).
- Der Commit-Stand wird ausschließlich aus einem lokalen Git-Checkout gelesen (`git rev-parse --short HEAD`); es gibt keinen Fallback auf ein separates Deploy-Stamp-File. Läuft der Prozess außerhalb eines Git-Checkouts, ist der Fallback „unknown" das erwartete (nicht fehlerhafte) Verhalten.
- Das Label-Wording aus der Tabelle oben ist ein Vorschlag und muss vom PO im Rahmen der Freigabe (Phase 3) bestätigt oder korrigiert werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um einen lokal begrenzten, additiven Helper nach etabliertem Projektmuster (`format_units_legend`), keine strukturelle Architekturänderung. Die einzige grundsätzliche Design-Entscheidung (Helper-Baustein vs. MIME-Ebene) ist bereits in der Analyse-Phase getroffen und in diese Spec übernommen (Issue #1241 fordert explizit den geteilten Baustein).

## Test Plan

### Kern (deterministisch, kein Netz/Live-Dienst) — AC-1 bis AC-10
Rendern der jeweiligen Mail-Objekte in-process (Golden-Email-Tests /
Helper-Unit-Tests), Assertion auf Footer-String-Vorkommen, ASCII-Eigenschaft,
Byte-Limit, `Date`-Header-Parsbarkeit, Commit-Hash-Format/Fallback. Keine
Mocks — echte Renderer-Aufrufe mit echten (ggf. minimalen) Fixture-Daten.

### Live-E2E (Staging, echte Zustellung) — AC-11
Test-Mail über den vollen Versandpfad an `gregor-test@henemm.com` senden,
per IMAP abrufen, alle drei Mail-Validatoren + Golden-Email-Suite gegen die
zugestellte Mail laufen lassen. Nur bei Exit 0 aller drei Validatoren gilt
„E2E bestanden".

## Changelog

- 2026-07-15: Initial spec created
