# Kontext: #3443 — S5d Entwurf aktivieren über Status-Pill im Kopf und Kebab

## Request Summary
Teil von S5 #2797 (V16, PO-Entscheidung „rein“). Soll (Mockup Fassung 4, `mockup-hub-fassung4.html` Z. 413, 430, 820, 828):
Status-Pill im Kopf; im Zustand „Entwurf“ steht daneben ein **Knopf** „Aktivieren“ (Akzent, `btn sm accent`), im Kebab
als **erster** Eintrag „Aktivieren“ (nur Entwurf). Klick ⇒ Status „aktiv“, Meldung „Aktiviert. Das erste Briefing kommt
morgen um 07:00.“ (Uhrzeit aus der Zustellung). Elementliste: `orte.*.kopf` Rolle `knopf` „Aktivieren“
(`aktionen.kopf.aktivieren`), `orte.*.kebab-menue` Ordnung 1 „Aktivieren“. Trip und Orte EIN Code (ADR-0097/0110).

## Ist-Stand (live)
- `HubKopf.svelte` hat seit #2913 c2 `aktivierenHref`: im Entwurf ein **Link** „Aktivieren“ neben der Pill.
  - Trip (`TripHeader.svelte:87–122`): Ziel `?tab=etappen`.
  - Orte (`routes/compare/[id]/+page.svelte:427–449`): Ziel `?tab=zustellung#versand`; zusätzlich „Setup abschließen“
    auf dem Platz von „Test schicken“ (`sendMode='setup'`, ADR-0110 Punkt 6).
- Kebab-Aktionen: `shared/subscriptionActions.ts` `subscriptionActions(kind, status, 'hub')` — Entwurf im Hub heute nur `delete`.
- Kebab-Meldungen: `shared/kebabBestaetigung.ts` (`erfolgsText`, `fehlerText`), #3442.
- Aktivierungskarte im Versand (nur Orte): `compare/CompareTabs.svelte:859–877`, `hubActivationBanner` in
  `compare/compareHubPersistenz.ts:100`; Klick ruft `handleToggleActive` (schedule manual ⇄ previous_schedule),
  einziger Schreibweg für Pausieren/Aktivieren (F004), Kebab delegiert per `toggleActiveFromParent`.
- Nächstes Briefing vom Server: `NextBriefing` + `formatNextBriefing` (`shared/versand-tab/nextBriefingText.ts:101`).

## Kernbefund: „Entwurf“ ist heute ein **abgeleiteter Daten-Zustand**, kein Schalter
- Trip: `utils/tripStatus.ts` `deriveTripStatus` ⇒ `draft` genau dann, wenn **keine Etappe ein Datum** trägt.
- Orte: `compare/subscriptionHelpers.ts` `deriveStatusFromPreset` ⇒ `draft` genau dann, wenn **Name fehlt oder keine Orte**.
- Es gibt kein Datenfeld „Entwurf“ (weder Go `internal/` noch Python). Anlegen eines Vergleichs ist immer zugleich
  Aktivieren (`CompareNewEditor` „Briefing aktivieren“ = ein POST mit Zeitplan).
- Folge: Ein Klick auf „Aktivieren“ kann einen Entwurf nicht aktiv machen, solange Daten fehlen (Trip ohne Datum hat
  keinen Versandtag; Vergleich ohne Orte hat nichts zu vergleichen). Die Aktivierungskarte toggelt im Entwurf nur den
  Zeitplan — der Status bleibt „Entwurf“. Das Mockup (Orte standardmäßig „entwurf“ mit vollständigen Daten) setzt
  einen Zustand „vollständig, aber noch nicht aktiviert“ voraus, den das Datenmodell nicht kennt.
- Prüfkonto-Seed (`scripts/staging_pruefkonto_mockupdaten.py:323`) legt den Vergleich aktiv an (`schedule daily`);
  die Elementlisten-Abnahme sieht „Aktivieren“ daher auf Staging nicht.

## Related Files
- `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte`
- `frontend/src/lib/components/trip-detail/TripHeader.svelte`, `frontend/src/routes/trips/[id]/+page.svelte`
- `frontend/src/routes/compare/[id]/+page.svelte`, `frontend/src/lib/components/compare/CompareTabs.svelte`
- `frontend/src/lib/components/shared/subscriptionActions.ts`, `shared/kebabBestaetigung.ts`
- `frontend/src/lib/components/compare/compareHubPersistenz.ts`, `compare/subscriptionHelpers.ts`, `utils/tripStatus.ts`
- i18n: `frontend/src/lib/i18n/messages/{de,en}/aktionen.json`, `vergleich.json`

## Existing Specs
- `docs/specs/modules/feat_2913_c2_seitenkopf.md` (Aktivieren-Link), `feat_3442_kebab_rueckfragen.md`,
  `feat_2278_aktionsmodell.md`, `rework_2837_s1_hub_kopf.md`; ADR-0110 Punkt 6 (Entwurfs-Regel).

## Risks
- Datenverlust beim Statuswechsel (F004): Aktivieren muss den einzigen Schreibweg `handleToggleActive` nutzen.
- Produktsemantik von „Entwurf“ (siehe Kernbefund) — Produktentscheidung, nicht technisch auflösbar.
- Zwei-Nutzer-Isolation bei jedem Schreibweg.

## Analysis

**Type:** Feature (Oberfläche Hub-Kopf + Kebab, Trip und Orte ein Code)

**Befund (Plan-Agent, Code in Go und Python geprüft):** Es gibt keinen Zustand „vollständig, aber nicht aktiviert“.
Trip mit Datum wird automatisch beliefert (`trip_report_scheduler.py` filtert nur `paused_at`/`archived_at`/`slot_aktiv`);
Vergleich mit `schedule manual` ist „pausiert“, nie „Entwurf“. Ein Klick kann einen Entwurf nicht aktiv machen;
die Meldung „Aktiviert …“ wäre im Entwurf falsch.

| Variante | Dateien | LoC | Risiko |
|---|---|---|---|
| A: expliziter Entwurfszustand (Feld, Go+Python-Scheduler, Backfill, „als Entwurf speichern“ beim Anlegen) | 20–25 | 500–800 | hoch (Schema, Bestandsdaten, neuer Schreibweg, ADR-0110 P6) |
| B: abgeleiteter Entwurf bleibt; „Aktivieren“ wird Knopf neben der Pill + erster Kebab-Eintrag (nur Entwurf); Klick führt zum fehlenden Teil und nennt ihn | 6–8 | 120–200 | niedrig (kein Schreibweg) |
| C: B + echter Wechsel, wo möglich (Vergleich vollständig, aber manual) über `toggleActiveFromParent`, Meldung mit Uhrzeit aus `NextBriefing` | 8–10 | 180–280 | mittel (Vermischung pausiert/Entwurf) |

**Affected Files (B):** MODIFY `shared/hub-kopf/HubKopf.svelte` (Link → Knopf, `onAktivieren`), `trip-detail/TripHeader.svelte`,
`routes/trips/[id]/+page.svelte`, `routes/compare/[id]/+page.svelte`, `shared/subscriptionActions.ts` (Entwurf/Hub: `activate`, `delete`),
`shared/kebabBestaetigung.ts` (Hinweistext „was fehlt“), i18n `de|en/aktionen.json`; Tests node:test.

**Risks:** F004 (kein neuer Schreibweg in B), Zwei-Nutzer-Isolation unberührt in B; Staging-Abnahme braucht einen Entwurf im Prüfkonto (Trip ohne Datum).

**Open Questions:** Produktentscheidung an PO: Entwurf explizit (A) oder abgeleitet (B)? Empfehlung B; A als eigenes Issue, falls gewünscht.

**PO-Entscheidung 27.11.2026 (AskUserQuestion):** Variante B „Knopf führt zum Fehlenden“. Knopf neben der Pill + erster
Kebab-Eintrag; Klick nennt, was fehlt, und öffnet die Stelle; „Aktiviert. Das erste Briefing kommt … um HH:MM.“ erscheint,
sobald der Entwurf dadurch wirklich aktiv geworden ist. Kein expliziter Entwurfszustand.
