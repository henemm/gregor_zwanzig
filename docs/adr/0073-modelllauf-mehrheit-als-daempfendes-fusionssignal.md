# ADR-0073: Modellauf-Mehrheit ist das erste Gewitter-Fusionssignal, das dämpfen darf

- **Status:** Akzeptiert
- **Datum:** 2026-09-19
- **Bezug:** GitHub-Issue #1983 (Gewitter S6, Epic #1419), Spec
  `docs/specs/modules/feat_1983_gewitter_modelllauf_mehrheit.md`, PO-Entscheid „beides, mit
  Schwellen" (2026-09-19), ergänzt ADR-0025 (eine Gewitter-Quelle für alle Kanäle)

## Kontext

Die Gewitter-Stufen-Fusion (`thunder_level_from_signals()` /
`app.thunder_scale.union_of_max_carriers`, ADR-0025) kannte bis zu diesem Ticket genau eine
Wirkrichtung: Jedes der vier Einzelsignale (Wettercode, Blitzdichte, CAPE, Blitzpotenzial)
trägt entweder gar nicht bei (`None`, „keine Aussage") oder hebt die fusionierte Stufe auf sein
eigenes Ergebnis an. Eine Dämpfung existierte nur **innerhalb** eines einzelnen Signals (CIN
dämpft CAPE, ADR-0071) — nie über die Fusionsgrenze hinweg, nie ausgehend von einem Signal auf
ein anderes.

Issue #1983 verdrahtet das im Konzeptdokument (`docs/features/gewitter-gesamtkonzept.md`,
Abschnitt 2.1) seit 2026-08-02 als Idee geführte, aber nie umgesetzte fünfte Signal
„Anteil der Ensemble-Modellläufe mit Gewittercode" (`weather_code` 95/96/99 über ICON-EPS +
GEFS, ohne ECMWF, `_fetch_ensemble_spread`). Der PO-Auftrag benannte dafür ausdrücklich **beide
Richtungen mit Schwellen** — nicht nur die im Konzept ursprünglich skizzierte reine Anhebung:
Grund ist die dokumentierte KHW-Überprognose (#2181/#2206: 9 von 13 Tagen „hoch" gegen 1 realen
Gewittertag). Eine reine Anhebung hätte diese Überprognose verstärkt statt bekämpft.

Damit entsteht zum ersten Mal ein Signal, das die Ergebnisse der vier anderen, unabhängig
berechneten Signale **nachträglich senkt** (< 10 % Member-Anteil ⇒ Stufe um genau eine Stufe
gedämpft, nie unter `NONE`, außer der Punkt ist radar-bestätigt). Das ist eine neue
Semantik-Klasse an der Fusion, die dokumentiert werden muss, bevor ein künftiges sechstes
Signal denselben Mechanismus kopiert oder — schlimmer — fälschlich annimmt, die Fusion sei
weiterhin rein additiv (max-only, wie ADR-0025 sie beschreibt).

## Entscheidung

1. **Die Gewitter-Fusion bleibt im Kern additiv (max-only, ADR-0025 unverändert gültig):** Vier
   Signale können weiterhin nur anheben oder fehlen. `modelllauf` fügt sich als **fünftes**
   Signal in dasselbe Muster ein — bei ≥ 60 % Gewittercode-Anteil hebt es wie jedes andere
   Signal auf `HIGH` (über die bestehende Aggregationsregel
   `app.thunder_scale.union_of_max_carriers`, keine zweite Fusionsregel).
2. **Zusätzlich — und das ist die eigentliche Neuerung dieser ADR — darf `modelllauf` als
   einziges Signal die bereits fusionierte Stufe nachträglich senken:** bei < 10 %
   Gewittercode-Anteil wird das fusionierte Ergebnis um genau eine Ordinalstufe gedämpft
   (`HIGH→MED→LOW→NONE`, Trägerliste bleibt erhalten außer bei Sturz auf `NONE`, dann geleert).
   10–59 % bleibt neutral (kein drittes, unbegründetes Band).
3. **Die Dämpfung ist an eine feste Sicherheits-Invariante gebunden:** Ein Datenpunkt, dessen
   Stufe durch den Radar-Override (`"radar"` in `thunder_level_signals`) auf eine Beobachtung
   zurückgeht, wird **nie** gedämpft — Beobachtung schlägt Modell. Eine Anhebung durch
   `modelllauf` bleibt an einem radar-bestätigten Punkt weiterhin möglich, weil sie dieselbe
   Invariante nicht verletzt (die Stufe wird dadurch nicht unter die Beobachtung gesenkt).
4. **Die Dämpfung wirkt als eine für alle Ordinalstufen gleiche, monotone Abbildung** auf das
   bereits fusionierte Maximum, nicht als Wiederholung der Fusion auf gedämpften
   Einzelsignalen — mathematisch gleichwertig (`f(max(S)) = max(f(s) für s ∈ S)` für ein
   monotones `f`), ohne die bestehende Aufrufreihenfolge (Fusion je Segment beim Wetterabruf,
   Ensemble-Anreicherung danach je Trip/Aufruf, #288) umzubauen.
5. **`modelllauf` ist ausdrücklich kein Ersatz für eine Gewitter-Wahrscheinlichkeits-Achse.**
   Der rohe Anteil wird zwar in `dp.thunder_probability_pct` geschrieben (vorbereitetes Feld
   aus #1474 AC-10), aber ausschließlich als internes Fusionssignal verwendet — kein Renderer
   zeigt ihn als Prozentzahl. Das Konzeptdokument (`gewitter-gesamtkonzept.md` Abschnitt 2.1)
   hatte genau diesen Anteil 2026-08-02 als **nutzersichtbare** zweite Achse verworfen (Messung
   „0,04 % Treffer in 53.760 Werten" — zu selten für eine belastbare Prozentanzeige). Diese
   ADR widerspricht dieser Ablehnung nicht: Sie gilt weiterhin für eine angezeigte
   Wahrscheinlichkeit. Als **binäres** Fusionssignal mit weit auseinanderliegenden,
   konservativen Schwellen (≥ 60 % / < 10 %) ist derselbe Rohwert dagegen tragfähig genug.

## Verworfene Alternativen

- **Dämpfung als Modifikator innerhalb von `_signal_levels()`** (Ticket-Vorgabe, Muster wie
  CIN dämpft CAPE) — am tatsächlichen Aufrufpfad unerreichbar: Der Ensemble-Abruf läuft erst
  **nach** der Fusion (`_enrich_ensemble_for_trip`, einmal je Trip), die vier rohen
  Einzelsignale liegen zu diesem Zeitpunkt nicht mehr vor, nur noch das bereits gebildete
  Maximum `dp.thunder_level`. Ein Parameter in `_signal_levels()` wäre ohne Umbau der
  „1 Abruf/Trip"-Struktur (#288) unerreichbar — außerhalb des Scopes dieses Tickets. Details
  in der Spec, Abschnitt „Architektur-Befund".
- **Reine Anhebung, wie im Ticket ursprünglich benannt** — hätte die dokumentierte
  KHW-Überprognose (#2181/#2206) verstärkt statt bekämpft. Verworfen per PO-Entscheid
  „beides, mit Schwellen" (2026-09-19).
- **Dämpfungsschwelle höher als 10 % ansetzen** (z. B. 30 %) — echte Gewittertage zeigen in
  unterdispersiven globalen Ensembles (ICON-EPS ~26 km, GEFS ~25 km) typischerweise NIEDRIGE
  Member-Anteile; eine zu hohe Schwelle hätte das Über-/Unterprognose-Problem nur in die
  andere Richtung verschoben. Herleitung: Spec, Abschnitt „Schwellen-Herkunft".
- **`modelllauf` als nutzersichtbare Prozent-Metrik einführen** — verworfen, s. Entscheidung 5.
  Eine Eichung an echten Daten ist ohnehin erst möglich, sobald `forecast_capture.py` den
  Member-Anteil mitschneidet (frühestens Saison 2027, Known Limitation der Spec).

## Konsequenzen

- **Positiv:** Die dokumentierte KHW-Überprognose bekommt einen ersten, gegenläufig wirkenden
  Mechanismus, ohne die bestehende additive Fusion (ADR-0025) für die anderen vier Signale
  anzutasten. Der Radar-Override bleibt strukturell unverändert vorrangig.
- **Negativ / Preis:** Die Gewitter-Fusion ist ab jetzt **nicht mehr rein additiv** — wer
  ADR-0025 liest, ohne diese ADR zu kennen, geht von einer falschen Invariante aus. Die
  Wirkung auf die 9 überprognostizierten KHW-Tage bleibt unbelegt, solange kein
  Member-Mitschnitt existiert (Known Limitation 2 der Spec). Die drei Schwellen (60 %, 10 %,
  20 Member) sind unkalibriert, wie bei jeder anderen unbelegten Schwelle im Projekt
  ausdrücklich als solche gekennzeichnet.
- **Folgepflichten:**
  - Ein künftiges sechstes Fusionssignal, das ebenfalls dämpfen soll, prüft zuerst, ob es die
    hier festgelegte Radar-Ausnahme (Entscheidung 3) und die Ein-Stufen-Begrenzung
    (Entscheidung 2) übernehmen kann, statt einen dritten Mechanismus zu erfinden.
  - `dp.thunder_probability_pct` bleibt so lange ohne eigenen Renderer-Anschluss, bis eine neue
    ADR das ausdrücklich ändert (Entscheidung 5) — ein Renderer, der die Zahl anzeigt, ohne
    diese ADR abzulösen, ist ein Review-Befund.
  - `fetch_forecast(enrich_ensemble=True)` (`trip_forecast.py`, `services/forecast.py`) bleibt
    von `modelllauf` unberührt (nur Typanpassung an `EnsembleHourStats`, keine neue Semantik) —
    s. Known Limitation 1 der Spec.
