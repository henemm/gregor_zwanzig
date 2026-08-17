---
entity_id: fix_1699_anker_ohne_briefing
type: bugfix
created: 2026-08-17
updated: 2026-08-17
status: draft
workflow: fix-1699-heute-abfrage-anker
version: "1.1"
tags: [alerts, trip, anchor, on-demand, issue-1699, observability]
---

# Abfrage-Anker ohne Briefing besteht die #1661-Datumsprüfung anstandslos (Issue #1699)

## Approval

- [x] Approved — PO, 2026-08-17. Einschliesslich der Altbestand-Auslegung aus AC-5
  („fehlendes Feld = briefing-gestuetzt"), die damit von einer Empfehlung zur Entscheidung wird.
- [x] AC-10 (Naht zu #1916) — Inhalt wörtlich vom PO vorgegeben, 2026-08-17 (nachgezogen nach
  Merge von #1916, Merge-Commit `4aa227f2`). AC-1 bis AC-9 inhaltlich unverändert.

## Purpose

Reine Abfrage-Kommandos (`glance`, `heute_gewitter`, `timeline_heute` u. a.) schreiben,
wenn kein undatierter Snapshot existiert, einen frischen Wetter-Snapshot direkt über
`WeatherSnapshotService.save()` — vorbei am geteilten Baustein
`write_anchor_and_reset_memory()`, der bei On-Demand-Zugriffen bewusst aussteigt
(#1007-Invariante). Seit #1661 prüft der Abweichungs-Alarm den undatierten Rückfall nur
noch auf das richtige **Datum** (`target_date == heute`) — und ein durch eine Abfrage
frisch geschriebener Snapshot besteht diese Prüfung anstandslos, obwohl ihm nie ein
Briefing zugrunde lag. Der Alarm-Vergleichspunkt wird dadurch nicht verschoben, sondern
**erfunden**: der Wetterzustand zum Abfragezeitpunkt gilt ab dann als Referenz, ohne dass
je ein Briefing verschickt wurde (ADR-0009 verlangt aber genau das). Diese Spec ergänzt
den Snapshot um ein additives Herkunftsmerkmal und lehnt einen nicht briefing-gestützten
Anker im Abweichungs-Alarm-Pfad ab — unter strikter Beibehaltung des amtlichen
Warnungs-Pfads, der denselben Snapshot nur als Geometrie liest.

Vollständige Herleitung, Code-Belege und PO-Entscheidungen:
`docs/context/fix-1699-heute-abfrage-anker.md`. Diese Spec wiederholt nichts davon,
sondern zieht Scope und Acceptance Criteria daraus.

> **Nachzug 2026-08-17 (nach Merge #1916):** `docs/context/fix-1699-heute-abfrage-anker.md`
> beschreibt den Stand VOR #1916 (Merge-Commit `4aa227f2`, `origin/main`) und nennt daher
> veraltete Zeilennummern in `trip_alert.py` — dieser Kontext-Beleg wird bewusst nicht
> nachträglich verändert (Analyse-Artefakt eines abgeschlossenen Analyse-Schritts). Diese
> Spec-Datei selbst wurde auf den aktuellen Working-Tree-Stand nachgezogen: `_get_cached_weather`
> hat seit #1916 (ADR-0056) eine DREISTUFIGE Prioritätskette (1. datierter Briefing-Anker,
> 2. rollierender Alarm-Anker aus #1916, 3. undatierter Rückfall) statt der vormals
> zweistufigen. Der #1699-Eingriff gehört unverändert in Stufe 3 — Details s. „Source" und
> „Implementation Details" unten.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._get_cached_weather` (Zeile 586-727, aktueller Stand
  nach #1916). Die neue Herkunftsprüfung sitzt in **Stufe 3** (undatierter Rückfall) —
  zwischen dem dortigen amtlichen-Warnungs-Ausstieg (Zeile 693-695) und der bestehenden
  #1661-Datumsprüfung (ab Zeile 696).
- **Zwei amtliche Ausstiege, nicht einer (seit #1916):** `_get_cached_weather` bedient
  amtliche Warnungen (`tagesgleicher_anker_noetig=False`) jetzt an **zwei** Stellen der
  Kette — Stufe 2 (Zeile 668-669, `if not tagesgleicher_anker_noetig: return rolling`,
  rollierender Anker) und Stufe 3 (Zeile 693-695, `if not tagesgleicher_anker_noetig:
  return undated`, undatierter Rückfall). Beide liefern für amtliche Warnungen bewusst nur
  Geometrie ohne Tagesprüfung — die neue #1699-Herkunftsprüfung darf **keinen** der beiden
  amtlichen Ausstiege berühren, sondern ausschließlich den Abweichungs-Alarm-Zweig in Stufe
  3 (nach Zeile 695).
- Nebendateien: `src/services/weather_snapshot.py` (neuer Parameter + neue Lesemethode),
  `src/services/trip_command_processor.py` (einziger Aufrufer mit `briefing_backed=False`),
  `src/services/alert_briefing_anchor.py` (Docstring, vierter Ablehnungsgrund — im
  aktuellen Working Tree bereits bei Zeile 64-69 vorhanden, unverifizierter Zwischenstand
  aus vorheriger Arbeit; Zeilenangabe hier nur nachgezogen, kein Auftrag an diese Spec-Revision,
  daran etwas zu ändern).

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/services/`). Kein Go-, kein
> Frontend-Code — die Diagnose-Datei nutzt das bestehende JSONL-Format aus #1661, dessen
> Go-seitige Auswertung (`analyzeAlertAnchorRejections`) bereits jeden `reason`-String
> gleich behandelt und deshalb unverändert bleibt.

## Estimated Scope

- **LoC:** ~35-40 Produktivcode, ~120-160 Tests (Schätzung aus der Analyse-Phase; Vorbehalt
  dort: der Nachweis für die Pfadtrennung amtlich/Abweichung kann das knapp machen). AC-10
  fügt keinen neuen Produktivcode-Pfad hinzu (reine Ordnungs-/Regressionsabsicherung
  zwischen #1699 und #1916, siehe unten) — nur zusätzliche Test-LoC.
- **Files:** 4 Produktivdateien, 2 bestehende Testdateien (additive Erweiterung).
- **Effort:** medium — kleiner Eingriff, aber im Alarm-Pfad; Fehlerrichtung „zu streng"
  würde amtliche Warnungen unterdrücken (siehe zentrale Zusicherung unten).

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/services/weather_snapshot.py` | MODIFY | `save()` (Zeile 61-86) bekommt additiven Schlüsselwort-Parameter `briefing_backed: bool = True`, schreibt das Feld ins JSON. Neue schlanke Lesemethode analog `load_target_date()` (jetzt Zeile 243-269, verschoben durch die #1916-Ergänzungen `save_alarm_anchor`/`load_alarm_anchor`/`alarm_anchor_target_date`), platziert direkt danach vor `load()` (Zeile 271); fehlt das Feld (Altbestand), liefert sie `True`. |
| `src/services/trip_command_processor.py` | MODIFY | `_fetch_and_save_snapshot` (Zeile 278), `save()`-Aufruf in Zeile 308: einziger Aufrufer, der `briefing_backed=False` übergibt. |
| `src/services/trip_alert.py` | MODIFY | Neue Prüfung in `_get_cached_weather`, in Stufe 3 (undatierter Rückfall), **nach** Zeile 695, **vor** der bestehenden Datumsprüfung ab Zeile 696. Neuer Ablehnungsgrund `not_briefing_backed`, protokolliert über `record_alert_anchor_rejected(...)`. Berührt Stufe 1 (Briefing-Anker) und Stufe 2 (rollierender #1916-Anker) NICHT. |
| `src/services/alert_briefing_anchor.py` | MODIFY (Doku) | Vierter Ablehnungsgrund im Docstring von `record_alert_anchor_rejected` — im aktuellen Working Tree bereits bei Zeile 64-69 vorhanden. Die Diagnose-Funktion selbst nimmt jeden String entgegen, kein Code-Eingriff nötig. |
| `tests/tdd/test_alert_anchor_day_guard.py` | MODIFY | Additive Testfälle im bestehenden Wächter (AC-1 bis AC-3, AC-6, AC-9, AC-10). |
| `tests/integration/test_weather_snapshot.py` | MODIFY | Roundtrip-Test für `briefing_backed` und Altbestand-Default (AC-8). |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `WeatherSnapshotService.save`/`load` | function | unverändert in Signatur-Grundform weiterverwendet — `briefing_backed` ist ein additiver Default-Parameter, kein Ersatz |
| `WeatherSnapshotService.load_target_date` (#1661) | function | direktes Vorbild für die neue schlanke Lesemethode — gleiches fail-soft-Muster, gleiche Ein-Feld-Lesestrategie |
| `TripAlertService._get_cached_weather` (#1661, dreistufig seit #1916) | function | Wirtsstelle der neuen Prüfung; die **zwei** amtlichen Ausstiege (`tagesgleicher_anker_noetig`, Stufe 2 Zeile 668-669 und Stufe 3 Zeile 693-695) bestimmen, wo die Prüfung sitzen darf — ausschließlich in Stufe 3, nach Zeile 695 |
| `WeatherSnapshotService.load_alarm_anchor`/`save_alarm_anchor`/`alarm_anchor_target_date` (#1916) | function | rollierender Alarm-Anker, Stufe 2 der Kette; von der #1699-Herkunftsprüfung NICHT direkt geprüft (kein `briefing_backed`-Feld dort) — die Naht zu diesem Baustein ist Gegenstand von AC-10 |
| `alert_briefing_anchor.record_alert_anchor_rejected` (#1661) | function | unverändert wiederverwendet für den vierten Grund `not_briefing_backed` |
| `write_anchor_and_reset_memory` / `on_demand`-Ausstieg (#1007) | function | die Invariante, die dieser Fix wiederherstellt — On-Demand-Abrufe bleiben read-only gegenüber Alarm-Zustand |
| `docs/specs/modules/fix_1661_anker_vom_falschen_tag.md` | doc | direkte Vorgänger-Scheibe; führte `target_date`-Prüfung und die Pfadtrennung amtlich/Abweichung ein — diese Spec erweitert dieselbe Methode um ein zweites, unabhängiges Kriterium |
| `docs/adr/0009-alerts-als-abweichungs-waechter.md` | doc | „Alerts melden Abweichung vom zuletzt versendeten Briefing" — Grundlage der fachlichen Zusicherung, dass ein Anker ohne Briefing ungültig ist |
| `docs/adr/0056-...` (#1916, rollierender Alarm-Anker) | doc | führte Stufe 2 der Prioritätskette ein; AC-10 dieser Spec sichert die Verträglichkeit beider Scheiben ab, ohne #1916 inhaltlich zu ändern |

## Nicht in dieser Scheibe

- **`_fetch_and_save_snapshot` legt Etappen von heute UND morgen unter `target_date =
  today` ab** (`trip_command_processor.py:301-303`). Eigenständiges Korrektheitsproblem,
  für diesen Fix ohnehin folgenlos (der Anker wird bereits wegen `briefing_backed=False`
  verworfen, bevor sein `target_date` überhaupt geprüft wird) — eigenes Issue.
- **Rückwirkende Bereinigung bereits geschriebener Pseudo-Anker.** Ein vor dem Deploy durch
  eine Abfrage entstandener Snapshot trägt kein `briefing_backed`-Feld und gilt nach der
  gewählten Auslegung (s. u.) als briefing-gestützt, bis das nächste reguläre Briefing ihn
  überschreibt. Kein Neuschreiben aus dem Alarm-Pfad heraus (widerspräche derselben
  #1584c-AC-7-Lehre wie in #1661: aus zeitweiliger Unterdrückung würde sonst Dauerstille).
- **Inhaltliche Änderungen an #1916 selbst.** Diese Spec ändert weder die Priorisierung der
  drei Stufen noch den rollierenden Anker-Mechanismus (Trigger (a)/(b), Alterungs-Ceiling).
  AC-10 fügt ausschließlich eine Test-Absicherung der ORDNUNG zwischen beiden Scheiben
  hinzu, keinen neuen Produktivcode-Pfad.

## Bekannte Grenze der gewählten Auslegung

Ein durch den Bug bereits entstandener Anker trägt kein `briefing_backed`-Feld und gilt
deshalb — wie jeder Altbestand — als briefing-gestützt (`True`), bis das nächste reguläre
Briefing ihn überschreibt. Bei laufenden Touren geschieht das binnen Stunden, bei noch
nicht gestarteten Touren ggf. erst zum Tourstart.

> **🔴 Diese Auslegung ist der freigabepflichtige Punkt dieser Spec.** Sie ist eine
> Empfehlung aus der Analyse-Phase, noch keine PO-Entscheidung — mit der Freigabe der Spec
> wird sie eine.

Begründung der Empfehlung: die strenge Gegenauslegung (fehlendes Feld = „unbekannt,
verwerfen") würde beim ersten Alarmlauf nach dem Deploy **jeden** vor dem Deploy legitim
geschriebenen Anker verwerfen und dadurch flächendeckend Alarme unterdrücken, bis das
nächste Briefing läuft — ein schwererer Schaden als der behobene.

**Zusatz nach #1916-Merge (Übergangsfenster des rollierenden Alarm-Ankers, verifiziert am
Code 2026-08-17):** Ein VOR dem Deploy dieser Scheibe bereits bestehender rollierender
Alarm-Anker (`{trip_id}_alarm_anchor.json`, Issue #1916) bleibt gültig, solange Stufe 2 der
Prioritätskette ihn an seinem eigenen Tagesbezug wiedererkennt
(`alarm_anchor_target_date(trip_id) == today`) — längstens bis zur nächsten Tagesgrenze,
weil eine Fortschreibung (Trigger (a)/(b) aus #1916) einen bereits gültigen `cached`-Wert
voraussetzt, den nur ein noch tagesaktueller Anker liefert. Fällt die Kette am Folgetag auf
Stufe 3 zurück, entscheidet der zugrunde liegende undatierte Snapshot über den weiteren
Verlauf — und hier ist die Formulierung „Stufe 3 lehnt den Pseudo-Anker ab, weil er nicht
briefing-gestützt ist" nur für EINEN der beiden möglichen Fälle richtig:

- Trägt der undatierte Snapshot explizit `briefing_backed=False` (jede nach dem Deploy
  dieser Scheibe geschriebene Abfrage), lehnt die NEUE Herkunftsprüfung dieser Scheibe ihn
  sofort ab (AC-1, AC-10) — die Quelle versiegt hier tatsächlich wegen `not_briefing_backed`.
- Trägt er dagegen KEIN Feld (Altbestand von vor dem Deploy dieser Scheibe), greift die neue
  Prüfung NICHT (Altbestand-Auslegung oben), sondern unverändert die bereits bestehende
  #1661-Datumsprüfung: sein `target_date` ist auf den Tag seiner Entstehung fixiert und
  stimmt am Folgetag nicht mehr mit „heute" überein — er wird mit `reason=wrong_day`
  verworfen, nicht mit `reason=not_briefing_backed`.

In beiden Fällen schließt sich das Übergangsfenster praktisch binnen rund eines Tages —
die zeitliche Aussage aus der ursprünglichen PO-Vorgabe trifft also zu, nur der genannte
Mechanismus („Stufe 3 lehnt wegen `not_briefing_backed` ab") gilt nicht für JEDEN
Pseudo-Anker: für Altbestand ohne Feld schließt stattdessen die ältere #1661-Datumsprüfung
das Fenster. Beleg: `trip_alert.py::_get_cached_weather`, Stufe 2 (Zeile 666-675) und Stufe
3 (Zeile 677-727).

## Implementation Details

### Datenseite — additives Herkunftsmerkmal

`WeatherSnapshotService.save()` (`weather_snapshot.py:61-86`) bekommt den
Schlüsselwort-Parameter `briefing_backed: bool = True` und schreibt ihn zusätzlich ins
JSON-Dict. Der einzige Aufrufer, der `False` übergibt, ist `_fetch_and_save_snapshot`
(`trip_command_processor.py:308`) — alle übrigen Aufrufer (regulärer Briefing-Lauf,
Compare-Presets) bleiben unverändert bei `True`, ohne den Parameter explizit setzen zu
müssen.

Eine neue, schlanke Lesemethode — Bauart wie `load_target_date()`
(jetzt `weather_snapshot.py:243-269`) — liest ausschließlich dieses eine Feld aus der
undatierten Datei. Jeder Fehler (Datei fehlt, JSON korrupt, Feld fehlt) wird abgefangen
und ergibt `True` — nicht `None` oder `False`: fehlendes Feld heißt hier laut Auslegung
oben „briefing-gestützt", nicht „unbekannt". Das ist der zentrale Unterschied zu
`load_target_date()`, wo ein fehlendes Feld `None` ergibt.

### Alarm-Seite — Prüfort = Wirkort, in Stufe 3 der Prioritätskette

`trip_alert.py:586-727` (`_get_cached_weather`) durchläuft seit #1916 DREI Stufen, bevor
sie verwirft:

1. **Stufe 1 — datierter Briefing-Anker** (`svc.load_dated(trip.id, today)`, Zeile 654-656):
   existiert er, wird er sofort zurückgegeben — unberührt von dieser Scheibe.
2. **Stufe 2 — rollierender Alarm-Anker** (#1916, Zeile 658-675): amtlicher Ausstieg bei
   Zeile 668-669 (`if not tagesgleicher_anker_noetig: return rolling`); bei
   `tagesgleicher_anker_noetig=True` nur gültig, wenn `alarm_anchor_target_date == today`
   (Zeile 670-671) — sonst Fallthrough auf Stufe 3. Diese Scheibe fügt hier NICHTS hinzu
   (kein `briefing_backed`-Feld auf rollierenden Ankern, s. AC-10).
3. **Stufe 3 — undatierter Rückfall** (Zeile 677 ff.): amtlicher Ausstieg bei Zeile 693-695
   (`if not tagesgleicher_anker_noetig: return undated`). **Hier, direkt danach und vor der
   bestehenden #1661-Datumsprüfung (ab Zeile 696), sitzt die neue Herkunftsprüfung dieser
   Scheibe:**

```
if not tagesgleicher_anker_noetig:
    return undated              # Zeile 693-695 — amtliche Warnungen: nur Geometrie
# NEU: Herkunftsprüfung genau hier einfügen
if not svc.load_briefing_backed(trip.id):
    reason = "not_briefing_backed"
    # gleiche Eskalations-/Diagnose-Behandlung wie wrong_day/too_old (#1661 Teil C)
    return None
# bestehende Datumsprüfung ab Zeile 696 unverändert
if anchor_date == today:
    return undated
```

Die neue Prüfung sitzt **zwischen** Zeile 695 und der bestehenden Datumsprüfung — niemals
davor und niemals in Stufe 1 oder 2. Begründung, wörtlich aus der Analyse übernommen:

**🔴 Der Fix muss zwischen zwei Alarm-Pfaden unterscheiden.** `_get_cached_weather`
bedient zwei Aufrufer über den Schalter `tagesgleicher_anker_noetig`, mit je einem
amtlichen Ausstieg in Stufe 2 (Zeile 668-669) und Stufe 3 (Zeile 693-695): amtliche
**Warnungen** — der Snapshot liefert dort nur die **Geometrie** (wo ist die Tour), die
Datumsprüfung aus #1661 wird hier bewusst übersprungen. Ab Zeile 696 läuft der
**Abweichungs-Alarm** — der Snapshot ist dort die **Vergleichsbasis** (ADR-0009). Daraus
folgt zwingend: Die neue Herkunftsprüfung darf **ausschließlich** in den Abweichungs-Zweig
der Stufe 3, also **nach** Zeile 695. Ein nicht briefing-gestützter Snapshot hat dieselbe
Geometrie wie ein echter — für amtliche Warnungen ist er einwandfrei. Läge die Prüfung vor
einem der beiden amtlichen Ausstiege, würde der Fix **amtliche Warnungen unterdrücken** und
damit in genau die Gegenrichtung kippen, die dieses Ticket verhindern soll (#1701: Alarme
müssen alle Kanäle erreichen).

Der neue Ablehnungsgrund `not_briefing_backed` wird — wie `wrong_day`/`too_old` aus #1661
— unbedingt eskaliert: `logger.warning(...)` mit Trip-Kennung und Grund, UND
`record_alert_anchor_rejected(user_id=..., entity_id=trip.id,
reason="not_briefing_backed")`. Existiert überhaupt ein Anker, war er im Bewusstsein des
Nutzers eine gültige Antwort — die Eskalation macht sichtbar, dass der Alarm sie NICHT als
Vergleichsbasis akzeptiert.

Verwerfen heißt wie in #1661 genau: `None` zurückgeben. Kein Anfassen von `alert_state`
oder Cooldown, kein Neuschreiben des Ankers.

**Naht zu #1916 (AC-10):** Gibt `_get_cached_weather` wegen `not_briefing_backed` `None`
zurück, ist `cached` in `check_all_trips()` (Zeile 540 ff.) falsy — `check_and_send_alerts()`
wird für diesen Trip in diesem Lauf gar nicht erst aufgerufen. Damit können auch die beiden
rollierenden-Anker-Schreibtrigger aus #1916 (Trigger (a): tatsächlicher Alarm-Versand,
Zeile 407-412; Trigger (b): opportunistische Ceiling-Auffrischung, Zeile 320-332) nicht
laufen. Diese Verträglichkeit ergibt sich strukturell aus der Reihenfolge der beiden
Scheiben und ist NICHT durch einen expliziten Check im Produktivcode abgesichert — AC-10
macht sie durch einen Test verbindlich, statt sie unbewacht der zufälligen
Implementierungsreihenfolge zu überlassen.

### Doku-Nachzug

`alert_briefing_anchor.py` bekommt den vierten Ablehnungsgrund `not_briefing_backed` im
Docstring ergänzt, analog zu `wrong_day`/`too_old`/`missing`. Die Diagnose-Funktion selbst
ist bereits generisch (nimmt jeden String entgegen) und braucht keinen Code-Eingriff.

## Expected Behavior

- **Input:** ein Alarm-Lauf für einen Trip, dessen einziger vorhandener Snapshot durch
  eine reine Abfrage (`glance`, `heute_gewitter`, `timeline_heute` u. a.) entstanden ist,
  nicht durch ein reguläres Briefing.
- **Output:** der Abweichungs-Alarm verwirft diesen Anker (`None`), NICHT stillschweigend
  als gültig verwendet; ein Diagnose-Eintrag mit `reason="not_briefing_backed"` entsteht.
  Amtliche Warnungen für denselben Trip bleiben unberührt — sie lesen denselben Snapshot
  weiterhin nur als Geometrie. Der bereits laufende rollierende Alarm-Anker aus #1916 wird
  in diesem Lauf weder erzeugt noch fortgeschrieben (AC-10).
- **Side effects:** ein neuer JSONL-Diagnose-Eintrag; kein neuer HTTP-Endpunkt, keine
  Migration von Bestandsdaten, kein neues Datenverzeichnis.

## Acceptance Criteria

- **AC-1:** Abfrage ohne vorhandenen Anker erzeugt keinen gültigen Alarm-Vergleichspunkt.
  Given ein Trip ohne undatierten Snapshot (kein Briefing gelaufen) / When der Nutzer
  `/glance` sendet und danach der Abweichungs-Alarm läuft / Then verwirft der Alarm den
  dabei entstandenen Snapshot und versendet keinen Abweichungsalarm.
  - Test: Kern. Trip-Fixture ohne Snapshot, `glance`-Kommando über den echten Verarbeitungspfad
    senden (schreibt `briefing_backed=False`-Snapshot), danach `check_and_send_alerts()`
    aufrufen. Assert: `_get_cached_weather` liefert `None`, kein Alarm-Versand.
  - Scheitert ohne Fix: der frisch geschriebene Snapshot trägt `target_date=heute` und
    besteht die #1661-Prüfung anstandslos, der Alarm vergleicht gegen den
    Abfragezeitpunkt statt gegen ein Briefing.

- **AC-2:** Die Diagnose unterscheidet „gar kein Anker" von „Anker ohne Briefing". Given
  Lage wie AC-1 / When der Alarm läuft / Then trägt
  `diagnostics/alert_anchor_rejected.jsonl` einen Eintrag mit
  `reason = "not_briefing_backed"` — nicht `missing`, nicht `wrong_day`.
  - Test: Kern. Wie AC-1, danach die JSONL-Datei einlesen (nicht per String-Suche im
    Dateiinhalt, sondern strukturiert parsen) und den `reason`-Wert der letzten Zeile
    prüfen.

- **AC-3 (zentrale Nicht-Regression):** Amtliche Warnungen bleiben unberührt. Given ein
  Trip, dessen einziger Snapshot aus einer Abfrage stammt, und eine vorliegende amtliche
  Warnung / When der Alarm-Lauf stattfindet / Then wird die amtliche Warnung versendet,
  weil für sie nur die Geometrie zählt (`tagesgleicher_anker_noetig=False`,
  `trip_alert.py:693-695`).
  - Test: Kern. Wie AC-1, zusätzlich amtliche Warnungs-Fixture für die Trip-Route
    vorbereiten. `check_official_alert_triggers()` direkt aufrufen. Assert: Warnung wird
    ausgelöst/versendet, unabhängig vom `briefing_backed`-Status des Snapshots.
  - **Mutations-kritischer Test dieser Scheibe:** verschiebt man die neue Prüfung
    fälschlich VOR den amtlichen Ausstieg in Stufe 3 (Zeile 693, statt danach) — oder in
    den amtlichen Ausstieg von Stufe 2 (Zeile 668) —, MUSS dieser Test rot werden —
    amtliche Warnungen würden sonst für jeden Trip mit reinem Abfrage-Anker verstummen.

- **AC-4:** Ein regulärer Briefing-Anker bleibt gültig. Given ein reguläres Briefing hat
  den Snapshot geschrieben (`target_date` = heute) / When der Alarm läuft / Then arbeitet
  der Abweichungsalarm unverändert und es entsteht kein Diagnose-Eintrag.
  - Test: Kern. Snapshot über den regulären Briefing-Pfad (`briefing_backed` implizit
    `True`) schreiben, Alarm-Lauf ausführen. Assert: Rückgabe sind die geladenen
    Segmente, keine neue Zeile in der Diagnose-Datei.

- **AC-5 (Altbestand):** Given eine vor dem Deploy geschriebene Snapshot-Datei OHNE das
  Feld `briefing_backed`, mit `target_date` = heute / When der Alarm läuft / Then gilt sie
  als briefing-gestützt, der Abweichungsalarm arbeitet normal und es entsteht kein
  Diagnose-Eintrag.
  - Test: Kern. Fixture-Datei direkt (nicht über `save()`) ohne den Schlüssel
    `briefing_backed` anlegen. Assert: Rückgabe der Lesemethode `True`, kein Verwerfen,
    keine Diagnose-Zeile.

- **AC-6:** Die Anzeigepfade bleiben vollständig. Given ein Trip ohne Snapshot / When der
  Nutzer `/glance`, `/gewitter` oder eine Timeline-Abfrage sendet / Then enthält die
  Antwort dieselben Wetterdaten wie vor dieser Änderung (Fortschreibung von AC-6 aus
  #1661).
  - Test: Kern. `WeatherExtractor.timeline()`/`.drilldown()` bzw. die
    Kommando-Antworttexte nach der Abfrage prüfen — Assert: `available=True`, Daten
    vorhanden, unverändert gegenüber dem Stand vor dieser Scheibe.

- **AC-7 (Selbstheilung):** Given ein durch eine Abfrage entstandener, als nicht
  briefing-gestützt markierter Snapshot / When danach ein reguläres Briefing läuft / Then
  ist der Anker wieder briefing-gestützt und der Abweichungsalarm arbeitet wieder.
  - Test: Kern. Erst Abfrage (schreibt `briefing_backed=False`), dann regulären
    Briefing-Lauf ausführen (überschreibt den Snapshot mit `briefing_backed=True`),
    danach Alarm-Lauf. Assert: kein Verwerfen mehr, kein neuer Diagnose-Eintrag.

- **AC-8 (Persistenz-Roundtrip):** Given `save(..., briefing_backed=False)` / When die
  Lesemethode das Feld liest / Then liefert sie `False`; bei regulärem `save()` ohne
  Angabe liefert sie `True`.
  - Test: Kern (`tests/integration/test_weather_snapshot.py`). Beide Fälle direkt gegen
    `WeatherSnapshotService` fahren (echte Datei in `tmp_path`), Rückgabewert der neuen
    Lesemethode prüfen.

- **AC-9 (Regression `/heute`):** Given der bestehende On-Demand-Pfad über
  `send_on_demand_report` (`on_demand=True`) / When `/heute` oder `/morgen` gesendet wird
  / Then bleiben Anker und Melde-Gedächtnis unberührt wie bisher (bewacht durch
  `tests/tdd/test_trip_briefing_anchor_unchanged.py::test_ac27_ad_hoc_abruf_laesst_anker_und_gedaechtnis_unberuehrt`).
  - Test: Kern, bestehender Test unverändert grün — reine Regressionskontrolle, dass
    dieser Fix den sauberen `/heute`-Pfad (der nie in `_fetch_and_save_snapshot` läuft)
    nicht anfasst.

- **AC-10 (Naht zu #1916 — kein rollierender Anker aus verworfener Basis):** Given ein
  Trip, dessen einziger Δ-Anker in Stufe 3 der Prioritätskette wegen `not_briefing_backed`
  verworfen wird (kein Briefing-Anker in Stufe 1, kein gültiger rollierender Anker in
  Stufe 2) / When der Alarm-Lauf (`check_all_trips` → `check_and_send_alerts`) für diesen
  Trip ausgeführt wird / Then entsteht in diesem Lauf KEIN neuer oder aktualisierter
  rollierender Alarm-Anker (`{trip_id}_alarm_anchor.json`) — weder über Trigger (a)
  (tatsächlicher Alarm-Versand, #1916) noch über Trigger (b) (opportunistische
  Ceiling-Auffrischung, #1916) —, weil `check_and_send_alerts()` bei verworfener
  Vergleichsbasis für diesen Trip in diesem Lauf gar nicht erst aufgerufen wird.
  - Test: Kern. Trip-Fixture mit ausschließlich einem `briefing_backed=False`-Snapshot
    (kein Briefing-Anker, kein rollierender Anker vorbestehend), `check_all_trips()` real
    durchlaufen lassen. Assert: `WeatherSnapshotService.load_alarm_anchor(trip.id)`
    liefert weiterhin `None`. Ergänzende Variante mit vorbestehendem, bereits abgelaufenem
    rollierenden Anker vom Vortag: Assert, dass dessen Datei nach dem Lauf unverändert
    bleibt (kein neuer `snapshot_at`/`target_date`).
  - Scheitert ohne #1699 bzw. bei falscher Eingriffsstelle innerhalb
    `_get_cached_weather`: der verworfene Anker würde dennoch als `cached` durchgereicht,
    `check_and_send_alerts()` liefe an und könnte über Trigger (a)/(b) einen rollierenden
    Anker aus einer nicht briefing-gestützten Basis erzeugen — der laut #1916-Kette danach
    in Stufe 2 ungeprüft an der neuen Herkunftsprüfung vorbei zurückgegeben würde.
  - PO-Begründung (wörtlich, sinngemäß übernommen): mit #1699 ist das automatisch erfüllt,
    aber „automatisch erfüllt heißt unbewacht, und ohne Test hängt es an der Reihenfolge
    zweier unabhängig entstandener Scheiben."

## Known Limitations

- Siehe Abschnitt „Bekannte Grenze der gewählten Auslegung" oben — durch den Bug bereits
  entstandene Pseudo-Anker heilen erst durch das nächste reguläre Briefing, nicht
  rückwirkend.
- **Übergangsfenster rollierender Anker (#1916):** ein vor dem Deploy dieser Scheibe
  bereits bestehender rollierender Alarm-Anker schließt sein Übergangsfenster praktisch
  binnen rund eines Tages — Detail-Mechanik (zwei unterschiedliche Ablehnungsgründe je
  nach Herkunft des zugrunde liegenden undatierten Snapshots) s. Abschnitt „Bekannte
  Grenze der gewählten Auslegung" oben, Zusatz nach #1916-Merge.
- Der Nebenaspekt `target_date` für heute+morgen (`trip_command_processor.py:301-303`)
  bleibt unverändert bestehen (s. „Nicht in dieser Scheibe").

## Testplan

Alle Tests laufen in der **Kern-Schicht** (deterministisch, kein Netz, keine
Live-Postfächer) — kein AC dieser Scheibe braucht Staging oder echten Versand.

| AC | Zieldatei | Ansatz |
|---|---|---|
| AC-1, AC-2, AC-3, AC-4, AC-6, AC-7 | `tests/tdd/test_alert_anchor_day_guard.py` | echter Abfrage-Pfad (`trip_command_processor`) + echter `TripAlertService`-Lauf, Diagnose-Datei strukturiert einlesen |
| AC-10 | `tests/tdd/test_alert_anchor_day_guard.py` | echter `check_all_trips()`-Lauf, aber **deterministischer Fixture-Anker** statt echtem Abfrage-Pfad (s. u.) |
| AC-5, AC-8 | `tests/integration/test_weather_snapshot.py` | echte Dateien in `tmp_path`/isolierter `get_data_dir()`, kein Mock |
| AC-9 | `tests/tdd/test_trip_briefing_anchor_unchanged.py` | Bestandstest, unverändert — reine Regressionskontrolle |

**Warum AC-10 den echten Abfrage-Pfad NICHT benutzt** (Korrektur aus Fix-Loop-Runde 1,
Finding F003): die echte Abfrage schreibt reale Fixture-Wetterwerte, gegen die der frische
Abruf kein Delta ergibt. Trigger (a) aus #1916 könnte dann gar nicht feuern, und der Test
wäre trivial grün — er bewiese nichts. Die AC-10-Tests setzen deshalb den
deterministischen Anker-Schreiber (200 km/h Böen) plus gezieltes `briefing_backed=False`
ein, sodass ein Alarm-Versand — und damit ein rollierender Anker — bei falscher
Implementierung tatsächlich entstünde. Dass der **Schreibpfad** das Merkmal setzt, weisen
AC-1, AC-2 und AC-7 über `TripCommandProcessor` nach; beide Enden der Naht sind damit
abgedeckt, nur nicht durch dasselbe AC.

**AC-3 ist der Mutations-kritische Test dieser Scheibe:** verschiebt man die neue
Herkunftsprüfung fälschlich vor einen der beiden amtlichen Ausstiege in `trip_alert.py`
(Stufe 2 Zeile 668, Stufe 3 Zeile 693) statt danach, MUSS AC-3 rot werden — sonst würden
amtliche Warnungen für Touren mit reinem Abfrage-Anker verstummen, was #1701 („Alarme
müssen alle Kanäle erreichen") direkt widerspricht.

Dafür braucht AC-3 **zwei** Tests, einen je Ausstieg (Korrektur aus Fix-Loop-Runde 1,
Finding F001 — vorher deckte nur Stufe 3 ab, und die Stufe-2-Hälfte der Zusicherung war
unbewacht):

- `test_ac3_amtliche_warnung_geht_trotz_anker_ohne_briefing_raus` — Stufe 3. Kein
  rollierender Anker vorhanden, die Kette fällt bis zum undatierten Rückfall durch.
- `test_ac3_amtliche_warnung_ueberlebt_auch_die_stufe_2_weiche` — Stufe 2. Nur mit einem
  **gültigen rollierenden Anker von heute** wird diese Weiche überhaupt betreten; ohne ihn
  liefert `load_alarm_anchor()` `None` und eine dort eingefügte Prüfung liefe nie.

**AC-10 prüft zusätzlich den Mechanismus, nicht nur seine Folge** (Korrektur aus
Fix-Loop-Runde 1, Finding F002): dass `check_and_send_alerts()` bei verworfener Basis „gar
nicht erst aufgerufen wird", weist
`test_ac10_verworfene_basis_ruft_check_and_send_alerts_gar_nicht_erst_auf` am echten
Kontrollfluss nach (Unterklasse des echten Dienstes, die den Aufruf protokolliert und an
die Originalfassung weiterreicht; zweite Tour im selben Lauf als Positivkontrolle). Ohne
ihn hing die Zusicherung nur daran, dass `_fetch_fresh_weather(None)` einen `TypeError`
wirft, den `check_all_trips()` verschluckt — ein späteres `cached_weather or []` hätte sie
lautlos gekippt.

**Die Torbedingung wird als KLASSE bewacht, nicht fallweise** (Korrektur aus
Fix-Loop-Runde 2, Finding F005). Ausgezählt am Torcode (`trip_alert.py:540-547`)
entscheidet das Tor aus genau zwei unabhängigen Größen — `cached` (Δ-Basis gültig /
verworfen) und `official_notices` (amtliche Warnung liegt vor / nicht), also vier
Kombinationen. `test_torbedingung_matrix_basis_mal_amtliche_warnung` fährt alle vier und
prüft je Kombination: läuft `check_and_send_alerts()`, wird zugestellt, entsteht ein
rollierender Anker, steht `not_briefing_backed` in der Diagnose. Die Positivkontrollen
stecken in der Parametrisierung selbst. Der **rollierende #1916-Anker ist keine dritte
Achse dieses Tors** — er ändert nur, woraus `cached` entsteht (Stufe 2 statt Stufe 3),
nicht die Torentscheidung; seine eigenen Nähte bewachen die beiden oben genannten
Stufen-2-Tests. Anlass: dieselbe Naht war zweimal fallweise nachgezogen worden (F002 ohne,
F005 mit amtlicher Warnung).

**AC-10 ist der Naht-Test zu #1916:** er wird NICHT durch die Implementierung dieser
Scheibe selbst rot/grün geschaltet (kein eigener neuer Codepfad), sondern durch die
Reihenfolge der beiden Prüfungen in `_get_cached_weather`/`check_all_trips`. Ein Refactor,
der `check_and_send_alerts()` künftig auch bei verworfenem Anker aufruft, MUSS AC-10 rot
werden lassen.

Kein Mock-Theater: alle Tests laufen über echte Dateien/echten Verarbeitungspfad (keine
`Mock()`/`patch()`/`MagicMock`, die nur die eigene Annahme zurückspiegeln), keine
Dateiinhalt-String-Checks als Verhaltensnachweis.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe stellt eine bestehende, bereits dokumentierte Invarianz
  wieder her, statt eine neue Entscheidung zu treffen:
  1. **#1007-Invariante** (`trip_report_scheduler.py:1495-1501`, „On-Demand-Abruf ist
     read-only gegenüber Snapshot-/Alert-Zustand") — der Fix macht den lesenden
     Alarm-Pfad wieder blind für Snapshots, die diese Invariante am Schreibpfad bereits
     verletzt (die Schreibseite selbst bleibt Konsens: Abfragen dürfen weiterhin
     Snapshots schreiben, damit die Anzeige funktioniert — AC-6).
  2. **ADR-0009** (Alerts als Abweichungs-Wächter) — ein Vergleichspunkt ohne
     zugrundeliegendes Briefing widerspricht der dort getroffenen Entscheidung direkt;
     dieser Fix stellt sie für den betroffenen Pfad wieder her, ohne das ADR selbst zu
     ändern.
  3. **#1661-Präzedenzfall** (additives Feld, schlanke Lesemethode,
     `record_alert_anchor_rejected`) wird strukturell wiederverwendet, kein neues Muster.
  4. **#1701** (Alarme müssen alle Kanäle erreichen) begrenzt den Wirkbereich der neuen
     Prüfung strikt auf den Abweichungs-Alarm-Pfad — amtliche Warnungen dürfen dadurch in
     keinem Fall verstummen (AC-3).
  5. **ADR-0056 / #1916** (rollierender Alarm-Anker) — diese Scheibe ändert #1916 nicht,
     sichert aber über AC-10 die Verträglichkeit ab: eine in Stufe 3 verworfene Basis darf
     nicht über die Stufe-2-Mechanik von #1916 wieder ins System zurückfließen.

## Changelog

- 2026-08-17: Initiale Spec. Scope aus `docs/context/fix-1699-heute-abfrage-anker.md`
  (Analyse-Ergebnis, PO-Entscheidung Altbestand-Auslegung, technischer Ansatz)
  übernommen, ohne Abweichung.
- 2026-08-17 (Nachzug nach Merge #1916, Merge-Commit `4aa227f2`): Zeilennummern in
  `Source`, `Affected Files` und `Implementation Details` auf den aktuellen Working-Tree-
  Stand korrigiert (dreistufige Prioritätskette statt zweistufig, zwei amtliche Ausstiege
  statt einem). Neues AC-10 (Naht zu #1916, PO-Vorgabe wörtlich übernommen) ergänzt.
  „Bekannte Grenze der gewählten Auslegung" um verifizierten Absatz zum Übergangsfenster
  des rollierenden Alarm-Ankers erweitert — dabei den in der Beauftragung skizzierten
  Mechanismus („Stufe 3 lehnt jeden Pseudo-Anker wegen `not_briefing_backed` ab") am Code
  korrigiert: das gilt nur für nach dem Deploy geschriebene Pseudo-Anker (Feld explizit
  `False`); Altbestand ohne Feld wird stattdessen weiterhin über die ältere
  #1661-Datumsprüfung abgewiesen (`reason=wrong_day`) — derselbe praktische ~1-Tag-Rahmen,
  anderer Ablehnungsgrund. AC-1 bis AC-9 inhaltlich unverändert.
- 2026-08-17 (Fix-Loop-Runde 1 nach Adversary-Verdict BROKEN): **nur Testplan-Text, keine
  AC geändert.** F001 — die Zusicherung „AC-3 fängt auch die Verschiebung in den amtlichen
  Ausstieg von Stufe 2" war falsch, weil der vorhandene Test Stufe 2 nie durchläuft; ein
  zweiter AC-3-Test mit gültigem rollierendem Anker macht sie wahr. F002 — der von AC-10
  behauptete Mechanismus („`check_and_send_alerts()` wird gar nicht erst aufgerufen") war
  von keinem Test geprüft und hing an einem verschluckten `TypeError`; ein Test am echten
  Kontrollfluss weist ihn jetzt nach. F003 — die Testplan-Zeile behauptete für AC-10 den
  echten Abfrage-Pfad; tatsächlich (und begründet) ein deterministischer Fixture-Anker.
- 2026-08-17 (Fix-Loop-Runde 2): **nur Testplan-Text, keine AC geändert.** F005 — die
  Torbedingung in `check_all_trips()` war zweimal fallweise nachgezogen worden; sie wird
  jetzt als Klasse über beide Achsen (Δ-Basis × amtliche Warnung, vier Kombinationen)
  parametrisiert bewacht. Begründung, warum der rollierende #1916-Anker keine dritte Achse
  dieses Tors ist, mit aufgenommen.
