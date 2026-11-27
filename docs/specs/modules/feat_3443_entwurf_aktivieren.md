---
entity_id: feat_3443_entwurf_aktivieren
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: feat-3443-entwurf-aktivieren
tags: [hub, kopf, kebab, entwurf, aktivieren, i18n, "#3443", "#2797", "#2791"]
---

# S5d: Entwurf aktivieren über Knopf im Kopf und Kebab (Trip und Orts-Vergleich)

## Approval

- [ ] Approved

## Purpose

Im Zustand „Entwurf“ steht im Hub-Kopf neben der Status-Pill ein Akzent-Knopf „Aktivieren“, und im Kebab-Menü ist „Aktivieren“ der erste Eintrag. Ein Entwurf ist heute kein Schalter, sondern ein abgeleiteter Daten-Zustand (Trip ohne datierte Etappe, Vergleich ohne Namen oder ohne Orte). Deshalb schaltet der Klick nichts ein: Er nennt, was am Entwurf noch fehlt, und öffnet die Stelle, an der es sich ergänzen lässt. Sobald der Nutzer das Fehlende ergänzt hat und der Entwurf dadurch wirklich aktiv geworden ist, zeigt der Kopf „Aktiviert. Das erste Briefing kommt {wann}.“. Grundlage ist die PO-Entscheidung vom 27.11.2026 (Variante B „Knopf führt zum Fehlenden“) in #3443 und das Mockup Fassung 4.

## Source

- **File:** `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte`, `frontend/src/lib/components/shared/subscriptionActions.ts`, `frontend/src/lib/components/shared/entwurfAktivieren.ts` (neu), `frontend/src/lib/components/shared/aktivierungsWechsel.svelte.ts` (neu)
- **Identifier:** `HubKopf` (Prop `onAktivieren` ersetzt `aktivierenHref`), `subscriptionActions` (neue Aktion `activate`), `entwurfAktivieren` (reines Modell: `fehltFuerAktivierung`, `hinweisFuer`, `aktiviertText`, `warAktivierung`), `erstelleAktivierungsWechsel` (Runen-Modul: erkennt den Wechsel Entwurf → aktiv und holt „nächstes Briefing“)

> **Schicht:** ausschließlich Frontend (SvelteKit, `frontend/src/...`). Keine Änderung an Go-API oder Python-Core. Gelesen wird nur der bestehende Endpunkt `GET /api/next-briefings`; geschrieben wird beim Klick auf „Aktivieren“ nichts.
> **Trip/Orts-Vergleich:** ein Code. Knopf (`HubKopf`), Kebab-Eintrag (`subscriptionActions`), Modell und Wechsel-Erkennung sind geteilt (ADR-0097, ADR-0110, #1170). Die Seiten reichen nur ihre Daten ein (Trip: Etappen mit Datum; Orte: Name und Orte) und den Zielreiter; es gibt keinen `context`-Zweig und keine Compare-eigene Komponente.
> **Kanäle:** nicht betroffen (keine Briefing- oder Alarminhalte; die Meldung zeigt nur den Termin des nächsten Briefings).

## Estimated Scope

- **LoC:** Produktivcode ca. 230, Tests ca. 400 (ca. 630 insgesamt)
- **Files:** 21 (9 Produktiv- und Katalogdateien, 4 Doku-Dateien, 8 Testdateien: 3 neue Kern-Tests, 1 neuer E2E, 4 umgestellte Bestandstests)
- **Effort:** medium

**Scope-Hinweis:** Der Produktivcode bleibt unter dem Projektlimit `scope_guard.max_loc_delta: 250`. Falls der Testumfang das Testlimit übersteigt, setzt der Workflow wie bei #3442 selbst den vorgesehenen Testumfang-Wert; es sind keine Änderungen an der Gate-Konfiguration und keine Schritte vorgesehen, die ein menschliches Override brauchen (Autark-Modus).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/hub-kopf/HubKopf.svelte` | component | Knopf neben der Status-Pill (statt Link), reicht Aktionen an den Kebab |
| `shared/subscriptionActions.ts` | module | Einzige Aktionsquelle des Hubs; neu `activate` als erster Eintrag im Entwurf |
| `frontend/src/lib/utils/tripStatus.ts` (`deriveTripStatus`) | module | Regel „Trip ist Entwurf“ (keine Etappe mit Datum); bleibt unverändert |
| `compare/subscriptionHelpers.ts` (`deriveStatusFromPreset`) | module | Regel „Vergleich ist Entwurf“ (Name fehlt oder keine Orte); bleibt unverändert |
| `shared/versand-tab/nextBriefingLoad.ts` (`ladeNaechstesBriefing`) | module | Holt `GET /api/next-briefings?trip_id=` bzw. `?preset_id=`; Fehler und fehlender Eintrag ergeben `null` |
| `shared/versand-tab/nextBriefingText.ts` (`NextBriefing`, `formatNextBriefing`) | module | Ein Formatierer für Tag und Uhrzeit („Do 29.10. 07:00 (CEST)“, zonenfrei aus `local_date`/`local_time`) |
| `shared/versand-tab/naechstesBriefingLader.svelte.ts` | module | Vorbild für Laufnummer-Schutz (späte ältere Antwort überschreibt nie eine neuere) |
| `shared/kebabBestaetigung.ts`, Meldungsweg der Seiten (`meldung` / `hub-aktion-meldung`) | module | Bestehender Meldungsweg des Kopfs (#3442), wird mitgenutzt |
| `compare/CompareTabs.svelte`, `shared/subscriptionTabs.ts` (`resolveTab`) | component | Reiter-Kennung des Orte-Reiters (`orte`) und Trip-Reiter (`etappen`) |
| `Btn` (Atom, variant `accent`, size `sm`) | atom | Knopf „Aktivieren“ (ADR-0118 Knopf-Stil, WCAG-AA) |
| Katalog `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | i18n | Bestehend `aktionen.kopf.aktivieren`; neu `aktionen.aktivieren.*` |
| `docs/context/einstellungen_neu/elementliste.json` | doc | `orte.*.kopf` Knopf „Aktivieren“, `kebab-menue` Ordnung 1 „Aktivieren“ |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (Z. 413, 430, 820, 828) | doc | Soll-Bild |
| ADR-0097, 0104, 0110, 0118 | ADR | Trip/Orte ein Code; DE/EN; Entwurfs-Regel (Punkt 6); Knopf-Stil |
| `feat_2913_c2_seitenkopf.md`, `feat_3442_kebab_rueckfragen.md`, `feat_2278_aktionsmodell.md` | spec | Werden fortgeschrieben (Link wird Knopf; Entwurfs-Aktionsliste) |

## Implementation Details

**Gewählte Variante B (PO-Entscheidung 27.11.2026, nicht neu verhandeln).** Variante A (expliziter Entwurfszustand mit neuem Feld, Scheduler-Umbau, Backfill) und Variante C (Vermischung von „pausiert“ und „Entwurf“) sind verworfen. Der Entwurf bleibt ein abgeleiteter Zustand; ein Klick schreibt nichts, daher bleibt die Datenverlust-Regel F004 (einziger Schreibweg `handleToggleActive`/Hub-Schreiber) unberührt.

**1. Knopf im Kopf (`HubKopf.svelte`).** Die Prop `aktivierenHref?: string` entfällt, neu `onAktivieren?: () => void`. Ist sie gesetzt, zeigt der Kopf im `hub-kopf-status` neben der Pill einen `Btn` (variant `accent`, size `sm`, testid `hub-kopf-aktivieren` bleibt stabil) mit dem Text `aktionen.kopf.aktivieren`; Klick ruft `onAktivieren`. Der Knopf ist ein echter Knopf (`<button>`, kein `href`). Die Seiten übergeben `onAktivieren` nur, wenn der Lebenszyklus `draft` ist (`TripHeader` für den Trip, `compare/[id]/+page.svelte` für Orte). Kein Zweig nach `context`.

**2. Kebab im Hub (`subscriptionActions.ts`).** Neue Aktions-Kennung `activate` mit Katalogschlüssel `aktionen.kopf.aktivieren` (kein Gefahr-Merkmal, keine Rückfrage: `braucheRueckfrage('activate')` ist falsch). `subscriptionActions(kind, 'draft', 'hub')` liefert `activate`, dann `delete`. Alle anderen Zustände und die Flächen `list` und `mobile` bleiben unverändert (Liste hat im Entwurf weiter „Einrichtung fortsetzen“ und „Löschen“). Das mobile Aktionsblatt im Hub nutzt dieselbe Funktion und zeigt den Eintrag mit. Beide Seiten bearbeiten `activate` in ihrem `handleHubAction`/`handleAction` und rufen dieselbe Seitenfunktion wie der Kopf-Knopf.

**3. Klick: was fehlt (`shared/entwurfAktivieren.ts`, rein und node-testbar).** `fehltFuerAktivierung(kind, objekt)` liefert die Liste der fehlenden Teile und wiederholt die bestehenden Regeln, ohne sie zu ändern: Trip `etappen_datum`, wenn keine Etappe ein Datum trägt (Regel `deriveTripStatus`); Orte `name`, wenn der Name leer ist, und `orte`, wenn keine Orte gewählt sind (Regel `deriveStatusFromPreset`). `hinweisFuer(teile)` liefert den Text aus dem Katalog als ganze Sätze je Fall (keine Grammatik-Zusammensetzung, damit DE und EN stimmen): „Zum Aktivieren fehlt noch: Datum der Etappen.“, „Zum Aktivieren fehlen noch: Orte.“, „Zum Aktivieren fehlt noch: ein Name.“, „Zum Aktivieren fehlen noch: Name und Orte.“. `zielFuer(kind, teile)` bestimmt die Stelle: Trip `?tab=etappen`; Orte mit fehlenden Orten (auch zusammen mit Name) `?tab=orte` (Kennung aus `CompareTabs`/`resolveTab`); fehlt nur der Name, keine Navigation, der Name wird im Kopf bearbeitet. Die Seite zeigt den Hinweis über ihren bestehenden Meldungsweg (Trip `meldung`, Orte `meldung(text, true)`; sichtbar als `hub-aktion-meldung`) und navigiert per `goto(ziel, { noScroll: true, keepFocus: true })`. Der Klick löst keinen Server-Schreibzugriff aus (kein PUT/PATCH/POST/DELETE); beim Trip und bei Orten bleibt die Seite ohne Neuladen stehen. Ist der Entwurf (laut Modell) gar nicht unvollständig, zeigt die Seite keinen Hinweis und nichts passiert (kann nur bei einem Stand-Wettlauf eintreten).

**4. „Aktiviert“-Meldung.** Quelle ist die bestehende serverseitige Angabe „nächstes Briefing“: `GET /api/next-briefings?trip_id=` bzw. `?preset_id=` über `ladeNaechstesBriefing(holen, context, id)` (Typ `NextBriefing`), Anzeige über `formatNextBriefing`. Heute lädt sie nur der Hub-Übersichtsreiter und der Versand-Reiter über `erstelleNaechstesBriefingLader` (nach jedem erfolgreichen Speichern neu); der Kopf hat keinen Zugriff darauf und lädt sie im Normalfall nicht. Festlegung: Ein neues Runen-Modul `aktivierungsWechsel.svelte.ts` (`erstelleAktivierungsWechsel(quelle, holen, beiMeldung)`) beobachtet den Lebenszyklus der Seite (`lifecycle`, Trip wie Orte). Springt er von `draft` auf `active` (Prüfung `warAktivierung(vorher, nachher)`; nicht bei `draft → archived` oder `draft → paused`, nicht beim ersten Lesen), holt das Modul genau einmal das nächste Briefing (Laufnummer-Schutz wie im Lader: eine spät eintreffende ältere Antwort überschreibt nie eine neuere) und meldet `aktiviertText(nb, context)`. Der Abruf erfolgt erst nach dem Wechsel, also nach dem erfolgreichen Speichern der Daten (Trip: `onTripUpdate`, Orte: übernommenes `currentPreset`), damit der Server den neuen Stand kennt. Wortlaut: „Aktiviert. Das erste Briefing kommt {wann}.“ mit `{wann}` = Ausgabe von `formatNextBriefing` (Wochentag, Datum, Uhrzeit, Zonenkürzel, z. B. „Do 29.10. 07:00 (CEST)“; Tag und Uhrzeit aus `local_date`/`local_time`, nie aus `at` in der Browser-Zone, ADR-0051). Liefert die Quelle keine Zeit (Abruf scheitert, kein Eintrag, `at == null`, Anzeige „—“), lautet die Meldung nur „Aktiviert.“ und nennt nie eine erfundene Uhrzeit. Beim ersten Laden einer bereits aktiven Seite gibt es keine Meldung und keinen zusätzlichen Abruf. Die Meldung läuft über denselben Meldungsweg wie die Hinweis-Meldung (`hub-aktion-meldung`) und wird wie jede Meldung bei der nächsten Aktion ersetzt.

**5. Bestehendes bleibt.** „Setup abschließen“ auf dem Platz von „Test schicken“ im Vergleich-Entwurf (ADR-0110 Punkt 6, `sendMode='setup'`, Ziel Versand-Reiter), die Aktivierungskarte im Versand-Reiter, und Pausieren/Fortsetzen/Archivieren/Reaktivieren/Löschen samt Rückfragen (#3442) funktionieren unverändert.

**6. Katalog (DE/EN, ADR-0104).** Neue Schlüssel in `aktionen.json` (de/en): `aktionen.aktivieren.hinweis_etappen_datum`, `…hinweis_orte`, `…hinweis_name`, `…hinweis_name_orte`, `…erfolg` („Aktiviert.“ / „Activated.“), `…erfolg_mit_zeit` („Aktiviert. Das erste Briefing kommt {wann}.“ / „Activated. The first briefing arrives {wann}.“). Der Knopf- und Menütext nutzt den bestehenden Schlüssel `aktionen.kopf.aktivieren` („Aktivieren“ / „Activate“). Kein hartkodierter Nutzertext.

**7. Mandantentrennung.** Diese Scheibe führt keinen neuen Datenpfad ein: Der Klick schreibt nichts, und der einzige neue Lesezugriff ist der bereits bestehende, mandantengetrennte Endpunkt `GET /api/next-briefings` (`user_id` aus dem Auth-Kontext, bestehende Zwei-Nutzer-Absicherung dort), der schon heute von Hub-Übersicht und Versand-Reiter genutzt wird. Ein zusätzlicher Zwei-Nutzer-Test entfällt deshalb. Der Staging-Test legt seine Abos mit dem Prüfkonto selbst an und löscht nur diese.

**8. Staging-Abnahme (Entwurf im Prüfkonto).** Der Prüfkonto-Seed legt Abos aktiv an, ein Entwurf ist dort nicht vorhanden. Der E2E-Test legt deshalb seine Entwürfe selbst per API an und löscht sie am Ende (Muster `seed(page, kind, …)` und Aufräumen aus `hub-kopf-c2-mockup.staging.spec.ts`): Trip mit einer Etappe ohne Datum (`stages` mit einer Etappe ohne `date`); Orts-Vergleich ohne Orte (`location_ids: []`). Der Wechsel auf „aktiv“ wird in der geöffneten Seite über die Oberfläche herbeigeführt (Trip: Datum der Etappe im Reiter Etappen setzen; Orte: Ort im Orte-Reiter hinzufügen), nicht per API-Aufruf im Hintergrund, weil der Wechsel innerhalb der Sitzung stattfinden muss.

## Bekannte Abweichungen vom Mockup

Das Mockup Fassung 4 (Z. 413, 430, 820, 828) schaltet „Aktivieren“ per Klick auf „aktiv“ und zeigt sofort „Aktiviert. Das erste Briefing kommt morgen um 07:00.“. Es setzt einen Zustand „vollständig, aber noch nicht aktiviert“ voraus, den das Datenmodell nicht kennt: Im Gregor-Datenmodell bedeutet Entwurf „es fehlen Daten“ (Trip ohne datierte Etappe, Vergleich ohne Namen oder Orte), ein Trip mit Datum wird automatisch beliefert, ein Vergleich mit Zeitplan „manuell“ ist „pausiert“. Deshalb gilt, abweichend vom Mockup: der Klick nennt, was fehlt, und öffnet die Stelle; die Meldung „Aktiviert …“ erscheint erst, wenn der Entwurf wirklich aktiv geworden ist; der Termin steht im Format der übrigen Anzeigen („Do 29.10. 07:00 (CEST)“ statt „morgen um 07:00“). Verweis: PO-Entscheidung 27.11.2026 (AskUserQuestion, Variante B) im Kontext `docs/context/feat-3443-entwurf-aktivieren.md` und im Issue #3443. Die Prüfkonto-Daten (aktiv angelegt) zeigen „Aktivieren“ auf Staging nicht; der Elementlisten-Abgleich für diesen Knopf braucht einen Entwurf (siehe Test Plan).

## Expected Behavior

- **Input:** Klick auf „Aktivieren“ im Hub-Kopf oder im Kebab-Menü eines Entwurfs (Trip oder Orts-Vergleich); später ergänzt der Nutzer das Fehlende.
- **Output:** Hinweis „Zum Aktivieren fehlt(en) noch: …“ und die passende Stelle öffnet sich (Trip: Reiter Etappen; Orte: Reiter Orte, bei nur fehlendem Namen keine Navigation). Sobald der Entwurf durch die ergänzten Daten aktiv wird: „Aktiviert. Das erste Briefing kommt {wann}.“ oder nur „Aktiviert.“, wenn kein Termin vorliegt.
- **Side effects:** Keine Schreibzugriffe durch den Klick. Ein einzelner Lesezugriff auf „nächstes Briefing“ nach dem Wechsel auf aktiv; keiner beim normalen Laden.

## Acceptance Criteria

- **AC-1:** Given der Hub eines Entwurfs (Trip ohne datierte Etappe bzw. Orts-Vergleich ohne Orte) / When der Kopf angezeigt wird / Then steht neben der Status-Pill ein Akzent-Knopf „Aktivieren“ (ein echter Knopf, kein Link), und in jedem anderen Zustand (aktiv, geplant, pausiert, archiviert) fehlt er.
  - Test: Kern-Schicht `node --test` auf das Kopf-Markup (Knopf-Element ohne `href`, Variante accent, genau einmal im Entwurf, nie sonst, beide Kontexte, DE und EN) plus Playwright gegen Staging mit selbst angelegten Entwürfen (Knopf sichtbar neben der Pill, nach Ergänzen der Daten verschwunden).

- **AC-2:** Given der Hub eines Entwurfs / When der Nutzer das Kebab-Menü (Desktop-Menü und mobiles Aktionsblatt) öffnet / Then lautet der erste Eintrag „Aktivieren“, danach folgt „Löschen …“, und die Listenmenüs sowie die Menüs aller anderen Zustände verhalten sich unverändert.
  - Test: `node --test` auf `subscriptionActions(kind,'draft','hub')` (Reihenfolge `activate`, `delete`, beide Arten) und auf unveränderte Ergebnisse für `list`/`mobile` und die übrigen Zustände, plus Playwright gegen Staging (Menüeintrag Nummer 1 in beiden Hubs, bei 390 px im Blatt).

- **AC-3:** Given ein Trip-Entwurf ohne Datum an den Etappen / When der Nutzer „Aktivieren“ im Kopf anklickt / Then erscheint „Zum Aktivieren fehlt noch: Datum der Etappen.“, der Reiter Etappen öffnet sich, und es geht kein Schreibzugriff (PUT, PATCH, POST, DELETE) an den Server.
  - Test: Playwright gegen Staging mit selbst angelegtem Trip-Entwurf (Meldungstext sichtbar, Adresse enthält `tab=etappen`, Anfragenzähler ohne Schreibaufrufe) plus `node --test` auf `fehltFuerAktivierung('trip', …)` und `hinweisFuer`.

- **AC-4:** Given ein Orts-Vergleich-Entwurf ohne Orte / When der Nutzer „Aktivieren“ anklickt / Then erscheint „Zum Aktivieren fehlen noch: Orte.“, der Reiter Orte öffnet sich, und es geht kein Schreibzugriff an den Server.
  - Test: Playwright gegen Staging mit selbst angelegtem Vergleich ohne Orte (Meldungstext, Adresse mit `tab=orte`, keine Schreibaufrufe) plus `node --test` auf `fehltFuerAktivierung('vergleich', …)` und `zielFuer`.

- **AC-5:** Given ein Orts-Vergleich-Entwurf, bei dem nur der Name fehlt bzw. Name und Orte fehlen / When die Seite die Aktivierung auswertet / Then lautet der Hinweis „Zum Aktivieren fehlt noch: ein Name.“ bzw. „Zum Aktivieren fehlen noch: Name und Orte.“, bei nur fehlendem Namen gibt es keine Navigation (der Name wird im Kopf bearbeitet), bei fehlenden Orten öffnet sich der Reiter Orte.
  - Test: `node --test` auf das Modell mit echten Vorlagen-Objekten (leerer Name, leere Ortsliste, beides) für Teile, Text und Ziel in DE und EN (im Staging-Konto lässt sich kein Vergleich ohne Namen anlegen).

- **AC-6:** Given ein Entwurf (Trip oder Orts-Vergleich) / When der Nutzer „Aktivieren“ einmal im Kopf und einmal im Kebab-Menü wählt / Then geschieht in beiden Fällen dasselbe (gleicher Hinweis, gleiche Stelle, kein Schreibzugriff), weil beide dieselbe Seitenfunktion aufrufen.
  - Test: Playwright gegen Staging in beiden Hubs (Kopf-Knopf und Kebab-Eintrag nacheinander, gleiche Meldung, gleiche Adresse, kein Schreibaufruf). Zusatz (`# doc-compliance-test`, kein Verhaltensnachweis): AST-Seitenbindung, dass der Kopf-Knopf `onAktivieren` und `handleHubAction`/`handleAction` für `activate` auf dieselbe Funktion zeigen.

- **AC-7:** Given ein Entwurf, bei dem der Nutzer das Fehlende in der geöffneten Seite ergänzt (Trip: Datum einer Etappe; Orte: einen Ort) / When der Entwurf dadurch aktiv wird und der Server einen nächsten Briefing-Termin nennt / Then zeigt der Kopf „Aktiviert. Das erste Briefing kommt {wann}.“ mit Wochentag, Datum, Uhrzeit und Zonenkürzel aus der Zustellung (Format wie die übrigen Anzeigen, z. B. „Do 29.10. 07:00 (CEST)“).
  - Test: Playwright gegen Staging in beiden Hubs (Daten über die Oberfläche ergänzen, Pill wechselt auf aktiv, Meldungstext passt zum Termin aus `GET /api/next-briefings`) plus Laufzeit-Test des Runen-Moduls mit dem echten Svelte-Client (Wechsel `draft → active` löst genau einen Abruf aus, Text enthält `formatNextBriefing`-Ausgabe).

- **AC-8:** Given der Wechsel von Entwurf auf aktiv / When die Quelle keinen Termin liefert (Abruf schlägt fehl, kein Eintrag, kein Termin vorhanden) / Then lautet die Meldung nur „Aktiviert.“, und es erscheint nie eine erfundene Uhrzeit.
  - Test: `node --test` auf `aktiviertText` mit `null`, `undefined`, `{ at: null, reason: 'none' }` und kaputtem Objekt (je „Aktiviert.“ in DE und EN) plus Laufzeit-Test des Runen-Moduls mit fehlschlagendem Abruf.

- **AC-9:** Given eine Seite, die beim Laden schon aktiv, pausiert oder archiviert ist, oder ein Zustandswechsel, der keine Aktivierung ist (aktiv → pausiert, Entwurf → archiviert, Archiv → aktiv) / When die Seite geladen wird bzw. der Wechsel passiert / Then erscheint keine „Aktiviert“-Meldung, und es geht kein zusätzlicher Abruf von „nächstes Briefing“ vom Kopf aus.
  - Test: `node --test` auf `warAktivierung` (alle Zustandspaare) und Laufzeit-Test des Runen-Moduls (kein Abruf beim ersten Lesen, kein Abruf bei anderen Wechseln) plus Playwright gegen Staging (aktiver Hub ohne Meldung, kein Aufruf von `/api/next-briefings` durch den Kopf beim Laden).

- **AC-10:** Given ein Orts-Vergleich-Entwurf bzw. ein Trip in jedem Zustand / When der Nutzer „Setup abschließen“, die Aktivierungskarte im Versand-Reiter, Pausieren, Fortsetzen, Archivieren, Reaktivieren oder Löschen benutzt / Then funktionieren sie wie vor dieser Änderung, einschließlich der Rückfragen aus #3442.
  - Test: bestehende Tests bleiben grün (`hub-kebab-rueckfragen.staging.spec.ts`, `kebab_seiten_bindung.test.ts`, `compare_hub_aktionen_verhalten.test.ts`, `trip_hub_aktionen_verhalten.test.ts`) plus Playwright gegen Staging („Setup abschließen“ sitzt im Vergleich-Entwurf auf dem Platz von „Test schicken“).

- **AC-11:** Given Sprache Deutsch oder Englisch am Nutzer / When Knopf, Menüeintrag, Hinweise und Meldungen erscheinen / Then stehen alle Texte im Katalog in beiden Sprachen („Aktivieren“ / „Activate“, die vier Hinweise, „Aktiviert.“ und die Meldung mit Termin), es gibt keinen hartkodierten Nutzertext, und der Termin kommt als Platzhalter.
  - Test: `node --test` Katalog-Parität DE/EN und `keine_hartkodierten_nutzertexte` plus Playwright gegen Staging in DE und EN (Knopftext, Hinweis).

- **AC-12:** Given Trip-Hub und Orts-Vergleich-Hub / When Knopf, Menüeintrag, Hinweis und Meldung angezeigt werden / Then stammen sie aus demselben Baustein (`HubKopf`, `subscriptionActions`, `entwurfAktivieren`, `aktivierungsWechsel`), und es gibt keine Compare-eigene Komponente und keinen Zweig nach `context`.
  - Test: Playwright gegen Staging in BEIDEN Hubs (Trip und Orte, je mit selbst angelegtem Entwurf): Knopf „Aktivieren“ neben der Pill und Menüeintrag „Aktivieren“ an erster Stelle sind sichtbar, der Klick zeigt in beiden Hubs denselben Hinweis nach demselben Muster. Zusatz (`# doc-compliance-test`, kein Verhaltensnachweis): AST-Seitenbindung (beide Seiten binden `onAktivieren` und `erstelleAktivierungsWechsel`, `HubKopf` ohne Zweig nach `context` für den Knopf) und bestehende Pendant-Prüfung (#1170).

- **AC-13:** Given die Elementliste für Trip und Orte / When der Abgleich gegen Staging mit einem Entwurf läuft / Then ist `kopf` mit Knopf „Aktivieren“ und `kebab-menue` mit „Aktivieren“ an Ordnung 1 gefunden, und der Knopf steht in der Elementliste ohne Abweichung zum Mockup.
  - Test: Playwright-Elementlisten-Abgleich (`elementliste-abgleich.staging.spec.ts`) gegen Staging mit einem selbst angelegten Entwurf, DE (Prüfkonto-Login, Seed-IDs).

## Definition of Done

- [ ] Knopf „Aktivieren“ neben der Status-Pill und erster Kebab-Eintrag „Aktivieren“ nur im Entwurf, Trip und Orte ein Code
- [ ] Klick nennt, was fehlt, und öffnet die Stelle; kein Schreibaufruf an den Server
- [ ] „Aktiviert. Das erste Briefing kommt …“ nur nach echtem Wechsel Entwurf → aktiv, Termin aus der Zustellung, nie erfunden
- [ ] DE/EN über den Katalog, Elementliste stimmt; Bestandstests umgestellt, nicht gelöscht
- [ ] Adversary-Verdict VERIFIED mit Mutations-Gegenprobe; alle 6 CI-Checks grün; Staging-E2E grün; ausgeliefert, Selftest grün

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht (deterministisch, `node --test`, kein Mock-Theater, echte Objekte statt Spiegel-Attrappen):

- [ ] Neu `shared/__tests__/entwurf_aktivieren.test.ts`: GIVEN echte `Trip`- und `ComparePreset`-Objekte (ohne Datum, mit Datum, leerer Name, leere Orte, beides) WHEN `fehltFuerAktivierung`, `hinweisFuer`, `zielFuer` THEN Teile, Katalogtext (DE/EN) und Ziel stimmen und decken sich mit `deriveTripStatus`/`deriveStatusFromPreset` (Konsistenz: Entwurf ⇔ Liste nicht leer); `warAktivierung` für alle Zustandspaare; `aktiviertText` mit Termin, ohne Termin, kaputtem Objekt (AC-3, AC-4, AC-5, AC-8, AC-9)
- [ ] Neu `shared/__tests__/aktivierungs_wechsel_laufzeit.test.ts` (echte Svelte-Client-Laufzeit wie `naechstes_briefing_lader_laufzeit.test.ts`): Wechsel `draft → active` löst genau einen Abruf und genau eine Meldung aus; kein Abruf beim ersten Lesen; Abruffehler ergibt „Aktiviert.“; späte ältere Antwort überschreibt keine neuere (AC-7, AC-8, AC-9)
- [ ] Neu `shared/__tests__/aktivieren_seiten_bindung.test.ts` (AST über `aktionsmodellAst.ts`, als Zusatz mit `# doc-compliance-test` gekennzeichnet, ersetzt keinen Verhaltensnachweis): beide Seiten binden `onAktivieren` und `erstelleAktivierungsWechsel`, Kopf-Knopf und Kebab rufen dieselbe Funktion, der Klickpfad enthält keinen Schreibaufruf (`setPaused`, `setArchived`, `deleteSubscription`, `api.put/patch/post`) (Zusatz zu AC-3, AC-6, AC-12)
- [ ] Umgestellt `shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts` (AC-5/AC-10 dort: heute „ist ein Link mit `href`“, neu „ist ein Knopf ohne `href`, Variante accent“; Katalog-Zeile bleibt), `shared/__tests__/aktionsmodell_seiten_bindung.test.ts` und die Hub-Aktionstests (Entwurf im Hub: `activate`, `delete`), Katalog-Parität für `aktionen.aktivieren.*` (AC-1, AC-2, AC-11)

E2E gegen Staging (Playwright, neu `frontend/e2e/hub-entwurf-aktivieren.staging.spec.ts`): AC-1 bis AC-4, AC-6, AC-7, AC-9, AC-10, AC-11, AC-12; Trip und Orts-Vergleich je mit selbst angelegtem Entwurf des Prüfkontos (siehe Implementation Details Punkt 8), Desktop und 390 px, Aufräumen am Ende. Umgestellt statt gelöscht: `frontend/e2e/hub-kopf-c2-mockup.staging.spec.ts` AC-5 (Klick auf „Aktivieren“ führt heute zu `tab=etappen` bzw. `tab=zustellung#versand`, neu: Hinweis und Reiter `etappen` bzw. `orte`). AC-13 über den bestehenden Elementlisten-Abgleich mit einem Entwurf.

## Scope (Affected Files)

| File | Change Type | LoC (ca.) | Description |
|------|-------------|-----------|-------------|
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | +10/-4 | Link `aktivierenHref` wird Knopf `onAktivieren` (accent, sm, testid `hub-kopf-aktivieren`) |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | MODIFY | +6/-6 | `onAktivieren` im Entwurf durchreichen, Ziel-Konstante entfällt |
| `frontend/src/lib/components/shared/subscriptionActions.ts` | MODIFY | +8/-2 | Aktion `activate`; Hub-Entwurf: `activate`, `delete` |
| `frontend/src/lib/components/shared/entwurfAktivieren.ts` | CREATE | +90 | Reines Modell: fehlende Teile, Hinweistext, Ziel, `warAktivierung`, `aktiviertText` |
| `frontend/src/lib/components/shared/aktivierungsWechsel.svelte.ts` | CREATE | +45 | Runen-Modul: Wechsel Entwurf → aktiv erkennen, nächstes Briefing einmal holen, Meldung |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | +30/-2 | `handleAktivieren`, `activate` im Menü, `erstelleAktivierungsWechsel`, Meldung |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | +32/-3 | wie Trip; Ziel `?tab=orte`; „Setup abschließen“ bleibt |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | MODIFY | +14 | Schlüssel `aktionen.aktivieren.*` (6 je Sprache; zählt als 2 Dateien) |
| `docs/context/einstellungen_neu/elementliste.json` | MODIFY | +/-0 | Prüfen/ergänzen: `kopf` Knopf „Aktivieren“, `kebab-menue` Ordnung 1 (Abgleich) |
| `docs/specs/modules/feat_2913_c2_seitenkopf.md`, `feat_3442_kebab_rueckfragen.md`, `feat_2278_aktionsmodell.md` | MODIFY | +3 | Changelog-Vermerk: Link wird Knopf, Entwurfs-Aktionsliste im Hub (3 Dateien) |
| `frontend/src/lib/components/shared/__tests__/entwurf_aktivieren.test.ts`, `aktivierungs_wechsel_laufzeit.test.ts`, `aktivieren_seiten_bindung.test.ts` | CREATE | +250 | Neue Kern-Tests |
| `frontend/e2e/hub-entwurf-aktivieren.staging.spec.ts` | CREATE | +150 | Staging-Test mit selbst angelegten Entwürfen |
| `hub_kopf_c2_mockup.test.ts`, `aktionsmodell_seiten_bindung.test.ts`, Hub-Aktionstests, `hub-kopf-c2-mockup.staging.spec.ts` | MODIFY | +/-40 | Umgestellte Bestandstests (4 Dateien) |

## Known Limitations

- Der Klick auf „Aktivieren“ schaltet keinen Entwurf ein, solange Daten fehlen; ein Zustand „vollständig, aber noch nicht aktiviert“ existiert im Datenmodell nicht. Ein expliziter Entwurfszustand (Variante A) wäre ein eigenes Issue, falls der PO ihn später wünscht.
- Der Termin in der Meldung entspricht dem Anzeigeformat der Zustellung (Wochentag, Datum, Uhrzeit, Zonenkürzel) und lautet nicht „morgen um 07:00“.
- Die Meldung „Aktiviert …“ erscheint nur, wenn der Wechsel in der geöffneten Sitzung geschieht; wer die Seite danach neu lädt, sieht sie nicht mehr.
- Auf Staging zeigt das Prüfkonto (aktiv angelegt) „Aktivieren“ nicht; die Abnahme braucht selbst angelegte Entwürfe.
- Ein Vergleich ohne Namen lässt sich über die Oberfläche nicht anlegen; dieser Fall ist nur im Kern-Test abgedeckt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (setzt ADR-0097, ADR-0110 Punkt 6 und die PO-Entscheidung vom 27.11.2026 aus #3443/#2797 um)
- **Rationale:** Die Entwurfs-Regel (abgeleiteter Zustand), „Trip und Orte ein Code“ und die Katalogtexte sind bereits entschieden. Diese Scheibe ersetzt einen Link durch einen Knopf, ergänzt einen Menüeintrag und zwei Meldungen; sie führt keinen neuen Zustand und keinen Schreibweg ein.

## Changelog

- 2026-11-27: Initial spec created (Issue #3443, Scheibe S5d von #2797, Epic #2791); Variante B laut PO-Entscheidung
