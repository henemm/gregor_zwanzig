---
entity_id: i18n_f2_hilfe_infobox_2651
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2651, frontend, python, model-haiku]
---

# i18n F2: Hilfe-Seite, Onboarding-Hilfe, Begriffserklärung und Infoboxen zweisprachig

**Issue:** #2651 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt 2, 3

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer Englisch eingestellt hat, liest die Hilfe-Seite „How Gregor works", die Erklärungen hinter dem ⓘ, die Infoboxen der Anlege-Reiter und das Willkommen mit der Startklar-Checkliste vollständig auf Englisch, mit denselben Fachbegriffen wie im Rest des Produkts (stage, location comparison, target ranges, confidence). Die Antwort-Befehle in der Hilfe zeigen dabei die englischen Befehlswörter, die der Bot schon heute versteht. Auf Deutsch bleibt jede Ausgabe wie heute.

## Source

- **File:** `frontend/src/routes/hilfe/+page.svelte`, `frontend/src/lib/components/molecules/Infobox.svelte`, `frontend/src/lib/components/molecules/BegriffErklaerung.svelte`, `frontend/src/lib/components/shared/infoboxKeys.ts`, `frontend/src/routes/_home/EmptyKachel.svelte`, `frontend/src/routes/_home/StartklarCheckliste.svelte`, `frontend/src/lib/i18n/format.ts`, `frontend/src/lib/i18n/messages/{de,en}/hilfe.json`, `.../bausteine.json`, `.../home.json`, `tests/test_hilfe_befehle_drift.py`
- **Identifier:** `befehle` (abgeleitet aus `hilfe.befehle.*`), `infoboxKey`, `BEGRIFF_KEYS`, `datum` in `StartklarCheckliste.svelte`, neu `fmtDateNumeric`, `command_rows`, `_COMMAND_SPECS` (nur gelesen)

> **Schicht-Hinweis:** Frontend (`frontend/src/...`) plus ein Python-Drift-Test, der die Python-Befehlsquelle `src/services/trip_command_processor.py` (nur lesend) mit dem Katalog vergleicht. Kein Produktcode in Python oder Go. Die Texte der Bereiche `hilfe` (42 Schlüssel), `bausteine` (20) und `home` (19) liegen seit #2647 in beiden Sprachen vor; dieses Paket prüft sie gegen das Glossar, passt die Befehlswörter an und beseitigt die letzten hartkodierten Stellen.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/routes/hilfe/+page.svelte` | prüfen | Ist bereits vollständig katalogbasiert (`$t`); nur Anpassungen, die der Test aus AC-1 verlangt |
| `frontend/src/lib/components/molecules/Infobox.svelte`, `BegriffErklaerung.svelte`, `frontend/src/lib/components/shared/infoboxKeys.ts` | prüfen | Bereits katalogbasiert; nur das Zeichen ⓘ steht im Markup |
| `frontend/src/routes/_home/EmptyKachel.svelte` | MODIFY | Zeilen 51-54 (Leerzustand für Bestandskonten) ersetzen: `title="Willkommen bei Gregor 20"`, `description="Leg deinen ersten Trip an oder starte einen Orts-Vergleich."`, `+ Neuer Trip`, `+ Neuer Vergleich` → `$t(...)` |
| `frontend/src/routes/_home/StartklarCheckliste.svelte` | MODIFY | Funktion `datum` (heute fest `'de-DE'`) → `fmtDateNumeric(new Date(iso), $locale)` |
| `frontend/src/lib/i18n/format.ts` | MODIFY | Neu: `fmtDateNumeric(d, lang)`: de `30.10.2026` (Zone Europe/Berlin, zweistellig, byte-gleich zur heutigen Ausgabe), en `30 Oct 2026` |
| `frontend/src/lib/i18n/messages/de/home.json`, `.../en/home.json` | MODIFY | Zwei neue Schlüssel `onboarding.leer.titel` und `onboarding.leer.beschreibung` (Tabelle unten) |
| `frontend/src/lib/i18n/messages/en/hilfe.json` | MODIFY | `hilfe.befehle.<wort>.befehl` auf die englischen Befehlswörter; Texte nach Glossar prüfen |
| `frontend/src/lib/i18n/messages/en/bausteine.json`, `.../en/home.json` | MODIFY | Glossar-Konformität prüfen und korrigieren (Test aus AC-3) |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | MODIFY | Einträge streichen, die zu den Dateien dieses Pakets gehören und von der Messung aus #2649 erfasst wurden (`routes/hilfe/` und Komponenten-Verzeichnisse). `routes/_home/` bleibt, solange andere Dateien dort Treffer haben (Paket #2652) |
| `tests/test_hilfe_befehle_drift.py` | MODIFY | Zusätzlich: englische Befehle gegen `_COMMAND_SPECS` (`wort_en` in Großschrift plus Argumentform) und gegen `bare_keywords()` |
| `frontend/src/lib/i18n/__tests__/glossar_konformitaet_de_en.test.ts` | CREATE | Produktbegriffe des Glossars erscheinen im englischen Text in der Glossar-Form |
| `frontend/src/routes/hilfe/__tests__/hilfe_zweisprachig.test.ts` | CREATE | Seite in `de` (Golden) und `en` (Restwort-Prüfung), vier Kanäle, Befehlstabelle |
| `frontend/src/routes/hilfe/__tests__/fixtures/hilfe.de.html` | CREATE | Golden der heutigen deutschen Ausgabe (vor der Umstellung schreiben) |
| `frontend/src/routes/_home/__tests__/onboarding_zweisprachig.test.ts` und `fixtures/onboarding.de.html` | CREATE | Willkommen, Leerzustand, Checkliste (Datum) in beiden Sprachen, Golden Deutsch |
| `frontend/src/lib/i18n/__tests__/format_datum_zeit.test.ts` | MODIFY | Fälle für `fmtDateNumeric` ergänzen |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** Die Infobox-Texte gibt es je Kontext (`...route`/`...vergleich`) über die Zuordnungstabelle `infoboxKeys.ts`; diese Teilung besteht seit #2521 und wird nicht verändert (die Standardwerte beider Kontexte sind inhaltlich verschieden).
- **Mandantentrennung:** nicht berührt; die Seiten lesen nur das eigene Profil, das der Layout-Loader schon lädt. Die Datumsausgabe nutzt die Sprache der eigenen Anfrage.
- **Kanäle:** Die Hilfe-Seite nennt alle vier Kanäle gleichrangig (E-Mail, Telegram, SMS, Premium SMS (Garmin inReach)); die englischen Texte erhalten dieselbe Reihenfolge und denselben Inhalt (ADR-0095).

## Estimated Scope

- **LoC:** ca. 120 Code (Datumsfunktion ca. 25, Komponenten ca. 20, Drift-Test ca. 40, Rest Katalogkorrekturen)
- **Files:** ca. 16
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2647 (S2) | package | Katalog `hilfe`/`bausteine`/`home` mit englischen Texten, `$t`, `fmt*` |
| #2649 (S4) | package | Ratsche und Allowlist |
| #2645 (S0) | package | Glossar (Produktbegriffe, Inbound-Befehle) |
| `src/services/trip_command_processor.py` (`_COMMAND_SPECS`, `command_rows`, `bare_keywords`) | module | Wahrheit für die Antwort-Befehle: `wort`, `wort_en`, Argumentform |
| #2521 / #2417 | issue | Hilfe-Seite und Onboarding bzw. englische Befehlswörter des Kurzform-Kanals |
| ADR-0104, ADR-0095, ADR-0042 | adr | Sprache am Nutzer, Kanal-Parität, Protokoll-Token nicht übersetzen |

## Implementation Details

**Vorgehen (Standard der F-Pakete).** Texte → Schlüssel (hier fast alle schon vorhanden), Englisch nach Glossar, Allowlist-Eintrag streichen, Ratsche und Parität grün, bestehende Tests über Katalogwerte prüfen. Nur `messages/{de,en}/hilfe.json`, `bausteine.json`, `home.json` anfassen; keine Schlüssel umbenennen; deutsche Texte nicht ändern; das im Glossar verbotene Produktwort ist untersagt.

**Befehlstabelle (englisch).** Die Antwort-Befehle sind Protokoll-Wörter. Die englischen Wörter wirken bereits wie ihr deutsches Pendant (`_BARE_KEYWORD_MAP` aus `_COMMAND_SPECS.wort_en`, #2417). Deshalb zeigt `en/hilfe.json` je `hilfe.befehle.<wort>.befehl` das englische Wort in Großschrift samt Argumentform; die deutschen Werte bleiben, damit der Drift-Test für Deutsch grün bleibt:

| Schlüssel (`hilfe.befehle.…befehl`) | de | en |
|---|---|---|
| `heute` | HEUTE | TODAY |
| `morgen` | MORGEN | TOMORROW |
| `jetzt` | JETZT | NOW |
| `gewitter` | GEWITTER | STORMS |
| `strecke` | STRECKE [km] | ROUTE [km] |
| `ruhetag` | RUHETAG [N] | RESTDAY [N] |
| `weiter` | WEITER | RESUME |
| `hilfe` | HILFE | HELP |
| `kuerzel` | KUERZEL | CODES |
| `startdatum` | STARTDATUM JJJJ-MM-TT | STARTDATE YYYY-MM-DD |
| `report` | REPORT [morning / evening] | REPORT [morning / evening] |

`status`, `pause`, `skip`, `stop` bleiben in beiden Sprachen gleich (`STATUS`, `PAUSE [2d / 12h]`, `SKIP`, `STOP`). In den englischen `.text`-Werten fehlt der Hinweis „(auch ABBRUCH)"; `CANCEL` aus dem Glossar wird erst von Paket #2673 verstanden und darf hier nicht beworben werden. Die Hinweise „(auch NOW)", „(auch HELP)", „(auch CODES)" entfallen in `en`, weil das Wort dort der Befehl selbst ist.

**Drift-Test (Python) erweitern.** `tests/test_hilfe_befehle_drift.py` liest nach #2647 `hilfe.json` (de). Neu: dieselbe Datei in `en`; für jeden Befehl aus `command_rows()` gibt es genau einen englischen Eintrag, dessen erstes Wort `wort_en.upper()` aus `_COMMAND_SPECS` entspricht (Argumentform gleich, `JJJJ-MM-TT` ↔ `YYYY-MM-DD`) und dessen Wort in `bare_keywords()` enthalten ist (echter Aufruf, kein Quelltext-Lesen).

**Beispiel-Schlüssel (de / en):**

| Schlüssel | de | en |
|---|---|---|
| `hilfe.titel` | So funktioniert Gregor | How Gregor works |
| `hilfe.kanaele.premium_sms` | Premium-SMS (Garmin inReach): Briefing und Alarme als kurzer Text über Satellit (je nach Tarif). | Premium SMS (Garmin inReach): briefing and alerts as short text via satellite (depending on your plan). |
| `tip.wertebereiche` | Ein Wertebereich legt für eine Metrik fest, welche Werte als passend gelten. … | A target range defines which values count as suitable for a metric. … |
| `onboarding.willkommen.neuer_vergleich` | + Neuer Vergleich | + New comparison |
| `onboarding.leer.titel` (neu) | Willkommen bei Gregor 20 | Welcome to Gregor 20 |
| `onboarding.leer.beschreibung` (neu) | Leg deinen ersten Trip an oder starte einen Orts-Vergleich. | Create your first trip or start a location comparison. |

`EmptyKachel.svelte` nutzt für die beiden Buttons des Leerzustands die vorhandenen Schlüssel `onboarding.willkommen.neuer_trip` und `onboarding.willkommen.neuer_vergleich` (gleicher Text, ein Schlüssel; keine Dopplung). Neu entstehen nur die zwei `onboarding.leer.*`-Schlüssel in `home.json`.

**Beispiel-Umstellung:** `frontend/src/routes/_home/EmptyKachel.svelte:51` `<EmptyState title="Willkommen bei Gregor 20" description="Leg deinen ersten Trip an oder starte einen Orts-Vergleich.">` → `<EmptyState title={$t('onboarding.leer.titel')} description={$t('onboarding.leer.beschreibung')}>`; Zeile 53 `+ Neuer Trip` → `{$t('onboarding.willkommen.neuer_trip')}`. Und `frontend/src/routes/_home/StartklarCheckliste.svelte:44` `new Date(iso).toLocaleDateString('de-DE', { timeZone: 'Europe/Berlin', … })` → `fmtDateNumeric(new Date(iso), $locale)`.

**`fmtDateNumeric`** erzeugt de `30.10.2026` (zweistellig Tag und Monat, vierstellig Jahr, Zone `Europe/Berlin`, identisch zur bisherigen Ausgabe) und en `30 Oct 2026` (Tag ohne führende Null, englische Monatskürzel aus eigener Tabelle, nicht aus `Intl`).

**Glossar-Konformitätstest** (`glossar_konformitaet_de_en.test.ts`): feste Liste Stamm → englische Form: Etappe → stage, Ortsvergleich → location comparison, Wertebereich → target range, Verlässlichkeit → confidence, Briefing → briefing, Alarm → alert, Versand → delivery, Korridor → corridor, Standardwerte → defaults. Für jeden Katalogschlüssel (alle 17 Bereiche), dessen deutscher Wert den Stamm (Groß-/Kleinschreibung egal) enthält, muss der englische Wert die englische Form enthalten (Groß-/Kleinschreibung egal, optionales Plural-`s`). Der Test liest außerdem die Glossar-Zeilen als Daten und prüft, dass jede Zeile der festen Liste dort mit derselben englischen Form steht.

**Allowlist-Eintrag, der entfernt wird:** die Einträge, die die Messung aus #2649 für `routes/hilfe/` und die Komponenten-Verzeichnisse dieses Pakets enthält; das Issue nennt `routes/hilfe`, `molecules/Infobox`, `molecules/BegriffErklaerung`, `shared/infoboxKeys`. Diese Dateien sind seit #2521 katalogbasiert und tauchen im Startstand daher nur auf, wenn die Messung Treffer fand. **Golden-Fixture:** `hilfe.de.html` und `fixtures/onboarding.de.html` (Willkommen, Leerzustand, Checkliste mit Testmail-Datum), beide VOR der Umstellung geschrieben. **Validator, Token-Wächter:** nicht berührt (Kurzform und Befehlswörter sind Protokoll-Token, siehe ADR-0042).

## Expected Behavior

- **Input:** Aufruf von `/hilfe`, der Startseite des Cockpits (Willkommen, Leerzustand, Checkliste), der ⓘ-Erklärungen und der Infoboxen mit `locale` = `de` oder `en`.
- **Output:** Alle Texte in der Sprache der Anfrage; Befehlswörter der Hilfe in der Sprache, die der Bot versteht; Datum der Testmail in der Sprachform.
- **Side effects:** Keine.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer mit Englisch / When `/hilfe` gerendert wird / Then sind Titel, Briefing-Zeiten, Alarme, die vier Kanäle (E-Mail, Telegram, SMS, Premium SMS) und die Befehlstabelle englisch, die Kanäle stehen in derselben Reihenfolge wie auf Deutsch, und es bleibt kein deutsches Restwort übrig.
  - Test: frontend/src/routes/hilfe/__tests__/hilfe_zweisprachig.test.ts — SSR-Render mit `locale` = `en`; nach Abzug aller englischen `hilfe.*`-Katalogwerte bleibt kein Wort übrig; Reihenfolge der vier Kanalschlüssel.

- **AC-2:** Given dieselbe Seite und die Onboarding-Flächen (Willkommen, Leerzustand, Checkliste mit Testmail-Datum) auf Deutsch / When sie gerendert werden / Then ist das HTML byte-gleich zur Ausgabe vor der Umstellung, insbesondere das Datum im Format `30.10.2026`.
  - Test: frontend/src/routes/hilfe/__tests__/hilfe_zweisprachig.test.ts und frontend/src/routes/_home/__tests__/onboarding_zweisprachig.test.ts — Vergleich mit `hilfe.de.html` und `onboarding.de.html` (Golden).

- **AC-3:** Given die Begriffserklärungen, Infoboxen und Hilfetexte / When ein deutscher Text einen Produktbegriff des Glossars enthält (zum Beispiel Wertebereiche, Etappe, Ortsvergleich, Alarm, Versand) / Then enthält der englische Text die Glossar-Form (target ranges, stage, location comparison, alert, delivery).
  - Test: frontend/src/lib/i18n/__tests__/glossar_konformitaet_de_en.test.ts — liest Katalog und Glossar als Daten (`# doc-compliance-test`, Konsistenzprüfung gegen das Glossar).

- **AC-4:** Given die Befehlstabelle auf Englisch / When sie mit der Python-Befehlsquelle verglichen wird / Then entspricht jeder englische Befehl samt Argumentform dem `wort_en` aus `_COMMAND_SPECS`, jedes englische Wort ist ein vom Bot erkanntes Alleinwort (`bare_keywords()`), und die deutsche Tabelle ist unverändert gleich `command_rows()`.
  - Test: tests/test_hilfe_befehle_drift.py — echter Aufruf von `command_rows()` und `bare_keywords()`; zusätzlich ein Negativfall mit einem erfundenen englischen Befehl, der rot werden muss.

- **AC-5:** Given ein Nutzer mit Englisch und ein Nutzer mit Deutsch nacheinander in derselben Serverrunde / When die Checkliste mit dem gleichen Testmail-Zeitpunkt (30.10.2026) gerendert wird / Then zeigt die englische Ausgabe `30 Oct 2026` und die deutsche `30.10.2026`, ohne dass eine die andere beeinflusst.
  - Test: frontend/src/routes/_home/__tests__/onboarding_zweisprachig.test.ts und frontend/src/lib/i18n/__tests__/format_datum_zeit.test.ts — zwei Renderläufe und die Formatfunktion mit festem Zeitpunkt.

- **AC-6:** Given der Leerzustand eines Bestandskontos auf Englisch / When das Cockpit leer ist / Then zeigt `EmptyKachel` „Welcome to Gregor 20", die Beschreibung und die Buttons „+ New trip" und „+ New comparison"; kein hartkodierter Text steht mehr in der Datei.
  - Test: frontend/src/routes/_home/__tests__/onboarding_zweisprachig.test.ts — SSR-Render von `EmptyKachel` ohne `willkommen`; der Ratschentest (bestehend) bestätigt, dass `EmptyKachel.svelte` keinen Treffer mehr hat.

- **AC-7:** Given die Allowlist nach diesem Paket / When die Ratschen- und Paritätstests laufen / Then sind sie grün, und die Allowlist enthält keinen Eintrag mehr für `routes/hilfe/`, `lib/components/molecules/Infobox.svelte`, `BegriffErklaerung.svelte` oder `infoboxKeys.ts`.
  - Test: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts und frontend/src/lib/i18n/__tests__/paritaet_de_en.test.ts (bestehend) — `# doc-compliance-test`.

## Known Limitations

- Annahme: Die vier Allowlist-Einträge aus dem Issue (`routes/hilfe`, `molecules/Infobox`, `molecules/BegriffErklaerung`, `shared/infoboxKeys`) existieren nur, wenn die Messung aus #2649 dort Treffer fand; die Dateien sind seit #2521 katalogbasiert. Der echte Restbestand dieses Pakets sind die Zeilen 51-54 in `EmptyKachel.svelte` und das feste Datumsformat in `StartklarCheckliste.svelte`.
- Annahme: Die englischen Befehlswörter in der Hilfe sind genau die heute wirksamen `wort_en`-Wörter. Das Wort `CANCEL` aus dem Glossar wird erst mit Paket #2673 verstanden und steht deshalb nicht in der Hilfe.
- Annahme: Der Name „Gregor 20" im Willkommenstitel ist ein Eigenname und bleibt in beiden Sprachen.
- `routes/_home/` bleibt in der Allowlist, bis Paket #2652 (F3) die übrigen Dateien migriert hat.
- Die Hilfe beschreibt nur die Befehle des Trip-Kanals (`command_rows("route")`), nicht die der Ortsvergleich-Antworten; das war schon so (Issue #2521).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (Nr. 4, 5, 7), ADR-0042
- **Rationale:** Erklärtexte folgen dem Glossar; Befehlswörter sind Protokoll-Token und zeigen genau das, was der Bot versteht.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
