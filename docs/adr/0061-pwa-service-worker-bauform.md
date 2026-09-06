# ADR-0061: PWA-Bauform — handgeführter Service Worker, vier Speicherregeln, Update erst auf Nachfrage

- **Status:** Akzeptiert
- **Datum:** 2026-09-06
- **Bezug:** ergänzt [ADR-0003](0003-multi-tenant-isolation.md) (Mandantentrennung) · `frontend/src/service-worker.ts`, `frontend/src/lib/pwa/serviceWorkerUpdate.ts`, `frontend/static/offline.html`, Issue #2128 (Scheibe 1 von Epic #2127)

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

### 2. Vier Speicherregeln, Reihenfolge bindend

| # | Anfrageart | Verhalten |
|---|---|---|
| 1 | Pfad beginnt mit `/api/` | Der Worker fasst sie **gar nicht** an — kein `respondWith`, der Browser holt selbst. Kein Lesen, kein Schreiben, keine Ausnahme. |
| 2 | Seitenaufruf (`request.mode === 'navigate'`) | Nur Netz, **nie** ablegen. Bei Netzfehler `offline.html` aus dem Speicher. |
| 3 | Programmdatei (`build` + `files` aus `$service-worker`) | Aus dem Speicher; Fehlgriff wird aus dem Netz beantwortet **und nachgelegt**. |
| 4 | alles Übrige | Netz, ohne Ablage. |

Die `/api/`-Grenze ist hart und steht vor allen anderen Regeln, damit sie auch
den Vorabruf beim Überfahren von Verweisen
(`data-sveltekit-preload-data="hover"`) erfasst — gerade der nutzerbezogene
Abruf wäre die anfälligste Stelle für eine versehentliche Ablage.

Regel 2 hält `cache-control: no-cache` aus `frontend/src/hooks.server.ts` in
Kraft, statt es zu unterlaufen. Ein abgelegtes HTML-Dokument wäre ein
eingefrorener Stand ohne Kennzeichnung — genau das, was Leitsatz 1 verbietet.

Das Nachlegen in Regel 3 ist kein Komfort: `install` läuft für einen bereits
installierten Worker nicht erneut. Ohne das Nachlegen bliebe ein vom
Betriebssystem geleerter Zwischenspeicher dauerhaft leer, und die App liefe bei
jedem Start wieder vollständig übers Netz.

Der Speichername trägt die Version (`gz-<version>`); `activate` löscht jeden
anderen Namen. Damit gibt es keinen unbemerkt weiterlebenden Altbestand.

### 3. Kein automatisches `skipWaiting`

`self.skipWaiting()` steht ausschließlich im `message`-Zweig und reagiert nur
auf `{type:"SKIP_WAITING"}`. Der Client zeigt bei einer bereitstehenden neuen
Fassung den Hinweis „Neue Version verfügbar" und schickt die Nachricht erst auf
Antippen; beim Wechsel der Kontrolle lädt er genau einmal neu. Bei der
Erstinstallation (kein `controller` vorhanden) erscheint kein Hinweis.

Registriert wird der Worker **nicht** von der App: SvelteKit tut das selbst
(`config.kit.serviceWorker.register` ist per Default `true`). Ein eigenes
`navigator.serviceWorker.register(...)` wäre eine Doppelregistrierung.

### 4. Räumen nur nach einem echten Abmelde-Vorgang

Beide Abmelde-Wege hängen ein Merkmal an das Redirect-Ziel; nur darauf löscht
die Anmeldeseite alle Caches und meldet den Worker ab. Bedingungsloses Räumen
beim Betreten der Anmeldeseite ist ausdrücklich ausgeschlossen: dort landet auch,
wessen Sitzung abgelaufen ist oder wer die Seite schlicht aufruft — das würde
die Offline-Fähigkeit genau dann zerstören, wenn sie gebraucht wird.

### 5. Inhalte bleiben online-gebunden

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
