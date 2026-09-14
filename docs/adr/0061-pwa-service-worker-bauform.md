# ADR-0061: PWA-Bauform — handgeführter Service Worker, fünf Speicherregeln, Update erst auf Nachfrage

- **Status:** Akzeptiert
- **Datum:** 2026-09-06 (§3 fortgeschrieben 2026-09-13, Issue #2316: aktive Update-Erkennung; Titel/§2 korrigiert — seit #2131 sind es fünf Speicherregeln, nicht vier; §3 fortgeschrieben 2026-09-14, Issue #2317: Warten auf eine ausstehende Speicherung vor `SKIP_WAITING`)
- **Bezug:** ergänzt [ADR-0003](0003-multi-tenant-isolation.md) (Mandantentrennung) · `frontend/src/service-worker.ts`, `frontend/src/lib/pwa/serviceWorkerUpdate.ts`, `frontend/static/offline.html`, Issue #2128 (Scheibe 1 von Epic #2127), Issue #2131 (Positivliste, Regel 2), Issue #2316 (aktive Update-Erkennung)

## Kontext

Die App soll auf Android und iOS vom Startbildschirm starten, ohne Netz eine
eigene verständliche Seite zeigen statt der Browser-Fehlerseite, ihre Schriften
selbst ausliefern und ein Programm-Update erst laden, wenn der Nutzer es
antippt. Dafür braucht es erstmals einen Service Worker — also erstmals einen
Gerätespeicher, in dem Antworten des Servers liegen bleiben.

Genau da liegt das Risiko. Das Produkt ist mandantenfähig: auf demselben Gerät
kann sich nacheinander mehr als ein Nutzer anmelden. Ein Speicher, der
nutzerbezogene Antworten aufbewahrt, zeigt dem nächsten Nutzer fremde Daten —
ein Bruch von ADR-0003, den der Nutzer nicht bemerken würde, weil die Anzeige
völlig normal aussieht.

Zweitens ist ein Service Worker zäh: er überlebt Neuladen und kann eine
fehlerhafte Programmversion festhalten. Ein Update, das sich selbst
durchdrückt, kann eine laufende Sitzung mitten in der Arbeit umschalten — auf
einer Tour die denkbar schlechteste Eigenschaft.

## Entscheidung

**Der Service Worker wird handgeführt geschrieben — kein `vite-plugin-pwa`,
kein Workbox.** Seine Speicherregeln sind abschließend aufgezählt, seine
Update-Übernahme braucht eine Nutzerhandlung.

### 1. Kein Generator-Werkzeug

`vite-plugin-pwa`/Workbox nehmen einem den Worker ab, bringen aber ihre eigenen
Voreinstellungen mit: Laufzeit-Strategien, die auch Datenantworten ablegen
(`NetworkFirst`/`StaleWhileRevalidate` über ganze URL-Muster), und
`skipWaiting`/`clientsClaim` als bequeme Voreinstellung. Beides ist hier
verboten — das erste durch Leitsatz 1 und 2 aus Epic #2127 und durch ADR-0003,
das zweite durch Leitsatz 4. Ein Werkzeug, dessen Voreinstellungen man
vollständig abschalten muss, spart nichts und verdeckt die entscheidende Zeile.
Der handgeführte Worker ist ~60 Zeilen und in vier Regeln lesbar.

### 2. Fünf Speicherregeln, Reihenfolge bindend

Ursprünglich vier Regeln (2026-09-06); Issue #2131 hat eine **fünfte** eingefügt
(Positivliste vorgehaltener Ansichten) und dabei die frühere Regel 2
(„Seitenaufruf, nur Netz") zu Regel 3 verschoben — Titel und diese Tabelle
sprachen bis 2026-09-13 fälschlich weiter von „vier".

| # | Anfrageart | Verhalten |
|---|---|---|
| 1 | Pfad beginnt mit `/api/` | Der Worker fasst sie **gar nicht** an — kein `respondWith`, der Browser holt selbst. Kein Lesen, kein Schreiben, keine Ausnahme. |
| 2 | Positivliste vorgehaltener Ansichten (`/trips/<id>`, `/compare/<id>`, je Seitenantwort und `__data.json`, Issue #2131) | Netz zuerst und dabei ablegen (`netzSonstSpeicher`); ohne Netz Antwort **mit Stand-Kennzeichnung** aus dem eigenen Speicher. |
| 3 | übriger Seitenaufruf (`request.mode === 'navigate'`) | Nur Netz, **nie** ablegen. Bei Netzfehler `offline.html`/die Offline-Übersicht aus dem Speicher. |
| 4 | Programmdatei (`build` + `files` aus `$service-worker`) | Aus dem Speicher; Fehlgriff wird aus dem Netz beantwortet **und nachgelegt**. |
| 5 | alles Übrige | Netz, ohne Ablage. |

Die `/api/`-Grenze ist hart und steht vor allen anderen Regeln, damit sie auch
den Vorabruf beim Überfahren von Verweisen
(`data-sveltekit-preload-data="hover"`) erfasst — gerade der nutzerbezogene
Abruf wäre die anfälligste Stelle für eine versehentliche Ablage.

**Feststellung zu Regel 1 (ausdrücklich, kein blinder Fleck):** Regel 1 ist
heute *wirkungsgleich redundant* zu Regel 5 (die frühere Regel 4 „alles
Übrige", durch die #2131-Positivliste um eine Position verschoben). Entfernt
man sie ersatzlos, fällt eine `/api/`-Anfrage durch bis Regel 5 — und die legt
nichts ab. Es gibt also derzeit keinen Nachweis, der allein auf das Entfernen
von Regel 1 rot wird; das ist kein Versäumnis, sondern die Folge davon, dass
Regel 5 nichts tut. Regel 1 steht als **ausdrückliche Grenze für den Fall, dass
Regel 5 je etwas ablegt** — und genau dieser Fall ist bewacht: `AC-21` prüft,
dass nach normaler Nutzung **ausschließlich** Programm- und
Positivlisten-Daten im Gerätespeicher liegen, und schlägt damit bei jeder
Änderung an, die Regel 5 zu einem Ablage-Zweig macht (`/api/` dabei
automatisch mit erfasst). Beide Nachweise (`AC-6`, `AC-21`) lösen zusätzlich
einen echten `/api/`-Abruf aus dem Browser aus, weil die Seitenwechsel ihre
Daten serverseitig holen — ohne ihn berührte kein Nachweis die `/api/`-Grenze.

Regel 2 (Issue #2131) legt Trip-/Vergleichs-Ansichten **mit Stand-
Kennzeichnung** ab — die einzige Ausnahme von „Inhalte bleiben
online-gebunden" (§5, unten präzisiert). Regel 3 hält `cache-control:
no-cache` aus `frontend/src/hooks.server.ts` für alle übrigen Seitenaufrufe in
Kraft, statt es zu unterlaufen. Ein dort abgelegtes HTML-Dokument wäre ein
eingefrorener Stand ohne Kennzeichnung — genau das, was Leitsatz 1 verbietet.

Das Nachlegen in Regel 4 ist kein Komfort: `install` läuft für einen bereits
installierten Worker nicht erneut. Ohne das Nachlegen bliebe ein vom
Betriebssystem geleerter Zwischenspeicher dauerhaft leer, und die App liefe bei
jedem Start wieder vollständig übers Netz.

Der Speichername trägt die Version (`gz-<version>`); `activate` löscht jeden
anderen Namen. Damit gibt es keinen unbemerkt weiterlebenden Altbestand.

### 3. Kein automatisches `skipWaiting` — und aktives, aber sparsames Prüfen (Issue #2316)

`self.skipWaiting()` steht ausschließlich im `message`-Zweig und reagiert nur
auf `{type:"SKIP_WAITING"}`. Der Client zeigt bei einer bereitstehenden neuen
Fassung einen Zweiknopf-Hinweis „Aktualisieren"/„Später" und schickt die
Nachricht erst auf Antippen; beim Wechsel der Kontrolle lädt er genau einmal
neu. Bei der Erstinstallation (kein `controller` vorhanden) erscheint kein
Hinweis.

Registriert wird der Worker **nicht** von der App: SvelteKit tut das selbst
(`config.kit.serviceWorker.register` ist per Default `true`). Ein eigenes
`navigator.serviceWorker.register(...)` wäre eine Doppelregistrierung.

**Fortschreibung 2026-09-13 (Issue #2316):** bis dahin bemerkte die App ein
Update nur zufällig, beim nächsten vollständigen Neustart. Jetzt prüft
`serviceWorkerUpdate.ts` aktiv, ohne die Nicht-Vorlade-Regel (Leitsatz 1/2 aus
Epic #2127) zu verletzen — `registration.update()` fragt beim Server nur das
Worker-Skript selbst ab (0 Byte dank ETag-Revalidierung, außer bei echter
neuer Fassung), niemals Programmdateien:

- **Auslöser:** `visibilitychange` (beim Sichtbarwerden), `pageshow`, ein
  30-Minuten-Intervall, das **nur läuft, solange die Seite sichtbar ist**
  (Timer stoppt beim Verstecken, startet beim erneuten Sichtbarwerden neu).
- **Drossel:** höchstens eine tatsächliche Prüfung pro 60 Sekunden, über eine
  hereingereichte Uhr (testbar, kein `Date.now()` direkt im Kern). Wartet
  bereits ein installierter Worker, lösen weitere Auslöser gar keine Prüfung
  mehr aus.
- **„Später":** modul-interner Zustand ohne Persistenz — hält bis zum nächsten
  echten Kaltstart (Modul-Neuinitialisierung), nicht bis zum nächsten
  Sichtbarwerden.
- **Rückfall ohne blinden Reload:** erreicht der übernommene Worker
  `activated`, aber `controllerchange` bleibt aus, lädt das Fenster nach 4
  Sekunden **genau einmal** automatisch neu (Timer hereingereicht, gegen
  einen späten `controllerchange` UND gegen einen zweiten Timer-Lauf
  abgesichert). Bleibt der Worker dagegen in `installed` hängen (Download im
  Worker gescheitert), wird **kein** Timer scharf — sonst würde ein
  gescheiterter Download in einen Reload auf dieselbe alte Fassung
  umgedeutet, ohne dass der Nutzer vom Fehlschlag erführe.
- **Fehlschlag-Meldung:** scheitert `programmdateienAblegen()` im `message`-
  Zweig des Workers (Netzfehler vor `skipWaiting()`), meldet der Worker
  `{type:'UPDATE_FEHLGESCHLAGEN'}` an **alle** Fenster
  (`clients.matchAll({ includeUncontrolled: true })` — der neue, noch nicht
  kontrollierende Worker sähe mit dem Default `includeUncontrolled: false`
  sonst keine Fenster und die Meldung verpuffte). Das Fenster zeigt eine
  verständliche Meldung, lädt nicht neu, die alte Fassung bleibt aktiv, und
  „Aktualisieren" bleibt antippbar.
- **Zurückgehalten** wird der Hinweis auf `/trips/new` und `/compare/new`
  (Anlege-Zustand lebt nur im Speicher, ein Reload verlöre ihn unbemerkt) und
  während der iOS-Installationshinweis oder das Passkey-Angebot am unteren
  Bildschirmrand sichtbar sind — nie zwei Systemhinweise übereinander.

Der Mechanismus ändert nichts an dieser ADR-Grundentscheidung (Speicherregeln,
kein automatisches `skipWaiting`, kein Vorladen) — er ergänzt nur, **wann**
geprüft wird. Details/Testplan: `docs/specs/modules/pwa_update_erkennung.md`.

**Fortschreibung 2026-09-14 (Issue #2317):** Vor dem `SKIP_WAITING`-Antippen wartet der Client
über eine Anmeldestelle (`frontend/src/lib/stores/aktiveSpeicherung.ts`) jede ausstehende
Speicherung der offenen Detailseite regulär ab (mit If-Match, ohne `keepalive`) statt einen
laufenden PUT durch den Fassungswechsel abzuschneiden. Schlägt das fehl (Konflikt, Netzfehler),
unterbleibt `SKIP_WAITING`, die alte Fassung bleibt aktiv und die Fehler-/Konfliktanzeige des
Reiters steht. Ändert nichts an der Bauform hier — nur eine zusätzliche Wartebedingung vor dem
ohnehin ausschließlich nutzergesteuerten `SKIP_WAITING`. Details:
`docs/specs/modules/speicherung_beim_neuladen.md`.

### 4. Räumen nur nach einem echten Abmelde-Vorgang

Beide Abmelde-Wege hängen ein Merkmal an das Redirect-Ziel; nur darauf löscht
die Anmeldeseite alle Caches und meldet den Worker ab. Bedingungsloses Räumen
beim Betreten der Anmeldeseite ist ausdrücklich ausgeschlossen: dort landet auch,
wessen Sitzung abgelaufen ist oder wer die Seite schlicht aufruft — das würde
die Offline-Fähigkeit genau dann zerstören, wenn sie gebraucht wird.

Weil „Auf allen Geräten abmelden" sein Redirect-Ziel unterwegs verliert (der
zentrale 401-Umleiter ersetzt es), trägt dieser Weg das Merkmal zusätzlich im
Sitzungsspeicher — gesetzt **vor** dem Aufruf. Das Merkmal ist deshalb doppelt
befristet: der Fehlerzweig räumt es weg (Netzfehler wie 5xx, AC-19), und es
verfällt nach 60 Sekunden (AC-20). Sonst machte ein liegen gebliebenes Merkmal
den nächsten, völlig regulären Sitzungsablauf zu einer vermeintlichen Abmeldung
— die Anmeldeseite räumte still den Gerätespeicher, und AC-12 wäre in der
Praxis verletzt, ohne dass es jemand bemerkt. Ein echtes Abmelden navigiert
sofort und liegt weit innerhalb des Fensters.

### 5. Inhalte bleiben online-gebunden

*(Stand 2026-09-06, durch Issue #2131 inzwischen abgelöst — s. Regel 2 in §2:
Trip-/Vergleichs-Ansichten liegen seither MIT Stand-Kennzeichnung im Speicher.
Absatz bleibt als Beleg der ursprünglichen Entscheidung stehen.)*

In dieser Scheibe wird **kein Inhalt** offline verfügbar, nur Programmdateien.
Wer ohne Netz eine Seite aufruft, sieht die Offline-Seite, nicht das zuletzt
gelesene Briefing. Offline-Inhalte mit Stand-Kennzeichnung sind Scheibe 4
(#2131) und brauchen dort eine eigene Entscheidung darüber, was mit welcher
Kennzeichnung abgelegt werden darf.

## Konsequenzen

**Positiv**

- Die `/api/`-Grenze ist eine einzelne, lesbare Zeile statt einer Konfiguration
  über mehrere Strategie-Objekte — sie lässt sich prüfen und mutieren.
- Der Nutzer verliert nie unangekündigt seinen Arbeitsstand an ein Update.
- Die App startet ohne Fremd-Host: keine Anfrage an `fonts.googleapis.com`.
- Der Speicher ist nach dem Abmelden nachweislich leer (AC-11), ohne dass ein
  bloßer Besuch der Anmeldeseite ihn leert (AC-12).

**Negativ / Kosten**

- Der Worker wird von Hand gepflegt. Jede neue Klasse von Anfragen muss bewusst
  einer der vier Regeln zugeordnet werden — es gibt keine Automatik, die das
  „irgendwie" erledigt. Das ist beabsichtigt.
- Die Bestandsstrecke in Playwright läuft künftig mit abgeschaltetem Worker
  (`serviceWorkers: 'block'`), nur die PWA-Nachweise mit aktivem. Ein neuer Test,
  der Worker-Verhalten prüfen will, muss ins `pwa`-Projekt.
- Ein fehlerhafter Worker bleibt zäh. Ausstiege: der versionierte Speichername,
  das Räumen beim Abmelden und die Tatsache, dass Seitenaufrufe nie aus dem
  Speicher beantwortet werden.

## Alternativen

- **`vite-plugin-pwa` mit abgeschalteten Laufzeit-Strategien.** Verworfen: die
  Ersparnis ist gering, die Angriffsfläche der Voreinstellungen bleibt. Ein
  Versionssprung des Plugins könnte still eine Strategie hinzufügen, die
  Datenantworten ablegt — der Verstoß gegen ADR-0003 wäre unsichtbar.
- **Offline-Seite als Svelte-Route (`/offline`).** Verworfen: mit `adapter-node`
  entsteht jedes HTML-Dokument am Server; ohne Netz gäbe es nichts zu rendern.
  Zudem liefe die Route in den Auth-Guard. Eine Datei in `static/` wird vom
  `sirv`-Handler vor der Auth-Weiche beantwortet und liegt über `files` im
  Speicher.
- **Automatisches Update mit `skipWaiting` im `install`.** Verworfen durch
  Leitsatz 4 aus Epic #2127: ein Umschalten mitten in der Arbeit ist auf einer
  Tour nicht zumutbar.
- **HTML-Dokumente „stale-while-revalidate" ablegen.** Verworfen: der Nutzer
  sähe einen alten Stand, ohne dass ihm der Stand angezeigt wird. Das ist
  Scheibe 4 und braucht eine Kennzeichnung, keine stille Ablage.
