# Context: feat-2969-elementliste-uebersicht

## Request Summary
Issue #2969 (Epic #2913): Der Reiter **Übersicht** fehlt in der Elementliste. Einträge für Trip und Orte (DE/EN) aus dem Mockup erzeugen, den Ganzseiten-Abgleich um den Reiter erweitern und die Pauschal-Ausnahme (`ausnahmen` mit `reiter: "uebersicht"`, `muster: "{text}"`) entfernen.

## Related Files
| File | Relevance |
|------|-----------|
| `scripts/elementliste_aus_mockup.ts` | Generator. Schleife `KONTEXTE × ZUSTAENDE` liest nur Wetter, Zustellung und Etappen/Orte (Z. 580–637); Übersicht fehlt. `ausleseImBrowser` leitet Abschnitte aus Mockup-Klassen ab (`.sectionh` → `abschnittskopf`, sonst `block-<i>`). |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | Soll-Bild. `viewUebersicht()` (Z. 707–709): Bereichskopf „Übersicht“ + Satz „Unverändert: Stand, letzte Briefings, nächster Versand.“ + Karte „Im Mockup nicht ausgearbeitet.“ — der Reiterinhalt ist im Mockup bewusst **nicht** neu gestaltet. Reiterleiste Z. 348/350: Übersicht ist erster Reiter in Trip und Orte. |
| `docs/context/einstellungen_neu/elementliste.json` | Ziel-Datei (2646 Einträge, kein `uebersicht`). Kopf/Reiterleiste stehen unter Reiter `wetter` und gelten reiterübergreifend (`REITERUEBERGREIFEND` in der Logik). |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Z. ~6137–6150: zwei Ausnahmen `ctx trip/orte`, `reiter uebersicht`, `muster {text}` mit Verweis #2969 — zu entfernen. |
| `frontend/e2e/elementliste_abgleich_logik.ts` | `planeLauf` bildet Kombinationen aus den Listeneinträgen (Z. ~224–254) ⇒ ohne Übersicht-Einträge wird der Reiter **nie besucht**, weder Hin- noch Gegenrichtung. `findeZusaetzliche` (Z. 751) erklärt Live-Texte über Liste, Konto-Texte, Ausnahmen (`trifftZiel`: ctx/reiter + text/muster, **kein Abschnitts-Scope**). `seitenPfad` → `/trips/<id>?tab=uebersicht` bzw. `/compare/<id>?tab=uebersicht`. |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | Staging-Lauf; Gegenrichtung liest alle Texte unter `[data-seite="hub"]` (Kopf + Reiterfläche). |
| `frontend/src/lib/components/shared/hub-uebersicht/HubUebersicht.svelte` | Live-Übersicht (ein Code für Trip und Orte, ADR-0097). Z. 118: `Bereichskopf` mit `aktionen.reiter.uebersicht` + `bausteine.hub_uebersicht.kopf_erklaer` („Unverändert: Stand, letzte Briefings, nächster Versand.“ / EN „Unchanged: status, latest briefings, next delivery.“, #3006). Darunter der bestehende Übersicht-Inhalt (Stand, letzte Briefings, nächster Versand). |
| `frontend/src/lib/components/molecules/Bereichskopf.svelte` | Marker `data-abschnitt="abschnittskopf"` — passt zum Generator-Abschnitt `abschnittskopf`. |
| `frontend/src/lib/__tests__/elementliste_aktuell.test.ts`, `elementliste_bereichskoepfe_3006.test.ts`, `elementliste_abgleich_ganzseite.test.ts`, `elementliste_besitzer_kern.test.ts`, `tests/test_2913_c2_besitzerliste.py`, `tests/test_3007_besitzerliste.py` | Bestehende Wächter um Liste, Hash, Bereichsköpfe und Besitzerliste — müssen nach Regenerierung grün bleiben. |

## Existing Patterns
- Reiter-Lesung im Generator: `frisch(ctx, zustand)` → `#tabs [data-tab=…]` klicken → `aufklappen()` → `lies(['#content'])` → `gruppen.push({ctx, reiter, zustand, …})`. Übersicht folgt exakt diesem Muster.
- Mockup-Rahmen/Notizen werden über `SKIP` (`.tag,.frame,.fb,[data-fb]`) ausgeschlossen.
- Bewusste Mockup≠App-Abweichungen bekommen einen Besitzer in `elementliste_besitzer.json` (art element/abschnitt/zusaetzlich mit Grund + Verweis); Live-Texte ohne Listeneintrag eine `ausnahme` mit Grund + Spec.
- Regenerierung: `cd frontend && node --experimental-strip-types ../scripts/elementliste_aus_mockup.ts` (deterministisch, Playwright gegen file://).

## Dependencies
- Upstream: Mockup Fassung 4, i18n-Katalog (`frontend/src/lib/i18n/messages/{de,en}`) für EN-Zuordnung (#2968-Regeln).
- Downstream: Staging-Abgleich (`npm run elementliste:abgleich`, `--abnahme` muss Exit 0 bleiben), Besitzer-/Freigaben-Wächter, Hash-Check.

## Existing Specs
- `docs/specs/modules/feat_2913_abgleich_ganzseite.md` — Z. 62/72/129: Übersicht als Ausnahme mit Verweis auf dieses Issue.
- `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md` — Generator (AC-9…AC-12).
- `docs/specs/modules/` zu #3006 (Bereichsköpfe) und #2968 (EN-Zuordnung).

## Risks & Considerations
- **Kernbefund:** Das Mockup gestaltet den Reiterinhalt nicht („Unverändert …“, „Im Mockup nicht ausgearbeitet.“). Aus dem Mockup entstehen nur Bereichskopf (Titel + Satz) und eine Platzhalter-Karte. Die Platzhalter-Karte ist eine Mockup-Notiz, kein Produkttext — sie darf nicht als Soll in die Liste (sonst dauerhaft „fehlt live“).
- **Gegenrichtung:** Sobald Übersicht-Einträge existieren, besucht der Lauf den Reiter und liest den ganzen Live-Inhalt. Der bestehende Übersicht-Inhalt (unverändert lt. Mockup) wäre dann `zusaetzlich`. Die Pauschal-Ausnahme `{text}` deckt heute auch Kopf/Reiterleiste ab; `ausnahmen` kennen keinen Abschnitts-Scope. Analyse muss entscheiden, wie der unveränderte Inhalt ehrlich geführt wird (enge, begründete Regel statt `{text}` für den ganzen Reiter).
- Vier Zustände (normal, lädt, Ladefehler, Konto mit Lücken): prüfen, was das Mockup für Übersicht in lädt/fehler rendert, und wie der Live-Reiter diese Zustände zeigt (sonst `nicht_pruefbar` ohne Besitzer ⇒ `--abnahme` rot).
- Mockup-Hash ändert sich nicht (Mockup bleibt), aber `elementliste.json` wird neu erzeugt — andere Einträge dürfen sich nicht verschieben (IDs enthalten Hash des Textes, Ordnung je Gruppe).
- Nebenbefund: Der Erklärsatz „Unverändert: …“ ist live als Produkttext übernommen (#3006) — klingt nach Mockup-Notiz. Nicht Teil dieses Issues; ggf. Nebenbefund-Triage (#1199).
- Abnahme braucht Staging-Lauf DE und EN mit `--abnahme` Exit 0.

## Analysis

### Type
Feature (Werkzeug/Prüfdaten des Ganzseiten-Abgleichs, Epic #2913). Tiefe Summe 2 ⇒ Kontext und Analyse in einem Durchgang.

### Befunde
1. **Mockup-Inhalt des Reiters:** `viewUebersicht()` ist in allen vier Zuständen gleich (kein `zst`-Zweig): Bereichskopf (`.sectionh`: h2 „Übersicht“, p „Unverändert: Stand, letzte Briefings, nächster Versand.“) + Karte `.card.pad.muted` „Im Mockup nicht ausgearbeitet.“. Ein Klick auf `data-ctx` setzt `tab='wetter'`; danach `#tabs [data-tab="uebersicht"]` klicken (wie bei den anderen Reitern).
2. **Soll-Aussage des Mockups:** Nur der Bereichskopf ist Soll. Die Karte ist eine Mockup-Notiz (kein Produkttext); der Inhalt darunter ist ausdrücklich „unverändert“ = die heutige App ist das Soll.
3. **Live:** `HubUebersicht.svelte` rendert oben `Bereichskopf` (Marker `data-abschnitt="abschnittskopf"`) mit `aktionen.reiter.uebersicht` („Übersicht“/„Overview“) und `bausteine.hub_uebersicht.kopf_erklaer` (DE wortgleich zum Mockup, EN „Unchanged: status, latest briefings, next delivery.“) ⇒ EN-Zuordnung über Katalog exakt möglich. Darunter der bestehende Inhalt (Trip: `HubOverview`; Orte: eigene Fläche im Baustein).
4. **Abgleich:** Kombinationen entstehen nur aus Listeneinträgen ⇒ mit Übersicht-Einträgen läuft Hinrichtung (Abschnitt `abschnittskopf`) und Gegenrichtung (ganzer Hub, Zustand normal) für `uebersicht` in Trip und Orte. Kopf/Reiterleiste werden über `REITERUEBERGREIFEND` aus den Wetter-Einträgen erklärt. Der unveränderte Inhalt wäre ohne Regel `zusaetzlich`.

### Varianten für den unveränderten Inhalt (Gegenrichtung)
| Variante | Änderung | Schutzwirkung | Aufwand |
|---|---|---|---|
| A Pauschal `{text}` behalten | keine | keine: verdeckt auch Kopf/Reiterleiste/Bereichskopf, neue Texte fallen nie auf | 0 |
| B Lesebereich im Lauf auf Kopf + Bereichskopf kürzen | Logik + Spec-Lauf | neue Texte im Inhalt fallen nie auf; Sonderpfad im Werkzeug | mittel |
| C **Einzel-Ausnahmen je Live-Text** (text bzw. muster, ctx/reiter, Grund „Mockup: Inhalt unverändert“, Spec dieses Issues), gewonnen aus einem echten Staging-Lesen DE+EN | nur Daten | jeder neue oder geänderte Text der Übersicht wird `zusaetzlich` ⇒ Schnappschuss des „unverändert“-Solls | klein |
| D Katalog-Präfix-Regel (`bausteine.hub_uebersicht.*`) | neue Ausnahmeart in der Logik | mittel (Datenwerte trotzdem einzeln) | mittel |

**Empfehlung: C** — nutzt den vorhandenen Mechanismus (`ausnahmen` mit ctx/reiter + text/muster), keine Logikänderung, ehrlichster Nachweis („unverändert“ wird zum festgehaltenen Soll). Konto-Werte (Trip-/Ortsnamen) erklärt bereits `ladeKontoTexte`; Datums-/Zeitwerte als `muster` mit `{…}`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/elementliste_aus_mockup.ts` | MODIFY | Je ctx × Zustand Reiter `uebersicht` lesen, nur Abschnitt `abschnittskopf` (`lies(['#content'], { nur: 'abschnittskopf' })`), Kopfkommentar ergänzen (Platzhalter-Karte = Mockup-Notiz) |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY (regeneriert) | +16 Einträge (2 ctx × 4 Zustände × Titel/Satz), bestehende Einträge unverändert |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 2 Pauschal-Ausnahmen raus; Einzel-Ausnahmen für den unveränderten Inhalt (DE+EN); ggf. Besitzer für herstellungsbedingte `nicht_pruefbar` der Zustände lädt/fehler/Lücken |
| `frontend/src/lib/__tests__/elementliste_uebersicht_2969.test.ts` | CREATE | RED: Liste enthält Übersicht-Einträge (Trip/Orte × 4 Zustände, nur `abschnittskopf`, DE/EN aus Katalog), keine Mockup-Notiz; Besitzerliste ohne Pauschal-Ausnahme; `findeZusaetzliche` für Übersicht: bekannter Inhalt erklärt, unbekannter Text `zusaetzlich` |
| `docs/specs/modules/feat_2969_elementliste_uebersicht.md` | CREATE | Spec |
| `docs/specs/modules/feat_2913_abgleich_ganzseite.md` | MODIFY (Doku) | Hinweis Übersicht-Ausnahme → durch #2969 ersetzt |

### Scope Assessment
- Files: 3 Code/Daten + 1 Test + Spec/Doku
- Estimated LoC: Generator +10, Test ~+120, Besitzerliste +N Ausnahmen (Daten)
- Risk Level: LOW–MEDIUM (nur Prüfwerkzeug/Prüfdaten, keine Produktoberfläche; Risiko: `--abnahme` rot durch neue `nicht_pruefbar` in Zuständen lädt/fehler/Lücken)

### Technical Approach
1. Generator erweitern, Liste regenerieren, Diff prüfen: nur neue `uebersicht`-Einträge.
2. Staging-Lauf DE/EN nur für Reiter Übersicht (Scope-Option des Laufs) ⇒ Live-Texte der Gegenrichtung erfassen ⇒ Einzel-Ausnahmen schreiben, Pauschal-Ausnahmen entfernen.
3. Vollständiger `--abnahme`-Lauf DE und EN: Exit 0.

### Dependencies
- Katalogschlüssel `aktionen.reiter.uebersicht`, `bausteine.hub_uebersicht.kopf_erklaer` (vorhanden, DE+EN).
- Staging-Prüfkonto mit Trip und Orts-Vergleich (vorhanden, vom Lauf genutzt).

### Open Questions
- keine Produktfrage. Nebenbefund: Live-Erklärsatz „Unverändert: …“ stammt aus der Mockup-Notiz (#3006) — als Nebenbefund in Sammel-Issue #1199 melden, nicht hier ändern.
