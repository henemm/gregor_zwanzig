---
entity_id: fix_1719_s4_kuerzel_vereinheitlichung
type: module
created: 2026-08-12
updated: 2026-08-12
status: draft
version: "1.0"
tags: [backend, frontend, metrik-kaskade, kuerzel, telegram, sms, issue-1719]
---

# #1719 Scheibe S4 — Ein Kürzel je Größe: Telegram und SMS sprechen dieselbe Sprache, der Editor löst sie auf

## Approval

- [ ] Approved — PO, 2026-08-__ („go")

## Purpose

Heute trägt dieselbe Wettergröße bis zu drei verschiedene Kürzel, je nachdem wo sie
erscheint. Der Nutzer, der in einer SMS `N13` liest, findet im Editor `TN` — und in einer
Telegram-Tabelle `H`, wo die SMS `HU` schreibt. Diese Scheibe führt die Kürzel zusammen und
macht sie im Editor auflösbar.

**Zwei Schritte, in dieser Reihenfolge:** erst die Systeme vereinheitlichen, dann erklären.
Eine Legende für drei Kürzelsysteme zu bauen hieße, einen Zustand zu dokumentieren, den
diese Scheibe abschafft.

## Source

- Issue #1719, Scheibe S4 (letzte offene Scheibe)
- **PO-Entscheid 2026-08-12** (mitten in der Analyse, wörtlich): *„Warum gibt es ein extra
  Telegram Kürzel? Das will ich nicht!"*
- **PO-Entscheid 2026-08-12** (Gestaltung, vor dem obigen): die Kürzel stehen als
  beschriftete Marken in der Zeile der Größe, nicht als getrennter Legendenblock.
- Kontext: `docs/context/feat-1719-s4-kuerzel-legende.md`
- Vorgänger: ADR-0050 (Kaskade), `fix_1453_namensformen.md` (führte die heutigen Marken ein)

## 🔴 Die Issue-Beschreibung von S4 ist überholt — hier steht der gemessene Stand

Der Issue-Text sagt, das Backend liefere „keinen Klartext je Kürzel". Das trifft nicht zu:
`/api/metrics` liefert `label`, `col_label` und `sms_code` (`api/routers/config.py:85-97`),
und `WeatherV2Reihenfolge.svelte:97-113` zeigt seit #1453 bereits zwei Marken je Zeile.

**Der wirkliche Defekt ist ein anderer.** Die Marke „Kürzel in der SMS" zeigt `sms_code` —
das sind laut `api/routers/config.py:97` die **Alarm**-Stammdaten (#914). Die Trip-SMS
rendert aus einer anderen Tabelle (`sms_trip.py:105-190`). Bei 5 von 25 Größen weicht das
Angezeigte vom Gesendeten ab:

| Größe | Editor zeigt | Trip-SMS sendet |
|---|---|---|
| Temperatur | `D` | `K` `D` |
| **Nacht-Tiefsttemperatur** | `TN` | **`N`** |
| Gefühlte Temperatur | `TF` | `FK` `FD` `WC` |
| Gewitter | `TH` | `TH` `TH+` |
| Neuschnee | `NS` | `NS24+` |

Bei der Nachttemperatur nennt der Editor ein Kürzel, das in **keiner** SMS vorkommt, während
das tatsächlich gesendete `N` nirgends erklärt wird.

## Der Ist-Stand: vier Kürzel-Familien für dieselbe Sache

| Ausgabeweg | Quelle | `wind_chill` | `humidity` |
|---|---|---|---|
| Mail-Stundentabelle (Trip + Vergleich) | `col_label` | `Feels` | `Humid` |
| Telegram-Stundentabelle (nur Trip) | `compact_label` | `TF` | `H` |
| Trip-SMS | `SMS_MULTI_SYMBOLS_BY_METRIC` → `SMS_SYMBOL_BY_METRIC` | `FK FD WC` | `HU` |
| Vergleichs-SMS · Alarm-SMS | `sms_code` („Register-Kürzel") | `TF` | `HU` |

`compact_label` und `sms_code` werden **getrennt von Hand gepflegt**. Gemessen
(`scratchpad/tg_vs_sms.py`): 11 Größen identisch, 11 abweichend, 3 mit Mehrfach-Token.
Niemand hält sie synchron, also sind sie auseinandergelaufen — Luftdruck heißt in Telegram
`P`, Regenwahrscheinlichkeit `P%`; im Register `HP` und `PR`.

**Beide Systeme stehen schon heute in derselben Nachricht:** `sms_trip.py:811` baut die
Änderungs-Token der SMS über `get_compact_label_for_field()`, also aus `compact_label`.

## Requirements

### 1. Telegram übernimmt das Register-Kürzel

**Regel:** Telegram nutzt das Register-Kürzel (`sms_code`) — **außer** wo das
Register-Kürzel eine *Tagesauswertung* bezeichnet statt der *Größe*.

**12 Ersetzungen** (Register-Kürzel benennt die Größe):

| Größe | Telegram heute | künftig |
|---|---|---|
| Nacht-Tiefsttemperatur | `TN` | `N` |
| Gefühlte Nacht-Tiefsttemperatur | `TFN` | `FN` |
| Luftfeuchtigkeit | `H` | `HU` |
| Regenwahrscheinlichkeit | `P%` | `PR` |
| Schneefallgrenze | `SG` | `SL` |
| Bewölkung | `C` | `CT` |
| Sichtweite | `V` | `VS` |
| Sonnenstunden | `☀` | `SU` |
| Luftdruck | `P` | `HP` |
| Nullgradgrenze | `0G` | `NL` |
| Neuschnee | `NS` | `NS24+` |
| Gewitter | `⚡` | `TH` |

**2 benannte Ausnahmen** (Register-Kürzel bezeichnet eine Tagesauswertung):

| Größe | bleibt | Grund |
|---|---|---|
| Temperatur | `T` | Register führt `D` (Tageshöchst) und `K` (Tagestiefst). Die Telegram-Zelle zeigt einen **Stundenwert** — ein Spaltenkopf „Tageshöchst" wäre dort eine falsche Aussage |
| Gefühlte Temperatur | `TF` | dito, Register-Trio `FK`/`FD`/`WC` |

> **PO-Entscheidungspunkt A:** Gewitter und Sonnenstunden tragen in Telegram heute ein
> Symbol (`⚡`, `☀`) statt Buchstaben. Oben sind sie als Ersetzung eingeplant (`TH`, `SU`),
> weil „ein Kürzel je Größe" sonst nicht gilt. Sollen die beiden Symbole stattdessen
> bleiben, ist das eine Zeile in der Ausnahmeliste — bitte bei der Freigabe sagen.

### 2. `compact_label` kann nicht mehr wegdriften

Das Feld bleibt bestehen (fünf Wirkorte, acht Testdateien lesen es), wird aber **abgeleitet
statt zweitgepflegt**: Vorgabe ist das Register-Kürzel; abweichen darf nur, was in einer
benannten Ausnahmeliste mit Begründung steht (Muster: `_SMS_SYMBOL_GRAMMAR` in
`sms_trip.py:114`).

Ohne diesen Schritt wiederholt sich der Defekt beim nächsten Katalog-Eintrag — genau so ist
er entstanden.

### 3. Der Editor zeigt zwei Familien, beide wahr

Je Zeile im Bereich „Reihenfolge" stehen beschriftete Marken:

- **Mail** — `col_label` (die breite Tabelle hat Platz für `Feels`, `Dew`)
- **Kurzform** — was SMS und Telegram senden, **alle** Kürzel der Größe

```
1. ⠿ Gefühlte Temperatur  °C    Mail Feels   Kurzform FK FD WC    [Roh|Einfach] [Aus]
2. ⠿ Nacht-Tiefsttemperatur °C  Mail Nacht   Kurzform N           [Roh|Einfach] [Aus]
```

**Die Quelle richtet sich nach der Fläche** — der Touren-Editor zeigt die Trip-SMS-Kürzel
(`/api/sms-symbols`, deckt Mehrfach-Token und Grammatik ab), die drei Vergleichs-Editoren
das Register-Kürzel, weil die Vergleichs-SMS aus `get_sms_code()` rendert
(`comparison.py:625`). Eine flächenblinde Korrektur würde den Vergleich falsch machen.

### 4. Die Marken bleiben in jeder Fenstergröße vollständig lesbar

**PO-Vorgabe 2026-08-12:** *„Stelle per Browser Tests sicher, dass alle Zeichen der Legende
in unterschiedlichen Browserauflösungen sichtbar bleiben. Aktuell ist es etwas Glückssache."*

#### Gemessene Ursache

```css
.label-cell { display: flex; min-width: 0; }      /* darf unter Inhaltsbreite schrumpfen */
.metric-label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col-badge { /* kein flex-shrink, kein white-space */ }
.sms-badge { white-space: nowrap; /* kein flex-shrink */ }

@media (max-width: 899px) {
  .label-cell { flex-wrap: wrap; }                /* unter 900px: Marken brechen um */
  .metric-label { white-space: normal; }
}
```

Die Zeile ist ein Grid `28px 16px 1fr auto`; die Marken sitzen in der `1fr`-Zelle mit
`min-width: 0`. **Unter 900 px** rettet der Umbruch alles. **Ab 900 px** gibt es keinen
Umbruch, und weil den Marken `flex-shrink: 0` fehlt, werden sie zusammengedrückt und ihr
Inhalt beschnitten. Die Bruchzone ist damit **900 px bis ~1300 px**.

Der e2e-Bestand prüft 1280 px (53 Vorkommen) und 390 px (20 Vorkommen) — beide **außerhalb**
der Bruchzone; 850 px liegt im sicheren Umbruch-Modus. Die vorhandenen Testbreiten umgehen
den Defekt systematisch, deshalb ist er nie aufgefallen.

**S4 verschärft ihn**, weil die Kurzform-Marke künftig `FK FD WC` statt `TF` trägt.

#### Anforderung

Die Marken sind **unverkürzbar**: Bei Platzmangel kürzt der Name (er ist im Klartext
daneben ohnehin lesbar), nie ein Kürzel. Reicht der Platz auch dann nicht, bricht die Zelle
um — in jeder Fensterbreite, nicht erst unter 900 px.

#### „Sichtbar" heißt geometrisch gemessen, nicht „im DOM"

Genau diese Verwechslung machte den Wächter aus #1453 blind. Jede Marke muss in **jeder**
geprüften Auflösung alle fünf Bedingungen erfüllen:

| # | Bedingung | Messung |
|---|---|---|
| 1 | Text nicht beschnitten | `el.scrollWidth <= el.clientWidth + 1` |
| 2 | vollständig innerhalb ihrer Zeile | `boundingBox` der Marke liegt in dem der `.row` |
| 3 | vollständig im Sichtfenster | `x >= 0` und `x + width <= viewport.width` |
| 4 | nicht von einem Nachbarelement überdeckt | `document.elementFromPoint(mitte)` liefert die Marke oder einen Nachfahren |
| 5 | Textinhalt exakt, kein Auslassungszeichen | gerenderter Text `=== ` erwartetes Kürzel, enthält kein `…` |

Zusätzlich je Auflösung: die Seite scrollt nicht horizontal
(`documentElement.scrollWidth <= window.innerWidth + 1`).

#### Auflösungsmatrix (verbindlich)

Vierzehn Breiten, mit Schwerpunkt auf der Bruchzone und beiden Rändern der Media-Query:

| Klasse | Auflösungen |
|---|---|
| Kleine Handys | 320×568 · 375×667 |
| Handys | 390×844 · 414×896 |
| Schmales Fenster / geteilter Bildschirm | 600×900 · 768×1024 |
| **Media-Query-Ränder** | **899×900 · 901×900** |
| **Bruchzone** | **960×900 · 1024×768 · 1180×820** |
| Desktop | 1280×900 · 1440×900 · 1920×1080 |

Geprüft wird gegen den **Worst Case**, nicht gegen eine bequeme Auswahl: „Gefühlte
Nacht-Tiefsttemperatur" (31 Zeichen, längster Name im Katalog) und „Gefühlte Temperatur"
(längste Kurzform `FK FD WC`) müssen beide in der Liste stehen.

## Acceptance Criteria

- **AC-1:** Given eine Telegram-Nachricht eines Trips mit den Größen Luftfeuchtigkeit,
  Bewölkung, Sichtweite, Luftdruck und Nullgradgrenze / When das Briefing gerendert wird /
  Then tragen die Spaltenköpfe der Stundentabelle `HU`, `CT`, `VS`, `HP`, `NL` — also
  dieselben Kürzel, die die SMS für diese Größen sendet.
  - Test: Kern-Test gegen `render_telegram_bubbles()` mit echter Fixture; Kopfzeile
    gegen `SMS_SYMBOL_BY_METRIC` gerechnet, nicht abgetippt.

- **AC-2:** Given der vollständige Metrik-Katalog / When Telegram-Kürzel und
  Register-Kürzel jeder Größe verglichen werden / Then sind sie identisch, außer für die
  Größen der benannten Ausnahmeliste, und jede Ausnahme trägt eine Begründung.
  - Test: Wächter über `get_all_metrics()`; ein neuer Katalog-Eintrag mit abweichendem
    `compact_label` und ohne Ausnahme-Eintrag macht ihn rot.

- **AC-3:** Given die Größen Temperatur und Gefühlte Temperatur / When die
  Telegram-Stundentabelle gerendert wird / Then stehen dort weiterhin `T` und `TF` — nicht
  `D`/`K` bzw. `FK`/`FD`/`WC`, weil die Zelle einen Stundenwert zeigt und keine
  Tagesauswertung.
  - Test: Kern-Test auf die Spaltenköpfe; Gegenprobe, dass die Ausnahme in der Liste steht.

- **AC-4:** Given ein Trip, dessen SMS ein Änderungs-Token enthält (z.B. Luftfeuchtigkeit
  steigt) / When die SMS gerendert wird / Then trägt das Änderungs-Token dasselbe Kürzel
  wie derselbe Wert an anderer Stelle derselben Nachricht — kein Token aus dem alten
  Telegram-System.
  - Test: Kern-Test gegen `format_sms_trip()` mit Änderungsdaten; Token-Kürzel gegen das
    Register gerechnet.

- **AC-5:** Given der Touren-Editor mit geöffnetem Reiter „Wetter-Metriken" / When der
  Nutzer den Bereich „Reihenfolge" ansieht / Then trägt jede Zeile zwei beschriftete
  Marken — „Mail" mit der englischen Fachkurzform und „Kurzform" mit **allen** Kürzeln,
  die SMS und Telegram für diese Größe senden.
  - Test: Playwright-Klickpfad gegen Staging; für „Gefühlte Temperatur" enthält die
    Kurzform-Marke `FK`, `FD` **und** `WC`, für „Nacht-Tiefsttemperatur" genau `N`.

- **AC-6:** Given der Touren-Editor / When eine Größe mit mehreren SMS-Kürzeln angezeigt
  wird / Then erscheinen alle ihre Kürzel, nicht nur das erste.
  - Test: derselbe Klickpfad; zusätzlich Kern-Wächter, der die angezeigte Kürzelmenge je
    Größe gegen `/api/sms-symbols` prüft — die Anzeige darf keine eigene Liste führen.

- **AC-7:** Given die drei Vergleichs-Editoren (Übersicht, Stundenverlauf, Ausblick) /
  When der Bereich „Reihenfolge" angezeigt wird / Then tragen die Zeilen ebenfalls beide
  Marken, und die Kurzform-Marke zeigt das Register-Kürzel — das, was die Vergleichs-SMS
  tatsächlich sendet.
  - Test: Playwright-Klickpfad gegen Staging für mindestens eine der drei Flächen;
    Kern-Wächter (AST) für alle drei, Muster `weather_metric_name_forms_visible.test.ts`.

- **AC-8:** Given der bestehende Wächter `weather_metric_name_forms_visible.test.ts`
  (#1453 AC-7) / When die Marken auf die neue Quelle umgestellt sind / Then ist er grün und
  prüft weiterhin, dass alle vier Editoren die Namensformen tragen.
  - Test: der Wächter selbst, mit an die neue Quelle angepasster Erwartung. Er prüft heute
    **Anwesenheit**, nicht Richtigkeit — genau deshalb blieb der falsche Wert unbemerkt.

- **AC-9:** Given eine Größe ohne SMS-Kürzel / When ihre Zeile angezeigt wird / Then
  erscheint keine leere oder erfundene Kurzform-Marke, sondern gar keine.
  - Test: Kern-Wächter mit einer Größe ohne Registereintrag.

- **AC-10:** Given der Touren-Editor mit einer Metrik-Liste, die „Gefühlte
  Nacht-Tiefsttemperatur" und „Gefühlte Temperatur" enthält / When der Bereich
  „Reihenfolge" in **jeder** der vierzehn Auflösungen der Matrix geladen wird / Then
  erfüllt **jede** Marke **jeder** sichtbaren Zeile alle fünf Sichtbarkeits-Bedingungen.
  - Test: Playwright-Klickpfad gegen Staging, über die Auflösungsliste iterierend, über
    alle Zeilen iterierend — keine Stichprobe. Fehlermeldung nennt Auflösung, Größe,
    Marke und die verletzte Bedingung.

- **AC-11:** Given eine der vierzehn Auflösungen / When der Bereich „Reihenfolge"
  angezeigt wird / Then scrollt die Seite nicht horizontal.
  - Test: derselbe Lauf; `documentElement.scrollWidth <= window.innerWidth + 1`.

- **AC-12:** Given eine Fensterbreite in der Bruchzone (900–1300 px) und eine Zeile, deren
  Name und Marken zusammen breiter sind als die Zelle / When die Zeile gerendert wird /
  Then wird **der Name** gekürzt oder die Zelle bricht um — **nie** eine Marke.
  - Test: gezielt bei 960 px und 1024 px; die Marke trägt ihren vollen Text
    (Bedingung 1 und 5), während der Name gekürzt sein **darf**.
  - Gegenprobe (Pflicht): Entfernt man die Unverkürzbarkeit der Marken aus dem CSS, muss
    dieser Test rot werden. Wird er es nicht, bewacht er nichts.

- **AC-13:** Given der Reihenfolge-Bereich einer der drei Vergleichs-Flächen / When er in
  den vierzehn Auflösungen geladen wird / Then gelten AC-10 und AC-11 dort ebenso.
  - Test: derselbe Klickpfad gegen mindestens eine Vergleichs-Fläche.

- **AC-14:** Given die Ziehgeste im Reihenfolge-Bereich / When nach den Layout-Änderungen
  eine Zeile per Drag umsortiert wird / Then landet sie an der Zielposition und der Stand
  wird gespeichert.
  - Test: Playwright; **Pflicht**, weil S3 in genau dieser Datei die Ziehgeste lautlos
    zerbrochen hat und 2553 Unit-Tests das nicht gesehen haben.

## Non-Goals (bewusst nicht in dieser Scheibe)

- **Die Mail-Kurzformen bleiben** (`Feels`, `Dew`, `Gust`). Sie stehen in einer breiten
  Tabelle mit Platz für lesbare Fachkurzformen; der PO-Entscheid betraf ausdrücklich das
  „extra Telegram Kürzel". Angenommen, nicht erfragt — Widerspruch bei der Freigabe genügt.
- **Kein Umbau der Trip-SMS-Mehrfachkürzel.** Dass die SMS Tagestiefst und -höchst trennt
  (`K`/`D`), ist gewollt und bleibt.
- **Kein Alarm-Kürzel-Ausweis** im Editor. Alarme nutzen `sms_code` und sind nach dieser
  Scheibe deckungsgleich mit der Kurzform — ein eigener Ausweis wäre Rauschen.
- **Kein Aufräumen des toten Codes** um `narrow.py:119` (`_detail_lines`, ohne Aufrufstelle,
  #1741).

## Risks

1. **Nutzersichtbare Änderung an jeder Telegram-Nachricht.** Zwölf Spaltenköpfe heißen
   anders. Das ist der Zweck, muss aber im Issue-Abschluss klar benannt werden.
2. **Acht Testdateien nageln `compact_label` fest** — u.a.
   `test_issue_635_telegram_weather.py`, `test_issue_1001_telegram_bubbles.py`,
   `test_channel_metric_matrix.py`. Erwartungswerte mitziehen, **keine Assertion
   entschärfen**: wo ein Test einen Spaltenkopf prüft, bekommt er den neuen Wert, nicht
   eine gelockerte Prüfung.
3. **Geteilter Baustein mit S3-Vorgeschichte.** In `WeatherV2Reihenfolge.svelte` hat S3 die
   Ziehgeste lautlos zerbrochen (neue Array-Referenz im Markup). Jede Änderung am
   Zeilen-Markup braucht den Klickpfad-Nachweis, dass Ziehen weiter funktioniert.
4. **#1771: kein Playwright-Spec läuft in der CI-Ampel.** Die Klickpfade dieser Scheibe
   müssen im Workflow von Hand gefahren werden und bewachen danach nichts automatisch.
5. **Telegram-Spaltenbreite.** Die Tabelle ist auf schmale Köpfe ausgelegt; `NS24+` ist
   fünf Zeichen. Die Breitenrechnung (`narrow.py:157-160`) passt sich an — zu prüfen ist,
   ob die Zeile dadurch umbricht.
6. **Das Layout-Problem ist vorbestehend, nicht von S4 verursacht** — S4 verschärft es nur.
   Die Reparatur (Abschnitt 4) ist damit Teil dieser Scheibe, nicht ein Nebenbefund: eine
   Legende, deren Zeichen bei manchen Fensterbreiten fehlen, erfüllt ihren Zweck nicht.
7. **Vierzehn Auflösungen × zwei Flächen sind ~28 Browserläufe.** Das kostet Laufzeit im
   Klickpfad-Bündel. Bewusst in Kauf genommen: die bisherigen zwei Standardbreiten haben
   die Bruchzone nachweislich verfehlt.
8. **Die Prüfung testet Geometrie, keine Ästhetik.** Ob eine umgebrochene Zeile *gut
   aussieht*, entscheidet der PO am Bildschirm — der `fresh-eyes-inspector` bewertet
   Screenshots aus der Bruchzone ohne Bug-Kontext.

## Implementation Details

- Kürzel-Vorgabe und Ausnahmeliste gehören in `metric_catalog.py` neben die
  `MetricDefinition` — eine Quelle, nicht zwei.
- Das Frontend führt **keine** eigene Kürzel-Liste; die Kurzform-Marke speist sich aus
  `/api/sms-symbols` (Touren) bzw. dem bereits gelieferten `sms_code` (Vergleich).
  `/api/metrics` braucht dafür **kein** neues Feld.
- Playwright folgt dem S2/S3-Tripel: `<name>.staging.setup.ts` + `.staging.spec.ts` +
  `playwright.<name>.staging.config.ts`.
