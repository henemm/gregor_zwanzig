---
entity_id: rework_2837_s1_hub_kopf
type: feature
created: 2026-11-06
updated: 2026-11-06
status: draft
version: "1.0"
workflow: rework-2837-hub-kopf-anlege-rahmen
tags: [epic-2345, trip-compare-teilung, hub-kopf, shared, paritaet, frontend-only, dod-2]
---

# Scheibe S1: Hub-Kopf für Trip und Ortsvergleich als ein Baustein (Issue #2837, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Der Kopf der Detailseite (`/trips/[id]` und `/compare/[id]`) ist heute zweimal verschieden gebaut. Der Trip hat eine eigene Leiste mit orangem „Senden", einem Status in einer eigenen Zeile und orangen Reiter-Zählern; der Ortsvergleich hat eine Leiste „ORTS-VERGLEICHE / Hub", schwarzes „Senden" neben dem Titel, den Status als Badge am Titel, ein horizontales Kebab-Symbol auf dem Handy und graue Reiter-Zähler. Das widerspricht der PO-Vorgabe „möglichst viel Code teilen" (ADR-0097) und ist die letzte offene Abnahme von Epic #2345 (DoD-2 Oberfläche).

Diese Spec legt **einen** geteilten Baustein `shared/hub-kopf/HubKopf.svelte` mit `context="route"|"vergleich"` an. Er trägt die Leiste (Breadcrumb bzw. mobiler Zurück-Link, Senden, Kebab, Meldungen) und bindet den bereits geteilten `SubscriptionHeader` ein. Beide Detailseiten benutzen ihn. Fachlich Verschiedenes kommt über Snippets herein (geschlossene Whitelist, siehe unten).

**Zuschnitt (fest entschieden):** Das Epic-Ticket #2837 umfasst Hub-Kopf **und** Anlege-Rahmen. Wegen des Scope-Deckels (250 Zeilen Code je Workflow) und der parallelen Arbeit #2792 S1c-4b in `TripNewEditor`/`CompareNewEditor` wird in zwei Scheiben geliefert:

- **S1 (diese Spec): Hub-Kopf**, konfliktfrei zu #2792 (die Editoren werden nicht berührt).
- **S2 (eigene Spec, Vorbedingung: #2792 S1c-4b gemergt): Anlege-Rahmen** (`/trips/new`, `/compare/new`). Hier nur als Ausblick benannt, **keine ACs**. Ebenfalls außerhalb: Aktivitätsprofil-Auswahl (#2792) und die Randbefunde des Issues (Badge „ALLE KANÄLE" abgeschnitten, Begriffe Wertebereiche/Ideal-Werte, Testdaten „Validator-1025 Compare").

Das Issue #2837 bleibt offen, bis auch S2 geliefert ist (Issue erst schließen, wenn alles erledigt ist).

## Entscheidungen zur Freigabe

Zur Freigabe in einfachem Deutsch. „Vorher" ist, was der Nutzer heute sieht, „Nachher" nach dem Umbau. Wo es nur um Trip oder nur um Ortsvergleich geht, steht es dabei; sonst gilt es für beide.

| Nr. | Thema | Vorher | Nachher | Warum |
|---|---|---|---|---|
| 1 | **„Senden"-Knopf: Farbe** | Beim Trip orange, beim Ortsvergleich schwarz | Bei beiden **schwarz** | Weiße Schrift auf dem Orange der Seite hat nur ein Kontrastverhältnis von 4,34 zu 1 und fällt damit unter die Lesbarkeits-Grenze von 4,5 zu 1 (WCAG-AA). Schwarz erreicht rund 15 zu 1. Außerdem ist Schwarz bei Hauptaktionen schon heute der Normalfall im Produkt (33 Knöpfe schwarz, 13 orange). Orange bleibt für „Weiter" und für Aktiv-Zustände. Das folgt Ihrem Leitprinzip „Hoher Kontrast gewinnt gegen weiche Optik". |
| 2 | **„Senden": Lage** | Trip: oben in der Leiste neben dem Menü; Ortsvergleich: neben der Überschrift | Bei beiden **in der Leiste ganz oben**: links der Pfad, rechts „Senden", Menü (drei Punkte) und Meldungen | Die Leiste wandert nicht, wenn der Titel lang ist und umbricht. |
| 3 | **Ortsvergleich im Entwurf** | „Setup abschließen" steht neben der Überschrift | „Setup abschließen" steht **genau an der Stelle von „Senden"** | Gleiche Lage wie beim Trip. Das ist bewusst ein fachlicher Unterschied: ein Entwurfs-Vergleich wird erst fertig eingerichtet, bevor man senden kann. Beim Trip im Entwurf ist „Senden" gesperrt. |
| 4 | **Pfad oben (Breadcrumb)** | Trip: „Trips / Kürzel oder Name". Ortsvergleich: „ORTS-VERGLEICHE / Hub" (nur am Computer) | Trip: „Trips / Kürzel oder Name". Ortsvergleich: „Orts-Vergleiche / Name des Vergleichs". Der vordere Teil ist bei beiden ein Link zur Liste. Auf dem Handy bei beiden ein Zurück-Pfeil | „Hub" sagt dem Nutzer nichts; der Name sagt, wo man ist. Der Eintrag „Hub" entfällt. |
| 5 | **Status (Aktiv, Pausiert, Entwurf …)** | Trip: eigene Zeile unter dem Kopf („AKTIV, läuft seit Tag 1"). Ortsvergleich: kleines Schild (Badge) neben dem Titel | Bei beiden **Schild neben dem Titel**. „Tag x von y" bzw. die Laufzeit steht daneben | Eine Zeile weniger, überall derselbe Platz. Datum, Kürzel und km/Höhenmeter beim Trip sowie Orte-Anzahl beim Ortsvergleich bleiben, weil sie fachlich verschieden sind. |
| 6 | **Menü (drei Punkte) auf dem Handy** | Trip: Punkte senkrecht; Ortsvergleich: waagerecht | Bei beiden **senkrecht** | Überall sonst im Produkt sind sie senkrecht. |
| 7 | **Zähler an den Reitern** (kleine Zahl hinter dem Reiter-Namen) | Trip: orange gefüllt; Ortsvergleich: grau | Bei beiden **grau** | Eine kleine orange Zahl (12 Pixel) fällt bei der Lesbarkeit durch; grau auf hellem Grund erreicht rund 4,7 zu 1 und besteht. Orange bleibt als Unterstreichung des aktiven Reiters. |

Was fachlich verschieden bleibt (geschlossene Liste, alles andere wird gleich): Datum, Kürzel, km und Höhenmeter, „Tag x von y" bzw. Laufzeit, die Kennzahl-Kacheln auf dem Handy (Trip), die Anzahl der Orte (Ortsvergleich) und die Entwurfs-Regel aus Zeile 3.

**Abgelöst wird dadurch:** Zwei frühere Entscheidungen aus #2284, nämlich „Seiten-Chrome bleibt in der Seite" (Breadcrumb, Zurück, Senden, Menü gehören nicht in den Baustein) und „Status und Meta bleiben außerhalb" (Trip-Kopf bleibt eine eigene Hülle). Sie stammen aus der Zeit, als der Kopf erstmals geteilt wurde; das Epic verlangt jetzt die volle Teilung. Siehe Abschnitt „Ablösung".

## Source

- **Neu (Pfade relativ zu `frontend/src/lib/components/`):** `shared/hub-kopf/HubKopf.svelte` (und, falls für die Testbarkeit nötig, `shared/hub-kopf/hubKopfModell.ts` für die reine Ableitung Breadcrumb-Text und Senden-Zustand je `context`). **Neue Dateien ausschließlich unter `shared/`** (Pendant-Sperre, `docs/reference/gates_und_ratschen.md`).
- **Geändert:**
  - `frontend/src/routes/trips/[id]/+page.svelte` (Leiste `:311-357` und zugehöriges CSS `:425-467` wandern in den Baustein; `<TripHeader>` `:359` bleibt als fachliche Hülle).
  - `frontend/src/routes/compare/[id]/+page.svelte` (Breadcrumb und Kopf `:359-397`, Aktionsspalte `:401-424` ersetzt).
  - `trip-detail/TripHeader.svelte` (Status-Zeile `:145-150` raus, Status wandert ins `badges`-Snippet; totes CSS `.header-actions`/`.briefing-msg` `:217-226` raus; Meta km/Hm und Mobil-Kacheln bleiben).
  - `molecules/SubscriptionKebab.svelte` (mobiler vertikaler Button wird hineingehoben; `MoreHorizontalIcon` entfällt in der Compare-Seite).
  - `mobile/MTabBar.svelte` (eigene neutrale Badge-Variante als Standard, **nicht** über `size`), `trip-detail/TripTabs.svelte` `:185-190` und `compare/CompareTabs.svelte` `:678-684` rufen dieselbe Variante.
  - i18n `lib/i18n/messages/{de,en}/vergleich.json`, `trip.json` (Breadcrumb-Elternteil; `vergleich.hub.krumel` entfällt).
  - Doku: `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md` (neu), `docs/adr/README.md` (Index-Eintrag), `docs/reference/design_system.md:64`, beide #2284-Specs („Abgelöst durch"-Hinweis).
- **Unverändert wiederverwendet:** `shared/subscription-header/SubscriptionHeader.svelte` (Snippets `eyebrow`, `namePrefix`, `badges`, `actions`, `meta`; `titleSize`), `atoms/BackLink`, `ui/btn/Btn.svelte`, `TripStatusBadge`, `CompareStatusPill`.

> **Schicht-Hinweis:** ausschließlich **Frontend** (SvelteKit). Kein Go-, kein Python-Code, kein Datenmodell, kein neuer Endpunkt.

> **Trip/Ortsvergleich-Teilung:** Kern dieser Spec. Der Baustein liegt unter `shared/hub-kopf/` mit Parameter `context="route"|"vergleich"` (Vorbild `shared/hub-uebersicht/HubUebersicht.svelte`, Spec `feat_2682_hub_uebersicht_geteilt.md`). Es wird keine Komponente mit Pendant unter `trip-detail/` oder `compare/` neu angelegt; die Pendant-Sperre löst nicht aus.
> **Mandantentrennung:** reine Oberfläche, kein datenbewegender Endpunkt. Der Senden-Dialog und die Kebab-Aktionen bleiben unverändert an die Seite gebunden (`onSend` und Aktionen kommen als Props, der Baustein ruft keine API selbst). Ein Zwei-Nutzer-Test entfällt deshalb; die bestehenden Aktions-E2E laufen unverändert.
> **Kanäle:** nicht betroffen. „Senden" öffnet wie bisher nur den Sende-Dialog (`aktionsmodell_seiten_bindung.test.ts:107-118`) und versendet selbst nichts.

## Entscheidungen (Tech Lead, am Code gemessen)

1. **Ein Baustein, `context` nur als Textwahl und Datenmarke.** Ein Markup ohne `kind`-Zweig im Aufbau; `context` wählt Breadcrumb-Elternteil, Eltern-Link, `data-kind` und Testid-Präfix. Das `status`-Snippet des Bausteins füllt das `badges`-Snippet des `SubscriptionHeader`.
2. **Senden `Btn variant="primary"`, Lage in der Leiste.** Beim Trip bisher `accent` (`trips/[id]/+page.svelte:322-330`, gesperrt bei draft/archived), beim Vergleich schon `primary` (`compare/[id]/+page.svelte:406-408`). Gemessene Kontraste: Weiß auf `--g-accent #c45a2a` 4,34:1 (AA-Schwelle 4,5:1 für kleinen Text verfehlt), Ink `--g-ink #1a1a18` auf Papier etwa 15:1. `Btn primary` 33x, `accent` 13x im Produkt. Testid bleibt `subscription-hub-send`.
3. **Draft-Logik bleibt fachlich verschieden, Lage gleich.** Vergleich-draft: „Setup abschließen" (`Btn primary`, bisher `compare/[id]/+page.svelte:402-403`) sitzt auf dem Platz von Senden. Trip: Senden gesperrt bei draft/archived. Ein „Setup abschließen"-Pendant für Trip-Entwürfe ist Produktfrage und **nicht** Teil dieser Scheibe.
4. **Breadcrumb aus dem Katalog.** Trip: `Trips / {shortcode ?? name}`; Vergleich: `Orts-Vergleiche / {name}`. Elternteil ist Link (Trips-Liste bzw. Vergleichs-Liste, Schlüssel `listen.trips.titel` / `listen.vergleiche.titel` aus `listen.json:5,9`, in de und en vorhanden, geprüft 2026-11-06), Kind ist kein Link. Mobil bei beiden `BackLink` (bisher Trip :314, Vergleich :364). Der Krümel „Hub" (`vergleich.hub.krumel`, `vergleich.json:36`) und die Mobil-Eyebrow „Orts-Vergleich · Hub" (`vergleich.json:37`) entfallen.
5. **Status als Badge in der Titelzeile für beide.** `TripStatusBadge` (`TripStatusBadge.svelte:16-23,39`) wandert in das `badges`-Snippet; `daysLabel` („Tag x von y") steht als fachlicher Zusatz daneben. Die Status-Zeile in `TripHeader` (:145-150) entfällt samt totem CSS. Vergleich unverändert (`CompareStatusPill` + Laufzeit).
6. **Kebab mobil vertikal.** Der mobile Button mit `EllipsisVerticalIcon` (`trips/[id]/+page.svelte:331-342`) wird in `SubscriptionKebab` gehoben und löst den horizontalen Compare-Button (`compare/[id]/+page.svelte:413-423`) ab. Beide Seiten reichen nur noch Aktionen an den Baustein.
7. **Reiter-Zähler neutral.** Eigene Badge-Variante in `MTabBar` (neutral `--g-paper-deep` mit `--g-ink-3`, nachgerechnet etwa 4,7:1, besteht AA). Sie wird **nicht** über `size="sm"` gesteuert (Größe und Farbe sind verschiedene Achsen). Der gefüllte Accent-Zähler (`MTabBar.svelte:134-143`) entfällt; Accent bleibt Aktiv-Unterstrich.
8. **Fachlich-verschieden als geschlossene Whitelist:** Datum (eyebrow), Shortcode (namePrefix), km/Hm (meta), „Tag x von y" bzw. Laufzeit, Mobil-Kennzahl-Kacheln (nur Trip), Orte-Anzahl (nur Vergleich), Draft-Logik (Entscheidung 3). Alles andere ist ein Markup. Titelgröße ist **keine** Whitelist-Ausnahme: beide nutzen `titleSize={38}` (der Prop existiert bereits in `SubscriptionHeader`, Vergleich heute 30 px).
9. **Region** `{region || '—'}` ist im geteilten `SubscriptionHeader:135` schon gleich; kein Code, nur Nachweis im Screenshot-Paar.
10. **Testids stabil.** `subscription-hub-send`, `trip-detail-h1`, `trip-detail-status-badge`, `trip-detail-breadcrumb-bar`, `compare-hub-*` bleiben. Neue gemeinsame Testids über `testidPrefix` (z. B. `hub-kopf-leiste`, `hub-kopf-breadcrumb`, `hub-kopf-status`); `HUB_SEL` in `frontend/e2e/helpers.ts` wird darauf zusammengeführt statt je Art verdoppelt.

## Ablösung

Dieser Umbau hebt zwei ausdrückliche Entscheidungen früherer Specs auf (nie still):

- **`feat_2284_s1_subscription_header.md` Entscheidung 6** („Seiten-Chrome bleibt in der Seite", `:94`): Breadcrumb, `BackLink`, Senden-Knopf, Kebab und mobiler Weitere-Aktionen-Knopf gehören ab jetzt in den geteilten `HubKopf`. Das „Aktionsmodell → #2278" bleibt gültig (Senden öffnet nur den Dialog; Aktionen kommen als Props).
- **`feat_2284_s2_trip_kopf.md` Entscheidungen 7 und 8** (`:116-119`): „`TripHeader` bleibt Hülle" gilt weiter für Datum, Shortcode, km/Hm und Mobil-Kacheln; **aufgehoben** ist „Status und Meta außerhalb des Bausteins" für den Status (kommt als Badge in `badges`).

Lieferbestandteile (Teil der Umsetzung, nicht dieser Spec-Datei):

1. Neues **ADR `docs/adr/0110-hub-kopf-und-anlege-rahmen-ein-baustein.md`** (0110 ist auf `origin/main` frei; Abschnitt „Löst ab": die beiden oben genannten Entscheidungen; „Schreibt fort": ADR-0097). Es gilt auch für den Anlege-Rahmen (S2), damit S2 kein zweites ADR braucht.
2. Eintrag in `docs/adr/README.md` (Index-Konsistenz, `tests/test_adr_index_drift.py`).
3. „Abgelöst durch ADR-0110 / #2837"-Hinweis in beiden alten Specs. `feat_2284_s2` ist ggf. eingefroren (`frozen_spec_sha256`): dann Vermerk im Changelog/Known Limitations wie bei `feat_2682` AC-19 und nicht an der gesperrten Kopftabelle.
4. `docs/reference/design_system.md:64` nachziehen: `--g-accent` = „Weiter / Aktiv-Zustand / KI-Vorschlag / Logo-Blitz", **Hauptaktion = Ink (`Btn primary`)**; Begründung Kontrast (`:22`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/subscription-header/SubscriptionHeader.svelte` | component | Titelblock (Name, Region, Profil, SaveIndicator, `badges`-Slot), bereits kontextneutral |
| `molecules/SubscriptionKebab.svelte` | component | Kebab-Menü; erhält den mobilen vertikalen Button |
| `mobile/MTabBar.svelte` | component | Reiterleiste; erhält neutrale Badge-Variante |
| `atoms/BackLink`, `ui/btn/Btn.svelte` | component | Zurück-Link, Senden |
| `trip-detail/TripStatusBadge.svelte`, `compare/CompareStatusPill.svelte` | component | Status-Badge je Art (fachlich eigene Inhalte, gleicher Platz) |
| `lib/i18n` Katalog (`trip.json`, `vergleich.json`, `listen.json`) | module | Breadcrumb-Texte de und en |
| `frontend/e2e/helpers.ts` (`HUB_KINDS`, `HUB_SEL`) | test helper | Paritäts-Schleifen |

## Scope (Estimated Scope)

- **Dateien:** 1 neu (HubKopf, optional +1 Modell) und ca. 8 geänderte Produktdateien (2 Seiten, TripHeader, SubscriptionKebab, MTabBar, TripTabs, CompareTabs, 2 i18n-Kataloge), dazu ca. 8 Test-/E2E-Dateien, 4 Doku-Dateien (ADR, README, design_system, 2 Specs).
- **LoC (Produktcode ohne Docs und i18n), ehrlich geschätzt:** HubKopf ca. +170, Seiten-Umbau ca. +40/-130 (Leiste/Aktionsspalte/CSS raus), TripHeader ca. -45, SubscriptionKebab ca. +25, MTabBar ca. +25/-10, Tabs ca. +/-6. Brutto ca. +270/-190, **netto ca. +80**, geänderte Zeilen insgesamt ca. 460. Je nachdem, ob das Limit netto oder brutto zählt, liegt die Scheibe unter bzw. klar über 250. **Vorgesehen ist `loc_limit_override 450`** (Brutto-Rundung mit Puffer; Begründung: überwiegend Verschieben vorhandener Zeilen in den Baustein, Verhaltensumbau gering; ein weiteres Abspalten würde den Baustein halbiert zurücklassen und die Parität erst später herstellen). Kein weiteres Abspalten über S2 hinaus.
- **Effort:** medium-high. **Risiko:** MEDIUM (nur Oberfläche, aber viele Zusicherungen und E2E verankern heute die Divergenz).

## Implementation Details

Reihenfolge, damit jeder Zwischenstand grün bleibt:

1. **Kebab und Zähler zuerst** (kleinster, unabhängiger Umbau): mobiler Button in `SubscriptionKebab`; `MTabBar` neutrale Variante, Tabs angeglichen.
2. **`HubKopf`** anlegen: Props `context`, `parent` (Label + Href), `crumb`, `sendLabel`, `onSend`, `sendDisabled`, `sendMode` (`'senden' | 'setup'`, `'setup'` nur Vergleich-draft), Kebab-Daten, `titleSize`, `testidPrefix`, Durchreichung der `SubscriptionHeader`-Props; Snippets `status`, `eyebrow`, `namePrefix`, `meta`, `meldungen`. Mobil Leiste mit `BackLink`, Desktop mit Breadcrumb, beide Senden in 44 px Touch-Höhe.
3. **Trip-Seite** auf `HubKopf` umstellen, `TripHeader` verkleinern (Status ins Snippet, totes CSS raus).
4. **Vergleich-Seite** auf `HubKopf` umstellen (Aktionsspalte entfällt), „Hub"-Krümel und Mobil-Eyebrow entfernen.
5. **i18n** de und en, Katalogtests (`keine_hartkodierten_nutzertexte.test.ts`) grün.
6. **ADR, Index, Doku** wie unter „Ablösung".

**i18n-Regeln (ADR-0104):** neue und verschobene Texte (Breadcrumb-Elternteil, Status-Zusatz, Aria-Labels des Kebab) nur über den Katalog, **de und en**; „Hub"-Krümel entfällt. Protokoll-Token (`sms_code`, `compact_label`, Kürzel) werden nie übersetzt; das Trip-Kürzel im Breadcrumb ist Nutzerdatum, kein Katalogtext.

## Expected Behavior

- **Input:** `context`, Trip bzw. Vergleich (Name, Kürzel, Status, Region, Profil), Sende- und Kebab-Aktionen als Props.
- **Output:** gleiche Leiste und gleicher Titelblock für beide Arten; sichtbarer Unterschied nur in der Whitelist (Entscheidung 8).
- **Side effects:** keine. „Senden" öffnet nur den Dialog; Kebab-Aktionen bleiben unverändert an die Seiten gebunden.

## Test Plan

### Divergenz-verankernde Tests: nicht löschen, umdrehen

| Test | Heute erzwungen | Neue (umgedrehte) Zusicherung |
|---|---|---|
| `frontend/e2e/hub-tab-bar.spec.ts` HT-8 `:202-223` | Badge-Optik je Art verschieden (Trip orange, Vergleich grau) | Per `HUB_KINDS`: Badge-Optik **gleich und neutral** (Hintergrund `--g-paper-deep`, Schrift `--g-ink-3`, kein Accent-Füllfarbton), bei 1440 und 390 px |
| `routes/compare/__tests__/bug_589_breadcrumb_links.test.ts` | „ORTS-VERGLEICHE" ist Link, „Hub" ist kein Link | Elternteil „Orts-Vergleiche" bleibt Link, Kind ist der **Vergleichsname** und kein Link; kein Krümel „Hub" |
| `trip-detail/TripHeader.issue699.test.ts` | keine zweite Breadcrumb im `TripHeader` | bleibt wahr (die Leiste liegt im `HubKopf`); zusätzlich: genau **eine** Breadcrumb im Seiten-Render |
| `frontend/e2e/issue-336-status-dedup` | Status als eigene Zeile unter dem Kopf, genau einmal | Status genau **einmal**, als Badge in der Titelzeile (`status`-Snippet); keine zweite Statuszeile |
| `frontend/e2e/hub-kopf-aufbau.spec.ts` KA-7 `:502/:514`, KA-10 `:442`, Senden `:346/:407` | Aufbau und Senden-Lage/Farbe je Art | Per `HUB_KINDS`: Senden in der Leiste, gleiche Position (Toleranz wenige px) und Hintergrundfarbe `--g-ink`; Vergleich-draft: „Setup abschließen" auf demselben Platz; Kebab-Symbol vertikal (mobil) |
| `shared/__tests__/subscription_header_einmal_gerendert.test.ts` (genau ein `<header class="trip-header">` `:229`) | genau ein Kopf pro Seite | bleibt: genau ein `SubscriptionHeader`-Render je Seite, jetzt **über** `HubKopf` |
| `shared/__tests__/aktionsmodell_seiten_bindung.test.ts` (`:107-118`, `:266-267`) | Senden öffnet nur Dialog; Draft-Bedingung Vergleich | bleibt; Pfad der Prüfung folgt `HubKopf`, Draft-Bedingung (Vergleich „Setup abschließen" vs. Trip gesperrt) bleibt wörtlich geprüft |
| `shared/__tests__/subscription_header_kontextneutral.test.ts`, `subscription_header_bedienlogik.test.ts` | Baustein kontextneutral | bleibt; kommt dasselbe für `HubKopf` (kein `context`-Zweig im Markup außer Textwahl) |
| `frontend/e2e/helpers.ts` `HUB_SEL` (`HUB_KINDS` `:609`, `HUB_SEL` `:617`) | je Art eigene Selektoren | gemeinsame Selektoren über Präfix; `ANLEGE_SEL` bleibt für S2 unberührt |

Weitere zu prüfende Tests (Zuordnung in Phase 4): `trip-detail/TripHeader.spacing`, `TripHeader.mobile-metrics`, E2E `trip-header-btn-migration`, `issue-302-trip-detail-redesign`, `issue-616-trip-one-surface`, `trip-detail-actions`, `hub-kopf-bearbeiten.spec.ts`. Jede Umhängung wird im Commit benannt, keine Zusicherung wird gelockert.

### Neu (TDD RED, aus Nutzersicht)

- [ ] E2E `HUB_KINDS`-Schleife bei 1440 und 390 px: Lage und Farbe von Senden gleich, Status-Badge in der Titelzeile, Kebab-Symbol vertikal, Zähler neutral, Breadcrumb-Aufbau (Elternteil Link, Kind kein Link).
- [ ] Mutation (Pflicht): Senden im Trip wieder auf `accent` ⇒ E2E rot; Zähler wieder `accent` ⇒ rot; Status wieder in eigene Zeile ⇒ rot. Eine Verfälschung, die kein Test fängt, ist ein Finding.
- [ ] Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`: neue `*compare*.spec.ts`-Dateien tragen `HUB_KINDS`-Schleife.
- [ ] Quelltext-grep zählt **nicht** als Verhaltensnachweis (Ausnahme `# doc-compliance-test` für die Doku-Punkte AC-12).

## Acceptance Criteria

- **AC-1:** Given ein aktiver Trip und ein aktiver Ortsvergleich im Desktop-Fenster (1440 px) / When der Nutzer jeweils die Detailseite öffnet / Then sitzt „Senden" bei beiden an derselben Stelle in der Leiste ganz oben rechts neben dem Menü, mit schwarzem Hintergrund und weißer Schrift, und kein „Senden" steht mehr neben der Überschrift.
  - Test: E2E `HUB_KINDS`-Schleife bei 1440 px: Position (Leiste, gleiche Zeile wie Breadcrumb) und berechnete Hintergrundfarbe von `subscription-hub-send` gleich für beide Arten.
- **AC-2:** Given Trip und Ortsvergleich auf dem Handy (390 px) / When der Nutzer die Detailseite öffnet / Then steht in der Leiste links der Zurück-Pfeil und rechts „Senden" (schwarz, mindestens 44 px hoch) und das Menü, bei beiden an derselben Stelle.
  - Test: E2E `HUB_KINDS`-Schleife bei 390 px: gleiche Lage, gleiche Farbe, Höhe der Senden-Fläche mindestens 44 px.
- **AC-3:** Given ein Ortsvergleich im Entwurf und ein Trip im Entwurf / When der Nutzer die Detailseite öffnet / Then steht beim Vergleich „Setup abschließen" genau an der Stelle von „Senden", und beim Trip ist „Senden" an dieser Stelle gesperrt (sichtbar deaktiviert).
  - Test: E2E: Position von „Setup abschließen" (Vergleich-draft) gleich der Position von `subscription-hub-send` (Trip-draft); Trip-Senden hat `disabled`.
- **AC-4:** Given ein Trip mit Kürzel und ein Ortsvergleich / When der Nutzer die Detailseite auf dem Computer öffnet / Then zeigt der Pfad oben „Trips / Kürzel" bzw. „Orts-Vergleiche / Name", der vordere Teil ist ein Link zur jeweiligen Liste, der hintere kein Link, und das Wort „Hub" kommt nirgends mehr vor.
  - Test: E2E `HUB_KINDS`: Text und Link-Eigenschaft der Krümel; Klick auf den Elternteil führt auf `/trips` bzw. `/compare`; kein Element mit Text „Hub" im Kopf.
- **AC-5:** Given ein Trip ohne Kürzel / When der Nutzer die Detailseite öffnet / Then zeigt der Pfad „Trips / Name des Trips" (Name statt Kürzel), und ein sehr langer Name wird in der Leiste abgeschnitten statt umzubrechen.
  - Test: E2E: Trip ohne Kürzel (Pfadtext = Name); Trip mit sehr langem Namen bei 390 px: Leiste bleibt einzeilig, „Senden" bleibt sichtbar.
- **AC-6:** Given Trip und Ortsvergleich mit Status aktiv, pausiert und Entwurf / When der Nutzer die Detailseite bei 1440 und 390 px öffnet / Then steht der Status bei beiden als Badge in der Titelzeile neben dem Namen, es gibt keine eigene Statuszeile mehr, und beim Trip steht „Tag x von y" bzw. beim Vergleich die Laufzeit daneben.
  - Test: E2E `HUB_KINDS` bei beiden Breiten: Statuselement liegt in der Titelzeile (gleiche Zeile wie `h1`, kein Umbruch in eigene Zeile außer bei bewusstem Umbruch aus AC-8); Status genau einmal vorhanden (`issue-336-status-dedup` umgedreht).
- **AC-7:** Given Trip und Ortsvergleich auf dem Handy / When der Nutzer das Menü (drei Punkte) betrachtet / Then sind die Punkte bei beiden senkrecht angeordnet, und ein Tippen öffnet bei beiden dasselbe Aktionsmenü.
  - Test: E2E `HUB_KINDS` bei 390 px: Symbol vertikal (Vergleich nicht mehr `MoreHorizontal`), gleiche Einträge im geöffneten Sheet.
- **AC-8:** Given ein Trip mit langem Namen, Status-Badge und Zusatz „Tag x von y" auf dem Handy (390 px) / When der Nutzer die Detailseite öffnet / Then läuft nichts aus dem Bild (kein waagerechtes Scrollen), das Badge bleibt vollständig lesbar, und der Titel darf umbrechen, ohne die Leiste zu verschieben.
  - Test: E2E bei 390 px: `scrollWidth <= clientWidth`, Badge vollständig im Viewport, Leiste unverändert oben.
- **AC-9:** Given Trip und Ortsvergleich / When der Nutzer den Titelblock vergleicht / Then sind Region-Platzhalter („—" bei leerer Region), Profil und Speicher-Anzeige im Kopf gleich aufgebaut, und die Titelgröße ist bei beiden gleich (38 px).
  - Test: E2E `HUB_KINDS`: Region-Platzhalter, Reihenfolge der Elemente; berechnete Schriftgröße des `h1` muss bei beiden gleich sein (38 px).
- **AC-10:** Given ein Trip mit Zählern an den Reitern und ein Ortsvergleich mit Zähler am Orte-Reiter / When der Nutzer die Reiterleiste bei 1440 und 390 px betrachtet / Then sind die Zähler bei beiden grau-neutral (heller Grund, dunkelgraue Schrift), keiner ist orange gefüllt, und der aktive Reiter bleibt orange unterstrichen.
  - Test: E2E `HUB_KINDS` (HT-8 umgedreht): berechnete Hintergrund- und Schriftfarbe der Badges gleich und nicht `--g-accent`; Kontrast Schrift/Grund mindestens 4,5:1 gemessen.
- **AC-11:** Given Trip und Ortsvergleich / When die Seiten gerendert werden / Then gibt es pro Seite genau einen Kopf (ein `SubscriptionHeader`, eine Breadcrumb), und „Senden" öffnet nur den Sende-Dialog und versendet nichts.
  - Test: bestehende Unit-/E2E-Tests (`subscription_header_einmal_gerendert`, `aktionsmodell_seiten_bindung`, `trip-detail-actions`) grün; E2E: Klick auf Senden öffnet den Dialog, kein Versand-Request vor Bestätigung.
- **AC-12:** Given die Umsetzung / When die Doku geprüft wird / Then liegen ADR-0110 („Löst ab": #2284 S1 Entscheidung 6, S2 Entscheidungen 7/8), der Eintrag in `docs/adr/README.md`, die „Abgelöst durch"-Hinweise in beiden alten Specs und der nachgezogene Wortlaut in `design_system.md:64` (Accent = Weiter/Aktiv, Hauptaktion = Ink) vor.
  - Test: `tests/test_adr_index_drift.py` grün; Doku-Prüfung in /60; ggf. `# doc-compliance-test` für die Hinweise.
- **AC-13:** Given neue und verschobene Nutzertexte (Breadcrumb-Elternteil, Aria-Labels, Status-Zusatz) / When die Oberfläche auf Deutsch und auf Englisch gerendert wird / Then erscheinen alle Texte über den Katalog in beiden Sprachen, und Protokoll-Token (Kürzel) bleiben unübersetzt.
  - Test: E2E mit Nutzersprache de und en für `HUB_KINDS` (Pfadtext des Elternteils übersetzt); `keine_hartkodierten_nutzertexte.test.ts` grün.
- **AC-14:** Given die Seiten der Editoren (`/trips/new`, `/compare/new`) und die Profil-Auswahl / When S1 geliefert ist / Then sind sie unverändert (kein Konflikt mit #2792).
  - Test: Diff-Prüfung in /60: keine Änderung in `TripNewEditor.svelte`, `CompareNewEditor.svelte`; `hub-anlegen-ablauf.spec.ts` unverändert grün.
- **AC-15:** Given (Abschluss) S1 ist auf Staging / When ein Fresh-Eyes-Prüfer ohne Vorwissen das Screenshot-Paar Hub-Kopf Desktop 1440 px und Mobil 390 px (Trip gegen Vergleich) vergleicht / Then findet er keinen Unterschied außer der fachlichen Whitelist (Datum, Kürzel, km/Hm, „Tag x von y", Kacheln, Orte-Anzahl, Entwurfs-Regel), und das Paar liegt als Kommentar im Epic #2345.
  - Test: `fresh-eyes-inspector` ohne Bug-Kontext auf vier Screenshots (2 Breiten x 2 Arten); Ergebnis und Bilder als Kommentar im Epic #2345 abgelegt; Issue #2837 bleibt bis S2 offen.

## Definition of Done

- AC-1 bis AC-15 sind erfüllt, jedes AC hat einen grünen Test aus dem Test Plan; alle divergenz-verankernden Tests sind umgedreht, keiner gelöscht.
- Pflicht-Mutationen aus dem Test Plan werden von mindestens einem Test gefangen (Adversary-Verdict VERIFIED).
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0.
- Lieferbestandteile Doku vorhanden: ADR-0110 samt Index-Eintrag, „Abgelöst durch"-Hinweise in `feat_2284_s1_subscription_header.md` und `feat_2284_s2_trip_kopf.md`, `design_system.md` nachgezogen.
- Fresh-Eyes-Screenshot-Paar Hub-Kopf (Desktop 1440 / Mobil 390, Trip gegen Vergleich) liegt als Kommentar im Epic #2345.
- Issue #2837 bleibt offen, bis S2 (Anlege-Rahmen) geliefert ist.

## Known Limitations

- **Anlege-Rahmen (S2, nur Ausblick):** `/trips/new` und `/compare/new` (Lage der Speicher-Aktionen, Abbrechen-Knopf, Weiter-Knopf, Breadcrumb „Trips / Neuer Trip", Label „Neuer Trip") folgen in einer eigenen Spec, **nachdem #2792 S1c-4b gemergt ist**. Gleiche Entscheidungen sind dafür vorgemerkt: Senden/Hauptaktion schwarz, Weiter orange mit sichtbarem Gesperrt-Zustand, Speicherleiste unten für beide. Hier **keine ACs**.
- Draft-Trip ohne „Setup abschließen"-Pendant ist Produktfrage und bleibt außerhalb.
- Die Randbefunde des Issues (Badge „ALLE KANÄLE" abgeschnitten, Begriffe Wertebereiche/Ideal-Werte, Testdaten „Validator-1025 Compare") gehören nicht hierher.
- Badge-Umbruch bei sehr langen Namen auf 390 px: mit AC-5 und AC-8 abgesichert, Verhalten bei extrem langen Namen („Titel umbricht, Leiste nicht") ist die gewählte Regel.

## Risiken

1. **Badge-Umbruch mobil bei langen Namen und gleichzeitigem Zusatz „Tag x von y"** — Gegenmaßnahme AC-5, AC-8 mit 390-px-Screenshot; Zusatz darf in eine zweite Zeile unter den Titel fallen, die Leiste nicht.
2. **Kontrast:** Neutral-Badge nachrechnen (ink-3 `#6b675c` auf paper-deep `#ecead9` etwa 4,7:1); Senden schwarz gewinnt gegen die Wortlaut-Formel „CTA = Accent" in `design_system.md:64` (wird nachgezogen). Wer später wieder Orange wünscht, braucht ein neues ADR.
3. **Parallelarbeit #2792 (S1c-4b)** baut gerade in `TripNewEditor`/`CompareNewEditor`; S1 berührt diese Dateien nicht (AC-14). Beide Seiten (`routes/*/[id]/+page.svelte`) werden von #2792 nicht verändert; vor Phase 6 trotzdem `origin/main` einziehen.
4. **Viele Tests verankern die Divergenz** (Tabelle Test Plan); sie werden umgedreht, nicht gelöscht. Vergessene Treffer zeigen sich als roter `frontend-test`/`e2e`-CI-Check.
5. **Aktions-Regressionen** (Senden, Kebab-Aktionen, Pausieren) durch das Verschieben der Leiste: AC-11 und die bestehenden Aktions-E2E fangen das.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0110 `hub-kopf-und-anlege-rahmen-ein-baustein` (Lieferbestandteil der Umsetzung, Eintrag in `docs/adr/README.md`).
- **Rationale:** Der Editor-Rahmen ist eine Entscheidungsfläche. Zwei frühere Entscheidungen (#2284 S1 Nr. 6, S2 Nr. 7/8) werden abgelöst, das darf nur über ein neues ADR mit „Löst ab" geschehen. Es schreibt ADR-0097 fort und begründet „Hauptaktion = Ink, Accent = Weiter/Aktiv" aus dem Kontrastprinzip.

## Changelog

- 2026-11-06: Initial spec created (Issue #2837, Epic #2345, Scheibe S1 Hub-Kopf; Anlege-Rahmen als Scheibe S2 ausgegliedert)
- 2026-11-07: Staging-Befund AC-15 (Fresh-Eyes, beide Arten „pausiert“): Status-Schild sah je Art anders aus (Trip `TripStatusBadge` groß/gelb, Vergleich `CompareStatusPill` klein/grau) und der Trip zeigte kein Profil in der Meta-Zeile (AC-9). Die Zeilen „`TripStatusBadge`, `CompareStatusPill` unverändert wiederverwendet“ (Source, Entscheidung 5, Dependencies) weichen damit von AC-15 ab; bindend ist AC-15 (Status-Schild steht nicht auf der Whitelist). BROKEN-Fix: ein gemeinsames Status-Schild im Hub-Kopf nach Design-System §Pill/Badge, `profileLabel` auch beim Trip. `CompareStatusPill` selbst bleibt unverändert.
