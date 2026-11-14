# Context: fix-2777-startseite-en-bilder

## Request Summary
Die öffentliche Startseite (`/`, ausgeloggt) zeigt in Englisch dieselben drei Beispielbilder wie in Deutsch (Briefing-Mail, Telegram, Alarm); die Bilder enthalten deutsche Texte. Ziel: eigene englische Bilder unter `frontend/static/landing/en/`, `en/start.json` zeigt darauf, ein Test sichert, dass `de` und `en` verschiedene, existierende Dateien referenzieren. Issue #2777 (Epic #2644, Nachtrag zu A2 #2681; Abhängigkeit #2681 ist geschlossen).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/i18n/messages/en/start.json` (Z. 22/25/28) | `start.mail.src`, `start.telegram.src`, `start.alarm.src` → auf `/landing/en/*.png` umstellen |
| `frontend/src/lib/i18n/messages/de/start.json` | bleibt auf `/landing/*.png` (Invariante) |
| `frontend/static/landing/{briefing-mail,briefing-telegram,alarm}.png` | deutsche Originale (#2520), 22–84 KB |
| `frontend/src/routes/_start/Startseite.svelte` (Z. 10–12, 59–61) | liest `$t('start.*.src')`, `{#each … (b.src)}` — keine Codeänderung nötig |
| `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` (Z. 60–70) | AC-7 aus #2520: Datei existiert, < 200 KB, Alt-Text — prüft nur den **de**-Katalog |
| `frontend/src/lib/i18n/__tests__/glossar_konformitaet_de_en.test.ts` (Z. 42–49) | Ausnahme `start.alarm.src` (Pfad enthält „alarm"); bleibt gültig bei `/landing/en/alarm.png` |
| `frontend/src/hooks.server.ts` | `/landing/*` wird als statische Datei vor dem Hook ausgeliefert (Prod `/landing/alarm.png` → 200); Unterordner `en/` ändert daran nichts |
| `frontend/src/lib/pwa/ansicht.test.ts` (Z. 12) | `/landing/alarm.png` als Nicht-Ablage-Pfad im Service Worker — Unterordner analog |

## Existing Patterns
- **Herkunft der deutschen Bilder (Commit d2281a402, #2520):** aus echten Renderern mit Fixture-Daten, nicht aus zugestellten Mails: Briefing-Mail aus `tests/fixtures/issue_974_evening_night_mail.html`, Alarm aus `official_alert_render_snapshot_1944.json` (`trip_html`), Telegram aus `render_telegram_bubbles()` mit Testsegment. Kein Erzeugungsskript im Repo.
- **Issue-Text verlangt** Bilder aus echt zugestellten englischen Staging-Mails des `en`-Testnutzers (A2 #2681: Subadresse `+en`, `scripts/staging_e2e_user_en.py`, Validatoren lesen beide Sprachen aus dem Stalwart-Testpostfach). Staging-Mailweg-Störung #2774 ist geschlossen.
- Renderer sind seit P2 (#2664), P6 (#2668), P7 (#2669) sprachfähig (`language=en`).
- Alt-Texte (en) beschreiben den Inhalt konkret: Alarm = „storm warning (level orange) and heat warning (level yellow) with validity period and affected segment" → das englische Alarm-Bild muss genau diesen Inhalt zeigen (oder Alt-Text wird angepasst).

## Dependencies
- Upstream: Renderer (Python `src/`), Staging-`en`-Nutzer (#2681), Playwright/Chromium für Screenshots.
- Downstream: nur die öffentliche Startseite; kein anderer Konsument der `start.*.src`-Schlüssel.

## Existing Specs
- `docs/specs/modules/oeffentliche_startseite_2520.md` — AC-7 (Screenshots, Alt-Texte, Dateiexistenz), Punkt 5 (statische Assets, Testdaten, keine Personendaten), Punkt 6 (keine SMS-Screenshots)
- `docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md` — Staging-Nutzer `en`
- `docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md` — Katalog pro Sprache

## Risks & Considerations
- **Personendaten:** Screenshots dürfen keine echten Empfänger/Adressen zeigen (öffentliches Repo, öffentliche Seite) — Sichtprüfung vor Commit; Staging-Testnutzer-Adresse im Mail-Kopf darf nicht im Bild stehen (nur Mail-Körper zuschneiden).
- **Gleichwertigkeit:** englische Bilder sollen inhaltlich den deutschen entsprechen (gleiche Bildart, ähnlicher Ausschnitt), damit Alt-Texte stimmen.
- **Größe:** < 200 KB pro Datei (bestehende Prüfung); neuer Test muss auch den `en`-Katalog abdecken.
- **Restdeutsch im Bild:** wenn der englische Render noch deutsche Wörter enthält, ist das ein Renderer-Befund (eigenes Issue), kein Grund, die Bilder zu retuschieren.
- Mail-Renderer-Commit-Gate greift nicht (keine Renderer-Änderung, nur statische PNGs + Katalog).

## Analysis

### Type
Bug (Sprach-Lücke auf der öffentlichen Startseite; Nachtrag zu A2 #2681)

### Befund zur Erzeugung
Die deutschen Bilder (#2520) stammen aus **statischen deutschen Fixture-Snapshots** (`issue_974_evening_night_mail.html`, `official_alert_render_snapshot_1944.json`) bzw. aus `render_telegram_bubbles()`. Die Snapshots sind fertiges deutsches HTML und lassen sich nicht auf Englisch umrendern. Alle drei Renderer sind aber sprachfähig: `render_official_alert_html(..., lang="en")` (`src/output/renderers/alert/official_alerts.py:1703`), `render_telegram_bubbles(..., lang="en")` (`src/output/renderers/narrow.py:699`), Briefing-Mail über die Trip-Report-Pipeline mit `language=en`.

### Technischer Ansatz (Tech-Lead-Entscheidung)
1. **Briefing-Mail:** echt zugestellte englische Staging-Briefing-Mail des `en`-Testnutzers (#2681, Stalwart-Testpostfach) — nur Mail-Körper, kein Kopf mit Empfängeradresse; per Playwright/Chromium als PNG.
2. **Alarm:** `render_official_alert_html(lang="en")` mit denselben Warnungen wie das deutsche Bild (Sturm Stufe orange + Hitze Stufe gelb, Gültigkeit, betroffenes Segment) — ein amtlicher Alarm lässt sich auf Staging nicht auf Bestellung auslösen; der Renderer ist genau der Code, der die zugestellte Mail baut. Alt-Text bleibt damit wahr.
3. **Telegram:** `render_telegram_bubbles(lang="en")` mit Testsegment analog zum deutschen Bild (Telegram landet nicht im Mail-Testpostfach).
4. Erzeugung als kleines, wiederholbares Skript `scripts/landing_screenshots.py` (de-Pfad unverändert, en-Ausgabe nach `frontend/static/landing/en/`), damit eine spätere Renderer-Änderung die Bilder reproduzierbar erneuern kann. Abweichung vom Issue-Wortlaut („aus zugestellten Mails“) nur beim Alarm/Telegram, begründet oben; im Issue dokumentieren.
5. `en/start.json`: `start.{mail,telegram,alarm}.src` → `/landing/en/{briefing-mail,briefing-telegram,alarm}.png`. `de/start.json` unverändert.
6. Sichtprüfung jedes PNG vor Commit: keine Personendaten, kein Restdeutsch (Restdeutsch = Renderer-Befund, eigenes Issue, nicht retuschieren), < 200 KB.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/static/landing/en/briefing-mail.png` | CREATE | englische Briefing-Mail |
| `frontend/static/landing/en/briefing-telegram.png` | CREATE | englische Telegram-Nachricht |
| `frontend/static/landing/en/alarm.png` | CREATE | englischer Alarm (Sturm orange, Hitze gelb) |
| `frontend/src/lib/i18n/messages/en/start.json` | MODIFY | drei `src`-Pfade auf `/landing/en/` |
| `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` | MODIFY | AC-7 für **beide** Kataloge; neu: `en`-Pfad ≠ `de`-Pfad je Bild, `en` liegt unter `/landing/en/`, beide Dateien existieren, < 200 KB |
| `scripts/landing_screenshots.py` | CREATE | reproduzierbare Erzeugung (Renderer → HTML → Playwright-PNG) |
| `docs/specs/modules/oeffentliche_startseite_2520.md` | MODIFY | Nachtrag: Bilder je Sprache |

Keine Änderung an `Startseite.svelte`, `hooks.server.ts` (statische Auslieferung von `/landing/en/*` wie `/landing/*`), Glossar-Ausnahme `start.alarm.src` bleibt gültig.

### Scope Assessment
- Files: 7 (3 Binär)
- Estimated LoC: +~150 / -3
- Risk Level: LOW — nur statische Bilder und drei Katalogzeilen der ausgeloggten Startseite; kein Renderer-, Versand- oder Datenpfad.

### Test-Strategie
Kern (node --test): Katalog-Test rot vor Umstellung (en == de). Mutation: en-Pfad zurück auf de → rot; en-Datei löschen → rot. E2E auf Staging: ausgeloggt mit `en` die Startseite laden, die drei `<img>` zeigen `/landing/en/…` und liefern 200.

### Dependencies
#2681 (en-Staging-Nutzer) geschlossen; #2774 (Staging-Mailweg) geschlossen. Playwright/Chromium lokal vorhanden.

### Open Questions
- keine (Produktentscheidung liegt nicht vor; Herkunftsweg ist technisch entschieden)
