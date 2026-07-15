# Context: feat-1256-s8d-mobile-editor-fidelity

## Request Summary

Scheibe S8d von #1256 = Restlisten-Posten **R4** (Vertrag: Restliste-Kommentar in #1256,
2026-07-14): Mobile-Liste bekommt kompaktes Mobile-Chrome + verliert das Suchfeld
(Handoff-5-P3), der mobile Editor-Orte-Tab wird ein echter Mobile-Stack, die Editor-CTAs
werden kontextuell (Labels + Disabled-Feedback), Profil-Auswahl-Häkchen mobil,
TopAppBar-Detail (kosmetisch), Desktop-Editor (create) bekommt Weiter-CTAs am Fuß der
Tabs Orte/Wertebereiche/Layout.

## Soll-Quellen (JSX = Wahrheit, Handoff-4 entpackt im Session-Scratchpad `handoff4/`)

| Quelle | Bindend für |
|---|---|
| `gregor-zwanzig-mobile/project/screen-compare-list-mobile.jsx` (64 Z.) | Mobile-Liste: MobileShell-Kopf Z.22 (title „Orts-Vergleiche", eyebrow „Workspace · N", right=Plus-IconBtn „Neuer Vergleich"), kurzer Intro Z.27-30, Stats `size="sm"` Z.42-44, Kachel-Stack Z.48-57, Content-Padding „12px 16px 24px" Z.24. **Suchfeld Z.32-35 entfällt** (Handoff-5-P3: „ersatzlos entfernen", `body-1256-compare-ui-fragen.md` Punkt 3) |
| `gregor-zwanzig-mobile/project/screen-compare-editor-mobile.jsx` (472 Z.) | Mobiler Editor: Orte-Tab-Stack Z.214-314 (Kopf „Im Vergleich · N" + min-2/viel/passt-Badge Z.229-236, nummerierte Picked-Karten mit ✕ Z.243-254, dashed Bibliotheks-Button Z.257-266, Sheet Z.281-311), Floating-CTAs Z.200-207/269-277/323-327/337-341 (kontextuelle Labels, disabled = variant quiet + opacity 0.4), Profil-Häkchen Z.190-194 (20px-Accent-Kreis + Check-SVG) + Metrik-Unterzeile `slice(0,4)+"…"` Z.186-188, TopAppBar Z.422-448 (create-right: „Aktivieren" nur bei isReady, sonst „…") |
| `claude-code-handoff/current/jsx/screen-compare-editor.jsx` (500 Z.) | Desktop-Editor create: CTA-Füße Vergleich Z.185-194 („⊘ Name fehlt" + „Orte hinzufügen →"), **Orte Z.298-307** („⊘ min. 2 Orte auswählen" + „Idealwerte festlegen →", Btn accent/quiet, opacity 0.45 + cursor not-allowed), **Idealwerte Z.322-328** („Layout einrichten →"), **Layout Z.338-344** („Versand einrichten →") — alle `!isEdit` |
| `claude-code-handoff/current/jsx/screen-compare-list.jsx` | Desktop-Liste behält Suchfeld (verdrahteter Filter Z.49-61) — P3 gilt NUR mobil |

## Related Files (Ist-Stand)

| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/+page.svelte` (101 Z.) | Listen-Seite. Mobil reflowt heute der Desktop-Kopf (32px-Titel, langer Intro, `padding: 32px 40px`, Z.33-47); Suchfeld Z.49-61 „immer sichtbar (Issue #582)" — mobil zu entfernen; Stats Z.63-68 ohne `size="sm"`; Mobile-Stack Z.70-83 (CompareTile dense, seit S8 mit Chevron) |
| `frontend/src/lib/components/compare/CompareEditor.svelte` (1414 Z.) | Editor-Rahmen, CSS-only-Weiche `.cm-desktop`/`.cm-mobile` (≤899px). Mobile App-Bar Z.1122-1156 (Struktur = Soll; Detail: right zeigt immer „Aktivieren" statt „…" wenn nicht bereit). Mobiler CTA Z.1269-1277: generisch „Weiter →"/„Aktivieren", immer primary, kein Disabled-Feedback. Mobiler Orte-Tab Z.1234-1247 mountet Step2Orte (Desktop-Grid!) + Bibliotheks-Button + Sheet Z.1282ff. Mobile Profil-Liste Z.1222-1231 ohne Häkchen, Metrik-Zeile ungekürzt. Desktop: nur Vergleich-Tab hat Fuß-CTA (`compare-editor-continue-orte`, Z.1054-1069) — Orte/Idealwerte/Layout fehlen |
| `frontend/src/lib/components/compare/compareEditorLogic.ts` | `TAB_ORDER`, `unlockedTabs`/`doneTabs` (Freischaltung: orte ab Name, idealwerte ab ≥2 Orte) — Quelle für CTA-Disabled-Bedingungen |
| `frontend/src/lib/components/compare/steps/Step2Orte.svelte` | Desktop-Grid (Smart-Import 2-spaltig Z.194, Bibliothek 3-spaltig Z.328), Picked-Liste mit min-2-Badge Z.59-67; keine interne Mobile-Weiche |
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` + `src/routes/+layout.svelte:70` | Globales Mobile-App-Chrome (Hamburger + Wordmark + Bell + Plus→/trips/new). Props eyebrow/right/leftIcon existieren (#373), Layout übergibt sie nicht. `mobile/MobileShell.svelte` wird nur im Design-System-Showcase genutzt, in keiner echten Route |

## Gap-Analyse (Soll → Ist)

**A. Mobile-Liste** (`compare/+page.svelte`)
- A1 Mobile-Chrome: kompakter mobiler Kopf statt reflowtem Desktop-Kopf — Titelzeile + Plus-Icon-Button (min. 44px Tap) + kurzer Intro (JSX-M:27-30). Desktop-Kopf → `hidden desktop:block`.
- A2 Suchfeld mobil ersatzlos weg (P3); Desktop behält. #582-Kommentar anpassen; **kein Test wacht über „Suche immer sichtbar"** (e2e/ + tests/ gegrept, nur GPX-Zufallstreffer).
- A3 Stats mobil `size="sm"` (Desktop unverändert), A4 mobiles Content-Padding kompakt (12/16/24 statt 32/40; Layout-`main` hat zusätzlich `px-4` — Doppel-Padding-Klasse aus S8 beachten).

**B. Mobiler Editor** (`.cm-mobile`-Zweig + Step2Orte)
- B1 Orte-Tab: mobiler Stack 1:1 JSX-M:226-266 statt Desktop-Grid-Mount. Soll-mobil hat KEIN Smart-Import-Panel und KEINE Inline-Bibliothek (nur Button → Sheet, beides existiert schon).
- B2 CTAs kontextuell: vergleich „Orte hinzufügen →"/„Name eingeben"; orte „Idealwerte festlegen →"/„noch N Ort(e) nötig"; idealwerte „Layout einrichten →"; layout „Versand einrichten →"; disabled = quiet + opacity 0.4 + kein onclick. Versand-Tab: Soll hat KEINEN Boden-CTA (Aktivieren sitzt in der App-Bar) — Ist zeigt dort „Aktivieren".
- B3 Profil-Häkchen (JSX-M:190-194) + Metrik-Unterzeile auf 4 Einträge + „…" gekürzt.
- B4 TopAppBar-Detail (kosmetisch): create-right „…" statt ausgegrautem „Aktivieren", solange nicht bereit (JSX-M:444).

**C. Desktop-Editor create**
- C1 Weiter-CTA-Füße für Orte/Idealwerte/Layout (JSX:298-307/322-328/338-344) im CompareEditor-Rahmen als Wrapper UM die geteilten Organismen. Vergleich-Tab-CTA existiert — gegen JSX:185-194 abgleichen (⊘-Hinweis „Name fehlt").

## Designentscheidungen (Analyse)

1. ~~In-Page-Mobile-Kopf statt TopAppBar~~ **REVIDIERT durch PO-Grundsatzregel
   2026-07-15 („nichts nachbauen — Claude-Design-Elemente verwenden, ggf.
   anpassen"):** Liste UND Editor befüllen die vorhandene globale
   `ui/sidebar/TopAppBar.svelte` (kanonische Design-Komponente aus #373,
   eyebrow/leftIcon/right-Props existieren, `title` fehlt → additiv ergänzen
   nach #373-Methode). Die nachgebaute `cm-mobile-appbar` im CompareEditor
   entfällt (behebt die heutige Doppel-Leiste mobil). Der ursprüngliche
   In-Page-Ansatz wäre ein Nachbau gewesen — der App-Bestand (Trip-Liste
   reflowt, Hub-In-Page-Eyebrow) ist keine Präzedenz, sondern dieselbe
   Alt-Lücke: seit #373 füttert keine Route die vorhandenen Design-Props.
2. **B1 als `dense`-Variante in Step2Orte** (eine Quelle, kein zweiter Orte-Stack im cm-mobile-Zweig) — Muster wie LayoutTab/VersandTab `dense`. Step2Orte ist compare-eigen (kein Trip-Pendant, Orte-Tab ist erlaubte Compare-Eigenheit).
3. **C0-Invariante:** CorridorEditor/LayoutTab/VersandTab/TripTabs = 0 Zeilen Diff. CTAs leben ausschließlich im CompareEditor-Rahmen.
4. **Alarme-Tab nicht anfassen** (#1258); CTA-Kette create bleibt vergleich→orte→idealwerte→layout→versand (alarme im create gesperrt, Bestand Z.1177).

## Dependencies

- Upstream: `compareEditorLogic.ts` (Lock-/Done-Sets als CTA-Bedingungen), `groupLocations()`, Atoms (Eyebrow/Btn/Stat/Card), MBtn, Sheet.
- Downstream: Staging-Suiten `.1256-s2/s6/s7/s8/s8c` (dürfen nicht brechen — insbesondere s8: `compare-mobile-vervollstaendigung.spec.ts` prüft Lock-Toast + floating CTA; s2: Klickpfade nutzen ggf. den generischen „Weiter →"-Text → Selektoren prüfen!).

## Risks & Considerations

- **CompareEditor.svelte 1414 Zeilen, LoC-Limit 250** — Umbau von CTA + Orte-Tab + App-Bar könnte knapp werden; kein Override ohne PO-Erlaubnis.
- Bestehende E2E-Wächter (geprüft): kein Spec hängt am „Weiter →"-Label; `compare-mobile-vervollstaendigung.spec.ts:288` und `issue-682-compare-editor-mobile.spec.ts:162` selektieren per testid (`cm-mobile-cta`, `compare-step2-mobile-library-btn`, `cm-mobile-appbar`) — diese testids MÜSSEN den Umbau überleben, sonst Suiten mitziehen.
- Versand-CTA mobil: 1:1 hieße entfernen (Aktivieren nur App-Bar) — Verhaltensänderung gegenüber S8-AC-24 („floating CTA unverändert") → als AC explizit machen, PO entscheidet beim Spec-go.
- Suchfeld-Entfernung mobil widerspricht historischem #582-Entscheid („immer sichtbar") — Handoff-5-P3 ist neuer und überstimmt; Quellen-Kommentar in der Datei mitziehen, sonst nächste „alter Kommentar/Wächter"-Falle.

## Existing Specs

- `docs/specs/modules/issue_1256_compare_ui_rewire.md` (Programm-Spec v1.3, Scheibenplan)
- `docs/specs/modules/feat_1256_s8c_hub_fidelity.md` (Vorgänger-Scheibe, Muster für Fidelity-ACs; Z.273 verweist R4 auf S8d)
