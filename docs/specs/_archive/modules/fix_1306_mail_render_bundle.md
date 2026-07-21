---
entity_id: fix_1306_mail_render_bundle
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [email, mail-render, profile-signature, issue-1306, bugfix, rot-triage-bundle-1]
---

<!-- Issue #1306 [triage:a] — Bundle 1 der Rot-Triage (Scheibe 2b, Issue #1211b).
     Tiefenanalyse (2 Sonnet-Agenten, 2026-07-18, file:line-belegt) in
     docs/context/fix-1306-mail-render-bundle.md — Single Source dieser Spec. -->

# Issue #1306 — Mail-Render-Bundle: Profil-Signatur in HTML + 3 stale Tests + 2 kleine Produktkorrekturen

## Approval

- [ ] Approved

## Purpose

Sechs Rot-Triage-Befunde aus Issue #1211b werden final behoben: ein echter
Produktbug (Profil-Signatur fehlt in `render_html`), zwei winzige, bewusst
begrenzte Produktkorrekturen (unklassifiziertes Config-Feld, Mobile-Breakpoint
um 1px daneben) sowie drei Tests, die nach Verifikation als stale erkannt
wurden (Produktverhalten ist korrekt, Test prüft eine überholte Erwartung).
Eine siebte, doppelt überholte Testdatei wird gelöscht statt gefixt.

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `def render_html(...)` (Z.766-793), Header-Aufbau `left_col`
  (Z.880-889), Mobile-Media-Query (Z.1424)
- **File:** `src/services/report_config_resolver.py`
- **Identifier:** `RENDER_NEUTRAL: dict[str, str]` (Z.41-73)

Vorbild-Code (bereits korrekt, dient als Referenz beim Fix):
`src/output/renderers/email/plain.py:105` (`sig = profile_signature(profile)`
+ Prefix-Zeile) sowie `src/output/renderers/email/profile_signature.py`
(alle 4 Profil-Signaturen fertig implementiert, Issue #241).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/profile_signature.py::profile_signature()` | Funktion (#241) | Liefert `accent_hex`/`icon`/`eyebrow` je `ActivityProfile`; wird in `render_html` bisher nie aufgerufen |
| `src/output/renderers/email/plain.py::render_plain()` | Funktion | Bereits korrektes Vorbild für den Aufrufmuster in `render_html` |
| `src/app/profile.py::ActivityProfile` | Enum | Eingabetyp `profile`-kwarg, bereits in `render_html`-Signatur (Z.784) vorhanden aber ungenutzt |
| `docs/specs/modules/issue_241_email_profile_pipeline.md` | Spec (Referenz) | Ursprüngliche Design-Vorgabe: Profil-Marker (Akzentfarbe, Eyebrow, Icon) im Header, Approved 2026-05-17 |
| `docs/specs/modules/issue_255_email_profil_signaturen.md` | Spec (Referenz) | Folge-Spec zu Header-Redesign (`class="header"` durch zweispaltigen Header ersetzt, #884/#890) — Grund, warum `test_ac4_255` einen toten Selektor prüft |
| `tests/golden/email/regenerate.py` | Tooling | Erzeugt die 5 HTML-Golden-Fixtures neu; wird unverändert ausgeführt, Fixture-Aufruf für `arlberg-winter-morning` wird korrigiert |
| Renderer-Mail-Gate #811 (`renderer_mail_gate.py`) | Pre-Commit-Gate | `html.py` ist Gate-Datei — Commit blockiert ohne frischen `test_issue_811_mode_matrix` + `briefing_mail_validator`-Lauf |
| CLAUDE.md „Trip/Ortsvergleich-Code-Teilung" | Policy | Betrifft hier nicht direkt (reiner Trip-Renderer), aber `render_html` wird auch von Compare-Pfaden über gemeinsame Bausteine genutzt — keine Compare-eigene Änderung nötig |

## Estimated Scope

- **LoC:** Produkt ~14 (html.py ~12 + report_config_resolver.py +1 +
  html.py-Breakpoint 1 Zeichen-Diff auf bestehender Zeile); Tests moderat
  (5 Dateien MODIFY, 1 Datei DELETE, 5 Golden-Fixtures generiert/regeneriert
  — zählen nicht gegen das LoC-Limit)
- **Files:** 2 Produktdateien, 6 Testdateien (5 MODIFY + 1 DELETE), 5 Golden-
  Fixtures (generiert)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/email/html.py` | MODIFY | `profile_signature(profile)` aufrufen + Eyebrow-Block (Akzent-Hex, Icon-SVG, `class="eyebrow"`) VOR bestehendem `_eyebrow("{RT}-BRIEFING")` in `left_col` einfügen; Route-Titel-`<div>` (Z.884-885) zu `<h1>` (semantisch, visuell identisch); Mobile-Breakpoint `601` → `600` (Z.1424) |
| `src/services/report_config_resolver.py` | MODIFY | `telegram_style` als neuer Eintrag in `RENDER_NEUTRAL` mit Begründungstext (nach Z.72) |
| `tests/tdd/test_email_profile_pipeline.py` | MODIFY | 5 `xfail`-Marker entfernen (Z.69/114/132/170/211), inkl. ac6 |
| `tests/tdd/test_issue_255_profil_signaturen.py` | MODIFY | 2 `xfail`-Marker entfernen; `test_ac4_255_accent_not_as_header_background` sinnwahrend umschreiben (toter `<div class="header"` Selektor → `G_HEADER_BG`-Anker, Zweck „Akzent nie als Header-Hintergrund" bleibt erhalten) |
| `tests/tdd/test_issue_257_trip_briefing_polish.py` | MODIFY | 2 `xfail`-Marker entfernen (AC-5 Breakpoint, AC-8 `preview_email.py --profile`) |
| `tests/tdd/test_report_config_render_contract.py` | MODIFY | `xfail`-Marker (Z.265) entfernen — nach Fix sind alle 28 `TripReportConfig`-Felder klassifiziert |
| `tests/tdd/test_horizon_filter.py` | MODIFY | `xfail`-Marker (Z.156) entfernen; th-Assertions auf attributtolerantes Regex `<th[^>]*>` umstellen (Produkt ist korrekt, Test war stale seit #900/#911) |
| `tests/tdd/test_stage_weather_endpoint.py` | MODIFY | `xfail`-Marker (Z.107) entfernen; `_KeyedFakeProvider` um `enrich_snow`-Parameter ergänzen (Vorbild `test_stage_weather_parity.py:53-60`) |
| `tests/tdd/test_bug_497_preview_content.py` | DELETE | Doppelt überholt: Bug bereits in `d6d8a193` gefixt, Codepfad in #954 entfernt; Test-Arrange hängt an gitignorten Realdaten |
| `tests/visual/test_issue_956_email_pixel_diff.py` | MODIFY (Kommentar) | Fragilitäts-Notiz ergänzen (BRIEFING-Substring-Query matcht künftig zuerst den neuen Eyebrow) — Assertion bleibt unverändert grün, kein Gate-Verhalten |
| `tests/golden/email/regenerate.py` | MODIFY | Aufruf für `arlberg-winter-morning` erhält explizites `profile=ActivityProfile.WINTERSPORT` (Docstring sagt Wintersport, Code übergab bisher kein Profil) |
| `tests/golden/email/gr20-spring-morning-html.txt`, `gr221-mallorca-evening-html.txt`, `gr20-summer-evening-html.txt`, `arlberg-winter-morning-html.txt`, `corsica-vigilance-html.txt` | MODIFY (generiert) | Neu eingefroren nach Header-Änderung — Byte-Vergleich wird durch die Profil-Signatur zwangsläufig invalidiert |

## Implementation Details

**html.py — Profil-Signatur einbauen:** In `render_html` wird
`sig = profile_signature(profile)` aufgerufen (Analogie zu `plain.py:105`)
und im `left_col`-Aufbau (Z.880-889) ein Eyebrow-Block VOR dem bestehenden
`_eyebrow(f"{_rt_upper}-BRIEFING")` eingefügt: `class="eyebrow"`-Element mit
Inline-Style in `sig.accent_hex`, `sig.icon` als `<svg>` (kein Unicode-Glyph
mehr — Outlook-Tofu-Risiko aus #241 damit strukturell vermieden) und
`sig.eyebrow`-Text (z. B. `WINTERSPORT · PISTE`). Ohne `profile`-Argument
liefert `profile_signature(None)` den ALLGEMEIN-Fallback (Grauton-Akzent,
`WETTER-BRIEFING`, Kompass-SVG) — bestehende Aufrufer ohne `profile`-kwarg
crashen nicht und zeigen weiterhin eine valide, nur generische Kopfzeile.

Die bestehende Route-Titel-`<div>` (Z.884-885) wird zu einem `<h1>`-Tag
umgeschrieben — visuell identisch (gleiche Inline-Styles), aber semantisch
korrekt. Diese Umstellung ist notwendig, damit AC-6 aus
`test_email_profile_pipeline.py` (Eyebrow → `<h1>`-Reihenfolge im DOM)
prüfbar wird; ohne `<h1>` gäbe es kein stabiles Anker-Element für den Test.

Der Mobile-Breakpoint (Z.1424, `@media (min-width:601px)`) wird auf `600`
korrigiert. Die Richtung (`min-width`, Mobile-First seit #799/Commit
`e44df5b9`, Gmail-Web-Fallback) bleibt unangetastet — nur der 1px-Fehler
zwischen der 600px-Grenze aus #305 v2 und der hier verbliebenen 601px wird
behoben.

**report_config_resolver.py:** Ein neuer Eintrag `"telegram_style": "..."` in
`RENDER_NEUTRAL` (nach Z.72) mit Begründungstext nach dem Muster der
bestehenden Einträge (z. B. „Steuert den Telegram-Kurzstil-Kanal, nicht den
E-Mail/Plain-Render-Pfad" — `telegram_style` beeinflusst laut #1260 nachweislich
weder `render_html` noch `render_plain`).

**Test-Anpassungen:** Die xfail-Marker wurden bereits in der vorgelagerten
Rot-Triage (Issue #1211b) mit `reason="#1306: ..."` gesetzt und referenzieren
exakt die hier beschriebenen Ursachen — sie werden nach dem jeweiligen Fix
entfernt, nicht neu geschrieben. `test_ac4_255_accent_not_as_header_background`
ist die Ausnahme: der Selektor `html.find('<div class="header"')` findet seit
dem #884/#890-Header-Redesign (zweispaltiger `left_col`/`right_col`-Aufbau)
keine Übereinstimmung mehr — der Test wird auf den `G_HEADER_BG`-Design-Token
als Anker umgeschrieben, der fachliche Zweck („Profil-Akzent erscheint nie als
Header-Hintergrundfarbe") bleibt unverändert erhalten.

## Expected Behavior

- **Input:** `render_html(..., profile=ActivityProfile.WINTERSPORT)` bzw.
  ohne `profile`-Argument
- **Output:** HTML-String mit Eyebrow-Block (Akzent-Hex, SVG-Icon, Label)
  VOR dem `<h1>`-Routentitel; bei fehlendem `profile` erscheint der
  ALLGEMEIN-Fallback statt eines Crashs oder einer leeren Kopfzeile
- **Side effects:** Jede künftig versendete Briefing-Mail zeigt sichtbar eine
  Profil-Kopfzeile (siehe Known Limitations) — reine Darstellungsänderung,
  keine Datenstruktur- oder Inhaltsänderung

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Aktivitätsprofil (alle 4 Profile parametrisiert), When `render_html(profile=...)` rendert, Then enthält das HTML die Profil-Signatur: Akzent-Hex des Profils, Eyebrow-Text (z. B. WINTERSPORT · PISTE), ein `<svg`-Icon und ein `class="eyebrow"`-Element VOR dem `<h1>`-Routentitel — belegt durch die grün werdenden Ex-xfail-Tests aus test_email_profile_pipeline.py (inkl. ac6) und test_issue_255 AC-3.
  - Test: `uv run pytest tests/tdd/test_email_profile_pipeline.py tests/tdd/test_issue_255_profil_signaturen.py -v` — alle vormals xfail markierten Tests laufen ohne `xfail`-Decorator grün durch, kein `xpass`.

- **AC-2:** Given ein Aufruf ohne profile-Argument, When gerendert wird, Then erscheint das ALLGEMEIN-Fallback-Signal (Grauton-Akzent + WETTER-BRIEFING + Kompass-SVG) und keine bestehende Mail-Struktur bricht — Golden-Fixtures werden EINMAL bewusst neu eingefroren (inkl. Korrektur des arlberg-Fixtures auf explizites Wintersport-Profil) und sind danach wieder Byte-stabil.
  - Test: `uv run python tests/golden/email/regenerate.py` einmalig ausführen, danach `uv run pytest tests/golden/email/` zweimal hintereinander grün (Byte-Stabilität, keine Nicht-Determinismus-Reste).

- **AC-3:** Given der Contract-Test test_report_config_render_contract, When `telegram_style` in RENDER_NEUTRAL mit Begründung klassifiziert ist, Then sind alle 28 TripReportConfig-Felder klassifiziert und der Ex-xfail-Test ist grün.
  - Test: `uv run pytest tests/tdd/test_report_config_render_contract.py -v` grün ohne `xfail`-Decorator; Diff zeigt genau einen neuen `RENDER_NEUTRAL`-Eintrag.

- **AC-4:** Given die Mobile-Media-Query, When die Schwelle von 601 auf 600 korrigiert ist (Mobile-First-RICHTUNG aus #799 bleibt unangetastet), Then ist test_issue_257::test_ac5 grün und .desktop-only/.mobile-compact-Verhalten unverändert.
  - Test: `uv run pytest tests/tdd/test_issue_257_trip_briefing_polish.py -v -k ac5` grün; Diff auf `html.py:1424` zeigt ausschließlich `601` → `600`, `min-width` bleibt erhalten (kein `max-width`).

- **AC-5:** Given die drei stale Tests (horizon_filter th-Regex, stage_weather enrich_snow-Fixture, 255-AC-4-Umschreibung), When sie minimal auf das belegte aktuelle Produktverhalten nachgezogen sind, Then sind sie grün, ohne dass eine fachliche Erwartung entfernt wurde; test_bug_497_preview_content.py ist mit dokumentierter Begründung gelöscht (doppelt überholt: Bug gefixt d6d8a193 + Pfad entfernt #954).
  - Test: `uv run pytest tests/tdd/test_horizon_filter.py tests/tdd/test_stage_weather_endpoint.py tests/tdd/test_issue_255_profil_signaturen.py -v` grün; `git status` zeigt `tests/tdd/test_bug_497_preview_content.py` als gelöscht; Commit-Text referenziert `d6d8a193` + `#954`.

- **AC-6:** Given html.py ist eine Renderer-Mail-Gate-Datei (#811), When committet wird, Then liegen frisch vor: test_issue_811_mode_matrix grün UND erfolgreicher briefing_mail_validator-Lauf gegen eine echt zugestellte Staging-Test-Mail — und die Profil-Kopfzeile ist in dieser echten Mail sichtbar (Zahl-für-Zahl-Plausibilität unberührt).
  - Test: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py -v` grün, danach `uv run python3 .claude/hooks/briefing_mail_validator.py` Exit 0 gegen `gregor-test@henemm.com` (Stalwart-Test-Postfach) mit sichtbarer Eyebrow-Zeile in der zugestellten Mail.

## Known Limitations

- **Sichtbare Produktänderung in jeder Mail (gewollt):** Jede künftig
  versendete Briefing-Mail zeigt oben eine Profil-Kopfzeile (SVG-Icon + Label
  in Profilfarbe). Da das Standard-Profil WINTERSPORT ist und der Scheduler
  das Profil durchreicht, erscheint das sofort in realen Mails. Das war seit
  #241/#255 spezifiziert und in Plain-Mails längst live — HTML zieht mit
  dieser Spec nach.
- **visual-956-Fragilität (dokumentiert, kein Gate):** Die BRIEFING-Substring-
  Query in `tests/visual/test_issue_956_email_pixel_diff.py` matcht künftig
  zuerst den neuen Eyebrow-Text statt der bisherigen einzigen Fundstelle.
  Assertion bleibt grün, aber der diagnostische Pixel-Diff-Wert steigt
  erwartbar — das ist notiert, kein blockierendes Gate.
- **Custom-ID-in-SMS ist ein neues Feature, kein Bug:** Der ursprüngliche
  Befund #497 (SMS-Präfix) prüfte ein Verhalten, das seit #1260-v2.0
  bewusstes Design ist (Etappen-Kompaktierung zu `E{N}`, verschluckt Custom-
  IDs wie `KHW_10`). Eine Custom-ID-Erhaltung in SMS wäre eine neue
  Anforderung und ist explizit NICHT Teil dieser Spec.
- **Dual-Modul-/Isolation-Themen bleiben #1308:** Der in derselben
  Rot-Triage gefundene `app.loader` vs. `src.app.loader`-Isolationsbefund
  (Bundle 3) ist ein separates Vorhaben und wird hier nicht mitbehandelt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (lokale Bugfix-Entscheidungen im Rahmen der Rot-Triage
  #1211b, keine neue Systemarchitektur)
- **Rationale:**
  1. **h1-Wiedereinführung als bewusste semantische Entscheidung:** Die
     Route-Titel-`<div>` (Z.884-885) wird zu `<h1>` umgeschrieben, obwohl das
     visuell identisch bleibt (gleiche Inline-Styles). Grund: `<h1>` liefert
     ein stabiles, semantisch korrektes DOM-Ankerelement, das AC-6 (Eyebrow
     → Routentitel-Reihenfolge) erst zuverlässig prüfbar macht. Verworfene
     Alternative: Reihenfolge nur über String-Position im HTML-Text prüfen —
     verworfen, weil das bei künftigen Whitespace-/Attribut-Änderungen
     fragiler wäre als ein Tag-basierter DOM-Test.
  2. **Befund 4 (SMS-Präfix): Test-Löschung statt Fix.** Die
     Etappen-Custom-ID-Kompaktierung zu `E{N}` ist #1260-v2.0-Design, kein
     Bug — der Test prüfte ein bereits zweifach überholtes Verhalten (Bug
     `d6d8a193` gefixt, Codepfad #954 entfernt). Nach CLAUDE.md-Test-Politik
     wird ein Test, der veraltetes Verhalten prüft, gelöscht statt künstlich
     am Leben erhalten. Eine Custom-ID-Erhaltung in SMS bliebe als separates,
     neu zu spezifizierendes Feature offen.
  3. **Breakpoint: Zahl-Korrektur statt Richtungs-Wechsel.** `min-width:601px`
     bleibt `min-width`, nur die Zahl wird auf `600` korrigiert. Verworfene
     Alternative: auf `max-width` umstellen (naheliegend, weil viele
     E-Mail-Clients Desktop-First mit `max-width` arbeiten) — verworfen, weil
     das die bewusste Mobile-First-Architektur aus #799 (Commit `e44df5b9`,
     Gmail-Web-Fallback-Schutz) invertieren und regressieren würde. Diese
     Spec schützt explizit die #799-Architekturentscheidung.

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1306, Bundle 1 der Rot-Triage
  #1211b (Sammelprojekt #1196), verifiziert durch Tiefenanalyse in
  `docs/context/fix-1306-mail-render-bundle.md`.
