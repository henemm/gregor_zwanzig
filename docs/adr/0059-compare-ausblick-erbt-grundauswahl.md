# ADR-0059: Der 3-Tages-Ausblick verhält sich wie ein Kanal — Grundauswahl statt eigener Liste (löst ADR-0053 Punkt 1 ab)

- **Status:** Akzeptiert
- **Datum:** 2026-08-21
- **Bezug:** Issue #1848 Scheibe A3, Spec
  `docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md` (AC-1 bis
  AC-12), PO-Freigabe 2026-08-21 („go"). **Löst ADR-0053 Punkt 1** ab (dort:
  Ausblick und Stundenverlauf bleiben bewusst global); **schreibt ADR-0050**
  (Metrik-Kaskade, Regeln 1–4) auf die Ausgabefläche „Ausblick" fort — für
  Trip bereits durch ADR-0055 geschehen, hier für den **Ortsvergleich**
  nachgezogen; **ergänzt den „Divergenz zum Ortsvergleich"-Abschnitt von
  ADR-0055**, dessen beschriebene Divergenz mit dieser Entscheidung entfällt.
  Der Stundenverlauf (`hourly_metrics`) bleibt von dieser Entscheidung
  unberührt und weiterhin global ohne Kaskadenbindung (ADR-0053 Punkt 1 gilt
  dafür unverändert fort).

## Kontext

ADR-0053 (2026-08-13) hatte für den Ortsvergleich bewusst nur die
**Übersichtstabelle** an eine kanal-eigene Metrikauswahl gebunden. Ausblick
und Stundenverlauf blieben dort ausdrücklich global — als Scheiben-Schnitt
begründet, nicht als fachliche Abgrenzung:

> „Ausblick (`outlook_metrics`) und Stundenverlauf (`hourly_metrics`) bleiben
> in dieser Scheibe bewusst global — eigene, getrennt gespeicherte
> Auswahllisten ohne Kanal-Ebene (Scheiben-Schnitt, kein Widerspruch zur
> Kaskaden-Zusage aus ADR-0050, weil diese sich auf Kanäle bezieht, nicht auf
> Ausgabeflächen)."

„Global" bedeutete dabei nicht nur „ohne Kanal-Ebene", sondern auch: der
Ausblick führte im Frontend eine **zweite, unabhängige Auswahl** — eine
Kästchenliste mit bis zu 23 Einträgen (`CompareOutlookLayoutControls.svelte`)
neben der Grundauswahl der Fläche, ohne dass diese beiden Auswahlen
irgendeine Beziehung zueinander hatten. Für den **Trip** war diese
Unabhängigkeit bereits mit ADR-0055 (2026-08-14) beendet worden — dort bindet
der Ausblick sich an die Grundauswahl und darf nur abwählen. ADR-0055 hielt
die entstandene Asymmetrie im Abschnitt „Divergenz zum Ortsvergleich"
ausdrücklich fest, als bewusste Folge des damaligen Zuschnitts, nicht als
Auslassung.

Gemessen am Stand vor dieser Scheibe (Issue #2029): **13 von 23** angebotenen
Kästchen im Trip-Ausblick waren bereits vor A1/A2 wirkungslos — das exakte
Symptom, das ADR-0053 selbst im Kontext-Abschnitt als „Attrappe" verwirft.
Für den Ortsvergleich lag dieselbe Fehlerklasse strukturell vor, weil die
Kästchenliste unabhängig von der Grundauswahl der Fläche befüllt werden
konnte.

## Entscheidung

**1. Der Ausblick bekommt in beiden Flächen (Trip UND Ortsvergleich) exakt
das Bedienverhalten eines Kanals.** Keine eigene Metrik-Auswahl mehr — die
Grundauswahl der Fläche ist die Ausgangsmenge (Maximum), aus der über den
„Aus"-Knopf abgewählt und über die „Aus"-Gruppe zurückgeholt wird
(`WeatherV2Reihenfolge` mit `offColumns`/`onRestore`,
`splitChannelMetricsForDisplay()` — dieselbe Funktion wie die Kanal-Reiter,
kein zweiter Algorithmus). Die zweite Kästchenliste
(`CompareOutlookLayoutControls.svelte`, `{#each groupCompareCatalog(catalog)}`)
entfällt ersatzlos.

**Damit ist ADR-0053 Punkt 1 für den Ausblick abgelöst.** Der
Stundenverlauf bleibt unberührt und trägt weiterhin eine eigene, globale
Liste ohne Kaskadenbindung — ADR-0053 Punkt 1 gilt für ihn unverändert fort.

**Damit entfällt auch die in ADR-0055 („Divergenz zum Ortsvergleich")
beschriebene Asymmetrie.** Trip- und Compare-Ausblick verhalten sich seit
dieser Scheibe **identisch**: beide erben die Grundauswahl ihrer Fläche
(Trip: `UnifiedWeatherDisplayConfig.allowed_metric_ids_for_report_type()`;
Compare: `resolve_enabled_metrics(active_metrics)`), beide dürfen nur
abwählen, beide nutzen dieselbe geteilte Editor-Komponente. Der Code war für
beide Flächen bereits geteilt (`compare_outlook_metric_ids.py`,
`CompareOutlookLayoutControls.svelte` mit `context="route"|"vergleich"`);
offen war allein die Semantik — wie in ADR-0055 vorausgesagt: „Wer den
Ortsvergleich später nachziehen will: … Eine Vereinheitlichung muss ihn
**hineinziehen**, nicht danebenlegen." Genau das leistet diese Scheibe.

**2. `null` bedeutet „ganze Grundauswahl", nicht „nichts".** Anders als bei
der Übersichtstabelle (ADR-0053 Punkt 4: `null` = kein Maximum, `[]` =
bewusste Leerauswahl) trägt `outlook_metrics` seit dieser Scheibe dieselbe
Drei-Werte-Semantik wie beim Trip-Ausblick (ADR-0055 Nachtrag 2026-08-20,
Punkt 2): Feld fehlt/`null` → volle Grundauswahl; Schnitt gegen die
Grundauswahl ergibt **nichts** → volle Grundauswahl **mit Protokoll-Warnung**
(AC-10) statt eines verschwundenen Blocks; gefüllt → die geschnittenen
Größen. Der stille Totalausfall — vor dieser Scheibe fiel der Ausblick-Block
bei einem Totalschnitt kommentarlos weg — wird damit strukturell
unmöglich.

**3. AC-13 aus `fix_1719_s3_aus_ist_ein_zustand.md` ist für den
Ausblick-Mountpunkt abgelöst.** Jene Spec verlangte, dass sich die drei
Vergleichs-Einbettungen der Reihenfolge-Liste (Übersicht, Ausblick,
Stundenverlauf) „exakt wie vor dieser Scheibe" verhalten — ohne
`offColumns`/`onRestore`. Die dortige Begründung („der Ausblick hat bereits
einen funktionierenden Rückweg über die Checkbox darüber") entfällt mit dem
Wegfall ebendieser Checkbox-Liste (Punkt 1 oben). Übersicht und
Stundenverlauf bleiben von AC-13 unverändert erfasst — nur der
Ausblick-Mountpunkt wechselt die Seite. Der AST-Wächter
`compare_outlook_metric_selection_structure.test.ts` prüft seit dieser
Scheibe das umgedrehte Verhalten (`offColumns`/`onRestore` MÜSSEN am
`WeatherV2Reihenfolge`-Aufruf des Ausblicks gesetzt sein).

**4. Der Gewitter-Zellenbau wandert in einen geteilten Baustein
(`thunder_branch.py`).** Kein Architektur-Entscheid im engeren Sinn, aber
Voraussetzung für Punkt 1: der feste Sieben-Spalten-Zweig löst als
Normalfall ab, trug bislang aber den einzigen vollständigen
Gewitter-Zellenbau (Onset-Uhrzeit, tragende Zutat, Hagel-Zusatz). Ohne
Auslagerung hätte jede Tour diese Details beim Wegfall des festen Zweigs
verloren. Details: `docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md`,
Changelog-Eintrag 2026-08-21 (Implementierung).

## Verworfene Alternativen

- **Nur den Trip-Ausblick lassen, Compare unangetastet.** Verworfen: hätte
  die von ADR-0055 selbst benannte Divergenz dauerhaft festgeschrieben, statt
  sie — wie dort vorausgesagt — durch Hineinziehen in die geteilte Auflösung
  zu beenden. Der PO-Auftrag zu #1848 verlangte die Kopplung ausdrücklich für
  **beide** Flächen.
- **Kanal-Ebene für den Ausblick gleich mitliefern (Kästchenliste behalten,
  zusätzlich nach Kanal filtern).** Verworfen: SMS und Premium-SMS erreichen
  den Ausblick baulich nicht (dasselbe Argument wie ADR-0055 Punkt 2 für den
  Trip); eine Kanal-Ebene für effektiv zwei Kanäle (E-Mail, Telegram) hätte
  Bedienfläche, Speicherweg und Auflösung ohne angefragten Nutzen verdoppelt.
- **`[]` weiterhin als „nichts anzeigen" behandeln (kein Totalausfall-Schutz).**
  Verworfen: das war exakt der gemessene stille Fehler (AC-10), den diese
  Scheibe beheben sollte — ein Ausblick, der beim Schnitt auf die leere Menge
  kommentarlos verschwindet, ist von einem Darstellungsfehler nicht
  unterscheidbar.

## Konsequenzen

- **Positiv:** Ausblick, Übersicht-Kanal-Layout (ADR-0053) und Trip-Ausblick
  (ADR-0055) folgen jetzt derselben Regel (ADR-0050, Regeln 1–4) über beide
  Flächen hinweg — eine einzige Kaskaden-Semantik statt dreier Varianten.
  Die Bestandswächter aus #1719 S3 (`splitChannelMetricsForDisplay()`) und
  #1848 A2 (Kennungsformat) werden ohne Zweitimplementierung wiederverwendet
  (AC-12, Block E der Spec).
- **Negativ / Preis:** Die Ausblick-Tabelle wird für bestehende Touren mit
  einer größeren Grundauswahl breiter als bisher — gewollte Folge, über die
  „Aus"-Knöpfe jederzeit korrigierbar (Known Limitations der Spec).
- **Getragene Grenze:** Ein reines Nachtgewitter ist in der Vorschau nicht
  von „gar kein Gewitter" zu unterscheiden — die Vorschau ist strikt auf das
  Tagesfenster verengt (dehnt den bestehenden Entscheid aus `fix_1841`
  AC-3 auf alle Touren aus, dreifach PO-bestätigt 2026-08-14/2026-08-21;
  kein neues ADR, da der bestehende Entscheid angewandt, nicht geändert
  wird). Tages-Briefing, Stundenverlauf und Alarme führen den
  Tag/Nacht-Split unverändert weiter.
- **Folgepflicht:** Der Stundenverlauf bleibt weiterhin ohne Kaskadenbindung
  (ADR-0053 Punkt 1 gilt für ihn fort) — eine Erwartung „das funktioniert
  doch überall wie beim Ausblick" ist für den Stundenverlauf falsch und muss
  bei jeder Anfrage dazu richtiggestellt werden, bis eine eigene Folge-Scheibe
  das ändert.
