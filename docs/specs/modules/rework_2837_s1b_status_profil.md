---
entity_id: rework_2837_s1b_status_profil
type: feature
created: 2026-11-08
updated: 2026-11-08
status: draft
version: "1.0"
workflow: rework-2837-s1b-status-profil
tags: [epic-2345, trip-compare-teilung, hub-kopf, status-schild, profil, shared, paritaet, frontend-only, dod-2]
---

# Nachbesserung S1b: ein gemeinsames Status-Schild und Profil in der Titel-Unterzeile (Issue #2837, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Die Staging-Abnahme von Scheibe S1 (Spec `rework_2837_s1_hub_kopf.md`, PR #2839, AC-15) am 2026-11-07 fand zwei sichtbare Unterschiede zwischen Trip-Hub und Vergleichs-Hub außerhalb der erlaubten Whitelist:

1. **Status-Schild:** Der Trip zeigt „PAUSIERT" in Großbuchstaben mit gelber Umrandung, der Vergleich „pausiert" in Kleinbuchstaben mit grauer Umrandung; ein aktiver Vergleich ist orange gefüllt. Es gibt dafür zwei Bausteine (`TripStatusBadge`, `CompareStatusPill`) für dasselbe Element.
2. **Profil in der Zeile unter dem Titel:** Der Vergleich zeigt „— ✎ · Wandern · 2 Orte", der Trip nur „— ✎", weil `TripHeader` dem Kopf kein Profil-Label übergibt.

Diese Spec ersetzt beide Status-Bausteine durch **einen** (`shared/status-schild/StatusSchild.svelte`), lässt den Trip das Profil wie der Vergleich zeigen und verlangt danach eine **neue** Staging-Abnahme (Fresh-Eyes-Paar). Sie **korrigiert Entscheidung 5 der S1-Spec** („Vergleich unverändert (`CompareStatusPill` + Laufzeit)") per Verweis; die S1-Spec selbst bleibt unverändert (Spec-Freeze). Alle übrigen S1-Entscheidungen, insbesondere 8 (Whitelist) und 10 (Testids), gelten weiter.

Das Issue #2837 bleibt offen, bis auch S2 (Anlege-Rahmen) geliefert ist.

## Entscheidungen zur Freigabe

Zur Freigabe in einfachem Deutsch. „Vorher" ist, was der Nutzer heute sieht, „Nachher" nach dem Umbau.

| Nr. | Thema | Vorher | Nachher | Warum |
|---|---|---|---|---|
| a | **Ein Baustein für das Status-Schild** | Trip und Vergleich haben je ein eigenes Schild (zwei Bausteine) | **Ein** gemeinsames Status-Schild für beide. Die beiden alten Bausteine entfallen ganz | PO-Vorgabe „möglichst viel Code teilen" (ADR-0097, ADR-0110 Punkt 4: Status als Schild in der Titelzeile bei beiden Arten). Gleicher Zustand ⇒ gleiches Schild. |
| b | **Optik: umrandet, nicht gefüllt** | Trip: Pill umrandet (pausiert gelb). Vergleich: aktiv orange **gefüllt**, pausiert/Entwurf grau umrandet | Bei beiden die umrandete Pill. **Vergleich aktiv wird umrandet statt gefüllt**, **Vergleich pausiert wird gelb** (dunkles Gelb-Braun) statt grau | Beide heutigen Optiken fallen teilweise durch die Lesbarkeits-Grenze von 4,5 zu 1 (WCAG-AA): Weiß auf dem Orange des gefüllten Vergleichs-Aktiv hat 4,34 zu 1, das gelbe Trip-Pausiert 2,77 zu 1 auf Papier. Die umrandete Pill mit dunklem Gelb-Braun besteht überall (siehe Kontrast-Tabelle). Das folgt Ihrem Leitprinzip „Hoher Kontrast gewinnt gegen weiche Optik". |
| c | **Texte und Schreibung** | Trip „PAUSIERT" (Katalog `trip.status.*`), Vergleich „pausiert" und „draft" (Katalog `listen.status.*`) | Bei beiden dieselben Texte aus `trip.status.*`, bei beiden dieselbe Großschreibung. Der Vergleich zeigt **„Entwurf"** statt „draft" | Gleicher Zustand ⇒ gleicher Text in gleicher Schreibung. Der Trip hat sechs Zustände, der Vergleich drei davon (Aktiv, Pausiert, Entwurf), also ist der Trip-Katalog die Obermenge. |
| d | **Profil bei beiden in der Unterzeile** | Vergleich „— ✎ · Wandern · 2 Orte", Trip „— ✎" | Trip „— ✎ · Trekking" (Profil = Aktivität des Trips). Hat der Trip keine Aktivität, steht kein Zusatz da (wie beim Vergleich ohne Profil) | Eine Zeile, ein Aufbau (S1 AC-9). |
| e | **Testid bleibt** | `trip-detail-status-badge` am Trip, `data-status` nur am Vergleich | `trip-detail-status-badge` bleibt an beiden Arten; `data-status` steht bei beiden | Bestehende Tests und Selektoren bleiben stabil (S1 Entscheidung 10). |

**Was bewusst bleibt:** Die Übersichts-Kachel zeigt bei einem aktiven Vergleich „läuft automatisch", der Kopf „Aktiv". Das ist eine bestehende, bewusste Abweichung (fachlicher Zusatz der Kachel) und nicht Teil dieser Nachbesserung.

### Kontrast (gemessen, WCAG-AA 4,5:1 für 11-px-Text; die App hat keine Dunkel-Tokens)

| Zustand / Variante | Textfarbe | auf Papier `--g-paper` #f6f4ee | auf Karte #fff | AA |
|---|---|---|---|---|
| Trip pausiert **heute** (umrandet, `--g-warning`) | #c08a1a | 2,77 | 3,05 | **fällt durch** |
| Pausiert **neu** (`--g-warn-deep`) | #8a6210 | 4,98 | 5,48 | besteht |
| Entwurf / Fertig / Archiviert (umrandet, neutral) | #5c5a52 | 6,28 | 6,91 | besteht |
| Geplant (umrandet, Info) | #2c5a8c | 6,48 | 7,12 | besteht |
| Aktiv (umrandet, `--g-accent-deep`) | #8c3e1a | 6,77 | 7,45 | besteht |
| Vergleich aktiv **heute** (Weiß auf `--g-accent` #c45a2a gefüllt) | #fff | 4,34 | – | **fällt durch** |
| Vergleich pausiert/Entwurf heute (`--g-ink-3`) | #6b675c | 5,13 | 5,65 | besteht |

## Source

- **Neu (Pfade relativ zu `frontend/src/lib/components/`):** `shared/status-schild/StatusSchild.svelte` (Name verbindlich; **neue Datei ausschließlich unter `shared/`**, Pendant-Sperre, `docs/reference/gates_und_ratschen.md`). Inhalt: `ui/pill/Pill` mit `data-outlined`, Prop `status: TripStatus` (die drei Vergleichs-Zustände `active|paused|draft` sind eine Teilmenge), Prop `testid`, `data-status`, Zuordnung Zustand ⇒ Tone und Label (TONE_MAP/LABEL_MAP), Labels `trip.status.*`.
- **Gelöscht:** `trip-detail/TripStatusBadge.svelte`, `compare/CompareStatusPill.svelte` (Inline-Styling-Altlast #488). Exporte in `trip-detail/index.ts` und `molecules/index.ts` entfallen.
- **Geändert:**
  - `trip-detail/TripHeader.svelte`: ruft `deriveTripStatus` selbst auf, bindet `StatusSchild` mit Testid `trip-detail-status-badge` ein; leitet `profileLabel` aus `aktivitaeten.find(o => o.value === trip.activity)?.label` ab und übergibt es an `HubKopf` (Ursache: bisher nur `profile` und `profileOptions` übergeben, `:136-158`).
  - `frontend/src/routes/compare/[id]/+page.svelte`: `StatusSchild` statt `CompareStatusPill` im Snippet `statusBadge` (`:357-362`); der Laufzeit-Hinweis `runtime-exceeded-hint` bleibt.
  - `frontend/src/app.css:495`: Regel `[data-slot=pill][data-outlined][data-tone=warning]`, Textfarbe `--g-warning` ⇒ `--g-warn-deep`. **Das ist eine Änderung einer Design-Token-Regel**, bewusst global, damit das Design-System-Atom `Pill` selbst AA-fest ist (die einzige produktive `data-outlined`-Nutzung ist das Status-Schild, sonst nur die Demo-Seite `routes/_design`). Im Commit wird sie als Token-Regel-Änderung benannt.
  - `compare/subscriptionHelpers.ts`: `STATUS_MAP` bleibt (Listen-Punkte und Kacheln nutzen es), nur der Pillen-Verbraucher entfällt.
- **Unverändert wiederverwendet:** `ui/pill/Pill.svelte`, `shared/hub-kopf/HubKopf.svelte` (reicht `profileLabel` bereits durch, `:42,61,99`), `shared/subscription-header/SubscriptionHeader.svelte` (rendert `· {profileLabel}` nur, wenn gesetzt, `:139`), `deriveTripStatus`.

> **Schicht-Hinweis:** ausschließlich **Frontend** (SvelteKit). Kein Go-, kein Python-Code, kein Datenmodell, kein Endpunkt.

> **Trip/Ortsvergleich-Teilung:** Kern dieser Nachbesserung. Der Baustein liegt unter `shared/status-schild/`; beide Alt-Bausteine (Trip- und Compare-Pendant) entfallen, danach 0 Importeure. Die Pendant-Sperre ist erfüllt, nicht umgangen.
> **Mandantentrennung:** reine Oberfläche, kein datenbewegender Endpunkt, kein Zwei-Nutzer-Test nötig; `user_id`-Pfade bleiben unberührt.
> **Kanäle:** nicht betroffen (keine Briefing- oder Alarm-Inhalte).

## Scope (Estimated Scope)

- **LoC:** ca. +200/-130 insgesamt; Produktcode ca. +50/-110, der Rest Tests.
- **Files:** ca. 6 Produktdateien (1 neu, 2 gelöscht, 3 bis 4 geändert, dazu `app.css`), ca. 12 Unit-Tests, 2 bis 3 E2E-Dateien, 1 Spec.
- **Effort:** medium. **Risiko:** LOW bis MEDIUM (isolierter Kopf-Bereich; das Risiko liegt in der Breite der Test-Umhängung und der sichtbaren Optik-Änderung beim Vergleich).
- **Deploy-Scope:** frontend-only (kein Go-/Python-Dienst, kein Datenmodell).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ui/pill/Pill.svelte` | component | Design-System-Atom mit `tone` und `data-outlined`, Grundlage des Schilds |
| `deriveTripStatus` | function | leitet den Trip-Zustand (6 Werte) ab; der Vergleich liefert `active|paused|draft` |
| `lib/i18n` Katalog (`trip.json`, de und en) | module | Status-Texte `trip.status.*` |
| `shared/hub-kopf/HubKopf.svelte`, `shared/subscription-header/SubscriptionHeader.svelte` | component | nehmen Schild (`status`-Snippet) und `profileLabel` auf |
| `ACTIVITY_TYPE_OPTIONS` / `aktivitaeten` | data | Quelle für das Profil-Label des Trips |
| `frontend/src/app.css` | stylesheet | Token-Regel für umrandete Warn-Pill |

## Implementation Details

Reihenfolge, damit jeder Zwischenstand grün bleibt:

1. **`StatusSchild`** anlegen (Pill, Tone-Zuordnung, Labels, `data-status`, Testid-Prop) samt Atomtest.
2. **`app.css`:** Warn-Textfarbe der umrandeten Pill auf `--g-warn-deep`.
3. **Trip:** `TripHeader` auf `StatusSchild` umstellen, `profileLabel` ableiten und übergeben.
4. **Vergleich:** Seite auf `StatusSchild` umstellen, Laufzeit-Hinweis unverändert.
5. **Alt-Bausteine löschen** (`TripStatusBadge`, `CompareStatusPill`), Exporte entfernen; `grep` auf 0 Importeure.
6. **Tests umhängen** (siehe Test Plan), i18n-Katalog de und en vollständig.

Zuordnung Zustand ⇒ Tone und Text (Texte aus `trip.status.*`, Schreibung per CSS-Großschrift bei allen gleich):

| Zustand | Tone | Umrandung/Textfarbe |
|---|---|---|
| Entwurf | neutral (default) | neutral, #5c5a52 |
| Geplant | info | blau, #2c5a8c |
| Aktiv | accent | orange-dunkel, #8c3e1a, umrandet (nicht gefüllt) |
| Pausiert | warning | `--g-warn-deep` #8a6210 |
| Fertig | neutral (default) | neutral, #5c5a52 |
| Archiviert | neutral (default) | neutral, #5c5a52 |

**i18n-Regeln (ADR-0104):** Status-Texte ausschließlich aus dem Katalog `trip.status.*`, de und en vollständig (alle sechs Zustände). Kein neuer hartkodierter Nutzertext; `keine_hartkodierten_nutzertexte.test.ts` bleibt grün. Das Profil-Label stammt aus dem bestehenden Aktivitäts-Katalog. Protokoll-Token bleiben unübersetzt.

## Expected Behavior

- **Input:** Zustand des Trips (sechs Werte) bzw. des Vergleichs (drei Werte), `trip.activity` bzw. Vergleichs-Profil.
- **Output:** In der Titelzeile ein Status-Schild, das bei gleichem Zustand auf beiden Hubs identisch aussieht (Text, Schreibung, Farbe, Umrandung); in der Unterzeile Region, Speicher-Zeichen und Profil in gleichem Aufbau.
- **Side effects:** keine. Listen-Punkte, Kachel-Texte und `STATUS_MAP` bleiben unverändert.

## Test Plan

Regeln: keine Mocks, die nur die eigene Annahme spiegeln; Quelltext-Greps gelten nicht als Verhaltensnachweis (Ausnahme `# doc-compliance-test`). Bestehende Tests werden **umgehängt, nicht gelöscht**; keine Zusicherung wird gelockert.

### Unit (`node --test`)

- Atomtest `StatusSchild` (aus `TripStatusBadge.atomic.test.ts` umbenannt und erweitert): alle sechs Zustände rendern den erwarteten Tone und den Katalogtext in de und en; `data-status` und `data-outlined` gesetzt; Testid-Prop wird durchgereicht.
- Paritätstest: gleicher Zustand, einmal als Trip und einmal als Vergleich gerendert, ergibt dasselbe Markup (Text, Tone, Attribute).
- Trip-Profil: `TripHeader` mit Aktivität liefert `profileLabel` an `HubKopf`; ohne Aktivität bleibt die Zeile ohne Zusatz.
- Keine Importeure: `CompareStatusPill` und `TripStatusBadge` werden produktiv nirgends mehr importiert (Import-Auflösung, kein String-Grep als Verhaltensnachweis).

### Umzuhängende Tests (Inventar aus dem Kontext)

| Datei | Umhängung |
|---|---|
| `shared/hub-uebersicht/__tests__/hub_uebersicht_modell.test.ts:469`, `hub_uebersicht_trip_ssr.test.ts:62,321` | Prop `trip` ⇒ `status` |
| `trip-detail/__tests__/tripStatusFinishedDraft.test.ts:26` | Source-Inspection auf TONE_MAP/LABEL_MAP zeigt auf die neue Datei `StatusSchild.svelte` |
| `trip-detail/TripStatusBadge.atomic.test.ts` | umbenennen auf `StatusSchild`, an neuen Pfad binden |
| `shared/hub-kopf/__tests__/hub_kopf_seiten_paritaet.test.ts:71`, `hub_kopf_baustein.test.ts` | Status-Schild und Profil-Zeile je Seite prüfen |
| `trip-detail/__tests__/f9Pruefstand.ts`, `compare/__tests__/f10Pruefstand.ts:136,241` | Importpfade und Selektoren |
| `compare/compare_detail.test.ts:67`, `compare/__tests__/issue_491_compare_detail.test.ts:54-59` | verlangten bisher den String „CompareStatusPill" ⇒ umdrehen auf `StatusSchild`/Testid |
| `lib/issue_577_atoms_design_fidelity.test.ts` | Atom-Fidelity auf `StatusSchild` |

### E2E (Playwright)

- `hub-versand-inline-bearbeiten.spec.ts:133,281-284`: Der Trip hat jetzt auch `data-status`; Kommentar und `.first()`-Locator prüfen.
- `trip-detail-actions.spec.ts:74-77`: Kommentare nachziehen.
- Weitere Suiten mit Status-Selektoren auf Weiterlauf prüfen: `issue-336-status-dedup`, `compare-hub-fidelity-s8c`, `design-system-lauf-b`, `accent-ctas`, `forms-dialogs-btn-migration`.
- Paritäts-Suite `hub-kopf-paritaet-compare-trip` erweitern: Status-Schild (Text, Schreibung, berechnete Farben, Umrandung) und Profil-Zeile je Zustand per `HUB_KINDS`-Schleife bei 1440 und 390 px.

### Mutationen (Pflicht, Adversary)

- Vergleich wieder auf eigenes Schild/gefüllt ⇒ Paritätstest rot.
- Pausiert-Textfarbe wieder `--g-warning` ⇒ Kontrast-Test rot.
- `profileLabel` im Trip weglassen ⇒ Profil-Test rot.
- Eine Verfälschung, die kein Test fängt, ist ein Finding.

## Acceptance Criteria

- **AC-1:** Given ein Trip und ein Ortsvergleich im selben Zustand (zum Beispiel beide pausiert) / When der Nutzer jeweils die Detailseite öffnet / Then zeigt das Status-Schild in der Titelzeile bei beiden denselben Text in derselben Schreibung, dieselbe Schriftfarbe und dieselbe Umrandung.
  - Test: E2E `HUB_KINDS`-Schleife bei 1440 und 390 px: sichtbarer Text, berechnete Schrift- und Randfarbe des Schilds gleich; Unit-Paritätstest gleicher Zustand ⇒ gleiches Markup.
- **AC-2:** Given ein Trip in jedem der sechs Zustände Entwurf, Geplant, Aktiv, Pausiert, Fertig, Archiviert / When der Nutzer den Trip-Hub öffnet / Then zeigt das Schild den jeweiligen Zustand mit der Zuordnung Entwurf, Fertig und Archiviert neutral, Geplant blau (Info), Aktiv orange-dunkel umrandet, Pausiert gelb-braun.
  - Test: Unit-Atomtest über alle sechs Zustände (Tone und Text, de und en); E2E für mindestens Aktiv, Pausiert und Entwurf mit berechneten Farben.
- **AC-3:** Given ein Ortsvergleich im Zustand Entwurf / When der Nutzer den Vergleichs-Hub öffnet / Then steht im Schild „Entwurf" (in derselben Großschreibung wie beim Trip) und nicht mehr „draft".
  - Test: E2E am Vergleich im Entwurf: Text des Schilds gleich dem Text des Trip-Entwurfs; kein Element mit dem englischen Wort „draft" im Kopf.
- **AC-4:** Given ein pausierter Trip oder Vergleich auf Papier- und auf Kartenhintergrund / When der Nutzer das Schild betrachtet / Then ist die Schrift dunkles Gelb-Braun (#8a6210) und erreicht mindestens 4,5 zu 1 Kontrast (gemessen 4,98 auf Papier, 5,48 auf Karte).
  - Test: E2E misst berechnete Schriftfarbe und Hintergrund und rechnet das Kontrastverhältnis nach (Schwelle 4,5); Unit-Test der Token-Regel `data-outlined` + `data-tone=warning` aus Nutzersicht über das gerenderte Schild.
- **AC-5:** Given ein aktiver Ortsvergleich / When der Nutzer den Vergleichs-Hub öffnet / Then ist das Aktiv-Schild umrandet mit dunkel-orangener Schrift (#8c3e1a, mindestens 4,5 zu 1) und nicht mehr orange gefüllt mit weißer Schrift (die alte Füllung hatte nur 4,34 zu 1).
  - Test: E2E: berechneter Hintergrund des Schilds ist transparent bzw. Seitenfarbe, nicht `--g-accent`; Kontrast Schrift zu Grund mindestens 4,5.
- **AC-6:** Given ein Trip mit gesetzter Aktivität (zum Beispiel Trekking) / When der Nutzer den Trip-Hub öffnet / Then steht in der Zeile unter dem Titel das Profil wie beim Vergleich, zum Beispiel „— ✎ · Trekking".
  - Test: E2E `HUB_KINDS`: Unterzeile des Trips enthält Region-Platzhalter, Speicher-Zeichen und das Aktivitäts-Label in derselben Reihenfolge wie beim Vergleich.
- **AC-7:** Given ein Trip ohne gesetzte Aktivität / When der Nutzer den Trip-Hub öffnet / Then steht in der Unterzeile kein Zusatz hinter „— ✎", genau wie beim Vergleich ohne Profil.
  - Test: Unit/E2E: Trip ohne `activity` ⇒ kein „·"-Zusatz im Titelblock; Vergleich ohne Profil identisch.
- **AC-8:** Given Trip und Ortsvergleich / When der Nutzer das Schild anspricht oder testet / Then trägt es bei beiden die Testid `trip-detail-status-badge` und das Attribut `data-status` mit dem Zustandswert.
  - Test: E2E `HUB_KINDS`: `[data-testid=trip-detail-status-badge]` existiert genau einmal je Hub und hat `data-status`; bisherige Tests, die diese Testid nutzen, bleiben grün.
- **AC-9:** Given die Umsetzung / When der Quellbaum geprüft wird / Then gibt es genau einen Status-Schild-Baustein unter `shared/status-schild/`, `TripStatusBadge` und `CompareStatusPill` existieren nicht mehr, und kein produktiver Code importiert sie (0 Importeure).
  - Test: Unit-Test auf Dateiexistenz und Import-Auflösung (Pendant-Sperre); `molecules/index.ts` und `trip-detail/index.ts` exportieren sie nicht mehr; Build und `svelte-check` grün.
- **AC-10:** Given ein Ortsvergleich, dessen Laufzeit überschritten ist / When der Nutzer den Vergleichs-Hub öffnet / Then steht neben dem Schild weiterhin der Laufzeit-Hinweis (`runtime-exceeded-hint`) unverändert.
  - Test: bestehender E2E/Unit-Test zu `runtime-exceeded-hint` bleibt grün, am neuen Schild geprüft.
- **AC-11:** Given die Oberfläche auf Deutsch und auf Englisch / When der Nutzer Trip- und Vergleichs-Hub öffnet / Then erscheinen alle sechs Status-Texte in der jeweiligen Sprache aus dem Katalog `trip.status.*`, ohne hartkodierte Texte.
  - Test: E2E mit Nutzersprache de und en für beide Arten; `keine_hartkodierten_nutzertexte.test.ts` grün; Katalogtest: alle sechs Schlüssel in de und en vorhanden.
- **AC-12:** Given Listen und Kacheln (Vergleichs-Liste, Cockpit-Kacheln, Übersichts-Kachel mit „läuft automatisch") / When S1b geliefert ist / Then sind deren Status-Punkte, Texte und `STATUS_MAP` unverändert, und die Übersichts-Kachel sagt bei aktivem Vergleich weiterhin „läuft automatisch", während der Kopf „Aktiv" zeigt.
  - Test: bestehende Listen-/Kachel-Tests unverändert grün; Diff-Prüfung in /60: keine Änderung an `STATUS_MAP`-Verbrauchern außer dem Wegfall der Pille.
- **AC-13:** Given die Nachbesserung ist auf Staging / When ein Fresh-Eyes-Prüfer ohne Vorwissen das Screenshot-Paar Hub-Kopf Desktop 1440 px und Mobil 390 px (Trip gegen Vergleich) im selben Zustand vergleicht / Then findet er keinen Unterschied außerhalb der Whitelist der S1-Spec (Datum, Kürzel, km/Hm, „Tag x von y", Kacheln, Orte-Anzahl, Entwurfs-Regel), und das Paar liegt als Kommentar im Epic #2345.
  - Test: `fresh-eyes-inspector` ohne Bug-Kontext auf vier Screenshots (2 Breiten x 2 Arten, beide im selben Zustand); Ergebnis und Bilder als Kommentar im Epic #2345; Issue #2837 bleibt bis S2 offen.

## Definition of Done

- AC-1 bis AC-13 erfüllt, jedes AC mit grünem Test aus dem Test Plan; alle umgehängten Tests bestehen, keiner gelöscht.
- Pflicht-Mutationen werden von mindestens einem Test gefangen (Adversary-Verdict VERIFIED).
- Pull Request mit allen 6 CI-Checks grün gemergt, `/e2e-verify` gegen Staging bestanden, Prod-Deploy mit Selftest-Exit 0 (Deploy-Scope frontend-only).
- Neues Fresh-Eyes-Paar (Desktop 1440 / Mobil 390) als Kommentar in Epic #2345.
- Issue #2837 bleibt offen, bis S2 geliefert ist.

## Known Limitations

- **Bewusste Abweichung bleibt:** Übersichts-Kachel „läuft automatisch" gegenüber Kopf „Aktiv" bei aktivem Vergleich (fachlicher Zusatz der Kachel, nicht Teil dieser Nachbesserung).
- **Listen-Punkte und `STATUS_MAP`** bleiben unberührt (kein Schild, eigene Darstellung).
- **Nebenbefund für #1199:** `listen.status.draft` lautet im deutschen Katalog „draft" (englisch). Das betrifft die Listen-Punkte, nicht den Kopf, und wird dort als Nebenbefund erfasst, nicht hier behoben.
- **Globale `app.css`-Änderung:** wirkt auch auf die Demo-Seite `routes/_design`, sonst gibt es keine weitere produktive `data-outlined`-Nutzung.
- Die App hat keine Dunkel-Tokens; die Kontrastangaben gelten für das helle Design.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Gedeckt durch ADR-0110 Punkt 4 („Status als Badge in der Titelzeile bei beiden Arten"), ADR-0097 (Trip/Ortsvergleich-Teilung) und ADR-0104 (Katalog, zweisprachig).
- **Rationale:** Die Nachbesserung setzt die bereits getroffene Entscheidung (ein Baustein) konsequent um und korrigiert nur die Umsetzungsentscheidung 5 der S1-Spec („Vergleich unverändert"). Die Korrektur steht in dieser Spec per Verweis; die S1-Spec bleibt wegen Spec-Freeze unverändert.

## Changelog

- 2026-11-08: Initial spec created (Issue #2837, Epic #2345, Nachbesserung S1b nach gescheiterter Staging-Abnahme AC-15 vom 2026-11-07; korrigiert S1-Entscheidung 5)
