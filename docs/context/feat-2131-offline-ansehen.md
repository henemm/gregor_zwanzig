# Context: feat-2131-offline-ansehen

Issue: [#2131](https://github.com/henemm/gregor_zwanzig/issues/2131) — Scheibe 4 zu Epic #2127
Vorgänger: #2128 (Scheibe 1, geschlossen, in `main`) · ADR-0061 · Spec `docs/specs/modules/pwa_installierbar_offline_start.md`
Track: Full Process (Intake-Score 6/6)

## Request Summary

Ohne Netz soll die App die zuletzt geladenen Inhalte (Trips, Briefings, Ortsvergleiche) weiter
anzeigen — jede so angezeigte Ansicht sichtbar mit ihrem Stand („Stand: 05.09., 06:12 — offline"),
Bearbeitungsflächen erkennbar gesperrt, Alarme gar nicht zwischengespeichert, der Gerätespeicher
mandantengetrennt und beim Abmelden geleert. Nur Ansehen — kein Bearbeiten, kein Puffern von
Änderungen (PO-Entscheid 2026-09-05).

## Related Files

### PWA-Schicht (Bestand aus #2128)

| Datei | Relevanz |
|---|---|
| `frontend/src/service-worker.ts` | Handgeführter Worker, 180 Z. **Regel 1 (`:140`) verbietet heute jede Berührung von `/api/*`**, Regel 3 (`:145`) liefert Seitenaufrufe nur aus dem Netz und legt HTML **nie** ab (`:111-116` nennt #2131 als die Scheibe, die das ändert). Genau ein Cache `gz-${version}` (`:30`), Precache = `build` + `files` (`:33`). |
| `frontend/src/lib/pwa/geraetespeicher.ts` | Räumen beim Abmelden — `raeumeGeraetespeicher()` (`:173`) löscht **alle** Cache-Buckets (`caches.keys()`) + Worker-Registrierungen, mit gemessener Nachkontrolle. Kennt **kein** localStorage und **kein** IndexedDB (`:104-146`). |
| `frontend/src/lib/pwa/serviceWorkerUpdate.ts` | Update-erst-auf-Nachfrage; `SKIP_WAITING`-Botschaft, genau ein Reload. |
| `frontend/src/routes/login/+page.svelte:22-29` | Einziger Ort, an dem geräumt wird — nur wenn `abmeldungLiegtVor($page.url)`. |
| `frontend/static/offline.html` | Eigenständige Offline-Seite, Inline-CSS, kein Zeitstempel, kein Link auf zwischengespeicherte Inhalte. |

### Datenabruf-Nähte

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/api.ts:61` | Naht A — einziger `fetch()` in `send()`; 401-Umleiter `:66-79`. Aber **nicht alle** Browser-Abrufe laufen hier durch (rohe `fetch()` u. a. in `routes/trips/+page.svelte:176,195,213`, `routes/compare/[id]/+page.svelte:183,238,252`, `lib/components/shared/AlarmeTab.svelte:122`). |
| `frontend/src/routes/**/+page.server.ts` | Naht B — **alle** Erstladungen sind SSR-Loader gegen `apiBase()` (Server-zu-Server). Es gibt **kein einziges `+page.ts`** im Repo. |
| `frontend/src/routes/api/[...path]/+server.ts:5-42` | Naht C — Catch-all-Proxy, reicht alle Antwort-Header durch (`:24-29`). Die eine serverseitige Stelle für einen Cachebarkeits-Marker. |
| `frontend/src/service-worker.ts:133` | Die einzige Stelle, die **jede** browserseitige API-Anfrage sieht. |

### Nutzer-Identität

| Datei | Relevanz |
|---|---|
| `frontend/src/hooks.server.ts:31` | `event.locals.userId` aus signiertem Cookie `gz_session`. |
| `frontend/src/routes/+layout.server.ts:18-21` | Gibt `userId` an **jede** Seite → im Browser als `page.data.userId`. |
| — | Der Service Worker sieht `page.data` **nicht**. Entweder `postMessage` an den Worker oder Ablage im Seitenkontext. |

### Bearbeitungsflächen und Sperr-Muster

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | Geteilter Speicher-Controller (`idle\|dirty\|saving\|error\|conflict`), 700-ms-Debounce (`:169`), `flush()` (`:181`). Instanziiert in `routes/trips/[id]/+page.svelte:39` und `routes/compare/[id]/+page.svelte:50`. **Die natürliche Ankerstelle für ein Offline-Gate.** |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | Dauerhaft sichtbare Zustandsanzeige, nie `display:none` (Barrierefreiheit). |
| `frontend/src/lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts:37-47` | **Vorlage für ein Offline-Gate:** reine Funktion → `{ disabled, hint }`, fail-closed mit ehrlichem Grund. |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte:40-43,140-152` | Vorlage für „gesperrt **mit** Begründung, nicht versteckt". Kommentar dort: „versteckt wäre vorgespiegelte Abwesenheit statt ehrlicher Sperre". |
| `frontend/src/lib/components/trip-detail/weatherSaveGate.ts:39-43` | Zweites Gate-als-pure-Funktion-Vorbild. |
| Flächen mit eigenem Knopf statt Controller | `WeatherMetricsTab.svelte:1477-1491`, `EditStagesPanelNew.svelte:895`, `TripNewEditor.svelte:484`, `BriefingsTab.svelte:47`, `routes/locations/+page.svelte:47,49,99`, `routes/account/+page.svelte:170,206,251` |

### Alarm-Endpunkte (dürfen nicht abgelegt werden)

| Endpunkt | Relevanz |
|---|---|
| `GET /api/cockpit/status` (`internal/handler/cockpit.go:44-48`) | **Mischantwort** `{briefings, alerts}` — ein URL-Ausschluss nähme auch die Briefing-Kacheln vom Cachen aus. Braucht Feld-Filter oder Endpunkt-Split (`cockpit.go:16-48` ist klein genug). |
| `GET /api/archive/stats` (`router.go:203`) | Briefings **und** Alarme pro Tour. |
| `POST /api/trips/{id}/alert-preview` (`router.go:171`) | POST — vom Worker ohnehin nicht angefasst (`service-worker.ts:142`). |
| Alarm-*Konfiguration* | Steckt in `trip.alert_rules` / `official_alerts_enabled` / `radar_alert_enabled` und kommt über `GET /api/trips/{id}` — per URL **nicht** von den Nutzdaten trennbar. Die kritische Größe ist die ausgelöste Alarm-**Historie**, nicht die Konfiguration. |

### Kennzeichnungs-Muster (Vorbilder, alle in Python)

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/unavailable_hint.py:23-56` | Prototyp „kennzeichnen statt weglassen": Danger-Box, ausdrücklich **kein** `G_INK_FAINT` („Lesbarkeit unter Zeitdruck"). Kernsatz: *„keine Warnung" bedeutet hier nicht sicher „alles ruhig"*. |
| `src/output/renderers/email/outlook_state_hint.py:18-53` | Styling **nach Schweregrad**: Information → schlichter Fließtext in `G_INK_MUTED`, kein Rahmen; nur Störung → Danger-Box. |
| `src/services/trip_alert.py:211` | `_messluecken_felder()`: Feld entsteht **immer**, sobald die Messung lief — eine Absenz hieße sonst zugleich „alles gemessen" und „Altdatensatz". Genau die Ununterscheidbarkeit, die #2131 für „frisch vs. zwischengespeichert" vermeiden muss. |
| `src/output/renderers/email/helpers.py:496` | `build_origin_footer()` (ADR-0034) — Angabe wird **umbefüllt, nie entfernt**. |

## Existing Patterns

- **Kennzeichnung statt Ausblenden** (ADR-0034, `unavailable_hint.py`, `_messluecken_felder`) — durchgängige Haltung des Produkts, bisher aber **ausschließlich in den Python-Mail-Renderern**. Ein Frontend-Äquivalent existiert nicht.
- **Gate als pure Funktion** → `{ disabled, hint }`, fail-closed (`premiumSmsAlarmGate.ts`, `weatherSaveGate.ts`); die UI rendert die Begründung sichtbar neben dem gesperrten Element.
- **Wrapper statt neues Atom**: `TripStatusBadge.svelte:8` ist ein Thin-Wrapper um `ui/pill/Pill.svelte` mit Tone-Mapping. Für ein Stand-Badge ist das die systemkonforme Bauart — `Pill` kennt `tone="warning"`, `app.css:437` liefert dafür den AA-tauglichen Look (`rgba(192,138,26,0.12)` + `--g-warn-deep`).
- **Zeitdarstellung**: `frontend/src/lib/utils/schedulerTime.ts:16` `formatNextRun()` erzeugt genau „05.09., 06:12 MESZ" (`toLocaleString('de-AT', …, timeZoneName:'short')`) — die einzige geteilte Funktion dieser Form. Konvention (`:5-8`): Browserzone des Nutzers, dazu Zonenkürzel. SSR-Sicherheit beachten (`SaveIndicator.svelte:15`, #880).
- **Playwright-Zweitnutzer**: kein geteilter Helper, das Muster wird inline dupliziert. Beste Vorlage `frontend/e2e/compare-cross-user-write-block.spec.ts:53-77` (inkl. Warnung: `newContext()` erbt ohne `storageState: undefined` die Projekt-Session).
- **Offline im Test**: beide Muster in Gebrauch — `context.setOffline()` (`pwa-grundausstattung.spec.ts:116`) und `context.route('**/*', r => r.abort())` (`pwa-update-und-abmelden.spec.ts:200`, mit dokumentierter Begründung: unter `setOffline` beantwortet der Browser Programmdateien aus dem HTTP-Cache, der Netzfehler träte gar nicht ein).

## Dependencies

- **Upstream:** #2128 / ADR-0061 (Service-Worker-Bauform, vier abschließend aufgezählte Speicherregeln) · ADR-0003 (Mandantentrennung) · ADR-0034 (Herkunft wird umbefüllt, nie entfernt) · ADR-0008 (Kontrast vor Optik) · `page.data.userId` aus `+layout.server.ts`
- **Downstream:** Playwright-Projekt `pwa` in CI (`.github/workflows/ci.yml:395-433`, Schwelle `E2E_MIN_EXECUTED_PWA: 27`) · Staging-Nachweis `frontend/e2e/playwright.2128.staging.config.ts` · `raeumeGeraetespeicher()` muss jede neue Speicherart mit erfassen

## Existing Specs

- `docs/specs/modules/pwa_installierbar_offline_start.md` — 24 ACs zu #2128. **Known Limitations (`:409-421`)** benennt die Lücke wörtlich: „Es werden keine Inhalte offline verfügbar — nur die Programmdateien. … Das ist Scheibe 4 (#2131)."
- `docs/adr/0061-pwa-service-worker-bauform.md:110-117` — „Offline-Inhalte mit Stand-Kennzeichnung sind Scheibe 4 (#2131) und brauchen dort **eine eigene Entscheidung** darüber, was mit welcher Kennzeichnung abgelegt werden darf." Verworfene Alternative (`:158-161`): stilles stale-while-revalidate für HTML.
- Für #2131 existiert noch **kein** Kontext-, Spec- oder ADR-Dokument (dieses Dokument ist das erste).

## Risks & Considerations

### R1 — Der Architektur-Kern: ohne Netz wird nie ein Loader erreicht

Alle Erstladungen sind SSR (`+page.server.ts`), es gibt **kein einziges `+page.ts`**. Ohne Netz
kommt der Nutzer nie in einen Loader — der Service Worker fängt schon bei `request.mode ===
'navigate'` ab. **Ein API-Cache allein bewirkt daher nichts**: die Seite, die ihn auswerten würde,
wird nie gerendert. Es gibt genau zwei Wege, und die Wahl gehört in ein ADR:

- **(a) HTML-Dokumente ablegen** — direkt gegen ADR-0061 Regel 2. Der Stand muss dann nachträglich
  in ein fertig gerendertes Dokument eingeblendet werden (Ablagezeitpunkt aus einem eigenen Header
  oder `Date`).
- **(b) Ladewege auf universal `+page.ts` umbauen**, damit die Seite clientseitig aus einer
  abgelegten API-Antwort rendern kann — sauberer bei der Kennzeichnung, aber ein Umbau quer durch
  alle Ansichten.

### R2 — Gecachtes HTML cacht Alarme implizit mit

Weg (a) aus R1 kollidiert frontal mit „Alarme werden nicht zwischengespeichert": im SSR-HTML der
Startseite ist die Alarm-Kachel bereits eingebrannt (`routes/+page.svelte:113`, gespeist aus
`/api/cockpit/status`). Ein abgelegtes Dokument trüge einen alten Alarm-Stand, der offline wie ein
aktueller aussieht — laut Ticket „die gefährlichste denkbare Anzeige". Auflösung nötig: Alarm-Bereiche
beim Ausliefern eines abgelegten Dokuments clientseitig durch „nicht abrufbar" ersetzen, oder Weg (b).

### R3 — Mandantentrennung: der Worker kennt den Nutzer nicht

Der Cache-Name ist heute `gz-${version}` ohne Nutzeranteil (`service-worker.ts:30`). Der Worker hat
keinen Zugriff auf `page.data.userId`; das Session-Cookie zu parsen wäre eine zweite
Wahrheitsquelle. Wege: `postMessage` der `userId` an den Worker, oder Ablage im Seitenkontext.
**Zusätzlich fehlt heute das Räumen beim Nutzer*wechsel*** — geräumt wird nur nach einem echten
Abmelden (`login/+page.svelte:22-29`). Meldet sich Nutzer B ohne vorheriges Abmelden von A an, bleibt
As Speicher liegen. Das ist der ADR-0003-Verstoß, den das Ticket ausdrücklich benennt.

### R4 — Neue Speicherarten fallen aus der Räumung

`raeumeGeraetespeicher()` räumt heute nur Cache Storage und Worker-Registrierungen
(`geraetespeicher.ts:104-146`). Landen Inhalte in IndexedDB oder localStorage, sind sie nach dem
Abmelden **noch da** — stille Verletzung von AC „Beim Abmelden wird der Gerätespeicher geleert".
Jede gewählte Speicherart muss in `einDurchgang()` **und** `istGeraeumt()` nachgezogen werden.

### R5 — Kein Merkmal trennt cachebar von nicht-cachebar

Im gesamten Go-Code steht **kein einziger `Cache-Control`-Header**; `/api/cockpit/status` und
`/api/trips` sehen auf der Leitung identisch aus. Drei Ansätze: `no-store` in den Alarm-Handlern +
Prüfung im Worker · explizite Allowlist im Worker (passt zu ADR-0061 „jede neue Klasse bewusst einer
Regel zuordnen", `:133-135`) · Endpunkt-Split von `/api/cockpit/status`.

### R6 — Keine Verbindungserkennung im Bestand

Kein `navigator.onLine`, kein `online`/`offline`-Listener, kein Verbindungs-Store im gesamten
`frontend/src`. Muss neu gebaut werden (Ort analog `frontend/src/lib/stores/`, Svelte-5-Runen).
Achtung: `navigator.onLine` meldet nur „Netzwerkschnittstelle vorhanden", nicht „Server erreichbar" —
ein Gate allein darauf sperrt im Captive-Portal nicht und sperrt im funktionierenden Netz
fälschlich nicht. Die belastbare Wahrheit ist der fehlgeschlagene Abruf.

### R7 — Speicherplatz

iOS ist deutlich strenger als Android. Verlangt sind feste Obergrenze und Ältestes-zuerst-Verdrängung
über nur die zuletzt tatsächlich angesehenen Inhalte. `cache.addAll` (alles-oder-nichts,
`service-worker.ts:40-45`) ist dafür die falsche Bauform — es braucht einzelne `put`-Aufrufe mit
Buchführung.

### R8 — Kein Frontend-Baustein für die Kennzeichnung

Es gibt keinen generischen Notice-/Callout-Baustein. Nächste Verwandte: `ui/pill/Pill.svelte`
(`tone="warning"`), `molecules/ComparePreviewMissing.svelte`, `ui/SaveIndicator.svelte` (Vorbild für
dauerhaft sichtbaren Zustand). `mobile/Toast.svelte` ist flüchtig und damit **ungeeignet** — die
Stand-Angabe muss dauerhaft am Inhalt stehen, nicht in einer Fußnote und nicht in einem
verschwindenden Hinweis (Ticket: „sichtbar am Inhalt, nicht in einer Fußnote").

### R9 — Umfang sprengt das LoC-Budget

Vier Umfangspunkte plus neues ADR plus Zwei-Nutzer-Playwright-Nachweis liegen deutlich über 250 LoC.
`loc_limit_override` ist beim Implementieren zu setzen.

### R10 — Spec-Diskrepanz aus #2128 (Nebenbefund)

`docs/specs/modules/pwa_installierbar_offline_start.md:215` behauptet, `frontend/src/lib/api.ts`
setze beim 401-Umleiten das Abmelde-Merkmal (AC-22). Im Code tut `api.ts` das nicht — es hängt nur
`status: 401` an den geworfenen Fehler (`api.ts:71-75`), damit `account/+page.svelte:331` den Merker
stehen lässt. Funktional äquivalent, der Spec-Satz ist irreführend. Kandidat für #1199, kein Blocker.

---

# Analysis

## Type

Feature (Scheibe 4 des Epics #2127). Kein Bugfix — die Lücke ist in #2128 bewusst offen gelassen
worden (`docs/specs/modules/pwa_installierbar_offline_start.md:409-421`).

## Zwei Befunde, die den Zuschnitt bestimmen

**B1 — `__data.json` ist eine eigene Anfrageklasse.** SvelteKit navigiert clientseitig nicht per
Seitenaufruf, sondern per `fetch()` auf `<pfad>/__data.json`. Diese Anfrage hat
`request.mode !== 'navigate'` und fällt heute durch bis Regel 4 (Netz, keine Ablage). Wer nur HTML
ablegt, kann offline eine Seite öffnen, aber nicht von ihr weg- und wieder zurücknavigieren. Die
Ablage braucht **beide** Klassen.

**B2 — Der Kaltstart trifft ausgerechnet die eine Route, die nicht abgelegt werden darf.**
`start_url` im Manifest ist `/` (`frontend/static/site.webmanifest:6`) — der Start vom Homescreen,
also der Normalfall einer installierten App. Genau diese Route trägt die Alarm-Kachel
(`routes/+page.svelte:113` aus `/api/cockpit/status`) und ist damit vom Ablegen ausgeschlossen. Ohne
Gegenmaßnahme startet die installierte App offline immer auf der Offline-Seite und zeigt nie einen
Stand — das Kernversprechen des Tickets ginge am häufigsten Weg vorbei.

## Technical Approach

Die Entscheidung fällt gegen einen Umbau aller Ladewege auf universal `+page.ts` (R1, Weg b) und für
die **Ablage der Seitenantworten unter einer geschlossenen Routen-Positivliste** (Weg a). Grund: der
Umbau der SSR-Kette berührt Auth-Weiterleitung, Fehlerbehandlung und jede Ansicht; er ist ein
eigenes Vorhaben, kein Nebeneffekt dieser Scheibe.

**A. Ablage-Positivliste statt Feldfilter.** Abgelegt werden Seitenantwort **und** `__data.json`
von `/trips/[id]` und `/compare/[id]`. `/` (Cockpit) und `/archiv` sind **dauerhaft
ausgeschlossen** — sie sind die einzigen beiden Routen, die Alarm-Historie führen. Damit fällt die
Forderung „Alarme werden nicht zwischengespeichert" auf URL-Ebene und braucht keinen Feldfilter im
Go-Handler und keinen Endpunkt-Split. Alarm-*Konfiguration* (`trip.alert_rules`) darf mitgehen —
das Ticket meint die ausgelösten Alarme, und die Konfiguration ist Teil des Trips.

**B. Der Stand wird beim Ablegen eingeschrieben, nicht beim Ausliefern.** Der Worker klont die
erfolgreiche Netzantwort, ersetzt darin ein festes Markierungselement aus dem Root-Layout durch die
fertig formatierte Stand-Zeile und legt **diese** Kopie ab; die live ausgelieferte Antwort bleibt
unverändert. Folge: der Stand steht im ersten Byte des offline ausgelieferten Dokuments — es gibt
kein Zeitfenster, in dem ein alter Stand ungekennzeichnet sichtbar wäre, und die Kennzeichnung
überlebt auch dann, wenn Client-JS gar nicht erst hydriert. Format nach dem Muster von
`frontend/src/lib/utils/schedulerTime.ts:37` (Gerätezone, Zonenkürzel).

**C. Mandantenkennung über einen Antwort-Header, nicht über `postMessage`.**
`frontend/src/hooks.server.ts` (setzt heute schon `cache-control` auf HTML) hängt an jede
authentifizierte Nicht-`/api/`-Antwort einen kurzen Hash von `event.locals.userId`. Der Worker liest
ihn beim Ablegen und bildet daraus den Cache-Namen. **Fail-closed:** fehlt der Header, wird nicht
abgelegt. Die Kennung stammt damit aus derselben signierten Sitzung, die den Inhalt autorisiert hat
— keine zweite Wahrheitsquelle, kein Zustand im Worker, der ein Prozessende nicht überlebt.

**D. Nutzerwechsel wird beim ersten Online-Abruf geräumt, nicht bei einem Ereignis.** Weil die
Kennung an jeder Antwort hängt, prüft der Worker bei jeder Ablage, ob ein Datencache mit fremder
Kennung existiert, und löscht ihn sofort. Das schließt R3 auch für den Weg „Nutzer B meldet sich an,
ohne dass A sich abgemeldet hat" — ohne neue Speicherart und ohne Zeitfenster.

**E. Cache Storage exklusiv — bindende Bauform.** Kein IndexedDB, kein localStorage. Damit greift
`raeumeGeraetespeicher()` (`geraetespeicher.ts:118-130`, iteriert `caches.keys()` ungefiltert) für
den neuen Bucket automatisch mit, und R4 bleibt geschlossen, ohne die Räumung anzufassen.

**F. Der `activate`-Sweep muss den Datencache aussparen.** `service-worker.ts:79-81` löscht heute
jeden Namen ≠ `gz-${version}`. Unverändert wäre der Offline-Stand nach jedem angenommenen Update
weg. Die Bedingung wird auf Programm-Cache-Namen präzisiert.

**G. Offline-Einstieg statt Sackgasse (löst B2).** Die Offline-Seite wird von einer Sackgasse zur
Übersicht: der Worker beantwortet einen gescheiterten Seitenaufruf mit einer Fassung, die die
abgelegten Ansichten mit Titel und Stand auflistet. Damit ist der Homescreen-Start offline brauchbar,
**ohne** dass `/` abgelegt werden muss — es wandern nur Titel und Zeitpunkt in die Liste, keine
Inhalte und schon gar keine Alarme. Das ist der Grund, warum die Listen-Routen (`/trips`,
`/compare`, `/locations`) in dieser Scheibe **nicht** in die Positivliste müssen: die Offline-Seite
übernimmt ihre Rolle als Navigationsweg.

**H. Bearbeitungssperre zweistufig — ehrlich und fail-closed.**
- *Stufe 1, statisch:* Trägt das ausgelieferte Dokument die Stand-Markierung, wurde es aus dem
  Speicher geliefert; jeder Schreibversuch darauf ist per Definition unzustellbar. Alle
  Bearbeitungsflächen dieser Seite werden bedingungslos gesperrt — die Information steht bereits im
  HTML, es braucht keinen Laufzeit-Netzcheck.
- *Stufe 2, Laufzeit:* für „online geöffnet, dann Netz weg". Neuer Verbindungs-Store unter
  `frontend/src/lib/stores/`, gespeist aus dem tatsächlichen Fehlschlag von `api.ts:61` — **nicht**
  aus `navigator.onLine` allein (das meldet nur eine vorhandene Netzwerkschnittstelle, nicht einen
  erreichbaren Server; R6).
- Sichtbar wird die Sperre über eine reine Gate-Funktion `{ disabled, hint }` nach dem Vorbild
  `shared/alarme-tab/premiumSmsAlarmGate.ts:37`, gerendert wie in
  `shared/versand-tab/VTBriefingChannels.svelte:203/212` — gesperrtes Element bleibt sichtbar und
  trägt seine Begründung.

**Sperr-Inventar durch den Zuschnitt begrenzt.** Von den 70 nutzerseitigen Schreibstellen im
Frontend sind offline nur die der beiden abgelegten Routen erreichbar. Für genau diese wird das
Inventar **vollständig** abgearbeitet — eine offline sichtbare, aber ungesperrte Schaltfläche wäre
genau das „scheinbar bedienbar", das das Ticket ausschließt. Die Flächen der nicht abgelegten Routen
sind offline nicht erreichbar und brauchen daher keine Sperre.

## Affected Files (with changes)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/src/service-worker.ts` | MODIFY | Positivliste, Ablage von Seitenantwort + `__data.json`, Stand-Einschrieb beim Ablegen, Mandanten-Bucket, Purge bei fremder Kennung, präzisierter `activate`-Sweep, Obergrenze + Ältestes-zuerst |
| `frontend/src/hooks.server.ts` | MODIFY | Mandanten-Header auf authentifizierte Nicht-`/api/`-Antworten |
| `frontend/src/routes/+layout.svelte` | MODIFY | Markierungselement für die Stand-Zeile (⚠ `publicPages`-Literal muss erhalten bleiben, `hooks.server.test.ts:64-77`) |
| `frontend/static/offline.html` | MODIFY | Übersicht der abgelegten Ansichten statt Sackgasse |
| `frontend/src/lib/stores/verbindung.svelte.ts` | CREATE | Verbindungs-Store aus echten Abruf-Fehlschlägen |
| `frontend/src/lib/components/shared/offlineGate.ts` | CREATE | Reine Funktion → `{ disabled, hint }` |
| `frontend/src/lib/api.ts` | MODIFY | Fehlschlag meldet an den Verbindungs-Store; Schreibversuch offline wird fail-closed abgewiesen |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | Offline-Zustand, kein Schreibversuch ins Leere |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | MODIFY | Offline-Zustand sichtbar (⚠ `saveIndicatorConflictBranch.test.ts` inspiziert die `{#if}`-Kette per Text) |
| Bearbeitungsflächen von `/trips/[id]` und `/compare/[id]` | MODIFY | Gate verdrahten: `TripHeader.svelte:45`, `TripTabs.svelte:188`, `EditStagesPanelNew.svelte:160/186/421`, `WeatherMetricsTab.svelte:943-997`, `AlarmeTab.svelte:315`, `CorridorEditor(.Mobile).svelte`, `BriefingScheduleTab.svelte:45/56`, `SavePresetDialog.svelte:114`, `CompareTabs.svelte:267-1026`, `compare/[id]/+page.svelte:114/141/158/239/252`, `trips/[id]/+page.svelte:85/164` |
| `frontend/e2e/pwa-grundausstattung.spec.ts` | MODIFY | AC-6/AC-7/AC-21 auf „Programm **und** Positivlisten-Daten" umschreiben |
| `frontend/e2e/pwa-update-und-abmelden.spec.ts` | MODIFY | „genau ein Cache-Name" → Programm-Cache plus höchstens ein Daten-Cache |
| `frontend/e2e/pwa-offline-ansehen.spec.ts` | CREATE | Offline-Nachweis inkl. **Zwei-Nutzer-Fall auf einem Profil** |
| `docs/adr/0062-*.md` | CREATE | Fortschreibung von ADR-0061 |
| `docs/specs/modules/pwa_offline_ansicht_letzter_stand.md` | CREATE | Spec |

## Scope Assessment

- Dateien: ~20 (4 CREATE Produktivcode/Test, ~14 MODIFY, 2 CREATE Doku)
- Geschätzte LoC: **+300–400 Produktivcode, +300–400 Tests** → `loc_limit_override` zwingend, vorab setzen
- Risk Level: **HIGH** — Mandantentrennung (ADR-0003), Anzeige von Entscheidungsgrundlagen

## Dependencies

Reihenfolge: (1) Mandanten-Header — blockiert alles Weitere · (2) Worker-Regeln inkl. `__data.json`
und `activate`-Sweep · (3) Stand-Einschrieb + Layout-Markierung · (4) Verbindungs-Store + Gate
(unabhängig, kann parallel) · (5) Anschluss `SaveStatus` + Einzelflächen · (6) Bestandswächter
umschreiben (erst wenn Verhalten steht) · (7) Zwei-Nutzer-Playwright-Nachweis. ADR-0062 parallel zu
(1)–(2), fertig bevor (5) beginnt.

## Wächter, die bewusst mitzuziehen sind

1. `frontend/e2e/pwa-grundausstattung.spec.ts:302-307` — AC-21 „nur Programm im Speicher",
   Baseline-Vergleich. Schärfster Wächter, schlägt bei **jedem** neuen Eintrag an.
2. `:322-329` — AC-7 „kein HTML im Speicher"; nennt #2131 bereits als Anlass.
3. `:199-204` — AC-6 „kein `/api/`-Eintrag".
4. `frontend/e2e/pwa-update-und-abmelden.spec.ts:277-279` — `toEqual([ALT])`, genau ein Cache-Name;
   dazu `:314-319`.
5. Sieben `{caches: 0, registrations: 0}`-Stellen und sechs Mengengleichheits-Stellen in derselben
   Datei — brechen, wenn der aktive Worker den neuen Bucket nach dem Räumen **nachlegt**.
6. `frontend/src/hooks.server.test.ts:25/35/64-77` — liest `+layout.svelte` per `readFileSync` und
   parst `publicPages` als Literal.
7. `frontend/src/lib/components/ui/__tests__/saveIndicatorConflictBranch.test.ts` — zerlegt
   `SaveIndicator.svelte` per Textmarker; ein neuer Zweig verschiebt die Blockgrenzen.
8. `frontend/src/lib/stores/__tests__/saveStatus.test.ts:445/456-459` — Export- und
   Prototyp-Wächter am Speicher-Controller.
9. `data-state`-Werte des SaveIndicators in 25 E2E-Dateien: ein zusätzlicher Zustand ist additiv
   unschädlich, **solange `idle` nach erfolgreichem Speichern weiterhin gesetzt wird**.
10. CI: Neue `frontend/e2e/pwa-*.spec.ts` laufen über `--project=pwa` automatisch mit, **ohne**
    Positivlisten-Eintrag; `E2E_MIN_EXECUTED_PWA: 27` ist eine `>=`-Schwelle, zusätzliche Fälle
    machen sie nicht rot. Reihenfolge PWA vor bug-703 beachten (Login-Ratenbegrenzung 30/h).

## Verworfene Alternativen

- **Umbau aller Ladewege auf universal `+page.ts`** — sauberere Kennzeichnung, aber berührt
  Auth-Weiterleitung und jede Ansicht. Eigenes Vorhaben, nicht Teil dieser Scheibe.
- **`postMessage` der `user_id` an den Worker** — der Worker-Prozess kann zwischen zwei Ereignissen
  beendet werden und verliert seinen Zustand; die Kennung käme aus einer zweiten Quelle neben der
  signierten Sitzung.
- **Feldweises Filtern der Alarme aus `/api/cockpit/status`** bzw. Endpunkt-Split — unnötig, sobald
  die Grenze routenweise gezogen wird; der Split bräche zudem
  `frontend/src/lib/issue_393_cockpit_kacheln.test.ts:29-45` und
  `docs/reference/api_contract.md:165`.
- **Alarm-Bereiche beim Ablegen aus dem HTML herausschneiden**, um `/` doch ablegen zu können —
  Textmanipulation an genau der Stelle, deren Fehlgehen die gefährlichste Anzeige des Produkts
  erzeugt. Die Offline-Übersicht (G) löst dasselbe Problem ohne dieses Risiko.
- **Stand per Client-JS nach dem Hydrieren einblenden** — es gäbe ein Zeitfenster, in dem ein alter
  Stand ungekennzeichnet sichtbar ist. Genau das verbietet das Ticket.

## Open Questions

Keine, die den PO betreffen. Der Zuschnitt (welche Routen offline vorgehalten werden) wird über die
Acceptance Criteria in Phase 3 zur Freigabe vorgelegt.
