---
entity_id: compare_metric_order
type: module
created: 2026-07-24
updated: 2026-07-24
status: draft
version: "1.0"
tags: [compare, shared, metrics, reihenfolge, bugfix]
---

<!-- Issue #1359 — Scheibe 1 von 2 (Metrik-Reihenfolge). Scheibe 2 (Orts-Reihenfolge) folgt separat. -->

# Metrik-Reihenfolge im Ortsvergleich (Scheibe 1 von Issue #1359)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich kann der Nutzer heute Wetter-Metriken nur an- und abwählen,
nicht aber in eine von ihm gewünschte Reihenfolge bringen — die Reihenfolge
in der Mail entsteht zufällig als Nebenwirkung der Klick-Historie. Diese
Scheibe schaltet den bereits existierenden, im Trip-Editor genutzten
Reihenfolge-Baustein (Ziehen-zum-Sortieren mit Positionsnummern) für den
Ortsvergleich frei und sorgt dafür, dass die eingestellte Reihenfolge
tatsächlich gespeichert wird und in der HTML-Vergleichsmail, ihrem
Klartext-Teil und der Telegram-Nachricht identisch erscheint. „Amtliche
Warnungen" bleibt dabei immer an erster Stelle.

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` —
  Vergleich-Zweig (Grundauswahl-Checkboxen, aktuell ohne Reihenfolge-Block)
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` —
  `weatherMetricsTabSections()`, `ROUTE_ONLY_SECTIONS`
- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` —
  `flushPendingWeatherMetricsSave()` (Diff-Guard)
- **File:** `src/output/renderers/comparison.py` — `render_comparison_text()`,
  `render_compare_telegram()`, `_channel_metric_cells()`
- **Identifier:** `toggleCompareMetric`, `WeatherV2Reihenfolge`, `SortableList`,
  `resolve_enabled_metrics`, `CV2_METRICS`, `_visible_metrics`

## Estimated Scope

- **LoC:** ~120-160 (unter dem 250er-Limit)
- **Files:** ~6 (siehe Implementation Details)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | intern (bestehend, unverändert) | Fertiger Reihenfolge-Baustein (`SortableList` + `DragHandle` + Positionsnummern) — wird für Compare **wiederverwendet**, nicht nachgebaut |
| `frontend/src/lib/components/shared/dnd/SortableList.svelte`, `DragHandle.svelte` | intern (bestehend, unverändert) | Ziehen-Mechanik (ADR-0024) — bereits geteilt |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | intern (bestehend) | Kennt `context="route"|"vergleich"` bereits (`hasLabelColumn`) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsTabSections.ts` | intern (MODIFY) | Steuert Sichtbarkeit des `reihenfolge`-Abschnitts je Kontext |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | intern (MODIFY) | Diff-Guard vor dem Speichern (`flushPendingWeatherMetricsSave`) |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts` (`COMPARE_METRIC_KEYS`) | intern (MODIFY) | Legacy-Standardreihenfolge für Altbestände ohne gespeicherte Auswahl |
| `src/output/renderers/compare_metric_ids.py` (`resolve_enabled_metrics`) | intern (bestehend, unverändert) | Bereits reihenfolge-erhaltend (`dict.fromkeys`) — trägt schon |
| `src/output/renderers/email/compare_html.py` (`CV2_METRICS`, `_visible_metrics`) | intern (bestehend, unverändert) | HTML-Pfad ordnet bereits korrekt nach der übergebenen Liste — trägt schon |
| `src/output/renderers/comparison.py` (`render_comparison_text`, `render_compare_telegram`) | intern (MODIFY) | Klartext + Telegram folgen heute einer festen Quellcode-Reihenfolge statt der übergebenen Liste |
| `.claude/hooks/renderer_mail_gate.py` (Issue #811) | Gate | Greift, weil `comparison.py` zu den Renderer-Dateien zählt — Pflicht-Nachweis vor Commit |
| `.claude/hooks/email_spec_validator.py` | Gate | Compare-Mail-Validator gegen echt zugestellte Staging-Mail |

## Implementation Details

### 1. Sperre 1 — Abschnitt für Vergleich freigeben

`weather-metrics-tab/weatherMetricsTabSections.ts:19` — `'reihenfolge'` aus
`ROUTE_ONLY_SECTIONS` herauslösen (Muster: `'official_alerts'`, das bereits
für beide Kontexte sichtbar ist, s. Zeile 24). `sms_schwellen` und
`report_config` bleiben route-exklusiv (dafür gibt es im Vergleich keine
Mail-Wirkung).

### 2. Vergleich-Zweig bindet denselben Baustein ein

`WeatherMetricsTab.svelte` — der `{#if context === 'vergleich'}`-Zweig
(aktuell reine Checkbox-Liste, Zeilen ~740-783) bekommt zusätzlich den
gleichen `LayoutTab` + `WeatherV2Reihenfolge` + `WeatherV2MailPreview`-Block,
den der Route-Zweig bereits benutzt (Zeilen ~853-885), mit `context`
dynamisch statt hart `"route"` und `primaryColumns={wiz.activeMetricKeys}`
statt `buckets.primary`. Eine kleine `metricById`-Ableitung aus dem bereits
geladenen Compare-Katalog (`compareCatalog`) liefert Label/Einheit für die
Zeilen. Der Route-Zweig bleibt unverändert (Regressionsschutz, geteilter
Baustein).

`onDndReorder` ruft im Vergleich-Zweig direkt `wiz.activeMetricKeys = newOrder`
und danach denselben Speicherauslöser, den der Idealwerte-Tab bereits für
Drag-Interaktionen nutzt (kein neues Speicher-Muster).

**Fixierte „Amtliche Warnungen"-Zeile:** `SortableList`/`WeatherV2Reihenfolge`
kennen nur die tatsächlich ziehbaren `primaryColumns` (`activeMetricKeys`);
„Amtliche Warnungen" liegt außerhalb dieses Namensraums (eigener Schalter
`officialAlertsEnabled`) und lässt sich nicht ohne Eingriff in den geteilten
Trip-Baustein als nicht-ziehbare Listenzeile einhängen. Gewählte Lösung
(PO-sanktionierter Fallback): ein Hinweistext im vorhandenen
`option-hint`-Muster direkt über dem Reihenfolge-Block im Vergleich-Kontext,
z. B. „Amtliche Warnungen stehen unabhängig von dieser Reihenfolge immer an
erster Stelle." Kein neues Bedienelement, kein Eingriff in `SortableList`.

### 3. Sperre 2 — `toggleCompareMetric` von Set auf Array

`WeatherMetricsTab.svelte:682-687` — `toggleCompareMetric` baut aktuell über
ein `Set` neu auf (`new Set(wiz.activeMetricKeys)` → `[...active]`), was die
Iterationsreihenfolge von `Set` nicht garantiert an der ursprünglichen
Listenposition festhält und beim Wiederanhaken ans Ende schiebt. Umstellung
auf Array-Filter/-Push (Trip-Muster, z. B. `onToggleMetric` im Route-Zweig):
Abwählen entfernt die ID aus dem Array an ihrer Position (Position geht
verloren, das ist beabsichtigt — abgewählt heißt "nicht mehr in der Mail");
Wiederanwählen hängt sie ans Ende an (definiertes, nachvollziehbares
Verhalten, keine geheime Merk-Position).

### 4. Sperre 3 — Diff-Guard erkennt reine Umsortierung nicht

`weatherMetricsCompareSave.ts:54-58` — `norm()` normalisiert aktuell mit
`[...s.activeMetricKeys].sort()` vor dem Vergleich. Zwei Listen mit
derselben Menge in unterschiedlicher Reihenfolge gelten dadurch als
identisch → `flushPendingWeatherMetricsSave` liefert `null` → kein PUT. Das
`.sort()` auf `activeMetricKeys` entfernen (reiner Array-Vergleich in
Reihenfolge). `officialAlertsEnabled` bleibt wie bisher normalisiert (ist
kein Array). Die AC-4-Eigenschaft aus `compare_weather_metrics_tab.md`
(„kein Schreiben ohne Nutzer-Geste") bleibt gewahrt, weil die Auslösung
weiterhin an einer echten Geste (Drag-Ende bzw. Checkbox-Toggle) hängt, nicht
am Diff-Guard.

### 5. Risiko: Speichern nach Ziehen muss tatsächlich feuern

Der Idealwerte-Tab löst Speichern über Tab-Wechsel/`window`-`pointerup` aus
— ein Muster, das für Checkbox-Toggles ausreicht. Nach einer echten
Ziehgeste unterdrücken Browser häufig das nachfolgende `click`-Ereignis;
`pointerup` feuert davon unabhängig, muss aber empirisch gegen Staging
geprüft werden, bevor diese Scheibe als fertig gilt (s. AC-3). Zeigt sich,
dass der Speichervorgang nach dem Ziehen ausbleibt, wird — wie im
Trip-Editor bereits gelöst — direkt aus `onDndReorder` heraus gespeichert
statt über den indirekten Pointerup-Umweg.

### 6. Klartext + Telegram folgen der Reihenfolge

`src/output/renderers/comparison.py`:

- `render_comparison_text()` (Zeilen ~68-193) rendert die Übersichtszeilen
  heute als feste Sequenz einzelner `if _metric_visible(...)`-Blöcke in
  Quellcode-Reihenfolge — `_metric_visible` (Zeilen 126-127) prüft nur
  Mitgliedschaft, nicht Position. Umbau: eine geordnete Iteration über
  `enabled_metrics` (wenn nicht `None`), die für jede ID die passende
  Renderzeile erzeugt; ist `enabled_metrics is None`, bleibt exakt die
  bisherige Quellcode-Reihenfolge erhalten (Regressionsschutz für
  Altbestände, AC-7). Empfehlung: keine zweite Katalog-Datenstruktur
  anlegen — eine schlanke `{metric_id: render_fn}`-Zuordnung auf Basis der
  bestehenden Zeilen-Logik genügt; Labels/Formatierung bleiben, wie sie
  sind.
- `render_compare_telegram()` → `_channel_metric_cells()` (Zeilen ~349-367)
  iteriert über die feste Tupel-Konstante `_CHANNEL_METRICS` und prüft
  ebenfalls nur Mitgliedschaft. Umbau: bei gesetztem `enabled_metrics` in
  dessen Reihenfolge iterieren (gefiltert auf das, was `_CHANNEL_METRICS`
  überhaupt kennt), sonst unverändert die bisherige Tupel-Reihenfolge.
  `_channel_metric_cells` wird auch von `render_compare_sms` genutzt — SMS
  ist damit ein *unbeabsichtigter, aber unschädlicher* Nutznießer derselben
  Reihenfolge-Korrektur (kein eigenes AC in dieser Scheibe, SMS ist ohnehin
  auf zwei Metriken budgetiert und war vom PO für die Reichweite dieser
  Scheibe nicht genannt).
- Typkorrektur: `enabled_metrics: set | None` → `enabled_metrics:
  list[str] | None` an allen Funktionssignaturen in dieser Datei (der
  latente Widerspruch aus der Analyse — faktisch wird bereits eine Liste
  durchgereicht, die Signatur lädt sonst zum nächsten Reihenfolge-Verlust
  ein).

### 7. Altbestands-Falle: Legacy-Standard auf Renderer-Reihenfolge ziehen

`corridorEditorState.ts:283-290` (`COMPARE_METRIC_KEYS`) hat heute eine
andere Reihenfolge als `compare_html.py:216-256` (`CV2_METRICS`, der
Renderer-Standard). `hydrateWeatherMetricsFromPreset` in
`weatherMetricsCompareSave.ts:22-26` greift auf `COMPARE_METRIC_KEYS`
zurück, wenn ein Preset noch nie `active_metrics` gespeichert hat. Speichert
ein solcher Altbestand zum ersten Mal irgendetwas über diesen Tab,
materialisiert sich die Frontend-Reihenfolge als `active_metrics` — und
weicht dann von der Reihenfolge ab, die die Mail vorher (ohne gespeicherte
Auswahl, `resolve_enabled_metrics(None)` → kein Filter → Renderer-Standard)
hatte. `COMPARE_METRIC_KEYS` wird deshalb auf die `CV2_METRICS`-Reihenfolge
(ohne die „warn"-Zeile, die kein Bestandteil von `activeMetricKeys` ist)
gezogen, damit ein Alt-Vergleich beim ersten Speichern dieselbe Mail behält
wie zuvor.

## Abgelöste Festlegung

`docs/specs/modules/compare_weather_metrics_tab.md:128-134` schreibt fest:

```
const ROUTE_ONLY_SECTIONS = ['reihenfolge', 'sms_schwellen', 'report_config'] as const;
```

als **komplett** route-exklusiv. Diese Festlegung vom 2026-07-18 wird mit
dieser Spec (2026-07-24) für das Element `'reihenfolge'` **abgelöst**:
`'reihenfolge'` wird für `context="vergleich"` sichtbar, `'sms_schwellen'`
und `'report_config'` bleiben unverändert route-exklusiv. Grund: Zum
Zeitpunkt von C1 (#1311) hatte der Ortsvergleich noch keinen Bedarf an einer
einstellbaren Metrik-Reihenfolge — die Grundauswahl allein genügte. Issue
#1359 stellt fest, dass genau das fehlt und die Nutzererwartung verletzt.
`compare_weather_metrics_tab.md` wird entsprechend nachgezogen (Tabelle
„Zu ändernde Festlegungen" im Kontext-Dokument).

**ADR-Prüfung:** Kein neues ADR nötig. Die zugrunde liegende
Architektur-Entscheidung — ein geteilter Baustein mit `context`-Dispatch für
Trip und Compare statt Duplikat — ist bereits in ADR-0021 (geteilte
`DeviationAlertEngine`, fortgeführt in `compare_weather_metrics_tab.md`s
ADR-0026-Verweis) getroffen; diese Scheibe erweitert lediglich, *welche*
bereits vorgesehenen Abschnitte im Vergleich-Kontext sichtbar sind, ohne
das Dispatch-Prinzip selbst zu ändern.

## Nicht in dieser Scheibe

Die **Orts-Reihenfolge** (der Orte-Tab verspricht „Reihenfolge = Spalten im
Briefing · ziehen zum Sortieren", die Mail sortiert aber weiterhin
alphabetisch) ist Teil B von Issue #1359 und wird in einer eigenen,
nachfolgenden Spec behandelt. Grund: PO-Priorität vom 2026-07-24 — die
Metrik-Reihenfolge zuerst, die Orts-Reihenfolge ist dem PO „relativ egal",
bleibt aber im Scope des Issues.

## Expected Behavior

- **Input:** Nutzer öffnet im Ortsvergleich-Editor den Tab
  „Wetter-Metriken" und zieht eine aktivierte Metrik an eine andere
  Position.
- **Output:** `display_config.active_metrics` wird in der gezogenen
  Reihenfolge gespeichert (bestehender RMW-Pfad, keine neue Persistenz);
  die nächste Vergleichs-Mail (HTML + Klartext) und Telegram-Nachricht
  zeigen die Metriken in genau dieser Reihenfolge, „Amtliche Warnungen"
  immer zuerst.
- **Side effects:** Keine — Alarmfunktion (`notify`/`metric_alert_levels`)
  bleibt unberührt (die ist bereits seit #1311 vom Mail-Inhalt entkoppelt).

## Acceptance Criteria

- **AC-1:** Given der Nutzer bearbeitet die Metrik-Liste eines
  Ortsvergleichs / When er eine angehakte Metrik an eine andere Stelle der
  Liste zieht / Then zeigt die Liste die Metrik sofort an der neuen
  Position, erkennbar an der geänderten Positionsnummer vor dem
  Metriknamen.
  - Test (Kern, deterministisch): Frontend-Komponententest zieht eine
    Zeile und prüft die resultierende Reihenfolge im internen Zustand
    ohne Netzwerk.

- **AC-2:** Given der Nutzer hat eine eigene Reihenfolge eingestellt und
  wählt eine Metrik vorübergehend ab / When er dieselbe Metrik anschließend
  wieder anhakt / Then erscheint sie am Ende der Liste und lässt sich von
  dort an die gewünschte Stelle ziehen — und die Reihenfolge **aller
  übrigen** Metriken ist dabei unverändert geblieben.
  - Test (Kern, deterministisch): Reihenfolge einstellen, eine mittlere
    Metrik abwählen und wieder anwählen, prüfen dass die restlichen
    Metriken exakt ihre relative Reihenfolge behalten haben und die
    wiederangewählte Metrik ziehbar am Ende steht.
  - Hintergrund: heute wird die Liste beim Anhaken komplett neu aufgebaut,
    wodurch sich die Reihenfolge unkontrolliert ändern kann. Der zweite
    Halbsatz ist der eigentliche Schutz — das Ans-Ende-Rutschen der
    wiederangewählten Metrik ist akzeptabel, weil es ab jetzt korrigierbar
    ist.

- **AC-3:** Given der Nutzer verändert für einen Ortsvergleich nur die
  Reihenfolge der Metriken, ohne eine einzige an- oder abzuwählen / When
  er die Seite danach neu lädt / Then zeigt der Editor weiterhin genau die
  geänderte Reihenfolge — sie wurde also tatsächlich gespeichert, nicht nur
  auf dem Bildschirm bewegt.
  - Test (Live-E2E, Staging): Playwright zieht eine Metrikzeile in
    veränderte Position, lädt die Seite neu und prüft die dargestellte
    Reihenfolge; zusätzlich wird geprüft, dass nach der Ziehgeste
    tatsächlich ein Speichervorgang ausgelöst wurde (nicht nur eine
    DOM-Bewegung ohne Persistenz).

- **AC-4:** Given der Nutzer hat für einen Ortsvergleich mit mindestens drei
  Orten eine eigene Metrik-Reihenfolge eingestellt / When der Vergleich als
  E-Mail an die konfigurierten Empfänger verschickt wird / Then erscheinen
  die Metriken in der tatsächlich zugestellten E-Mail — sowohl in der
  Tabellen-Darstellung als auch im Klartext-Abschnitt derselben Mail — in
  genau dieser Reihenfolge.
  - Test (Live-E2E, Staging): echte Vergleichs-Mail an ein Test-Postfach
    auslösen, per IMAP abrufen und mit dem Compare-Mail-Validator
    (`email_spec_validator.py`) gegen die zugestellte Mail prüfen —
    Vorschau oder DOM genügen nicht als Nachweis.

- **AC-5:** Given dieselbe eingestellte Metrik-Reihenfolge wie in AC-4 / When
  derselbe Ortsvergleich als Telegram-Nachricht an den Empfänger geht / Then
  erscheinen die Metriken in der Telegram-Nachricht in derselben Reihenfolge
  wie in der E-Mail.
  - Test (Kern, deterministisch): Renderer-Test rendert dieselbe
    Metrik-Auswahl/-Reihenfolge über den Telegram-Renderer und vergleicht
    die Zeilenfolge mit dem erwarteten Ergebnis (kein Live-Telegram-Versand
    nötig, da rein renderende Funktion mit fester Eingabe).

- **AC-6:** Given der Nutzer betrachtet die Metrik-Liste im Editor und hat
  amtliche Warnungen eingeschaltet / When er die Reihenfolge der Metriken
  beliebig umsortiert / Then steht „Amtliche Warnungen" in der zugestellten
  Mail unverändert an erster Stelle, und im Editor erklärt ein sichtbarer
  Hinweis, dass diese Zeile immer zuerst kommt und nicht Teil der
  sortierbaren Liste ist (kein Eindruck eines Sortier-Fehlers).
  - Test (Kern, deterministisch): Editor öffnen, prüfen dass die
    Amtliche-Warnungen-Zeile nicht Teil der ziehbaren Liste ist und ein
    erklärender Hinweistext sichtbar ist. Ergänzend (Live-E2E): in der
    zugestellten Mail aus AC-4 steht „Amtliche Warnungen" unabhängig von der
    übrigen Reihenfolge immer an erster Stelle.
  - **Präzisiert am 2026-07-24 nach der Staging-Verifikation.** Der
    Mail-Nachweis gilt für die **HTML-Vergleichsmatrix** — dort steht die
    Warn-Zeile in beiden Durchgängen auf Position 1, auch wenn `warn` in
    keiner der Metrik-Listen vorkam. Der **Klartext-Teil hat gar keine
    „Amtliche Warnungen"-Zeile**: Warnungen erscheinen dort als
    ⚠️-Zeilen *hinter* den Metrik-Zeilen des jeweiligen Ortes
    (`render_official_alerts_plain`). Gegen `d2838c65` geprüft: **vorher
    identisch, keine Regression dieser Scheibe.** Das AC ist damit für die
    HTML-Matrix erfüllt und für den Klartext gegenstandslos — nicht
    verletzt. Ob der Klartext eine eigene Warn-Zeile bekommen soll, ist
    eine eigene Produktfrage, nicht Teil von #1359.
  - Einschränkung des Nachweises: Die Warn-Zellen waren inhaltlich leer
    (`—`), weil zum Prüfzeitpunkt für die Testorte keine amtliche Warnung
    aktiv war. Bewiesen ist die **Position** der Zeile, nicht das Rendern
    eines Warntextes — das deckt der bestehende Bestand an
    Warnungs-Tests ab.

- **AC-7:** Given ein Ortsvergleich, für den noch nie eine Metrik-Auswahl
  gespeichert wurde / When für ihn zum ersten Mal seit dieser Änderung die
  Vergleichs-Mail gerendert wird, ohne dass der Nutzer den Metriken-Tab
  geöffnet hat / Then ist die Reihenfolge der Metriken in der Mail identisch
  zu der, die dieser Vergleich schon vor dieser Änderung hatte — nichts
  ändert sich ungefragt für Altbestände.
  - Test (Kern, deterministisch): Charakterisierungstest rendert einen
    Vergleich ohne gespeicherte Metrik-Auswahl vor und nach der Änderung
    und vergleicht die Zeilenfolge auf Gleichheit.

- **AC-8:** Given eine leere Metrik-Auswahl erreicht den Renderer / When die
  Vergleichs-Mail daraus erzeugt wird / Then enthält sie keine
  Metrik-Übersichtszeilen — die in AC-7 eingeführte Altbestands-Regel darf
  eine leere Auswahl nicht in „alle Metriken" umdeuten.
  - Test (Kern, deterministisch): Renderer mit explizit leerer Metrikliste
    aufrufen und auf eine Mail ohne Übersichtszeilen prüfen.
  - **Eingegrenzt am 2026-07-24 nach RED-Befund.** Ursprünglich formuliert
    als „Nutzer wählt alle Metriken ab → Mail bleibt leer". Die RED-Phase
    hat gezeigt, dass eine bewusst leere Auswahl schon **vor** dieser
    Änderung auf dem Weg zum Renderer zu „nichts eingestellt" verflacht und
    die Mail deshalb **alle** Metriken zeigt (`resolve_enabled_metrics`,
    `src/output/renderers/compare_metric_ids.py` — `if not active_metrics:
    return None`). Das ist ein eigenständiger, älterer Fehler ohne Bezug zur
    Reihenfolge; ihn hier mitzufixen wäre eine ungeprüfte
    Verhaltensänderung an einer zweiten Baustelle. → eigenes Issue,
    verlinkt im Changelog. AC-8 schützt in dieser Scheibe nur noch die
    Renderer-Ebene, wo das Verhalten bereits korrekt ist und durch AC-7
    nicht kaputtgehen darf.

- **AC-10:** Given der Nutzer hat eine Metrik-Reihenfolge eingestellt und
  bekommt den Ortsvergleich zusätzlich per SMS / When die SMS erzeugt wird,
  in die nur zwei Metriken passen / Then sind es die beiden, die in seiner
  Reihenfolge am weitesten oben stehen — die Sortierung entscheidet also
  mit, was auf dem knappsten Kanal ankommt.
  - Test (Kern, deterministisch): dieselbe Metrik-Menge in zwei
    Reihenfolgen durch den SMS-Renderer schicken und prüfen, dass jeweils
    die beiden vordersten Metriken erscheinen.
  - PO-Entscheidung 2026-07-24: ausdrücklich gewollt. Ohne dieses AC wäre
    es eine unbeabsichtigte, ungetestete Nebenwirkung des geteilten
    Bausteins `_channel_metric_cells`.

- **AC-9:** Given ein Trip mit einer im Wetter-Metriken-Tab eingestellten
  Metrik-Reihenfolge (Buckets/Reihenfolge-Bereich) / When der Nutzer den
  Trip-Editor wie vor dieser Änderung bedient (Metrik in eine Position
  ziehen, speichern, Trip-Briefing prüfen) / Then verhält sich der Tab in
  jeder Hinsicht identisch zum Stand vor dieser Änderung — der geteilte
  Baustein bleibt für den Trip unverändert funktionsfähig.
  - Test (Kern, deterministisch): bestehende Trip-Testsuite für den
    Wetter-Metriken-Tab bleibt unverändert grün.

## Known Limitations

- Die fixierte „Amtliche Warnungen"-Zeile wird über einen Hinweistext
  gelöst, nicht über eine technisch nicht-ziehbare Listenzeile innerhalb
  von `SortableList` — eine Änderung an `SortableList` selbst hätte
  Auswirkungen auf den Trip-Editor und andere Nutzer dieses Bausteins und
  ist damit außerhalb des Risikoprofils dieser Scheibe.
- SMS ist seit PO-Entscheidung 2026-07-24 **kein** unbenannter Nebeneffekt
  mehr, sondern durch AC-10 abgedeckt und getestet.
- **HTML und Klartext haben unterschiedliche Standard-Reihenfolgen**, solange
  ein Vergleich noch nie eine Metrik-Auswahl gespeichert hat (RED-Befund
  2026-07-24): HTML folgt der Deklarationsreihenfolge von `CV2_METRICS`,
  der Klartext seiner eigenen Quellcode-Reihenfolge. Beide Ist-Zustände
  sind in AC-7 eingefroren statt angeglichen — Angleichen würde die Mail
  eines Altbestands ungefragt ändern und damit AC-7 verletzen. Sobald der
  Nutzer irgendetwas speichert, folgen beide derselben Liste und der
  Unterschied verschwindet. **Bewusst so, nicht „nebenbei" reparieren.**
- **`LayoutTab` wird im Vergleich-Zweig bewusst NICHT eingebunden**, obwohl
  die Implementation Details das ursprünglich vorsahen (Abweichung
  2026-07-24, vom Entwickler begründet und vom Adversary unabhängig
  bestätigt). Zwei Gründe: (1) Die Kappungsaussage von `LayoutTab` ist
  spaltenbasiert („N Spalten · max 8"). Im Ortsvergleich sind die Spalten
  die **Orte**, Metriken sind Zeilen — mit Metriken als `colCount` stünde
  dort eine sachlich falsche Zahl, und sie widerspräche der korrekten
  Aussage des Hub-Reiters „Layout" (`CompareTabs.svelte`, eigener
  `CompareLayoutRow`-Pfad). Die echten Compare-Budgets sind 7 Metrik-Zellen
  je Ort (Telegram) und 2 (SMS), nicht die 8 aus `CHANNEL_COL_BUDGET`.
  (2) `WeatherV2MailPreview` rendert hartcodierte Trip-Beispielwerte
  („Beispiel-Tour · Etappe 1", Stundenspalten) und wäre im Vergleich eine
  Attrappe — die echte Vergleichs-Mail-Vorschau ist der Hub-Reiter
  „Vorschau" (Server-Render), der bereits existiert.
  Der eigentlich geteilte Baustein `WeatherV2Reihenfolge` **ist**
  wiederverwendet. Diese Abweichung ist damit kein Verstoß gegen die
  Teilungs-Invariante, sondern deren korrekte Anwendung: den passenden
  Baustein teilen, den unpassenden nicht zweckentfremden.
- `toggleCompareMetric` liegt heute als lokale Funktion in
  `WeatherMetricsTab.svelte:682-687` und ist dadurch nicht deterministisch
  testbar. Für AC-2 wird sie in eine Pure-Function-Datei extrahiert —
  Muster: das bereits existierende `weatherMetricsTabSections.ts`. Keine
  neue Struktur, sondern Anwendung des im selben Ordner etablierten.
- Die Orts-Reihenfolge (Scheibe 2 von Issue #1359) bleibt bis zur
  Folge-Spec unverändert fehlerhaft (Mail sortiert weiterhin alphabetisch).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe erweitert lediglich die Sichtbarkeit eines
  bereits vorhandenen, geteilten Bausteins (`reihenfolge`-Abschnitt) auf
  einen zweiten Kontext und korrigiert eine Renderer-Reihenfolge-Lücke —
  keine neue Architektur-, Datenmodell- oder Persistenzentscheidung; die
  zugrunde liegende Entscheidung „ein Baustein, `context`-Dispatch für
  Trip/Compare" ist bereits durch ADR-0021 und die Trip/Compare-Teilungs-
  Invariante (CLAUDE.md) getroffen.

## Changelog

- 2026-07-24: Initial spec erstellt — Issue #1359, Scheibe 1 (Metrik-Reihenfolge)
- 2026-07-24: AC-2 und AC-6 nach PO-Durchsicht geschärft (AC-2 schützt jetzt
  ausdrücklich die Reihenfolge der *übrigen* Metriken; AC-6 gegen
  beobachtbares Mail-Verhalten formuliert statt gegen einen Ziehversuch).
- 2026-07-24: Nach RED-Befunden — **AC-10** (SMS folgt der Reihenfolge, PO-go)
  ergänzt; **AC-8** auf die Renderer-Ebene eingegrenzt, die vorgelagerte
  Leerauswahl-Verflachung nach **Issue #1366** ausgelagert; Known Limitation
  zu abweichenden Standard-Reihenfolgen HTML vs. Klartext ergänzt;
  Pure-Function-Extraktion für AC-2 vermerkt.
- 2026-07-24: `LayoutTab`-Abweichung nach Adversary-Runde 1 dokumentiert.
- 2026-07-24: LoC-Grenze dieses Workflows auf PO-Freigabe angehoben — Umfang
  folgt aus der PO-Entscheidung „Reihenfolge überall gleich" (vier Kanäle
  statt nur HTML).
