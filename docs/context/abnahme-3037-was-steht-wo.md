# Kontext: Abnahme „Was steht wo“ (#3037)

Workflow `abnahme-3037-was-steht-wo`, Issue #3037 (Teil von #2795 / Epic #2791, Baustein B7 aus `docs/specs/modules/feat_3122_was_steht_wo.md` Z. 48).

## Request Summary

Abschlussabnahme der Tabelle „Was steht wo“ im Reiter Wetter (Bau #3122, alle Kinder außer #3364 zu):

1. Ganzseitenvergleich Soll-Bild `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` gegen Staging, Trip und Orte, Computer (1280) und Handy (390), jede Abweichung zugeordnet (behoben oder eigenes Issue).
2. Orte mit genau einem Ort: Bereich heißt „Orte“, kein Text setzt mehrere Orte voraus (ADR-0124 Nr. 10).
3. Handy: bei Orten fünf Haken-Spalten mit Umschaltern nebeneinander (ADR-0124 „Konsequenzen“, Spec #3122 AC-33: 390 px, EN, kein seitliches Scrollen, WCAG AA).
4. Elementlisten-Abgleich `--abnahme` DE+EN grün für den Bereich der Tabelle.
5. „Einstellung = Ausgabe“: Prüfkatalog #3047 für das neue Datenmodell grün; Staging-Nachweis mit Mail-Validatoren `--konfig`.
6. Soll/Ist-Bild an den PO (Mockup links, Staging rechts).

**Abhängigkeit:** #3364 (gregor-zwanzig-4b, Phase 6) ändert die Trip-Karte („nur morgens/abends“-Kennzeichnung) und macht drei `todo`-Fälle des Katalogs grün. Trip-Bild und Katalog-Vollständigkeit erst nach dessen Auslieferung; Orte-Teil und Werkzeuge vorher.

## Related Files

| Datei | Bedeutung |
|---|---|
| `frontend/e2e/ganzseitenaufnahme.ts` | `ganzseite(page, datei)`: Ganzseitenbild, hebt `.h-screen`/Overflow auf, blendet Fixiertes aus, prüft Bildbreite = Viewport |
| `frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts` (Test AC-30 ab Z. 374) + `playwright.2980-c2-bildabgleich.staging.config.ts` | Ganzseite Trip/Orte × DE/EN × 1280/390; Mockup-Kontext per `[data-ctx="trip|orte|ort1"]`; Mockup nur DE |
| `frontend/e2e/was-steht-wo-bildabgleich.staging.spec.ts` + `playwright.3283-wsw-bildabgleich.staging.config.ts` | nur Karte, nur 1280, trip/orte(3)/ort1 × DE/EN, Wegwerf-Abo via `seedAbo(..., {orte:1|3})` (`was-steht-wo.helpers.ts` Z. 26) |
| `scripts/elementliste_abgleich.ts`, `frontend/e2e/elementliste_abgleich_logik.ts` | `npm run elementliste:abgleich -- [--strict] [--abnahme] [--scope wetter/normal] [--sprache en]`; Filter nur je Reiter |
| `scripts/staging_pruefkonto_mockupdaten.py` (`fuehre_seed` Z. 534), `docs/runbooks/staging_pruefkonto_seed.md` | Prüfkonto-Seed: GR221-Trip, Münsterland (3 Orte), archivierter Trip; **kein Ein-Ort-Abo** |
| `tests/fixtures/einstellung_gleich_mail/fallliste_*.json`, `tests/tdd/test_einstellung_gleich_mail_*.py` | Prüfkatalog #3047 (Kern-Schicht); Wächter zählt grün/Ausnahme/offen |
| `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts` Z. 685–740 | drei `todo`-Fälle „nur morgens/abends“ → #3364 |
| `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/email_spec_validator.py` | Validatoren mit `--konfig` (`docs/reference/mail_validators.md` Z. 137–459; Ein-Ort-Fall Z. 423–437) |
| `.claude/tools/staging_mail_pruefen.py` | löst Staging-Mails aus, legt immer drei Orte an, kein `--konfig` |
| `.claude/agents/mockup-bildpruefer.md` | erwartet Mockup-Bild, Staging-Bild (gleicher Viewport/Zustand), Elementlisten-Auszug; max. zwei Runden |

## Existing Patterns

- Ganzseitenbilder: #2980 (ganze Seite) und #3283 (Karte, Kontexte inkl. ort1) — für #3037 zusammenführen: ganze Seite × trip/orte/ort1 × DE/EN × 1280/390.
- Elementliste nur mit Prüfkonto-Login + Seed-IDs (sonst Scheinabweichungen).
- Frühere Abgleichberichte als Vorlage: `docs/artifacts/fix-3192-wetter-dialog-abgleich/abgleich-*.md`, `feat-3151-pruefkonto-abgleich/abgleich-de.md` (Haupt-Checkout; `docs/artifacts/` ist gitignored).
- Bildprüfung mit `mockup-bildpruefer` je Kontext/Breite.

## Dependencies

- Staging (`https://staging.gregor20.henemm.com`), Staging-`.env` (Prüfkonto, Validator-Login), Stalwart-Test-Postfach.
- API `POST /api/briefings/{id}/send?kind=route|vergleich[&report_type=evening]` (`docs/reference/api_contract.md` Z. 980) für Mails mit bekannter Konfiguration.
- #3364 (Trip-Anzeige, Katalog-todo).

## Existing Specs

- `docs/specs/modules/feat_3122_was_steht_wo.md` — AC-21 (Abgleich `--strict` DE/EN, Trip/3 Orte/1 Ort, Bildprüfer ≤2 Runden), AC-27, AC-33 (Handy), AC-35–37 (ein Ort), Z. 318/324 (Validatoren `--konfig`), Z. 354 (Handy am Gerät in #3037).
- `docs/adr/0124-was-steht-wo-eine-tabelle.md` — Nr. 10, „Konsequenzen“ Z. 54, „Folgepflichten“ Z. 55–67.
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md`, `feat_3154_karte_abgleich.md`, `feat_2913_abgleich_ganzseite.md`.

## Lücken (zu bauen)

1. Staging-Playwright-Lauf ganze Seite × trip/orte/ort1 × DE/EN × 1280/390 (Mockup-Gegenbild DE je Kontext und Breite).
2. Ein-Ort-Fall: Wegwerf-Abo (`seedAbo`) genügt für Bild; für Elementliste/Mail ggf. Seed erweitern.
3. Mail-Nachweis mit `--konfig` für Trip, 3 Orte, 1 Ort (Konfig per GET, Versand per API, Validator).
4. Soll/Ist-Zusammensetzung (links Mockup, rechts Staging) für den PO.
5. Veralteter Hinweis `docs/reference/mail_validators.md` Z. 139 („Soll ab #3122 … noch nicht gebaut“).
6. Spec `rework_3036_uebergangsblock_aufloesen.md` steht noch auf `draft`, obwohl #3036 geliefert ist (Nebenbefund).

## Risks

- Ganzseitenvergleich deckt Abweichungen außerhalb der Karte auf (Kopf, andere Karten) → jede braucht einen Besitzer (Issue), nicht „kommt später“.
- Trip-Bild vor #3364-Auslieferung wäre veraltet.
- Elementliste ohne Prüfkonto → Hunderte Scheinabweichungen.
- `staging_mail_pruefen.py` erzeugt drei Orte — Ein-Ort-Mail braucht eigenen Weg.
- Handy „am Gerät“: Agent kann nur 390-px-Viewport prüfen; echtes Gerät sieht der PO über das Bild.

## Analysis

**Type:** Feature (Abnahme mit Prüfwerkzeug; Produktcode nur, falls eine Abweichung in der Karte im selben Workflow behoben wird).

### Affected Files

| Datei | Change | Zweck |
|---|---|---|
| `frontend/e2e/wsw-abnahme-3037.staging.spec.ts` | CREATE (~150 LoC) | Prüfkonto-Login per `/api/auth/login` (Muster `elementliste-abgleich.staging.spec.ts` Z. 382, **nicht** 1895-Setup); Ganzseitenbild Reiter Wetter trip/orte/ort1 × DE/EN × 1280/390 + Mockup-Gegenbilder (DE); AC-33-Prüfung (390 px EN Orte: fünf Spalten, kein seitliches Scrollen); Ein-Ort-Texte (Bereich „Orte“, kein Plural) |
| `frontend/playwright.3037-wsw-abnahme.staging.config.ts` | CREATE (~30 LoC) | nginx-Basic-Auth wie #3283, `workers: 1`, kein storageState-Setup |
| `scripts/soll_ist_bild.py` | CREATE (~60 LoC) | Mockup links / Staging rechts je Kontext+Breite zu einem PNG (PIL) für den PO |
| `docs/reference/mail_validators.md` | MODIFY (~5 Z.) | veralteter Hinweis Z. 139 („Soll ab #3122 … noch nicht gebaut“) |

### Varianten (Plan-Agent, Zahlen aus Seed-Skript)

| Variante | Last | Aufwand | Urteil |
|---|---|---|---|
| Ein-Ort per Wegwerf-Abo im Prüfkonto | +1 Vergleich, +1 Ort | ~0 LoC (`seedAbo` orte:1) | **gewählt**; Aufräumen in `finally` + `afterAll` per Namenspräfix |
| Ein-Ort per Seed-Erweiterung | dauerhaft | 30–50 LoC + Runbook | nicht nötig; Elementliste kennt nur Trip/Orte-IDs |
| geteiltes Konto | Free-Quota, keine Mockup-Daten | niedrig | ungeeignet (Scheinabweichungen) |

### Scope/Risk

~250 LoC, 4 Dateien, Test-/Werkzeugschicht. Risiko niedrig für das Produkt. Restrisiken: Quota im Prüfkonto (vorab prüfen, klar abbrechen), hängende Wegwerf-Abos, Sprachumschaltung des Prüfkontos (am Ende DE), Abweichungen außerhalb der Karte (je eigenes Issue).

### Technical Approach / Reihenfolge

1. Werkzeuge bauen (Spec, Config, Bildskript), Orte + Ein-Ort zuerst aufnehmen.
2. Elementliste `--abnahme` DE+EN (`--scope wetter/normal`, Prüfkonto + Seed-IDs).
3. Mail-Nachweis Orte (3 Orte, 1 Ort) und Trip: Konfig per GET, Versand `POST /api/briefings/{id}/send?kind=…`, Validatoren mit `--konfig`.
4. Katalog #3047 Kern-Schicht: Ausgangsstand 26.11. grün (EXIT 0, 3 xfail = Fälle aus #3364). Vollständig grün erst nach #3364.
5. Nach Auslieferung #3364: Trip-Bild, Trip-Mail, Katalog erneut.
6. `mockup-bildpruefer` je Kontext/Breite (≤2 Runden), Soll/Ist-Bild an den PO, Abweichungen zuordnen.

### Dependencies

#3364 (gregor-zwanzig-4b) für Trip-Teil und Katalog-todo; Staging, Prüfkonto-Seed, Stalwart-Test-Postfach.

### Open Questions

Keine Produktfrage. Handy „am Gerät“: Agent prüft 390-px-Viewport; das echte Gerät sieht der PO über das Bild.
