# Context: fix-1306-mail-render-bundle

## Request Summary
Issue #1306 [triage:a]: Die 6 Mail-/Render-Befunde aus der Rot-Triage beheben. Tiefenanalyse (2 Sonnet-Agenten, 2026-07-18, alles file:line-belegt) korrigiert 3 der ursprünglichen Diagnosen: dort ist das PRODUKT korrekt und der xfail-Test stale.

## Befund-Lage nach Verifikation

| # | Befund | Verifiziertes Urteil | Fix |
|---|---|---|---|
| 1 | **Profil-Signatur fehlt in HTML** | ECHT. `render_html` (html.py:784) liest `profile` nie; alle Bausteine fertig in profile_signature.py (4 Profile: Akzentfarbe/Icon/Eyebrow/SVG); plain.py:105 = Vorbild | ~10-12 LoC html.py: `sig = profile_signature(profile)` + Eyebrow-Block VOR bestehendem `_eyebrow("{RT}-BRIEFING")` in left_col (Z.880-889); Eyebrow-Text in G_ACCENT, SVG trägt Profil-Akzent. PLUS: Route-Titel-div zu `<h1>` (Z.884-885, semantisch, visuell identisch — macht ac6 grün, bewusste Entscheidung). preview_email.py braucht KEINE Änderung |
| 2 | Thunder-Spalte Heute-Block | PRODUKT OK (Horizon-Filter liefert korrekt Thdr/Wind/Temp je Tag, per Repro belegt). Test stale: erwartet `<th>Label</th>` ohne das seit #900/#911 vorhandene style-Attribut | Test: 6 Assertions auf attributtolerantes Regex (`<th[^>]*>`); ~6 LoC, KEIN Produktcode |
| 3 | wind_max_kmh JSON null | PRODUKT OK (Serialisierung liefert null, per Repro belegt). Test-Fixture-Drift: `_KeyedFakeProvider` ohne `enrich_snow`-Param, dadurch TypeError und leere Results | Test: 1 Zeile Signatur (Vorbild test_stage_weather_parity.py:53-60) |
| 4 | SMS-Präfix bug_497 | DOPPELT STALE: Bug bereits d6d8a193 gefixt UND Codepfad in #954 entfernt; Test-Arrange hängt an gitignorten Realdaten. Aktuelles Verhalten (Etappen-Kompaktierung zu E{N}, verschluckt Custom-IDs wie KHW_10) ist bewusstes #1260-v2.0-Design | **Tech-Lead-Entscheid:** Test LÖSCHEN (Test-Politik: prüft überholtes Verhalten eines entfernten Pfads). Custom-ID-in-SMS wäre neues Feature, nicht Bug — in #1306 dokumentieren |
| 5 | TripReportConfig-Feld unklassifiziert | ECHT: `telegram_style` (models.py:760, #1260) fehlt in beiden Listen; wirkt nachweislich nicht auf email_html/plain | 1 Dict-Eintrag RENDER_NEUTRAL (report_config_resolver.py nach Z.72) mit Begründungstext |
| 6 | Mobile-Breakpoint | TEILWEISE: `min-width:601px` ist bewusste #799-Mobile-First-Architektur (e44df5b9 — Gmail-Web-Fallback!); nur die Zahl weicht ab | 3 Zeichen: 601 auf 600 in html.py:1424. NIEMALS Richtung invertieren (regressiert #799) |

## Pflicht-Nacharbeiten (aus Analyse 1)
- 5 Golden-HTML-Fixtures neu einfrieren (`tests/golden/email/regenerate.py`) — Header-Änderung invalidiert Byte-Vergleich zwangsläufig. Dabei Fixture-Bug arlberg-winter-morning beheben (Docstring sagt wintersport, übergibt aber kein profile — nach Fix zeigt es sonst ALLGEMEIN; profile explizit übergeben).
- `test_ac4_255` sinnwahrend umschreiben (prüft toten `class="header"`-Selektor; Zweck „Akzent nie als Header-Hintergrund" via G_HEADER_BG-Anker erhalten).
- xfail-Marker der grün werdenden Tests entfernen (ac6 wird durch die h1-Einführung ebenfalls grün).
- tests/visual/test_issue_956: Fragilität notiert (BRIEFING-Substring-Query matcht künftig den neuen Eyebrow zuerst) — Assertion bleibt grün; Pixel-Diff-Diagnosewert steigt erwartbar (kein Gate).

## Sichtbare Produktänderung (für PO-Freigabe zentral)
Jede künftige Briefing-Mail zeigt oben die Profil-Kopfzeile (SVG-Icon + Label in Profilfarbe, z. B. Schneeflocken-SVG + WINTERSPORT · PISTE in Blau). Da das Standard-Profil WINTERSPORT ist und der Scheduler das Profil durchreicht, erscheint das sofort in realen Mails. Genau das war seit #241/#255 spezifiziert und ist in Plain-Mails längst live — HTML zieht nach.

## Gates & Risiken
- **Renderer-Mail-Gate #811 (un-überspringbar):** html.py ist Mail-Inhalts-Datei — vor Commit: test_issue_811_mode_matrix grün + frischer briefing_mail_validator-Lauf (echte Staging-Test-Mails via for_testing(), IMAP-Prüfung Test-Postfach). Validator-Risiko geprüft: X-GZ-Header MIME-seitig, kein Konflikt; die th-Regex des Validators ist attributtolerant.
- Parallele Sessions: html.py ist heiße Datei (#911/#956-Historie) — vor Commit fetch+ff + Diff-Kontrolle.
- LoC: Produkt ~15, Tests/Fixture-Anpassungen moderat; Goldens generiert (zählen nicht).

## Retro-Notiz (für #1199/Gedächtnis)
2b-xfail-reasons wurden teils aus historischer Befund-Prosa übernommen, ohne den AKTUELLEN Fehlschlag zu verifizieren (Befunde 2/3/4 = Beispiele). Regel für künftige Triagen: xfail-reason erst nach Blick auf die tatsächliche aktuelle Assertion-Meldung formulieren.
