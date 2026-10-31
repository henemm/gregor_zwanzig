---
entity_id: i18n_s4_ratsche_frontend_2649
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2649, frontend, model-sonnet]
---

# i18n S4: Ratsche Frontend (keine hartkodierten Nutzertexte in Svelte-Markup, jeder Katalogschlüssel hat einen Verwender)

**Issue:** #2649 · **Epic:** #2644 · **Modell:** Sonnet · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitt 2, 3 (Ratsche Frontend)

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Ab diesem Paket kann kein neuer deutscher Text mehr am Katalog vorbei in die Oberfläche gelangen: ein Test meldet jeden Textknoten und jedes beschriftende Attribut in Svelte-Dateien, das nicht aus dem Katalog kommt, mit Datei und Zeile. Der heutige Altbestand steht in einer Allowlist, die nur kürzer werden darf; jedes Migrationspaket (F1 bis F11) streicht seinen Eintrag. Ein zweiter Test stellt sicher, dass kein Katalogschlüssel ohne Verwender im Katalog liegen bleibt.

## Source

- **File:** `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` (neu), `frontend/src/lib/i18n/__tests__/hardcode_scan.ts` (neu), `frontend/src/lib/i18n/hardcode_allowlist.json` (neu), `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` (neu), `docs/reference/gates_und_ratschen.md`
- **Identifier:** `scanneMarkup`, `scanneVerzeichnis`, `pruefeGegenAllowlist`, `verwenderSchluessel`

> **Schicht-Hinweis:** Reines Test- und Doku-Paket im Frontend (`frontend/src/lib/i18n/`), kein Produktcode. Der Scanner ist ein Test-Hilfsmodul unter `__tests__/` und wird nicht ausgeliefert. Läuft im bestehenden Test-Werkzeug `node:test` (die Konventionen nennen Vitest; im Repo gibt es nur `node:test`, siehe #2647).

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `frontend/src/lib/i18n/__tests__/hardcode_scan.ts` | CREATE | Reiner Scanner: `scanneMarkup(quelltext) → { zeile, art, text }[]`, `scanneVerzeichnis(wurzel) → Treffer je Datei`, Kommandozeile `--messen` gibt die Präfix-Liste aus |
| `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts` | CREATE | Ratschen-Test über alle `*.svelte` unter `frontend/src/` plus Unit-Tests des Scanners an Fixtures |
| `frontend/src/lib/i18n/__tests__/fixtures/hardcode/schlecht_button.svelte`, `gut_button.svelte`, `schlecht_attribute.svelte`, `gut_attribute.svelte` | CREATE (4) | Kleine Svelte-Dateien als Prüfling für die Scanner-Unit-Tests (liegen unter `__tests__/`, werden vom echten Lauf nicht gescannt) |
| `frontend/src/lib/i18n/hardcode_allowlist.json` | CREATE | JSON-Liste von Pfad-Präfixen relativ zu `frontend/src/`, Startstand per Messung |
| `frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` | CREATE | Verwender-Test über alle Bereichsdateien |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Neuer Abschnitt „i18n-Ratschen (Epic #2644)" und eine Zeile in der Tabelle „Regel-Budget: Prüfdaten im Überblick" (Prüfdatum 2027-01-28) |

### Querschnitts-Prüfpunkte

- **Trip/Ortsvergleich-Teilung:** Die Ratsche gilt für alle Svelte-Dateien gleich; sie verlangt keine Pendant-Struktur. Texte identischer Trip-/Ortsvergleich-Flächen gehören laut Konventionen nach `aktionen.*`; das erzwingt dieses Paket nicht, die Adversary-Prüfung der F-Pakete tut es.
- **Mandantentrennung:** nicht berührt (keine Nutzerdaten, kein Endpunkt).
- **Kanäle:** nicht berührt (Weboberfläche, keine Briefing- oder Alarm-Inhalte).

## Estimated Scope

- **LoC:** ca. 220 (Scanner ca. 110, Ratschen-Test ca. 60, Verwender-Test ca. 50), dazu die Allowlist-Daten
- **Files:** 9
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| #2647 (S2) | package | Bereichsdateien `messages/{de,en}/*.json`, `index.ts` mit vereinigter Karte, Aufrufformen `t`, `$t`, `tr`, `trFor`, `tn` |
| `docs/reference/gates_und_ratschen.md` | doc | Tabelle der Gates; Regel-Budget verlangt Prüfdatum (+90 Tage) |
| Muster „Ratsche leeren macht den abhängigen Test vakuum-grün" (`gates_und_ratschen.md`) | rule | Der Test bricht ab, wenn der Scanner zu wenige Dateien findet |
| ADR-0104 | adr | Nr. 8: Ratschen mit schrumpfender Allowlist |

## Implementation Details

**Scanner (Konventionen Abschnitt 3, wörtlich umgesetzt).** Für jede `*.svelte` unter `frontend/src/` — ausgenommen Pfade mit `/__tests__/`, `routes/_design*` und `routes/email-preview-dev` — wird der Quelltext so aufbereitet, dass **die Zeilennummern erhalten bleiben** (entfernte Bereiche werden durch gleich viele Zeilenumbrüche ersetzt):

1. `<script>…</script>`, `<style>…</style>` und `<!-- … -->` entfernen.
2. Svelte-Ausdrücke `{…}` entfernen (auch `{#if …}`, `{:else}`, `{/each}`, `{@render …}`; geschachtelte geschweifte Klammern bis Tiefe 3 behandeln).
3. HTML-Entities (`&nbsp;`, `&times;`, `&amp;` …) entfernen.
4. **(a) Textknoten:** der Text zwischen Tags, der mindestens zwei Buchstaben aus `[A-Za-zÄÖÜäöüß]` enthält, ist ein Treffer (`art: 'text'`). Zeichen wie `×`, `→`, `ⓘ`, `•`, `✓` zählen nicht als Buchstaben.
5. **(b) Attribute:** statische Werte (ohne `{`) von `title`, `aria-label`, `placeholder`, `alt`, `label` mit mindestens zwei Buchstaben sind Treffer (`art: 'attribut'`).

**Allowlist.** `hardcode_allowlist.json` ist eine sortierte JSON-Liste von Zeichenketten. Ein Eintrag ist ein Pfad relativ zu `frontend/src/` mit Schrägstrichen; ein Verzeichnis endet auf `/` (Präfix), eine einzelne Datei steht vollständig. Granularität des Startstands: für Dateien unter `routes/<ordner>/` und `lib/components/<ordner>/` das Verzeichnis `routes/<ordner>/` bzw. `lib/components/<ordner>/`; Dateien direkt in `routes/` oder `lib/components/` einzeln. `lib/components/shared/` (und weitere große Ordner) dürfen von einem F-Paket durch die noch belasteten Unterordner/Dateien ersetzt werden; das ist eine Kürzung.

**Messung des Startstands (Pflicht, dokumentieren).** Der Entwickler erzeugt die Liste einmalig mit `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types src/lib/i18n/__tests__/hardcode_scan.ts --messen`, übernimmt sie in die JSON-Datei und trägt Datum, Commit und gemessene Zahlen (Dateien mit Treffern, Trefferzeilen, Einträge) in den Kopfkommentar des Ratschen-Tests und in die Doku-Zeile ein. Erwartet wird eine Liste, die mindestens die großen Bereiche des Ist-Stands aus dem Epic enthält (`lib/components/shared/`, `lib/components/compare/`, `routes/`-Unterordner, `lib/components/trip-detail/`); die Messung entscheidet, nicht diese Aufzählung.

**Ratschen-Test (zwei Richtungen).** Der Test `keine_hartkodierten_nutzertexte.test.ts` schlägt fehl, wenn (1) ein Treffer in keiner Allowlist-Zeile liegt (Meldung `Datei:Zeile  "Text"`), oder (2) ein Allowlist-Eintrag keinen einzigen Treffer mehr abdeckt (Meldung `Eintrag ohne Treffer: <eintrag> – aus hardcode_allowlist.json streichen`). Dadurch zwingt das Paket, das einen Bereich migriert, zum Streichen seines Eintrags, und ein vergessener Eintrag kann sich nicht still halten. Zusätzlich bricht der Test ab, wenn der Scan weniger als 150 Dateien findet (Messaufbau leer).

**Verwender-Test.** Sammelt alle Schlüssel der vereinigten Karte `de` und prüft, dass jeder in `frontend/src/` (ohne `__tests__/`) vorkommt als: `t('k')`, `$t('k')`, `tr('k')`, `trFor(…, 'k')`, `tn('k', …)`/`$tn('k', …)` (dann zählen `k.one` und `k.other`), als Schlüssel-Literal in einer Zuordnungstabelle (Muster `infoboxKeys.ts`: der Schlüssel steht als `'bereich.x'`-Literal in einer `.ts`/`.svelte`-Datei), oder unter einem Kommentar `// i18n-dynamic: <präfix>` (alle Schlüssel mit diesem Präfix zählen). Ein Schlüssel ohne Verwender macht den Test rot mit dem Schlüsselnamen.

**Beispiel (vorher → nachher, die Ratsche reagiert):** Eine Komponente mit `<button>Speichern</button>` ist ein Treffer (`text`); `<button>{$t('aktionen.speichern')}</button>` ist keiner. `<input placeholder="Suche">` ist ein Treffer (`attribut`), `<input placeholder={$t('aktionen.suche')}>` nicht.

**Allowlist-Eintrag, der entfernt wird:** keiner (dieses Paket legt die Liste an). **Golden-Fixture:** die vier Svelte-Fixtures unter `__tests__/fixtures/hardcode/`. **Validator, Token-Wächter:** nicht berührt.

**Doku-Zeile** in `docs/reference/gates_und_ratschen.md`: „i18n-Ratsche Frontend `keine_hartkodierten_nutzertexte.test.ts` + `katalog_schluessel_haben_verwender.test.ts` (Epic #2644, S4) — Prüfdatum 2027-01-28; Allowlist bleibt bis Abschluss von Epic #2644 bestehen und darf nur schrumpfen, danach leer."

## Expected Behavior

- **Input:** alle `*.svelte` unter `frontend/src/`, `hardcode_allowlist.json`, die vereinigte Katalogkarte.
- **Output:** grün, wenn jeder Treffer in der Allowlist steht, jeder Allowlist-Eintrag einen Treffer hat und jeder Katalogschlüssel einen Verwender hat; sonst rot mit Datei:Zeile bzw. Schlüsselname.
- **Side effects:** keine; der Scanner liest nur.

## Acceptance Criteria

- **AC-1:** Given eine neue Komponente mit `<button>Speichern</button>` außerhalb der Allowlist / When der Ratschen-Test läuft / Then ist er rot und nennt Datei und Zeile des Textknotens.
  - Test: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts — echter Scanner und echte Allowlist-Prüfung auf `fixtures/hardcode/schlecht_button.svelte` (Treffer mit Zeilennummer, nicht in der Allowlist). `# doc-compliance-test` (Ratschentest).

- **AC-2:** Given `<button>{$t('aktionen.speichern')}</button>` und ein Attribut `placeholder={$t('aktionen.suche')}` / When der Scanner läuft / Then gibt es keinen Treffer, während `<input placeholder="Suche">` und `aria-label="Schließen"` je einen Treffer der Art `attribut` ergeben.
  - Test: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts — Scanner an `gut_button.svelte`, `gut_attribute.svelte`, `schlecht_attribute.svelte`; Zeilennummern bleiben trotz entfernter Skript-/Stilblöcke korrekt.

- **AC-3:** Given der heutige Quelltext / When der Ratschen-Test über alle Svelte-Dateien läuft / Then ist er grün, weil jeder gefundene Treffer unter einem Allowlist-Präfix liegt, und er ist rot, wenn ein Allowlist-Eintrag keinen Treffer mehr abdeckt (Meldung nennt den Eintrag).
  - Test: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts — echter Lauf über das Repository (grün) und Prüffunktion mit einer um einen toten Eintrag ergänzten Liste (rot).

- **AC-4:** Given der Scanner findet auf dem echten Verzeichnisbaum weniger als 150 Svelte-Dateien oder sucht im falschen Verzeichnis / When der Test läuft / Then bricht er mit „Messaufbau leer" ab, statt vakuum-grün zu sein.
  - Test: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts — Prüffunktion mit leerem und mit falschem Wurzelverzeichnis.

- **AC-5:** Given ein Katalogschlüssel ohne Verwender / When der Verwender-Test läuft / Then ist er rot und nennt den Schlüssel; Schlüssel, die über `tn('x', …)` (`x.one`/`x.other`), über eine Zuordnungstabelle oder über einen Kommentar `// i18n-dynamic: <präfix>` benutzt werden, gelten als verwendet.
  - Test: frontend/src/lib/i18n/__tests__/katalog_schluessel_haben_verwender.test.ts — echte Prüffunktion mit kleinen Quelltext-/Katalog-Mengen für alle vier Verwenderarten und den Negativfall; danach echter Lauf über den Bestand (grün). `# doc-compliance-test`.

- **AC-6:** Given die Pfade `__tests__/`, `routes/_design*` und `routes/email-preview-dev` / When gescannt wird / Then werden sie nicht gemeldet, aber alle übrigen Pfade (auch `lib/components/ui/` und `routes/`) schon.
  - Test: frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts — Scanner-Auswahlfunktion mit Beispielpfaden.

## Known Limitations

- Annahme: Pfad-Präfixe in der Allowlist beziehen sich auf `frontend/src/` und enden bei Verzeichnissen auf `/`. Das Issue F1 nennt `routes/(auth)` und F2 nennt `molecules/Infobox`; diese Pfade gibt es nicht. Maßgeblich ist, was die Messung findet (zum Beispiel `routes/login/` statt `routes/(auth)`).
- Nicht erfasst (Konventionen): Texte, die in `<script>` stehen, Texte in übergebenen Komponenten-Props außer `title|aria-label|placeholder|alt|label` (zum Beispiel `eyebrow="…"`), gemischte Attributwerte wie `title="Speichern {x}"`, und `*.ts`-Dateien (kommen mit Paket #2660 hinzu).
- Eigennamen (Marke „Gregor") werden wie jeder Text gemeldet und stehen in der Allowlist (`lib/brand/`, Entscheidung in einem F-Paket); reine Zahlen und Einheiten ohne zwei Buchstaben werden nicht gemeldet; Einheiten mit zwei Buchstaben (`km`) sind Treffer und werden bei Bedarf über Ausdrücke `{…}` gesetzt.
- Der Verwender-Test erkennt dynamische Schlüssel nur über den Kommentar; ein Schlüssel, der nur zusammengesetzt wird, ohne Kommentar, gilt als verwaist.
- Der Schutz „Allowlist darf nur schrumpfen" ist kein Test (der Vergleich mit dem Git-Vorgänger gehört nicht in den Lauf); die Adversary-Prüfung kontrolliert pro Paket, dass der Eintrag nur entfernt oder verfeinert wurde.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104 (Nr. 8)
- **Rationale:** Eine schrumpfende Allowlist macht aus der einmaligen Migration ein dauerhaftes Gate, ohne alle Bereiche in einem Zug umzustellen.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
