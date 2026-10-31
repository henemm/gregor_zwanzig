---
entity_id: i18n_s0_adr_glossar_2645
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2645, docs, model-sonnet]
---

# i18n S0: ADR-0104 freigeben, Glossar abgleichen, API-Vertrag um `language` ergänzen

**Issue:** #2645 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt 1, 2, 4 (Tabelle der Wettergrößen)

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Bevor Code entsteht, muss die Grundsatzentscheidung zur Zweisprachigkeit gültig sein und das Vokabular stimmen: ADR-0104 wird von „Vorgeschlagen" auf „Akzeptiert" gesetzt, das Glossar wird mit dem Metrik-Register abgeglichen und um die Konto- und Anmeldewörter ergänzt, und der API-Vertrag nennt das neue Nutzerfeld `language` als einzige Wahrheit. Für Nutzer ändert sich noch nichts; alle späteren Pakete (S1 bis A2) lesen ab hier nur noch diese Dokumente und treffen keine eigene Wortwahl.

## Source

- **File:** `docs/adr/0104-zweisprachigkeit-de-en.md`, `docs/adr/README.md`, `docs/adr/0042-namensform-folgt-der-platzgrenze.md` (nur prüfen), `docs/reference/i18n_glossar.md`, `docs/reference/api_contract.md`
- **Identifier:** Statuszeile `**Status:**` (ADR-0104), Indexzeile `0104` (README), Abschnitte „Wettergrößen" und „Konto und Anmeldung" (Glossar), neuer Abschnitt „Nutzerprofil und Sprache" (API-Vertrag)

> **Schicht-Hinweis:** Reines Doku-Paket. Kein Go-, Python- oder Frontend-Produktcode. Die einzige neue Code-Datei ist ein Drift-Test (`# doc-compliance-test`), der Glossar, ADR-Index und Vertrag gegen den Ist-Stand prüft.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `docs/adr/0104-zweisprachigkeit-de-en.md` | MODIFY | Status auf `Akzeptiert (PO-Entscheidung <Tag der Block-Freigabe, YYYY-MM-DD>)`; Entscheidung 3: Go-Katalogpfad auf `internal/i18n/messages/{de,en}/<bereich>.json` korrigieren (Konventionen Abschnitt 2 gilt) |
| `docs/adr/README.md` | MODIFY | Indexzeile `0104`: Status-Spalte `Akzeptiert` (Klassen-Abgleich in `tests/test_adr_index_drift.py`) |
| `docs/adr/0042-namensform-folgt-der-platzgrenze.md` | prüfen, keine Änderung | Kopfzeile „Ergänzt durch: ADR-0104" steht bereits (Zeile 7) |
| `docs/reference/i18n_glossar.md` | MODIFY | Wettergrößen-Beispiele auf das Register `src/app/metric_catalog.py` korrigieren; Abschnitt „Konto und Anmeldung" neu; Zeile „Punkt" im Abschnitt „Zeit und Format" korrigieren; Kopfzeile „freigegeben" statt „Erstliste" |
| `docs/reference/api_contract.md` | MODIFY | Neuer Abschnitt „Nutzerprofil und Sprache" (Tabelle, kein ```go-Block); Inventarzeile `/api/auth/profile` und `/api/auth/register` um `language` ergänzen |
| `tests/test_i18n_glossar_und_vertrag.py` | CREATE | `# doc-compliance-test`: Glossar-Eindeutigkeit, Register-Abgleich, ADR-Status-Konsistenz, Vertragsabschnitt |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** nicht berührt (Doku). Das Glossar legt ein Vokabular für beide Kontexte fest.
- **Mandantentrennung:** nicht berührt (keine Nutzerdaten). Der Vertrag hält fest, dass `language` aus dem Auth-Kontext des angemeldeten Nutzers gelesen und geschrieben wird, nie aus einem Fallback `"default"`.
- **Kanäle:** nicht berührt. Das Glossar nennt die vier Kanäle (E-Mail, Telegram, SMS, Premium SMS) unverändert als Eigennamen.

## Estimated Scope

- **LoC:** ca. 90 Zeilen Doku-Änderung plus ca. 110 Zeilen Test (kein Produktcode)
- **Files:** 6 (5 Doku-Dateien, davon 1 nur geprüft, plus 1 Test)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Epic #2644 / Block-Freigabe des PO | process | Das Datum der Block-Freigabe (Konventionen Abschnitt 7) wird als PO-Entscheidung in die Statuszeile geschrieben |
| `tests/test_adr_index_drift.py` | test | Erzwingt Gleichstand von Dateistatus und Indexstatus |
| `tests/test_api_contract_drift.py` | test | Erzwingt Route-Inventar und verbietet erfundene ```go-Tags: der neue Abschnitt nutzt deshalb eine Tabelle |
| `src/app/metric_catalog.py` (`get_all_metrics`, `MetricDefinition.label_de`, `col_label`) | module | Wahrheit für die Wettergrößen-Beispiele im Glossar |
| ADR-0042, ADR-0095, ADR-0101 | adr | Werden von ADR-0104 ergänzt bzw. benannt |

## Implementation Details

**1. ADR-0104.** Nur die Statuszeile (Format laut `tests/test_adr_index_drift.py`: Präfix `Akzeptiert`, Zusatz in Klammern erlaubt) und Entscheidung 3 ändern. Der Text von Entscheidung 3 nennt heute `internal/i18n/messages/{de,en}.json`; richtig ist je Bereich `internal/i18n/messages/{de,en}/<bereich>.json` (Bereiche `fehler`, `auth`, `konto`, `fach`, `mail`). Alle anderen Abschnitte bleiben wörtlich.

**2. Glossar.** Fünf Beispielzeilen der Wettergrößen-Tabelle widersprechen dem Register und werden korrigiert (Register ist die Wahrheit):

| alt im Glossar | neu (aus Register und Konventionen) |
|---|---|
| Windböen / Wind gusts / Gust | Böen / Wind gusts / Gust |
| Niederschlag / Precipitation / Prec | Niederschlag / Precipitation / Rain |
| Niederschlagswahrscheinlichkeit / Precipitation probability / PoP | Regenwahrscheinlichkeit / Rain probability / Rain% |
| Gewitter / Thunderstorm / Thund | Gewitter / Thunderstorm / Thdr |
| Schneehöhe / Snow depth / Snow | Schneehöhe / Snow depth / SnowH |

Neuer Abschnitt „Konto und Anmeldung" (je Zeile genau eine englische Entsprechung): Anmelden → sign in · Abmelden → sign out · Registrieren → sign up · Passwort → password · Benutzername → username · E-Mail → email · Sprache → language · Hilfe → help · Testmail → test email. Die Zeile `12.5 (Punkt)` im Abschnitt „Zeit und Format" erhält als englische Spalte `12.5 (point)`. Die Kopfzeile „Erstliste aus der Planung, Freigabe in #2645" wird zu „freigegeben mit #2645".

**3. API-Vertrag.** Neuer Abschnitt „Nutzerprofil und Sprache (Issue #2646, Epic #2644)" als Tabelle:

| Stelle | Feld / Verhalten |
|---|---|
| `GET /api/auth/profile` | `language`: `"de"` oder `"en"`, immer vorhanden. Ein Nutzer ohne gespeichertes Feld erhält `"de"` (ADR-0104 Nr. 9); `user.json` bleibt dabei unverändert |
| `PUT /api/auth/profile` | `language` optional; nur `"de"` oder `"en"`. Anderer Wert (auch leer): 400 `{"error":"invalid_language"}`, nichts wird geschrieben. Merge-Schreibweise: Bestandsfelder bleiben (ADR-0101) |
| `POST /api/auth/register` | `language` optional; fehlt es, bleibt das Feld unbestimmt (= `de`); ungültig: 400 `{"error":"invalid_language"}`, kein Konto |
| Cookie `gz_lang` | Go setzt es bei Login, Registrierung und Profil-Update mit `language` (`Path=/`, `Max-Age=31536000`, `SameSite=Lax`, `Secure` bei https, nicht HttpOnly) |
| `POST /lang` (nur SvelteKit-Frontend, nicht Go) | Formfeld `lang`; setzt `gz_lang` für Besucher (Paket #2648) |
| Fehlerobjekt (Zielbild ab #2675) | `{"code": "...", "message": "..."}`; bis dahin bleibt `{"error": "..."}` |

Der Vertrag erwähnt `/api/me` nicht: dieser Endpunkt existiert im Router nicht; das Nutzerprofil liefert `GET /api/auth/profile`.

**4. Drift-Test** `tests/test_i18n_glossar_und_vertrag.py` (beginnt mit `# doc-compliance-test`, Pfade relativ zur Testdatei): liest das Glossar als Daten und prüft (a) jede Tabellenzeile hat eine nicht leere englische Spalte, jedes deutsche Wort kommt höchstens einmal vor, (b) in keiner englischen Spalte steht „tour", (c) die zwölf Pflichtbegriffe des Issues sowie die neuen Konto-Wörter sind vorhanden, (d) für jede Zeile der Wettergrößen-Tabelle gibt es im Register (`get_all_metrics()`) einen Eintrag mit gleichem `label_de` und gleichem `col_label`, (e) Dateistatus von ADR-0104 beginnt mit „Akzeptiert", (f) der Vertrag enthält den Abschnitt „Nutzerprofil und Sprache" mit `invalid_language` und `gz_lang`.

## Expected Behavior

- **Input:** Repository-Stand mit ADR-0104 „Vorgeschlagen", fünf abweichenden Glossar-Beispielen und ohne Sprachfeld im Vertrag.
- **Output:** ADR-0104 „Akzeptiert" in Datei und Index; Glossar stimmt mit dem Register überein; der Vertrag beschreibt `language`, `invalid_language` und `gz_lang`.
- **Side effects:** Keine. `tests/test_adr_index_drift.py` und `tests/test_api_contract_drift.py` bleiben grün.

## Acceptance Criteria

- **AC-1:** Given ADR-0104 im Repository / When der Statuswächter für den ADR-Index läuft / Then steht der Status in Datei und Index als „Akzeptiert" und es gibt keine Abweichung zwischen beiden.
  - Test: tests/test_adr_index_drift.py (bestehend) und tests/test_i18n_glossar_und_vertrag.py — beweist, dass der Status in Datei und Index übereinstimmt und mit „Akzeptiert" beginnt (`# doc-compliance-test`, Dokumentationspaket).

- **AC-2:** Given das Glossar / When ein Begriff aus dem Ist-Stand des Epics gesucht wird (Trip, Etappe, Ortsvergleich, Briefing, Wertebereiche, Versand, Alarm, Korridor, Verlässlichkeit, Standardwerte, Kürzel, Ruhetag) / Then hat jeder genau eine englische Entsprechung und kein deutsches Wort steht in zwei Zeilen mit unterschiedlicher Übersetzung.
  - Test: tests/test_i18n_glossar_und_vertrag.py — liest alle Tabellenzeilen als Daten und prüft Vollständigkeit der zwölf Pflichtbegriffe und Eindeutigkeit (`# doc-compliance-test`).

- **AC-3:** Given die Tabelle der Wettergrößen im Glossar / When sie mit dem Metrik-Register verglichen wird / Then stimmen deutscher Name und Kurzform (`col_label`) jeder Zeile mit genau einer Größe des Registers überein, sodass kein Paket eine falsche Kurzform übernimmt.
  - Test: tests/test_i18n_glossar_und_vertrag.py — ruft `get_all_metrics()` echt auf und vergleicht `label_de` und `col_label` mit den Glossarzeilen (`# doc-compliance-test`).

- **AC-4:** Given die englischen Spalten des Glossars / When nach dem Wort das im Glossar verbotene Produktwort ist untersagt bzw. „tour" gesucht wird / Then gibt es keinen Treffer, denn das Produkt kennt nur Trip, Etappe, Ortsvergleich und Briefing.
  - Test: tests/test_i18n_glossar_und_vertrag.py — prüft jede englische Tabellenspalte auf „tour" (`# doc-compliance-test`).

- **AC-5:** Given der API-Vertrag / When ein Entwickler das Sprachfeld nachschlägt / Then findet er `language` (Werte `de`/`en`, Standard `de`), den Fehlercode `invalid_language`, den Cookie `gz_lang` und den Hinweis, dass das Profil über `GET /api/auth/profile` kommt; die Drift-Wächter für Routen und JSON-Tags bleiben grün.
  - Test: tests/test_api_contract_drift.py (bestehend) und tests/test_i18n_glossar_und_vertrag.py — prüft Abschnitt und Kernbegriffe (`# doc-compliance-test`).

- **AC-6:** Given ADR-0042 und ADR-0104 / When die Kopfzeilen gelesen werden / Then nennt ADR-0042 „Ergänzt durch: ADR-0104", und ADR-0104 nennt in Entscheidung 3 den Go-Katalogpfad je Bereich (`internal/i18n/messages/{de,en}/<bereich>.json`).
  - Test: tests/test_i18n_glossar_und_vertrag.py — prüft beide Textstellen (`# doc-compliance-test`).

## Known Limitations

- Annahme: Die Wettergrößen-Tabelle der Konventionen (Abschnitt 4) deckt nicht alle Register-Einträge ab (zum Beispiel fehlen die gefühlten Tages-Tiefst-/Höchsttemperaturen und `sunshine`). Das Glossar bekommt hier nur die korrigierten Beispiele; die vollständige englische Benennung aller Größen ist Aufgabe von Paket #2662.
- Annahme: Der Beispieltag `Do 30.10.` im Glossar und im ADR bleibt als Format-Illustration stehen (der 30.10.2026 ist ein Freitag); die Formatfunktionen (#2647, #2662) werden mit berechneten Wochentagen getestet, nicht mit diesem Beispiel.
- Das Datum der PO-Entscheidung in der Statuszeile ist der Tag der Block-Freigabe aus Konventionen Abschnitt 7, nicht der Tag der Spec.
- Das Glossar regelt keine Satzbausteine; die Sentence-case-Regel steht in den Konventionen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (wird mit diesem Paket akzeptiert); ergänzt ADR-0042
- **Rationale:** Die Zweisprachigkeit berührt Datenmodell, Kanäle und Auth, daher muss die Entscheidung vor dem ersten Code gelten und das Vokabular zentral festliegen.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
