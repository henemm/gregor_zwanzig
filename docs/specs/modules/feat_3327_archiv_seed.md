---
entity_id: feat_3327_archiv_seed
type: feature
created: 2026-11-24
updated: 2026-11-24
status: draft
version: "1.0"
tags: [funktionsseiten, archiv, staging, seed, pruefkonto, epic-3318, issue-3327]
workflow: feat-3327-archiv-seed
---

# Archiv-Bild der Funktionsseite mit Prüfkonto-Archiv-Trip

## Approval

- [ ] Approved

## Purpose

Das Bild „Archiv“ auf der Funktionsseite zeigt heute ein leeres Archiv und erklärt damit nichts. Der Prüfkonto-Seed (#2967) legt deshalb zusätzlich einen zweiten, frei erfundenen Trip an und archiviert ihn genau einmal, danach wird das Bild in Deutsch und Englisch neu aufgenommen und Alt-Text sowie Anleitungen werden nachgezogen (Issue #3327, Teil von #3318).

## Source

- **File:** `scripts/staging_pruefkonto_mockupdaten.py` (erweitert), `tests/tdd/test_staging_pruefkonto_mockupdaten.py` (erweitert)
- **Identifier:** neue Konstanten `ARCHIV_TRIP_ID`, `ARCHIV_TRIP_NAME`, Funktion `soll_archiv_trip()`, Methode `PruefkontoSeed.sichere_archiviert(trip)`, Aufruf in `fuehre_seed`
- **Schicht:** Prüfwerkzeug (`scripts/`, `tests/`), Frontend-Texte und Bilder (`frontend/src/lib/i18n/messages/`, `frontend/static/funktionen/`) und Runbooks. Kein Go-API- und kein Python-Core-Produktcode; der Seed spricht nur die bestehende Go-API auf Staging an (`POST/PUT /api/trips`, `PATCH /api/trips/{id}/state`).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orts-Vergleich-Teilung:** n/a. Es entsteht kein UI-Baustein; ein Prüfwerkzeug füllt das Prüfkonto, die Archiv-Seite bleibt unverändert.
> - **Mandantentrennung:** Der Seed schreibt nur unter der Anmeldung des eigenen Prüfkontos und nur auf die feste eigene ID `gz2967-archiv-kuestenpfad`; `user_id` kommt aus dem Auth-Kontext der API, nie `"default"`. Der bestehende Zwei-Nutzer-Test des Seeds (AC-10 aus #2967) deckt den neuen Trip mit ab.
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt ändert sich. Der Seed sendet für den Archiv-Trip bewusst keine Wetter-, Kanal- oder Tabellenkonfiguration; Go vergibt bei der Neuanlage ohne `display_config` die Standardvorlage des Nutzers (#2794), das ist folgenlos. Der Trip erzeugt, weil archiviert und in der Vergangenheit liegend, keinen Versand über E-Mail, Telegram, SMS oder Premium-SMS.

## Estimated Scope

- **LoC:** ca. +90 / -10 (Seed ~30, Test ~50, Texte und Doku ~20)
- **Files:** 7 Textdateien plus 2 Bilddateien
- **Effort:** low (Risiko niedrig: nur Staging-Prüfkonto, feste eigene ID, keine Produktlogik)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| scripts/staging_pruefkonto_mockupdaten.py | MODIFY | Konstanten und `soll_archiv_trip()` (fiktiver Trip, 3 Etappen in der Vergangenheit); `sichere_archiviert` (PATCH nur, wenn `archived_at` fehlt); Aufruf in `fuehre_seed` nach Tarif und Haupt-Trip. Ausgabe `ELEMENTLISTE_TRIP_ID` bleibt der GR221-Trip |
| tests/tdd/test_staging_pruefkonto_mockupdaten.py | MODIFY | Fake-Go-API: Route `PATCH /api/trips/{id}/state` (`{"archived": true}` setzt `archived_at`), PUT ersetzt und entfernt dabei `archived_at` (bewusst strenger als Go, s. u.); neue Tests zu AC-1 bis AC-4 |
| frontend/src/lib/i18n/messages/de/funktionen.json | MODIFY | Alt-Text `funktionen.bild.archiv.alt` beschreibt den Bildinhalt (ein archivierter Trip) |
| frontend/src/lib/i18n/messages/en/funktionen.json | MODIFY | Englischer Alt-Text `funktionen.bild.archiv.alt`, gleicher Inhalt |
| frontend/static/funktionen/archiv.webp | MODIFY | Neu aufgenommen per `funktionen_screenshots.py --nur archiv` (DE) |
| frontend/static/funktionen/en/archiv.webp | MODIFY | Neu aufgenommen (EN) |
| docs/runbooks/funktionen_screenshots.md | MODIFY | Sichtprüfungs-Zeile `archiv` aktualisiert; Abschnitt „Bekannte Schwäche Archiv-Bild“ ersetzt durch Hinweis auf den Seed-Trip |
| docs/runbooks/staging_pruefkonto_seed.md | MODIFY | Bestand des Prüfkontos um den archivierten Trip ergänzt, Reihenfolge „erst Seed, dann Archiv-Bild“ |
| docs/specs/modules/feat_2967_pruefkonto_mockupdaten.md | MODIFY | Changelog-Eintrag und Hinweis, dass der Seed zusätzlich den Archiv-Trip anlegt (#3327) |

### Nicht-Ziele

- Keine Änderung an Produktcode, an der Archiv-Seite, der Trip-Liste oder an Gate-Konfigurationen.
- Der Archiv-Trip bekommt keine Kanal-, Wetter- oder Tabellenkonfiguration.
- Keine Berührung echter Trips des Product Owners; der Seed schreibt nur auf die feste Prüfkonto-ID.
- `ELEMENTLISTE_TRIP_ID` bleibt der GR221-Trip; der Elementlisten-Abgleich (#2913) wird nicht verändert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `scripts/staging_pruefkonto_mockupdaten.py` (`sichere_datensatz`, `_merge`, `fuehre_seed`) | Bestand | Upsert nach festem ID-Muster `gz2967-…`; `_merge` = `{**ist, **soll}` erhält `archived_at` |
| `tests/tdd/test_staging_pruefkonto_mockupdaten.py` (Fake-Go-API, `_trip_merge_wie_go`) | Bestand | Zustandsbehafteter Fake, Nachbildung des Go-Verhaltens (kein Mock-Theater) |
| `internal/handler/trip.go` (`UpdateTripStateHandler` Z. 625–700, `CreateTripHandler` Z. 293, `UpdateTripHandler` Z. 393) | Quelle | PATCH mit `{"archived": true}` setzt `archived_at`; nur der POST-Upsert ohne `archived_at` auf einen archivierten Trip reaktiviert (Quote geprüft, Z. 293); der PUT merged auf den Bestand, sein DTO kennt kein `archived_at`, er reaktiviert nie |
| `frontend/src/routes/archiv/+page.server.ts` | Quelle | Archiv listet Trips mit `archived_at`, zeigt Name, „N Etappen“, Datum |
| `frontend/src/routes/trips/+page.server.ts` | Quelle | Trip-Liste blendet archivierte Trips aus |
| Briefing-Auswahl (`next_briefing.py`, `loader.py`, `scheduler_dispatch_service.py`) | Quelle | Archivierte Trips werden übersprungen, also kein Versand |
| `scripts/funktionen_screenshots.py` (`--nur archiv`) | Werkzeug | Neuaufnahme DE und EN gegen Staging |
| Tarif Premium im Prüfkonto (`sichere_tarif`) | Voraussetzung | Anlage prüft die Trip-Quote; Tarif wird im Seed vor dem Trip gesetzt |
| Epic #3318, Issue #3327 | Tracking | Auftrag und Einordnung |

## Implementation Details

**Fiktiver Archiv-Trip (fest):**

- ID `gz2967-archiv-kuestenpfad`, Name „Küstenpfad Probelauf“, Region „Nordsee (fiktiv)“. Kein Bezug zu GR221, GR20, KHW oder anderen echten Trips des Product Owners.
- Drei Etappen mit festen IDs `gz2967-archiv-kuestenpfad-e1` bis `-e3` und Daten in der Vergangenheit: E1 „Dünenhof → Leuchtturm“ am 12.06.2026, E2 „Leuchtturm → Deichkrug“ am 13.06.2026, E3 „Deichkrug → Fährhafen“ am 14.06.2026. Je Etappe zwei fiktive Wegpunkte (Start, Ziel) mit Koordinaten und Höhe nach dem Muster von `_wegpunkt`.
- Keine Kanal-, Wetter- oder Tabellenkonfiguration.

**Ablauf in `fuehre_seed` (nach Tarif und Haupt-Trip):**

1. `sichere_datensatz("/api/trips", soll_archiv_trip())`: GET 404 ⇒ POST; sonst PUT nur bei Abweichung. Das `soll` enthält nie `archived_at`, `_merge` übernimmt es aus dem Ist-Stand. Der echte Go-PUT (`UpdateTripHandler`) merged ohnehin auf den Bestand und reaktiviert nie; reaktivieren kann nur der POST-Upsert (`trip.go` Z. 293), den der Seed für einen bestehenden Trip nicht nutzt. Der Erhalt von `archived_at` im Soll schützt gegen den strengeren Fake (s. u.) und gegen einen künftigen Wechsel auf ersetzendes Schreiben.
2. `sichere_archiviert(trip)`: fehlt `archived_at` im Ergebnis, dann `PATCH /api/trips/{id}/state` mit Body `{"archived": true}` (nicht `{"state": …}`, das wirkt nicht). Ist `archived_at` gesetzt, passiert nichts. Das Archivdatum ist der Tag des ersten Seed-Laufs und bleibt danach stabil.
3. Rückgabe und stdout von `main` bleiben unverändert (`ELEMENTLISTE_TRIP_ID` = GR221).

**Bild und Texte (Hand-Arbeit nach dem Seed-Lauf auf Staging):** `scripts/funktionen_screenshots.py --nur archiv` für DE und EN aufnehmen, Bild ansehen (ein Eintrag „Küstenpfad Probelauf“, „3 Etappen“, Datum), Alt-Text DE/EN an den Bildinhalt anpassen, Runbooks nachziehen.

## Expected Behavior

- **Input:** Seed-Lauf auf dem Staging-Host mit Prüfkonto-Zugang wie bisher (`uv run python scripts/staging_pruefkonto_mockupdaten.py`).
- **Output:** Prüfkonto enthält zusätzlich genau einen archivierten Trip; die Archiv-Seite des Prüfkontos zeigt einen Eintrag; Exit 0.
- **Side effects:** Schreibzugriff nur auf die feste ID `gz2967-archiv-kuestenpfad` im Prüfkonto; kein Versand.

## Acceptance Criteria

- **AC-1:** Given ein Prüfkonto ohne den Küstenpfad-Trip / When der Seed zum ersten Mal läuft / Then legt er den Trip „Küstenpfad Probelauf“ mit drei Etappen in der Vergangenheit an und archiviert ihn über die Archiv-Schaltung der API (`PATCH /api/trips/{id}/state` mit `{"archived": true}`), sodass der Trip ein Archivdatum trägt.
  - Test: Kern-Test mit der vorhandenen Fake-Go-API liest den Trip nach dem Lauf: ID, Name, 3 Etappen mit Datum vor heute, `archived_at` gesetzt; der Fake verzeichnet genau einen PATCH mit `{"archived": true}`.

- **AC-2:** Given der Küstenpfad-Trip ist bereits archiviert / When der Seed ein zweites Mal läuft / Then schreibt er nichts an diesem Trip (weder PUT noch PATCH), reaktiviert ihn nicht, das Archivdatum bleibt unverändert und der Exit-Code ist 0.
  - Test: Kern-Test fährt den Seed zweimal; im zweiten Lauf zählt der Fake null Schreibaufrufe auf den Archiv-Trip, `archived_at` ist byte-gleich und nicht entfernt.

- **AC-3:** Given der archivierte Küstenpfad-Trip wurde von Hand verändert (z. B. anderer Name) / When der Seed läuft / Then stellt er den Soll-Namen per PUT wieder her, behält dabei das Archivdatum (der Trip bleibt archiviert) und archiviert nicht ein zweites Mal.
  - Test: Kern-Test ändert den Namen im Fake-Zustand, lässt den Seed laufen und prüft Soll-Name, unveränderten `archived_at` und null PATCH-Aufrufe.

- **AC-4:** Given das Prüfkonto enthält den aktiven Trip „GR221 Mallorca“ / When der Seed den Archiv-Trip anlegt und archiviert / Then bleibt der GR221-Trip aktiv (kein Archivdatum), unverändert, und stdout nennt weiterhin dessen ID als `ELEMENTLISTE_TRIP_ID`.
  - Test: Kern-Test prüft nach dem Lauf, dass GR221 kein `archived_at` hat, seine Daten gleich bleiben und die stdout-Zeile die GR221-ID trägt (nicht die Archiv-ID).

- **AC-5:** Given der Küstenpfad-Trip ist archiviert / When Trip-Liste, Briefing-Auswahl und Versand-Planung des Prüfkontos laufen / Then erscheint der Trip nicht in der Trip-Liste, und es wird für ihn weder ein Briefing noch ein Alarm versendet.
  - Test: Kern-Test (Fake-API bzw. vorhandene Auswahl-Funktionen des Cores mit echten Testdaten) prüft, dass der archivierte Trip aus Trip-Liste und fälligen Briefings herausfällt; Staging-Sichtprüfung bestätigt, dass der Archiv-Trip nicht in der Trip-Liste des Prüfkontos erscheint (keine zusätzliche Karte).

- **AC-6:** Given der Seed ist auf Staging gelaufen / When das Archiv-Bild für Deutsch und Englisch neu aufgenommen wird / Then zeigt jedes Bild genau einen Eintrag „Küstenpfad Probelauf“ mit „3 Etappen“ und Archivdatum und ist nicht mehr leer.
  - Test: Staging-Nachweis: Seed-Lauf, danach `funktionen_screenshots.py --nur archiv` in DE und EN, Sichtprüfung beider Bilder (Eintrag, Etappenzahl, Datum lesbar, nichts abgeschnitten).

- **AC-7:** Given die neuen Archiv-Bilder / When die Funktionsseite das Bild einbindet / Then beschreibt der Alt-Text auf Deutsch und auf Englisch den Bildinhalt (ein archivierter Trip mit Etappenzahl und Datum) und nicht mehr „leeres Archiv“.
  - Test: Der bestehende Übersetzungs-Paritätstest bleibt grün (beide Sprachen haben `funktionen.bild.archiv.alt`); Sichtprüfung vergleicht Alt-Text und Bild.

- **AC-8:** Given die Runbooks und die Spec zu #2967 / When #3327 abgeschlossen ist / Then nennen `funktionen_screenshots.md` und `staging_pruefkonto_seed.md` den archivierten Prüfkonto-Trip und die Reihenfolge „erst Seed, dann Archiv-Bild“, der Abschnitt „Bekannte Schwäche Archiv-Bild“ ist ersetzt, und die Spec 2967 trägt einen Changelog-Eintrag.
  - Test: Doku-Abnahme durch Lesen beider Runbooks und der Spec (`# doc-compliance-test`, kein Verhaltensnachweis); die Verhaltensnachweise liegen in AC-1 bis AC-6.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN Prüfkonto ohne Archiv-Trip WHEN Seed erstmals läuft THEN Trip mit 3 vergangenen Etappen existiert und ist archiviert (ein PATCH `{"archived": true}`) (AC-1).
- [ ] GIVEN Archiv-Trip archiviert WHEN zweiter Seed-Lauf THEN null Schreibaufrufe auf den Trip, `archived_at` erhalten, Exit 0 (AC-2).
- [ ] GIVEN Archiv-Trip mit abweichendem Namen WHEN Seed läuft THEN PUT stellt den Namen her, `archived_at` bleibt, kein PATCH (AC-3).
- [ ] GIVEN GR221 aktiv WHEN Seed läuft THEN GR221 ohne `archived_at`, stdout-ID = GR221 (AC-4).
- [ ] GIVEN Archiv-Trip archiviert WHEN Trip-Liste und fällige Briefings ermittelt werden THEN Trip fehlt in beiden (AC-5).
- [ ] GIVEN zwei Nutzer im Fake-Server WHEN Seed als Prüfkonto läuft THEN der Archiv-Trip entsteht nur beim Prüfkonto (Erweiterung des Zwei-Nutzer-Tests).

Die Fake-Go-API erhält dazu die Route `PATCH /api/trips/{id}/state` und ein PUT, der ersetzt und `archived_at` dabei entfernt. Das ist bewusst strenger als Go (der echte PUT merged und reaktiviert nie; reaktivieren kann nur der POST-Upsert): verlöre der Seed `archived_at` je aus dem Soll, würde ein Test rot. Die Tests laufen ohne Mock-Theater gegen diesen zustandsbehafteten Fake.

### Staging-Nachweis (E2E-Phase)

- [ ] Seed zweimal hintereinander auf dem Staging-Host, beide Exit 0, zweiter Lauf ohne Änderung (AC-1, AC-2).
- [ ] `funktionen_screenshots.py --nur archiv` in DE und EN, Sichtprüfung beider Bilder und der Alt-Texte (AC-6, AC-7).

## Definition of Done

- AC-1 bis AC-8 erfüllt, Kern-Tests vorher rot und nachher grün belegt.
- Mutationsprobe des Adversary: Entfernt man den Erhalt von `archived_at` oder die Bedingung vor dem PATCH, wird ein Test rot.
- Seed auf Staging zweimal gelaufen (Exit 0, zweiter Lauf ohne Änderung), Archiv-Bilder DE+EN neu aufgenommen und gesichtet.
- Alle 6 CI-Checks am PR grün; #3327 nach Prod-Deploy und Selftest geschlossen, Epic #3318 bleibt offen.

## Known Limitations

- Das Archivdatum im Bild ist der Tag des ersten Seed-Laufs auf Staging; es ändert sich nur, wenn der Trip im Prüfkonto gelöscht und neu angelegt wird. Eine spätere Neuaufnahme zeigt dann das neue Datum.
- Der Archiv-Trip zählt kurz als aktiver Trip, bis er archiviert ist; das Prüfkonto ist Premium (Tarif wird vorher gesetzt), die Quote bleibt damit unkritisch.
- Der Seed funktioniert wie bisher nur auf dem Staging-Host.
- Nur fiktive Daten: Name, Orte und Koordinaten des Küstenpfad-Trips sind erfunden (öffentliches Repo).

## Kein Cron, kein Heartbeat

Der Seed wird nur von Hand gestartet; es gibt keinen Cronjob und keinen Dauerdienst, daher keinen Heartbeat.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Erweiterung eines Prüfwerkzeugs für Staging-Testdaten plus Bild und Texte; berührt keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma). Die bestehende Archiv-Schaltung der API wird unverändert genutzt.

## Changelog

- 2026-11-24: Initial spec created (Issue #3327, Teil von #3318)
- 2026-11-24: Adversary-Befunde F001/F002 Text korrigiert (PUT reaktiviert in Go nie, nur der POST-Upsert; Fake ist bewusst strenger. „Keine Wetterkonfiguration“ präzisiert: Seed sendet keine, Go vergibt bei Neuanlage die Standardvorlage, #2794)
