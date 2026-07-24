# ADR-0033: Amtliche Warn-Karte zeigt nur betroffene Segmente, kein Vollrouten-Gitter

- **Status:** Akzeptiert
- **Datum:** 2026-07-23
- **Bezug:** Ersetzt die #1233/#1216-Spec-Festlegung (nie als ADR dokumentiert).
  Bundle `bundle:G-mail-darstellung`, Issue #1326a. Spec:
  `docs/specs/modules/warnmail_official_alert_display.md` (AC-1).

## Kontext

Die #1233/#1216-Spezifikation legte fest, dass die amtliche Warn-Karte (Standalone-
Alert-Mail UND der in Abweichungs-Alarme eingebettete Warn-Block) die GESAMTE
Trip-Route zeigt: betroffene Segmente als normale Chips, alle übrigen Segmente
als durchgestrichene Chips (`.seg.off`, `line-through`) plus einem erklärenden
Hinweistext („übrige Strecke frei — keine amtliche Warnung für Segment X, Y,
…"). Diese Festlegung stand nur in den Specs zu #1216/#1233, nie als
eigenständiges ADR.

Bei Trips mit vielen Segmenten (z.B. 63) betraf eine einzelne amtliche Warnung
oft nur 1 Segment — die Karte zeigte dann 62 durchgestrichene Chips, um genau
EIN betroffenes Segment zu markieren (#1326a). Das Signal-Rausch-Verhältnis der
Mail kollabierte: die eigentliche Information („welches Segment ist betroffen")
ging in einem Vollrouten-Gitter unter.

## Entscheidung

Die amtliche Warn-Karte nennt **ausschließlich den betroffenen Umfang** — keine
durchgestrichenen Chips der übrigen, nicht betroffenen Segmente, kein „übrige
Strecke frei"-Hinweistext. `build_official_alert_notices()`
(`src/output/renderers/alert/official_alerts.py`) setzt `free_chips` für den
Trip-Pfad jetzt fest auf `[]` — analog dem Compare-Builder
(`build_compare_official_alert_notices`), der dieses Verhalten bereits hatte
und als Vorbild diente. Redundante Scope-Wiederholungen in Headline/Quelle-Box
(die denselben Umfang wie der einzige Chip nochmals in Prosa nannten) entfallen
ebenfalls (`_scope_matches_sole_chip`).

## Verworfene Alternativen

- **Vollrouten-Gitter beibehalten, nur Chip-Anzahl begrenzen** — löst das
  Signal-Rausch-Problem nicht grundsätzlich, nur graduell; bei 63 Segmenten
  bliebe die Karte weiterhin dominiert von "frei"-Information statt der
  eigentlichen Warnung.
- **Zusammenfassung „62 von 63 Segmenten frei" statt Einzel-Chips** — weiterhin
  eine Aussage über NICHT betroffene Fläche, die die Karte nicht treffen muss;
  die Karte soll ausschließlich sagen, was zutrifft.

## Konsequenzen

- **Positiv:** Die Warn-Karte skaliert unabhängig von der Trip-Segmentzahl —
  eine Warnung für 1 von 63 Segmenten sieht identisch knapp aus wie eine für 1
  von 4 Segmenten.
- **Negativ / Preis:** Nutzer sehen nicht mehr explizit, WELCHE Segmente
  garantiert frei sind — nur, welche betroffen sind (Umkehrschluss weiterhin
  möglich, aber nicht mehr explizit ausgeschrieben).
- **Folgepflichten:** Neue Warn-Karten-Änderungen dürfen `free_chips` im
  Trip-Pfad nicht wieder befüllen, ohne dieses ADR abzulösen. Der
  Compare-Pfad (`build_compare_official_alert_notices`) war von dieser
  Umkehr nicht betroffen (setzte `free_chips=[]` bereits vorher).
