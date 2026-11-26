# Kontext: Abnahme „Was steht wo“, Fortsetzung (#3037 Teil 2)

Workflow `abnahme-3037-teil2`, Issue #3037 (Teil von #2795 / Epic #2791). Teil 1 (`abnahme-3037-was-steht-wo`,
Spec `docs/specs/modules/feat_3037_was_steht_wo_abnahme.md`, Kontext `docs/context/abnahme-3037-was-steht-wo.md`)
ist live: Staging-Abnahmelauf + Soll/Ist-Bildwerkzeug, Orte und ein Ort 4/4 bestanden.

## Request Summary

Fortsetzung laut Abschnitt „Fortsetzung #3037“ der Teil-1-Spec, nachdem die Vorbedingungen erfüllt sind:

- #3419–#3422 (Soll-Bild, Elementliste, Seed-Region, Abgleich-Werkzeug) **zu und live** (PR #3429).
- #3364 („nur morgens/abends“) **zu und live**; Katalog #3047: keine Fallliste enthält mehr `rot_erwartet`
  (`grep -c rot_erwartet tests/fixtures/einstellung_gleich_mail/*.json` = 0 überall) ⇒ keine `xfail` mehr.

Zu liefern:
1. Trip-Kontext: Ganzseitenbilder DE/EN × 1280/390 (Werkzeug kann es schon: `ABNAHME_KONTEXTE=trip`).
2. Elementliste `--abnahme --scope wetter/normal` DE und EN: Abschnitt „was-steht-wo“ ohne Abweichung,
   übrige Abweichungen mit Besitzer.
3. Staging-Mails Trip, drei Orte, ein Ort: Validatoren mit `--konfig` Exit 0.
4. Katalog #3047 Kern-Schicht ohne `xfail`.
5. `mockup-bildpruefer` je Kontext/Breite ohne offenen Befund (≤ 2 Runden), Soll/Ist-Bilder an Henning.
6. Danach #3037 schließen; dann #3009 (Abnahme Epic #2913).

## Related Files

| Datei | Bedeutung |
|---|---|
| `frontend/e2e/wsw-abnahme-3037.staging.spec.ts` + `frontend/playwright.3037-wsw-abnahme.staging.config.ts` | Abnahmelauf (Kontexte per `ABNAHME_KONTEXTE`, Bilder nach `BILD_DIR`) |
| `scripts/soll_ist_bild.py` | Soll/Ist-Zusammensetzung |
| `scripts/elementliste_abgleich.ts` | Abgleich `npm run elementliste:abgleich -- --abnahme --scope wetter/normal [--sprache en]` |
| `.claude/tools/staging_mail_pruefen.py` (+ `tests/tdd/test_staging_mail_pruefweg.py`) | Staging-Mailweg: legt Wegwerf-Trip bzw. **immer drei Orte** + Preset an, Einzelversand, Validator **ohne `--konfig`** |
| `.claude/hooks/briefing_mail_validator.py`, `.claude/hooks/email_spec_validator.py`, `.claude/hooks/_soll_aus_konfiguration.py` | `--konfig PFAD` (rohes gespeichertes JSON), Compare zusätzlich `--orte` (`{"<id>": "<Name>"}`); Ein-Ort-Regel nur mit `--konfig` (`docs/reference/mail_validators.md` Z. 423–437, Aufruf Z. 450–459) |
| `tests/tdd/test_einstellung_gleich_mail_*.py`, `tests/fixtures/einstellung_gleich_mail/` | Katalog #3047 |
| `.claude/agents/mockup-bildpruefer.md` | Bildprüfer |

## Existing Patterns

- Mailweg-Werkzeug mit injizierbarem Netzrand (`main(transport=…, validator_runner=…)`), Kern-Schicht-Tests ohne Netz.
- Validator-Aufruf mit `--konfig` und `--orte` (Referenz Z. 450–459); Postfach geteilt ⇒ Auswahl über Betreff-Marker.

## Lücke (zu bauen)

`staging_mail_pruefen.py` kann weder `--konfig` noch einen Ein-Ort-Vergleich. Für Punkt 3 braucht es:
- Option `--orte-anzahl 1|3` (Standard 3, Verhalten unverändert),
- Option `--konfig`: nach dem Anlegen das **gespeicherte** Objekt per API lesen (Trip bzw. Preset), als JSON in
  eine Datei im Sitzungs-Artefaktordner (nicht weltlesbar nach /tmp) schreiben und an den Validator `--konfig`
  (Compare zusätzlich `--orte` mit den angelegten Orten) übergeben.

## Dependencies

Staging, Staging-`.env` (Prüfkonto, Kern-Secret, IMAP), Stalwart-Test-Postfach, Prüfkonto-Seed.

## Existing Specs

`docs/specs/modules/feat_3037_was_steht_wo_abnahme.md` (Teil 1, Fortsetzungsziele), `feat_3122_was_steht_wo.md`
(AC-21, AC-33, AC-35–37), `feat_3047_einstellung_gleich_mail_pruefkatalog.md`, `feat_3419_elementliste_nachzug.md`.

## Risks

- Neue Abweichungen außerhalb der Karte im Ganzseitenvergleich ⇒ je eigenes Issue (nie „kommt später“).
- Staging-Mailweg zeitweise kaputt (#2774-Muster) ⇒ ehrlich benennen, nicht lokal ersetzen.
- Ein-Ort-Vergleich: Validator-Regel „Bereichsname Orte“ greift nur mit `--konfig`.
- Wegwerf-Objekte müssen auch bei Fehlern entfernt werden (bestehendes `_raeume_auf`).

## Analysis

**Type:** Feature (Abnahme; Werkzeug-Ergänzung im Mail-Prüfweg, kein Produktcode).

### Messungen 26.11. (Analysephase)

- Katalog #3047 Kern-Schicht: **929 passed, 0 xfail** (Fallliste ohne `rot_erwartet`) ⇒ Fortsetzungsziel erfüllt.
- Elementliste `--abnahme --scope wetter/normal` (Prüfkonto, Seed frisch):
  - DE: gefunden 1040, abweichend 8, nicht prüfbar 48, zusätzlich 14, **0 ohne Besitzer**, Exit 0.
  - EN: gefunden 1015, abweichend 9 (kopf 6, metriken 3), nicht prüfbar 72, zusätzlich 21, **0 ohne Besitzer**;
    Abschnitt `was-steht-wo` ohne Abweichung.
- Abnahmelauf Bilder: erster Versuch ohne `.claude/validator.env` (Basic-Auth) abgebrochen, zweiter Lauf läuft.

### Affected Files

| Datei | Change | Zweck |
|---|---|---|
| `.claude/tools/staging_mail_pruefen.py` | MODIFY (~70 LoC) | `--orte-anzahl {1,3}` (Default 3), `--konfig`: gespeichertes Objekt per `GET /api/trips/{id}` bzw. `GET /api/compare/presets/{id}` lesen, als `konfig.json` (+ Compare `orte.json` `{"<id>":"<Name>"}`) in `tempfile.mkdtemp` (0700/0600) ablegen, an den Validator `--konfig`/`--orte` reichen, im `finally` löschen |
| `tests/tdd/test_staging_mail_pruefweg.py` | MODIFY (~120 LoC) | Kern-Schicht ohne Netz (Fake-Staging-Rand, `_Runner` nimmt argv auf) |
| `docs/reference/mail_validators.md` | MODIFY (~6 Z.) | Aufruf des Mail-Prüfwegs mit `--konfig`/`--orte-anzahl` |

### Varianten (Plan-Agent)

| Variante | LoC Skript | LoC Test | Risiko | Urteil |
|---|---|---|---|---|
| A Erweiterung `staging_mail_pruefen.py` | ~70 | ~120 | niedrig | **gewählt** |
| B neues Skript | ~150 | ~150 | Doppelpflege Anlegen/Aufräumen/Auth | nein |
| C Konfig aus Store-Datei | ~40 | ~60 | Skript spricht nur HTTP | nein |
| D Handarbeit mit curl | 0 | 0 | nicht wiederholbar | nein |

### Befunde gegen den Plan

1. DE-Lauf hat nur den Betreff-Marker; mit `--konfig` zusätzlich `--to-contains` (Wegwerf-Nutzer) mitgeben, damit
   die Mail nachweislich dem Nutzer des JSON gehört (Referenz verlangt das).
2. Betreff des Ein-Ort-Vergleichs beim ersten Echtlauf prüfen.
3. `--min-locations`: mit `--konfig` aus der Konfiguration abgeleitet, ein Ort zulässig.
4. `--orte` nur zusammen mit `--konfig`.
5. GET liefert das Objekt über Go-Structs, nicht byte-roh; die Validatoren erwarten genau die API-Form
   („wie die Go-API es liefert“), passt.

### Reihenfolge

1. RED-Tests Mail-Prüfweg → 2. Umsetzung → 3. Echtläufe Staging: Trip, drei Orte, ein Ort (je DE; Trip auch EN) →
4. Bilder + `mockup-bildpruefer` je Kontext/Breite → 5. Soll/Ist-Bilder an Henning → 6. Issue schließen.

### Open Questions

Keine Produktfrage.

## Befund Echtlauf Mails 26.11.

- Orte (3) und ein Ort mit `--konfig`: Validator Exit 0.
- Trip DE/EN mit `--konfig`: Exit 1, einzige Meldung „Ampelfarbe … kein Vergleichswert (Ampelpunkt, Klartext ohne Zahl,
  kein Rohwert in --ampel-werte)“ für Wind/Böen/Regen/Regen-W. (Regel #3237, `briefing_mail_validator.py` ~Z. 1242).
  Ohne `--konfig` Exit 0. Lösung (Spec AC-1 ergänzt): Wegwerf-Trip im `--konfig`-Modus mit Form „Roh“ für diese Größen.
