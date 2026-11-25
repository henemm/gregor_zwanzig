# Context: rework-2988-ampel-ableitung

Issue #2988 (Eintrag **P10** in #1986; „NEU-7" im Issue-Text ist dort nicht zu finden). Priorität medium, kein Ausfall.

## Request Summary

Die Ampel-Ableitung (Vorlage + Abo-Abweichungen → aufgelöste Ampel, aktive Metriken, Abweichungszahl) existiert in Python und noch einmal im Frontend. Ziel laut Issue: nur Python leitet ab, das Frontend liest das Ergebnis; der Paritätstest wird überflüssig oder bleibt als Regressionswächter.

## Related Files

Abkürzung: `WT/` = `frontend/src/lib/components/shared/wetter-tab/`.

| File | Relevance |
|------|-----------|
| `src/app/ampel.py` | Quelle: `_aufloesen`/`template_id_for`, `_verschmelzen`, `resolve_ampel` (rund 35 Produktaufrufe), `deviation_count` und `ampel_for` (beide ohne Produktaufrufer), `validate_ampel` (`src/app/loader.py:1038`) |
| `WT/ampelModell.ts` | Spiegel: `verschmelzen`, `zaehleAbweichungenGegen`, `zaehleAbweichungen`, `ampelFehler`, `aktiveMetriken`, `eigeneVorlageAmpel`, `zuruecksetzen`, `vorlageIdVon` |
| `WT/wetterZustand.ts` | Hauptverbraucher: `standAusAbo` (:101), `mitEnabled` (:117), `BASIS_IM_KONTEXT`/`vorlageImKontext`, `mengeVon`, `abweichungenVon` (:165), `mitVorlage` (:171) |
| `WT/ampelSchreiben.ts` | `abweichungsMenge` (:39): Umkehrung der Ableitung (Minimalmenge für das Speichern), **nur im Frontend vorhanden**, kein Python-Gegenstück |
| `WT/wetterTabLaden.ts` | `aktiveMetriken` (:51), `eigeneVorlageAmpel` (:89), Laden von `/api/metrics`, `/api/templates`, `/api/metric-presets` |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | Editor: `signatur` (:113, aus `mengeVon`), `aendern` (:137), Grenzen-/Gewitterprüfung (:162), Anzeige (:223–238) |
| `frontend/src/lib/components/alerts-tab/alarmAbAnzeige.ts` | `vorlageIdFuer` (:66): weiterer Spiegel von `_aufloesen`, mit Tabelle `PROFIL_ZU_VORLAGE`; genutzt von `AlarmeTab.svelte`, `vorlageName.ts`, `wetterZustand.ts`, `compareNewVorlage.ts`. Nicht im Issue-Wortlaut |
| `internal/handler/ampel.go` | Dritter Spiegel, nur Validierung beim Speichern. Nicht im Issue-Wortlaut |
| `api/routers/config.py:25` | `GET /api/templates` liefert die vollständigen Vorlagen-Ampeln aus Python |
| `api/routers/placements.py`, `src/services/placements_view_service.py:101`, `internal/handler/placements.go:232`, `WT/wasStehtWoSpeicherung.ts` | Vorbild „Server leitet für ungespeicherten Entwurf ab" |

**Aufrufer der Frontend-Exporte (Produkt):** `verschmelzen` → wetterZustand, WetterTabInhalt · `zaehleAbweichungenGegen` → wetterZustand · `aktiveMetriken` → ampelSchreiben, wetterTabLaden, wetterZustand · `eigeneVorlageAmpel` → wetterTabLaden · `zuruecksetzen` → wetterZustand · `grenzenFehler`/`gewitterFehler` → WetterTabInhalt · `gleicheSeite` → ampelSchreiben · `vorlagenAusTemplates` → HubOverview, HubUebersicht, wetterTabLaden.
**Ohne Produktaufrufer (nur Tests):** `zaehleAbweichungen`, `ampelFehler` (wird aber intern von `verschmelzen` benutzt), `vorlageIdVon` (intern von `zaehleAbweichungen` und `eigeneVorlageAmpel` benutzt).

## Existing Patterns

- **Server-Ableitung für einen Entwurf:** `POST /api/briefings/placements/vorschau?kind=` nimmt einen ungespeicherten Entwurf, schreibt nichts. Go setzt `user_id` aus der Anmeldung, Grenze 256 KiB. Frontend: 400 ms Entprellung, veraltete Antworten per Ticket verworfen (`wasStehtWoSpeicherung.ts:115–120`, :171). Heute nur im Anlegen genutzt.
- **Lese-Antworten** (`GET /api/trips/{id}`, `GET /api/compare/presets/{id}`) kommen allein aus dem Go-Store: `display_config.ampel` roh, ohne Auflösung, ohne Python-Aufruf. Keine Antwort enthält heute eine Abweichungszahl.
- **Speichern:** automatisch, 700 ms Entprellung; Trip zwei PUTs, Ortsvergleich über die Hub-Schreibschlange (If-Match, 412 → neu laden), Anlegen ohne Netz bis zum Anlege-POST.
- **Fehlerfall im Reiter:** scheitert das Laden, erscheint „Erneut laden". Keine eigene Offline-Behandlung.

## Dependencies

- **Upstream:** `AMPEL_TEMPLATES` (`src/app/ampel_templates.py`), `/api/templates`, `/api/metrics`, `/api/compare/metrics`, `DERIVED_METRIC_RULES` (Frontend-Kopie von `loader.py:988`).
- **Downstream:** Reiter Wetter (Trip, Ortsvergleich, beide Anlege-Ketten), Speicher-Payloads, eigene Vorlagen, Karte „Was steht wo". Python-Renderer lesen `resolve_ampel` und sind vom Umbau nicht berührt, solange die Quelle gleich bleibt.

## Existing Specs

- `docs/specs/modules/feat_2794_s3a_teil3_wetter.md`: :143 definiert den Spiegel ausdrücklich (Zeilenangaben zu `ampel.py` veraltet); :149 „Frontend hält beide Quellen konsistent", verworfen: Resolver-Umstellung (ii) und Ableitung in Go (iii). Eine Ableitung in Python per Endpunkt wurde dort nicht erwogen. :238 **AC-28**, :247 **AC-37**, :253 **AC-39**; :314 nennt die Entscheidung lokal und umkehrbar.
- `docs/specs/modules/feat_2794_s3a_reiter_wetter.md`: :144, :266.
- `docs/specs/modules/feat_3222_windrichtung.md`: S4 (#3230, offen) ändert `ampelModell.ts`/`ampelSchreiben.ts`.
- ADR-0106, ADR-0126, ADR-0127 (Frontend und Go halten kein Metrik-Wissen).

## Tests und Fixtures

| Fixture | Python | Frontend | Go |
|---|---|---|---|
| `ampel_auswahl_paritaet.json` (7 Vorlagen, 11 Fälle) | `test_2794_teil3_auswahl_paritaet.py` | `ampelModell.auswahl_paritaet.test.ts` | – |
| `ampel_deviation_cases.json` (22) | `test_ampel_abweichungszaehler.py` | `ampelModell.paritaet.test.ts`, `ampelModell.test.ts` | – |
| `ampel_validierung_vektoren.json` (32) | `test_ampel_modell_und_aufloesung.py` | `ampelModell.test.ts` | `ampel_validierung_test.go` |
| `ampel_windrichtung_cases.json` (19 + 4) | `test_feat_3222_windrichtung_kern.py` | `ampelModell.test.ts` | `ampel_windrichtung_test.go` |

Die Metadaten in `ampel_deviation_cases.json` nennen eine nicht vorhandene Testdatei (`test_2794_ac28_abweichungszaehler.py`). Rund 30 Frontend-Tests nutzen `vorlagenAusTemplates`, viele laden das Modul über `__tests__/wetterTabDaten.ts`.

**Ratsche** (`tests/unit/ein_katalog_ausnahmen.json`): `ampelModell.ts` FRONTEND_LISTE 2, FRONTEND_VERZWEIGUNG 1; `internal/handler/ampel.go` GO_VERZWEIGUNG 2. `wetterZustand.ts`, `ampelSchreiben.ts`, `wetterTabLaden.ts` nicht gelistet (kein Befund erlaubt).

## Risks & Considerations

1. **Zielkonflikt mit AC-28:** Der Zähler muss „nach jeder Eingabe sofort" stimmen; heute läuft er lokal, ohne Netz. Ein Serverergebnis bringt Verzögerung und einen Fehlerfall. Das ist die Kernfrage der Analyse.
2. **Speichern hängt an der Ableitung:** `signatur` (löst das automatische Speichern aus) und die Speicher-Payload nutzen `mengeVon` → `abweichungsMenge`. Liest das Frontend nur den Zähler vom Server, bleibt die Ableitung für das Speichern im Frontend bestehen; zieht auch das Speichern um, ändert sich der Schreibweg (Bestandsdaten, Read-Modify-Write, #102).
3. **Zähler nicht deckungsgleich:** `deviation_count` zählt gegen die Rohvorlage (`ampel.template`), der Editor gegen die „Vorlage im Kontext" (#3193: abgeleitete Kinder im Trip, nicht ausgebbare Größen im Ortsvergleich neutral) und auf der Minimalmenge. Der Paritätstest deckt `zaehleAbweichungen` ab, das kein Produktcode aufruft. Die Editorzahl hat kein Python-Gegenstück.
4. **Vorlagenwechsel und Zurücksetzen** brauchen nur Vorlagen, die `/api/templates` schon fertig liefert (`verschmelzen(vorlage, null)` ist dort nur eine Kopie). Echte Ableitung steckt in `standAusAbo` (Erst-Laden), `eigeneVorlageAmpel` (eigene Vorlagen) und in Zähler/Menge (je Eingabe).
5. **`aktiveMetriken` und `auswahlLesen`** mischen gespeicherte Liste, Mail-Standard und Ampel; Abgrenzung in der Spec nötig.
6. **Umfang:** Ein vollständiger Umzug (Laden, Zähler, Menge, Validierung, Vorlagen-ID) liegt voraussichtlich über 250 LoC und 5 Dateien; Schnitt in Scheiben prüfen.
7. **Überschneidungen:** #3357 (offen) ändert `VorlageKarte.svelte`, `WetterMetrikenVersandPanel.svelte`; #3230 (S4 Windrichtung) ändert `ampelModell.ts`/`ampelSchreiben.ts`; #3260 läuft am selben Grundsatz.
8. **Mandantentrennung:** ein neuer Endpunkt braucht `user_id` aus der Anmeldung und Tests mit zwei Nutzern (Vorbild `placements.go:232`).

## Nebenbefund (gelesen, nicht ausgeführt)

`zeilenAbweichung` (`WT/ampelSchreiben.ts:28`) vergleicht `enabled`, Grenzen und `alarm_ab`, aber nicht `modus`/`sektoren`. Ein gespeicherter abweichender Windrichtungs-Modus fehlt damit in der erzeugten Minimalmenge. Heute setzt keine Oberfläche diese Felder (S4 #3230 offen); über die API gesetzte Werte können beim nächsten Speichern im Reiter betroffen sein (ob Go die gespeicherten Felder dabei erhält, ist nicht geprüft). Ausführung scheiterte, weil in diesem Arbeitsordner die Frontend-Pakete nicht installiert sind. In der Analyse mit dem Umzug der Minimalmenge klären oder an #3230 geben.

## Offene Fragen für die Analyse

1. Welcher Teil zieht um: nur Lesen (aufgelöste Ampel beim Laden), auch Zähler, auch die Minimalmenge beim Speichern?
2. Wie wird AC-28 („sofort") mit einem Serverergebnis erfüllt, und was zeigt der Reiter bis zur Antwort oder ohne Netz? Produktfrage nur, falls sich das sichtbare Verhalten ändert.
3. Gehören `vorlageIdFuer` und die Go-Validierung in dieses Issue (nicht im Wortlaut)?
4. Werden die unbenutzten Stellen (`zaehleAbweichungen`, `deviation_count`, `ampel_for`) entfernt oder zur einzigen Quelle ausgebaut?

## Analysis

### Type

Feature (Rework, kein sichtbar geändertes Verhalten). Keine Produktfrage an den PO, weil AC-28 („sofort") und der Fehlerfall AC-9 unverändert gelten.

Belegart: alle Aussagen sind am Code gelesen, nichts davon ist ausgeführt. Frontend-Pakete sind in diesem Arbeitsordner nicht installiert; der Zufallstest der unabhängigen Bewertung scheiterte am `$lib`-Alias. Die Gleichheiten unter „Nachweispflicht" sind deshalb in /40 als Test zu belegen.

### Variantenvergleich (LoC und Dateizahlen geschätzt)

| | A: alles je Eingabe vom Server | B: Auflösung in Python, Editier-Delta im Frontend |
|---|---|---|
| Produktdateien | rund 16 | rund 13 |
| Produkt-LoC | +600 / −450 | +330 / −200 |
| AC-28 „sofort" | verletzt (Entprellung + Netz) | erfüllt |
| Automatisches Speichern, Anlegen | hängen am Netz | bleiben lokal |
| Neuer Fehlerfall | bei jeder Eingabe | nur beim Laden (AC-9 „Erneut laden" besteht) |
| Lieferungen à 250 LoC | 4–5 | 4 |

**Empfehlung: B.** Jede Rechnung existiert danach einmal: die **Auflösung** (Vorlage + Abweichungen → Ampel, Vorlagen-ID, Gültigkeit) nur in Python, das **Editier-Delta** (Minimalmenge, hat in Python kein Gegenstück) nur im Frontend.

### Technical Approach

1. **Endpunkt (Python, Go reicht durch):** zustandsloser, angemeldeter POST, nimmt eine Liste von Einträgen: Abo-Sicht `{ampel, preset_name, profil}` oder eigene Vorlage `{ampel}` bzw. Altbestand `{metrics}`. Antwort je Eintrag `{vorlage_id, ampel}` aus `_aufloesen`/`_verschmelzen`. Liest nur `AMPEL_TEMPLATES` und den Rumpf, kein Store. Vorbild `BriefingPlacementsPreviewHandler` (`internal/handler/placements.go`): 401 ohne Anmeldung, 256 KiB, Objektprüfung; `ProxyHandler` reicht nicht (nur GET). `user_id` setzt `forwardPreview`. Test mit zwei Nutzern und ohne Anmeldung. Eintrag in `docs/reference/api_contract.md` (erzwungen durch `tests/test_api_contract_drift.py`).
2. **Altbestand eigene Vorlagen** (`eigeneVorlageAmpel`, Zweig ohne `ampel`, AC-39) wandert nach Python; dort fehlt er heute.
3. **Zähler:** `abweichungenVon` = Zahl der Einträge in `mengeVon(...).metrics` + 1 bei `thunder`. Die Prüfung „Vorlage fehlt → 0" bleibt. `zaehleAbweichungenGegen`, `zaehleAbweichungen`, Python `deviation_count` entfallen (kein Produktaufrufer).
4. **`mitEnabled`** setzt `enabled` direkt; **`aboAmpel`** (`WetterTabInhalt.svelte:238`) wird aus `aufgeloest` + Auswahl gebaut. Fehlende Auswahl-Zeilen mit `ohneZeile()` ergänzen, null-Grenzen wie heute zu leer normalisieren, `template` aus der Basis. Bewusste Abweichung: `modus`/`sektoren` bleiben in der eigenen Vorlage erhalten (heute verloren).
5. **`zuruecksetzen`:** Kopie der fertigen Vorlage aus `/api/templates`, keine Ableitung.
6. **Laden:** `LeseClient` bekommt `post`; `ladeWetterDaten` lädt Vorlagen/Katalog/eigene Vorlagen und fragt danach die Auflösung in EINEM Aufruf (Abo + eigene Vorlagen) ab. `standAusAbo` bekommt die aufgelöste Ampel hereingereicht und bleibt synchron.
7. **412 (`vergleichSaveFn`):** Auflösung VOR `neuGeladen` abwarten (im Speicherer, nach dem `get`), `neuGeladen` bleibt synchron und atomar. Scheitert die Auflösung, gilt derselbe Weg wie beim gescheiterten `get` (kein Neuladen, Konflikt gemeldet).
8. **`vorlageGespeichert`:** Antwort des POST trägt schon die vollständige Ampel; direkt übernehmen. In der Spec festhalten, dass das nur für frisch gespeicherte Vorlagen gilt.
9. **Übersichten** (`hubUebersichtModell.ts`), im Issue nicht genannt, rufen `standAusAbo` synchron:
   - `wertebereicheKarte` (Orte) nutzt nur `auswahl`. Bei geladenem Katalog greift dort nie die Ampel (Liste oder Mail-Standard), also direkt `auswahlLesen`, kein Serveraufruf.
   - `tripAlarmZaehler` (Trip, zwei Verwendungen) braucht die aufgelöste Ampel: `HubOverview` lädt sie beim Öffnen und bei Trip-Änderung; bis dahin „—" wie heute bei nicht geladenen Vorlagen.

Danach entfallen im Frontend: `verschmelzen`, `ampelFehler`, `metrikFehler`, `windrichtungUngueltig`, `WIND_MODI`/`WIND_SEKTOREN`, `zaehleAbweichungen(Gegen)`, `zeileWeichtAb`, `richtungWeichtAb`, `vorlageIdVon`, `eigeneVorlageAmpel`. Bleiben: `grenzenFehler`/`gewitterFehler` (Meldungen während der Eingabe), `gleicheSeite`, `abweichungsMenge`, `aktiveMetriken`, `auswahlLesen`. Die Ratsche `ein_katalog_ausnahmen.json` für `ampelModell.ts` schrumpft.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/ampel.py` | MODIFY | Auflösung für Entwurfseinträge inkl. Altbestand eigener Vorlagen; `deviation_count` entfällt |
| `api/routers/ampel.py`, `api/main.py` | CREATE / MODIFY | POST-Endpunkt, Registrierung |
| `internal/handler/ampel_aufloesung.go`, `internal/router/router.go` | CREATE / MODIFY | Durchreichen mit Anmeldung und Größengrenze |
| `docs/reference/api_contract.md` | MODIFY | Endpunkt |
| `WT/ampelModell.ts`, `WT/wetterZustand.ts`, `WT/wetterTabLaden.ts`, `WT/wetterTabSpeicherung.ts` | MODIFY | Spiegel entfernen, Serverergebnis lesen, 412 |
| `organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | Laden, `aboAmpel`, Vorlage gespeichert |
| `shared/hub-uebersicht/hubUebersichtModell.ts`, `trip-detail/HubOverview.svelte` (evtl. `HubUebersicht.svelte`) | MODIFY | aufgelöste Ampel hereinreichen |
| `tests/unit/ein_katalog_ausnahmen.json` | MODIFY | schrumpft |
| Tests | MODIFY / CREATE | 31 Frontend-Testdateien betroffen (23 nutzen `standAusAbo`); Hilfe in `__tests__/wetterTabDaten.ts`, das schon Python per `uv run` aufruft. Neu: Endpunkt (Python, Go) |

### Scope Assessment

- Files: rund 13 Produktdateien, rund 35 Testdateien
- Estimated LoC: +330/-200 Produkt
- Risk Level: MEDIUM (Reiter Wetter in Trip, Orte, Anlegen; Speicherweg bleibt unverändert)

**Schnitt, jede Lieferung für sich auslieferbar:**
1. **S1 (ohne Netz):** Zähler aus der Menge, `aboAmpel`/`mitEnabled` ohne `verschmelzen`, `deviation_count` weg. Rund 80 LoC.
2. **S2:** Endpunkt Python + Go + Vertrag, mit Regressionsfixture. Rund 200 LoC.
3. **S3:** Reiter Wetter liest das Ergebnis (Laden, eigene Vorlagen, 412).
4. **S4:** Übersichten lesen das Ergebnis, Spiegel und überflüssige Tests löschen, Ratsche senken.

### Dependencies und Reihenfolge

- **#3357 (offen):** berührt nur `VorlageKarte.svelte` und einen Vorlagen-Test. Kein Warten.
- **#3230 (offen):** keine Voraussetzung. Dort steht der Nebenbefund an, dass `zeilenAbweichung` `modus`/`sektoren` nicht in die Menge schreibt; gehört zu #3230, hier nicht beheben. Nach S1 zählt der Zähler diese Felder mit, sobald die Menge sie trägt.
- **Nicht in diesem Issue:** Go-Validierung (`ampel.go`, notwendige Schreibgrenze, Fixture-Wächter bleibt), `vorlageIdFuer` in `AlarmeTab`, `vorlageName`, `compareNewVorlage` (Namensanzeige bzw. Alarm-Anzeige), `DERIVED_METRIC_RULES`, `ampel_for`, Umzug von `auswahlLesen`. Vorlagen-ID des Reiters selbst kommt nach S3 vom Server; für die übrigen Nutzer von `vorlageIdFuer` in S4 Folge-Issue anlegen.

### Nachweispflicht (in /40 rot bzw. als Wächter)

- Zähler aus der Menge = heutiger Zähler, über die Fixtures und erzeugte Fälle (beide Kontexte).
- Eigene Vorlage aus dem neuen `aboAmpel`: gleiche Wirkung wie heute (Payload-Vergleich, Ausnahme `modus`/`sektoren`).
- Endpunkt gleich `resolve_ampel` für alle 7 Vorlagen, ungültige Ampel, unbekannte Vorlage, `profil`, `preset_name`, Altbestand; zwei Nutzer, ohne Anmeldung 401.
- Zähler im Reiter ändert sich nach einer Eingabe ohne Netzaufruf.
- Laden mit gescheiterter Auflösung zeigt AC-9, speichert nichts; 412 verliert keine Eingabe still.
- `ampel_deviation_cases.json` und `ampel_auswahl_paritaet.json` werden zu Regressionsfixtures; der falsche Testname in den Metadaten wird korrigiert.
- AC-28 und AC-37 in `feat_2794_s3a_teil3_wetter.md` und `feat_2794_s3a_reiter_wetter.md` als teilweise abgelöst markieren (nur der Teil „Python-Referenz und Frontend-Spiegel gleich").

### Beantwortete offene Fragen

1. Es zieht um: Auflösung, Vorlagen-ID des Reiters, Gültigkeit, Altbestand eigener Vorlagen. Zähler und Menge bleiben im Frontend.
2. AC-28 bleibt lokal erfüllt; keine Produktfrage.
3. Nein (siehe „Nicht in diesem Issue").
4. `zaehleAbweichungen` und `deviation_count` entfallen, `ampel_for` bleibt.

### Open Questions

Keine.

## RED-Stand Scheibe S1 (2026-11-25)

Dieser Durchlauf liefert **nur S1** (AC-1, AC-2, AC-3, AC-14, Python-Zähler weg). Für S2 bis S4 folgt je Scheibe ein eigener RED-Schritt im selben Workflow, sonst wäre S1 nicht einzeln auslieferbar.

- **Referenz:** `tests/fixtures/ampel_zaehler_referenz_2988.json`, 367 Fälle (Zähler, gepackte eigene-Vorlage-Ampel) und 93 Speicher-Rümpfe, einmalig aus dem Code vor dem Umbau (Stand b47b34553) erzeugt; der Generator ist bewusst nicht eingecheckt. Fälle: `WT/__tests__/zaehlerFaelle2988.ts`, Prüfstand: `WT/__tests__/reiter2988.ts`.
- **Rot (15):** `eigene_vorlage_payload_2988.test.ts` (12: `aboAmpelVon` fehlt, `modus`/`sektoren` gehen im Dialog verloren), `tests/tdd/test_2988_kein_python_zaehler.py` (3).
- **Von Anfang an grün (Wächter, kein RED möglich, weil der Umbau das Verhalten erhalten soll):** `zaehler_referenz_2988`, `speicher_payload_2988`, `zaehler_ohne_netz_2988`. Ihre Schärfe ist in /50 per Mutation nachzuweisen (Gewitter nicht mitzählen, `mitEnabled` mutiert Vorlage, Menge statt Vorlage im Kontext, Kind-Ableitung).
- **Vertrag:** `aboAmpelVon(stand, vorlagen, context, alt = {})` in `wetterZustand.ts`; tiefe Kopie, keine `null`-Grenzen, jede Zeile mit `lower`/`upper`; nichtssagende Zeilen ohne Vorlagen-Zeile bleiben weg. `thunder` und `template` aus der Vorlage im Kontext plus Stand.
- **In /50 zu entfernen:** `tests/tdd/test_ampel_abweichungszaehler.py` ganz; in `test_ampel_modell_und_aufloesung.py` `test_abweichungszahl_zaehlt_grenzen_gewitter_und_alarmstufe` und der Import; in `test_feat_3222_windrichtung_kern.py` `test_abweichungszahl_modus_und_sektoren`, `test_sektoren_vergleich_als_menge_bei_gleichem_modus` und der Import. Fixtures bleiben (Frontend liest sie bis S4). Ist `_vorlage_der_ampel` danach ohne Aufrufer, entfällt es mit.
- **Bekannt:** Die Fälle `windrichtung_modus_abweichend` und `windrichtung_sektoren_hinzugefuegt` stehen in der Referenz mit 0 (heutiges Verhalten, Known Limitation, gehört zu #3230); das `expected: 1` der alten Fixture galt der Python-Zahl.
- **Live:** `frontend/e2e/rework-2988-zaehler.spec.ts` (nicht ausgeführt, läuft in `/e2e-verify`).

## Hinweise aus der Gegenprüfung S1 (2026-11-25)

- **S3 (F004):** `aboAmpelVon` setzt vollständige Zeilen und vollständiges `thunder` im Stand voraus. Die vom Endpunkt gereichte Ampel muss beides tragen (Test in S3).
- **S4 (F005):** `zaehleAbweichungenGegen` hat keinen Produktaufrufer mehr. Mit dem Löschen entfällt der Wächter für den Mengenvergleich der Sektoren (`ampelModell.test.ts`); er gehört dann zu #3230. Die Metatexte in `ampel_deviation_cases.json` (`_issue`) und `ampel_windrichtung_cases.json` (`_abweichung`) nennen noch entfernte Python-Funktionen.
- **F007 (Bestand):** `mitEigenerVorlage` ist für `enabled === true` und `nurAusgebbar` ohne Wächter; in S3 mit absichern.
- **Offen beobachten:** `test_einstellung_gleich_mail_validatoren.py` lief im breiten Lauf zweimal ins 30-s-Zeitlimit (wechselnder Test), allein immer grün.

## RED-Stand Scheibe S2 (2026-11-25)

Dieser Durchlauf liefert **nur S2** (AC-4 bis AC-8, AC-19). S1 ist eingespielt und auf Staging geprüft.

- **Referenz:** `tests/fixtures/ampel_aufloesung_2988.json`, 138 Fälle (131 Abo-Sicht, 7 Altbestand), einmalig aus dem Frontend-Code vor dem Umbau (Stand 80cf9f726) erzeugt; Generator bewusst nicht eingecheckt. Gegenprobe: alle 131 Abo-Fälle stimmen heute mit `resolve_ampel` überein. Ausgelassen ist nur `template_kein_string` (bekannte Verhaltensangleichung); die Angleichung selbst prüft `test_ac5_ungueltige_ampel_verliert_auch_ihre_vorlage`.
- **Rot:** `tests/tdd/test_2988_ampel_aufloesung.py` (Router fehlt), `internal/handler/ampel_aufloesung_2988_test.go` (`AmpelAufloesungHandler` fehlt, das Testpaket baut bis dahin nicht), `internal/router/ampel_aufloesung_route_2988_test.go` (404), `tests/test_api_contract_drift.py::test_inventory_lists_ampel_aufloesung`.
- **Von Anfang an grün (Wächter):** `test_ac19_resolve_ampel_unveraendert` (131 Fälle). Schärfe in /50 per Mutation nachweisen.
- **Vertrag:** Go `AmpelAufloesungHandler(pythonURL string)` in `internal/handler/ampel_aufloesung.go`, prüft Form selbst (kein Kern-Aufruf bei 400/413), reicht den Rumpf byte-gleich weiter, Query genau `user_id`. Python `api/routers/ampel_aufloesung.py` mit `router`; Kern-400 trägt `code: bad_request` und `detail` in Nutzersprache (Text nur über den Katalog).
- **Fallen für /50:** (1) FastAPI-Standard bei kaputtem JSON ist 422, verlangt ist 400. (2) `validate_ampel` prüft Mengenzugehörigkeit ohne Typprüfung (`alarm_ab: []`, `thunder.mittel: []` sind nicht hashbar); gelesen, nicht ausgeführt. Der Endpunkt darf daran nicht scheitern. (3) `1e999` wird in Python `inf` und sprengt die JSON-Antwort; gilt als ungültige Ampel. (4) Altbestand: nur `enabled is True`, unlesbare Zeilen übergehen. (5) `{}` als `ampel` ist Abo-Sicht, nicht Altbestand.

## Offen aus der Gegenprüfung S2 (2026-11-25, beide LOW, nicht blockierend)

- **F006:** Der Vertrag (`api_contract.md`, Zeile `/api/ampel/aufloesung`) und sein Wächter schreiben „256 KB", umgesetzt und getestet sind 256 KiB. Bei der nächsten Berührung in S3/S4 angleichen.
- **F007:** Kein Test prüft Großschreibung bei `alarm_ab`, `thunder.mittel`, `thunder.hoch` („RED" ist ungültig). In S3 einen Testfall ergänzen.
