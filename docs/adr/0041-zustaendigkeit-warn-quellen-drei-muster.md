# ADR-0041: Zuständigkeit einer Warn-Quelle wird nach Art des Endpunkts bestimmt — nicht einheitlich über eingecheckte Geometrie

- **Status:** Akzeptiert (PO-Entscheidung 2026-08-01)
- **Datum:** 2026-08-01
- **Bezug:** Issue #1397 (Defekt 2, „ZAMG-Zuständigkeit ist ein Radar-Rechteck"), Issue #1400, Issue #1445 S1/S3, Spec `docs/specs/modules/fix_1397_s4_it_grenze.md`, ADR-0018 (Fail-soft in Warnquellen)

## Kontext

Jede amtliche Warn-Quelle beantwortet über `covers(lat, lon)` die Frage „bin ich für diesen Ort zuständig?". Historisch benutzten **alle** Quellen dafür ein **Wetter- oder Radar-Gitter-Rechteck** aus `radar_service.py` — also den Ausschnitt, für den Vorhersagedaten vorliegen, nicht das Gebiet, für das die Warnbehörde spricht. Das ist der falsche Datentyp für diese Frage.

Die Folgen sind mehrfach in Produktion gemessen worden:

| Vorfall | Wirkung |
|---|---|
| #1397 Defekt 2 (Juli) | Die INCA-Box reicht nach Südtirol, Bayern, Slowenien. Der koordinatenbezogene ZAMG-Endpunkt antwortet dort mit 404, was als **Ausfall** zählte ⇒ „Amtliche Warnungen aktuell nicht abrufbar", obwohl die Quelle schlicht nicht zuständig war. Dazu 308 Fehlabrufe an einem Tag. |
| #1400 (Juli) | Die AROME-Box von Vigilance umfasst Mailand, Turin, Genf, Barcelona; zusammen mit einem bedingungslosen Zentroid-Rückfall bekamen diese Orte **französische** Warnungen zugeschrieben — Mailand die von Nizza. |
| #1397 S4 (2026-08-01) | Der neue italienische Feed-Adapter aus #1445 brachte dieselbe Krankheit zurück: 39 Punkte einer Grenztour lösten einen grundlosen Ausfallhinweis aus, dazu einen Dauer-Alarm im Betriebsmonitor. |

Der letzte Fall ist der lehrreichste: Das Muster kehrt bei **jedem neuen Quellen-Adapter** zurück, weil die Radar-Konstanten griffbereit im selben Repository liegen und ein Rechteck die naheliegende erste Fassung ist.

Naheliegend wäre gewesen, aus #1397 die Regel „jede Quelle prüft gegen eine eingecheckte Gebietsgeometrie" abzuleiten — so stand die Forderung auch wörtlich im Issue. Zwei Messungen desselben Tages sprechen dagegen: Eingecheckte Geometrie **driftet**. #1434 (DPC-Zonen-Neuschnitt) und #1397 S4 (italienische Zonenkarte an der Staatsgrenze) sind beides Fehlerbilder, die *durch* eine eingecheckte Karte entstanden, nicht trotz ihr.

## Entscheidung

**Die Zuständigkeitsprüfung richtet sich nach der Art des Endpunkts. Drei Muster, in dieser Rangfolge:**

**Muster A — die Quelle kennt ihre Fläche lokal ⇒ echte Geometrie prüfen.**
Anzuwenden, wenn die Flächen ohnehin im Repository liegen und fachlich gebraucht werden.
*Vorbild:* `massif_closure.covers()` → `massif_at(lat, lon) is not None`; `meteoalarm_feed.covers()` (IT) → `_zone_for_point(...) is not None`.

**Muster B — koordinatenbezogener Fremdendpunkt ⇒ seine eigene Auskunft auswerten.**
Wenn der Dienst je Koordinate antwortet und „nicht zuständig" von „ausgefallen" unterscheidbar meldet, ist **seine** Antwort maßgeblich, nicht unsere Nachbildung seines Hoheitsgebiets. `covers()` darf dann ein grober, netzfreier Vorfilter bleiben; die Feinentscheidung fällt in `fetch()`.
*Vorbild:* `geosphere_warn` — INCA-Bbox als Vorfilter, `not_covered_statuses={404}` als eigentliche Zuständigkeitsantwort. Ebenso `meteoalarm_feed` (AT) über die ZAMG-Gemeindenummer.

**Muster C — Rechteck mit nachgelagertem stillem Filter ⇒ zulässig, solange nachweislich kein Ausfall daraus entsteht.**
Ein zu breites `covers()` ist unschädlich, wenn `fetch()` den Punkt still verwirft (`return []` **ohne** `mark_fetch_incomplete()`), denn dann entsteht kein `unavailable`.
*Vorbild:* `dpc.covers()` — DPC-Bbox, aber `_zone_at() is None → return []`. Am 2026-08-01 gegengeprüft: null Drift-Meldungen bei denselben Grenzpunkten, die den Feed-Adapter zum Fehlalarm brachten.

**Verbindliche Prüffrage bei jeder neuen oder geänderten Warn-Quelle:** *Kann ein Punkt, für den wir nicht zuständig sind, einen Ausfall-Hinweis auslösen?* Ist die Antwort ja, ist Muster A oder B zwingend. Ist sie nein, genügt C.

Die Rechteck-Konstanten aus `radar_service.py` bleiben als **Vorfilter** erlaubt — als **Zuständigkeitsnachweis** sind sie es nicht.

## Verworfene Alternativen

- **Einheitlich eingecheckte Staatsgrenzen für alle Quellen** (die wörtliche Forderung aus #1397 Defekt 2). Verworfen: erzeugt eine weitere pflegebedürftige Geodatei je Land, deren Veralten genau die Fehlerklasse ist, die #1434 und #1397 S4 verursacht hat. Für ZAMG käme hinzu, dass wir das österreichische Staatsgebiet nachbilden würden, während der Dienst selbst jederzeit verbindlich Auskunft gibt.
- **Zuständigkeit generell erst in `fetch()` entscheiden**, `covers()` immer `True`. Verworfen: `base.py` zählt jede abdeckende Quelle in `covering`, und ein Fetch je Quelle und Punkt kostet Zeit und Fremdlast — der netzfreie Vorfilter hat seinen Zweck.
- **Zentroid-/Nachbarschafts-Rückfall bei Nichttreffer** („nächstgelegenes Gebiet gewinnt"). Verworfen mit #1400: liefert für jeden Punkt der Erde ein Ergebnis und schreibt Orten fremde Warnungen zu. Ein Nichttreffer muss `None` bleiben dürfen.

## Konsequenzen

- **#1397 Defekt 2 gilt über Muster B als erfüllt.** Die wörtliche Forderung „`covers()` bildet das echte Staatsgebiet ab" wird damit **bewusst nicht** umgesetzt; `geosphere_warn.covers()` behält die INCA-Bbox als Vorfilter. Nutzersichtbar ist der Defekt behoben (kein falscher Ausfallhinweis), der Fehlverbrauch fiel von 308 auf 23 Abrufe/Tag gegen einen Dienst **ohne** Mengenbegrenzung.
- **Der Restverbrauch ist akzeptiert, nicht übersehen.** Muster B verhindert Fehlabrufe nicht vollständig, es dämpft sie über den Cache der „nicht zuständig"-Antwort. Wird dieser Rest je teuer — etwa weil ein Dienst kontingentiert wird —, ist das ein neuer Befund, kein Rückfall.
- **Zwei Quellen sind noch ungeprüft:** `vigilance` und `meteo_forets` benutzen weiterhin AROME-Rechtecke. In #1397 ausdrücklich als „mitprüfen, nicht zwingend mitfixen" geführt; nach diesem ADR ist die offene Frage konkret: Können sie für einen nicht-französischen Punkt einen Ausfall-Hinweis auslösen? Wird als eigener Befund verfolgt, nicht in #1397.
- **Jeder neue Warn-Quellen-Adapter** beantwortet die Prüffrage oben in seiner Spec. Das ist die Gegenmaßnahme gegen den in #1397 S4 belegten Rückfall.
- ADR-0018 (Fail-soft) bleibt unberührt: Auch unter Muster B wirft `fetch()` nie, sondern liefert `[]`.
