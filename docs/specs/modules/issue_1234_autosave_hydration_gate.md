---
entity_id: issue_1234_autosave_hydration_gate
type: bugfix
created: 2026-07-14
updated: 2026-07-14
status: draft
version: "1.1"
tags: [bug, dataloss, frontend, trip-editor, autosave, epic-1230]
workflow: fix-1234-mount-autosave-metrics
---

# Spec: #1234 — Auto-Save im Inhalt-Tab darf Metriken nicht stillschweigend leeren

## Approval

- [x] Approved — PO Henning, 2026-07-14 („Go" nach Vorlage der 6 ACs inkl. Known Limitations)

## Purpose

Ein Nutzer öffnet im Trip-Editor den Tab „Inhalt" und **fasst nichts an**. Kurz darauf sind seine ausgewählten Wetter-Metriken weg — ersetzt durch eine leere Liste. Zusätzlich sind **alle Alarm-Regeln des Trips gelöscht**, weil das Backend die Alarme gegen die (nun leere) Metrik-Liste synchronisiert. Ohne Warnung, ohne Weg zurück außer manueller Neukonfiguration.

Diese Spec beseitigt den stillen Datenverlust — **ohne** den legitimen Fall „Nutzer wählt bewusst alle Metriken ab" unmöglich zu machen.

Ursache ist ein Wettlauf: Eine Unterkomponente normalisiert die Report-Konfiguration beim Öffnen und schreibt sie zurück; für die Auto-Speicher-Logik ist das von einer Nutzeränderung nicht unterscheidbar. Der zu speichernde Inhalt wird dabei zu einem Zeitpunkt gebaut, an dem der Metrik-Katalog noch nicht geladen ist — heraus kommt „keine Metriken". Vollständige Kausalkette mit Belegzeilen: `docs/context/fix-1234-mount-autosave-metrics.md`.

## Source

**Zu ändern:**
- **File:** `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
  - **Identifier:** `scheduleAutoSave()` (Z. 447-457) — schedult ohne Bereitschaftsprüfung, baut den Payload sofort
  - **Identifier:** `buildWeatherPayload()` (Z. 400-417) — setzt den Key `metrics` bedingungslos
  - **Identifier:** `load()` (Z. 237-259) — `finally { loading = false }` auch im Fehlerfall
  - **Identifier:** `initFromTrip()` (Z. ~180-235) — baut `buckets` aus dem Katalog
  - **Identifier:** reportConfig-Watch-`$effect` (Z. 461-468) — Baseline aus Prop-Rohwert
  - **Identifier:** Loading-/Error-Guards im Markup (Z. 491, Z. 506)

**Neu:**
- **File:** `frontend/src/lib/components/trip-detail/weatherSaveGate.ts`
  - **Identifier:** `weatherSaveGate(input): 'save' | 'skip'` — reine Entscheidungsfunktion, unit-testbar ohne Mocks

**Referenz-Vorbild (unverändert):**
- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
  - **Identifier:** `saveGateDecision(rows): 'schedule' | 'dirty'` (Z. 517-519) — datenbasiertes Gate, das Muster dieser Lösung

> **PFLICHT — Schicht-Hinweis:** Affected Files MUSS die richtige Schicht treffen:
> - **Frontend / User-UI** → `frontend/src/...` (SvelteKit, produktive Oberfläche auf gregor20.henemm.com)
> - **Go-API** → `cmd/server/`, `internal/` (Production-API auf Port 8090)
> - **Python-Core / Domain-Backend** → `api/`, `src/services/`, `src/app/`, `src/providers/` (FastAPI Core über `api.main:app`)
>
> **Verortung dieser Spec: ausschließlich Frontend** (`frontend/src/lib/components/trip-detail/`). Der Bug entsteht im SvelteKit-Client (Auto-Save schickt einen Payload los, bevor der Metrik-Katalog geladen ist). Die Go-API (`internal/handler/weather_config.go`) und der Python-Core sind **geprüft und bewusst nicht betroffen** — eine serverseitige Ablehnung leerer Metrik-Listen würde AC-4 („bewusste Abwahl aller Metriken") unmöglich machen. Begründung siehe *Implementation Details*.

## Estimated Scope

- **LoC:** ~70–100 (inkl. Tests; LoC-Limit 250 — kein Override nötig)
- **Files:** 1 geändert (`WeatherMetricsTab.svelte`), 1 neue Quelldatei (`weatherSaveGate.ts`), 2 neue Testdateien
- **Effort:** medium

Backend (Go + Python): **keine Änderung**.

## Dependencies

| Komponente | Grund | Status |
|---|---|---|
| `trip-detail/WeatherMetricsTab.svelte` | Einziger Ort mit Auto-Save-Verdrahtung + Payload-Bau — hier greift der Fix | wird geändert |
| `trip-detail/weatherSaveGate.ts` | Reine Entscheidungsfunktion (Daten-/Absichts-Gate) | **neu** |
| `stores/saveStatusStore.svelte.ts` | Debounce-Mechanik (`schedule`/`flush`) | benutzt, **unverändert** |
| `edit/EditReportConfigSection.svelte` | Verursacht den auslösenden Rückschreib-Vorgang, hat aber 4 Aufrufer inkl. Anlege-Flow | **bewusst unverändert** |
| `internal/handler/weather_config.go` | Nimmt leere Metrik-Liste an, löscht daraufhin Alarm-Regeln — muss so bleiben (AC-4 / #1191) | **bewusst unverändert** |
| `shared/corridor-editor/corridorEditorState.ts:517` | Vorbild-Muster für das Daten-Gate | unverändert |

## Implementation Details

**Verworfener Ansatz A (Adversary-Challenge, dokumentiert damit er nicht wiederkehrt):** Timing-Guards stapeln (`loading`-Fix + `hydrated`-Flag + Baseline-Reset). Zwei belegte Löcher:
1. Der `hydrated`-Merker wäre **bereits gesetzt**, wenn `EditReportConfigSection` mountet (`load()` ruft `initFromTrip()` **vor** `loading = false`, die Kindkomponente mountet **nach** `loading = false`). Das Gate hätte im Normalfall nichts geschützt — die gesamte Schutzwirkung hinge an einer einzigen, unscheinbaren Zeile.
2. Der `loading`-Guard hängt an einer Variable, die im `finally` **auch bei Ladefehler** auf „fertig" springt. Bei fehlgeschlagenem Katalog-Fetch rendert der Editor leer weiter, Fehlermeldung ist bei gesetztem `saveController` ausgeblendet (Z. 506) → stiller **Arbeits**verlust im Browser statt stillem **Daten**verlust am Server. Kein Fortschritt.

**Gewählter Ansatz B — Daten und Absicht prüfen, nicht Zeitpunkte.** Drei Änderungen mit je eigener, nicht redundanter Aufgabe:

1. **Echter Ladezustand.** Ein `catalogLoaded`, das **nur bei Erfolg** wahr wird (nicht im `finally`). Der Render-Guard hängt daran statt an `loading`.
2. **Sichtbarer Fehlerpfad.** Schlägt das Laden fehl, zeigt der Tab Fehler + Wiederholen statt eines leeren Editors. Die Fehleranzeige darf nicht länger von `!saveController` abhängen.
3. **Absichts-Gate: ohne Nutzergeste kein Schreibzugriff.** `weatherSaveGate()` entscheidet:

   | Katalog geladen | Nutzer hat im Tab etwas getan | Entscheidung |
   |---|---|---|
   | nein | — | `skip` |
   | ja | **nein** | `skip` ← **der Bug (AC-1/AC-2) UND AC-6** |
   | ja | **ja** | `save` ← **AC-4 und AC-5 bleiben möglich** |

   **„Nutzergeste"** = eine echte Interaktion des Nutzers **innerhalb** des Tabs „Inhalt": Metrik umschalten/entfernen/umsortieren, Darstellungsmodus wechseln, Schwellwert ändern, Preset anwenden — **oder** eine Änderung an den E-Mail-Inhalt-Optionen (Checkboxen der Report-Konfiguration). Der Merker wird **ausschließlich** aus echten DOM-Ereignissen gesetzt — **nie** in einem `$effect`, nie durch eine Normalisierung, nie durch das Laden.

   **Warum keine Sonderfälle nach Datenlage:** Jeder *legitime* Speichervorgang folgt einer Nutzeraktion. Es gibt keinen Fall, in dem ohne Zutun des Nutzers geschrieben werden müsste. Damit ist „ohne Geste nichts schreiben" nicht nur die einfachste, sondern die **einzig vollständige** Regel: Sie deckt den Wettlauf, den Ladefehler, den leeren Katalog und jeden heute unbekannten Weg gleichermaßen ab — ohne dass man jeden dieser Wege einzeln kennen muss. Insbesondere bleibt AC-4 („bewusst alles abwählen") möglich, weil das Abwählen selbst die Geste **ist**.

Punkt 3 ist die tragende Schicht. Punkte 1 und 2 beseitigen die Bedingung, die den Wettlauf ermöglicht, und den Folgefehler im Fehlerfall.

**Warum nicht im Backend:** Ein Guard „leere Metrik-Liste ablehnen" würde den Bug stoppen und gleichzeitig AC-4 unmöglich machen. Die Unterscheidung „leer ≠ nie konfiguriert" hat das Projekt im Orts-Vergleich bei **#1191** bewusst hergestellt. Wir würden einen Datenverlust gegen einen Semantik-Rückschritt tauschen. Der Client muss aufhören, Unsinn zu senden; das Backend darf ihm weiter glauben.

## Expected Behavior

| Situation | Heute (Bug) | Nach dem Fix |
|---|---|---|
| Tab „Inhalt" öffnen, nichts anklicken | Metriken werden auf `[]` gesetzt, **Alarm-Regeln gelöscht** | Nichts wird geschrieben |
| Metrik-Katalog nicht ladbar | Leerer Editor ohne Fehlermeldung; jede Aktion verpufft still | Fehlermeldung + Wiederholen, kein Editor, kein Schreibzugriff |
| Metrik umschalten / umsortieren / Schwellwert ändern | Auto-Speichern | Auto-Speichern (unverändert) |
| Bewusst **alle** Metriken abwählen | Wird gespeichert | Wird gespeichert (unverändert) |

## Test Plan

| Test | Schicht | Prüft |
|---|---|---|
| `weatherSaveGate.test.ts` | Kern (Vitest, reine Funktion, keine Mocks) | Entscheidungstabelle oben, Zeile für Zeile: nicht geladen → `skip` · Leerung ohne Absicht → `skip` · Leerung **mit** Absicht → `save` (AC-4) · normale Änderung → `save` (AC-5) |
| `weather-metrics-tab-autosave.spec.ts` | Playwright (echter Browser, echte Komponente) | **Repro AC-1/AC-2:** Katalog-Antwort verzögern → Tab öffnen → nichts klicken → über die Debounce-Zeit hinaus warten → Tab wechseln. Über abgefangene Netzwerk-Requests: **kein** PUT mit `metrics: []`. Danach Trip neu laden: Metriken **und** Alarm-Regeln unverändert. |
| dito | Playwright | **AC-3:** Katalog-Endpoint antwortet mit Fehler → Fehlermeldung sichtbar, kein Editor, kein PUT. |
| dito | Playwright | **AC-4:** Alle Metriken bewusst abwählen → PUT mit leerer Liste geht raus → nach Reload leer. |
| dito | Playwright | **AC-6:** Tab öffnen ohne Klick → **kein** PUT überhaupt. |

**Der RED-Nachweis ist AC-1:** Der Test muss den Wettlauf deterministisch treffen (Verzögerung der Katalog-Antwort), vor dem Fix rot sein und nach dem Fix grün. Ein Test, der den Wettlauf nur zufällig trifft, ist kein Beweis.

## Acceptance Criteria

- **AC-1:** Given ein Trip hat mehrere Wetter-Metriken konfiguriert / When der Nutzer den Tab „Inhalt" öffnet, dort **nichts** anklickt und danach den Tab wechselt / Then bleiben die gespeicherten Metriken des Trips unverändert — es wird kein Speichervorgang mit leerer Metrik-Liste abgeschickt, weder nach Ablauf der Auto-Speicher-Verzögerung noch durch das Abschließen offener Speichervorgänge beim Tab-Wechsel.
  - Test: Playwright gegen Staging, Katalog-Antwort künstlich verzögert (trifft den Wettlauf deterministisch): Trip mit 5 Metriken öffnen → Tab „Inhalt" anklicken → 3 s warten (> Debounce) → auf Tab „Etappen" klicken. Über abgefangene Netzwerk-Requests prüfen: kein `PUT /api/trips/{id}/weather-config` mit `metrics: []`. Danach Seite neu laden: die 5 Metriken sind noch da.

- **AC-2:** Given ein Trip hat Wetter-Metriken **und** Alarm-Regeln konfiguriert / When der Nutzer den Tab „Inhalt" öffnet, ohne etwas zu ändern / Then bleiben auch die Alarm-Regeln des Trips vollständig erhalten (sie werden heute als Folgeschaden der geleerten Metrik-Liste mitgelöscht).
  - Test: Wie AC-1, zusätzlich vorher Alarm-Regeln setzen. Nach dem Tab-Wechsel den Trip über die API neu laden und prüfen: `alert_rules` unverändert (Anzahl und Inhalt), nicht leer.

- **AC-3:** Given der Metrik-Katalog kann nicht geladen werden (Server antwortet mit Fehler) / When der Nutzer den Tab „Inhalt" öffnet / Then sieht er eine verständliche Fehlermeldung mit einer Möglichkeit, den Ladevorgang zu wiederholen, und **keinen** leeren Editor; es wird in diesem Zustand nichts gespeichert und keine Nutzeraktion still verworfen.
  - Test: Playwright, `/api/metrics` antwortet mit 500 → Tab „Inhalt" öffnen. Sichtbar: Fehlertext + Wiederholen-Schaltfläche. Nicht sichtbar: Metrik-Editor. Kein PUT im Netzwerk-Mitschnitt.

- **AC-4:** Given ein Trip hat Wetter-Metriken konfiguriert / When der Nutzer bewusst **alle** Metriken abwählt / Then wird diese leere Auswahl gespeichert und bleibt nach dem Neuladen der Seite erhalten — „bewusst leer" bleibt von „nie konfiguriert" unterscheidbar und möglich.
  - Test: Playwright, Tab „Inhalt" vollständig laden → jede Metrik einzeln abwählen → Debounce abwarten. Netzwerk: `PUT .../weather-config` mit `metrics: []` geht raus. Nach Seiten-Neuladen: keine Metrik aktiv (nicht etwa die Standard-Auswahl wieder da).

- **AC-5:** Given der Tab „Inhalt" ist vollständig geladen / When der Nutzer eine Metrik umschaltet, umsortiert, entfernt oder einen Schwellwert ändert / Then wird die Änderung wie bisher automatisch gespeichert — die bestehende Auto-Speicher-Funktion bleibt in vollem Umfang erhalten.
  - Test: Playwright, Tab laden → eine Metrik zuschalten → Debounce abwarten → Seite neu laden: die Metrik ist aktiv. Zusätzlich: Schwellwert ändern → nach Reload erhalten.

- **AC-6:** Given ein bestehender Trip / When der Nutzer den Tab „Inhalt" öffnet, dort nichts anklickt, die Auto-Speicher-Verzögerung abwartet und anschließend den Tab wechselt / Then wird **überhaupt kein** Speichervorgang auf den Trip ausgelöst — nicht nur keiner mit leerer Metrik-Liste, sondern gar keiner. (Strengere Fassung von AC-1: Das bloße Ansehen eines Tabs darf keine Schreibzugriffe erzeugen.)
  - Test: Playwright, Netzwerk-Mitschnitt über den gesamten Ablauf: **null** PUT-Requests auf `/api/trips/{id}` und `/api/trips/{id}/weather-config`.

## Known Limitations (Teil der Freigabe)

- **Das Backend akzeptiert weiterhin eine leere Metrik-Liste.** Bewusste Entscheidung (AC-4 / #1191), keine Lücke. Ein Client mit einem anderen Bug könnte denselben Schaden erneut anrichten. Eine serverseitige Absicherung wäre nur mit einer expliziten Absichts-Kennzeichnung im Datenformat möglich — Datenmodell-Eingriff, gehört in Epic #1230, nicht in diesen Bugfix.
- **Die Alarm-Regel-Kaskade bleibt bestehen:** Werden die Metriken (berechtigt) geleert, löscht das Backend weiterhin die zugehörigen Alarm-Regeln. Bei *gewollter* Abwahl vermutlich richtiges Verhalten — explizit entschieden wurde es nie.
- **Zwei latente Zwillinge bleiben unangetastet:** `BriefingScheduleTab.svelte:68-79` und `shared/VersandTab.svelte:239-259` benutzen dasselbe fehleranfällige Muster (Vergleichs-Baseline aus dem Prop-Rohwert). Kein Datenverlust, weil sie keine Metriken schreiben — höchstens ein überflüssiger Speichervorgang. `VersandTab` ist **geteilter Code**; sobald dort das automatische Speichern für den Orts-Vergleich angeschaltet wird, kommt die Fehlerklasse mit. Vorgewarnt in #1256 (Kommentar 2026-07-14). Nebenbefund → #1199, nicht Teil dieses Fixes.
- **AC-2 ist auf Staging heute nur in der Unveränderheits-Fassung nachweisbar, nicht in der starken Fassung „Trip hat Alarm-Regeln, sie überleben".** Grund: **#1257** (vorbestehend, seit #809/#817) — Metrik-Katalog und Alarm-Regel-Enum führen getrennte Namenslisten für dieselben Wettergrößen (`gust` vs. `wind_gust`, `precipitation` vs. `precipitation_sum`, `thunder` vs. `thunder_level`) mit leerer Schnittmenge. `ActiveAlertableMetricIDs()` (`internal/model/trip.go:180-216`) findet dadurch nie einen Treffer, `SyncAlertRules()` liefert bei jedem Speichern und Laden (`internal/store/trip.go:115,141`) `[]` — ein frisch angelegter Trip mit Alarm-Regel kommt bereits in der POST-Antwort mit `alert_rules: []` zurück (empirisch auf Staging geprüft; 0 von 15 Produktions-Trips haben Alarm-Regeln). Der Test liest deshalb den Ist-Zustand nach dem Anlegen und prüft danach auf Gleichheit (`toEqual(before.alert_rules)`) statt auf eine bestimmte Anzahl. Sobald #1257 gefixt ist, wird der Test ohne Änderung zur starken Fassung, weil `before.alert_rules` dann die gesetzte Regel enthält.

## Architektur-Entscheidung (ADR)

**Keine neue ADR erforderlich.** Diese Spec trifft keine neue Architektur-Entscheidung, sondern **bestätigt und verteidigt eine bestehende**: „Leere Auswahl ≠ nie konfiguriert" — festgelegt in #1191 für den Orts-Vergleich (`compareEditorSave.ts:94-100`). Genau deshalb wird der Fix client- und nicht serverseitig gebaut. Die Entscheidung, ob das Datenmodell künftig eine explizite Absichts-Kennzeichnung bekommt (und damit eine serverseitige Absicherung erlaubt), gehört in Epic #1230 und wird hier ausdrücklich **nicht** vorweggenommen.

## Changelog

| Datum | Version | Änderung |
|---|---|---|
| 2026-07-14 | 1.0 | Erstfassung. Ansatz A (gestapelte Timing-Guards) im Adversary-Challenge verworfen: Das „ist geladen"-Gate wäre wirkungslos gewesen (Merker bereits gesetzt, wenn die Unterkomponente mountet), und der Katalog-Ladefehler hätte einen stillen *Arbeits*verlust im Browser erzeugt. Ersetzt durch Ansatz B (Daten- + Absichts-Gate, echter Ladezustand, sichtbarer Fehlerpfad). AC-6 nach Validator-Befund von der Mechanismus-Formulierung („Normalisierung") auf reine Nutzersicht umgestellt und dabei verschärft. |
| 2026-07-14 | 1.1 | Auf die Template-Gliederung gezogen (Source, Estimated Scope, Implementation Details, Expected Behavior, ADR ergänzt) — die Erstfassung folgte einer selbstgebauten Struktur. Inhaltlich unverändert, ACs unberührt. |
| 2026-07-14 | 1.2 | **Korrektur eines Fehlers in dieser Spec, gefunden vom Adversary (Verdict BROKEN, Finding F001).** Die Entscheidungstabelle in *Implementation Details* v1.0/v1.1 enthielt die Zeile „Katalog geladen · Payload würde **nicht** leeren · Nutzergeste **egal** → `save`". Dieses „egal" widerspricht AC-6 direkt: Beim bloßen Öffnen des Tabs wird die Report-Konfiguration von einer Unterkomponente normalisiert, der Payload ist dann **nicht** leer — die Tabelle erlaubte also einen echten Schreibzugriff ohne jede Nutzeraktion. Genau das trat ein (kein Datenverlust, aber ein stiller PUT). Die Implementierung hatte die Tabelle **korrekt** umgesetzt; die Tabelle war falsch. Ersetzt durch das einfachere und vollständige Absichts-Gate „ohne Nutzergeste kein Schreibzugriff". **Die sechs Acceptance Criteria sind unverändert** — die Korrektur bringt die Umsetzungsbeschreibung mit ihnen in Einklang, nicht umgekehrt. |
| 2026-07-14 | 1.3 | **Known Limitations um vorbestehenden Fremd-Bug #1257 ergänzt** (gefunden im Staging-Lauf gegen `99e98fca`, Fix-Loop 4). Der AC-2-Test lässt sich in seiner starken Fassung heute nicht herstellen, weil das Backend `alert_rules` bei jedem Speichern/Laden gegen ein anderes Namens-Vokabular als den Metrik-Katalog synchronisiert (Schnittmenge leer) und dabei stets leert — unabhängig von diesem Fix. Der Test prüft daher auf Unveränderheit gegenüber dem tatsächlich gespeicherten Ist-Zustand statt auf eine feste Anzahl. **AC-2 selbst ist unverändert** — nur die Nachweisbarkeit auf dem heutigen Backend ist eingeschränkt, dokumentiert und mit #1257 verknüpft. |
