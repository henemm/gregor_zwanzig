---
entity_id: rework_3399_vorlage_aufloesung
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: rework-3399-vorlage-aufloesung
tags: [ampel, rework, vorlage, adr-0127, frontend]
---

# Vorlagen-Rangfolge nur noch im Server (Frontend übernimmt `vorlage_id`)

## Approval

- [ ] Approved

## Purpose

Welche Wetter-Vorlage („Allgemein", „Alpen-Trekking" usw.) für einen Trip oder Ortsvergleich gilt, wird heute zweimal entschieden: im Server (`resolve_entwurf`) und noch einmal in der Oberfläche (`vorlageIdFuer`: Ampel-Vorlage vor Vorlagenname vor Profil vor „Allgemein"). Nach diesem Umbau entscheidet nur noch der Server; die Oberfläche übernimmt dessen Vorlagen-ID für „Alarm ab"-Vorgabe, Vorlagenname und „Kopie aus Vorlage".

Sichtbar ändert sich wenig: Der Vorlagenname erscheint erst nach der Server-Antwort; bis dahin und bei einem Fehler steht „—", nie ein geratenes „Allgemein". Grundlage ist Issue #3399 (Folge aus #2988 S4), ADR-0127 Nr. 3 (Frontend hält kein Metrik-Wissen). Analyse: `docs/context/rework-3399-vorlage-aufloesung.md`.

## Source

- **File:** `frontend/src/lib/components/shared/wetter-tab/vorlagenIdLader.ts` (neu), `frontend/src/lib/components/alerts-tab/alarmAbAnzeige.ts`, `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts`
- **Identifier:** `vorlageIdFuer`, `PROFIL_ZU_VORLAGE` (entfallen in S4), `aboVorlagenName`, `feldsatzAusVorlage`, `ladeVorlagenIds` (neu)

> **Schicht-Hinweis:** Reine Frontend-Änderung (`frontend/src/...`, SvelteKit). Python-Core (`src/app/ampel.py`, `resolve_entwurf`) und Go-Durchreichung (`POST /api/ampel/aufloesung`) existieren seit #2988 und bleiben unverändert.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Ein kontextfreier Lader in `shared/wetter-tab/`, keine Pendants. AlarmeTab, Hub-Übersicht und Abo-Karte nutzen ihn für beide Arten.
> - **Mandantentrennung:** Der Endpunkt liest und schreibt keinen Nutzerbestand und liefert nutzerunabhängige Ergebnisse (Vertrag #2988 AC-7). Es werden keine Nutzerdaten bewegt; ein Test mit zwei Nutzern ist daher nicht nötig. `user_id` setzt wie bisher die Go-API aus der Anmeldung, nie `"default"`.
> - **Kanäle:** Keine Auswirkung auf E-Mail, Telegram, SMS und Premium-SMS (nur Anzeige und Startwert der Oberfläche).
> - **i18n:** „—" ist kein übersetzter Text. Es entstehen keine neuen Nutzertexte, der Katalog bleibt unberührt.

## Estimated Scope

- **LoC:** ca. 450 bis 550 netto Produktcode, je Scheibe höchstens 250 (Tests zählen nicht)
- **Files:** ca. 15 Produktdateien (S1: 2, S2: 4, S3a: 3, S3b: 5, S4: 1), höchstens 5 je Scheibe, ca. 9 Testdateien
- **Effort:** medium (fünf Lieferungen nacheinander; ein Issue, Schluss erst nach S4)

## Scope

- **Enthalten:** Alle Frontend-Stellen, die die Vorlagen-ID heute selbst bestimmen (Alarme-Reiter, Vorlagenname in Hub-Übersicht, Abo-Karten und Vergleichsliste, Anlegen als Kopie), übernehmen `vorlage_id` aus `POST /api/ampel/aufloesung`; danach wird `vorlageIdFuer` samt `PROFIL_ZU_VORLAGE` gelöscht. Dateien je Scheibe: Tabellen unter „Scheiben".
- **Nicht enthalten:** Python-Auflösung und Endpunkt (unverändert), `GET /api/templates`, `auswahlLesen`/`aktiveMetriken`/`DERIVED_METRIC_RULES` (siehe Known Limitations).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/ampel/aufloesung` (`app.ampel.resolve_entwurf`) | endpoint | einzige Quelle der Vorlagen-ID, unverändert |
| `GET /api/templates` | endpoint | bleibt für die Vorlagen-Ampeln („Alarm ab"-Vorgabe) |
| `shared/wetter-tab/ampelAufloesung.ts` (`loeseAmpelnAuf`, `eintragAusAbo`) | module | Client der Auflösung, Pakete à 32 |
| `shared/hub-uebersicht/tripAufloesung.ts` | module | Vorbild: Ticket, Cache je Eintrag, scheitert nie |
| `alerts-tab/alarmAbAnzeige.ts` (`ladeVorlagenAmpeln`, `STANDARD_VORLAGE`, `alarmAbAus`) | module | bleiben |
| `shared/wetter-tab/__tests__/wetterTabDaten.ts` | test helper | ruft echtes `resolve_entwurf` per Subprozess (Zeilen 107-130) |
| ADR-0127 | adr | Entscheidungsgrundlage |

## Implementation Details

**Lader (S1):** `vorlagenIdLader.ts` nimmt Abos entgegen, bildet je Abo den Schlüssel `JSON.stringify(eintragAusAbo(abo))`, schickt alle noch nicht gecachten Einträge in einem gebündelten Aufruf von `loeseAmpelnAuf` und liefert je Abo `{ zustand: 'laedt' | 'geladen' | 'fehler', vorlageId: string | null }`. Modulweiter Cache je Schlüssel, Ticket gegen veraltete Antworten, wirft nie. Es wird nur `vorlage_id` verwendet; die aufgelöste Ampel enthält Abo-Abweichungen und taugt nicht als „Alarm ab"-Vorgabe, diese kommt weiter aus der Vorlagen-Ampel (`/api/templates`).

**Anzeige:** `aboVorlagenName(lang, vorlageId | null)` liefert den Anzeigenamen der ID oder „—". Listen (Trip-Liste, Vergleichsliste) laden alle sichtbaren Zeilen in einem Aufruf (Pakete à 32 durch `loeseAmpelnAuf`).

**Kopie beim Anlegen (S2):** Die Quelle wird serverseitig in `routes/compare/new/+page.server.ts` aufgelöst (dort wird die Quelle schon geladen), das Ergebnis `vorlageId` geht als Seitendaten an den Editor und von dort als Argument an `feldsatzAusVorlage(preset, locations, vorlageId)`. Der bestehende Startwert-Mechanismus (`untrack`) bleibt, der Editor startet erst nach der Auflösung. Scheitert die Auflösung (Netzfehler, 4xx/5xx), startet der Editor ohne Vorlagen-ID: Name, Orte, Versand, Alarme, Tagesfenster und Layout der Quelle werden wie bisher übernommen, nur die Vorlage bleibt auf der Anlege-Voreinstellung (wie bei einem Neuanlegen ohne Quelle). Keine Fehlerseite, kein geratener Wert aus der Rangfolge.

**Parität:** Python kennt nur Systemvorlagen (`AMPEL_TEMPLATES`), das Frontend leitete dieselbe Menge aus `/api/templates` ab; bei gültigen Daten ändert sich nichts. Unterschied: `aboVorlagenName` übergab bisher kein `preset_name`, `eintragAusAbo` schon. Bei einem Ortsvergleich mit `preset_name` gewinnt künftig das Server-Ergebnis (dasselbe wie im Reiter Wetter); der alte Name ignorierte `preset_name` dort.

### Scheiben (je höchstens 250 LoC Produktcode, höchstens 5 Produktdateien, einzeln auslieferbar; `vorlageIdFuer` bleibt bis S4)

**S1 – Lader und Alarme-Reiter (ca. 120 LoC).**

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/vorlagenIdLader.ts` | CREATE | gebündelter, gecachter Lader `Abo → vorlage_id` |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | `vorlageAmpel = vorlagenAmpeln[vorlageId]`; ID fehlt ⇒ null ⇒ „—" |
| Tests | CREATE | `vorlagenIdLader.test.ts` (echtes `resolve_entwurf`), AlarmeTab-Fälle |

**S2 – Kopie beim Anlegen (ca. 100 LoC).**

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare-new/compareNewVorlage.ts` | MODIFY | `feldsatzAusVorlage(…, vorlageId)`, `JEDE_VORLAGE` entfällt |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Prop `vorlageId`, an `feldsatzAusVorlage` |
| `frontend/src/routes/compare/new/+page.server.ts` | MODIFY | löst die Quelle vor dem Start auf, Fehler ⇒ `vorlageId: null` |
| `frontend/src/routes/compare/new/+page.svelte` | MODIFY | reicht `data.vorlageId` durch |
| Tests | MODIFY | `compareNewVorlage.test.ts`, `anlegen_ohne_profil_3198.test.ts:223` |

**S3a – Name und Hub-Übersicht (ca. 90 LoC).**

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/wetter-tab/vorlageName.ts` | MODIFY | `aboVorlagenName(lang, vorlageId \| null)` |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts` | MODIFY | `wertebereicheKarte` nimmt `vorlageId` |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | MODIFY | lädt per Lader |
| Tests | MODIFY | `hub_uebersicht_vorlagenrang_2988.test.ts`, `compare_hub_fidelity.test.ts:86-90`, `vergleich_hub_sprache.test.ts:294`, `feat3298_vergleich_ohne_altfelder.test.ts:259` |

**S3b – Abo-Karte und Listen (ca. 130 LoC).**

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` | MODIFY | Name/ID als Prop statt eigener Rangfolge |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | lädt per Lader |
| `frontend/src/routes/_home/SubscriptionKachel.svelte` | MODIFY | lädt per Lader |
| `frontend/src/routes/trips/+page.svelte`, `frontend/src/routes/compare/+page.svelte` | MODIFY | Listen laden gebündelt; Vergleichsliste-Spalte „Vorlage" |
| Tests | MODIFY | `vorlage_statt_profil_2796.test.ts:82-103`, `reaktivitaet_waechter.test.ts:107` |

**S4 – Rangfolge löschen (ca. 60 LoC, überwiegend Löschungen).**

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/alerts-tab/alarmAbAnzeige.ts` | MODIFY | `vorlageIdFuer`, `PROFIL_ZU_VORLAGE` entfernt |
| Tests | MODIFY/DELETE | `alertMetricLevelRowTitleRender.test.ts:35,96-100` (Unit-Test von `vorlageIdFuer` fällt weg), Rest-Tests, Grep-Nachweis |

## Expected Behavior

- **Input:** Trip oder Ortsvergleich (Ampel, `preset_name`, `profil`), Ortsvergleich-Quelle beim Anlegen.
- **Output:** Vorlagenname und „Alarm ab"-Vorgabe der Server-Vorlage; „—" bei Laden und Fehler.
- **Side effects:** Zusätzlicher Lese-Aufruf je Ansicht, in Listen genau einer pro 32 Zeilen; identische Einträge werden nicht erneut abgefragt. Keine Änderung an Speicher-Payloads oder Bestandsdaten.

## Test Plan

### Automated Tests (TDD RED, aus Nutzersicht)
- [ ] Kern Frontend (`node --test`, Lese-Client mit echtem Python `resolve_entwurf` per Subprozess nach `wetterTabDaten.ts:107-130`, kein Mock-Theater): AC-1 bis AC-9
- [ ] Anzupassende Tests (Signaturen nachziehen, Regeltests durch echtes `resolve_entwurf` ersetzen): `alertMetricLevelRowTitleRender.test.ts`, `vorlage_statt_profil_2796.test.ts`, `compare_hub_fidelity.test.ts`, `compareNewVorlage.test.ts`, `feat3298_vergleich_ohne_altfelder.test.ts`, `vergleich_hub_sprache.test.ts`, `anlegen_ohne_profil_3198.test.ts`, `hub_uebersicht_vorlagenrang_2988.test.ts`, `reaktivitaet_waechter.test.ts`
- [ ] Live (Playwright gegen Staging): AC-1, AC-3, AC-5
- [ ] AC-8 Grep-Nachweis als Dateiinhalt-Check, ausdrücklich mit Marker `# doc-compliance-test` (einzige erlaubte Ausnahme der Test-Politik)
- Bewusste Ausnahme: kein Zwei-Nutzer-Test, weil der Endpunkt keine Nutzerdaten liest oder schreibt (siehe Querschnitts-Prüfpunkte)
- [ ] Rot zuerst: S1 AC-1, AC-6, AC-7; S2 AC-5; S3a AC-2, AC-9; S3b AC-3, AC-4; S4 AC-8

## Acceptance Criteria

- **AC-1:** Given ein Trip und ein Ortsvergleich, deren Vorlage der Server aus Ampel-Vorlage, Vorlagenname oder Profil auflöst / When der Reiter Alarme geöffnet wird / Then zeigt die „Alarm ab"-Vorgabe den Wert der vom Server aufgelösten Vorlage, nicht den einer vom Frontend errechneten; solange die Antwort aussteht und bei einem Fehler steht „—".
  - Scheibe: S1
  - Test: Kern `vorlagenIdLader.test.ts` und AlarmeTab-Fall mit echtem `resolve_entwurf` (Trip und Vergleich); Live `frontend/e2e/rework-3399-alarme.spec.ts`.

- **AC-2:** Given ein Ortsvergleich in der Hub-Übersicht / When die Karte Wertebereiche geladen ist / Then entspricht der angezeigte Vorlagenname der Server-Vorlage; solange die Antwort aussteht und bei einem Auflösungsfehler steht „—", nie „Allgemein".
  - Scheibe: S3a
  - Test: Kern `hub_uebersicht_vorlagenrang_2988.test.ts` (Zustände laedt, geladen, fehler mit echtem Python bzw. fehlschlagendem Client).

- **AC-3:** Given die Abo-Karte auf der Startseite, im Hub-Kopf, in der Trip-Liste und in der Vergleichsliste / When die Karten angezeigt werden / Then zeigt jede den Vorlagennamen der Server-Vorlage, bis zur Antwort und bei Fehler „—".
  - Scheibe: S3b
  - Test: Kern je Einbinder (`vorlage_statt_profil_2796.test.ts` angepasst); Live `frontend/e2e/rework-3399-karten.spec.ts`.

- **AC-4:** Given die Vergleichsliste mit mehreren Zeilen / When die Spalte „Vorlage" geladen wird / Then zeigt jede Zeile den Namen der Server-Vorlage, und alle Zeilen werden in einem gebündelten Aufruf (nicht einem je Zeile) aufgelöst; die Trip-Liste ebenso.
  - Scheibe: S3b
  - Test: Kern `vorlagenIdLader.test.ts` mit zählendem Client (ein Aufruf für bis zu 32 Zeilen, ein weiterer erst ab Zeile 33).

- **AC-5:** Given die Anlege-Seite „Vergleich als Kopie" mit einer Quelle / When die Seite geöffnet wird / Then übernimmt der Editor die vom Server aufgelöste Vorlage der Quelle als Vorlage der Kopie, schon beim Start; scheitert die Auflösung, startet der Editor ohne Vorlagen-ID (Vorlage auf der Anlege-Voreinstellung), alle übrigen Felder der Quelle sind übernommen und es erscheint keine Fehlerseite.
  - Scheibe: S2
  - Test: Kern `compareNewVorlage.test.ts` (mit ID und mit `null`), `anlegen_ohne_profil_3198.test.ts`; Live `frontend/e2e/rework-3399-kopie.spec.ts`.

- **AC-6:** Given dieselben Abos erscheinen mehrfach (Hub, Karte, Alarme-Reiter) / When die Ansichten nacheinander öffnen / Then wird für identische Einträge der Auflösung kein weiterer Aufruf gesendet (Cache je Eintrag), und eine veraltete Antwort überschreibt keine neuere Änderung.
  - Scheibe: S1
  - Test: Kern `vorlagenIdLader.test.ts` (Aufrufzähler, Ticket-Reihenfolge).

- **AC-7:** Given ein Abo, dessen Auflösung die Vorlage „alpen-trekking" liefert und dessen Ampel von der Vorlage abweicht / When die „Alarm ab"-Vorgabe angezeigt wird / Then stammt sie aus der Vorlagen-Ampel von `/api/templates` und enthält keine Abweichung des Abos (nur die ID kommt aus der Auflösung).
  - Scheibe: S1
  - Test: Kern AlarmeTab-Fall (Abo mit Abweichung, Vorgabe gleich Vorlagenwert).

- **AC-8:** Given der Stand nach S4 / When im Frontend-Quelltext nach `vorlageIdFuer` und `PROFIL_ZU_VORLAGE` gesucht wird / Then gibt es keinen Treffer außerhalb von Kommentaren, und die Anzeigen der AC-1 bis AC-5 laufen unverändert grün.
  - Scheibe: S4
  - Test: Grep-Nachweis in `reaktivitaet_waechter.test.ts` (Ausnahme `# doc-compliance-test`, Ratschen-Wächter) plus die Kerntests der AC-1 bis AC-5 als Verhaltensnachweis.

- **AC-9:** Given ein Ortsvergleich mit gesetztem `preset_name`, den die alte Namensanzeige ignorierte / When der Vorlagenname angezeigt wird / Then gilt das Ergebnis des Servers (Rang Ampel-Vorlage vor `preset_name` vor `profil`, unbekannte Vorlage fällt auf „Allgemein" durch den Server), dieselbe Vorlage wie im Reiter Wetter.
  - Scheibe: S3a, S3b
  - Test: Kern `hub_uebersicht_vorlagenrang_2988.test.ts` (Fall `preset_name` gesetzt, Referenz echtes `resolve_entwurf`).

## Definition of Done

- AC-1 bis AC-9 grün (Kern ohne Netz, Live-Teile gegen Staging), fünf Lieferungen S1, S2, S3a, S3b, S4 eingespielt.
- `vorlageIdFuer` und `PROFIL_ZU_VORLAGE` existieren nicht mehr; Issue #3399 wird erst nach S4 geschlossen.
- Produktion aktualisiert, Selftest Exit 0.

## Known Limitations

- **`auswahlLesen`, `aktiveMetriken`, `DERIVED_METRIC_RULES`** bleiben im Frontend (siehe Known Limitations von `rework_2988_ampel_ableitung.md`).
- **`/api/templates` bleibt:** die Vorlagen-Ampeln für die „Alarm ab"-Vorgabe kommen weiter von dort; nur die Vorlagen-ID kommt aus der Auflösung.
- Ansichten brauchen eine erreichbare Auflösung; offline steht „—" statt eines Namens.
- Bis zur Antwort steht „—" (kurzes Aufblitzen beim Öffnen); frühere Anzeigen erschienen sofort.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Der Umbau setzt ADR-0127 Nr. 3 („Frontend hält kein Metrik-Wissen") und ADR-0106 (Server löst auf) um. Datenmodell, Speicherweg, Kanäle, Auth und Editor-Paradigma bleiben unverändert; es wird keine bestehende Entscheidung rückgängig gemacht.

## Changelog

- 2026-11-26: Initial spec created (Phase 3), Grundlage `docs/context/rework-3399-vorlage-aufloesung.md`.
