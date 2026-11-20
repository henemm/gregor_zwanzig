---
entity_id: feat_3189_vorlage_herkunft
type: feature
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: feat-3189-vorlage-herkunft
tags: [wetter, vorlage, herkunft, i18n, trip-vergleich-teilung]
---

# Herkunft eigener Wetter-Vorlagen (#3189)

## Approval

- [ ] Approved

## Purpose

Speichert ein Nutzer im Reiter Wetter eine eigene Vorlage, merkt sich die App automatisch, aus welchem Trip bzw. Orts-Vergleich sie stammt. Im Vorlagen-Menü zeigt die Unterzeile dann ohne Beschreibung „eigene · aus <Name> gespeichert“ (EN „saved from <name>“); mit Beschreibung bleibt „eigene · <Beschreibung>“ (PO-Entscheid, Issue #3189).

## Source

- **File:** `internal/model/metric_preset.go`
- **Identifier:** `MetricPreset` (neu: `Herkunft *PresetHerkunft`), dazu `internal/handler/metric_preset.go` (`createPresetRequest`, Create), `internal/store/metric_preset.go` (`migrateMetricPreset`), Frontend `VorlageKarte.svelte` (`eigeneUnterzeile`)

Schichten: Go-API (Datenmodell, Handler, Store) und SvelteKit-Frontend. Python-Core unberührt: `MetricPreset` wird in `src/`/`api/` nicht gespiegelt (Issue-Text „Python-DTO“ entfällt).

> **Querschnitt:**
> - **Trip/Orts-Vergleich:** geteilter Code (`WetterTabInhalt`, `VorlageKarte`, `SavePresetDialog` unter `shared/` bzw. `organisms/wetter-tab/`); keine Kontext-Zweige, Art = vorhandenes `kind` (route|vergleich).
> - **Mandantentrennung:** Datei je Nutzer `data/users/<id>/metric_presets.json`; Test mit zwei Nutzern.
> - **i18n:** neuer Katalogschlüssel DE+EN (ADR-0104); der Name ist Nutzertext und wird nie übersetzt.
> - **Daten-Schema:** additives optionales Feld, Read-Modify-Write, kein Replace.
> - **Kanäle:** nicht betroffen (reine Editor-Oberfläche, kein Briefing- oder Alarm-Inhalt).

## Estimated Scope

- **LoC:** ca. 120-160 Produktivcode, zusätzlich Tests
- **Files:** ca. 9 Quelldateien plus Tests und Doku
- **Effort:** medium

## Scope

**Im Scope:** optionales Feld `herkunft {id, name}` an der eigenen Wetter-Vorlage (Go-Modell, Handler-Create, Store-Migration), Weitergabe der Herkunft beim Speichern aus dem Reiter Wetter (Trip und Orts-Vergleich, geteilter Code), Unterzeile im Vorlagen-Menü (Beschreibung vor Herkunft vor nur „eigene“), Katalogschlüssel DE/EN, `api_contract.md`, Tests (Go, node --test, Staging-E2E).

**Besitzer-Einträge:** Die Besitzerliste der Elementliste führt keinen Eintrag an `#3189` (Stand 20.11. nach #3151: die Mockup-Zeile „eigene · aus GR221 gespeichert“ wird im Prüfkonto über die Beschreibung gefunden). Zu übernehmen ist daher nichts; der Zählwächter `tests/test_2913_c2_besitzerliste.py` bleibt unverändert und darf keinen `#3189`-Eintrag zeigen.

**Nicht im Scope:** Python-Core (kein Spiegel von `MetricPreset`), nachträgliches Befüllen bestehender Vorlagen, Live-Auflösung umbenannter Trips/Vergleiche, Herkunft im Anlege-Modus.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/metric_preset.go` | module | Create nimmt validierte Herkunft an; Patch bleibt ohne Herkunftsfeld |
| `internal/store/metric_preset.go` (`migrateMetricPreset`) | module | map-basierte Migration muss `herkunft` explizit lesen, sonst Verlust beim Save |
| `wetterTabLaden.ts` (`eigeneVorlageAus`) | module | Abbildung `MetricPreset` -> `EigeneVorlage`, nimmt Herkunftsname mit |
| `ampelSchreiben.ts` (`eigeneVorlagePayload`) | module | schreibt `herkunft` in den POST-Body |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | module | neuer Schlüssel `wetter.vorlage.eigene_aus_herkunft` |
| ADR-0104 | adr | Zweisprachigkeit, Katalogpflicht |
| ADR-0083 | adr | Schreibsperre `LockMetricPresets` bleibt unverändert wirksam |
| ADR-0106 / ADR-0108 | adr | Profil-Ampel und Tempo an der Vorlage, werden nicht berührt |
| `fix_3192_wetter_dialog_abgleich.md` (AC-8) | spec | Unterzeile mit Beschreibung muss unverändert grün bleiben |
| `feat_3111_wetter_dialoge_mockup.md` (AC-5) | spec | bisherige Unterzeilen-Regel, wird um Herkunft erweitert |

## Implementation Details

1. **Modell:** `MetricPreset.Herkunft *PresetHerkunft` mit `json:"herkunft,omitempty"`; `PresetHerkunft{ID string "id"; Name string "name"}`. Die Art steckt schon im `kind` der Vorlage und wird nicht doppelt gespeichert.
2. **Create:** `createPresetRequest.Herkunft` optional. Name trimmen, auf 200 Zeichen kappen; leerer Name oder leere id = Feld verwerfen (kein Fehler).
3. **Mandantenprüfung (Entscheidung):** Die Herkunft-id wird NICHT gegen Trips/Vergleiche des Nutzers aufgelöst, sondern als reiner Verweistext des Clients gespeichert. Begründung: Der Wert wird nur im eigenen Menü desselben Nutzers angezeigt, aus dem Store des Nutzers geladen und enthält keine fremden Daten; es gibt keinen Lesepfad über Nutzergrenzen (Datei je Nutzer, `WithUser`). Ein Lookup würde Trip- und Vergleichs-Stores in den Preset-Handler ziehen und im Anlege-/Löschfall Sonderlogik brauchen. Folge: eine fremde id kann nichts preisgeben, weil nie aufgelöst wird; Namenskappung und Escaping begrenzen Missbrauch.
4. **Patch:** unverändert, Struct-Merge lässt `herkunft` stehen; Herkunft wird nur beim Create gesetzt.
5. **Store:** `migrateMetricPreset` liest `herkunft` (map mit id/name) wie `description`/`ampel`; Bestand ohne Feld bleibt nil und gültig.
6. **Name einfrieren:** Der Name gilt zum Speicherzeitpunkt; spätere Umbenennung oder Löschung des Trips ändert die Aussage nicht („aus GR221 gespeichert“ ist ein Ereignis der Vergangenheit).
7. **Frontend:** `WetterTabInhalt` leitet `herkunft = {id: aboId, name: (trip ?? preset).name}` ab, nur wenn nicht `createMode` und Name nicht leer; Durchreichen über `VorlageKarte` an `SavePresetDialog` (neue optionale Prop), `eigeneVorlagePayload` schreibt es nur mit nicht leerem Namen. `EigeneVorlage.herkunftName?` wird in `eigeneVorlageAus` aus `p.herkunft?.name` gefüllt; die POST-Antwort enthält die Herkunft, daher aktualisiert sich das Menü ohne Neuladen.
8. **Unterzeile `eigeneUnterzeile`:** Beschreibung vorhanden -> „eigene · <Beschreibung>“; sonst Herkunft -> „eigene · “ + `$t('wetter.vorlage.eigene_aus_herkunft', {name})`; sonst „eigene“. Schlüssel DE „aus {name} gespeichert“, EN „saved from {name}“.
9. **Doku/Seed:** `docs/reference/api_contract.md` dokumentiert `herkunft` bei POST `/api/metric-presets`. Der Prüfkonto-Seed (`scripts/staging_pruefkonto_mockupdaten.py`) und `EIGENE_VORLAGE_BESCHREIBUNG` bleiben unverändert (Beschreibung hat Vorrang, AC-8 bleibt grün).

## Expected Behavior

- **Input:** POST `/api/metric-presets` mit `kind` und optional `herkunft {id, name}`; Anzeige im Vorlagen-Menü.
- **Output:** gespeicherte Vorlage trägt `herkunft` (Name eingefroren); Unterzeile nach Priorität Beschreibung > Herkunft > „eigene“.
- **Side effects:** keine; Bestand ohne Feld bleibt unverändert, Anlege-Modus erzeugt keine Herkunft.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Go Handler: GIVEN Nutzer A WHEN POST mit `herkunft {id,name}` THEN Antwort und List enthalten Herkunft; Name mit Leerraum/über 200 Zeichen wird getrimmt/gekappt, leerer Name = kein Feld.
- [ ] Go Handler: GIVEN gespeicherte Vorlage mit Herkunft WHEN PATCH (Name/Metriken) THEN `herkunft` bleibt unverändert.
- [ ] Go Store: GIVEN Datei mit Altbestand ohne `herkunft` UND Datei mit `herkunft` WHEN Load + Save + Load THEN Altbestand unverändert gültig, Herkunft überlebt (Round-Trip über `migrateMetricPreset`).
- [ ] Go Mandanten: GIVEN Nutzer A mit Herkunft-Vorlage und Nutzer B WHEN B listet THEN B sieht nichts von A; B speichert eigene mit gleicher id, A bleibt unberührt.
- [ ] node --test: `eigeneVorlagePayload` schreibt `herkunft` nur mit Name; `eigeneVorlageAus` übernimmt `herkunftName`; Unterzeilen-Priorität in DE und EN; `createMode` liefert keine Herkunft.
- [ ] i18n-Tests (`deutsch_unveraendert.test.ts`, `wetter_tab_i18n.test.ts`): Schlüssel in de und en vorhanden, Platzhalter `{name}` in beiden.
- [ ] Playwright (Staging): Vorlage ohne Beschreibung aus Trip und aus Orts-Vergleich speichern, Menü zeigt ohne Neuladen „eigene · aus <Name> gespeichert“; Aufräumen der Testvorlage; `s3a2794-teil3-vorlage.spec.ts` AC-8 bleibt grün.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit einem Trip „GR221“ und einem Orts-Vergleich / When er im Reiter Wetter „Als eigene Vorlage speichern“ wählt (POST) / Then ist `herkunft {id, name}` an der Vorlage gespeichert, der Name zum Speicherzeitpunkt eingefroren (spätere Umbenennung ändert ihn nicht), und ein PATCH der Vorlage lässt `herkunft` unberührt.
  - Test: Go-Handlertest (POST, Umbenennung des Trips, PATCH) und Playwright-Speichern aus Trip und Orts-Vergleich.
- **AC-2:** Given Bestands-Vorlagen ohne Feld `herkunft` / When die Daten geladen und gespeichert werden (Store-Migration `migrateMetricPreset`) / Then bleiben sie gültig und unverändert, und eine Vorlage mit `herkunft` behält das Feld nach Load und Save.
  - Test: Go-Store-Round-Trip mit Datei ohne und mit Feld.
- **AC-3:** Given zwei verschiedene Nutzer / When beide Vorlagen speichern und listen / Then sieht jeder nur seine eigenen Vorlagen samt Herkunft; die Herkunft-id wird nicht fremd aufgelöst (reiner Verweis im eigenen Datenbestand), Name wird getrimmt und auf 200 Zeichen gekappt, leerer Name verwirft das Feld ohne Fehler.
  - Test: Go-Handlertest mit zwei Nutzern, nur der Besitzer sieht seine Herkunft.
- **AC-4:** Given eine eigene Vorlage im Vorlagen-Menü / When die Unterzeile berechnet wird / Then gilt die Reihenfolge Beschreibung („eigene · <Beschreibung>“), sonst Herkunft (DE „eigene · aus {name} gespeichert“, EN „eigene · saved from {name}“ je nach Sprache aus dem Katalog), sonst nur „eigene“; Trip und Orts-Vergleich nutzen denselben Code.
  - Test: node --test auf die Unterzeilenfunktion mit allen drei Fällen in DE und EN.
- **AC-5:** Given der Anlegen-Modus, in dem Trip bzw. Vergleich noch nicht existiert / When der Nutzer eine eigene Vorlage speichert / Then wird keine Herkunft gespeichert und die Unterzeile zeigt nur „eigene“.
  - Test: node --test für die Herkunftsableitung bei `createMode` und Go-Test, dass ein POST ohne `herkunft` kein Feld erzeugt.
- **AC-6:** Given Staging mit einem Prüfkonto / When eine Vorlage ohne Beschreibung gespeichert wird (Trip und Orts-Vergleich) / Then zeigt das Menü sofort ohne Neuladen „eigene · aus <Name> gespeichert“, die Testvorlage wird aufgeräumt, und der Test #3192 AC-8 (mit Beschreibung) bleibt grün.
  - Test: Browser-E2E auf Staging gegen die echte Oberfläche.
- **AC-7:** Given ein Entwickler liest die API-Beschreibung / When er POST `/api/metric-presets` nachschlägt / Then ist das optionale Feld `herkunft {id, name}` samt Regeln (eingefroren, nur beim Anlegen, 200 Zeichen) dokumentiert.
  - Test: Doku-Prüfung `# doc-compliance-test` auf den Eintrag in `docs/reference/api_contract.md`.

## Definition of Done

- [ ] Alle ACs durch Tests belegt, Kern-Schicht (Go, node --test) grün, Staging-E2E grün.
- [ ] Adversary-Prüfung mit Mutations-Gegenprobe (u. a. `migrateMetricPreset` ohne Herkunft, PATCH überschreibt Herkunft) ohne offenes Finding.
- [ ] i18n-Parität DE/EN, kein hartkodierter Nutzertext.
- [ ] `api_contract.md` aktualisiert; PR mit allen CI-Checks grün, Deploy und Selftest Exit 0.

## Known Limitations

- Name ist eingefroren: Umbenennen oder Löschen des Trips/Vergleichs verändert die Unterzeile nicht (bewusst).
- Bestehende Vorlagen ohne Herkunft werden nicht nachträglich befüllt (Herkunft unbekannt).
- Herkunft ist nicht nachträglich editierbar und nicht verlinkt; die `id` ist für spätere Verlinkung vorgesehen.
- Die Herkunft-id wird nicht gegen vorhandene Trips geprüft (siehe Implementation Details, Punkt 3).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additives optionales Feld am bestehenden Datenmodell. Es ändert keine Entscheidung aus ADR-0104 (i18n, wird befolgt), ADR-0083 (Schreibsperre), ADR-0106/ADR-0108 (Ampel/Tempo an der Vorlage); keine Entscheidungsfläche wird berührt.

## Changelog

- 2026-11-20: Initial spec created (Issue #3189)
