# ADR-0036: Nebenlaeufigkeitsschutz ueber Inhalts-Fingerabdruck statt Versionsfeld

- **Status:** Akzeptiert
- **Datum:** 2026-07-27
- **Bezug:** GitHub-Issue #1395 (Scheiben S1/S2), Spec
  `docs/specs/modules/issue_1395_s2_etag_ifmatch.md`

## Kontext

`UpdateTripHandler` und die uebrigen Trip-Schreibpfade machen ein reines
Read-Modify-Write ohne jeden Versionsbegriff. Treffen zwei Schreibvorgaenge
zeitlich zusammen, gewinnt der, der ZULETZT ANKOMMT — nicht der, der zuletzt
abgeschickt wurde. Bei den vorangegangenen Kaskaden-Bugs (#1389/#1390/#1393)
wurden acht Fehler in sechs Pruefrunden gefunden, alle derselben Klasse: ein
Datenstand wird im Client festgehalten und spaeter verwendet, obwohl er
inzwischen veraltet ist. Jede Runde schloss eine Luecke in einer clientseitigen
Eigenkonstruktion, die es nur gibt, weil der Server keine Nebenlaeufigkeit
kennt.

Ein serverseitiger Schutz braucht einen Stempel, der zuverlaessig anzeigt: „das
ist noch derselbe Stand, den ich zuletzt gelesen habe". Zwei Rahmenbedingungen
schraenken die Wahl ein:

1. **Dieselbe Datei wird von zwei Sprachen geschrieben.** `briefings/<id>.json`
   wird sowohl vom Go-API (`internal/store`) als auch vom Python-Kern
   geschrieben (`src/app/loader.py:1581-1648` `save_trip`) — Telegram-/
   SMS-Kommandos (`src/app/trip_command_processor.py:852,928,1046,1069,1128,1142`),
   `skip_next`-Verbrauch (`src/app/trip_report_scheduler.py:517`),
   Migrationsskripte.
2. **Der Python-Kern bewahrt unbekannte Felder ausdruecklich**
   (`_deep_merge_preserve_unknown`, `loader.py:124-137`). Ein Feld, das nur Go
   pflegt, wird von Python beim Schreiben unveraendert durchgereicht — es
   erkennt die eigene Aenderung also nicht als Anlass, den Stempel
   fortzuschreiben.

## Entscheidung

Der Nebenlaeufigkeitsschutz beruht auf einem **sha256-Fingerabdruck ueber die
tatsaechlichen Bytes der Datei auf Platte**, nicht auf einem im Dokument
mitgefuehrten Zaehler- oder Zeitstempelfeld:

- `Store.BriefingFingerprint(id)` (S1, `internal/store/briefing_fingerprint.go`)
  liest `briefings/<id>.json` und liefert den sha256-Hex-Wert der Rohbytes.
  Fehlt die Datei, ist das ein gueltiger Zustand („noch kein Stand") und kein
  Fehler.
- Der Fingerabdruck wird per HTTP-Header transportiert: `ETag` in
  GET-Antworten, `If-Match` in PUT-Anfragen (S2). Er lebt AUSSERHALB des
  Dokuments, wird also nie mit ins JSON persistiert und kann daher keinen
  Namens- oder Schema-Konflikt mit bestehenden Feldern ausloesen.
- Da er aus den tatsaechlichen Bytes berechnet wird, aendert sich der
  Fingerabdruck bei JEDER Aenderung der Datei — unabhaengig davon, ob Go oder
  Python geschrieben hat. Der Python-Schreibpfad muss dafuer NICHT angepasst
  werden.

## Verworfene Alternativen

- **`version`-Zaehlfeld im Dokument.** Verworfen: braucht eine zweite,
  spiegelbildliche Umsetzung in `loader.save_trip` — ein weiterer
  Cross-Language-Wertekontrakt der Art, die bereits #802/#1000/#1250
  eingebrockt hat. Zusaetzlich eine Schema-Aenderung in Go, TypeScript und
  `openapi.yaml`, und eine Migration fuer 19 Bestandstouren.
- **`updated_at`-Zeitstempelfeld im Dokument.** Verworfen: alle Nachteile von
  „version" PLUS eine Namenskollision mit den bereits bestehenden
  `updated_at`-Feldern in `display_config`/`report_config`/`weather_config`
  (`loader.py:1259,1444,1459,1551`), die Python bei jedem Speichern ohnehin auf
  „jetzt" setzt — die schlechteste der drei Varianten.
- **Ein Rumpf-Feld statt eines HTTP-Headers.** Verworfen: scheidet strukturell
  aus, weil bei `PUT /api/trips/{id}/weather-config` der Rumpf DIE
  Konfiguration IST. Ein `"version"`-Feld darin wuerde ununterscheidbar in
  `display_config` persistiert und selbst zu einem unbekannten, aber
  gespeicherten Konfigurationswert.

## Konsequenzen

- **Positiv:** Keine Schema-Aenderung, keine Migration, keine Aenderung am
  Python-Kern. Jede Bestandsdatei hat automatisch ab dem ersten `GET` einen
  gueltigen Fingerabdruck. Der Schutz gilt gleichermassen fuer Go- und
  Python-Schreibvorgaenge, ohne dass Python je vom Vertrag wissen muss.
- **Negativ / Preis:** Der Fingerabdruck ist nicht menschenlesbar (kein
  fortlaufender Zaehler, keine Uhrzeit) und aendert sich bei JEDER
  Byte-Aenderung — auch bei reiner In-Memory-Heilung, die beim naechsten
  Speichern zurueckgeschrieben wird (gemessener S1-Befund: ein folgenloses
  Speichern aendert die Datei trotzdem, weil `LoadTrip` beim Lesen heilt, ohne
  zurueckzuschreiben). Ein Client, der einen `ETag` aus einer GET-Antwort
  festhaelt, MUSS nach dem eigenen erfolgreichen PUT den in der PUT-Antwort
  mitgelieferten NEUEN `ETag` uebernehmen — der alte aus dem GET ist ab dem
  ersten Speichern potenziell veraltet.
- **Folgepflichten:** Jeder neue Schreibpfad auf `briefings/<id>.json` (Go oder
  Python) muss sich bewusst sein, dass sein Schreibvorgang den Fingerabdruck
  fortschreibt und damit bestehende `If-Match`-Werte anderer Clients
  entwertet — das ist der gewuenschte Effekt, keine Nebenwirkung. Kuenftige
  Konsumenten des Fingerabdrucks (z. B. das Frontend in S3, der Ortsvergleich
  in S6) uebernehmen denselben Header-Vertrag (`ETag`/`If-Match`), statt einen
  eigenen Stempel-Mechanismus zu erfinden.

## Fortschreibung (Issue #1433): Verhalten nach 412 / Teilfeld-Prinzip

Der Client verwirft den gemerkten Fingerabdruck nach einem `412` **nicht** mehr
(vorher: „Discard nach 412", der naechste Schreibvorgang lief ohne Vorbedingung
durch und ueberschrieb die Fremdaenderung). Stattdessen markiert die
ETag-Registry die Ressource als Konflikt und behaelt den alten Stempel: jeder
weitere Schreibvorgang — auch ein Unload-Flush mit `keepalive` — traegt das alte
`If-Match` und wird wieder abgelehnt, bis „Nochmal speichern" den Trip frisch
holt (GET) und alle gescheiterten Speichervorgaenge wiederholt. Dazu sendet
jeder Reiter nur seine Eigenfelder (Teilfeld-Nutzlast, `pickEigenfelder`); der
einstufige Server-Merge (`mergeConfigMap`) haelt alle nicht erwaehnten Felder.
Ein gueltiges `If-Match` zusammen mit einer veralteten Vollkopie fremder Felder
wuerde sonst 200 liefern und den Verlust absegnen — die Teilfelder sind der
eigentliche Schutz, Stempel und Konflikt-Sperre ergaenzen ihn fuer gleiche
Schluessel. Gleichzeitiges Aendern desselben Schluessels in zwei Tabs bleibt
eine bekannte Grenze. Spec: `docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md`.

**Semantik von „Nochmal speichern" (Fix-Loop 1+2, #1433).** Leitsatz: Was der Nutzer
zuletzt sah und gespeichert hat, gewinnt; es darf keine zwei Wahrheiten fuer dieselbe
Eingabe geben (Listeneintrag vs. sichtbarer Reiter).

- Scheitert der GET des Retries, bleibt der Zustand `conflict` (Liste, Markierung und
  Knopf bleiben) — die Eingaben gehen nicht verloren.
- Die Seite uebernimmt den Trip bei `'geholt'` (BEVOR die Eintraege erneut gesendet
  werden; Trip und Stempel gemeinsam, AC-19) und erfaehrt den vollen Erfolg bei
  `'wiederholt'`.
- Regel 1: bei `'geholt'` werden die Reiter NICHT neu aufgebaut — sie leiten ihren
  Zustand nur beim Mount aus `trip` ab; ein Neuaufbau liesse Listeneintrag und
  sichtbaren Reiter auseinanderlaufen. Neuaufbau nur nach vollem Erfolg; bei Teilerfolg
  verlassen die erfolgreichen Eintraege die Liste, gescheiterte bleiben, kein Remount.
- Regel 2: ein erfolgreiches Speichern (200) unter dem Schluessel eines Reiters
  entfernt dessen offenen Listeneintrag; ein aelterer Rumpf wird nie ueber eine neuere
  erfolgreiche Schreibung gespielt. Leert das die Liste, endet der Konflikt.
- AC-19-Uebernahme erfolgt in Compare erst nach vollem Retry-Erfolg, weil der
  Hub-Reiter reaktiv auf `currentPreset` hydriert (`CompareTabs.svelte`, `$effect` auf
  `preset`); dort wird nach vollem Erfolg frisch geholt. Beim Wiederholen setzen die
  Compare-Speicherfunktionen ihre Anzeige bei Nicht-412-Fehlern nicht zurueck
  (`imWiederholen`).
- Fix-Loop 4 (F301a): scheitert ein Retry (auch nur teilweise), legt der Controller den
  Stempel von VOR dem GET zurueck (einfachste sichere Variante: auch ein neuerer Stempel
  eines Teil-PUT wird nicht behalten) und die Konflikt-Markierung bleibt gesetzt; Zustand
  `conflict` mit der vollstaendigen Liste. Jeder Save eines offenen oder erstmals
  geoeffneten Reiters mit veraltetem Stand bekommt damit 412. Der frische Stempel
  wird erst nach VOLLEM Erfolg endgueltig (die Markierung faellt beim naechsten Retry).
- Bekannte Grenzen (F301b/F302, bewusst nicht im Code geaendert): (a) der Retry sendet den
  gesamten Eigenfeld-Satz des Reiters (Spec §2: Teilfeld je Reiter, nicht je geaendertem
  Schluessel) — ein Fremdwert in DERSELBEN Reiter-Gruppe wird mit dem Wert ueberschrieben,
  den der Nutzer im Reiter sah (Leitsatz oben). (b) Ein Top-Level-`null` (z. B.
  `alert_quiet_from: null` nach Leeren der Ruhezeit) wird lokal fortgeschrieben, der
  Go-Server ignoriert nil-Zeiger (`internal/handler/trip.go:371-375`) — vorbestehende
  Server-Eigenheit, nur die Anzeige im Konfliktfenster weicht ab.
- Der Seitenkopf uebernimmt den Stempel nur im Browser (`browser`-Guard): die Registry ist
  modulglobal und im SSR-Prozess nutzeruebergreifend geteilt.
- Der Bestandstest `apiTripEtagHeaders` ist durch AC-18/AC-24 umgeschrieben (der
  Stempel bleibt nach 412 stehen, statt verworfen zu werden).

**Eine Wahrheit: Seitenstand = letzter Serverstand ⊕ ausstehende Nutzlasten (Fix-Loop 3, #1433).**
Wurzel von F101/F201: Nach einem Konflikt lagen ungesicherte Eingaben nur in der Liste des
Controllers (Closures); der Seitenstand (`trip` bzw. der Hub-Stand `currentPreset`), aus dem
Reiter beim (Wieder-)Mount lesen, wusste davon nichts — ein neu gemounteter Reiter zeigte den
Altstand, die Liste hielt etwas anderes. Invariante:

- Jeder Listeneintrag traegt neben der Ausfuehrung die zuletzt GESENDETE Eigenfeld-Nutzlast als
  Daten (`merkeNutzlast`, beim Senden gesetzt — nie nachtraeglich neu berechnet).
- Bei `412` wird die Nutzlast ueber `registriereAbgelehnt` gemeldet; der Halter des Stands
  schreibt ihn lokal fort (`wendeNutzlastAn`: einstufiger Merge wie Go `mergeConfigMap`, Arrays
  und die zweite Ebene werden ersetzt, `undefined` wird uebersprungen). Kein Stempelwechsel.
  Trip: die Seite (`trip`). Compare: der Hub (`CompareTabs`) — und NUR dessen interner
  Hydrationsstand, nicht die Seiten-Prop `preset`, weil deren Wechsel die Hydrations-Flags
  zuruecksetzt und den offenen Reiter ueber seine Eingabe neu hydrieren wuerde. Verloren ging
  die Eingabe dort, wenn ein ERSTMALS geoeffneter Nachbar-Reiter (Versand teilt Abkuehlzeit/
  Ruhezeit mit Alarme) `wizardState` aus dem Altstand hydrierte.
- Bei `'geholt'` ist der Seitenstand GET-Stand ⊕ alle ausstehenden Nutzlasten (Reihenfolge der
  Liste), Stand und Stempel gemeinsam (AC-19). Ein Ersatz per Dedup-Schluessel enthaelt die
  fruehere Eingabe damit automatisch (der neue Reiter hat sie beim Mount gelesen).
  **Ausnahme Compare:** die Seite setzt `currentPreset` bei `'geholt'` NICHT (gemessen: ein
  Wechsel der Prop `preset` setzt via `CompareTabs.svelte:717` die Hydrations-Flags zurueck, der
  offene Reiter hydriert `wizardState` neu und ueberschreibt eine ungesicherte Eingabe 77 → 45).
  Der Hub-Stand bleibt dort bis zum `'wiederholt'`-Neuaufbau „alt ⊕ ausstehende Nutzlasten".
  Bekanntes Restrisiko: nach einem GESCHEITERTEN Compare-Retry hydriert ein erstmals geoeffneter
  Reiter Fremdfelder aus diesem alten Hub-Stand.
- Offene Reiter aendern sich dabei nicht (Trip: lesen nur beim Mount). Compare 'wiederholt'
  uebernimmt den frisch geholten Stand nur, wenn seit Beginn des GET nichts Neues ansteht und
  der Registry-Stempel noch passt (Muster Trip-Seite `inRegistry`).
