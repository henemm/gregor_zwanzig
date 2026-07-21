---
entity_id: issue_661_trip_new_mobile
type: module
created: 2026-06-08
updated: 2026-06-08
status: implemented
version: "1.0"
tags: [frontend, mobile, trip-new, design-compliance, epic-622]
---

# Spec: Neue Tour anlegen — Mobile-Parität /trips/new (#661, #622 AC-9)

## Approval

- [x] Approved (PO 'go' 2026-06-08)

## Purpose

Der Progressive Tab Editor `/trips/new` (#622 Desktop, #658 Wegpunkte) erhält die **Mobile-Adaption
(AC-9)**: Auf Viewport ≤899px rendert der gesamte Anlege-Flow gemäß verbindlicher Design-Quelle
`screen-trip-new-v2-mobile.jsx` — App-Leisten-Kopf, scrollbare Touch-TabBar, gestapelte Route-/Etappen-
Karten, Sheet-basierte Detaileingaben, Floating-CTAs. **Reine responsive/Layout-Arbeit, frontend-only,
additiv. Die Funktionslogik (Lock/Done-State, GPX-Parsing, ein finaler POST) und das Desktop-Layout
(≥900px) bleiben unverändert (Regressionsschutz).** Schließt das #622-Paket vollständig ab.

## Source

- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte` (Kern — Mobile-Markup + `<style>`-Media-Queries)
- **Mitbetroffen (mobiles Wrapper-Padding):** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`, `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` — nur falls Overflow auf 375px nachweisbar; sonst Padding im TripNewEditor-Tab-Wrapper.
- **Wiederverwendet (unverändert):** `mobile/{Sheet,MBtn,MInput,MField,Toast,TopAppBar}.svelte`, `trip-detail/WeatherMetricsTab.svelte` (#618 mobil), `edit/EditStagesPanelNew.svelte` (eigenes Mobile-Layout), `trip-new/tripNewLogic.ts` (Logik).
- **Design-Quelle (verbindlich, 1:1):** `docs/design-requests/trip-anlegen-2026-06-06/screen-trip-new-v2-mobile.jsx`

## Estimated Scope

- **LoC:** ~400–500 (PO 2026-06-08: „ein Paket, höheres Budget" — `loc_limit_override` mit PO-Freigabe gesetzt).
- **Files:** 1 Kern (`TripNewEditor.svelte`) + ggf. 2 Padding-Anpassungen + 1 E2E-Spec.
- **Effort:** high (CSS-only-Pattern erzwingt parallel gerendertes Mobile-Markup; Inline-Style-Refactor).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `mobile/Sheet.svelte` | reuse | Etappenname-Edit + Skip-Bestätigung (Bottom-Sheet) |
| `mobile/{MBtn,MInput,MField,Toast,TopAppBar}.svelte` | reuse | Touch-Primitives + App-Leiste + Lock-Toast |
| `trip-detail/WeatherMetricsTab.svelte` | reuse | Wetter-Tab (bereits mobil, #618) |
| `edit/EditStagesPanelNew.svelte` | reuse | Wegpunkte-Editor (eigenes Mobile-Layout) |
| `trip-new/tripNewLogic.ts` | reuse | Lock/Done/Progress/Payload — unverändert |
| `app.css` `@media (max-width:899px)` | constraint | kanonische Breakpoint-Grenze |

## Implementation Details

**Zentrales Muster (etabliert in #618):** Responsive = CSS-only `@media (max-width:899px)`, **kein
JS-Viewport-Switch**. Da `TripNewEditor` heute durchgängig Inline-Styles nutzt (Media-Queries können
Inline-Styles nicht überschreiben), werden die mobil veränderten Bereiche in **CSS-Klassen** überführt
bzw. Desktop-/Mobile-Markup **parallel gerendert** und per `display:none` umgeschaltet:

```
.tn-desktop { display: block; }   .tn-mobile { display: none; }
@media (max-width:899px){ .tn-desktop{display:none} .tn-mobile{display:block} }
```

- **Kopf:** Desktop-Breadcrumb-Zeile bleibt (`.tn-desktop`); mobil `TopAppBar` (title=aktiver Tab-Label,
  eyebrow=Tour-Name, leftIcon=back→`/trips`, right=„Speichern" — aktiv nur wenn `ready`).
- **Fortschritt:** mobil flex:1-Segmente + „N/4" (`TNM_Progress`).
- **TabBar:** scrollbar, `min-height:44px`, gesperrter Tab-Tap → `Toast` 2s (statt Desktop-Flash).
- **Route-Tab:** `MField`/`MInput`, native `<input type=date>` (16px), Floating-CTA `position:fixed`/absolute.
- **Etappen-Tab:** vertikale Cards (T-Badge, tappbarer Name → `Sheet`, Auto-Datum, GPX-Slot volle Zeile),
  „+ Etappe", Floating-CTAs bei `etDone`.
- **Wegpunkte-Tab:** eingebetteter `EditStagesPanelNew` rendert sein **eigenes Mobile-Layout** (Karte +
  Höhenprofil-Sheet + Liste, touch-bedienbar). **Bewusste Abweichung vom JSX-Mock-Placeholder** (R4):
  kein Funktionsverlust — der echte Editor ist bereits mobil bedienbar (PO 2026-06-08).
- **Wetter-Tab:** `WeatherMetricsTab createMode` — bereits mobil (FAB + Sheet, #618), unverändert.
- **Zeitplan/Alerts:** mobiles Tab-Wrapper-Padding (16px) statt Desktop `40px`/`max-width:720`.
- **Logik unangetastet:** `unlockedTabs/doneTabs/stageDate/progressCount/canSave/buildCreateTripPayload`,
  ein finaler `POST /api/trips`. Mobil identische `activeTab`/`stages`/`channels`-State-Quelle.

## Expected Behavior

- **Input:** Aufruf `/trips/new` auf Viewport ≤899px (eingeloggter Nutzer).
- **Output:** Mobiles Layout gemäß `screen-trip-new-v2-mobile.jsx`; voll bedienbarer Anlege-Flow bis POST.
- **Side effects:** keine neuen — exakt ein `POST /api/trips` am Schluss (wie Desktop). Kein Backend-/Schema-Change.

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter Nutzer öffnet `/trips/new` auf einem Mobile-Viewport (≤899px) / When die Seite geladen ist / Then zeigt eine obere App-Leiste den Titel des aktiven Tabs, als Eyebrow den Tour-Namen (oder „Neue Tour") und rechts eine „Speichern"-Aktion, **während** die Desktop-Breadcrumb-Zeile („Trips / Neue Tour" + Abbrechen/Speichern) nicht sichtbar ist.
  - Test: Playwright @375×667, `/trips/new` — App-Leisten-„Speichern" sichtbar, Desktop-Breadcrumb-Container `hidden`/`display:none` (computed).

- **AC-2:** Given der Mobile-Viewport mit gesperrtem Tab (z.B. „Etappen" ohne Tour-Name) / When der Nutzer den gesperrten Tab antippt / Then erscheint ein kurzer Toast-Hinweis mit dem Lock-Grund und der aktive Tab wechselt **nicht**; die TabBar ist horizontal scrollbar und jedes Tab-Ziel ist ≥44px hoch.
  - Test: Playwright @375 — Tap auf gesperrtes „Etappen" → Toast sichtbar, `activeTab` bleibt „Route"; Tab-`boundingBox().height ≥ 44`.

- **AC-3:** Given der Mobile-Viewport, Route-Tab / When er rendert / Then sind Tour-Name-, Region- und Startdatum-Eingaben volle Breite gestapelt (kein horizontaler Overflow) und der primäre Weiter-CTA schwebt am unteren Rand; nach Eingabe von Name **und** Startdatum wird der CTA aktiv und führt in den Etappen-Tab.
  - Test: Playwright @375 — Inputs `clientWidth ≤ viewport`, Floating-CTA `position:fixed/absolute` am unteren Rand; Name+Datum eintippen → CTA klickbar → `activeTab`=„etappen".

- **AC-4:** Given der Mobile-Viewport, Etappen-Tab / When er rendert / Then werden Etappen als vertikale Karten dargestellt (kein Desktop-Grid), jede mit T-Badge, antippbarem Namensfeld, Auto-Datum und voll­breitem GPX-Slot; Tippen auf den Namen öffnet ein Bottom-Sheet zur Namenseingabe, und die Übernahme schreibt den Namen in die Karte zurück.
  - Test: Playwright @375 — Etappen-Karten gestapelt (kein `grid-template-columns` mit 5 Spalten); Tap Name → `Sheet` offen → Text eingeben + „Übernehmen" → Kartentitel aktualisiert.

- **AC-5:** Given der Mobile-Viewport, Wegpunkte-Tab (nach GPX-Upload freigeschaltet) / When er rendert / Then erscheint der eingebettete Wegpunkt-Editor in seinem **Mobile-Layout** (Karte + Höhenprofil + Wegpunkt-Liste, mit dem Finger bedienbar, kein horizontaler Overflow), und die Aktionen „Überspringen"/„Wegpunkte übernehmen" sind erreichbar und führen in den Wetter-Tab.
  - Test: Playwright @375 — Wegpunkte-Tab öffnen, Editor-Mobile-Container sichtbar, keine Breite > Viewport; „übernehmen" → `activeTab`=„metriken".

- **AC-6:** Given der Mobile-Viewport / When der Nutzer die Tabs Wetter-Metriken, Briefing-Zeitplan und Alerts öffnet / Then passt der Inhalt jeweils in die 375px-Breite ohne horizontalen Overflow (Wetter nutzt das #618-Muster FAB+Sheet; Zeitplan/Alerts mobiles Padding) — kein Element ist breiter als der Viewport.
  - Test: Playwright @375 — je Tab `document.scrollingElement.scrollWidth ≤ innerWidth + 1`; Wetter-FAB „So kommt es an" sichtbar.

- **AC-7:** Given der Mobile-Viewport mit erfüllten Pflichtschritten (Name+Datum, GPX, Wetter besucht, Zeitplan besucht) / When der Nutzer „Speichern" in der App-Leiste auslöst / Then wird die Tour mit **genau einem** `POST /api/trips` angelegt und auf `/trips/{id}` navigiert — identische Persistenz wie Desktop (gleicher Payload inkl. Etappen/Wegpunkte).
  - Test: Playwright @375 gegen Staging — kompletter Flow bis „Speichern", Netzwerk zeigt **einen** `POST /api/trips`, danach URL `/trips/<neueId>`; angelegter Trip im Backend prüfbar.

- **AC-8:** Given ein Desktop-Viewport (≥900px) / When `/trips/new` rendert / Then ist das Layout gegenüber dem Live-Desktop unverändert (Breadcrumb-Kopf, Etappen-Grid, max-width-Container) und **kein** Mobile-Element (App-Leiste, Floating-CTA, Toast-TabBar) ist sichtbar.
  - Test: Playwright @1280×900 — Desktop-Breadcrumb sichtbar, Mobile-App-Leiste `display:none`; Etappen-Grid vorhanden. Plus erneutes Desktop-Pixel-Gate gegen Live (Regressionsschutz).

- **AC-9:** Given ein aus `screen-trip-new-v2-mobile.jsx` gerendertes SOLL-Mobile-PNG (Technik #632/#658) / When der Live-Mobile-Render bei 375px pixelweise verglichen wird / Then liegt die Diff-Quote unter dem vereinbarten Schwellwert (Richtwert ≤ 12% wegen Daten-Divergenz Mock vs. echter State; finaler Wert im Validierungs-Schritt begründet).
  - Test: Pixel-Diff-Skript (Wegwerf, in `docs/artifacts/<workflow>/`) SOLL-PNG vs. Live-375px-Screenshot, Diff < Schwellwert.

## Known Limitations

- **L1 — Wegpunkte-Abweichung vom JSX-Mock (R4):** Der eingebettete Editor zeigt mobil sein echtes,
  funktionsvolles Layout statt des vereinfachten JSX-Karten-Platzhalters. Bewusste PO-Entscheidung
  (2026-06-08) gegen Funktionsverlust. Das Pixel-Gate (AC-9) bewertet daher den Wegpunkte-Tab nachsichtiger
  bzw. klammert ihn aus, falls die Mock-Divergenz dominiert (im Validierungs-Schritt begründen).
- **L2 — Pixel-Schwellwert datenbedingt:** SOLL-PNG nutzt Mock-Daten (feste Etappen/GPX/Wegpunkte), der
  Live-Render echten State → Diff-Anteil ist teils Daten-, nicht Layout-Divergenz (Muster #579/#618).
- **L3 — Reuse-Komponenten:** Falls `EditReportConfigSection`/`AlertRulesEditor` auf 375px Overflow zeigen,
  wird **nur** mobiles Wrapper-/Komponenten-Padding ergänzt — keine Funktions- oder Desktop-Änderung.

## Changelog

- 2026-06-08: Implementation completed. TripNewEditor.svelte responsive Layout (CSS-only @ 899px), Mobile-Markup parallel + All 9 ACs (#622 Paket) verified.
- 2026-06-08: Initial spec created (Issue #661, #622 AC-9 Mobile-Parität).
