---
entity_id: feat_2284_s1_subscription_header
type: feature
created: 2026-10-03
updated: 2026-10-03
status: draft
version: "1.0"
tags: [compare-hub, trip-hub, kopf, shared, refactoring, paritaet]
---

# Geteilter Kopf-Baustein `SubscriptionHeader`, Vergleich-Hub darauf umgestellt (Issue #2284 Scheibe S1)

## Approval

- [ ] Approved

## Purpose

Erste Scheibe von #2284 (Epic #2345, Etappe P2: Hub-Kopf-Parität Trip ↔ Vergleich). Heute ist der Kopf
des Vergleich-Hubs als Inline-Markup direkt in `routes/compare/[id]/+page.svelte` gebaut, und zwar
**doppelt**: ein Desktop-Block und ein Mobil-Block tragen dieselben `data-testid`s. Der Trip-Hub hat
einen anderen, eigenen Kopf (`TripHeader.svelte`). Ein Baustein für beide Hubs ist das Ziel von #2284;
diese Scheibe legt ihn an und stellt zunächst den Vergleich-Hub darauf um.

**Für den Nutzer ändert sich am Vergleich-Kopf nichts.** Name, Region und Aktivitätsprofil sind weiter
per Stift inline editierbar, das Speichern schreibt dieselben Felder, Fehler erscheinen an derselben
Stelle, alle `data-testid`s bleiben. Es entfällt nur die Doppelung im Code: es gibt **ein** Markup für
Desktop und Mobil.

Was der Baustein leistet:

- Name (Überschrift), Region (Textzeile) und Profil (Kachelreihe) inline bearbeiten, alles über Props
  gesteuert.
- Er kennt **keinen** Speicherweg: das Speichern liefert die Seite als Funktion `onSaveField(field, value)`,
  die bei Fehler wirft. Der Baustein zeigt die Fehlermeldung am jeweiligen Feld.
- Er kennt **keinen** Kontext-Unterschied im Markup: Trip und Vergleich unterscheiden sich nur durch
  Props (Optionen, Präfix, Beschriftung, Snippets).
- Er stellt einen leeren `actions`-Snippet-Slot als Andockpunkt für das Aktionsmodell aus #2278 bereit.

## Source

- **Frontend (Pfade relativ zu `frontend/src/`):**
  `lib/components/shared/subscription-header/SubscriptionHeader.svelte` (CREATE),
  `routes/compare/[id]/+page.svelte` (MODIFY: Inline-Markup `:337-387` und `:420-482` entfällt, Speicher-
  funktionen `:170-225` werden zu `onSaveField`),
  `lib/components/shared/__tests__/subscription_header_*.test.ts` (CREATE, s. Test-Plan)
- **Identifier:** `SubscriptionHeader`, `onSaveField`, `testidPrefix`, `compare-hub-name-edit-toggle`,
  `compare-hub-name-edit`, `compare-hub-name-save`, `compare-hub-name-save-error`,
  `compare-hub-region-edit-toggle`, `compare-hub-region-edit`, `compare-hub-region-save`,
  `compare-hub-region-save-error`, `compare-hub-profil-option-{wert}`, `compare-hub-profil-save-error`

> **Schicht-Hinweis:** ausschließlich **Frontend**. Kein Go-API-, kein Python-Core-Code, kein Schema-
> Eingriff, kein Mail-Renderer. Der Backend-Vertrag von `PUT /api/compare/presets/{id}` (Merge:
> fehlendes Feld = unverändert, seit #2285) bleibt unberührt.

## Entscheidungen

1. **Ort `shared/`.** Der Baustein liegt unter `frontend/src/lib/components/shared/subscription-header/`
   und ist damit vom `pendant_gate` ausgenommen (das überwacht nur neue Dateien in `compare/`,
   `compare-new/`, `trip-detail/`, `trip-new/`). Genau so ist es gewollt: ein Baustein für beide Hubs,
   kein Compare-eigenes Pendant zu `TripHeader`.
2. **Props.** `kind` (`'trip' | 'vergleich'`, rein beschreibend, **nicht** im Markup verzweigt — er
   kann z. B. in `data-kind` stehen), `name`, `region`, `profile` (aktueller Wert), `profileOptions`
   (Liste `{value,label}`; Vergleich: `ACTIVITY_PROFILE_OPTIONS`), `profileLabel` (Anzeigetext für die
   Unterzeile; leer ⇒ entfällt), `regionMaxLength` (Vergleich: 60), `testidPrefix` (Vergleich:
   `compare-hub`), `onSaveField(field, value)`, dazu Snippets `eyebrow`, `badges` (Platz neben dem Namen:
   Status-Pille und „Laufzeit überschritten"), `meta` (Zusatztext der Unterzeile, z. B. „· 3 Orte") und
   `actions` (in S1 von keiner Seite befüllt).
3. **Kein `api`-Import im Baustein.** `onSaveField(field, value)` mit `field ∈ {'name','region','profile'}`
   ist ein `async`-Callback; er **wirft** bei Fehler. Der Baustein fängt den Fehler, liest
   `e.error` (Fallback `'Speichern fehlgeschlagen'`) und zeigt ihn am Feld an — identisch zum heutigen
   `catch`-Block. Die Seite bildet daraus die drei heutigen PUTs (nur das geänderte Feld, kein Spread der
   Seiten-Kopie — Regel aus #2375/#2381) und ersetzt nach Erfolg `currentPreset` **mit neuer Objekt-
   Referenz** (Cross-Tab-Resync in `CompareTabs`).
   **Nachtrag nach Integration von #1433 / PR #2486 (2026-10-03):** Die Signatur lautet
   `onSaveField(field, value, schliessen: () => void): Promise<void>` mit **drei Ausgängen**:
   (a) **übernommen** — die Seite ruft `schliessen()` (aus `nachErfolg` von `baueSpeicherung`), das Feld
   schließt; (b) **Konflikt (412)** — die Seite übergibt an den Konflikt-Controller („Nochmal speichern",
   `speichereOderMeldeKonflikt`, Eintrag je Feld `kopf-name|kopf-region|kopf-profil`), das Promise wird
   **ohne** `schliessen()` erfüllt: Feld bleibt offen, keine eigene Fehlermeldung; gelingt der Retry
   später, ruft `nachErfolg` `schliessen()` und das Feld schließt; (c) **Fehler** — wirft wie oben. Der
   Baustein schließt das Feld ausschließlich über `schliessen`. Während „Nochmal speichern" läuft, wird
   `currentPreset` nicht ersetzt (Guard `imWiederholen`, #1433 F101). Für den Nutzer ändert sich
   gegenüber dem #1433-Stand nichts.
4. **Kein `if kind ===` im Markup.** Alle Unterschiede zwischen Trip und Vergleich laufen über Props
   (Optionen, Präfix, Snippets, `regionMaxLength`). Das ist Voraussetzung dafür, dass S2 den Trip-Kopf
   ohne Markup-Zweig auf denselben Baustein setzen kann.
5. **EIN Markup für Desktop und Mobil.** Unterschiede der Darstellung (Schriftgrößen, Knopfbeschriftung
   „Umbenennen/Speichern/Abbrechen" auf Desktop gegen „OK/×" mobil, Mindest-Tippfläche 44 px mobil) laufen
   über responsive Klassen (`desktop:`-Variante ab 900 px, wie in der Seite heute). Wo ein Text je
   Viewport abweicht, stehen beide Texte als `hidden desktop:inline` bzw. `desktop:hidden` im selben
   Knopf. Weicht die mobile Anordnung dennoch stark ab, ist ein `{#snippet}` **innerhalb** des Bausteins
   erlaubt — nie eine zweite Komponente.
6. **Seiten-Chrome bleibt in der Seite.** Breadcrumb (Desktop), `BackLink` (Mobil), der
   „Test senden"/„Setup abschließen"-Knopf, `CompareKebab` und der mobile „Weitere Aktionen"-Knopf
   gehören nicht zum Baustein (Aktionsmodell → #2278). Die Mobil-Eyebrow „Orts-Vergleich · Hub" wird als
   `eyebrow`-Snippet übergeben (nur mobil sichtbar), der Status samt „Laufzeit überschritten" als
   `badges`-Snippet.
7. **Fehler- und Offen-Verhalten unverändert übernommen:** Bei fehlgeschlagenem Speichern von Name oder
   Region bleibt das Eingabefeld **offen** mit dem eingetippten Wert (kein Rücksprung in den Anzeige-
   Modus, kein `<h1>`); die Fehlermeldung erscheint unter dem Feld mit `role="alert"`. Der Profil-Klick
   hat keinen Eingabemodus: bei Fehler erscheint die Meldung unter den Kacheln, die Auswahl bleibt auf
   dem zuletzt gespeicherten Wert (die Kachel springt erst nach erfolgreichem Speichern um, weil
   `profile` aus der Seite kommt). Während des Speicherns ist der jeweilige Knopf (Name/Region: Speichern;
   Profil: alle Kacheln) `disabled`. „Abbrechen" verwirft Eingabe und Fehler.
8. **Speicher-Chip bleibt an seinem Ort.** Der Chip (`SaveIndicator`, Montage in `CompareTabs.svelte`)
   wird in S1 nicht angefasst. Sein Umzug in den Baustein ist Teil von Scheibe S2 derselben Issue #2284
   (wegen der gleichzeitigen Änderung an `TripHeader`, erst nach Merge von PR #2486).

## Acceptance Criteria

**AC-1:** Given ein Nutzer öffnet den Vergleich-Hub im Desktop-Viewport (1280 px) When er den Stift am
Namen klickt, einen neuen Namen eingibt und „Umbenennen" klickt Then erscheint der neue Name sofort in
der Überschrift (`<h1>`) und steht nach einem Neuladen der Seite unverändert dort, weil `PUT
/api/compare/presets/{id}` ihn gespeichert hat.

**AC-2:** Given ein Nutzer öffnet den Vergleich-Hub im Mobil-Viewport (375 px) When er Name, Region und
Aktivitätsprofil nacheinander über Stift bzw. Kachel ändert (Mobil-Knöpfe „OK") Then sind alle drei Werte
nach dem Neuladen persistiert (Name im Titel, Region in der Unterzeile, gewählte Profil-Kachel mit
`data-selected="true"`), und die Bedienung entspricht dem Desktop-Ablauf mit denselben `data-testid`s.

**AC-3:** Given ein Nutzer ändert im Vergleich-Hub nur die Region When der Speichervorgang abgeschlossen
ist Then enthält der gesendete `PUT /api/compare/presets/{id}` ausschließlich `display_config: { region }`
(Name, Profil und alle weiteren Felder fehlen im Body), und beim anschließenden `GET` sind `name`,
`profil`, `location_ids`, `schedule` und `display_config`-Schwesterfelder unverändert; analog sendet eine
Namensänderung nur `{ name }` und ein Profilklick nur `{ profil }`.

**AC-4:** Given der Speicherversuch von Name oder Region scheitert (PUT antwortet 500 mit
`{"error":"Serverfehler"}`) When der Nutzer „Speichern" klickt Then erscheint unter dem Feld die
Fehlermeldung mit `data-testid="compare-hub-name-save-error"` bzw. `compare-hub-region-save-error` und
`role="alert"` (Text aus `error`, sonst „Speichern fehlgeschlagen"), das Eingabefeld bleibt offen und
enthält weiter den eingetippten Wert, und der serverseitig gespeicherte Wert ist unverändert.

**AC-5:** Given der Speicherversuch beim Profil scheitert (PUT antwortet 500) When der Nutzer eine andere
Profil-Kachel klickt Then erscheint `compare-hub-profil-save-error` unter der Kachelreihe, und die zuvor
gespeicherte Kachel bleibt als einzige mit `data-selected="true"` markiert.

**AC-6:** Given der Baustein `SubscriptionHeader` wird serverseitig (SSR) einmal mit den Props des
Vergleichs (`kind="vergleich"`, `testidPrefix="compare-hub"`, `profileOptions` = die vier Werte aus
`ACTIVITY_PROFILE_OPTIONS`, `regionMaxLength=60`) und einmal mit einem Trip-Prop-Satz (`kind="trip"`,
`testidPrefix="trip"`, andere `profileOptions` z. B. `trekking`/`skitour`, `regionMaxLength=80`) gerendert
When beide Ausgaben verglichen werden Then trägt jede Ausgabe genau die Präfix-testids und genau die
Optionen ihres Prop-Satzes (kein `compare-hub-…` im Trip-Satz und umgekehrt, Optionenzahl 4 bzw. die des
Trip-Satzes), und beide Ausgaben haben dieselbe Gerüststruktur (Überschrift, Region-Zeile, Kachelreihe) —
es gibt keine Markup-Verzweigung nach `kind`.

**AC-7:** Given der Baustein erhält keinen `actions`-Snippet, kein `meta`-Snippet und kein `badges`-
Snippet When er gerendert wird Then erscheint kein leerer Wrapper-Knoten für diese Slots im DOM (keine
Layout-Lücke), und mit übergebenem `actions`-Snippet erscheint dessen Inhalt genau einmal im Kopf.

**AC-8:** Given der Vergleich-Hub ist im Desktop-Viewport (1280 px) geöffnet When die Seite geladen ist
Then existiert jede der Kopf-testids (`compare-hub-name-edit-toggle`, `compare-hub-region-edit-toggle`,
`compare-hub-profil-option-wandern` usw.) **genau einmal** im DOM (`locator.count() === 1`) und ist
sichtbar; im Mobil-Viewport (375 px) ebenfalls genau einmal und sichtbar. Es gibt keine ausgeblendete
Zweitinstanz mehr.

**AC-9:** Given der Vergleich-Hub ist im Mobil-Viewport (375 px) geöffnet When die Seite geladen ist Then
steht die Eyebrow „Orts-Vergleich · Hub" über dem Namen, im Desktop-Viewport (1280 px) ist sie
nicht sichtbar, und die Unterzeile zeigt Region, Profil-Label (nur wenn bekannt, ohne führendes oder
doppeltes „ · ") und die Orte-Anzahl wie bisher (z. B. „Wandern · 3 Orte"); Desktop zeigt zusätzlich den
Breadcrumb „ORTS-VERGLEICHE / Hub".

**AC-10:** Given die Region-Eingabe im Vergleich-Hub ist offen When der Nutzer mehr als 60 Zeichen
tippt Then lässt das Feld nur 60 Zeichen zu (`maxlength="60"`, aus `regionMaxLength`); die Unterzeile
(Profil-Label, Orte-Anzahl) ist während der Bearbeitung ausgeblendet wie bisher.

**AC-11:** Given Nutzer A besitzt einen Ortsvergleich und Nutzer B ist mit eigener Sitzung angemeldet
When B `PUT /api/compare/presets/{id von A}` mit genau dem Rumpf sendet, den der Hub-Kopf schickt
(nur `{ "name": "fremd" }`) Then ist A's Preset-Datei danach byte-gleich zu vorher und A liest beim
anschließenden GET weiterhin seinen alten Namen; welchen Status B erhält (404 oder eine Antwort, die
nur B's eigenen Namensraum betrifft), ist nicht Teil der Zusicherung — entscheidend ist, dass A's Daten
unberührt bleiben. Nutzer A kann sein Preset über den Hub-Kopf weiterhin ändern. (Regressionsnachweis
des bestehenden Backend-Schutzes mit zwei verschiedenen Nutzern; der Baustein enthält keinen eigenen
Netzwerkzugriff und kann die `user_id` aus dem Auth-Kontext nicht umgehen.)

**AC-12:** Given die bestehenden Playwright-Spezifikationen `compare-hub-name-region-profil`,
`compare-hub-inline-edit`, `compare-hub-save-chip` und `compare-hub-fidelity-s8c` When sie nach der
Umstellung unverändert (ohne Änderung an den Spec-Dateien) gegen den CI-Stack laufen Then sind alle
grün; insbesondere die Layout-Zusicherungen aus `compare-hub-fidelity-s8c` (Breadcrumb-Krümel, mobile
Eyebrow, Profil-Label „Wandern" in der Desktop-Unterzeile) bleiben erfüllt. **Einzige erlaubte
Ausnahme (PO-Entscheid 2026-10-03):** in `compare-hub-fidelity-s8c.spec.ts` (Test „Unterzeile zeigt
"Wandern" statt "wandern"") darf der Selektor `.hidden.desktop\:block` — der nur wegen der doppelten
Desktop/Mobil-Kopie nötig war, die AC-8 abschafft — auf den einen Kopf (z. B. `[data-kind="vergleich"]`)
eingegrenzt werden. Prüfaussage, Viewport (1280 px) und erwarteter Text „Wandern" bleiben unverändert.
Ausgenommen sind ferner bekannte, vom Kopf unabhängige Rote, die mit dem Stand vor der Umstellung
genauso scheitern (Nachweis per Vorher-Lauf).

## Test-Plan

**Kern (deterministisch, `node --test`):** Das Frontend läuft über `node --import ./test-lib-loader.mjs
--experimental-strip-types --experimental-test-module-mocks --test` (kein Vitest). Bausteintests folgen
dem SSR-Harness-Muster von `shared/__tests__/alarme_tab_premium_sms_channel_row_render.test.ts`
(`register` des SSR-Hooks `frontend/test-svelte-ssr-hooks.mjs`, `render` aus `svelte/server`, Prüfling
relativ zur Testdatei aufgelöst, kein Mock, kein Datei-Grep).

| Testdatei (nach Verhalten benannt) | Deckt |
|---|---|
| `shared/__tests__/subscription_header_kontextneutral.test.ts` | AC-6 (zwei Prop-Sätze, Präfix und Optionen je Satz, gleiche Gerüststruktur), AC-7 (keine leeren Slot-Wrapper, `actions` genau einmal), AC-10 (`maxlength` aus Prop) |
| `shared/__tests__/subscription_header_einmal_gerendert.test.ts` | AC-8 (im SSR-Output jede Kopf-testid genau einmal; Namens-Knopftexte beider Viewports im selben Knopf, kein zweites Kopf-Markup) |

SSR führt weder `onMount` noch Klick-Handler aus; die Speicher- und Fehlerpfade (AC-1 bis AC-5) werden
deshalb **nicht** im SSR „bewiesen", sondern im E2E (Nachweis aus Nutzersicht). Mutationsgegenprobe für
den Adversary (Pflicht): (a) `if kind === 'trip'`-Zweig ins Markup einbauen ⇒ AC-6 muss rot werden;
(b) in der Seite den PUT-Body auf `{...currentPreset, name}` verfälschen ⇒ AC-3 muss rot werden;
(c) Fehlerfall: `catch` leeren ⇒ AC-4/AC-5 rot; (d) Desktop-Block wieder doppeln ⇒ AC-8 rot.

**Live-E2E (Playwright, CI-Stack/Staging):** Neue Datei `frontend/e2e/compare-hub-kopf-einmal.spec.ts`
für AC-2 (Mobil, alle drei Felder + Reload), AC-3 (Mitschnitt des PUT-Rumpfs per `page.route` je Feld:
der Rumpf enthält genau den einen Schlüssel `name` bzw. `display_config.region` bzw. `profil` — exakte
Schlüsselmenge, nicht nur „enthält"; danach GET des Presets: übrige Felder wie vor dem Edit), AC-5
(Profil-Fehler per `page.route`), AC-8 (Zählung `count() === 1` in beiden Viewports), AC-9
(Eyebrow/Breadcrumb je Viewport) und AC-10 (Region-Eingabe öffnen ⇒ `maxlength="60"` greift beim Tippen
von 61 Zeichen, und die Unterzeile mit Profil-Label und Orte-Anzahl ist während der Bearbeitung nicht
sichtbar, nach Abbrechen wieder sichtbar). AC-1, AC-3 (Body-Prüfung
per `page.route`-Mitschnitt oder `request`-Listener), AC-4 laufen bereits teilweise in
`compare-hub-name-region-profil.spec.ts` (AC-1, AC-4, AC-7 dort) und werden dort unverändert
mitgefahren (AC-12). AC-11 als Go-Handler-Test mit zwei Nutzern: Der bestehende
`TestComparePresetPutServerFields_TenantIsolation` (`internal/handler/compare_preset_put_server_fields_test.go:167`)
deckt nur den Spiegelfall mit vollem Rumpf ab (A schreibt, B's gleichnamige Datei bleibt gleich). Neu
kommt ein Fall mit dem minimalen Kopf-Rumpf `{ "name": … }` von B gegen A's ID hinzu, der A's Datei
byte-genau vergleicht. Alle E2E-Spezifikationen arbeiten gegen
Wegwerf-Presets, nie gegen Daten des PO.

**Verifikation nach Merge:** Staging-Auto-Deploy abwarten, `compare-hub-*`-Specs gegen Staging, Hub
von Hand in beiden Viewports ansehen. Kein Mail-Renderer berührt ⇒ kein Mail-Validator im Umfang.

## Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| **Layout-Regression** der Hub-Fläche (`compare-hub-fidelity-s8c`: Breadcrumb, Eyebrow, Unterzeile) | Seiten-Chrome (Breadcrumb, BackLink, Aktionsspalte, Kebab) bleibt unverändert in der Seite; AC-9 und AC-12 bewachen die Anordnung; Screenshot-Vergleich vor/nach in beiden Viewports |
| **Mobil-Anordnung** weicht stark von Desktop ab (Aktionsknopf neben dem Namen, 44-px-Tippflächen, Knopfbeschriftung) | Ein Markup mit responsiver Klasse; bei starker Abweichung `{#snippet}` im selben Baustein, nie eine zweite Komponente (Entscheidung 5) |
| **Datenverlust durch Spread der Seiten-Kopie** (Fehlerklasse #2375/#2381) | `onSaveField` sendet nur das geänderte Feld; AC-3 und Mutationsgegenprobe (b) |
| **Veralteter Resync in `CompareTabs`** nach dem Speichern | `currentPreset` wird nach Erfolg mit neuer Objekt-Referenz ersetzt (Entscheidung 3) |
| **Doppel-testids** bleiben unbemerkt, weil die E2E `:visible` filtert | AC-8 zählt ohne `:visible` |
| **Parallele Arbeit #1433 / PR #2486** an Trip-Dateien | **Eingetreten:** #2486 hat die Kopf-Speicherfunktionen in `routes/compare/[id]/+page.svelte` geändert. S1 wurde nach dem Merge auf der main-Fassung neu aufgebaut, der #1433-Konfliktschutz bleibt vollständig erhalten (Nachtrag zu Entscheidung 3); die Trip-Seite folgt in S2 |

## Out of Scope

Alles Folgende gehört weiterhin zu Issue #2284 bzw. zum Epic und folgt in eigenen Scheiben/Tickets — es
ist hier **nicht** abgespalten, sondern zeitlich danach:

- **S2 (#2284):** Trip-Kopf auf den Baustein (Region inline mit `trip-region-*`-testids, Aktivität aus dem
  Etappen-Reiter in den Kopf) und Umzug des Speicher-Chips in den Baustein für beide Hubs — nach Merge
  von PR #2486.
- **S3 (#2284):** Rückbau der Trip-Hüllen `AlarmeScheduleTab` und `BriefingScheduleTab` samt totem Knopf.
- **S4 (#2284):** ein gemeinsamer `VTLaufzeit`-Baustein.
- **S5 (#2284):** ein Ladeweg für den `metricsCatalog` in beiden Hubs.
- **S6 (#2284):** explizites `context=` an allen Mounts samt Mount-Wächter.
- **#2278:** Aktionsmodell (Kebab/Lifecycle-Aktionen). S1 liefert nur den leeren `actions`-Slot.
- **#2287** (Reiter-Kennungen) und **#2288** (Drag & Drop): folgen nach #2284.

## Betroffene Dateien und Umfang

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | CREATE, ca. +230 |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY, ca. −150 netto (Markup weg, drei Speicherfunktionen zu einer `onSaveField`) |
| `frontend/src/lib/components/shared/__tests__/subscription_header_*.test.ts` | CREATE (zählt nicht gegen das LoC-Limit der Produktiv-Dateien) |
| `frontend/e2e/compare-hub-kopf-einmal.spec.ts` | CREATE |

Schätzung Produktivcode: +~230 / −~150, 2 Dateien. Risiko MEDIUM (Umbau einer häufig genutzten Fläche,
geschützt durch bestehende E2E mit unveränderten testids). Passt in das LoC-Limit von 250 je Workflow.

## Abhängigkeiten

| Entity | Type | Purpose |
|--------|------|---------|
| `ACTIVITY_PROFILE_OPTIONS` / `presetProfileLabel` (`lib/types.ts`) | Upstream | Profil-Optionen und Profil-Label des Vergleichs, als Props an den Baustein |
| `Btn`, `PencilIcon` | Upstream | Bedienelemente im Kopf |
| Go `UpdateComparePresetHandler` | Upstream (unverändert) | Speichert nur das gesendete Feld, Mandantentrennung |
| `routes/compare/[id]/+page.svelte` | Downstream | Einziger Nutzer in S1; ab S2 zusätzlich `routes/trips/[id]/+page.svelte` bzw. `TripHeader` |
| `docs/context/feat-2284-hub-kopf-paritaet.md` | Kontext | Analyse und Scheibenplan |
| `docs/specs/modules/feat_1273_s2_compare_hub_name_region_profil.md` | Kontext | Bestehende Verhaltens-Spec des Compare-Kopfs, deren ACs gültig bleiben |

## Changelog

- 2026-10-03: Entscheidung 3 um den Konfliktausgang (`schliessen`-Callback) ergänzt — Integration von #1433 / PR #2486
- 2026-10-03: AC-12 präzisiert — Selektor-Eingrenzung in `compare-hub-fidelity-s8c` erlaubt (Widerspruch zu AC-8 aufgelöst, PO-Entscheid)
- 2026-10-03: Initial spec created (Scheibe S1 von #2284, Epic #2345 Etappe P2)
