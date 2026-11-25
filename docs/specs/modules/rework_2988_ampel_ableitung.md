---
entity_id: rework_2988_ampel_ableitung
type: refactor
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: rework-2988-ampel-ableitung
tags: [ampel, rework, p10, einzige-quelle, endpunkt]
---

# Ampel-Ableitung nur einmal (Python), das Frontend liest das Ergebnis

## Approval

- [ ] Approved

## Purpose

Aus den Einstellungen eines Trips oder Ortsvergleichs wird die fertige Wetter-Ampel (Grenzen, aktive Metriken, Alarmstufen) heute an zwei Stellen zusammengesetzt: im Server und noch einmal in der Oberfläche. Beide Rechnungen müssen bei jeder Änderung von Hand gleich gehalten werden, und ein Paritätstest bewacht das. Nach diesem Umbau rechnet nur noch der Server; die Oberfläche fragt das Ergebnis ab und zeigt es an.

Für Nutzer ändert sich nichts Sichtbares: Der Zähler „von der Vorlage abweichend" reagiert weiter sofort beim Tippen, der Reiter Wetter zeigt dieselben Werte, gespeichert wird dasselbe. Nur beim Öffnen des Reiters (und der Trip-Übersicht) wird einmal mehr beim Server nachgefragt; scheitert das, erscheint wie bisher „Erneut laden", und es wird nichts gespeichert.

Grundlage ist Issue #2988 (Eintrag P10 der Paritäts-Bestandsaufnahme #1986). Analyse, Variantenvergleich (Variante B ist entschieden), Schnitt, Liste „Nicht in diesem Issue" und Nachweispflicht: `docs/context/rework-2988-ampel-ableitung.md`. Dort steht es, hier nicht wiederholt.

## Source

- **File:** `src/app/ampel.py`, `api/routers/ampel_aufloesung.py` (neu), `internal/handler/ampel_aufloesung.go` (neu), `frontend/src/lib/components/shared/wetter-tab/`
- **Identifier:** `resolve_ampel`, `resolve_entwurf` (neu), `POST /api/ampel/aufloesung` (neu), `standAusAbo`, `abweichungenVon`, `ladeWetterDaten`

> **Schicht-Hinweis:** Auflösung im Python-Core (`src/app/`, `api/`); Durchreichen mit Anmeldung in der Go-API (`internal/`); Lesen und Editier-Delta im SvelteKit-Frontend. Die Go-Validierung `internal/handler/ampel.go` bleibt unberührt (Known Limitations).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Ein Baustein in `shared/wetter-tab/` (`context="route"|"vergleich"`), keine Neuanlage mit Pendant. Die neue Abfrage-Funktion `ampelAufloesung.ts` ist kontextfrei.
> - **Mandantentrennung:** Der Endpunkt liest und schreibt keinen Nutzerbestand. `user_id` kommt aus der Anmeldung (Go), nie `"default"`; Test mit zwei Nutzern und ohne Anmeldung (AC-7).
> - **Kanäle:** Keine Auswirkung. E-Mail, Telegram, SMS und Premium-SMS lesen weiter `resolve_ampel`, unverändert (AC-19). Kein Design-Einfluss.

## Estimated Scope

- **LoC:** ca. +350/-220 Code, vier Scheiben je höchstens 250 LoC Code (Tests, Doku, Fixtures zählen nicht)
- **Files:** 14 Produktdateien, ca. 35 Testdateien (31 Frontend-Testdateien nutzen den Spiegel, 23 davon `standAusAbo`)
- **Effort:** high (vier Lieferungen nacheinander; ein Issue, Issue-Schluss erst nach S4)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app/ampel.py` (`_aufloesen`, `_verschmelzen`, `resolve_ampel`, `validate_ampel`) | module | Die einzige Auflösung; der Endpunkt ruft sie |
| `app/ampel_templates.py` (`AMPEL_TEMPLATES`, `DEFAULT_TEMPLATE`) | module | Vorlagen, Rückfall „allgemein" |
| `GET /api/templates`, `/api/metrics`, `/api/metric-presets`, `/api/compare/metrics` | endpoint | liefern weiter Vorlagen, Katalog, eigene Vorlagen (unverändert) |
| `internal/handler/placements.go` (`BriefingPlacementsPreviewHandler`), `preview_proxy.go` (`forwardPreview`) | module | Vorbild: Anmeldung, 256 KiB, Objektprüfung, `user_id` aus der Anmeldung |
| `api/routers/placements.py`, `services/send_outcomes.py` (`error_body`) | module | Vorbild Router und Fehlerform |
| `docs/reference/api_contract.md`, `tests/test_api_contract_drift.py` | doc/test | Vertrag, Drift-Wächter |
| `tests/unit/ein_katalog_ausnahmen.json` | ratchet | sinkt in S4 |
| ADR-0106, ADR-0126, ADR-0127 | adr | tragen die Entscheidung (siehe ADR-Abschnitt) |

## Implementation Details

### Der Endpunkt (S2)

`POST /api/ampel/aufloesung`, Go-Route (angemeldet) reicht an Python gleichen Pfads durch. Der Name folgt dem Vorbild `.../placements/vorschau` (Substantiv).

- **Rumpf:** JSON-Objekt `{"eintraege": [Eintrag, ...]}`. Ein Eintrag ist ein Objekt mit optionalen Feldern `ampel` (Objekt oder null), `preset_name` (Text oder null), `profil` (Text oder null), `metrics` (Liste `{metric_id, enabled}` oder null). Es gibt zwei Formen: Abo-Sicht (Trip/Ortsvergleich oder eigene Vorlage mit `ampel`) und Altbestand einer eigenen Vorlage (`ampel` fehlt oder null UND `metrics` ist eine Liste).
- **Antwort 200:** `{"ergebnisse": [{"vorlage_id": "<id>", "ampel": {…vollständige Ampel…}}, ...]}`, gleiche Länge und Reihenfolge wie `eintraege`. `ampel.template` ist gleich `vorlage_id`.
- **Je Eintrag Abo-Sicht:** exakt `resolve_ampel` (Rang `ampel.template` > `preset_name` > `profil`, `summer_trekking` → `alpen-trekking`). Eine ungültige Ampel (Regeln `validate_ampel`) ist kein Fehler: sie wird mit Logzeile ignoriert und die Vorlage greift. Eine unbekannte Vorlage (oder ein unbekanntes Profil) fällt auf „allgemein". Ergebnis ist nie ein Fehler je Eintrag.
- **Altbestand:** Vorlage „allgemein", alle Zeilen `enabled=false`, dann `enabled=true` für jede Listenzeile mit `enabled: true` (fehlende Zeile wird mit leeren Grenzen und `alarm_ab: never` angelegt). Das ist die Umsetzung von `eigeneVorlageAmpel` (AC-39 der Reiter-Spec).
- **Fehler:** 401 `unauthorized` ohne Anmeldung (Go, vor allem anderen); 413 `payload_too_large` über 256 KiB; 400 `bad_request`, wenn der Rumpf kein JSON-Objekt ist, `eintraege` keine Liste ist, mehr als 32 Einträge enthält, ein Eintrag kein Objekt ist, `preset_name`/`profil` kein Text und `metrics` keine Liste ist. Bei 400 wird nichts teilweise beantwortet. Python antwortet bei denselben Fehlern ebenfalls 400 (innere Grenze). Die Gültigkeit des Inhalts von `ampel` ist kein 400, sondern der Rückfall oben.
- **Zustandslos:** kein Store-Zugriff, keine Datei unter `data/users/<user_id>/`, kein ETag. `user_id` setzt Go aus der Anmeldung (Client-Wert verworfen) und reicht ihn als Query durch; Python braucht ihn nur für die Sprache der Fehlertexte. Das Ergebnis hängt nie vom Nutzer ab. Zeitlimit wie `previewProxyTimeout`.
- **Python:** neue Funktion `resolve_entwurf(eintrag)` in `src/app/ampel.py` (Formweiche + `_aufloesen`/`_verschmelzen`, kein zweiter Algorithmus); `api/routers/ampel_aufloesung.py` prüft die Form und ruft sie. Registrierung in `api/main.py`.
- **Vertrag:** Tabellenzeile und Abschnitt in `docs/reference/api_contract.md`.

### Was im Frontend bleibt (und warum)

„Nur Python leitet ab" gilt für die **Auflösung**: Vorlage + Abweichungen → Ampel, Vorlagen-ID des Reiters, Gültigkeit, Altbestand eigener Vorlagen. Im Frontend bleibt das **Editier-Delta**, weil es in Python kein Gegenstück hat und jede Eingabe sofort wirken muss (AC-28 der Reiter-Spec):

- `abweichungsMenge`/`zeilenAbweichung` (`ampelSchreiben.ts`): die kleinste Menge, die gespeichert wird. Der Zähler ist danach schlicht die Zahl ihrer Einträge (+1 bei Gewitterfarbe), die Rechnung steckt nur einmal im Frontend.
- `grenzenFehler`/`gewitterFehler` (Meldung während der Eingabe, bevor etwas gespeichert wird), `gleicheSeite`, `aktiveMetriken`, `auswahlLesen` (mischt Liste, Mail-Standard, Ampel; eigene Abgrenzung, kein Teil dieses Issues), `mitEntwurf`, `mitMetrik`, `ohneMetrik`, `mitAlarmAb`.
- `mitEnabled` setzt `enabled` direkt, das neue `aboAmpel` (für „Als eigene Vorlage speichern") wird aus der aufgelösten Ampel und der Auswahl gebaut (fehlende Zeilen als leere Zeile, offene Grenzen als leere Seite, `template` aus der Vorlage im Kontext); `modus`/`sektoren` bleiben darin erhalten (heute gehen sie verloren, bewusste Verbesserung).
- Vorlagenwechsel und Zurücksetzen kopieren die fertige Vorlage aus `/api/templates`, es wird nichts abgeleitet.

### Scheiben (je höchstens 250 LoC Code, einzeln auslieferbar, Reihenfolge S1, S2, S3, S4)

**S1 – Zähler und Eigene-Vorlage-Ampel ohne Spiegel (ca. 90 LoC, ohne Netz).** Vorher werden aus dem alten Code Referenzzahlen erzeugt und eingecheckt (`tests/fixtures/ampel_zaehler_referenz_2988.json`).

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/.../shared/wetter-tab/wetterZustand.ts` | MODIFY | `abweichungenVon` zählt Menge-Einträge; `mitEnabled` ohne `verschmelzen`; neues `aboAmpelVon` |
| `frontend/.../organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | `aboAmpel` über `aboAmpelVon` |
| `src/app/ampel.py` | MODIFY | `deviation_count`, `_richtung_weicht_ab`, `_ohne_offene` entfernt (kein Produktaufrufer) |
| `tests/tdd/test_ampel_abweichungszaehler.py`, `tests/tdd/test_ampel_modell_und_aufloesung.py`, `tests/tdd/test_feat_3222_windrichtung_kern.py` | MODIFY/DELETE | Verweise auf `deviation_count` entfallen, Fixtures bleiben |
| Frontend-Tests, `tests/fixtures/ampel_zaehler_referenz_2988.json` | CREATE/MODIFY | AC-1, AC-2, AC-3, AC-14 |

**S2 – Endpunkt (ca. 190 LoC).** Python, Go, Vertrag; noch kein Aufrufer. Regressionsfixture `tests/fixtures/ampel_aufloesung_2988.json` wird einmalig mit dem noch vorhandenen Frontend-Code erzeugt (7 Vorlagen, ungültige Ampel, unbekannte Vorlage, `profil`, `preset_name`, Altbestand) und eingecheckt.

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/ampel.py` | MODIFY | `resolve_entwurf` |
| `api/routers/ampel_aufloesung.py`, `api/main.py` | CREATE/MODIFY | Router, Registrierung |
| `internal/handler/ampel_aufloesung.go`, `internal/router/router.go` | CREATE/MODIFY | Handler nach Vorbild `BriefingPlacementsPreviewHandler`, Route |
| `docs/reference/api_contract.md` | MODIFY | Vertrag, Changelog |
| Tests | CREATE | `tests/tdd/test_2988_ampel_aufloesung.py`, `internal/handler/ampel_aufloesung_2988_test.go`, Router-Route-Test; AC-4 bis AC-8, AC-19 |

**S3 – Reiter Wetter liest das Ergebnis (ca. 220 LoC).** Beim Laden und bei „Erneut laden" ein Aufruf für Abo-Sicht plus alle eigenen Vorlagen der Art (Pakete zu je 32 Einträgen, damit 256 KiB und die Eintragsgrenze nie reißen); `standAusAbo` bekommt die aufgelöste Ampel hereingereicht und bleibt synchron; `zuruecksetzen` kopiert nur noch; frisch gespeicherte eigene Vorlage übernimmt die Ampel aus der POST-Antwort (`/api/metric-presets` liefert sie vollständig, gilt nur für frisch gespeicherte); im Ortsvergleich wird bei 412 die Auflösung vor `neuGeladen` abgewartet (im Speicherer, nach dem `get`); scheitert sie, gilt derselbe Weg wie beim gescheiterten `get` (kein Neuladen, Konflikt gemeldet, `neuGeladen` bleibt synchron und atomar).

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/.../shared/wetter-tab/ampelAufloesung.ts` | CREATE | `loeseAmpelnAuf(client, eintraege)`, Pakete, wirft bei Fehler |
| `frontend/.../shared/wetter-tab/wetterTabLaden.ts` | MODIFY | `LeseClient.post`; `ladeWetterDaten` löst auf; `eigeneVorlageAus` nimmt die Ampel entgegen |
| `frontend/.../shared/wetter-tab/wetterZustand.ts` | MODIFY | `standAusAbo(…, aufgeloest, …)`, `mitVorlage` ohne `verschmelzen` |
| `frontend/.../shared/wetter-tab/wetterTabSpeicherung.ts` | MODIFY | 412: Auflösung nach dem `get`, vor `neuGeladen` |
| `frontend/.../organisms/wetter-tab/WetterTabInhalt.svelte` | MODIFY | Laden, `neuGeladen`, `vorlageGespeichert` |
| `frontend/.../shared/wetter-tab/ampelModell.ts` | MODIFY | `zuruecksetzen` als Kopie |
| Tests | CREATE/MODIFY | Hilfe `__tests__/wetterTabDaten.ts` (ruft schon echtes Python per `uv run`); AC-9 bis AC-15 |

**S4 – Übersichten, Spiegel löschen, Ratsche (ca. 190 LoC, überwiegend Löschungen).**

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/.../shared/hub-uebersicht/hubUebersichtModell.ts` | MODIFY | `tripAlarmZaehler` (damit `tripAlarmAbText` und `tripWetterAlarmAktiv`) erhält die aufgelöste Ampel, ohne sie „—"/false; `wertebereicheKarte` liest `auswahlLesen` direkt (bei geladenem Katalog greift die Ampel dort nie) |
| `frontend/.../trip-detail/HubOverview.svelte` | MODIFY | lädt die Auflösung beim Öffnen und bei Änderung der Trip-Ampel (Ticket gegen veraltete Antworten wie `wasStehtWoSpeicherung.ts`) |
| `frontend/.../shared/hub-uebersicht/HubUebersicht.svelte` | MODIFY (nur falls nötig) | Aufruf der Karte unverändert halten |
| `frontend/.../shared/wetter-tab/ampelModell.ts` | MODIFY | entfernt: `verschmelzen`, `ampelFehler`, `metrikFehler`, `windrichtungUngueltig`, `WIND_MODI`, `WIND_SEKTOREN`, `zaehleAbweichungen(Gegen)`, `zeileWeichtAb`, `richtungWeichtAb`, `vorlageIdVon`, `eigeneVorlageAmpel` |
| `tests/unit/ein_katalog_ausnahmen.json` | MODIFY | Zähler für `ampelModell.ts` sinkt |
| Spiegel-Tests, `ampel_deviation_cases.json`, `ampel_auswahl_paritaet.json` | DELETE/MODIFY | Paritätstests entfallen, Fixtures werden Regressionsfixtures; falscher Testname in den Metadaten wird korrigiert |
| `docs/specs/modules/feat_2794_s3a_teil3_wetter.md`, `feat_2794_s3a_reiter_wetter.md` | MODIFY | Markierung AC-28/AC-37 (nur hier, in S4) |
| `docs/adr/0126-*.md` | MODIFY | Nachtrag zur Folgepflicht (TS-Spiegel und `deviation_count` entfallen, #2988) |

### Bezug zu den Specs `feat_2794_s3a_teil3_wetter.md` und `feat_2794_s3a_reiter_wetter.md`

Teilweise abgelöst wird nur der Teil „Python-Referenz und Frontend-Spiegel liefern dieselbe Zahl/Menge":
- **AC-28** (teil3 Zeile 238, reiter Zeile 266): „Python-Referenz `deviation_count` und Frontend-Spiegel liefern dieselbe Zahl" entfällt (es gibt nur noch die Frontend-Zählung auf der Menge). Weiter gültig: fünf Änderungsarten zählen einmal je Metrik, Zurücknehmen zählt nicht, der Picker zeigt die Zahl sofort (hier AC-1, AC-2).
- **AC-37** (teil3 Zeile 247): „Frontend-Ableitung und Python `resolve_ampel` liefern dieselbe Menge aktiver Metriken" entfällt als Parität (nur noch Python leitet ab). Weiter gültig: beide Auswahlquellen konsistent, Speicherung der Abweichungsmenge (hier AC-14).
- Die Entscheidung in teil3 Zeile 149 („Frontend hält beide Quellen konsistent") wird für die Auflösung abgelöst; die Verwerfung von Ableitung in Go bleibt bestehen.

## Expected Behavior

- **Input:** Abo-Sicht des Trips/Ortsvergleichs und eigene Vorlagen (nur Lesen), danach Nutzereingaben im Reiter.
- **Output:** Reiter, Zähler, Übersichten und gespeicherte Daten wie vor dem Umbau; Auflösung stammt allein aus Python.
- **Side effects:** Ein zusätzlicher Lese-Aufruf beim Öffnen des Reiters und der Trip-Übersicht. Keine Änderung der Speicher-Payloads oder Bestandsdaten.

## Test Plan

### Automated Tests (TDD RED, aus Nutzersicht)
- [ ] Kern Frontend (`node --test`, Lese-Client-Einspeisung mit echtem Python aus `wetterTabDaten.ts`, kein Mock-Theater): AC-1 bis AC-3, AC-9 bis AC-18
- [ ] Kern Python (pytest, FastAPI-`TestClient`, ohne Netz): AC-4 bis AC-8, AC-19
- [ ] Kern Go (`go test`): AC-7
- [ ] Live (Playwright gegen Staging, Request-Zähler und zwei Sitzungen): AC-1, AC-10 bis AC-12, AC-15
- [ ] Rot zuerst: S1 AC-1 bis AC-3 und AC-14 (Referenz vor Umbau erzeugt); S2 AC-4 bis AC-8; S3 AC-9 bis AC-13, AC-15; S4 AC-16 bis AC-18

## Acceptance Criteria

- **AC-1:** Given der Reiter Wetter eines Trips und eines Ortsvergleichs ist geöffnet / When der Nutzer eine Grenze ändert, „Alarm ab" umstellt, eine Metrik hinzufügt oder entfernt, die Gewitterfarbe ändert, eine Vorlage übernimmt oder zurücksetzt / Then zeigt der Zähler sofort die neue Zahl, und dabei geht kein Netzaufruf an die Auflösung.
  - Scheibe: S1, wiederholt in S3
  - Test: Kern `frontend/.../wetter-tab/__tests__/zaehler_ohne_netz_2988.test.ts` (Client zählt Aufrufe), Live `frontend/e2e/rework-2988-zaehler.spec.ts` (Request-Zähler je Kontext).

- **AC-2:** Given die 22 Fälle aus `ampel_deviation_cases.json` und erzeugte Fälle (7 Vorlagen mal Änderungsart, Elter/Kind-Metriken, nicht ausgebbare Metriken im Ortsvergleich, Gewitterfarbe) / When der Zähler in beiden Kontexten berechnet wird / Then ist jede Zahl gleich der Referenzzahl, die vor dem Umbau mit dem alten Code erzeugt wurde.
  - Scheibe: S1
  - Test: Kern `zaehler_referenz_2988.test.ts` gegen `tests/fixtures/ampel_zaehler_referenz_2988.json`.

- **AC-3:** Given ein Reiter mit Abweichungen in beiden Kontexten / When der Nutzer „Als eigene Vorlage speichern" wählt / Then ist der gesendete Rumpf (Ampel, Metrikliste) gleich dem Rumpf vor dem Umbau; einziger Unterschied: `modus`/`sektoren` der Windrichtung bleiben erhalten statt zu fehlen.
  - Scheibe: S1
  - Test: Kern `eigene_vorlage_payload_2988.test.ts` (`eigeneVorlagePayload` mit neuem `aboAmpel`, Referenz vor Umbau).

- **AC-4:** Given eine Anfrage je der 7 Systemvorlagen / When der Endpunkt sie auflöst / Then ist die Antwort-Ampel gleich der Vorlagen-Ampel aus `GET /api/templates` (bzw. Vorlage plus Abweichungen gleich der Referenz aus `ampel_aufloesung_2988.json`), und `vorlage_id` nennt die Vorlage.
  - Scheibe: S2
  - Test: Kern `tests/tdd/test_2988_ampel_aufloesung.py` (Python-Testclient, kein Mock).

- **AC-5:** Given Einträge mit ungültiger Ampel (z. B. Grenzen in falscher Reihenfolge), unbekannter Vorlage, nur `profil` (auch `summer_trekking`, Großschreibung), nur `preset_name` und mit Vorlage in `ampel.template` / When aufgelöst / Then gilt die Rangfolge Ampel-Vorlage vor `preset_name` vor `profil`, eine ungültige Ampel wird ignoriert und die Vorlage greift, eine unbekannte Vorlage fällt auf „allgemein", und kein Eintrag erzeugt einen Fehler.
  - Scheibe: S2
  - Test: Kern `test_2988_ampel_aufloesung.py`, Fälle gegen `ampel_aufloesung_2988.json`.

- **AC-6:** Given eine eigene Vorlage im Altformat (nur `metrics`-Liste, keine `ampel`) / When aufgelöst / Then ist die Ampel gleich dem Ergebnis des heutigen `eigeneVorlageAmpel` („allgemein", nur die gelisteten und aktiven Metriken an, fehlende Zeilen leer angelegt).
  - Scheibe: S2
  - Test: Kern `test_2988_ampel_aufloesung.py` (Referenz aus dem alten Code).

- **AC-7:** Given zwei angemeldete Nutzer A und B und ein Aufruf ohne Anmeldung / When jeder denselben Rumpf sendet bzw. der Aufruf ohne Anmeldung kommt / Then antwortet der anonyme Aufruf 401, A und B erhalten dieselbe Antwort, beim Weiterreichen trägt die Anfrage je die `user_id` des angemeldeten Nutzers (nie `"default"`, ein vom Client gesendeter Wert wird verworfen), und es wird nichts unter `data/users/` gelesen oder angelegt; ein Rumpf, der kein Objekt ist, ein ungültiger Eintrag oder mehr als 32 Einträge ergeben 400, mehr als 256 KiB ergeben 413.
  - Scheibe: S2
  - Test: Kern `internal/handler/ampel_aufloesung_2988_test.go` (zwei Nutzer, 401, 400, 413) und `test_2988_ampel_aufloesung.py` (Dateibaum unverändert).

- **AC-8:** Given der neue Endpunkt / When der Vertrags-Wächter läuft / Then steht er mit Pfad, Rumpf, Antwort und Fehlerfällen in `docs/reference/api_contract.md`.
  - Scheibe: S2
  - Test: `tests/test_api_contract_drift.py` (Vertragsdrift, Ausnahme vom Dateiinhalt-Verbot).

- **AC-9:** Given ein gespeicherter Trip und ein gespeicherter Ortsvergleich mit Vorlage, Abweichungen und eigenen Vorlagen (auch im Altformat) / When der Reiter Wetter geöffnet wird / Then zeigt er dieselbe Vorlage, dieselben Zeilen, Grenzen, Alarmstufen und denselben Zähler wie vor dem Umbau, und die eigenen Vorlagen stehen mit derselben Ampel in der Liste.
  - Scheibe: S3
  - Test: Kern `wetter_laden_aufloesung_2988.test.ts` (Referenz vor Umbau), Live `frontend/e2e/rework-2988-laden.spec.ts`.

- **AC-10:** Given die Auflösung scheitert beim Laden (Netzfehler oder 5xx) / When der Reiter öffnet / Then erscheint „Erneut laden", es wird nichts gespeichert (kein PUT, kein POST), und nach „Erneut laden" mit gelingender Auflösung ist der Reiter bereit.
  - Scheibe: S3
  - Test: Kern `wetter_laden_fehler_2988.test.ts` (Schreib-Client zählt 0), Live `rework-2988-laden.spec.ts` (Endpunkt-Abbruch per Netzwerk-Regel).

- **AC-11:** Given ein Bestands-Trip und ein Bestands-Ortsvergleich (auch Altformat) / When der Reiter geöffnet wird und der Nutzer länger als die Speicher-Entprellung (700 ms) nichts eingibt / Then wird nichts automatisch gespeichert (Signatur vor und nach dem Öffnen gleich).
  - Scheibe: S3
  - Test: Kern `signatur_stabil_2988.test.ts`, Live `rework-2988-laden.spec.ts` (Schreib-Request-Zähler 0).

- **AC-12:** Given ein Ortsvergleich, den in einer zweiten Sitzung jemand zuerst geändert hat / When die erste Sitzung speichert und der Server 412 antwortet / Then lädt der Reiter den Stand neu inklusive Auflösung, die fremde Änderung ist sichtbar, der Konflikt wird gemeldet und keine eigene Eingabe geht still verloren; scheitert die Auflösung, verhält es sich wie bei einem gescheiterten Nachladen (kein Neuladen, Konflikt gemeldet).
  - Scheibe: S3
  - Test: Kern `vergleich_412_aufloesung_2988.test.ts`, Live `rework-2988-konflikt.spec.ts` (zwei Sitzungen).

- **AC-13:** Given der Nutzer speichert im Reiter eine eigene Vorlage / When der Dialog bestätigt wird / Then erscheint sie sofort in der Liste mit vollständiger Ampel aus der Antwort des Speicherns, ohne zusätzlichen Aufruf der Auflösung, und lässt sich übernehmen.
  - Scheibe: S3
  - Test: Kern `eigene_vorlage_gespeichert_2988.test.ts`.

- **AC-14:** Given ein Stand mit Abweichungen und mit Feldern, die der Reiter nicht anfasst (andere `display_config`-Schlüssel, `report_config`, Tagesfenster) / When der Reiter speichert / Then sind die Rümpfe (Trip: `weather-config` und Trip-PUT; Ortsvergleich: PUT) gleich den Rümpfen vor dem Umbau, nichts geht verloren (Read-Modify-Write mit Merge, #102).
  - Scheibe: S1 und S3
  - Test: Kern `speicher_payload_2988.test.ts` (Referenz) plus unveränderte `ampelSchreiben.test.ts`.

- **AC-15:** Given die Anlege-Seiten für Trip und Ortsvergleich / When der Nutzer im Reiter Wetter eine Vorlage wählt, eine Grenze ändert und anlegt / Then trägt das angelegte Abo dieselbe Ampel und Auswahl wie vor dem Umbau, und vor dem Anlege-Aufruf wird nichts gespeichert.
  - Scheibe: S3
  - Test: Live `frontend/e2e/rework-2988-anlegen.spec.ts` (Trip und Ortsvergleich), Kern `anlegen_2988.test.ts`.

- **AC-16:** Given die Übersicht eines Trips / When sie öffnet, die Auflösung noch aussteht oder scheitert, bzw. danach vorliegt / Then zeigt der Alarmzähler „—" (und die Alarm-Aktiv-Aussage verhält sich wie bei nicht geladenen Vorlagen), nach der Antwort dieselbe Zahl wie der Reiter Wetter, und nach einer Änderung der Trip-Ampel wird neu aufgelöst, ohne dass eine veraltete Antwort übernommen wird.
  - Scheibe: S4
  - Test: Kern `hub_uebersicht_aufloesung_2988.test.ts`, Live `rework-2988-uebersicht.spec.ts`.

- **AC-17:** Given die Übersicht eines Ortsvergleichs / When sie öffnet / Then zeigt die Karte Wertebereiche dieselbe Metrikzahl wie vorher („—" bis der Katalog geladen ist), und dafür geht kein zusätzlicher Aufruf an die Auflösung.
  - Scheibe: S4
  - Test: Kern `wertebereiche_karte_2988.test.ts` (Aufrufzähler 0, Zahl gleich Referenz).

- **AC-18:** Given der Stand nach S4 / When die Ratsche und die Frontend-Tests laufen / Then ist der Spiegel aus dem Frontend entfernt (kein `verschmelzen`, `vorlageIdVon`, `zaehleAbweichungen`, `eigeneVorlageAmpel`, `ampelFehler` mehr), der Eintrag für `ampelModell.ts` in `tests/unit/ein_katalog_ausnahmen.json` ist gesunken (`FRONTEND_LISTE` 2 auf 0, `FRONTEND_VERZWEIGUNG` nicht höher), und `ampel_deviation_cases.json` sowie `ampel_auswahl_paritaet.json` laufen als Regressionsfixtures gegen den Endpunkt.
  - Scheibe: S4
  - Test: Kern `tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py` (Ratsche, Ausnahme vom Dateiinhalt-Verbot) und `test_2988_ampel_aufloesung.py` (Regressionsfixtures).

- **AC-19:** Given ein Abo mit Abweichungen / When E-Mail, Telegram, SMS und Premium-SMS gerendert werden / Then ist `resolve_ampel` für die 7 Vorlagen und die Fixture-Abos gleich dem Stand vor dem Umbau, und die bestehenden Renderer-Kerntests der vier Kanäle bleiben unverändert grün.
  - Scheibe: S2, bleibt bis S4
  - Test: Kern `test_2988_ampel_aufloesung.py` (Vergleich gegen eingefrorene Referenz) plus unveränderte Renderer-Tests.

## Known Limitations

Nicht umgezogen, weil nicht Teil dieses Issues (Liste „Nicht in diesem Issue" der Kontextdatei):

- **Go-Validierung** (`internal/handler/ampel.go`): notwendige Schreibgrenze, bleibt; ihr Fixture-Wächter `ampel_validierung_vektoren.json` bleibt.
- **`vorlageIdFuer`** (`alerts-tab/alarmAbAnzeige.ts`) mit Nutzern `AlarmeTab.svelte`, `vorlageName.ts`, `compareNewVorlage.ts`: Namens- und Alarm-Anzeige; `standAusAbo` verlässt sie in S3. Folge-Issue wird in S4 angelegt.
- **`auswahlLesen`/`aktiveMetriken`**, **`DERIVED_METRIC_RULES`** (Frontend-Kopie von `_DERIVED_METRIC_RULES`, `loader.py:988`), `ampel_for`: unverändert.
- **`modus`/`sektoren` in `zeilenAbweichung`:** fehlen heute in der erzeugten Menge; Behebung gehört zu #3230 (S4 Windrichtung), hier nicht. Der Zähler zählt sie mit, sobald die Menge sie trägt.
- **Kleine Verhaltensangleichung:** Bei einer gespeicherten, ungültigen Abo-Ampel ignoriert Python auch deren `template` (Vorlage dann aus `preset_name`/`profil`), das Frontend nutzte es bisher. Go verhindert das Speichern ungültiger Ampeln; der Fall betrifft nur Altdaten. Es gilt Python.
- **Auflösung ohne `kontext`:** wie `resolve_ampel` (Trip-Regeln); Gegenwind im Ortsvergleich verhindert Go beim Speichern.
- Beim Öffnen des Reiters braucht es jetzt eine erreichbare Auflösung; offline bleibt „Erneut laden" (wie schon bei Katalog und Vorlagen).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Geprüft wurden ADR-0106 (Ampel als einzige Bewertung, `resolve_ampel` als Auflösung), ADR-0126 (Windrichtung; Folgepflicht „neue Ampel-Felder in `_verschmelzen`, `deviation_count`, Go und TS-Spiegel gleichzeitig": die Teile `deviation_count` und TS-Spiegel entfallen, `_verschmelzen` und Go-Validierung gelten weiter; S4 hält das als Nachtrag im ADR fest) und ADR-0127 Nr. 3 („Frontend und Go halten kein Metrik-Wissen"). Der Umbau setzt ADR-0127 Nr. 3 und ADR-0106 um und ändert keine Entscheidungsfläche: Datenmodell, Speicherweg, Kanäle, Auth und Editor-Paradigma bleiben gleich. Der Endpunkt folgt dem etablierten Muster „Server rechnet für einen Entwurf" (#3304, `placements/vorschau`). Die Alternative in `feat_2794_s3a_teil3_wetter.md` („Frontend hält beide Quellen konsistent") war dort ausdrücklich „lokal und umkehrbar" und ist keine ADR-Entscheidung; ihre Ablösung braucht daher kein ADR. Würde später die Variante A (jede Eingabe zum Server) gewählt, wäre das ein neues ADR, weil AC-28 (sofortiger Zähler) dann berührt wird.

## Changelog

- 2026-11-25: Initial spec created (Phase 3), Grundlage `docs/context/rework-2988-ampel-ableitung.md`.
