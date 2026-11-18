# Context: 3007-etappen-orte-listen

## Request Summary
Issue #3007 (Teil von Epic #2913, frühere Scheibe „e“): Die Listen der Reiter **Etappen** (Trip) und **Orte** (Orts-Briefing) sollen dem Mockup Fassung 3 entsprechen (Elemente, Reihenfolge, Texte, DE+EN, aus Design-System-Bausteinen nach ADR-0112). Der Elementlisten-Abgleich `--abnahme` soll für diese Reiter keine Abweichung und keine Fremdtexte mehr melden; die Sammel-Einträge `{text}` für beide Reiter in `elementliste_besitzer.json` entfallen. Nicht hier: Tempo/Fortbewegung (#2796, offen), 1..n Orte / Ein-Ort-Briefing (#2798, offen), Bereichsköpfe (#3006, geliefert).

## Soll (Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`)
- **Etappen** `viewEtappen()` Z. 577-587: Bereichskopf → Tempo-Karte (Fortbewegung, Tempo flach, Aufstieg; gehört zu #2796, Abschnitt `tempo`) → `.card` mit je Etappe einer `.lrow`: links `<b>E1 · Port d'Andratx → Estellencs</b><small>7,8 km · ↑520 m</small>`, rechts `<span class="meta">Gehzeit 3:10</span>` + `btn sm quiet` „Tempo ändern“.
- **Orte** `viewOrte()` Z. 588-591: Bereichskopf mit „+ Ort hinzufügen“ → `.card` mit je Ort einer `.lrow`: links `<b>Münster</b><small>Stadt · 60 m</small>` (Gruppe/Region · Höhe), rechts `btn sm quiet` „entfernen“ (Text, kein ✕).
- CSS: `.lrow` Z. 140-143 (flex, gap 14px, padding 14px 20px, border-top rule-soft, erste ohne Linie; `b` 600; `small` ink-3 12.5px), `.meta` Z. 40 (mono 13px ink-3), `.btn.sm` Z. 46, `.btn.quiet` Z. 50 (transparent, ink-2, padding-inline 4px), `.card` Z. 72.
- Kein Reihenfolge-Hinweis, kein Rang-Badge, kein Ziehgriff, keine Wechselfarben im Mockup.

## Elementliste (`docs/context/einstellungen_neu/elementliste.json`, je Zustand normal/laedt/fehler/luecken gleich)
- `trip/etappen/liste`: 10 Einträge — je Etappe Titel-Muster `E{zahl} · …`, Kennzahl `{zahl} km · ↑{zahl} m`, nur E1 zusätzlich `Gehzeit {zahl}:{zahl}`; je Etappe Knopf „Tempo ändern“. Alle `luecke:true`, kein `i18n_key`, kein `text_en`.
- `orte/orte/liste`: 9 Einträge — Name, `{Gruppe} · {zahl} m`, Knopf „entfernen“; alle `luecke:true`.
- Kopf-Einträge (`abschnittskopf`) sind seit #3006 befüllt (`luecke:false`).

## Besitzerliste (`docs/context/einstellungen_neu/elementliste_besitzer.json`, Liste `besitzer`)
- Index 746 / 747: `zusaetzlich` `{text}` für trip/etappen bzw. orte/orte, Verweis `#2913-e` → laut Issue zu entfernen.
- Index 338 / 347: `abschnitt` `liste` für trip/etappen bzw. orte/orte, Verweis `#2913-e` → mit dieser Scheibe auflösen.
- Index 337 / 346: `abschnitt` `abschnittskopf` (Verweis `#2913-e`) stehen noch drin, obwohl #3006 die Köpfe geliefert hat → prüfen, ob entfernbar (Abgleich zeigt Kopf als gefunden?).
- Index 339: `tempo` → bleibt (#2796).
- `ausnahmen`: Übersicht `{text}` (#2969), Stift-Beschriftungen — nicht betroffen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:212-222` | Etappen-Zweig: Bereichskopf-Snippet `etappenKopf` → `EditStagesSection` (kopf-Prop) bzw. Lade-Reiterfläche |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | Durchreicher auf `EditStagesPanelNew` |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` (1201 Z.) | Heutiger Etappen-Reiter = voller Editor: EtappenStrip, MapCanvas, ProfileEditor, WaypointCard, Datums-/Zeitfelder, Kaskade, Pausentag, Löschdialog, Mobil-Zweig (`mobile-stages-list`, `StageCardM`, SortableList). Naismith-Gehzeit `computeArrivalTimes`/`activityToSpeed` vorhanden |
| `frontend/src/lib/components/trip-detail/waypoints/EtappenStrip.svelte` | Etappen-Leiste (Auswahl/Sortieren) — Kandidat oder Konkurrent für die Mockup-Liste |
| `frontend/src/lib/components/mobile/StageCardM.svelte` | Mobile Etappenzeile |
| `frontend/src/lib/components/compare/CompareTabs.svelte:734-790` | Orte-Reiter: Bereichskopf (#3006), `hub-section-hint` Reihenfolge-Hinweis, Card + SortableList mit `hub-orte-row` (DragHandle, `CompareLocationRow`, ✕-Knopf `hub-orte-remove`), Aufklapp-Panel `hub-orte-panel` |
| `frontend/src/lib/components/molecules/CompareLocationRow.svelte` | Rang-Badge + Name + Gruppe + Höhe rechts, Inline-Styles (kein Mockup-Muster) |
| `frontend/src/lib/components/molecules/Einstellungszeile.svelte` | Vorhandenes `.lrow`-Molekül (#2913 Teil 2, AC-15): `titel`, `hinweis`, `children`-Snippet rechts, `data-slot`-Haken → naheliegender Baustein für beide Listen |
| `frontend/src/lib/components/molecules/Bereichskopf.svelte` | Kopf (#3006), `data-abschnitt="abschnittskopf"` |
| `frontend/src/lib/components/shared/hub-reiterflaeche/HubReiterflaeche.svelte` | Reiterfläche beider Kontexte |
| `frontend/src/lib/components/atoms/Btn.svelte`, `Card.svelte` | Knopf (sm/quiet?), Karte |
| `frontend/e2e/elementliste_abgleich_logik.ts` | Abgleich: Abschnitt über `data-abschnitt` in `[data-seite="hub"]`, Reihenfolge, `findeZusaetzliche`, Besitzer/Ausnahmen |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | Abnahme-Lauf gegen Staging |
| `tests/test_2913_c2_besitzerliste.py` | Konsistenztest der Besitzerliste |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | Katalog; vorhanden u. a. `trip.hub.kopf.etappen_*`, `vergleich.hub.kopf.*`, `layout.ausgabe.entfernen`, `vergleich.hub.reihenfolge_hinweis`, `vergleich.hub.ziehen_sortieren` |

## Existing Patterns
- Abschnitt-Haken: statisches `data-abschnitt="<name>"` am Container (z. B. `kanaele`, `metriken`, `anpassen`). Für die Listen fehlt `data-abschnitt="liste"` heute in beiden Reitern.
- `.lrow` als Molekül `Einstellungszeile` (Snippet rechts) — Zustellung/Wetter nutzen es bereits.
- Elementliste-Nachzug per Skript: `luecke:true` → `i18n_key`/`text_en`/`luecke:false`, IDs unverändert (so in #3006).
- Trip/Orte-Teilung (ADR-0097, CLAUDE.md): gleiche Zeilen-Bausteine für beide Listen; Orte-eigen nur Orte-Tab-Inhalt.
- Tests: `node --test` mit SSR-Render, statische Strukturtests, Staging-Abgleich.

## Dependencies
- Upstream: Design-Tokens, `$t`, Btn/Card, SortableList/DragHandle (Reihenfolge), Naismith-Gehzeit, Stage-/Location-Typen (`loc.group`, `loc.elevation_m`, Etappen-Distanz/Aufstieg aus Wegpunkten).
- Downstream: E2E `mobile-stages-listen-only.spec.ts`, `etappen-strip-*.spec.ts`, `mobile-etappen-sortieren-speichert.spec.ts`, `trip-hub-etappenliste-titel.spec.ts`, `compare-hub-inline-edit.spec.ts` (Testids `hub-orte-row`, `hub-orte-remove`, `hub-orte-add`, `hub-orte-panel`), Elementlisten-Abgleich, Anlegen-Editoren (nutzen dieselben Panels).

## Existing Specs
- `docs/specs/modules/issue_503_etappen_waypoints.md` (Etappen-Editor), `mobile_stages_tab_listen_only` (PO-Entscheid F5: mobil nur Liste), `issue_489_compare_row_molecules.md`, `feat_2913_abgleich_ganzseite.md`, Spec zu #3006 (Bereichsköpfe), `feat_2913_c2_seitenkopf.md`.

## Risks & Considerations
- **Etappen-Editor vs. Mockup-Liste (Hauptfrage für die Analyse):** Das Mockup zeigt nur eine Etappenliste; live ist der Reiter ein voller Editor (Karte, Höhenprofil, Wegpunkte, Datum/Startzeit, Pausentag). Grundentscheidung Karte `reiter` (grundentscheidungen.html Z. 273): „Etappen und Wegpunkte (**unverändert**)“, Feature-Inventar E1 „Startzeit, Pausentag, Ankunftszeiten — abgedeckt“. ⇒ Editor darf nicht entfallen; Liste muss ergänzen/ersetzen, ohne Funktionen zu verlieren (z. B. Liste oben als Übersicht/Auswahl, Editor darunter). Klären, ob das aus Mockup + Entscheidungen ableitbar ist oder eine PO-Frage ist.
- **Tempo-Abhängigkeit:** Etappen-Zeile enthält „Gehzeit h:mm“ und Knopf „Tempo ändern“ — beides fachlich #2796 (persistente Tempo-Felder, offen). Gehzeit ist heute per Naismith berechenbar; „Tempo ändern“ ohne Tempo-Felder wäre ein toter Knopf. Abgrenzung für die Abnahme (Besitzer-Eintrag auf #2796 umhängen?) nötig.
- **Orte-Zeile:** Mockup ohne Rang-Badge, Ziehgriff, Reihenfolge-Hinweis, Wechselfarbe; „entfernen“ als Textknopf statt ✕. Reihenfolge per Ziehen ist aber bestehende Funktion (Vergleichstabelle-Reihenfolge) — Mockup-Satz „ohne Rangfolge“; Zuordnung zu #2798 prüfen, keine Funktion still entfernen.
- Testids `hub-orte-row`/`-remove`/`-add`/`-panel`, `mobile-stages-list`, `stage-cardm-row` von Bestandstests genutzt.
- Elementliste: 76 `luecke:true`-Einträge (10+9 je 4 Zustände) bekommen Katalogschlüssel/EN-Texte; Muster-Einträge (`{zahl}`) für Beispieldaten des Prüf-Datensatzes — Abgleich-Datensatz (Staging-Prüf-Trip/-Vergleich) muss Etappen/Orte liefern.
- Besitzer 337/346 (Kopf) prüfen und ggf. mit entfernen; Besitzerliste-Konsistenztest anpassen.
- Parallelität: #3006 ist geliefert; keine andere offene Arbeit an TripTabs/CompareTabs bekannt — vor Phase 6 erneut prüfen.

## Analysis

### Type
Feature (Teil von Epic #2913, Oberflächen-Scheibe nach ADR-0112)

### Abgeleitete Produkt-Entscheidungen (keine PO-Frage nötig)
- **Etappen-Editor bleibt vollständig** (Grundentscheidung Z. 273 „Etappen und Wegpunkte (unverändert)“, Inventar E1 abgedeckt). Hub-Standardansicht zeigt nur die Mockup-Liste; Klick/Enter auf eine Etappenzeile klappt den bestehenden Editor (Karte, Profil, Wegpunkte, Datum, Startzeit, Pausentag) für diese Etappe darunter auf. Begründung: Abgleich zählt jeden *sichtbaren* Text (`checkVisibility`, `elementliste-abgleich.staging.spec.ts:107`) als Fremdtext; Aufklapp-Muster existiert bereits im Orte-Reiter (`hub-orte-panel`). Anlegen-Editor (TripNewEditor) unverändert über Prop (z. B. `listeZuerst`, Standard false).
- **„Tempo ändern“ und Tempo-Karte gehören #2796**: Knopf entfällt in dieser Scheibe; die Element-IDs „Tempo ändern“ bekommen Besitzer-Einträge `art:element` → #2796; Besitzer 339 (tempo) bleibt.
- **Gehzeit h:mm** wird mit der vorhandenen Gehzeit-Rechnung (`computeArrivalTimes`/`activityToSpeed`, nicht das deprecatete `naismithHours`) je Etappe gezeigt; Pausentag-Zeile ohne Kennzahlen/Gehzeit.
- **Orte**: Zeile Name + „Gruppe · Höhe m“, Textknopf „entfernen“ (Btn sm quiet). Rang-Badge, Reihenfolge-Hinweis und Wechselfarbe entfallen (Mockup „ohne Rangfolge“). Sortieren per textlosem Ziehgriff bleibt (Inventar E2 „Reihenfolge unverändert“), Ziehgriff behält aria-label. Fehlen Gruppe oder Höhe, nur der vorhandene Teil (kein verwaistes „·“).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/Einstellungszeile.svelte` | MODIFY | optional klickbar (role=button, aria-expanded, Enter/Leertaste) |
| `frontend/src/lib/components/shared/…/Listenzeile` (Name offen) | CREATE | gemeinsamer Zeilen-Baustein Trip/Orte (ADR-0097) auf Basis Einstellungszeile |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | Hub-Modus: Liste `data-abschnitt="liste"` + Aufklapp-Editor; Desktop-Strip im Hub-Modus ersetzt durch Liste |
| `frontend/src/lib/components/edit/EditStagesSection.svelte` | MODIFY | Prop durchreichen |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Hub-Modus einschalten |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Orte-Liste nach Mockup, `data-abschnitt="liste"`, Hinweis/Rang/✕ raus |
| `frontend/src/lib/components/molecules/CompareLocationRow.svelte` | DELETE (falls ungenutzt) | einziger Nutzer ist CompareTabs |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` | MODIFY | ca. 6-10 Schlüssel (Gehzeit, entfernen, Kennzahl-Muster) |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | 76 `luecke:true`-Einträge → i18n_key/text_en, IDs unverändert |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 337/338/346/347/746/747 raus, „Tempo ändern“-Elemente → #2796 |
| `tests/test_2913_c2_besitzerliste.py` | MODIFY | Konsistenz nachziehen |
| node-Tests (SSR) für Zeilenbaustein, Etappen-/Orte-Liste | CREATE | |
| E2E-Specs mit Editor-ohne-Klick (etappen-strip-*, waypoints-editor, issue-407, issue-498, hub-editor-autosave-*, hub-save-chip, fix-2954) und Orte (compare-hub-inline-edit u. a.) | MODIFY | Zeilenklick vor Editor; Rang/✕/Hinweis-Erwartungen |

### Scope Assessment
- Files: ca. 10 Quell-/Daten-Dateien + ca. 10-12 E2E-Specs
- Estimated LoC: +600/-250 (inkl. Tests) — über Standard-Limit, daher zwei Teilschritte im Plan: (1) gemeinsamer Zeilenbaustein + Orte, (2) Etappen
- Risk Level: MEDIUM (Etappen-Editor ist zentraler Arbeitsbereich; viele Bestands-E2E)

### Technical Approach
Gemeinsamer Listenzeilen-Baustein auf `Einstellungszeile`; Orte zuerst (klein), dann Etappen mit Hub-Modus-Prop und Aufklapp-Editor; danach Elementliste/Besitzerliste nachziehen und Staging-Abgleich `--abnahme` als Nachweis. Abgleich läuft im Desktop-Viewport (kein Viewport-Override in der Staging-Spec) → Mobil-Zweig (bereits Listen-Modus, PO F5) bleibt unangetastet.

### Dependencies
Kennzahlen: `Stage.distanceKm`/`ascentM` (optional, `utils/tripStats.ts`); Gehzeit `computeArrivalTimes`/`activityToSpeed`; `Btn`, `Card`, `SortableList`/`DragHandle`, `Bereichskopf` (#3006).

### Open Questions (technisch, in Phase 3/4 selbst klären)
- [ ] Staging-Prüf-Trip: Etappen mit distanceKm/ascentM? Prüf-Vergleich: Orte mit group/elevation_m? Sonst Prüf-Datensatz ergänzen.
- [ ] Abgleich-Verhalten bei Gehzeit in allen Zeilen (Elementliste führt nur E1) — Mehrfachtreffer prüfen.
- [ ] Besitzer 337/346 (Kopf) nur entfernen, wenn Abgleich den Kopf findet.
