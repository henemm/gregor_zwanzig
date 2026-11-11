# Context: fix-2919-en-restbegriffe

## Request Summary
Bei Profilsprache `en` bleiben vier deutsche Texte stehen (Mobile-UX-Audit Runde 2, #2601): die Filterchips auf `/trips` und `/compare` („Alle/Aktiv/Geplant/Pausiert/Fertig"), der Status „AKTIV" auf den Trip- und Vergleichskarten, die Überschrift „AKTIONEN" im mobilen Aktionsblatt und der Logo-Untertitel „WETTER-BRIEFING" auf `/login` und den übrigen Seiten mit Logo. Die Behebung läuft nur über den Katalog (`docs/reference/i18n_konventionen.md`). Teil von Epic #2730.

## Related Files
| File | Relevance |
|------|-----------|
| frontend/src/lib/components/molecules/StatusFilterPills.svelte | `PILLEN`-Array mit hartkodierten deutschen Labels (Z. 15-21) |
| frontend/src/lib/components/organisms/SubscriptionCard.svelte | `statusText` (Z. 71-77) zeigt den rohen Wert von `HomeTripStatus` bzw. eine Literal-Map (`aktiv/pausiert/draft/archiviert`), CSS uppercase |
| frontend/src/lib/utils/tripStatus.ts | `tripStatus()` liefert deutsche Werte (`aktiv/geplant/fertig/draft/pausiert`). Das sind Logikwerte, die auch `activeOrNextTrip`, der Filter und die Zählung nutzen: **nicht** übersetzen, nur bei der Anzeige auf Katalogschlüssel abbilden |
| frontend/src/lib/components/shared/status-schild/StatusSchild.svelte | Vorbild: `LABEL_MAP` TripStatus → `trip.status.*`, `$t(...)` |
| frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte | `eyebrow="AKTIONEN"` hartkodiert (Z. 30) |
| frontend/src/lib/brand/BrandWordmark.svelte | Default `caption = 'V0.20 · Wetter-Briefing'` (Z. 17), über `Wordmark.svelte` auf `/login`, `/`, `/reset-password`, `/verify-email`, `/forgot-password`, `_start/Startseite` und in `BrandSidebar` |
| frontend/src/lib/components/ui/wordmark/Wordmark.svelte | Wrapper: übergibt `caption=undefined`, damit greift der Default |
| frontend/src/lib/i18n/messages/{de,en}/*.json | Katalog: `trip.status.*` gibt es schon (de/en). Für Filter „Alle", „Aktionen" und den Logo-Untertitel fehlen Schlüssel |
| frontend/src/lib/i18n/__tests__/hardcode_scan.ts + keine_hartkodierten_nutzertexte.test.ts | Hardcode-Ratsche: prüft Textknoten und nur die Attribute `title/aria-label/placeholder/alt/label`. `eyebrow=`, Default-Werte von Props und Literale in Objekt-Arrays rutschen durch, deshalb hat die Ratsche diese vier Stellen nicht gefunden |

## Existing Patterns
- Status-Name: `trip.status.*` mit `$t(...)` beim Rendern (StatusSchild, i18n F9).
- Aktionsnamen: `subscriptionActions()` per `tr()`, reaktiv über `void $locale`.
- Protokoll- und Logikwerte (`aktiv`, `geplant` …) bleiben unübersetzt, nur die Anzeige läuft über den Katalog (ADR-0104).

## Dependencies
- Upstream: `$lib/i18n` (`t`, `locale`, `tr`), Katalog-JSON de/en.
- Downstream: Trip- und Vergleichsliste (Filter, Karten), Startseite (Karten, Wordmark), Auth-Seiten (Wordmark), mobiles Aktionsblatt, BrandSidebar.

## Existing Specs
- docs/specs/modules/i18n_s4_ratsche_frontend_2649.md (Hardcode-Ratsche)
- docs/specs/modules/rework_2837_s1b_status_profil.md (StatusSchild)
- docs/reference/i18n_konventionen.md

## Risks & Considerations
- `HomeTripStatus`-Werte sind Logik (Filter, Hero-Auswahl, `data-status`-Selektoren in Tests/E2E): nur die Anzeige ändern, nicht die Werte.
- `data-field="status"`-Textinhalt wird ggf. in bestehenden Tests geprüft (de-Text „aktiv"): betroffene Tests mitziehen.
- Der Wordmark-Untertitel ist eine Marken-Caption („V0.20 · …"): Versionsteil bleibt, nur „Wetter-Briefing" → „Weather briefing".
- Die Lücke der Ratsche: sollte sie ausgeweitet werden (eyebrow, Prop-Defaults), damit die nächste Stelle dieser Art auffällt? In der Analyse entscheiden, inkl. Startstand (neue Treffer anderswo).
- Deutsch muss unverändert aussehen (Großschreibung per CSS bleibt).

## Analysis

### Type
Bug (i18n-Lücke: vier deutsche Restbegriffe bei Profilsprache `en`). Analyse direkt im Main Context (Scope: 6 Quelldateien, alle Stellen in /10-context bereits lokalisiert und hier nachgeprüft), daher keine Explore-/Plan-Subagenten.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/molecules/StatusFilterPills.svelte | MODIFY | `PILLEN` trägt Katalogschlüssel statt Text; Anzeige `$t(key)`. „Alle" → neuer Schlüssel `listen.filter.alle` (de „Alle"/en „All"); Aktiv/Geplant/Pausiert/Fertig → vorhandene `trip.status.active/planned/paused/finished` (de exakt „Aktiv/Geplant/Pausiert/Fertig", Groß-/Kleinschreibung unverändert) |
| frontend/src/lib/components/organisms/SubscriptionCard.svelte | MODIFY | `statusText` bleibt Logikwert; neue Anzeige-Abbildung Logikwert → `listen.status.*` (vorhanden: aktiv/geplant/pausiert/fertig/draft, de-Werte identisch klein geschrieben wie heute). Fehlt: `listen.status.archiviert` (de „archiviert", en „archived") → neu anlegen. `data-field="status"` zeigt `$t(...)` |
| frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte | MODIFY | `eyebrow={$t('aktionen.sheet.eyebrow')}`; neuer Schlüssel de „AKTIONEN", en „ACTIONS" |
| frontend/src/lib/brand/BrandWordmark.svelte | MODIFY | Default-Caption aus dem Katalog: Prop-Default `undefined` → Fallback `$t('nav.konto_sheet.version')` wiederverwenden ODER neuer Schlüssel `bausteine.wordmark.caption` (de „V0.20 · Wetter-Briefing", en „V0.20 · Weather briefing"). Empfehlung: neuer eigener Schlüssel (Bedeutung „Logo-Untertitel", nicht „Konto-Sheet-Version"); `caption={null}` (explizit ohne Caption) muss weiter funktionieren — Unterscheidung `undefined` vs `null` |
| frontend/src/lib/i18n/messages/{de,en}/listen.json, aktionen.json, bausteine.json | MODIFY | 4 neue Schlüssel je Sprache (`listen.filter.alle`, `listen.status.archiviert`, `aktionen.sheet.eyebrow`, `bausteine.wordmark.caption`) |
| frontend/src/lib/i18n/__tests__/hardcode_scan.ts | MODIFY | Ratsche: Attributliste um `eyebrow` erweitern (Startstand gemessen: außerhalb `_design-system` genau 1 Treffer = SubscriptionActionSheet, wird hier behoben) |
| frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts | MODIFY | neue Schlüssel in die DE-Unverändert-Liste |
| frontend/src/lib/components/organisms/__tests__/subscription_card.test.ts | MODIFY | Pillen-Test für `en` ergänzen; de-Erwartung `Alle (9)…` bleibt |

### Scope Assessment
- Files: ~8 Quell-/Katalogdateien + 1–2 Testdateien
- Estimated LoC: +60/-15
- Risk Level: LOW

### Technical Approach
- Logikwerte (`aktiv`, `geplant`, `all`, `HomeTripStatus`, `data-testid`, `data-status`) bleiben unverändert (ADR-0104); nur die Anzeige läuft über `$t(...)`.
- Deutsch bleibt pixelgleich: Filterchips bekommen exakt dieselben Wörter (Großschreibung wie heute), Kartenstatus behält Kleinschreibung (`listen.status.*`) + CSS-uppercase, Eyebrow bleibt „AKTIONEN", Wordmark bleibt „V0.20 · Wetter-Briefing".
- Prop-Default in BrandWordmark: Katalogtext reaktiv (`$t`) zur Renderzeit auflösen, nicht als statischer Default (sonst kein Sprachwechsel).
- Ratsche: nur `eyebrow` ergänzen (billig, null Altlast). Prop-Defaults und Literale in Objekt-Arrays generisch zu erkennen ist teuer und fehleranfällig (Logikwerte wie `'aktiv'` sähen identisch aus) → nicht in diesem Ticket; abgedeckt durch Verhaltenstests (en-Rendering der vier Stellen).
- Nachweis: Komponententests rendern mit `locale=en` und erwarten „All/Active/Planned/Paused/Finished", Kartenstatus „active", Eyebrow „ACTIONS", Caption „V0.20 · Weather briefing"; mit `de` die heutigen Texte.

### Dependencies
- `$lib/i18n` (`t`, `locale`), Katalog de/en, Typ-Ableitung `MessageKey` (neue Schlüssel in beiden Sprachen nötig, Paritätstest).
- Downstream: /trips, /compare, Startseite (Karten), Auth-Seiten + Startseite + BrandSidebar (Wordmark), mobiles Aktionsblatt.
- E2E `hub-list-menu.spec.ts` sucht `· aktiv` (de-Text, Kleinschreibung) → bleibt gültig, weil de-Wert „aktiv" unverändert.

### Open Questions
- keine (alle Entscheidungen technisch; Deutsch bleibt unverändert, Englisch folgt dem Katalog)
