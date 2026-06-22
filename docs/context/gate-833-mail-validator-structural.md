# Context: gate-833-mail-validator-structural

## Request Summary

Das kanonische Mail-Acceptance-Gate (`briefing_mail_validator.py`) prüft die zugestellte
Briefing-Mail nur als **MIME-String** — es rendert nie, kennt keine Viewport-Breite und
vergleicht nie die Konsistenz *zwischen* den Aussage-Ebenen. Dadurch sind eine ganze
Defekt-Klasse (#807 Ebenen-Widerspruch, #808 Sonne-0-min, #831 Mobil-Einfach wirkungslos,
#94 EN-Spaltenköpfe, #794 Mobile-Overflow) durchgerutscht. **Ziel von #833:** das Gate
strukturell so erweitern, dass diese **Klasse** künftig **vor** dem Versand rot wird —
NICHT die Einzelbugs fixen (die laufen separat, Tests existieren bereits).

## Scope-Abgrenzung (wichtig)

- **IN Scope:** Erweiterung von `.claude/hooks/briefing_mail_validator.py` (+ ggf. neues
  Render-Hilfsmodul) und der Matrix-Vertragstest (#811) um Viewport-Abdeckung.
- **OUT of Scope:** Die Einzelbugs #807/#808/#831/#94/#794 fixen. Deren RED-Tests
  (`tests/tdd/test_issue_807_reproduction.py`, `_808_sonne_pill.py`, `_831_mobile_einfach.py`)
  existieren bereits und gehören NICHT zu diesem Workflow.
- Der Bundle-Teil #851/#852 ist bereits committet (f76dd083); nur #833 steht aus.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/briefing_mail_validator.py` | **Das Gate.** 414 LoC, stdlib-only, String-basiert. `_validate_full` (103), `_check_plausibility` (131) — hier setzt die Erweiterung an. |
| `tests/tdd/test_issue_811_mode_matrix.py` | Modus-Matrix-Vertragstest. `_data_cells()` (139-144) sucht NUR `<table class="resp">` (Desktop) — Mobile-Pfad ungetestet. AC-2 von #833. |
| `.claude/hooks/renderer_mail_gate.py` | Commit-Gate. Bindet 2 Nachweise (Matrix-Test + Validator-Log) via sha256/`validated_at` (Anti-Stale). `_validator_log_ok` (170-210). |
| `.claude/hooks/e2e_browser_test.py` | **Playwright-Muster-Vorbild.** `sync_playwright`, `chromium.launch(headless=True)`, `new_page(viewport={...})`, `page.content()`. |
| `tests/tdd/test_briefing_mail_inhalt.py` | Multi-Viewport-Vorbild: schreibt HTML in tmp, `page.goto(f"file://{p}")`, `new_context(viewport={"width":375,"height":812})`, `page.evaluate(...)`. `_strip_media_blocks` (103-128). |
| `src/output/renderers/email/html.py` | Renderer. Aussage-Ebenen + Desktop/Mobile-Umschaltung (siehe unten). |
| `src/output/renderers/email/helpers.py` | Pill-Logik (`_pill_for_metric` 1004-1193), `fmt_val` (410-555), Sonne-Pille (1076-1081). |
| `docs/reference/mail_validators.md` | Doku der drei Mail-Gates — muss nach der Erweiterung aktualisiert werden. |

## Aussage-Ebenen & Responsive-Umschaltung (Render-Targets)

**CSS-Breakpoint: 601px** (`html.py:676-685`). `.desktop-only` (display:block ≥601px /
none ≤600px) vs `.mobile-compact` (none ≥601px / block ≤600px). Render-Test-Targets laut
AC-1: **≥1000px** (Desktop) und **≤390px** (Mobile) — beide eindeutig jenseits des Breakpoints.

| Ebene | Funktion | Datei:Zeile | Hinweis |
|-------|----------|-------------|---------|
| Ein-Zeiler-Spitze (Header/Stats) | `render_html` stats_grid | `html.py:268-305` | Segmente/Distanz/Höhe |
| Überblick-Pills | `build_metrics_summary_pills` / `_pill_for_metric` | `helpers.py:1196-1237` / `1004-1193` | Spitzenwert je Metrik (max Wind/Böen, Sonne-min) |
| Desktop-Stundentabelle | `_render_html_table` (`<table class="resp">`, `data-label`) | `html.py:84-112` | Ampel-Emoji bei `indicator_keys` |
| Mobile-Monospace-Raster | `_render_mobile_compact_rows` (`<pre>`, festbreite Spalten) | `html.py:116-204` | Einfach→fällt auf Desktop-Tabelle zurück (post #831); Roh→Monospace |
| Sonne-X-min-Pill | `_pill_for_metric` sunshine-Case | `helpers.py:1076-1081` | `int(round(total*60))` min — Quelle für AC-4-Gegenprobe |

Spaltenköpfe (AC-5): aus `metric_catalog.py` `col_label` — heute teils englisch (`Time`,
`Feels`, `Wind`, `Gust`, `Rain`, `Sun` hardcodiert/Katalog).

## Existing Patterns

- **Headless-Render:** HTML in tmp-Datei schreiben → `page.goto(f"file://{path}")` →
  `page.wait_for_load_state("networkidle")` → `page.evaluate(...)` / `page.content()`.
  Viewport via `new_context(viewport={...})` oder `new_page(viewport={...})`.
- **Playwright installiert:** `pyproject.toml:70` (`playwright>=1.57.0`), Browser in
  `~/.cache/ms-playwright` (chromium-1223 etc.) vorhanden.
- **Validator-Konvention:** Exit 0 (bestanden) / 1 (Spec-Verletzung) / 2 (technischer
  Fehler). YAML-Log fail-soft (`_write_validation_log`). Marker-Header-Dispatch.
- **Anti-Stale-Gate:** `renderer_mail_gate` bindet Nachweise an sha256(Mail-Dateien) +
  `validated_at > mtime`. Jede Renderer-Änderung erzwingt erneuten Lauf.

## Dependencies

- **Upstream (was das Gate nutzt):** IMAP-Fetch der zugestellten Staging-Mail; stdlib
  `email`. NEU: Playwright (sync API) + Chromium-Headless für Render.
- **Downstream (was das Gate gatet):** `renderer_mail_gate.py` blockiert `git commit` auf
  Mail-Renderer-Dateien bis Validator-Log frisch+grün. CLAUDE.md macht den Validator-Lauf
  zur Pflicht vor „E2E bestanden".

## Risks & Considerations

1. **False-Positive-Gefahr (AC-3/AC-4):** Ebenen-Konsistenz braucht semantisches Parsen
   (Peak-Wind aus Ein-Zeiler vs Pill vs Tabellen-Max). Toleranzen müssen kalibriert sein,
   sonst Dauer-Rot → Gate-Erosion. **Anti-Falle:** großzügig kalibrieren, gegen die echte
   gerenderte Staging-Mail testen.
2. **Stdlib-only-Bruch:** Validator ist heute stdlib-only/isoliert ladbar. Playwright macht
   ihn schwergewichtig. Entscheidung nötig: Render-Checks als Pflicht, aber bei fehlendem
   Browser **Exit 2** (technischer Fehler), nicht Exit 1 (False-Negative vermeiden).
3. **AC-6 ist das Herzstück:** Jede neue Prüfung MUSS durch eine bewusst defekte Mail
   bewiesen rot werden — sonst ist die Erweiterung selbst unverifiziert (vgl. Memory
   „QA-Versagensanalyse ist der wesentliche Schritt").
4. **#811-Matrix-Test koppeln:** AC-2 verlangt den Roh/Einfach-Vertrag in BEIDEN Viewports.
   `_data_cells()` muss zusätzlich die `.mobile-compact`-Variante durchlaufen.
5. **LoC-Limit 250:** Render-Logik + 6 Check-Kategorien + Self-Test-Fixtures sprengen das
   evtl. — vorab mit PO klären statt Override.
6. **Mocks verboten:** Render gegen ECHTES gerendertes HTML (Playwright), Self-Test gegen
   echte konstruierte HTML-Artefakte — kein `Mock()`.

## Analysis

### Type
Rework / Tooling-Härtung (QA-Gate). Kein User-facing Feature.

### Altbug-Status (materiell für Enforcement)
- **#807 (Ebenen-Widerspruch) CLOSED** 2026-06-16 — AC-3-Check ist Regressions-Wächter, live grün erwartet.
- **#808 (Sonne 0 min) CLOSED** 2026-06-19 — AC-4-Check, live grün erwartet.
- **#831 (Mobil-Einfach) CLOSED** 2026-06-15 — AC-2-Check, live grün erwartet.
- **#94 (EN-Spaltenköpfe) OPEN** — AC-5-Check meldet die Live-Mail **korrekt rot** (Header
  „Gust/Rain/Sun" sind live englisch). Das ist das Gate, das seine Arbeit tut.
- **#794 (Mobile-Lesbarkeit) OPEN** — Overflow; AC-1 deckt nur Viewport-Existenz ab.

### AC-3-Klärung: „Ein-Zeiler" = Header-Schlagzeile
Aus #807: die drei Ebenen sind **Header-Schlagzeile** („Böen bis 84 km/h ab 14:00"),
**Metriken-Überblick-Pills** und **Stundentabelle** — NICHT der Trip-Stats-Grid
(Distanz/Höhe). AC-3 vergleicht je Metrik **Spitzenwert + Zeitbezug** über die Ebenen, die
für diese Metrik existieren. #807-Fix vereinheitlichte das Fenster → Ebenen sollten jetzt
(nahezu) identisch sein; die Toleranz deckt nur Anzeige-Rundung ab.

### Technischer Ansatz pro AC (Tech-Lead-Entscheidungen)
| AC | Ansatz | Enforcement |
|----|--------|-------------|
| AC-1 Render | Lazy-Import Playwright in `_check_rendered()`; HTML-Part → tmp-Datei → `page.goto(file://)` bei 1000px+390px; Sichtbarkeit via `page.evaluate(offsetHeight/getComputedStyle)`, nicht nur `page.content()`. Fehlt Browser → **Exit 2** (technischer Fehler), nie Exit 1. | hart |
| AC-2 Vertrag beide Viewports | Matrix-Test (`test_issue_811`) um `_data_cells_mobile()` erweitern (`.mobile-compact` `<pre>`/Tabelle), CSS-visibility-aware via `offsetHeight`. Gate macht Mobile-Smoke (Mobile-Block sichtbar + Stundendaten). | hart |
| AC-3 Ebenen-Konsistenz | Regex-Parser: Spitzenwert+Zeit aus Header-Schlagzeile, Pills, Tabellen-Max je Metrik; nur vorhandene Ebenen vergleichen. Toleranz eng genug für #807-Klasse (Δ≥4), locker für Rundung (±1 Ganzzahl / ±3 km/h). | hart (live grün, #807 fix) |
| AC-4 Plausibilität | Sonne: Σ Tabellen-Sonnenstunden·60 vs Pill-„Sonne X min" (nur Roh-Tabelle numerisch; Einfach-Emoji → skip). Regen: „kein Regen"-Pill ⇒ Tabellen-Σ < 0.1 mm. | hart (live grün, #808 fix) |
| AC-5 Lokalisierung | Blacklist eindeutiger EN-Begriffe (Gust/Rain/Sun/Feels/Cloud/Thunder/Visib…), **Homographe wie „Wind" ausgenommen**; `<th>` + Mobile-Header-Zeile extrahieren. | hart (meldet #94 live rot — gewollt) |
| AC-6 Selbsttest | `tests/tdd/test_issue_833_gate.py`: konstruierte defekte `email.message.Message` (Sonne-Widerspruch, EN-Header, Ebenen-Mismatch) → `validate_message` muss Exit-1/Fehlerliste liefern. **Kein Mock** — echtes konstruiertes Artefakt. String-basiert (kein Playwright nötig für die String-Checks). | — |

### Enforcement-Modell (Tech-Lead-Entscheidung, KEIN Warning-Theater)
Alle Checks sind **hart** (Exit 1). **Kein** Warning-/Soft-Modus — ein ignorierter Warn-Hinweis
wäre genau das „Sicherheits-Theater", das #833 anprangert. Verifikation der Gate-Fähigkeit
läuft über den **Self-Test (AC-6)** gegen bewusst defekte Artefakte, nicht über die Live-Mail.
**Konsequenz:** AC-5 meldet die Live-Mail rot, bis #94 (EN-Header → Deutsch) gefixt ist — d.h.
#94 wird damit zum nächsten Pflicht-Schritt für Mail-Renderer-Arbeit. Das ist das Gate, das
funktioniert; #94-Fix entsperrt sich selbst (deutsche Header machen AC-5 grün).

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | Neue Checks AC-1..AC-5 in `_validate_full`; `_check_rendered` (Playwright lazy); Helper-Parser. |
| `tests/tdd/test_issue_811_mode_matrix.py` | MODIFY | `_data_cells_mobile()` + Mobile-Viewport-Assertions (AC-2). |
| `tests/tdd/test_issue_833_gate.py` | CREATE | Self-Test (AC-6): defekte Artefakte → Gate rot. |
| `docs/reference/mail_validators.md` | MODIFY | Doku der erweiterten Checks. |

### Scope Assessment
- Files: 4 (2 MODIFY Code, 1 CREATE Test, 1 Doku)
- Geschätzte LoC: ~195 Gate + ~30 Matrix-Test = **~225** (Doku/Tests zählen tlw. nicht) — **knapp unter 250**. Falls Implementierung sprengt: PO fragen (kein Override).
- Risk Level: **MEDIUM** — False-Positive-Gefahr (AC-3/AC-4 Toleranz) und Headless-Flakiness sind die Hauptrisiken.

### Risiken
1. **False-Positives AC-3/AC-4** (Toleranz-Kalibrierung) → Gate-Erosion. Mitigation: gegen echte Staging-Mail kalibrieren, eng-aber-rundungstolerant.
2. **Playwright-Flakiness** im Commit-Gate → Exit 2 (nicht 1) bei Render-Fehler; `timeout` in `goto`.
3. **Stdlib-Bruch** → Lazy-Import, Validator bleibt ohne Playwright ladbar (nur Render-Checks dann Exit 2).

### Open Questions
- [ ] AC-5 redet die Live-Mail rot bis #94 gefixt (gewollt). Heads-up an PO, keine Blocker-Frage.

## Existing Specs / Referenzen

- `docs/context/bundle-851-852-833-email-fidelity.md` — Vor-Kontext (Bundle), #833-ACs.
- `docs/reference/mail_validators.md` — Single Source of Truth der drei Gates.
- Issue #811 (Modus-Matrix), #564 (Selftest-Muster), Memory `feedback-qa-failure-analysis`.
