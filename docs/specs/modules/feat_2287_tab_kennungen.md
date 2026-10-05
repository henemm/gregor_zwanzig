---
entity_id: feat_2287_tab_kennungen
type: feature
created: 2026-10-05
updated: 2026-10-05
status: draft
version: "1.0"
tags: [trip-hub, compare-hub, reiter, kennungen, shared, paritaet, url, anlegen]
workflow: feat-2287-tab-kennungen
---

# Eine Reiterleiste: gemeinsame Reiter-Kennungen und ein gemeinsames `resolveTab()` für Trip- und Ortsvergleich-Hub (Issue #2287)

## Approval

- [ ] Approved

## Purpose

Issue #2287 (Epic #2345, Etappe P2 „eine Reiterleiste"). Trip-Hub und Ortsvergleich-Hub zeigen dieselben
Reiter, nennen sie in der Adresszeile aber verschieden: Wertebereiche heißt im Trip `alerts`, im Vergleich
`idealwerte`; Versand heißt `briefings` bzw. `versand`; Übersicht `overview` bzw. `uebersicht`; Vorschau
`preview` bzw. `vorschau`. Die Folgen sind nutzersichtbar: Ein Link mit der Kennung des anderen Hubs landet
**still auf der Übersicht** (Beispiel: die Home-Schnellaktion „Vorschau" eines Ortsvergleichs nutzt
`?tab=preview` und öffnet die Übersicht), und jede neue Schnellaktion muss die Kennungen beider Hubs kennen.

Nach dieser Etappe gilt für beide Hubs **eine** Tabelle, **eine** Auflösungsfunktion und **dieselben
Kennungen**:

`uebersicht · etappen|orte · wetter-metriken · wertebereiche · alarme · versand · vorschau`

Alte Kennungen (Lesezeichen, Verlauf, geteilte Links) werden in **beiden** Hubs auf den richtigen neuen Reiter
umgeleitet. Der Sonderfall `wertebereicheTabId(ctx)` (kontextabhängige Kennung für Wertebereiche) entfällt.
Die Anlege-Seiten (`/trips/new`, `/compare/new`) nutzen für ihre gemeinsame Schwanz-Kette dieselben Kennungen.

Kein Backend, keine Mails, keine Datenmigration: Der Reiter lebt ausschließlich in der URL (`?tab=`), es
gibt keinen localStorage-Merker, und in `internal/`, `src/`, `api/`, `cmd/` kommt kein `?tab=`-Link vor.

### Was der PO nach dieser Etappe anders sieht

1. In der Adresszeile steht überall dieselbe Kennung: `?tab=wertebereiche`, `?tab=versand`,
   `?tab=vorschau` — egal ob Trip oder Ortsvergleich.
2. Alte Links funktionieren weiter und werden beim Öffnen **einmal** auf die neue Kennung umgeschrieben (kein
   zusätzlicher Verlaufseintrag; die Zurück-Taste führt nicht auf die alte URL zurück).
3. Zwei Fehler verschwinden: Die Home-Schnellaktion „Vorschau" eines Ortsvergleichs öffnet jetzt die Vorschau
   (statt der Übersicht), und die „Wetter"-Links der Trip-Liste und der Wetter-Zusammenfassung öffnen jetzt
   den Reiter Wetter-Metriken (statt nur die Trip-Seite).
4. Sonst ändert sich am Bildschirm nichts (gleiche Reiter, gleiche Reihenfolge, gleiche Beschriftung).

## Source

- **Frontend (Pfade relativ zu `frontend/src/`):**
  - `lib/components/shared/subscriptionTabs.ts` (**CREATE**: `subscriptionTabs(kind)`, `resolveTab(kind, raw)`, LEGACY-Tabelle)
  - `lib/components/compare/compareTabsResolve.ts` (**DELETE**, einziger produktiver Importeur `CompareTabs.svelte`)
  - `lib/components/trip-detail/TripTabs.svelte` (MODIFY: Tabelle/Auflösung aus shared, Default, Flush-Guard-Literale, URL-Bereinigung, testids, Badge-Schlüssel)
  - `lib/components/compare/CompareTabs.svelte` (MODIFY: dito, `idealwerte`→`wertebereiche`, `handleValueChange`, Panel-testids)
  - `lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` (MODIFY: `SELBST_SPEICHERNDE_VERGLEICH_REITER`)
  - `lib/components/shared/alarme-tab/alarmeTabSections.ts` (MODIFY: `wertebereicheTabId` löschen)
  - `lib/components/shared/anlegeLockEngine.ts` (MODIFY: Kommentar „je Seite verschieden" entfällt)
  - `lib/components/trip-new/TripNewEditor.svelte`, `trip-new/tripNewLogic.ts`, `lib/components/compare-new/CompareNewEditor.svelte` (MODIFY: Kennungen der Schwanz-Kette)
  - `routes/trips/[id]/+page.svelte`, `routes/compare/[id]/+page.svelte` (MODIFY: Defaults, `tabNachUebernahme`, `?tab=vorschau`/`?tab=versand`)
  - `routes/+page.svelte` (Home: `TRIP_TAB_MAP`, alle `?tab=`-Links, Vergleich-Vorschau), `routes/trips/+page.svelte`, `routes/compare/+page.svelte` (Prüfung)
  - `lib/components/trip-detail/{HubOverview,BriefingPreviewCard,AlertsPreviewCard,PreviewCard}.svelte`, `lib/components/trip-detail/alerts-tab/AlertPreviewCard.svelte` (Sprunglinks)
  - `lib/components/edit/WeatherSummaryCard.svelte` (`#weather`)
  - `lib/components/shared/VersandTab.svelte` (`onJump('stages')`)
- **Tests:** `lib/components/shared/__tests__/subscription_tabs_resolve.test.ts` (CREATE) sowie bestehende Unit-Tests und E2E-Specs (siehe Testplan).
- **Kontext:** `docs/context/feat-2287-tab-kennungen.md` (Ist-Stand, Zeilen, Risiken).

> **Schicht:** ausschließlich Frontend (SvelteKit). Kein Go-, kein Python-Code. Verifiziert: kein `?tab=` in
> `internal/`, `src/`, `api/`, `cmd/`.

## Estimated Scope

- **LoC (produktiv):** grob +180 / −120 (neues Modul ~80, ~25 Literal-Tausche, Löschungen ~45) **plus** die
  Anlege-Editoren (wenige Zeilen Literal-Tausch in drei Dateien). Das Limit von 250 pro Workflow wird
  voraussichtlich überschritten → in `/50` vorher `workflow.py status`, danach ggf.
  `workflow.py set-field loc_limit_override 500` (Testcode und E2E-Tausch zählen nicht).
- **Files:** ~23 produktiv, ~8 Unit-Tests, E2E-Specs (mechanischer Tausch, ~100 Dateien betroffen).
- **Effort:** medium. **Risiko:** MEDIUM — fachlich einfach, aber breit; E2E ist nicht in der CI-Ampel.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `MTabBar.svelte` | Komponente (bereits geteilt) | Reiterleiste; bekommt Items aus `subscriptionTabs(kind)`, kennt selbst keine Kennungen |
| `SubscriptionHeader.svelte` (#2284) | Komponente (geteilt) | Hub-Kopf, kennt keine Reiter — unberührt |
| `compare_layout_tab_dissolution` | Spec | Vorbild der Alt-Umleitung (`RETIRED_TABS`), wird verallgemeinert |
| `feat_2277_s4_anlege_lockengine` | Spec | `TailIds`/`tailUnlocked` der Anlege-Seiten |
| SvelteKit `page.url.searchParams`, `goto`, `history.replaceState` | Framework | Lesen/Schreiben von `?tab=` |

## Implementation Details

### Entscheidungen (begründet)

**E1 — Ein geteiltes Modul.** `shared/subscriptionTabs.ts` (ein Code für beide kinds, wie im Epic gefordert):

```
type Kind = 'trip' | 'vergleich'
subscriptionTabs(kind) -> [{ id, label }]      // Reihenfolge = Reiterleiste in beiden Hubs
resolveTab(kind, raw)  -> { tab, legacy: boolean, known: boolean }
```

Reihenfolge der Auflösung in `resolveTab`:
1. neue Kennung des eigenen kind (Tabelle von `subscriptionTabs(kind)`) → unverändert;
2. LEGACY-Tabelle, **kind-übergreifend**: `overview→uebersicht`, `stages→etappen`, `weather→wetter-metriken`,
   `alerts→wertebereiche`, `briefings→versand`, `preview→vorschau`, `idealwerte→wertebereiche`,
   `layout→wetter-metriken`;
3. kind-fremde Punkte-Kennung: `orte` im Trip → `etappen`; `etappen` im Vergleich → `orte`;
4. sonst Fallback `uebersicht` (`known: false`).

`legacy` ist `true` für Treffer aus 2 und 3, damit die Hubs die URL bereinigen können (E4).
`compareTabsResolve.ts` entfällt ersatzlos (`COMPARE_TABS`, `RETIRED_TABS`, `resolveCompareTab` gehen im
neuen Modul auf).

**E2 — Abweichung vom Issue-Text: Punkte-Reiter heißt `etappen` (Trip) bzw. `orte` (Vergleich), nicht
`punkte`.** Das Issue-Zielbild nennt `punkte|etappen|orte`. `punkte` existiert im ganzen Code nirgends,
Trip-Anlegen nutzt bereits `etappen`, der Vergleich bereits `orte`, und die Kennung ist für den Nutzer in der
URL sichtbar — eine sprechende Bezeichnung ist besser als ein neues Kunstwort. Die Reiter-Position und die
Teilung (Punkte-Reiter ist der einzige kind-eigene Reiter) bleiben wie vom Epic vorgesehen.

**E3 — Präzisierung zu Issue-AC-1 („kein stiller Fall auf Übersicht").** Der stille Fall des Issues waren
**alte Kennungen** (`/trips/{id}?tab=alerts`); die werden jetzt umgeleitet. Eine **völlig unbekannte**
Kennung (weder neu noch alt, z. B. Tippfehler `?tab=foo`) öffnet weiterhin die Übersicht, und die URL wird auf
die Übersicht bereinigt (Parameter `tab` entfernt). Das ist ein **bewusster Rest-Fallback**, keine
Lücke: Für einen kaputten Link bringt eine Fehlermeldung dem Nutzer nichts, der Hub bleibt voll bedienbar, und
es entsteht keine neue Fehler-UI. Es bleibt also **eine** Stelle, an der still auf die Übersicht gefallen
wird — und nur für Kennungen, die es in keinem Hub je gegeben hat.

**E4 — URL-Bereinigung bei Alt-Kennung.** Wird beim Öffnen eine Alt-Kennung (oder kind-fremde
Punkte-Kennung) erkannt, schreibt der Hub die Adresszeile **einmal** per `replaceState` auf die neue Kennung
um (kein zusätzlicher Verlaufseintrag). Lesezeichen und weitergeteilte Links werden dadurch eindeutig. Je Hub
im bestehenden Muster: Trip `goto(url, { replaceState: true })`, Vergleich `history.replaceState`.

**E5 — testids werden mit umbenannt, im selben Ticket.** Betroffen: `trip-detail-tab-*`,
`trip-detail-badge-*`, `trip-detail-panel-*`, `compare-detail-tab-idealwerte`,
`compare-detail-panel-idealwerte`, `compare-editor-continue-idealwerte` sowie die kennungsabgeleiteten
testids der Anlege-Seiten (`compare-editor-tab-*`, `cm-mobile-tab-*`, TripNew-Entsprechungen) für die
umbenannten Kennungen. Begründung: Dauerhaft stabile Alt-testids würden genau die Drift konservieren, die
das Epic beseitigt; ein Folgeticket hieße stumm rote E2E. Der Tausch in den E2E-Specs ist mechanisch
(Wortgrenzen, nur in testid-Kontexten). **E2E ist nicht in der CI-Ampel** — die betroffenen Specs MÜSSEN in
`/e2e-verify` gegen Staging laufen; erst dort fallen Brüche auf.

**E6 — Anlege-Editoren sind im Scope (kein Abspalten).** Die Schwanz-Kette der Anlege-Seiten nutzt dieselben
Kennungen wie die Hubs: `wetter-metriken`, `wertebereiche`, `alarme`, `versand`; der Punkte-Reiter heißt
`etappen` (Trip) bzw. `orte` (Vergleich). Ist-Stand: Trip-Anlegen `metriken`/`wertebereiche`, Vergleich-Anlegen
`metriken`/`idealwerte` (`CompareNewEditor.svelte` Typ `CompareNewTabId` :61, `TAIL` :62-64,
`PROGRESS_STEPS` :65, `TAB_DEFS` :113-117, `switchTab` :207-211, Weiter-Knopf :426,
Panel-Weichen :429/:525/:550; Trip: `TabId` in `tripNewLogic.ts:21`, `TAB_DEFS` :76-81, `TAIL` :28).
Kind-eigen bleiben nur Reiter ohne Hub-Pendant:
- erster Reiter (Trip `route`, Vergleich `vergleich` = Name/Grunddaten): Anlegen hat keine Übersicht;
- Trip-Anlegen `wegpunkte` („Wegpunkte prüfen", **optionaler** Unter-Schritt nach `etappen`, nur für GPX-Prüfung;
  im Hub gibt es dafür keinen Reiter) — bleibt unverändert.
Die Anlege-Seiten schreiben kein `?tab=`; die Freischalt-Reihenfolge (`tailUnlocked`) ist unverändert. Der
Kommentar in `anlegeLockEngine.ts:11` („je Seite verschieden: wertebereiche vs. idealwerte") wird obsolet und
entfällt. Mit der Umbenennung hat `TailIds` in beiden Seiten dieselben Werte.

**E7 — Bestandsbugs werden mitgelöst** (nutzersichtbar, je ein AC): Home-Schnellaktion „Vorschau" eines
Ortsvergleichs (`routes/+page.svelte:585`, `?tab=preview`) und die `#weather`-Hash-Links
(`routes/trips/+page.svelte:141,529`, `lib/components/edit/WeatherSummaryCard.svelte:28`), die heute den
Wetter-Metriken-Reiter nicht öffnen, weil der Hash nie gelesen wird → `?tab=wetter-metriken`.

**E8 — Nicht anfassen (andere Namensräume, nur Namensgleichheit):** `WeatherMetricsTab.svelte:1018` und
`tripSpeicherung.ts:141` (`'wetter-metriken'` als Speicher-Schlüssel), `subscriptionHelpers.ts:300`
(Action-ID `preview`), Kebab-Keys der Trip-Liste (`routes/trips/+page.svelte` :94-96/:112).

**E9 — Teilung (Pendant-Sperre).** `subscriptionTabs.ts` liegt unter `shared/` (ein Code für beide kinds, Parameter
`kind`). `TripTabs.svelte` und `CompareTabs.svelte` bleiben **kind-eigen**: Panels, Badges, Speicher-Controller
und Inhalte der Reiter unterscheiden sich (Etappen vs. Orte, Trip-Speicher vs. Vergleich-Speicher), ihre
Zusammenlegung ist eine eigene Etappe des Epics #2345 und nicht Teil von #2287. Die Reiterleiste selbst
(`MTabBar`) ist bereits geteilt; mit dieser Spec kommen auch Tabelle, Auflösung und Alt-Umleitung dazu. Es wird
**kein** neues Compare-Pendant zu einer Trip-Komponente angelegt.

### Zu ändernde Stellen (Zeilennummern am 2026-10-05 verifiziert, relativ zu `frontend/src/`)

| Stelle | Änderung |
|---|---|
| `lib/components/trip-detail/TripTabs.svelte` | `TABS` :85-93, `VALID_VALUES` :111, `resolve()` :113-115, `initialTab` :48/:127-129, Flush-Guard-Literale **:168**, `goto(?tab=)` :178, testids :106/:107/:195, Badge-Interface :25-33/:63-71, Panel-Weiche :196-214 |
| `lib/components/compare/CompareTabs.svelte` | `resolve` :135-137, Default :128/:139, testid :149, `history.replaceState` :175-177, ~13 `activeTab ===`-Vergleiche, `handleValueChange('…')` :875-946, Panel-testids :778-1156 |
| `lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | `SELBST_SPEICHERNDE_VERGLEICH_REITER` **:251-256**: `idealwerte`→`wertebereiche` |
| `lib/components/shared/alarme-tab/alarmeTabSections.ts` | `wertebereicheTabId` :41-43 löschen (kein produktiver Aufrufer; der Alarme-Reiter springt in beiden kinds auf `wertebereiche`) |
| `routes/trips/[id]/+page.svelte` | `?tab=` lesen :115 (Default `overview`→`uebersicht`), Durchreichen :396 |
| `routes/compare/[id]/+page.svelte` | `?tab=` lesen :205, `tabNachUebernahme` :117/:133, `?tab=vorschau` :260, `?tab=versand` :348 |
| `routes/+page.svelte` (Home) | `TRIP_TAB_MAP` :92/:99, `?tab=overview` :97/:190/:279/:701, stages :299, weather :305, briefings :311, preview :317, alerts :382; Vergleich idealwerte :573, versand :579, `?tab=preview` :585 |
| `routes/trips/+page.svelte` | `?tab=preview` :139/:164/:521; `#weather` :141/:529 |
| `routes/compare/+page.svelte` | `?tab=vorschau` :127 (bereits neu, nur prüfen) |
| `lib/components/trip-detail/HubOverview.svelte` | `makeJumpHandler` :58/:106/:115/:122/:128 |
| `BriefingPreviewCard.svelte:51`, `AlertsPreviewCard.svelte:61`, `PreviewCard.svelte:26/:34`, `alerts-tab/AlertPreviewCard.svelte:65` | Sprunglinks |
| `lib/components/edit/WeatherSummaryCard.svelte:28` | `goto(/trips/${id}#weather)` → `?tab=wetter-metriken` |
| `lib/components/shared/VersandTab.svelte:305` | `onJump?.('stages')` → `'etappen'`; Übersetzung `stages|etappen` in `TripNewEditor.svelte:366` entfällt/vereinfacht |

Hinweis: `routes/trips/[id]/edit/+page.server.ts:5-6` reicht `?tab=` ungeprüft an die Detailseite durch; die
Auflösung dort übernimmt der Hub, eine Änderung ist nicht nötig (durch Test abgedeckt, AC-13).

## Expected Behavior

- **Input:** `?tab=<Kennung>` in der URL von `/trips/{id}` bzw. `/compare/{id}`; Klicks auf Reiter,
  Sprunglinks und Schnellaktionen.
- **Output:** der gleichnamige Reiter wird geöffnet; bei Alt-Kennung zusätzlich einmalige URL-Bereinigung.
- **Side effects:** keine (kein Backend, kein localStorage, keine Daten).

## Acceptance Criteria

- **AC-1:** Given ein Trip-Hub und eine URL mit einer Alt-Kennung (`overview`, `stages`, `weather`, `alerts`,
  `briefings` oder `preview`) / When die Seite geöffnet wird / Then öffnet sich der zugehörige neue Reiter
  (Übersicht, Etappen, Wetter-Metriken, Wertebereiche, Versand bzw. Vorschau) — insbesondere landet
  `/trips/{id}?tab=alerts` im Reiter Wertebereiche und nicht auf der Übersicht.
  - Test: Unit `resolveTab('trip', …)` je Alt-Kennung (tabellengetrieben) plus Hub-Pfad (AC-12).

- **AC-2:** Given ein Ortsvergleich-Hub und eine URL mit einer Alt-Kennung (`idealwerte`, `layout`) oder einer
  Trip-Alt-Kennung (`alerts`, `briefings`, `weather`, `stages`, `preview`, `overview`) / When die Seite geöffnet
  wird / Then öffnet sich der zugehörige neue Reiter (`idealwerte`/`alerts`→Wertebereiche, `layout`/`weather`→
  Wetter-Metriken, `briefings`→Versand, `preview`→Vorschau, `overview`→Übersicht, `stages`→Orte); die
  Auflösung ist in beiden Hubs dieselbe Tabelle (Beispiel: `/compare/{id}?tab=alerts` → Wertebereiche).
  - Test: Unit `resolveTab('vergleich', …)` für alle Alt-Kennungen; Bestandstest `compare_layout_tab_dissolution`
    `?tab=layout` bleibt als Alt-Umleitung gültig.

- **AC-3:** Given eine Alt-Kennung wurde erkannt (Trip oder Vergleich) / When der Hub den Reiter geöffnet hat /
  Then zeigt die Adresszeile die neue Kennung (`?tab=wertebereiche` statt `?tab=alerts`/`?tab=idealwerte`),
  und es entsteht kein zusätzlicher Verlaufseintrag: die Zurück-Taste führt nicht zurück auf die Alt-URL.
  - Test: Hub-Pfad-Test je Hub (AC-12) bzw. Playwright: nach `goto(?tab=alerts)` ist `page.url()` `…tab=wertebereiche`
    und `history.length` unverändert gegenüber dem Direktaufruf.

- **AC-4:** Given beliebiger Hub (Trip oder Vergleich) / When die URL `?tab=` eine der neuen Kennungen enthält
  (`uebersicht`, `etappen`|`orte`, `wetter-metriken`, `wertebereiche`, `alarme`, `versand`, `vorschau`) /
  Then öffnet sich in beiden Hubs genau der gleichnamige Reiter ohne URL-Umschreibung — insbesondere öffnet
  `?tab=versand` in Trip und Vergleich den Versand-Reiter.
  - Test: Unit `resolveTab` für alle neuen Kennungen × beide kinds (`legacy: false`, `known: true`).

- **AC-5:** Given der Punkte-Reiter ist je Hub verschieden benannt / When im Trip `?tab=orte` bzw. im Vergleich
  `?tab=etappen` geöffnet wird / Then öffnet der Trip den Reiter Etappen und der Vergleich den Reiter Orte
  (kind-fremde Punkte-Kennung wird auf den eigenen Punkte-Reiter umgeleitet und die URL entsprechend bereinigt).
  - Test: Unit `resolveTab('trip','orte')` → `etappen`, `resolveTab('vergleich','etappen')` → `orte`.

- **AC-6:** Given eine völlig unbekannte Kennung (weder neu noch alt, z. B. `?tab=foo`) / When ein Hub geöffnet
  wird / Then öffnet sich die Übersicht und der Parameter `tab` wird aus der Adresszeile entfernt; es erscheint
  keine Fehlermeldung. Das ist der bewusste Rest-Fallback (Entscheidung E3), er gilt in beiden Hubs gleich.
  - Test: Unit `resolveTab(kind,'foo')` → `uebersicht`, `known: false`; ebenso leerer/fehlender Wert.

- **AC-7:** Given der Nutzer hat im Trip-Hub in einem selbst speichernden Reiter (Wertebereiche, Wetter-Metriken,
  Versand, Alarme, Etappen) eine ungespeicherte Änderung (`saveController.hasPending`) / When er auf einen
  anderen Reiter wechselt / Then wird die Änderung vor dem Wechsel gespeichert (Flush), wie vor #2287 — die
  Flush-Guard-Literale in `TripTabs.svelte` benutzen die neuen Kennungen, ein vergessenes Alt-Literal darf den
  Schutz nicht still abschalten.
  - Test: Hub-Test mit neuer Kennung je Reiter der Guard-Liste: Reiterwechsel mit `hasPending` ruft `flush()`
    (rot, wenn ein Literal noch `alerts`/`weather`/`briefings`/`stages` lautet).

- **AC-8:** Given der Nutzer hat im Ortsvergleich-Hub in einem selbst speichernden Reiter eine ungespeicherte
  Änderung / When er den Reiter wechselt / Then greift der Flush-Guard weiter: `SELBST_SPEICHERNDE_VERGLEICH_REITER`
  enthält `wertebereiche` (nicht mehr `idealwerte`), `alarme`, `wetter-metriken`, `versand`; ein Wechsel aus dem
  Reiter Wertebereiche mit ausstehender Speicherung löst den Flush aus.
  - Test: Unit auf die Liste inkl. Flush-Verhalten des generischen Guards mit `wertebereiche`; Mutation
    (`wertebereiche` zurück auf `idealwerte`) muss genau diesen Test rot machen.

- **AC-9:** Given der Nutzer ist in einem Hub und klickt einen Sprunglink (HubOverview-Karten, BriefingPreviewCard,
  AlertsPreviewCard, PreviewCard, AlertPreviewCard, VersandTab-`onJump`, `handleValueChange` im Vergleich,
  Vergleich-Detailseite nach „Übernehmen" (`tabNachUebernahme`) / `?tab=vorschau` / `?tab=versand`) / When der
  Link ausgelöst wird / Then öffnet sich der erwartete Reiter, und die dabei erzeugte URL enthält ausschließlich
  neue Kennungen (keine Umleitung nötig).
  - Test: pro Sprunglink Zielkennung gegen `subscriptionTabs(kind)` prüfen (jede erzeugte Kennung ist neu und
    bekannt); stichprobenartig im Browser.

- **AC-10:** Given die Schnellaktionen von Startseite, Trip-Liste und Vergleich-Liste (Übersicht, Etappen,
  Wetter, Versand, Vorschau, Alarme, Wertebereiche) / When der Nutzer eine Schnellaktion wählt / Then landet er
  im jeweils richtigen Reiter und die URL enthält nur neue Kennungen — **insbesondere** öffnet die Startseiten-
  Schnellaktion „Vorschau" eines Ortsvergleichs jetzt die Vorschau (Bestandsfehler: bisher `?tab=preview`,
  Landung auf der Übersicht), und die „Wetter"-Links der Trip-Liste und der Wetter-Zusammenfassung
  (`WeatherSummaryCard`) öffnen den Reiter Wetter-Metriken (Bestandsfehler: Hash `#weather` wurde nie gelesen).
  - Test: Unit-Test auf die erzeugten Ziel-URLs (Home `TRIP_TAB_MAP`, Vergleich-Vorschau, `#weather`-Ersatz) und
    E2E auf Staging für die drei Bestandsfehler; kein `#weather` mehr im Quelltext der drei Stellen.

- **AC-11:** Given der Reiter „Alarme" verweist auf die Wertebereiche / When der Nutzer im Alarme-Reiter den
  Sprunglink zu den Wertebereichen anklickt (Trip und Vergleich) / Then springen beide Hubs mit derselben
  Kennung `wertebereiche`; die kontextabhängige Funktion `wertebereicheTabId` existiert nicht mehr (weder im
  Quelltext noch im Test `alarme_tab_sections.test.ts`).
  - Test: der Test auf `wertebereicheTabId` (`alarme_tab_sections.test.ts:96-101`) wird gelöscht; Sprungziel-Test
    je kind auf `wertebereiche`.

- **AC-12:** Given der echte Hub-Pfad (nicht nur die Hilfsfunktion) / When im Trip-Hub `?tab=alerts` bzw. im
  Vergleich-Hub `?tab=idealwerte` übergeben wird / Then rendert der Hub das Panel Wertebereiche
  (`trip-detail-panel-wertebereiche` bzw. `compare-detail-panel-wertebereiche`) und schreibt die URL auf
  `?tab=wertebereiche` um. Ein reiner Unit-Test auf `resolveTab` genügt nicht: der Test MUSS belegen, dass
  `TripTabs` und `CompareTabs` die gemeinsame Auflösung wirklich benutzen.
  - Test: SSR-Harness (wie bestehende `__tests__`) oder Playwright je Hub; Mutation „Hub benutzt eigene
    Auflösung / vergisst die Umleitung" muss rot werden.

- **AC-13:** Given die Anlege-Seiten `/trips/new` und `/compare/new` / When der Nutzer die Reiter der
  Schwanz-Kette durchläuft / Then tragen diese in beiden Seiten dieselben Kennungen (`wetter-metriken`,
  `wertebereiche`, `alarme`, `versand`; Punkte-Reiter `etappen` bzw. `orte`), die Freischalt-Reihenfolge ist
  unverändert (Wertebereiche erst nach Wetter-Metriken, Alarme erst nach Wertebereichen, Versand erst nach
  Alarmen), und beide Seiten übergeben `tailUnlocked` identische `TailIds`. Der optionale Trip-Schritt
  `wegpunkte` und die ersten Reiter `route`/`vergleich` bleiben kind-eigen. Es wird kein `?tab=` geschrieben.
  - Test: `tailUnlocked`-Test mit beiden Seiten-`TailIds` (identisch), `compare_layout_tab_dissolution`-Test
    angepasst (`COMPARE_TAIL`), Playwright der Anlege-Flows mit neuen testids.

- **AC-14:** Given ein Handy (Breite < 768 px) / When ein Hub geöffnet wird / Then zeigt die Reiterleiste
  (`MTabBar`) in Trip und Vergleich dieselben Kennungen in derselben Reihenfolge wie am Desktop
  (Übersicht · Etappen|Orte · Wetter-Metriken · Wertebereiche · Alarme · Versand · Vorschau), und ein Antippen
  öffnet den gleichnamigen Reiter.
  - Test: Item-Liste von `MTabBar` kommt aus `subscriptionTabs(kind)` (Gleichheit Desktop/Mobil im Unit-Test);
    E2E mit Handy-Viewport.

- **AC-15:** Given die Umbenennung der testids (E5) / When der Quelltext von Frontend und E2E geprüft wird /
  Then kommt keines der Alt-Literale (`overview`, `stages`, `weather`, `alerts`, `briefings`, `preview` in
  `trip-detail-tab-/-badge-/-panel-*`-Kontexten; `idealwerte` in `compare-detail-*`, `compare-editor-*`,
  `cm-mobile-tab-*`) mehr in einem testid-Kontext unter `frontend/e2e` und `frontend/src` vor
  (`rg`-Prüfung = 0 Treffer), und die betroffenen E2E-Specs laufen in `/e2e-verify` gegen Staging grün.
  - Test: `rg`-Prüfung im Adversary-/Validate-Schritt; E2E-Lauf in `/e2e-verify` (Hard Gate, nicht in der CI-Ampel).

## Testplan

- **Laufzeit:** Frontend-Tests laufen über `node --test` (kein Vitest). Testdateien nach Verhalten benennen:
  `shared/__tests__/subscription_tabs_resolve.test.ts` (neu), kein Issue-Nummer-Name.
- **Unit (Kern, deterministisch):** `resolveTab` für beide kinds: alle neuen, alle Alt-, kind-fremde,
  unbekannte und leere Kennungen; `subscriptionTabs(kind)` Reihenfolge/Labels; `legacy`-/`known`-Flags.
- **Hub-Pfad-Tests (Pflicht, AC-12):** je Hub mindestens ein Test über den echten Pfad (SSR-Harness wie in den
  bestehenden `__tests__` oder Playwright): `?tab=alerts` (Trip) bzw. `?tab=idealwerte` (Vergleich) öffnet
  Wertebereiche und schreibt die URL um.
- **Flush-Guard-Test je Hub mit neuer Kennung (AC-7, AC-8).**
- **Bestehende Unit-Tests anpassen oder löschen** (laufen in der Ampel `frontend-test`):
  `alerts-tab/issue_850_alert_metrics_stale.test.ts:69`, `compare/__tests__/issue_1273_s3_redirect_links.test.ts:82-94`,
  `utils/safeRedirect.test.ts:13`, `routes/trips/trip_edit_leitet_auf_detailseite_um.test.ts:44-46`,
  `shared/__tests__/alarme_tab_sections.test.ts:28,96-101` (Test auf `wertebereicheTabId` **löschen**),
  `compare/__tests__/compare_layout_tab_dissolution.test.ts` (`COMPARE_TAIL` :55 auf `wertebereiche`; :207
  `?tab=layout` bleibt gültig als Alt-Umleitung).
- **E2E (nicht in der CI-Ampel):** mechanischer Literal-Tausch der testids in den E2E-Specs (Trip:
  `overview`≈10, `stages`≈27, `weather`≈53, `alerts`≈6, `briefings`≈7, `preview`≈3 Treffer in
  `trip-detail-tab-*`; Vergleich: `idealwerte`≈12 in `compare-detail-tab-*`, plus `-panel-`/`-badge-`/
  `compare-editor-*`); Prüfkriterium `rg` auf Alt-Literale in testid-Kontexten = 0 (AC-15). Die betroffenen
  Specs MÜSSEN in `/e2e-verify` gegen Staging laufen; ein Flake wird wiederholt, erst reproduzierbares
  Scheitern ist ein Befund.
- **Fresh-Eyes:** Keine sichtbare UI-Änderung außer dem korrekt geöffneten Reiter (gleiche Reiter, Reihenfolge,
  Beschriftung, Layout). Ein `fresh-eyes-inspector` bringt hier keinen zusätzlichen Befund und ist nicht
  erforderlich; die visuelle Gleichheit prüft der Adversary stichprobenartig per Screenshot-Vergleich.
- **Mutations-Gegenprobe (Adversary, Pflicht):** u. a. `wertebereiche` im Vergleich-Guard zurück auf
  `idealwerte`; ein Trip-Guard-Literal zurück auf `alerts`; Hub benutzt eigene statt gemeinsamer Auflösung;
  LEGACY-Eintrag `idealwerte` entfernen; Home-Vergleich-Vorschau zurück auf `preview`; `legacy`-Flag auf `false`
  setzen (URL wird nicht bereinigt). Je Mutation muss **ein benannter Test** rot werden.

## Known Limitations

- **Unbekannte Kennungen** (Tippfehler) fallen bewusst weiterhin auf die Übersicht (E3), ohne Fehlermeldung.
- **`TripTabs.svelte`/`CompareTabs.svelte` bleiben zwei Komponenten** (E9); ihre Zusammenlegung ist eine
  spätere Etappe des Epics #2345.
- Die URL-Schreibweise unterscheidet sich weiterhin technisch (Trip `goto`, Vergleich `history.replaceState`);
  das Ergebnis in der Adresszeile ist gleich.
- Alte Lesezeichen funktionieren ohne Befristung (die LEGACY-Tabelle bleibt); ein Rückbau wäre ein eigenes
  Prüfdatum (siehe ADR-Abschnitt).
- E2E-Brüche durch übersehene testids werden erst in `/e2e-verify` sichtbar, nicht in der CI-Ampel.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Konvergenz innerhalb des bestehenden Editor-Paradigmas und der in `docs/adr/` dokumentierten
  Trip/Ortsvergleich-Teilung (Epic #2345); es wird keine dokumentierte Entscheidung rückgängig gemacht, sondern
  die Angleichung der Reiter-Kennungen vollzogen. Regel-Budget: keine neue Pflicht-Regel, kein neues Gate.
  Die LEGACY-Tabelle ist kein Gate; Prüfdatum für ihren möglichen Rückbau: 2027-01-05 (+90 Tage), sofern in
  Zugriffsprotokollen keine Alt-Kennung mehr auftaucht.

## Changelog

- 2026-10-05: Initial spec created (v1.0) — Issue #2287, Epic #2345 Etappe P2.
