---
entity_id: compare_location_order
type: module
created: 2026-07-24
updated: 2026-07-24
status: draft
version: "1.0"
tags: [compare, shared, locations, reihenfolge, bugfix]
---

<!-- Issue #1359 — Scheibe 2 von 2 (Orts-Reihenfolge). Scheibe 1
     (Metrik-Reihenfolge, `compare_metric_order.md`) ist bereits ausgeliefert. -->

# Orts-Reihenfolge im Ortsvergleich (Scheibe 2 von Issue #1359)

## Approval

- [ ] Approved

## Purpose

Der Orte-Tab im Ortsvergleich-Editor zeigt Ziehgriffe und Positionsnummern
und sagt dem Nutzer wörtlich zu: „Reihenfolge = Spalten im Briefing · ziehen
zum Sortieren" (`CompareTabs.svelte:1182`). Die Speicherung dieser
Reihenfolge funktioniert bereits nachweislich (PUT 200). Verloren geht sie
erst danach, an drei unabhängigen Stellen zwischen Speicherung und
Mail-Versand — die zugestellte Mail sortiert die Orte stattdessen weiterhin
hart alphabetisch. Diese Scheibe schließt alle drei Verluststellen, sodass
die konfigurierte Reihenfolge tatsächlich in der HTML-Vergleichsmatrix, in
den Orts-Abschnitten (Stundenverlauf) unterhalb der Matrix, im Klartext-Teil
und in der Telegram-Nachricht ankommt. Am Orte-Tab selbst ändert sich nichts
— er funktioniert bereits korrekt.

> **Korrektur 2026-07-24 nach RED-Befund:** Eine frühere Fassung nannte einen
> „Zusammenfassungs-Textblock unter der Matrix". Den gibt es in der
> zugestellten Mail nicht mehr — er wurde mit #1300 zurückgebaut (Rückbau von
> #1278, siehe `docs/specs/modules/rework_1300_compare_summary_block_removal.md`;
> der Helfer `format_location_summary` ist seither toter Code ohne Aufrufer).
> Die real orts-geordnete Fläche unterhalb der Matrix sind die
> **per-Ort-Stundenverlauf-Abschnitte**. Darauf zielen die ACs.

## Source

- **File:** `src/services/scheduler_dispatch_service.py` —
  `send_one_compare_preset()`, Zeile 340 (Verluststelle 1: Cache-Reihenfolge
  statt Preset-Reihenfolge)
- **File:** `src/services/comparison_engine.py` — `ComparisonEngine.run()`,
  Zeile 278 (Verluststelle 2: Score-Sortierung)
- **File:** `src/output/renderers/email/compare_html.py` —
  `sort_locations_alphabetically()`, Zeilen 1014-1019 (Verluststelle 3: der
  eine geteilte Sortier-Helfer für alle vier Aufrufstellen)
- **File:** `src/output/renderers/comparison.py` — drei der vier
  Aufrufstellen des Helfers: `render_comparison_text()` Zeile 154,
  `render_compare_telegram()` Zeile 379, `render_compare_sms()` Zeile 551
- **File:** `src/services/compare_preview_service.py` —
  `ComparePreviewService._resolve_locations()`, Zeilen 210-227 (das bereits
  korrekte Muster, Docstring wörtlich „Echte Orte des Nutzers in
  Preset-Reihenfolge")
- **Identifier:** `_resolve_locations`, `sort_locations_alphabetically`,
  `location_ids`, `ComparePreset.LocationIDs`

## Estimated Scope

- **LoC:** ~50-70 (unter dem 250er-Limit)
- **Files:** ~6 (siehe Implementation Details)
- **Effort:** low-medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ComparePreviewService._resolve_locations()` (`compare_preview_service.py:210-227`) | intern (bestehend, Muster) | Bereits korrektes Muster (dict-by-id, Iteration über `location_ids`) — wird als gemeinsam genutzte Funktion gezogen, nicht neu erfunden |
| `ComparePreset.LocationIDs` (`internal/model/compare_preset.go:18`) | intern (bestehend, unverändert) | Bereits geordnete Liste, Speicherweg funktioniert nachweislich (PUT 200). Die Listenposition IST die Reihenfolge — **kein neues Feld** |
| `sort_locations_alphabetically()` (`compare_html.py:1014-1019`) | intern (MODIFY) | Der eine bestehende Sortier-Helfer für alle vier Aufrufstellen — wird umgestellt (und, weil der Name sonst lügt, umbenannt), nicht verdoppelt |
| `send_one_compare_preset()` (`scheduler_dispatch_service.py:340`) | intern (MODIFY) | Verluststelle 1 |
| `ComparisonEngine.run()` (`comparison_engine.py:278`) | intern (MODIFY) | Verluststelle 2 |
| `render_comparison_text()`, `render_compare_telegram()`, `render_compare_sms()` (`comparison.py:154,379,551`) | intern (MODIFY, nur Import/Aufruf des umbenannten Helfers) | Drei der vier Aufrufstellen der Verluststelle 3 |
| `src/app/user.py` (`ComparisonResult.locations`-Kommentar, Zeile 175) | intern (MODIFY) | Falscher Kommentar „Sorted by score (descending)", seit #1110 überholt |
| `docs/specs/modules/compare_location_summary.md` (Zeile 381, AC-10) | Doku (MODIFY) | Ablösung der alphabetischen Festlegung |
| `docs/specs/_archive/modules/issue_1110_compare_mail_v2.md` (AC-1, Zeilen 223-227, 54, 70-73) | Doku (MODIFY) | Ablösung im Archiv vermerken, nicht überschreiben |
| `tests/tdd/test_issue_1110_compare_mail_v2.py` | Test (MODIFY) | Zwei alphabetisch-prüfende Tests werden umgedreht/migriert |
| `.claude/hooks/renderer_mail_gate.py` (Issue #811) | Gate | Greift, weil `compare_html.py`/`comparison.py` zu den Renderer-Dateien zählen — Pflicht-Nachweis vor Commit |
| `.claude/hooks/email_spec_validator.py` | Gate | Compare-Mail-Validator gegen echt zugestellte Staging-Mail (≥3 Orte) |

## Implementation Details

### 1. Verluststelle 1 — Versandpfad filtert über den Cache statt über die Reihenfolge

`scheduler_dispatch_service.py:340` baut die Ortsliste heute als
`[loc for loc in all_locations_cache if loc.id in location_ids]` — das
iteriert über `all_locations_cache` (beliebige Cache-Reihenfolge) und prüft
nur Mitgliedschaft. Die Reihenfolge von `location_ids` geht hier verloren,
noch bevor irgendeine Sortierung greift.

Das korrekte Muster existiert bereits in
`ComparePreviewService._resolve_locations()`: dict-by-id aufbauen, dann über
`location_ids` iterieren. Da diese Methode keinerlei `self`-Zustand
verwendet (reine Funktion aus zwei Argumenten), wird ihr Kern — dict-by-id
aufbauen + reihenfolge-erhaltend über `location_ids` filtern — in eine
gemeinsam genutzte Funktion gezogen, die beide Aufrufer nutzen. Bevorzugte
Umsetzung: der Ordnungs-Kern (ohne das Laden aus dem Nutzerverzeichnis, das
bei `send_one_compare_preset()` bereits über `all_locations_cache` erledigt
ist) wandert in eine kleine, von beiden Seiten importierbare Funktion, z. B.
`order_locations_by_ids(locations, location_ids)` neben
`_resolve_locations()` in `compare_preview_service.py` (kein neues Modul
nötig — die Datei ist der etablierte Ort für Orts-Auflösung im
Compare-Pfad). `_resolve_locations()` ruft sie intern auf, statt die Logik
zu duplizieren; `send_one_compare_preset()` importiert sie zusätzlich.
Es gibt keinen Grund, die Extraktion zu unterlassen — kein Zustand, kein
Seiteneffekt, keine zirkuläre Import-Gefahr (`scheduler_dispatch_service.py`
importiert bereits andere Renderer-/Service-Funktionen lokal in der
Funktion).

### 2. Verluststelle 2 — Score-Sortierung im Engine-Kern entfernen

`comparison_engine.py:278` — `results.sort(key=lambda r: r.score ...,
reverse=True)` wird ersatzlos entfernt. Die vorausgehende Schleife
(`for loc in locations: results.append(...)`) baut `results` bereits exakt
in der Reihenfolge des `locations`-Arguments auf — nach Entfernen der
Sortierung ist die Eingabereihenfolge automatisch die Ausgabereihenfolge,
ohne zusätzlichen Code. `LocationResult.score` bleibt berechnet und
gefüllt (wird an anderer Stelle noch gelesen), nur die Sortierung danach
entfällt. `ComparisonResult.winner` bleibt im Modell (ungenutzt im Repo,
verifiziert durch repoweite Suche), wird aber von keinem Renderer mehr
gelesen — unverändert seit #1110.

### 3. Verluststelle 3 — den einen Sortier-Helfer umstellen, nicht verdoppeln

`sort_locations_alphabetically()` bleibt die **einzige** Stelle, die alle
vier Aufrufer (`compare_html.py:1092`, `comparison.py:154,379,551`) nutzen
— das bleibt strukturell erhalten (Docstring-Zusage „keine
Doppel-Implementierung"). Nach Behebung von Verluststelle 1 und 2 kommt die
Reihenfolge bereits korrekt in `ComparisonResult.locations` an; der Helfer
muss also nicht mehr sortieren, sondern die bereits korrekte Reihenfolge
unverändert durchreichen. Da der Name `sort_locations_alphabetically` nach
dieser Änderung lügen würde, wird er umbenannt (Vorschlag:
`location_render_order()`), Body wird zur Identität (`return
list(locations)`), Docstring wird entsprechend korrigiert (Grund: einziger
Choke-Point, falls künftig doch wieder eine serverseitige Sortierung nötig
würde — deshalb bleibt die Funktion bestehen statt ersatzlos entfernt zu
werden). Alle vier Aufrufstellen werden auf den neuen Namen umgestellt,
sonst unverändert.

### 4. Vierte Verluststelle ausgeschlossen — reproduzierbare Suchstrategie

Die Analyse hat bereits alle 26 Fundstellen von `location_ids` in `src/`
geprüft und vier als ordnungserhaltend bestätigt:
`compare_official_alert.py:115`, `compare_alert.py:154`,
`compare_radar_alert.py:132`, `compare_preview_service.py:221`. Damit diese
Aussage zum Implementierungszeitpunkt erneut geprüft werden kann (Code kann
inzwischen gedriftet sein), gilt folgende Suchstrategie, die vor dem Commit
erneut auszuführen ist:

1. `grep -rn "location_ids" src/` (Tests ausgeschlossen) — jeder Treffer
   muss entweder (a) eine der drei behobenen Verluststellen, (b) eine der
   vier bereits bestätigten ordnungserhaltenden Stellen, oder (c) neuer Code
   sein, der dieselbe Prüfung (dict-by-id + Iteration über `location_ids`,
   nicht über eine andere Sammlung) erfüllt.
2. `grep -rn "\.sort(\|sorted(" src/` gefiltert auf Treffer, deren sortiertes
   Objekt `results`, `locations` oder ein Wert vom Typ `LocationResult`/
   `ComparisonResult` ist — fängt Sortierungen ab, die nicht über
   `location_ids` laufen (z. B. die jetzt entfernte Score-Sortierung).
3. `grep -rn "location_render_order\|sort_locations_alphabetically" src/` —
   es dürfen exakt die vier bekannten Aufrufstellen erscheinen, keine
   fünfte, unter keinem der beiden Namen.

### 5. Kein neues Datenmodell-Feld

`location_ids` (Go: `ComparePreset.LocationIDs`) ist bereits eine geordnete
Liste; die Listenposition ist die Reihenfolge. Es wird kein `order`-Feld
analog zum Trip-Modell (`models.py:537`) eingeführt — anders als bei
Metriken (Scheibe 1) gibt es hier auch keinen „Altbestand ohne gespeicherte
Auswahl"-Fall: jedes Preset hat laut `_resolve_locations()` immer eine
nicht-leere `location_ids`-Liste (leere Liste wirft `ValueError`, „nichts zu
vergleichen") — es gibt also keine Zweideutigkeit über die Standard-
Reihenfolge für Bestandsdaten aufzulösen.

## Abgelöste Festlegung

Die alphabetische Sortierung ist **keine Panne**, sondern eine
PO-Entscheidung vom 2026-07-08 mit eigenen, dokumentierten
Akzeptanzkriterien. Sie wird ordentlich abgelöst, nicht still überfahren:

- `docs/specs/modules/compare_location_summary.md:381`: „…HTML-Zusammenfassungs-Block
  + Klartext-Zusammenfassungs-Block, je ein Satz pro Ort mit Daten,
  **alphabetisch geordnet**, unterhalb der Übersicht…" — wird umgeschrieben
  auf „in der konfigurierten Reihenfolge".
- `docs/specs/modules/compare_location_summary.md:464-471` (AC-10): „Given
  ein Vergleich mit mehreren Orten, When die Zusammenfassungs-Sektion
  erscheint, Then sind die Orte **alphabetisch geordnet**, identisch zur
  Reihenfolge in der Matrix darüber — es gibt keine Sortierung nach Score
  und keine optische Hervorhebung eines „Gewinner"-Orts." — wird
  umgeschrieben auf „in der vom Nutzer konfigurierten Reihenfolge,
  identisch zur Reihenfolge in der Matrix darüber". Der zweite Halbsatz
  (keine Score-Sortierung, kein Gewinner) bleibt unverändert gültig.
- `docs/specs/_archive/modules/issue_1110_compare_mail_v2.md:223-227`
  (AC-1): „AC-1 (präzisiert per PO-Entscheidung 2026-07-08: alphabetisch
  statt Preset-Reihenfolge): Given eine zugestellte Ortsvergleich-E-Mail
  (HTML-Teil) / When ich sie öffne / Then enthält sie an keiner Stelle
  einen Score-Wert, eine „Bester Standort"/„Empfehlung"-Box oder
  Gewinner-Tags — die Orte erscheinen **alphabetisch nach Ortsname
  sortiert** (case-insensitiv), nicht nach Rang." — Archiv-Datei bleibt
  historisch unverändert (Archiv wird nicht umgeschrieben), bekommt aber
  einen Ablösungs-Vermerk mit Verweis auf diese Spec.
- `docs/specs/_archive/modules/issue_1110_compare_mail_v2.md:54`: „…
  `ComparisonResult.locations` (Anzeige-Reihenfolge = **alphabetisch nach
  Ortsname**, kein Score-Sort mehr — `.winner`-Property bleibt im Modell,
  wird von der Mail nicht mehr gelesen; PO-Update 2026-07-08)" — Ablösungs-
  Vermerk wie oben.
- `docs/specs/_archive/modules/issue_1110_compare_mail_v2.md:70-73`: „Ort-
  Reihenfolge in HTML und Klartext = **alphabetisch nach Ortsname**
  (deutsch, case-insensitiv, z. B. `sorted(locs, key=lambda l:
  l.location.name.casefold())`) — PO-Update 2026-07-08 (überstimmt frühere
  „Preset-Reihenfolge"). Gilt einheitlich für Übersichts-Spalten UND
  Stundentabellen-Abschnitte." — Ablösungs-Vermerk wie oben. Bemerkenswert:
  diese Formulierung überstimmte 2026-07-08 bereits eine **frühere**
  Preset-Reihenfolge-Festlegung — diese Scheibe stellt exakt jene ältere
  Festlegung wieder her.
- `src/app/user.py:175`: Kommentar `# Sorted by score (descending)` neben
  `ComparisonResult.locations` ist seit #1110 (Score-Sortierung entfernt)
  bereits falsch und wird auf den tatsächlichen Zustand korrigiert
  („Reihenfolge = konfigurierte Preset-Reihenfolge, kein Score-Sort").

**ADR-Prüfung:** Kein neues ADR nötig. Begründung: Die abgelöste
Festlegung war eine **Ausführungs-Entscheidung** aus #1110 (welche Sortier-
Regel der eine geteilte Helfer anwendet), keine Architektur-Entscheidung.
Die zugrunde liegende Architektur — genau ein Sortier-Helfer für alle
Renderer-Pfade statt vier unabhängiger Sortierungen — wird durch diese
Scheibe nicht verändert, sondern bestätigt (der Helfer bleibt bestehen,
bekommt nur einen zutreffenderen Namen und Inhalt).

## Nicht in dieser Scheibe

- **Metrik-Reihenfolge** (Scheibe 1 von Issue #1359, `compare_metric_order.md`)
  — bereits ausgeliefert und live.
- **Issue #1366** — die vorgelagerte Verflachung „leere Metrik-Auswahl wird
  vor dem Renderer in `None` (= alle Metriken) umgedeutet"
  (`compare_metric_ids.py`) betrifft Metriken, nicht Orte, und ist unter
  #1366 separat getrackt.
- Änderungen am Orte-Tab selbst (Ziehen, Positionsnummern, Hinweistext) —
  der Tab funktioniert bereits korrekt und wird nicht angefasst.

## Expected Behavior

- **Input:** Nutzer legt im Orte-Tab eines Ortsvergleichs eine bestimmte
  Reihenfolge fest (z. B. Zillertal, Innsbruck, Stubai) und speichert.
- **Output:** Die nächste Vergleichs-Mail (HTML-Matrix, Klartext-Teil,
  Zusammenfassungs-Textblock) und die zugehörige Telegram-Nachricht zeigen
  die Orte in genau dieser Reihenfolge — nicht alphabetisch, nicht nach
  Wetter-Bewertung.
- **Side effects:** Die SMS-Kurzfassung (`render_compare_sms()`) teilt sich
  denselben Sortier-Helfer und wechselt als unvermeidbare Folge ebenfalls
  von alphabetischer auf konfigurierte Reihenfolge (s. Known Limitations —
  kein eigenes AC, da nicht Teil der vom PO benannten Reichweite, aber
  Konsequenz der Ein-Helfer-Vorgabe). Sonst keine — Alarmfunktion bleibt
  unberührt.

## Acceptance Criteria

- **AC-1:** Given der Nutzer hat für einen Ortsvergleich mit mindestens
  drei Orten im Orte-Tab eine eigene, bewusst nicht-alphabetische
  Reihenfolge eingestellt und gespeichert / When der Vergleich als E-Mail
  an die konfigurierten Empfänger verschickt wird / Then erscheinen die
  Orte in der tatsächlich zugestellten E-Mail — in der Vergleichsmatrix
  oben — in genau dieser Reihenfolge, nicht alphabetisch sortiert.
  - Test (Live-E2E, Staging): echte Vergleichs-Mail mit drei Orten in
    z. B. der Reihenfolge Zillertal/Innsbruck/Stubai an ein Test-Postfach
    auslösen, per IMAP abrufen und die Orts-Reihenfolge in der Matrix
    gegen die konfigurierte Reihenfolge prüfen.

- **AC-2 (Gegenprobe):** Given derselbe Ortsvergleich wie in AC-1 wird
  anschließend auf eine andere Reihenfolge umgestellt (z. B. Innsbruck vor
  Zillertal vor Stubai) / When der Vergleich erneut verschickt wird / Then
  zeigt die neu zugestellte Mail exakt die neue Reihenfolge — die Mail
  kippt also mit der Einstellung mit, statt zufällig bei der ersten
  Reihenfolge stehenzubleiben.
  - Test (Live-E2E, Staging): dieselbe Prozedur wie AC-1 mit vertauschter
    Reihenfolge, zweite zugestellte Mail muss sich von der ersten
    unterscheiden und der neuen Einstellung folgen.

- **AC-3:** Given der Nutzer zieht im Orte-Tab einen Ort an eine neue
  Position und verlässt den Tab (die Speicherung ist bereits belegt
  funktionierend) / When der nächste planmäßige oder manuell ausgelöste
  Versand dieses Vergleichs stattfindet / Then folgt die zugestellte Mail
  der neu gezogenen Reihenfolge, ohne dass sonst etwas am Vergleich
  verändert wurde.
  - Test (Kern, deterministisch): eine gespeicherte Preset-Reihenfolge wird
    unverändert bis zum Renderer durchgereicht geprüft (Fixture-Preset mit
    fester, nicht-alphabetischer Orts-Reihenfolge → Renderer-Eingabe zeigt
    exakt diese Reihenfolge); der volle Bedien-Weg (Ziehen → Speichern) ist
    zusätzlich durch AC-1/AC-2 gegen Staging abgedeckt.

- **AC-4:** Given eine zugestellte Vergleichs-Mail mit konfigurierter,
  bewusst nicht-alphabetischer Orts-Reihenfolge (wie in AC-1) / When man
  die Vergleichsmatrix, die Orts-Abschnitte (Stundenverlauf) unterhalb der
  Matrix, den Klartext-Teil derselben Mail und die zugehörige
  Telegram-Nachricht nebeneinanderlegt / Then zeigen alle vier exakt
  dieselbe Orts-Reihenfolge — es gibt nicht zwei verschiedene Sortierungen
  innerhalb derselben Auslieferung.
  - Test (Live-E2E, Staging): dieselbe zugestellte Mail aus AC-1 liefert
    Reihenfolgen für Matrix, Orts-Abschnitte und Klartext; ergänzend
    (Kern, deterministisch): Telegram-Renderer mit derselben
    Reihenfolge/demselben `ComparisonResult` aufgerufen und die
    Zeilenfolge gegen die HTML-Reihenfolge verglichen.

- **AC-5:** Given ein Ortsvergleich, bei dem der nach Wetterlage
  „schlechteste" Ort in der vom Nutzer eingestellten Reihenfolge zufällig
  ganz vorne steht / When die Vergleichs-Mail erzeugt wird / Then steht
  dieser Ort trotzdem an erster Stelle — es findet keine unsichtbare
  Neusortierung nach Wetter-Bewertung mehr statt, weder erkennbar noch
  versteckt.
  - Test (Kern, deterministisch): Vergleichsdaten mit klar unterschiedlich
    guter/schlechter Wetterlage je Ort in einer Reihenfolge aufbauen, die
    der Bewertung nach „falsch herum" wäre, und prüfen, dass die
    Ausgabereihenfolge unverändert der Eingabereihenfolge entspricht.

- **AC-6:** Given ein bestehender Ortsvergleich, dessen gespeicherte
  Orts-Reihenfolge zufällig bereits alphabetisch ist / When seine nächste
  Vergleichs-Mail nach dieser Änderung erzeugt wird / Then sieht sie
  zeichengleich so aus wie vorher — für diesen Vergleich ändert sich
  nichts sichtbar, obwohl der zugrunde liegende Mechanismus jetzt ein
  anderer ist.
  - Test (Kern, deterministisch): Charakterisierungstest rendert einen
    Vergleich mit zufällig alphabetischer Orts-Reihenfolge vor und nach der
    Änderung und vergleicht HTML- und Klartext-Ausgabe auf Gleichheit.

- **AC-7:** Given der Nutzer öffnet den Orte-Tab eines Ortsvergleichs vor
  und nach dieser Änderung / When er das Ziehen der Orte, die
  Positionsnummern und den Hinweistext „Reihenfolge = Spalten im
  Briefing · ziehen zum Sortieren" betrachtet und benutzt / Then verhält
  sich der Tab in jeder Hinsicht identisch zum Stand vor dieser Änderung —
  diese Arbeit repariert ausschließlich, was mit der bereits
  funktionierenden Einstellung danach passiert, nicht die Einstellung
  selbst.
  - Test (Kern, deterministisch): bestehende Frontend-Tests für den
    Orte-Tab (Ziehen, Persistenz, Hinweistext) bleiben unverändert grün,
    kein Diff an Editor-Dateien in dieser Änderung.

- **AC-8:** Given der Nutzer bekommt den Ortsvergleich zusätzlich per SMS,
  in die nicht alle Orte passen / When die SMS erzeugt wird / Then stehen
  die Orte in seiner konfigurierten Reihenfolge und es schaffen die
  vordersten hinein — die übrigen werden weiterhin ehrlich als „+k"
  ausgewiesen, nie still weggelassen. Seine Reihenfolge entscheidet damit
  mit, welche Orte auf dem knappsten Kanal ankommen.
  - Test (Kern, deterministisch): dieselben Orte in zwei Reihenfolgen durch
    den SMS-Renderer schicken und prüfen, dass jeweils die vordersten
    erscheinen und der „+k"-Rest stimmt. Zusätzlich ein Wächter, dass die
    Endgarantie `len <= 140` in beiden Fällen und im Standardfall hält.
  - **Nachgetragen 2026-07-24, nicht vom Spec-Writer als Known Limitation
    belassen.** Die SMS hängt an derselben Ein-Helfer-Struktur und kippt
    ohnehin mit — das ist eine für den Nutzer **sichtbare**
    Verhaltensänderung (welche Orte er unterwegs zu sehen bekommt) und
    gehört deshalb in ein geprüftes Akzeptanzkriterium statt in eine
    Fußnote. Deckt sich mit der PO-Entscheidung zur analogen Frage bei den
    Metriken (Scheibe 1, AC-10, PO-go 2026-07-24): „meine Reihenfolge
    bestimmt die SMS mit".

## Known Limitations

- ~~SMS als unbenannte Nebenwirkung~~ — **ersetzt durch AC-8 (2026-07-24).**
  Die ursprüngliche Einordnung als „unschädlich" war falsch: `render_compare_sms()`
  iteriert über die sortierten Orte und **kappt** am 140-Zeichen-Budget mit
  einem `+k`-Suffix (`comparison.py:551 ff.`). Die Reihenfolge entscheidet
  damit, **welche Orte der Nutzer unterwegs überhaupt zu sehen bekommt** —
  eine sichtbare Verhaltensänderung, kein Randdetail. Sie gehört in ein
  geprüftes AC, sonst ändert sich Nutzerverhalten ungetestet.
- **Der Renderer-Helfer bleibt bestehen, obwohl er nach dieser Änderung
  keine Sortierung mehr durchführt** (Identity-Funktion). Grund: einziger
  Choke-Point für alle vier Aufrufstellen — sollte künftig doch wieder eine
  serverseitige Sortierregel gebraucht werden, gibt es weiterhin genau eine
  Stelle dafür, statt vier Aufrufstellen einzeln anzufassen.
- Die Fehler-Ort-Reihenfolge (ein Ort, der nicht geladen werden konnte)
  bleibt ebenfalls an seiner konfigurierten Position stehen, nicht mehr ans
  Ende oder an den Anfang verschoben — das ist eine Konsequenz aus AC-5,
  nicht gesondert getestet, weil kein bestehender Test dieses Verhalten
  bisher isoliert prüfte und keine Nutzererwartung dazu dokumentiert ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe korrigiert eine Ausführungs-Entscheidung aus
  #1110 (welche Sortier-Regel der eine geteilte Renderer-Helfer anwendet),
  keine Architektur-, Datenmodell- oder Persistenzentscheidung. Die
  zugrunde liegende Architektur — ein Sortier-Helfer für alle vier
  Renderer-Aufrufstellen statt vier unabhängiger Sortierungen — bleibt
  unverändert bestehen und wird durch diese Scheibe bestätigt, nicht
  ersetzt.

## Changelog

- 2026-07-24: Initial spec erstellt — Issue #1359, Scheibe 2 (Orts-Reihenfolge)
