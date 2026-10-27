# ADR-0063: PWA-Offline-Inhalte — Ablage-Positivliste, Mandanten-Bucket über Header, Alarm-Flächen bewusst ausgeschlossen

- **Status:** Akzeptiert
- **Datum:** 2026-09-08
- **Bezug:** schreibt [ADR-0061](0061-pwa-service-worker-bauform.md) fort (Speicherregeln, Cache-Name-Bauform) ·
  ergänzt [ADR-0003](0003-multi-tenant-isolation.md) (Mandantentrennung) · knüpft an
  [ADR-0034](0034-herkunftsfusszeile-reale-datenquelle.md) (kennzeichnen statt weglassen) ·
  `frontend/src/service-worker.ts`, `frontend/src/hooks.server.ts`,
  `docs/specs/modules/pwa_offline_ansicht_letzter_stand.md`, Issue #2131 (Scheibe 4 von Epic #2127)

## Kontext

ADR-0061 hatte den Service Worker aus #2128 bewusst auf reine Programmdateien beschränkt und
unter „Inhalte bleiben online-gebunden" ausdrücklich festgehalten, dass Offline-Inhalte mit
Stand-Kennzeichnung eine eigene, spätere Entscheidung brauchen. Genau diese Scheibe ist #2131:
Ohne Netz soll die App die zuletzt geladene Trip-Ansicht und die zuletzt geladene
Ortsvergleichs-Ansicht weiterhin zeigen — statt der bloßen Offline-Seite.

Zwei Risiken aus ADR-0061 wirken hier fort und werden schärfer, sobald tatsächlich Inhalte
abgelegt werden. Erstens die Mandantentrennung: ein Speicher, der nutzerbezogene Antworten
aufbewahrt, darf einem später angemeldeten anderen Nutzer auf demselben Gerät nichts von seinem
Vorgänger zeigen. Zweitens ein neues, spezifisches Risiko dieser Scheibe: die App zeigt
Wetter-Alarme auf der Startseite und im Archiv. Ein zwischengespeicherter Alarm-Stand wäre
gefährlicher als gar keine Anzeige — ein Wanderer, der einer veralteten Entwarnung vertraut, ist
schlechter dran als einer, der weiß, dass er offline keine Alarme sehen kann.

Zusätzlich navigiert SvelteKit clientseitig nicht per vollständigem Seitenaufruf, sondern holt
bei jedem Linkklick `<pfad>/__data.json` nach — eine eigene Anfrageklasse, die ADR-0061 noch
nicht kannte, weil sie bei reinen Programmdateien nicht auftaucht. Und `start_url` im Manifest
zeigt auf `/`, ausgerechnet die Route mit der Alarm-Kachel: ohne Gegenmaßnahme würde die vom
Homescreen gestartete App offline immer in einer Sackgasse landen.

## Entscheidung

Es entsteht ein zweiter Cache-Bucket `gz-daten-<mandanten-hash>` neben dem Programm-Cache aus
ADR-0061, mit eigener Mandantentrennung, eigener Positivliste und eigener Verdrängung.

### 1. Ablage-Positivliste statt Feldfilter oder Endpunkt-Split

Abgelegt werden Seitenantwort **und** `__data.json` ausschließlich von `/trips/[id]` und
`/compare/[id]`. Die Startseite (Cockpit) und `/archiv` sind dauerhaft ausgeschlossen — sie sind
die einzigen beiden Routen, die Alarm-Historie zeigen. Damit erledigt sich „Alarme werden nicht
zwischengespeichert" auf URL-Ebene, ohne einen Feldfilter im Go-Handler und ohne einen
Endpunkt-Split von `/api/cockpit/status`. Alarm-*Konfiguration* (`trip.alert_rules`) darf
mitgehen; gemeint sind die ausgelösten Alarme, nicht die Einstellungen dazu.

### 2. Der Stand wird beim Ablegen eingeschrieben, nicht beim Ausliefern

Der Worker klont die erfolgreiche Netzantwort, ersetzt darin ein festes Markierungselement aus
dem Root-Layout durch die fertig formatierte Stand-Zeile und legt diese Kopie ab; die live
ausgelieferte Antwort bleibt unverändert. Der Stand steht damit im ersten Byte des offline
ausgelieferten Dokuments — es gibt kein Zeitfenster, in dem ein alter Stand ungekennzeichnet
sichtbar wäre, auch nicht vor der Hydrierung. Eine nachträgliche Einblendung per Client-JS wäre
genau dieses Zeitfenster gewesen.

### 3. Mandantenkennung über einen signierten Antwort-Header, fail-closed

`hooks.server.ts` hängt an jede authentifizierte Nicht-`/api/`-Antwort einen kurzen Hash von
`event.locals.userId`. Der Worker liest ihn beim Ablegen und bildet daraus den Cache-Namen
(`gz-daten-<hash>`, getrennt vom Programm-Cache `gz-${version}`). **Fehlt der Header, wird nicht
abgelegt.** Die Kennung stammt aus derselben signierten Sitzung, die den Inhalt bereits
autorisiert hat — keine zweite Wahrheitsquelle und kein Zustand, der ein Prozessende des Workers
überleben müsste.

### 4. Nutzerwechsel wird beim ersten Online-Abruf geräumt

Weil die Kennung an jeder Antwort hängt, prüft der Worker bei jeder Ablage, ob im Datenspeicher
bereits ein Bucket mit fremder Kennung existiert, und löscht ihn sofort. Das schließt auch den
Fall „Nutzer B meldet sich an, ohne dass Nutzer A sich vorher abgemeldet hat" — ohne neue
Speicherart und ohne Zeitfenster, in dem beide Bestände nebeneinander lägen.

### 5. Cache Storage bleibt exklusiv

Kein IndexedDB, kein localStorage — wie schon in ADR-0061 für den Programm-Cache festgelegt.
`raeumeGeraetespeicher()` aus #2128 iteriert `caches.keys()` ungefiltert; der neue Bucket läuft
damit automatisch mit, ohne dass die Räumfunktion selbst angefasst werden müsste.

### 6. Der `activate`-Sweep spart Datencaches aus

Der Bestandssweep aus #2128 löscht jeden Cache-Namen ungleich dem aktuellen Programm-Cache.
Unverändert übernommen würde der abgelegte Stand nach jedem angenommenen Update gelöscht — die
Bedingung wird auf Programm-Cache-Namen präzisiert. Datencaches bleiben von diesem Sweep
unberührt und unterliegen stattdessen der eigenen Obergrenze mit Ältestes-zuerst-Verdrängung.

### 7. Offline-Übersicht statt Ablage von `/`

Die Offline-Seite aus #2128 wird von einer Sackgasse zu einer Übersicht: ein gescheiterter
Seitenaufruf wird mit einer Liste der abgelegten Ansichten (Titel, Stand) beantwortet, gespeist
aus derselben Obergrenze. Damit ist der Homescreen-Start offline brauchbar, ohne dass `/` selbst
je abgelegt werden müsste.

### 8. Bearbeitungssperre zweistufig, beide Stufen fail-closed

Ein statischer Zustand für aus dem Gerätespeicher geladene Dokumente (die Stand-Markierung im
HTML sperrt bedingungslos) und ein Laufzeit-Zustand für den Fall „online geöffnet, Netz fällt
danach weg" (`verbindung.svelte.ts`): sofortiges Sperren auf das `offline`-Ereignis und auf jeden
tatsächlich fehlgeschlagenen Abruf, Entsperren ausschließlich nach einem nachweislich gelungenen
Abruf — nie allein auf das `online`-Ereignis, weil es nur eine Netzwerkschnittstelle meldet,
keinen erreichbaren Server.

## Verworfene Alternativen

- **Alarm-Bereiche per Textmanipulation aus einem abgelegten `/`-Dokument herausschneiden.**
  Verworfen: Eingriff genau an der Stelle, deren Fehlgehen die gefährlichste Anzeige des Produkts
  erzeugen würde — ein Parsing-Fehler ließe einen Alarm-Stand stehen.
- **Mandantenkennung per `postMessage` an den Worker statt per Header.** Verworfen: der
  Worker-Prozess kann zwischen zwei Ereignissen vom Browser beendet werden und verliert dabei
  jeden In-Memory-Zustand; ein Header aus derselben Sitzung, die den Inhalt schon autorisiert
  hat, braucht keinen zweiten, potenziell veralteten Wahrheitsträger.
- **Umbau aller Ladewege auf universal `+page.ts`**, damit der SSR-Loader die einzige
  Datenquelle bliebe. Verworfen: technisch sauberer für die Kennzeichnung, aber ein Umbau der
  gesamten SSR-Kette (Auth-Weiterleitung, Fehlerbehandlung, jede Ansicht) und damit ein eigenes
  Vorhaben, kein Nebeneffekt dieser Scheibe.
- **Nutzerwechsel über ein eigenes Ereignis oder einen Timer räumen.** Verworfen: die
  Kennungsprüfung läuft ohnehin bei jeder Ablage mit — ein zusätzlicher Auslöser wäre zweiter
  Zustand ohne Zusatznutzen und mit eigenem Zeitfenster-Risiko.
- **Entsperren bereits auf das `online`-Ereignis.** Verworfen: `navigator.onLine` meldet nur eine
  vorhandene Netzwerkschnittstelle, nicht einen erreichbaren Server — ein Funkloch mit
  eingebuchtem Netz oder ein WLAN-Anmeldeportal würde eine Fläche scheinbar wieder bedienbar
  machen, deren Schreibversuch weiterhin ins Leere liefe.

## Konsequenzen

**Positiv**

- Die Alarm-Abgrenzung ist eine Routen-Positivliste, keine Feld- oder Endpunkt-Unterscheidung —
  sie berührt weder `docs/reference/api_contract.md` noch den Go-Handler.
- Der Stand ist untrennbar Teil des abgelegten Bytestroms; es gibt keinen Anzeige-Pfad, der ihn
  vergessen könnte.
- Die Mandantentrennung braucht keinen zweiten Wahrheitsträger und keinen Worker-Zustand über
  Ereignisgrenzen hinweg.
- Der Homescreen-Start ist offline nutzbar, ohne dass die gefährlichste Fläche des Produkts
  jemals in den Gerätespeicher gelangt.

**Negativ / Preis**

- Zwei Cache-Buckets statt einem: jede Änderung an der Ablage-Positivliste muss künftig bewusst
  entschieden werden, es gibt keine Automatik. Das ist beabsichtigt, so wie schon in ADR-0061 bei
  den vier Speicherregeln.
- Die Listenseiten (`/trips`, `/compare`, `/locations`) und das Archiv bleiben offline nicht
  einsehbar; nur die Offline-Übersicht dient als Navigationsweg. Eine bewusste Einschränkung
  dieser Scheibe, keine vergessene Fläche.
- Ein fehlerhafter Mandanten-Header (z. B. durch einen Fehler in `hooks.server.ts`) führt dazu,
  dass gar nichts abgelegt wird — fail-closed nimmt hier lieber „keine Offline-Ansicht" in Kauf
  als „falsche Offline-Ansicht".

**Folgepflichten**

- Jede neue Route, die künftig offline verfügbar sein soll, muss bewusst in die Positivliste
  aufgenommen werden — eine implizite Erweiterung über Musterabgleich ist ausdrücklich nicht
  vorgesehen.
- Jede neue alarmführende Fläche bleibt von dieser Positivliste fernzuhalten; wird eine bestehende
  Positivlisten-Route (`/trips/[id]`, `/compare/[id]`) jemals um eine Alarm-Anzeige erweitert,
  braucht das eine erneute Prüfung dieser Entscheidung, kein stillschweigendes Mitlaufen.
- Bearbeitungs- und Speichern-Elemente auf `/trips/[id]` und `/compare/[id]` müssen bei jeder
  Erweiterung an das Sperr-Inventar (`offlineGate.ts`/`OfflineSperre.svelte`) angeschlossen
  werden — eine neue Schreibfläche ohne Anschluss würde offline scheinbar bedienbar bleiben.
