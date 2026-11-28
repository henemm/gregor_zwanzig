# Context: fix-3241-en-chips-abgleich (#3241, Epic #2913)

## Request Summary

Der englische Elementlisten-Abgleich (Reiter Wetter, Abschnitt `metriken`) prüft mehrere Texte nicht einzeln.
61 Besitzer-Einträge in `docs/context/einstellungen_neu/elementliste_besitzer.json` verweisen auf #3241.
Ziel: alle einzeln prüfbar machen, Besitzer abräumen, Zählwächter `#3241` auf 0.

## Ausgangslage (EN-Staging-Abgleich, Prüfkonto, 28.11.2026, Scope wetter)

Die 54 Element-Besitzer verteilen sich so:

| Klasse | Anzahl | Status heute | Ursache |
|---|---|---|---|
| A Register-Metriknamen („Regenwahrscheinlichkeit“, „Tiefe Wolken“, „UV-Index“, „Bewölkung“) | 10 | **gefunden** | seit #3154 (metrik_namen.json) schon gelöst; Besitzer veraltet |
| B Einheit + Hinweis „mm · Summe“, „m · Minimum“ | 6 | abweichend „Text nicht sichtbar“ | Erzeuger nimmt „Summe“/„Minimum“ aus einem fremden Katalogschlüssel (Großschreibung „Total“/„Minimum“), live steht `wetter.hinweis.*` („total“/„minimum“) |
| C „°C · Tageshöchst · Tagestief“ | 4 | nicht_pruefbar (EN-Lücke) | Segmentregel teilt an „ · “, „Tageshöchst“ allein nicht im Katalog; als Ganzes ist es `wetter.hinweis.temperature` |
| D „· grün: bis 6“ (UV, ohne Einheit) | 2 | nicht_pruefbar (EN-Lücke) | `wetter.gruen.bis` = „grün: bis {bis} {einheit}“ mit leerer Einheit, kein Erzeuger-Treffer |
| E Metrik-Chips „+ {metrik}“ | 32 | nicht_pruefbar „in EN ist nur das Muster prüfbar“ | `bewerteKontoChips` prüft in EN nur das Muster |

Dazu 7 `zusaetzlich`-Besitzer: „Cloud cover“, „Rain probability“, „UV index“ (heute nicht mehr zusätzlich → veraltet),
„mm · total“, „°C · daily high · daily low“, „m · minimum“, „· green: up to {zahl}“ (verschwinden, sobald B–D in der
EN-Liste stehen).

## Related Files

- `scripts/elementliste_aus_mockup.ts` — Erzeuger der Elementliste: `ermittleEn`, Sonderfälle `chipEn`, `listenzeileEn` (Zeile 672 Aufrufkette).
- `docs/context/einstellungen_neu/elementliste.json` — Erzeugnis (neu erzeugen: `cd frontend && node --experimental-strip-types ../scripts/elementliste_aus_mockup.ts`).
- `frontend/e2e/elementliste_abgleich_logik.ts` — `bewerteKontoChips` (~Z. 1527), `bewerteAbschnitt` (~Z. 1640), `NamensPaar`/`namenPaareAus` (#3422).
- `frontend/e2e/elementliste-abgleich.staging.spec.ts` — ruft `bewerteAbschnitt` (Z. 507, 535); `namenDeEn` liegt schon vor (Z. 392).
- `frontend/src/lib/i18n/messages/{de,en}/wetter.json` — `wetter.hinweis.*`, `wetter.gruen.*`.
- `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` — Live-Aufbau Grünbereich/Hinweis.
- `docs/context/einstellungen_neu/elementliste_besitzer.json`, `tests/test_2913_c2_besitzerliste.py` (Zählwächter Z. 189).

## Existing Patterns

- Kontextbezogene Sonderfälle im Erzeuger nach Abschnitt (`listenzeileEn` für `liste`, `chipEn` für Rolle chip).
- DE→EN-Metriknamen über `NamensPaar` aus `metrik_namen.json` (+ `vergleich.zeile.*`), schon im EN-Lauf geladen.
- DE-Chip-Logik: einzeln gefunden, wenn genau der Text sichtbar; sonst „in diesem Konto kein Chip“ (nicht_pruefbar), erstes Element vertritt die Chip-Zeile.

## Ansatz (Analyse)

1. Erzeuger: neuer Sonderfall für Abschnitt `metriken` (Metrik-Zeile): „<Einheit> · <wetter.hinweis.*-DE>“ → „<Einheit> · <EN>“, Hinweis allein
   genauso; Grünbereich ohne Einheit „· grün: bis {zahl}“ (bzw. ab/von–bis) aus `wetter.gruen.*` mit leerer `{einheit}`. Vorrang vor der
   allgemeinen Segmentregel nur in diesem Abschnitt, Katalogschlüssel wird gesetzt.
2. Abgleich: `bewerteKontoChips` erhält die Namenspaare; im EN-Lauf ist die Einzelerwartung „+ <EN-Name>“ (Name aus `text_de` über das Chip-Muster,
   EN über das Paar), Bewertung wie DE. Kein Paar ⇒ nicht_pruefbar mit eigenem Grund (fail-closed, nie geraten).
3. Liste neu erzeugen, 61 Besitzer abräumen, Zählwächter `#3241: 0`.

## Dependencies / Dependents

- Abgleich `--strict`/`--abnahme` DE und EN (Abnahme #3009) hängt an der Besitzerliste.
- DE-Lauf darf sich nicht ändern (DE-Chip-Pfad und DE-Muster unverändert).

## Risks

- Neu-Erzeugen der Liste kann fremde Einträge verschieben (Mockup-Drift) → Diff auf `metriken`-Einträge prüfen.
- Element-IDs hängen am DE-Text; bleiben gleich.
- Unit-Tests der Erzeuger-Regeln (`feat3205…`, `feat3419…`, `feat3250…`) müssen grün bleiben.

## Analysis

**Type:** Feature (Prüfwerkzeug), kein Produktcode.

**Affected Files:**

| Datei | Change |
|---|---|
| `scripts/elementliste_aus_mockup.ts` | MODIFY: Sonderfall `metrikZeileEn` (Abschnitt `metriken`): „<Einheit> · <wetter.hinweis.*>“ und Grünbereich ohne Einheit |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY (neu erzeugt): nur die 12 betroffenen Einträge (B 6, C 4, D 2) dürfen sich ändern |
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY: `bewerteKontoChips`/`bewerteAbschnitt` mit Namenspaaren, EN-Einzelprüfung der Chips |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY: `namenDeEn` an `bewerteAbschnitt` reichen (2 Aufrufe) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY: 61 Einträge `#3241` entfernen |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY: Zählwächter `#3241: 0` |
| `frontend/e2e/fix3241_*.test.ts` | CREATE: Unit-Tests (node --test) für Erzeuger-Regel und EN-Chip-Bewertung |

**Bestand der Metrik-Zeilen** (Liste heute): alle anderen „<Einheit> · <Hinweis>“-Zeilen (Mittelwind, Spitze, vor der Etappe,
Gipfel in Wolken, …) und Grünbereiche mit Einheit sind schon korrekt (Segmentregel bzw. Katalogmuster). Nur „Summe“, „Minimum“
(Großschreibung aus fremdem Schlüssel), „Tageshöchst · Tagestief“ (enthält selbst „ · “) und „· grün: bis 6“ (ohne Einheit) scheitern.
Der Sonderfall nimmt den Katalogschlüssel `wetter.hinweis.<id>` bzw. `wetter.gruen.*`, den die App live rendert (MetrikZeile.svelte,
ampelModell.ts), und ist auf den Abschnitt `metriken` begrenzt; bestehende korrekte Zuordnungen bleiben textgleich.

**Scope/Risk:** ~7 Dateien, ~120 LoC inkl. Tests. Risiko niedrig (nur Prüfwerkzeug, DE-Lauf unverändert).

**Technical Approach:** siehe „Ansatz“ oben. EN-Chip: Metrikname aus `text_de` über das DE-Muster „+ {metrik}“, EN-Name aus
`NamensPaar` (exakter DE-Name, normalisiert); sichtbar ⇒ gefunden; nicht sichtbar ⇒ wie DE (erstes Element vertritt die Zeile,
sonst nicht_pruefbar „in diesem Konto kein Chip“); kein Paar ⇒ nicht_pruefbar „kein EN-Name für <DE>“.

**Open Questions:** keine (reine Werkzeugarbeit, Ziel im Issue festgelegt).
