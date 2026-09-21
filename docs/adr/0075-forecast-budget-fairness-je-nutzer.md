# ADR-0075: Das Open-Meteo-Tagesbudget bleibt ein globaler Topf — der Zähler je Nutzer entscheidet nur, wen eine erreichte Schwelle trifft

- **Status:** Akzeptiert
- **Datum:** 2026-09-21
- **Bezug:** GitHub-Issue #2387 (Scheibe S1 von #2150, Epic #2138 Multi-User), Spec
  `docs/specs/modules/forecast_budget_je_nutzer.md`, ergänzt ADR-0029 (Open-Meteo als
  Standard-Provider) und ADR-0003 (Mandantentrennung), Präzedenz ADR-0070 (Wartebudget je
  Nutzeraufruf)

## Kontext

`ForecastBudgetGate` (`src/services/forecast_budget.py`, seit #1329 Scheibe C+) zählt
ausgelöste Open-Meteo-Abrufe in **einem einzigen, für alle Nutzer geteilten** Tagestopf
(`<data_root>/diagnostics/forecast_budget.json`, `DAILY_BUDGET = 9000`). Erreicht der
globale Zähler 80 % (`POLLING_THRESHOLD`) bzw. 95 % (`BRIEFING_ONLY_THRESHOLD`), wird
**jeder** Nutzer gedrosselt — auch der, der an dem Verbrauch keinen Anteil hat. Ein
Vielverbraucher schaltet damit die Alarm-Prüfung aller anderen ab.

Seit Epic #2138 ist Gregor Zwanzig mandantenfähig; genau dieser Effekt ist damit keine
theoretische Randerscheinung mehr, sondern der Regelfall bei wachsender Nutzerzahl. Das
Ticket #2387 verlangt daher eine Zuordnung des Verbrauchs zum Verursacher — ohne den
Kontoschutz gegenüber dem Anbieter aufzugeben.

Zugleich gibt es einen Verweisfehler im Bestand: `forecast_budget.py:38` beruft sich auf
„ADR-0032"; `docs/adr/0032-*.md` behandelt aber die Wizard-Abschaffung. Ein ADR zum
Budget-Gate wurde nie angelegt. Dieses Dokument schließt beide Lücken.

## Entscheidung

1. **Der globale Topf bleibt der alleinige Kontoschutz gegenüber Open-Meteo.** Ein Zähler je
   Nutzer mit je vollem `DAILY_BUDGET` ist ausdrücklich verworfen — er hätte bei N Nutzern
   das N-fache Budget zur Folge und genau den Kontoschutz aufgehoben, den das Gate leisten
   soll. Der Nutzer-Topf (`data/users/<user_id>/diagnostics/forecast_budget.json`) ist ein
   reiner **Verteilungsschlüssel**, kein zweites Budget.

2. **Das Drosselungsmodell ist dreistufig.** `allow(priority)` entscheidet in dieser
   Reihenfolge:
   - **Stufe 0** — globaler Anteil unter der Schwelle der Priorität: niemand wird gedrosselt
     (Bestandsverhalten, unverändert).
   - **Stufe 2** — globaler Anteil ≥ 100 % von `DAILY_BUDGET`: jede Priorität außer
     `user_briefing` wird gedrosselt, **unabhängig** vom fairen Anteil. Diese Prüfung steht
     bewusst **vor** Stufe 1, damit ein unlesbarer Nutzer-Topf den harten Kontoschutz nicht
     aufweichen kann.
   - **Stufe 1** — Schwelle erreicht, aber unter 100 %: gedrosselt wird nur, wer mit seinem
     eigenen Tagesverbrauch **über** seinem fairen Anteil `DAILY_BUDGET / max(N, 1)` liegt.
     `N` ist die Größe der Menge der heute aktiven Nutzer, geführt als zusätzliches Feld
     `active_users` in der globalen Datei und demselben UTC-Tagesreset unterworfen wie der
     Zähler selbst.

   `user_briefing` bleibt in **allen drei** Stufen ungedrosselt (Produktgrundsatz, unverändert
   seit #1329).

3. **Fail-open gilt auch je Nutzer.** Ein unlesbarer Nutzer-Topf (kaputtes JSON, IO-Fehler)
   oder ein Lock-Timeout gilt als „nicht überschritten" — nie als Drosselungsgrund. Der
   verschluckte Lesefehler wird als `WARNING` des Gate-Loggers sichtbar, damit der Weg im
   Betrieb beobachtbar bleibt. Das ist die Fortschreibung der Fail-open-Semantik, die die
   Klasse seit #1329 für den globalen Zähler trägt.

4. **Die Provider-Schicht bleibt bewusst nutzerfrei.** `thunder_enrichment.py` über
   `src/providers/openmeteo.py` bucht weiterhin **unattributiert** in den globalen Topf, ohne
   Eintrag in einem Nutzer-Topf und ohne Eintrag in `active_users`. Eine Durchreichung der
   Kennung durch diese Schicht würde die Schichtung brechen und keinen Unterschied im
   Drosselungsverhalten erzeugen (die Priorität dort ist immer `user_briefing`).

   Technisch ist `user_id` deshalb ein **Pflichtparameter ohne Default**, der `None`
   ausdrücklich zulässt: `ForecastBudgetGate()` bricht laut, `ForecastBudgetGate(None)` ist
   die sichtbare, geschriebene Entscheidung „unattributiert". Das ist der entscheidende
   Unterschied zu einem Ersatzwert wie `"default"`, der den Verbrauch einem **fremden Konto**
   zuschriebe (ADR-0003). Eine unattributierte Instanz kann folgerichtig keinen fairen Anteil
   haben und fällt in Stufe 1 auf das Bestandsverhalten zurück — **drosseln**, nie eine
   Befreiung: ein Aufruf ohne Kennung darf nie mehr dürfen als einer mit Kennung.

5. **Der Go-Status-Endpunkt bleibt auf Aggregate beschränkt.** `/api/scheduler/status` ist
   ohne Anmeldung erreichbar; Nutzerkennungen dürfen dort nie erscheinen. `forecastBudgetFile`
   (`internal/scheduler/forecast_budget_health.go`) deklariert `active_users` nicht, das Feld
   fällt beim Unmarshal weg — es gibt bewusst **keine** Strukturänderung auf der Go-Leseseite.
   Ein Schutztest (`forecast_budget_user_privacy_test.go`) friert diese Eigenschaft ein, damit
   ein späteres „active_users für die Beobachtbarkeit durchreichen" an einem Test scheitert
   statt still Kennungen zu veröffentlichen.

6. **`DAILY_BUDGET`, `POLLING_THRESHOLD` und `BRIEFING_ONLY_THRESHOLD` bleiben wörtlich an
   ihrer bisherigen Stelle** (`forecast_budget.py`, Klassenkopf) stehen — nicht umbenannt,
   nicht verschoben, nicht in eine andere Datei gezogen. Grund:
   `TestForecastBudgetConstantsMatchPython` (`internal/scheduler/forecast_budget_health_test.go`)
   liest den Python-Quelltext zur Laufzeit und wird rot, sobald eine Konstante wandert. Der
   faire Anteil wird zur **Laufzeit** aus ihnen abgeleitet und lebt als eigene Methode
   **neben** ihnen, nie an ihrer Stelle.

## Verworfene Alternativen

- **Volles `DAILY_BUDGET` je Nutzer.** Einfachste Fairness, aber N × Budget gegenüber dem
  Anbieter — hebt den Kontoschutz auf, siehe Punkt 1.
- **Rückwirkender Split des globalen Bestandszählerstands auf die Nutzer-Töpfe** (Merge-
  Migration analog `ThrottleStore`). Verworfen zugunsten von „globalen Bestand stehen lassen,
  je Nutzer frisch beginnen" (Präzedenz `track_resolution_health.py`): es ist ein Tageszähler
  — ein rückwirkender Split wäre ohnehin nur eine Schätzung, und der Bestand läuft binnen 24 h
  aus. Read-Modify-Write mit Merge bleibt für jeden **einzelnen** Schreibvorgang Pflicht
  (ADR-0031), nur der initiale Rückwirkungs-Merge zwischen beiden Töpfen entfällt.
- **Nutzerverzeichnis bei jedem `allow()` scannen, um N zu bestimmen.** Verworfen wegen der
  IO-Last im 15-Minuten-Alarm-Loop; die Menge `active_users` in der ohnehin gelesenen globalen
  Datei liefert dasselbe N für einen Dateizugriff, den es schon gibt.
- **`user_id` durch die Provider-Schicht reichen.** Siehe Punkt 4 — Schichtungsbruch ohne
  Verhaltensgewinn.

## Konsequenzen

- Der faire Anteil ist eine **Momentaufnahme**, keine Reservierung: werden im Tagesverlauf
  weitere Nutzer aktiv, sinkt `DAILY_BUDGET / N` — ein früh berechneter Anteil kann später
  unterschritten werden. Das ist gewollt.
- Bei genau einem aktiven Nutzer ist der faire Anteil das ganze Tagesbudget. Stufe 1 greift
  dann nie, und die Drosselung dieses Nutzers beginnt erst bei 100 % (Stufe 2). Das ist die
  korrekte Folge: wo es keine zweite Partei gibt, gibt es keine Fairness-Frage.
- Der **Schreibweg** von `active_users` ist sicherheitskritisch: fällt er aus, bleibt `N`
  dauerhaft 0, der faire Anteil damit das ganze Tagesbudget, und Stufe 1 feuert nie — bei
  81 % globaler Auslastung liefe `polling` dann für **jeden** durch, wo es heute für jeden
  blockiert. Das wäre keine fehlende Funktion, sondern eine ausgelieferte Rückentwicklung des
  Kontoschutzes. Eine Positivkontrolle auf den Schreibweg ist deshalb Pflichtbestandteil der
  Testabdeckung, nicht Kür.
- Der UTC-Tagesschnitt bleibt bewusst UTC, nicht die Zeitzone des Nutzers: das Kontingent hängt
  am Konto des Anbieters, nicht am Kalender des Nutzers.
- Drei Pfade (`comparison_engine.py`, `forecast.py`, `trip_forecast.py`) umgehen Cache **und**
  Gate weiterhin vollständig und fließen in keinen der beiden Töpfe ein — derselbe Scope-
  Schnitt wie in `fix_1329_forecast_cache_budget.md`.
