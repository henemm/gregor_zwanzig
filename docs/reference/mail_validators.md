# Mail-Validatoren & Renderer-Gate — Detail-Referenz

Kompakte Übersicht + Dispatch-Tabelle stehen in `CLAUDE.md` → Abschnitt
„Mail-Validatoren & Renderer-Gate". Dieses Dokument hält die vollständigen
Plausibilitäts-Schwellen, das Dispatch-Verhalten, die Anti-Stale-Mechanik und
die Historie.

Es gibt **drei verschiedene Mail-Pfade** mit **drei verschiedenen Gates**. Den
falschen Validator auf einen Pfad anzuwenden ist ein Fehler — er kann strukturell
nie bestehen (Dauer-Exit-1) und führt zu falschem „Feature kaputt" oder
Gate-Erosion.

## 1. `email_spec_validator.py` — Orts-Vergleich-Mail (ZWINGEND)

**Geltungsbereich:** prüft **ausschließlich** den **Orts-Vergleich-Mail**-Pfad.
Fest auf dessen Struktur verdrahtet: zwei Tabellen, die **Vergleichstabelle**, die
**Winner-Box** (Empfehlung) und mindestens `--min-locations` Orte (Default 3).
Eine **Trip-Briefing-Mail** (anderer Versandpfad, n Stundentabellen pro Etappe,
keine Winner-Box) kann diesen Validator **strukturell nie** bestehen → Dauer-Exit-1.

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

Prüft: Struktur, Location-Anzahl, Plausibilität, Format, Vollständigkeit der
Orts-Vergleich-Mail. Läuft in der Acceptance-Stage gegen die Staging-Mail:
Test-Trip mit Empfänger `gregor-test@henemm.com`, IMAP-Quelle ist das Stalwart-
Test-Postfach (`mail.henemm.com`). `fetch_latest_email()` priorisiert seit #972
`GZ_TEST_IMAP_USER`/`GZ_TEST_IMAP_PASS` vor `GZ_IMAP_*`/`GZ_SMTP_*`, sodass
verlässlich gegen das Test-Postfach geprüft wird. Credentials aus den Settings —
niemals im Klartext. Kein Gmail.

**Nur bei Exit 0** darfst du „E2E Test bestanden" sagen. Einfache String-Checks
beweisen NICHTS — sie prüfen nicht, ob Daten SINNVOLL sind.

## 2. `briefing_mail_validator.py` — Trip-Briefing-Mail (seit #733)

**Geltungsbereich:** kanonisches Acceptance-Gate für **Trip-Briefing-Mails**
(beide Formate: `full` HTML / `compact` Nur-Text seit #722). Dispatcht
deterministisch über zwei Marker-Header, die `build_mime_message()` setzt:
`X-GZ-Mail-Type: trip-briefing|compare` und `X-GZ-Format: full|compact`.

```bash
uv run python3 .claude/hooks/briefing_mail_validator.py
```

Prüft format-spezifisch auf **Plausibilität** (nicht bloß String-Presence) gegen
die echt zugestellte Mail aus dem Stalwart-Test-Postfach. `fetch_latest_message()`
priorisiert seit #972 `GZ_TEST_IMAP_USER`/`GZ_TEST_IMAP_PASS` vor
`GZ_IMAP_*`/`GZ_SMTP_*` (Pattern wie `radar_alert_mail_validator.py`), damit der
Validator verlässlich gegen `gregor-test@henemm.com` prüft. Kein Mock, kein Gmail.

- **full:** `multipart/alternative`, je ein `text/html`- und `text/plain`-Part,
  ≥1 sequenzielle Stundentabelle (≥2 `HH:00`-Zeilen), Werte selbst-konsistent
  (`temp_lo <= temp_hi`, Wind/Regen ≥ 0, nicht alle None/0), Stunden im
  Tagesfenster 06–22 — dieser Check läuft seit #974 nur noch auf dem HTML-Teil
  **vor** dem ersten „🌙 Nacht am Ziel"-Marker; die Nacht-Sektion (evening-Full-
  Mails, Ankunft→06:00 Folgetag, legitime Stunden wie 00/02/04) ist davon
  ausgenommen und löst keinen False-Positive mehr aus. Temperatur-Range- und alle
  übrigen Checks laufen weiter auf dem vollen HTML. Subject nicht leer.
- **compact:** single `text/plain`, 7bit (oder QP bei reinem ASCII), `isascii`,
  < 2 KB, HART: Kopf + `== Metriken-Ueberblick ==` + Footer; Ausblick ist
  **optional** (der Renderer lässt ihn legitim weg, wenn keine Stabilität/Trend-
  Daten vorliegen); **keine** Stundentabelle.

**Dispatch-Verhalten:** `compare`-getaggte Mail → sauberes No-Op (Exit 0, falscher
Validator). Fehlender Marker-Header → Exit 1 (Mail nicht vom getaggten Renderer).
Plausibilitäts-Schwellen sind bewusst weit kalibriert (gegen False-Positives, die
Deploys fälschlich blockieren). **Nur bei Exit 0** darfst du „E2E Test bestanden"
sagen.

Der ergänzende `IMAP-MIME-Verhaltenstest` (seit #722, #721, #636) bleibt als
Unit-/Integrationsbeweis gültig; der Validator kodifiziert genau dieses Muster als
Gate. Der `email_spec_validator.py` ist für Trip-Briefing-Mails **nicht** zuständig.

## 3. `renderer_mail_gate.py` — Commit-Gate für Mail-Renderer (seit #811)

Commit-Hook (PreToolUse→Bash-Kette nach `pre_commit_gate.py`). Macht die
Validator-„PFLICHT" technisch **un-überspringbar**: Sobald ein `git commit` eine
Mail-Inhalts-Datei staged (`src/output/renderers/email/*.py`, `src/formatters/*.py`,
`src/outputs/email.py`), **blockiert der Commit (Exit 2)**, bis im aktiven Workflow
**beide** Nachweise vorliegen:

1. der **Modus-Matrix-Vertragstest** (`tests/tdd/test_issue_811_mode_matrix.py`)
   lief grün — er rendert die echte Mail über
   `{full,compact}×{Einfach,Roh}×{briefing,alert}` und erzwingt, dass der Roh-Modus
   Zahlen statt Ampelpunkte zeigt (deckt **Briefing- UND Alert/„Update"-Mail** ab,
   da gemeinsamer `render_email`-Pfad);
2. ein erfolgreicher **`briefing_mail_validator.py`**-Lauf
   (`*_briefing_validation.yaml` mit `passed: true`).

**Anti-Stale:** Der Matrix-Nachweis bindet an einen sha256 der Mail-Dateien, der
Validator-Nachweis an seine `validated_at`-Frische — jede neue Renderer-Änderung
invalidiert beide → Test + Validator müssen erneut laufen. **Kein globaler/ENV-
Bypass.** Verhindert stille Mail-Format-Defekte vor dem Merge (Issue #810-Klasse).

**Abhilfe bei Blockade** (kein Override): Vertragstest laufen lassen
(`uv run pytest tests/tdd/test_issue_811_mode_matrix.py` — der Lauf schreibt den
Matrix-Nachweis automatisch) und den `briefing_mail_validator.py` gegen die
zugestellte Staging-Mail grün bekommen.

## Strukturelle Render-Checks im briefing_mail_validator (Issue #833)

Der Trip-Briefing-Validator prüft die `full`-Mail nicht mehr nur als MIME-String,
sondern **rendert** den HTML-Part headless (Playwright/Chromium) bei **≤390px** und
**≥1000px** und bewertet das gerenderte Artefakt. Fehlt Playwright/der Browser, wird
**Exit 2** (technischer Fehler) signalisiert — **nie** Exit 1 (kein False-Negative).

Erzwungene Invarianten (alle hart, Exit 1):

| Check | Funktion | Was rot wird |
|---|---|---|
| **Viewport-Render** (AC-1) | `_check_rendered` | Bei einer Breite ist keine Wetter-Tabelle sichtbar **oder** der für die Breite falsche Block ist sichtbar (≤390px → `.desktop-only`; ≥1000px → `.mobile-compact`) — Dual-Render/#794-Klasse. Konditional: flache Tabellen ohne responsive Wrapper bleiben gültig. |
| **Ebenen-Konsistenz** (AC-3) | `_check_layer_consistency` | Pill-Spitzenwert ≠ Tabellen-Spalten-Max (> ±3 km/h), Mapping über th-Spaltenindex (#807). |
| **Metrik-Plausibilität** (AC-4) | `_check_metric_plausibility` | „Sonne X min" ≠ Σ Sonnenstunden·60 (±5 min, nur Roh-Tabelle); „kein Regen" bei Regensumme ≥ 0.1 mm (#808). |
| **Lokalisierung** (AC-5) | `_check_localization` | Englische Spaltenköpfe (Gust/Rain/Sun/Feels/Cloud/Thunder/Visib/Humid) in der deutschen Mail; Homograph „Wind" ausgenommen (#94). |

Der Mobile-Vertrag (#831) wird zusätzlich im Matrix-Test über `_data_cells_mobile()`
in **beiden** Auflösungen geprüft. Selbsttest: `tests/tdd/test_issue_833_gate.py`
füttert bewusst defekte Mails und beweist, dass das Gate sie rot meldet (kein Mock,
echte MIME-Artefakte).
