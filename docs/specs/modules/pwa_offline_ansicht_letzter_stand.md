---
entity_id: pwa_offline_ansicht_letzter_stand
type: module
created: 2026-09-06
updated: 2026-09-06
status: draft
version: "1.0"
tags: [pwa, frontend, offline, service-worker, tenant-isolation, issue-2131, epic-2127]
workflow: feat-2131-offline-ansehen
---

# PWA: offline den letzten Stand ansehen

Issue #2131 · Scheibe 4 zu Epic #2127 · Workflow `feat-2131-offline-ansehen`

## Approval

- [ ] Approved

## Purpose

Ohne Netz zeigt die App weiterhin die zuletzt geladene Trip-Ansicht und die zuletzt geladene
Ortsvergleichs-Ansicht — statt der bloßen Offline-Seite aus Scheibe 1 (#2128). Jede so gezeigte
Ansicht trägt sichtbar am Inhalt ihren Stand („Stand: 05.09., 06:12 — offline, aus dem
Gerätespeicher"), Bearbeitungsflächen sind sichtbar gesperrt statt versteckt, Alarme werden
grundsätzlich **nicht** zwischengespeichert, und der Gerätespeicher bleibt streng je Nutzer getrennt
und wird beim Abmelden vollständig geleert. Es wird nur angesehen — nichts wird offline bearbeitet
oder gepuffert (PO-Entscheid 2026-09-05).

## Source

- **File:** `frontend/src/service-worker.ts` (Erweiterung des Bestands aus #2128)
- **Identifier:** `fetch`-Ereignisbehandlung (Positivliste, Stand-Einschrieb, Mandanten-Bucket,
  Purge, Verdrängung), plus kleine Ergänzung in `frontend/src/hooks.server.ts` (Mandanten-Header)
- **Schicht:** Frontend (SvelteKit). **Kein Go-Anteil, kein Python-Anwendungscode.** Alle
  Nachweise laufen als Playwright (`frontend/e2e/`) oder `node:test` (ADR-0020); es gibt keinen
  Python-Prüfmittel-Anteil wie in #2128.

> Betroffene Dateien liegen ausschließlich unter `frontend/src/...` und `frontend/static/...`. Kein
> Handler in `internal/` oder `api/`/`src/services/` wird geändert — die Alarm-Abgrenzung läuft über
> eine Routen-Positivliste im Worker, nicht über einen Feld- oder Endpunkt-Split im Go-Backend
> (siehe Implementation Details, Abschnitt A).

## Estimated Scope

- **LoC:** ~300–400 Produktivcode, ~300–400 Tests (Limit für diesen Workflow anzuheben,
  `loc_limit_override` vorab setzen)
- **Files:** ~20 (4 CREATE Produktivcode/Test, ~14 MODIFY, 2 CREATE Doku)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/service-worker.ts` (#2128) | Modul | Bestehende vier Speicherregeln, Cache-Name `gz-${version}`, `activate`-Sweep — wird erweitert, nicht ersetzt |
| `frontend/src/lib/pwa/geraetespeicher.ts` (#2128) | Modul | Räumt heute alle Cache-Buckets ungefiltert (`caches.keys()`) — der neue Bucket läuft automatisch mit (Abschnitt E) |
| `frontend/src/hooks.server.ts` | Auth-Weiche | Liefert `event.locals.userId`; bekommt den neuen Mandanten-Header für Nicht-`/api/`-Antworten |
| `frontend/src/routes/+layout.server.ts` | Loader | Reicht `userId` als `page.data.userId` weiter — Referenz für die Herkunft der Mandantenkennung |
| `frontend/src/lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts` | Vorbild | Reine Gate-Funktion `{ disabled, hint }`, fail-closed — Bauform für `offlineGate.ts` |
| `frontend/src/lib/utils/schedulerTime.ts` | Funktion | `formatNextRun()` liefert das Zeitformat „05.09., 06:12 MESZ" — Vorbild für die Stand-Zeile |
| `frontend/e2e/pwaHelpers.ts` (#2128) | Testwerkzeug | `activateServiceWorker`, `cacheNames`, `readCacheEntries`, `storageAndRegistrationCount` |
| `frontend/e2e/compare-cross-user-write-block.spec.ts:53-77` | Testvorbild | Zwei-Nutzer-Muster auf einem Browserprofil (Achtung: `newContext({ storageState: undefined })`) |
| ADR-0061 | Entscheidung | PWA-Bauform aus #2128, benennt #2131 wörtlich als die Scheibe für Inhalte mit Stand-Kennzeichnung |
| ADR-0003 | Entscheidung | Mandantentrennung — bindend auch für den Gerätespeicher |
| ADR-0034 | Entscheidung | Herkunfts-/Standangaben werden umbefüllt, nie stillschweigend entfernt |
| ADR-0008 | Entscheidung | Kontrast vor Optik — Stand-Zeile und Sperr-Begründung müssen lesbar bleiben, nicht `--g-ink-4` |
| ADR-0020 | Entscheidung | Frontend-Unit-Tests laufen mit `node:test`, nicht vitest |

## Implementation Details

Die Analyse (`docs/context/feat-2131-offline-ansehen.md`) hat zwei Kernbefunde ermittelt, die den
Zuschnitt bestimmen: Erstens navigiert SvelteKit clientseitig nicht per Seitenaufruf, sondern per
`fetch()` auf `<pfad>/__data.json` — eine eigene Anfrageklasse, die zusätzlich zum HTML-Dokument
abgelegt werden muss, sonst funktioniert Offline-Navigation zwischen zwei abgelegten Ansichten
nicht. Zweitens trägt `start_url` im Manifest den Wert `/`, also ausgerechnet die Route mit der
Alarm-Kachel — ohne Gegenmaßnahme würde die installierte App offline immer auf der Sackgassen-Seite
landen.

Die Entscheidung fällt gegen einen Umbau aller Ladewege auf universal `+page.ts` (der SSR-Loader
bliebe die einzige Datenquelle) und für eine **Ablage-Positivliste über eine geschlossene
Routenmenge**, ergänzt um eine Offline-Übersicht als Einstiegspunkt. Im Einzelnen:

**A. Ablage-Positivliste statt Feldfilter.** Abgelegt werden Seitenantwort **und** `__data.json`
ausschließlich von `/trips/[id]` und `/compare/[id]`. Die Startseite (`/`, Cockpit) und `/archiv`
sind dauerhaft ausgeschlossen — sie sind die einzigen beiden Routen, die Alarm-Historie zeigen.
Damit erledigt sich „Alarme werden nicht zwischengespeichert" auf URL-Ebene; es braucht keinen
Feldfilter im Go-Handler und keinen Endpunkt-Split von `/api/cockpit/status`. Alarm-*Konfiguration*
(`trip.alert_rules`) darf mitgehen, gemeint sind die ausgelösten Alarme, nicht die Einstellungen.

**B. Der Stand wird beim Ablegen eingeschrieben, nicht beim Ausliefern.** Der Worker klont die
erfolgreiche Netzantwort, ersetzt darin ein festes Markierungselement aus dem Root-Layout
(`+layout.svelte`) durch die fertig formatierte Stand-Zeile (Format wie `schedulerTime.ts`:
Gerätezone, Zonenkürzel, plus Hinweis „offline, aus dem Gerätespeicher") und legt diese Kopie ab;
die live ausgelieferte Antwort bleibt unverändert. Der Stand steht damit im ersten Byte des offline
ausgelieferten Dokuments — kein Zeitfenster, in dem ein alter Stand ungekennzeichnet sichtbar wäre,
auch nicht vor der Hydrierung.

**C. Mandantenkennung über einen Antwort-Header, fail-closed.** `hooks.server.ts` hängt an jede
authentifizierte Nicht-`/api/`-Antwort einen kurzen Hash von `event.locals.userId`. Der Worker liest
ihn beim Ablegen und bildet daraus den Cache-Namen (`gz-daten-<hash>`, getrennt vom Programm-Cache
`gz-${version}`). Fehlt der Header, wird nicht abgelegt — die Kennung stammt aus derselben
signierten Sitzung, die den Inhalt autorisiert hat, keine zweite Wahrheitsquelle und kein Zustand,
der ein Prozessende des Workers überleben müsste (verworfen: `postMessage` der `userId` an den
Worker — der Worker-Prozess kann zwischen zwei Ereignissen beendet werden und verliert seinen
Zustand).

**D. Nutzerwechsel wird beim ersten Online-Abruf geräumt, nicht bei einem Ereignis.** Weil die
Kennung an jeder Antwort hängt, prüft der Worker bei jeder Ablage, ob im Datenspeicher bereits ein
Bucket mit fremder Kennung existiert, und löscht ihn sofort. Das schließt auch den Fall „Nutzer B
meldet sich an, ohne dass Nutzer A sich vorher abgemeldet hat" — ohne neue Speicherart und ohne
Zeitfenster, in dem beide Bestände nebeneinander lägen.

**E. Cache Storage exklusiv — bindende Bauform.** Kein IndexedDB, kein localStorage. Damit greift
`raeumeGeraetespeicher()` (iteriert `caches.keys()` ungefiltert) für den neuen Bucket automatisch
mit, ohne dass die Räumfunktion selbst angefasst werden muss.

**F. Der `activate`-Sweep muss den Datencache aussparen.** Der Bestandssweep aus #2128 löscht jeden
Cache-Namen ungleich dem aktuellen Programm-Cache. Unverändert übernommen würde der Stand nach jedem
angenommenen Update gelöscht — die Bedingung wird auf Programm-Cache-Namen präzisiert, Datencaches
bleiben von diesem Sweep unberührt und unterliegen stattdessen der Obergrenze aus Abschnitt G.

**G. Offline-Einstieg statt Sackgasse (löst den Kaltstart-Fall).** Die Offline-Seite aus #2128 wird
von einer Sackgasse zu einer Übersicht: der Worker beantwortet einen gescheiterten Seitenaufruf mit
einer Fassung, die die abgelegten Ansichten mit Titel und Stand auflistet, gespeist aus einer festen
Obergrenze mit Ältestes-zuerst-Verdrängung (einzelne `put`-Aufrufe mit Buchführung statt
`cache.addAll`, das ist alles-oder-nichts und für laufende Verdrängung ungeeignet). Damit ist der
Homescreen-Start (`start_url: "/"`) offline brauchbar, ohne dass `/` selbst abgelegt werden muss —
es wandern nur Titel und Zeitpunkt in die Liste, keine Inhalte und keine Alarme. Die Listen-Routen
(`/trips`, `/compare`, `/locations`) brauchen deshalb in dieser Scheibe keine eigene Ablage: die
Offline-Übersicht übernimmt ihre Rolle als Navigationsweg (verworfen: Alarm-Bereiche beim Ablegen
per Textmanipulation aus dem HTML von `/` herausschneiden — Eingriff genau an der Stelle, deren
Fehlgehen die gefährlichste Anzeige des Produkts erzeugen würde).

**H. Bearbeitungssperre zweistufig — ehrlich und fail-closed.**
- *Stufe 1, statisch:* Trägt das ausgelieferte Dokument die Stand-Markierung, stammt es aus dem
  Gerätespeicher; jeder Schreibversuch darauf wäre ohnehin unzustellbar. Alle Bearbeitungs- und
  Speichern-Elemente dieser Seite werden bedingungslos gesperrt — die Information steht bereits im
  HTML, ein Laufzeit-Netzcheck ist dafür nicht nötig.
- *Stufe 2, Laufzeit:* für den Fall „online geöffnet, Netz fällt erst danach weg". Ein neuer
  Verbindungs-Store (`frontend/src/lib/stores/verbindung.svelte.ts`, Svelte-5-Runen) sperrt
  **asymmetrisch**, und zwar bewusst:
  - **Sofort sperren** meldet das `offline`-Ereignis des Geräts. Es ist als *negatives* Signal
    verlässlich — wenn das Gerät sagt, es hat keine Verbindung, hat es keine. Auf den ersten
    fehlgeschlagenen Abruf zu warten wäre falsch: dieser Abruf wäre der Schreibversuch, der laut
    AC-10 gerade nicht ins Leere laufen darf.
  - **Ebenfalls sperren** tut jeder tatsächlich fehlgeschlagene Abruf über `api.ts:61`. Das fängt
    die Lage ab, in der das Gerät eine Verbindung meldet, aber niemand antwortet (Funkloch mit
    eingebuchtem Netz, Anmeldeportal im WLAN).
  - **Entsperren** tut das `online`-Ereignis ausdrücklich **nicht** von sich aus — dafür ist es als
    positives Signal untauglich (`navigator.onLine` meldet nur eine vorhandene
    Netzwerkschnittstelle, nicht einen erreichbaren Server). Entsperrt wird erst, wenn ein Abruf
    wieder nachweislich gelungen ist. Damit ist das Verhalten in beide Richtungen fail-closed: im
    Zweifel gesperrt, nie scheinbar bedienbar.
- Sichtbar wird die Sperre über eine reine Gate-Funktion `{ disabled, hint }`
  (`frontend/src/lib/components/shared/offlineGate.ts`) nach dem Vorbild `premiumSmsAlarmGate.ts` —
  das gesperrte Element bleibt sichtbar und trägt seine Begründung, verschwindet nicht (ADR-0034:
  kennzeichnen statt weglassen).

**Sperr-Inventar begrenzt auf die zwei abgelegten Routen.** Von allen nutzerseitigen
Schreibstellen im Frontend sind offline nur die von `/trips/[id]` und `/compare/[id]` erreichbar.
Für genau diese wird das Inventar vollständig abgearbeitet, einschließlich `SaveIndicator.svelte`
(eigener Offline-Zustand) und `saveStatusStore.svelte.ts` (kein Schreibversuch ins Leere). Flächen
der nicht abgelegten Routen sind offline nicht erreichbar und brauchen deshalb keine eigene Sperre.

**Reihenfolge der Umsetzung:** (1) Mandanten-Header — blockiert alles Weitere · (2) Worker-Regeln
inklusive `__data.json` und präzisiertem `activate`-Sweep · (3) Stand-Einschrieb und
Layout-Markierung · (4) Verbindungs-Store und Gate (kann parallel zu 1–3 laufen) · (5) Anschluss
`SaveStatus` und Einzelflächen · (6) Bestandswächter (`pwa-grundausstattung.spec.ts`,
`pwa-update-und-abmelden.spec.ts`) erst umschreiben, wenn das Verhalten steht · (7)
Zwei-Nutzer-Playwright-Nachweis.

## Expected Behavior

- **Input:** Seitenaufrufe, Client-Navigationen (`__data.json`) und Datenabrufe von `/trips/[id]`
  und `/compare/[id]`, mit und ohne Netz; Abmelde- und Nutzerwechsel-Vorgänge.
- **Output:** Bei Netz unverändert live aus dem SSR-Loader. Bei fehlendem Netz: die zuletzt
  abgelegte Fassung der beiden Ansichten inklusive eingeschriebener Stand-Zeile und gesperrter
  Bearbeitungsflächen; für alle übrigen Routen weiterhin die Offline-Seite, jetzt als Übersicht der
  abgelegten Ansichten statt Sackgasse. `/`, `/archiv` und alle `/api/`-Antworten werden nie abgelegt.
- **Side effects:** Ein zweiter Cache-Bucket (`gz-daten-<mandanten-hash>`) entsteht neben dem
  Programm-Cache aus #2128, mit fester Obergrenze und Ältestes-zuerst-Verdrängung. Ein
  Nutzerwechsel auf demselben Gerät löscht beim ersten Online-Abruf des neuen Nutzers den
  Daten-Bucket des vorherigen. Abmelden über beide bekannten Wege leert auch diesen Bucket.

## Acceptance Criteria

- **AC-1:** Given eine Trip-Ansicht wurde mit bestehender Verbindung einmal vollständig geöffnet /
  When das Netz danach abgeschaltet und dieselbe Trip-Ansicht erneut geöffnet wird / Then zeigt die
  Seite den zuletzt geladenen Inhalt der Trip-Ansicht, nicht die Offline-Seite.
  - Test: Playwright öffnet `/trips/[id]` online, schaltet den Kontext auf offline, navigiert erneut
    zu derselben Adresse und prüft, dass der Trip-Inhalt (nicht die Offline-Seite) sichtbar ist.

- **AC-2:** Given eine Ortsvergleichs-Ansicht wurde mit bestehender Verbindung einmal vollständig
  geöffnet / When das Netz danach abgeschaltet und dieselbe Ansicht erneut geöffnet wird / Then
  zeigt die Seite den zuletzt geladenen Inhalt des Ortsvergleichs, nicht die Offline-Seite.
  - Test: Playwright öffnet `/compare/[id]` online, schaltet den Kontext auf offline, navigiert
    erneut dorthin und prüft, dass der Vergleichsinhalt sichtbar ist.

- **AC-3:** Given eine Trip- oder Ortsvergleichs-Ansicht wird ohne Netz aus dem Gerätespeicher
  gezeigt / When die Seite betrachtet wird / Then steht sichtbar am Inhalt eine Stand-Zeile mit
  Datum, Uhrzeit und der ausdrücklichen Angabe, dass die Ansicht ohne Netz aus dem Gerätespeicher
  stammt.
  - Test: Playwright liest den sichtbaren Text der Stand-Zeile aus und prüft, dass Datum, Uhrzeit
    und der Herkunftshinweis darin enthalten sind.

- **AC-4:** Given eine Trip-Ansicht wurde online abgelegt / When der abgelegte Cache-Eintrag direkt
  ausgelesen wird, ohne dass die Seite im Browser dargestellt wird / Then enthält bereits dieses
  abgelegte Dokument die fertig formatierte Stand-Zeile.
  - Test: Playwright liest über `readCacheEntries` den abgelegten Eintrag aus `caches` aus und prüft
    den Text im Dokument selbst — die Stand-Zeile darf nicht erst durch eine Anzeige-Logik
    entstehen, sondern muss bereits im abgelegten Bytestrom stehen.

- **AC-5:** Given eine Trip-Ansicht und eine Ortsvergleichs-Ansicht wurden online abgelegt / When
  das Netz ausgeschaltet ist und von der einen offline per Verweis zur anderen gewechselt wird /
  Then erscheint die zweite Ansicht mit ihrem eigenen Stand, ohne dass ein Netzwerkfehler auftritt.
  - Test: Playwright navigiert offline per Client-seitigem Linkklick (SvelteKit lädt dabei
    `<pfad>/__data.json`, nicht die Seite selbst) von der Trip- zur Ortsvergleichs-Ansicht und
    zurück und prüft beide Stand-Zeilen.

- **AC-6:** Given die Startseite (Cockpit) wurde online besucht / When das Netz ausgeschaltet und
  die Startseite erneut aufgerufen wird / Then erscheint die Offline-Übersicht, niemals ein
  zwischengespeicherter Alarm-Stand der Startseite.
  - Test: Playwright besucht `/` online, schaltet den Kontext auf offline, ruft `/` erneut auf und
    prüft, dass die Offline-Übersicht erscheint und keine Cockpit-Alarm-Kachel sichtbar ist.

- **AC-7:** Given normale Nutzung der App — Besuch von Startseite, Archiv, einer Trip-Ansicht und
  einer Ortsvergleichs-Ansicht / When der gesamte Gerätespeicher danach ausgelesen wird / Then
  enthält er keinen Eintrag zu `/api/cockpit/status`, keinen zu `/api/archive/stats` und keine
  Seitenantwort von `/` oder `/archiv`.
  - Test: Playwright durchklickt alle vier Bereiche und listet anschließend jeden Eintrag jedes
    Cache-Bestands auf, geprüft gegen diese vier Ausschlüsse.

- **AC-8:** Given die App wird ohne Netz benutzt / When die Offline-Übersicht erscheint, weil eine
  Alarme führende Ansicht (Startseite oder Archiv) nicht vorgehalten wird / Then trägt sie einen
  eigenen, sichtbaren Satz, dass Alarme ohne Netz nicht abrufbar sind — die Abwesenheit der
  Alarm-Anzeige wird also ausdrücklich benannt und nicht stillschweigend übergangen.
  - Test: Playwright ruft `/` und `/archiv` offline auf und prüft, dass der Hinweis auf nicht
    abrufbare Alarme als eigener sichtbarer Text vorhanden ist — nicht nur, dass die Alarm-Kachel
    fehlt (das prüft bereits AC-6).

- **AC-9:** Given eine Trip-Ansicht wird ohne Netz aus dem Gerätespeicher angezeigt / When die
  Bearbeitungs- und Speichern-Elemente dieser Ansicht betrachtet werden / Then sind sie sichtbar,
  aber gesperrt, und tragen jeweils eine sichtbare Begründung für die Sperre.
  - Test: Playwright prüft den gesperrten Zustand und den sichtbaren Begründungstext mehrerer
    Bearbeitungsflächen (Etappen-Editor, Alarm-Tab, Speichern-Knopf).

- **AC-10:** Given eine gesperrte Bearbeitungsfläche in einer offline gezeigten Ansicht / When der
  Nutzer trotzdem versucht, sie zu bedienen / Then löst das keinen Schreibvorgang aus.
  - Test: Playwright zeichnet den Netzwerkverkehr während des Bedienversuchs auf und prüft, dass
    keine schreibende Anfrage abgeschickt wird.

- **AC-11:** Given eine Trip-Ansicht wurde mit Netz geöffnet und ist normal bedienbar / When das
  Netz danach wegfällt, ohne dass die Seite neu geladen wird / Then sperren sich die Bearbeitungs-
  und Speichern-Elemente und zeigen ihre Begründung, obwohl die Ansicht nicht aus dem
  Gerätespeicher, sondern live geladen wurde.
  - Test: Playwright öffnet die Ansicht online, schaltet den Kontext ohne Neuladen auf offline und
    prüft, dass die Elemente **ohne vorherigen Bedienversuch** gesperrt sind und die Begründung
    erscheint — die Sperre darf nicht erst durch einen fehlgeschlagenen Speicherversuch entstehen.

- **AC-12:** Given Nutzer A hat auf einem Browserprofil Inhalte offline abgelegt und sich
  ordnungsgemäß abgemeldet / When sich Nutzer B auf demselben Profil anmeldet und die App ohne Netz
  nutzt / Then sieht Nutzer B keinen der Inhalte von Nutzer A.
  - Test: Playwright meldet A im selben Kontext an, besucht Trip- und Vergleichsansicht, meldet ab,
    meldet B im selben Kontext (Profil) an, schaltet offline und prüft, dass As Cache-Einträge
    fehlen und keine seiner Ansichten erreichbar ist.

- **AC-13:** Given eine authentifizierte Seitenantwort, der aus einem Fehlerfall heraus der
  Mandanten-Header fehlt / When der Worker diese Antwort verarbeitet / Then wird sie nicht im
  Gerätespeicher abgelegt.
  - Test: Playwright fängt die Antwort per Routen-Mock ab, entfernt den Mandanten-Header und prüft,
    dass danach kein neuer Cache-Eintrag zu dieser Adresse existiert.

- **AC-14:** Given Nutzer A hat Inhalte abgelegt, sich aber nicht abgemeldet / When sich Nutzer B
  auf demselben Profil anmeldet und den ersten Online-Abruf einer Trip- oder Ortsvergleichs-Ansicht
  auslöst / Then wird As Daten-Speicherbereich bei genau diesem ersten Abruf gelöscht.
  - Test: Playwright meldet A an, legt Inhalt ab, wechselt im selben Kontext zu B ohne
    Abmelde-Aufruf, löst einen Online-Abruf aus und prüft, dass As Cache-Name danach nicht mehr
    existiert.

- **AC-15:** Given ein Nutzer mit gefülltem Inhaltsspeicher (Trip- und/oder Ortsvergleichs-Ansicht
  abgelegt) / When er sich abmeldet — über die Seitenleiste oder über „Auf allen Geräten abmelden"
  / Then ist auch der Inhaltsspeicher vollständig leer, nicht nur der Programm-Cache.
  - Test: Playwright füllt den Inhaltsspeicher, meldet über beide Wege ab und liest jeweils
    `caches.keys()` samt Einträgen aus.

- **AC-16:** Given ein Nutzer mit abgelegtem Inhalt / When ein angenommenes Programm-Update
  eintritt / Then bleibt der offline vorgehaltene Inhalt unverändert erhalten.
  - Test: Playwright legt Inhalt ab, löst ein Update aus, tippt „Jetzt aktualisieren" an und prüft
    nach dem Neuladen, dass der Inhaltscache weiterhin vorhanden und lesbar ist.

- **AC-17:** Given der Inhaltsspeicher hat die festgelegte Obergrenze an abgelegten Ansichten
  erreicht / When eine weitere Ansicht abgelegt wird / Then wird die älteste abgelegte Ansicht
  entfernt, während die neue erhalten bleibt.
  - Test: Playwright legt mehr Ansichten ab, als die Obergrenze erlaubt, und prüft, dass die
    älteste fehlt, während die übrigen inklusive der neuesten vorhanden sind.

- **AC-18:** Given die installierte App wird ohne Netz gestartet / When die Offline-Übersicht
  erscheint / Then listet sie die vorgehaltenen Ansichten jeweils mit ihrem Stand auf, und das
  Öffnen eines gelisteten Eintrags zeigt die zugehörige Ansicht.
  - Test: Playwright legt vorher zwei Ansichten ab, startet offline auf `/`, prüft die Liste samt
    Stand-Angaben und klickt einen Eintrag an, um die Ansicht zu öffnen.

## Known Limitations

- Die Listenseiten (`/trips`, `/compare`, `/locations`), die Startseite und das Archiv werden
  offline nicht vorgehalten; der Einstieg läuft über die Offline-Übersicht (Abschnitt G).
- Es wird nichts bearbeitet und nichts gepuffert — Änderungen an einer offline gezeigten Ansicht
  sind grundsätzlich unmöglich, nicht nur eingeschränkt (PO-Entscheid 2026-09-05).
- Live-Wetterabrufe und Vorschauen (`/api/forecast`, `/api/trips/{id}/stages/weather`, alle
  `/api/preview/...`) bleiben ohne Netz unerreichbar — sie liegen unter `/api/` und fallen damit
  unter die seit #2128 geltende harte Ausschlussregel.
- Die bestehenden Nachweise `frontend/e2e/pwa-grundausstattung.spec.ts` (AC-6, AC-7, AC-21) und
  `frontend/e2e/pwa-update-und-abmelden.spec.ts` (Erwartung „genau ein Cache-Name") werden durch
  diese Scheibe bewusst umgeschrieben: AC-6/AC-7/AC-21 prüfen künftig „Programm **und**
  Positivlisten-Daten" statt „nur Programm", und die Cache-Zahl-Erwartung wird auf „Programm-Cache
  plus höchstens ein Daten-Cache" angepasst. Das ist Teil des Umfangs dieser Scheibe, kein
  Kollateralschaden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0062 (neu anzulegen, Fortschreibung von ADR-0061)
- **Rationale:**
  1. **Ablage-Positivliste statt Feldfilter oder Endpunkt-Split** — nur `/trips/[id]` und
     `/compare/[id]` (Seitenantwort und `__data.json`) werden abgelegt; `/` und `/archiv` sind
     dauerhaft ausgeschlossen, weil sie Alarm-Historie führen. Das löst die Alarm-Abgrenzung auf
     Routenebene, ohne den Go-Handler `/api/cockpit/status` aufzuspalten und ohne
     `docs/reference/api_contract.md` zu berühren.
  2. **Der Stand wird beim Ablegen in die Kopie eingeschrieben, nicht beim Ausliefern per Client-JS
     nachträglich eingeblendet** — sonst gäbe es ein Zeitfenster, in dem ein alter Stand
     ungekennzeichnet sichtbar wäre, auch vor der Hydrierung. Das verbietet das Ticket ausdrücklich.
  3. **Mandantenkennung über einen signierten Antwort-Header, nicht per `postMessage` an den
     Worker** — der Worker-Prozess kann zwischen zwei Ereignissen vom Browser beendet werden und
     verliert dabei jeden In-Memory-Zustand; ein Header aus derselben Sitzung, die den Inhalt schon
     autorisiert hat, ist die einzige Quelle ohne zweiten Wahrheitsträger. Fehlt der Header, wird
     grundsätzlich nicht abgelegt (fail-closed, ADR-0003).
  4. **Nutzerwechsel wird beim ersten Online-Abruf des neuen Nutzers geräumt, nicht über ein neues
     Ereignis oder einen Timer** — dieselbe Kennungsprüfung, die jede Ablage ohnehin durchläuft,
     erkennt einen fremden Bestand und entfernt ihn sofort; kein zusätzlicher Zustand, kein
     Zeitfenster mit zwei koexistierenden Mandanten-Beständen.
  5. **Cache Storage exklusiv, kein IndexedDB, kein localStorage** — damit bleibt
     `raeumeGeraetespeicher()` aus #2128 unverändert wirksam, weil sie bereits ungefiltert über
     `caches.keys()` iteriert; eine zweite Speicherart hätte die Räumfunktion selbst angefasst und
     ein neues Fehlerrisiko für „beim Abmelden bleibt doch etwas liegen" geschaffen.
  6. **Offline-Übersicht statt Ablage von `/`** — der Homescreen-Start (`start_url: "/"`) trifft
     ausgerechnet die Route mit der Alarm-Kachel. Statt Alarm-Bereiche per Textmanipulation aus
     einem abgelegten `/`-Dokument herauszuschneiden (Risiko: Fehler genau an der Stelle, deren
     Fehlgehen die gefährlichste Anzeige des Produkts erzeugt), listet die bestehende Offline-Seite
     aus #2128 die abgelegten Ansichten mit Titel und Stand auf — ohne dass `/` selbst je abgelegt
     würde.
  7. **Kein Umbau der Ladewege auf universal `+page.ts`** — technisch sauberer für die Kennzeichnung,
     aber ein Umbau der gesamten SSR-Kette (Auth-Weiterleitung, Fehlerbehandlung, jede Ansicht) und
     damit ein eigenes Vorhaben, kein Nebeneffekt dieser Scheibe. Die Positivliste erreicht dasselbe
     Ziel mit deutlich kleinerem Eingriff.

## Changelog

- 2026-09-06: Initial spec created (Issue #2131, Scheibe 4 zu Epic #2127)
