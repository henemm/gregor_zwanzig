---
entity_id: feat_2050_s4a_radar_teilausfall
type: feature
created: 2026-08-23
updated: 2026-08-23
status: draft
workflow: feat-2050-s4a-radar-teilausfall
version: "1.0"
tags: [alarm, nowcast, radar, protokoll, ausfall]
---

# Radar-Teilausfall wird protokolliert statt lautlos zu verschwinden (Issue #2050, Scheibe S4a)

## Approval

- [ ] Approved

## Purpose

Ein echter Ausfall der Radar-Quelle oder ihrer Gewitter-Beiabfrage endet im Alarmpfad heute
lautlos — im Alarmprotokoll des Nutzers ununterscheidbar von „geprüft, alles ruhig". Diese
Scheibe erfüllt **Szenario 6 / Anforderung B-4** („Teilausfall einer Quelle gilt nie als
Entwarnung") und **D-2** („jede Unterdrückung hat einen benannten Grund samt der Werte, die zur
Entscheidung führten") für den Radar-/Nowcast-Zweig: ein Totalausfall des Abrufs wird zu einem
eigenen, benannten Protokolleintrag statt eines stummen Ausstiegs, und eine ausgefallene
Gewitterprüfung darf die Briefing-Unterdrückung nicht mehr tragen — sie soll dort nicht länger
wie ein geprüftes „kein Gewitter" wirken.

## Source

- **File:** `src/services/trip_alert.py` — Radar-Alarmblock `check_radar_alerts`
  (Eingriffsstellen: Ausnahme-Fang `:1554-1560`, stummer Ausstieg vor `radar_alert_due()`
  `:1680-1681`, Briefing-Unterdrückung `:1735`, Protokoll-Helfer `_protokolliere_radar_unterdrueckung`
  `:1296-1319`)
- **File:** `src/services/compare_radar_alert.py` — spiegelbildliche Stelle im Ortsvergleich
  (Ausnahme-Fang `:440-442`, stummer Ausstieg vor `radar_alert_due()` `:447-448`)
- **File:** `src/services/alert_log.py` — Grund-Register (`REASON_DATA_UNAVAILABLE` fehlt,
  `:52-69`)
- **File:** `src/output/renderers/email/undelivered_hint.py` — deutsche Beschriftung und
  failed/withheld-Einordnung (`_REASON_LABELS`/`_REASON_BLOCK`, `:48-77`)
- **Identifier:** `check_radar_alerts`, `_protokolliere_radar_unterdrueckung`,
  `_check_one_preset`/`_detect_triggered_locations`

Schicht: ausschließlich Python-Core (`src/services/`, `src/output/renderers/`). Kein Go-, kein
Frontend-Anteil — `internal/store/log.go` liest weiterhin nur die sechs bestehenden Felder aus
`entries`, nie `not_delivered`; die neuen Einträge bleiben dort unsichtbar, wie schon die
bestehenden Radar-Gründe aus #2050 S3b.

## Basisstand — diese Scheibe setzt auf #2051 S2a auf

Alle Zeilennummern oben beziehen sich auf den Stand **vor** dem Merge von **#2051 S2a**
(räumliche Ausdehnung, Branch `feat-2051-s2-raeumliche-ausdehnung`, fertig und Adversary-VERIFIED
zum Zeitpunkt dieser Spec). Jene Scheibe ersetzt den **einen** `get_nowcast`-Aufruf durch eine
Schleife über bis zu `RADAR_ZONE_MAX_POINTS` Messpunkte entlang der Reststrecke. Abgestimmt
(2026-08-23): **#2051 S2a merged zuerst, S4a rebasiert darauf.** Für den Zuschnitt folgt daraus:

- **Der Teilausfall *über die Messpunkte* ist dort bereits behandelt und bewacht.** Ein
  ausgefallener Folgepunkt gilt als **Lücke** — weder nass noch trocken — und trennt keine Zone
  (`_zonen_messwert`); ein Fehler dort kostet den Alarm nicht, er wird geschluckt und
  protokolliert (`logger.warning` mit Koordinate, Trip-ID, Fehler). Das ist die sichere
  Richtung und **nicht** Gegenstand dieser Scheibe. Der dortige `logger.warning` wird allenfalls
  ergänzt, nie ersetzt.
- **Offen und Gegenstand dieser Scheibe bleibt der Ausfall des *auslösenden* Punktes.** Dort
  bleibt `data_unavailable` auch nach #2051 S2a bitgleich mit „kein Regen": die Auslöseregel
  liest den Marker weiterhin nicht. Genau diese Stelle schließt AC-1/AC-2.
- **Zwei Ebenen mit unterschiedlicher Fehlerpolitik** nach dem Merge: der auslösende Punkt bricht
  bei einem Fehler den Trip ab (dorthin gehört der Protokolleintrag), die Folgepunkte laufen
  weiter. Die Eingriffsstelle des auslösenden Zweigs wandert dabei nach oben.
- **Quelle der Lückenzahl für AC-12/AC-13** (von #2051 S2a am Code belegt, Stand nach deren
  Merge): `_zonen_ergebnisse` (`:1524-1546`) ist positionsgleich zu den Messpunkten und lebt an
  der Lesestelle `:1680` — Index *i* gehört zu Punkt *i*, ein `None` steht für „hier wurde nicht
  nachgesehen" (Ausnahme beim Abruf, `throttled`, `data_unavailable`, leeres Ergebnis). Die
  verdichteten Felder `rain_zones`/`km_measured` an `RadarAlertRequest` tragen die Zahl **nicht**
  — sie muss vor der Verdichtung abgegriffen werden. 🔴 **Vor dem Bauen zu prüfen:**
  `_zonen_ergebnisse` ist eine lokale Variable ab `:1524`; es ist nachzuweisen, dass **kein**
  Verzweigungspfad `:1680` erreicht, ohne sie gesetzt zu haben — sonst entsteht ein `NameError`
  in einem Randfall, der auf Tour zuschlägt. Der Hinweisgeber hat Reihenfolge und Einrückung
  verifiziert, ausdrücklich aber **nicht** jeden Pfad einzeln durchgespielt.
- **Abgelöste Zusicherung beachten:** Die #2017-Invariante „genau **ein** `get_nowcast`-Aufruf je
  Trip" ist bewusst auf eine Obergrenze (`<=` gegen `RADAR_ZONE_MAX_POINTS`) abgelöst. In dieser
  Scheibe wird **kein** `== 1`-Assert auf die Aufrufzahl eingeführt, und nach dem Rebase ist mit
  `git diff origin/main --diff-filter=D` sowie einem Blick auf
  `tests/tdd/test_issue_822_radar_nowcast_segment.py` und `_assert_messpunkt` in
  `tests/tdd/test_radar_alert_follows_ortstag.py` zu prüfen, dass die `<=`-Asserts nicht still
  zurückgedreht wurden — sonst bekäme die Ausdehnung nur noch einen Messpunkt und wäre faktisch
  tot, ohne dass eine Ampel es anzeigt.

## Estimated Scope

- **LoC:** ~90–140 Produktivcode (ohne Tests/Doku); mit den elf ACs zugehörigen Tests kommen
  voraussichtlich weitere ~150–220 Zeilen dazu — Gesamtsumme kann das 250-LoC-Standardlimit
  reißen, `loc_limit_override` ggf. nötig.
- **Files:** ~7 — 4 Produktivdateien, 2 Testdateien, 1 ADR-Nachtrag
- **Effort:** medium
- **Risiko:** MEDIUM — kritischer Alarmpfad, aber additive Änderung an einer bestehenden,
  gut abgesicherten Protokollierungs-Stelle; keine Signaturänderung an geteilten Bausteinen

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/radar_service.py::NowcastResult.data_unavailable` | dataclass field | Bestehender Marker (#1628 S1), bisher außerhalb von `radar_service.py` in keiner Zeile Produktivcode gelesen — wird hier erstmals in die Auslöseentscheidung geführt |
| `src/services/radar_service.py::NowcastResult.convective_checked` | dataclass field | Bestehender Marker (#1628-Umfeld), bisher nur in `format_now_text` (`:680`, `/jetzt`-Pull-Pfad) gelesen — wird hier erstmals im Alarmpfad gelesen |
| `src/services/alert_log.py::append_suppressed_entry` | function | Bestehender Protokoll-Schreibpfad, unverändert in Signatur; `gate_reason` bleibt Pflichtfeld |
| `src/services/trip_alert.py::_protokolliere_radar_unterdrueckung` | function | Fertiger Schreibweg des Radar-Zweigs, wird an den zwei neuen Stellen aufgerufen |
| `src/services/trip_alert.py::radar_alert_due` | function | Bleibt unverändert — die neue Prüfung auf `data_unavailable` läuft davor, nicht als Änderung dieser Funktion |
| `src/output/renderers/email/undelivered_hint.py::_REASON_LABELS`/`_REASON_BLOCK` | module data | Bekommt einen neuen Eintrag für den neuen Grund, Block `"failed"` (Abgrenzung zu AC-5) |
| `tests/helpers/alarm_pruefstrecke.py::AlarmPruefstrecke.lauf(zweig="radar", radar_service=…)` | test helper | DI-Seam für einen gestubbten Radar-Service mit vorgegebenem `NowcastResult`, unverändert |
| `tests/tdd/test_radar_cooldown_overtake.py`, `tests/tdd/test_nowcast_suppression_logging.py` | test | Vorlagen für gestubbte `NowcastResult`-Objekte durch den echten Pfad |

## Betroffene Dateien

| Datei | Änderungstyp | Zeilen | Beschreibung |
|---|---|---|---|
| `src/services/alert_log.py` | MODIFY | ~`:52-69` | Neue Konstante `REASON_DATA_UNAVAILABLE` mit Begründungskommentar |
| `src/services/trip_alert.py` | MODIFY | `:1554-1560`, `:1680-1681`, `:1735` | Protokoll-Aufruf bei Ausnahme und bei `data_unavailable`; Briefing-Unterdrückung um `convective_checked` erweitert |
| `src/services/compare_radar_alert.py` | MODIFY | `:440-448` | Spiegelbildlicher Protokoll-Aufruf für den Ortsvergleich-Radarpfad (Teil A only, s. Abgrenzung unten) |
| `src/output/renderers/email/undelivered_hint.py` | MODIFY | `:48-77` | Deutsche Beschriftung + `"failed"`-Einordnung für den neuen Grund |
| `docs/adr/0018-*.md` | MODIFY | Nachtrag | Datierter Nachtrag: die dritte, nutzerbezogene Ebene aus B-4 ist jetzt abgedeckt |
| `tests/tdd/test_radar_data_unavailable_reason.py` | CREATE | — | Teil A: Totalausfall-ACs (AC-1 bis AC-6, AC-10, AC-11) |
| `tests/tdd/test_radar_convective_check_failure.py` | CREATE | — | Teil B: Gewitterprüfungs-Ausfall-ACs (AC-7 bis AC-9) |

## Implementation Details

### Teil A — Totalausfall der Radarquelle

`result.data_unavailable` wird **vor** dem bestehenden `radar_alert_due()`-Aufruf (`:1680-1681`)
abgefragt: bei `True` läuft ein eigener Zweig mit `_protokolliere_radar_unterdrueckung(trip,
alert_log.REASON_DATA_UNAVAILABLE, effective_channels)` statt des heutigen stummen `continue`.
Die neue Konstante `REASON_DATA_UNAVAILABLE` ist eigenständig — keiner der sieben bestehenden
Gründe (`cooldown`, `daily_limit`, `double_alert_guard`, …) beschreibt einen Fremdausfall, und
eine Vermengung würde spätere Auswertungen in die Irre führen.

Derselbe Grund entsteht im Ausnahme-Zweig (`:1554-1560`): scheitert `get_nowcast()` mit einer
geworfenen Ausnahme statt mit einem fail-soft-Leerergebnis, ist das fachlich derselbe
Quellenausfall, nur in anderer Form. Der Protokoll-Aufruf mit `REASON_DATA_UNAVAILABLE` erfolgt
dort **unabhängig davon**, ob zusätzlich eine offene Sperrzeit vorlag (`_sperrzeit_offen`) — die
bestehende Verzweigung, die dort nur bei offener Sperrzeit überhaupt protokolliert, deckt den
Regelfall (keine offene Sperrzeit) nicht ab und ist genau die heute stumme Lücke aus #1628.

Die Absicherung folgt dem bestehenden Muster von `_protokolliere_radar_unterdrueckung`: ein
scheiternder Protokoll-Eintrag darf nie den Alarm der übrigen Trips desselben Nutzers mitreißen
(Muster `fix_1479`) — das umgebende `try/except` bleibt unverändert.

**Parität Ortsvergleich.** Dieselbe Zusicherung gilt an der gleichartigen Stelle in
`compare_radar_alert.py` (`_detect_triggered_locations`, Ausnahme-Fang `:440-442` und stummer
Ausstieg vor `radar_alert_due()` `:447-448`) — Muster `entity_id=preset_id,
entity_type="compare"`, wie an den bereits bestehenden `append_suppressed_entry`-Aufrufen
derselben Datei (aus #2050 S3b). Die Schwester-Scheibe S3b hat beide Flächen im selben Commit
bedient; ein Ausfall-Grund, den nur eine Fläche kennt, wäre ein Paritätsbruch. Teil B (die
Briefing-Unterdrückung) hat im Ortsvergleich **kein** Gegenstück — dort existiert keine
„bereits im Briefing angekündigt"-Prüfung (`compare_radar_alert.py:259-261`), also auch nichts,
das durch eine ausgefallene Gewitterprüfung fälschlich abgeschwächt werden könnte. Die Parität
aus AC-6 gilt deshalb ausdrücklich nur für Teil A.

**Deutsche Beschriftung.** Der neue Grund braucht einen Eintrag in `_REASON_LABELS` und
`_REASON_BLOCK` (`undelivered_hint.py:48-77`), sonst erscheint im Briefing der rohe Code statt
eines lesbaren Texts. Block `"failed"`, nicht `"withheld"`: ein Quellenausfall ist keine
Nutzereinstellung, im Gegensatz zu den bestehenden `"withheld"`-Gründen (Stille Stunden,
Cooldown, Tageslimit).

### Teil B — ausgefallene Gewitterprüfung trägt die Briefing-Unterdrückung nicht mehr

Die bestehende Bedingung bei `:1735` — `if _briefing_announced and not result.is_convective and
not _overtaking: … continue` — wird um die Vorbedingung erweitert, dass die Gewitterprüfung
tatsächlich stattgefunden hat (`result.convective_checked`). War sie ausgefallen, greift die
Unterdrückung nicht: der Sicherheits-Override aus #883 („konvektive Gefahr durchbricht die
Briefing-Unterdrückung") soll nicht durch eine nie stattgefundene Prüfung ausgehebelt werden
können — heute wird `is_convective` bei fehlendem Beiabruf per Vorgabe `False`, aus „nicht
geprüft" wird so still „kein Gewitter".

Der Ausfall der Gewitterprüfung wird im Protokolleintrag des betroffenen Laufs festgehalten
(AC-9, Anforderung D-2). Ist der Lauf trotz ausgefallener Prüfung noch an einer nachgelagerten
Stelle unterdrückt (z. B. am Doppel-Alarm-Guard), muss dieser Umstand in genau diesem Eintrag
sichtbar sein. Ein Präzedenzfall für „einen zusätzlichen Wert im bestehenden Feld
unterbringen" existiert bereits an derselben Stelle (`gate_reason=f"briefing_announced:
{_briefing_precip}mm"`, `:1743`) — die konkrete Umsetzung (neues optionales Feld an
`append_suppressed_entry` vs. Suffix an einem bestehenden Feld) ist eine Implementierungs-
entscheidung der GREEN-Phase, die Zusicherung selbst ist die beobachtbare Auffindbarkeit im
Protokoll.

### Nachweisfalle (aus #2050 S3b übernommen, gemessen beim Deploy)

Für einen Nachweis am E-Mail-Block ist die Reihenfolge zwingend *Briefing senden → Eintrag
schreiben → zweites Briefing senden*; der Anker `last_briefing_at` macht den naiven Weg blind.

## Expected Behavior

- **Input (Teil A):** ein Radar-Prüflauf, dessen Abruf mit `data_unavailable=True` oder mit
  einer geworfenen Ausnahme endet.
- **Output (Teil A):** genau ein `not_delivered`-Eintrag im `alert_log` des jeweiligen Nutzers
  mit `gate_reason == alert_log.REASON_DATA_UNAVAILABLE`; kein Alarm wird versendet.
- **Input (Teil B):** ein Radar-Prüflauf mit `convective_checked=False`, dessen Menge eine
  Briefing-Ankündigung nicht monoton überholt (`_overtaking=False`).
- **Output (Teil B):** die Briefing-Unterdrückung greift nicht — der Lauf durchläuft die
  nachfolgenden Prüfungen wie ein Lauf mit erfolgreicher, positiver Gewitterprüfung; der Ausfall
  der Prüfung ist im Protokolleintrag des Laufs auffindbar.
- **Side effects:** der neue Grund erscheint im „nicht zugestellt"-Block der Briefing-E-Mail
  unter einer deutschen Beschriftung im Abschnitt „FEHLGESCHLAGEN"; SMS/Telegram bleiben
  unberührt (kein `undelivered`-Bezug in diesen Renderern).

## Acceptance Criteria

- **AC-1:** Given ein Radar-Prüflauf, dessen Abruf einen echten Quellenausfall meldet
  (`NowcastResult.data_unavailable=True`), When der Radar-Alarmpfad für einen Trip geprüft wird,
  Then entsteht genau ein Protokolleintrag im Alarmprotokoll des Nutzers mit einem eigenen,
  benannten Ausfall-Grund (`REASON_DATA_UNAVAILABLE`) — statt wie heute ohne jede Spur zu enden
  — und es geht kein Alarm raus.

- **AC-2:** Given der Radar-Abruf scheitert mit einer geworfenen Ausnahme statt mit einem
  Leerergebnis, When derselbe Radar-Alarmpfad geprüft wird, Then entsteht derselbe Protokoll-
  eintrag mit demselben Ausfall-Grund wie in AC-1 — fachlich derselbe Fall in anderer Form, nur
  einen der beiden zu behandeln ließe die Hälfte aller echten Ausfälle weiterhin still.

- **AC-3:** Given ein Radar-Prüflauf mit echten, vollständigen Radardaten, der schlicht keinen
  Regen findet, When der Radar-Alarmpfad geprüft wird, Then entsteht **kein** Protokolleintrag —
  eine ruhige Viertelstunde ist kein Vorfall (Abgrenzung, muss rot werden, wenn man sie
  verletzt).

- **AC-4:** Given eine eigene Budget-Drosselung des Abrufs (`throttled=True,
  data_unavailable=False`), When der Radar-Alarmpfad geprüft wird, Then entsteht **kein**
  Ausfall-Eintrag — ADR-0018 trennt den selbst gewählten Rückzug vom Fremdausfall, eine
  Vermengung ließe eine externe Auswertung den eigenen Rückzug als Anbieterausfall eskalieren.

- **AC-5:** Given ein Ausfall-Eintrag mit `REASON_DATA_UNAVAILABLE` liegt im Alarmprotokoll
  eines Nutzers, When das nächste E-Mail-Briefing für diesen Nutzer gerendert wird, Then
  erscheint der Grund im „nicht zugestellt"-Abschnitt als deutsche Beschriftung — nicht als
  roher Code — im Block „FEHLGESCHLAGEN — da ist etwas schiefgegangen", nicht in „ZURÜCKGEHALTEN
  — so hast du es eingestellt", weil ein Quellenausfall keine Nutzereinstellung ist.

- **AC-6:** Given dieselbe Ausfall-Lage wie in AC-1, aber am gleichartigen Radarpfad des
  Ortsvergleichs (`compare_radar_alert.py`), When dieser Pfad geprüft wird, Then entsteht
  ebenfalls genau ein Protokolleintrag mit `REASON_DATA_UNAVAILABLE` und `entity_type ==
  "compare"` — die Schwester-Scheibe S3b hat beide Flächen im selben Commit bedient, ein
  Unterdrückungsgrund, den nur eine Fläche kennt, wäre ein Paritätsbruch.

- **AC-7:** Given die Gewitterprüfung eines Radar-Abrufs ist nachweislich ausgefallen
  (`NowcastResult.convective_checked=False`), When derselbe Abruf ohne den Ausfall die
  Briefing-Unterdrückung ausgelöst hätte (`is_convective=False` würde greifen), Then trägt die
  Prüfung die Briefing-Unterdrückung nicht mehr, und der Radar-Alarm wird nicht allein aus
  diesem Grund unterdrückt.

- **AC-8:** Given die Gewitterprüfung wurde durchgeführt und ergab kein Gewitter
  (`convective_checked=True, is_convective=False`), When derselbe Radar-Alarmpfad geprüft wird,
  Then greift die Briefing-Unterdrückung unverändert wie heute — der reine Δ-Modell-Charakter
  bleibt erhalten (Gegenprobe, sichert AC-7 gegen Übersteuerung).

- **AC-9:** Given ein Radar-Lauf mit ausgefallener Gewitterprüfung (`convective_checked=False`),
  When dieser Lauf einen Protokolleintrag erzeugt, Then ist der Ausfall der Gewitterprüfung in
  diesem Eintrag festgehalten — nachträglich muss belegbar sein, dass die Entscheidung ohne
  Gewitterinformation fiel (Anforderung D-2: benannter Grund samt der Werte).

- **AC-10:** Given ein Radar-Prüflauf ohne jeden Ausfall (echte Daten, echte Gewitterprüfung,
  Regen über der Auslöseschwelle), When der Radar-Alarmpfad geprüft wird, Then löst der Lauf
  weiterhin aus und der Alarm wird tatsächlich versendet — ohne diesen Nachweis belegt kein
  einziger der übrigen Tests, dass die Prüfung überhaupt etwas misst (Positivkontrolle).

- **AC-11:** Given zwei verschiedene Nutzer erleiden im selben Prüfzyklus je einen
  Radar-Quellenausfall, When beide Alarmpfade geprüft werden, Then landet jeder Ausfall-Eintrag
  ausschließlich im Alarmprotokoll des jeweils betroffenen Nutzers — zwei Nutzer teilen sich
  keinen Eintrag.

- **AC-12:** Given ein ausgelöster Radar-Alarm, dessen räumliche Ausdehnung aus Messpunkten
  bestimmt wurde, von denen mindestens einer ausgefallen ist (`derive_rain_zones` überspringt
  ihn heute kommentarlos, `rain_extent.py:77-78`), When der Alarm protokolliert wird, Then hält
  der Protokolleintrag fest, dass und an welcher Stelle Messpunkte fehlten — eine Ausdehnung,
  die aus vier von sechs Punkten stammt, ist nachträglich als solche erkennbar und nicht von
  einer vollständig vermessenen zu unterscheiden (Anforderung E-1: Messpunkt und Vergleichsbasis
  gehören ins Protokoll).

- **AC-13:** Given der auslösende erste Messpunkt meldet Regen, während **alle** Folgepunkte
  ausfallen, When der Alarm protokolliert wird, Then weist der Eintrag sämtliche Folgepunkte als
  fehlend aus — die Ausdehnungsaussage schrumpft in diesem Fall still auf den einen gemessenen
  Punkt zusammen (`km X-X`), und genau dieser Extremfall muss im Protokoll vom echten Befund
  „Regen nur auf einem Kilometer" unterscheidbar sein.

## Nicht Ziel

- **Kein neuer Alarm und keine neue Alarmart.** Szenario 6 verlangt wörtlich „als Ausfall
  behandeln und protokollieren" — Buchführung, nicht Meldung. Ein Alarm „konnte nicht prüfen"
  alle 15 Minuten wäre Lärm, und #2050 schließt neue Alarmarten ausdrücklich aus.
- **Die Beschriftung der Alarmnachricht selbst**
  (`src/output/renderers/alert/render.py:480,625,699,773,914`): Bei ausgefallener
  Gewitterprüfung nennt die Nachricht das Ereignis heute „Regen" bzw. `R` in der
  SMS-Kurzform, obwohl niemand auf Gewitter geprüft hat. Das ist derselbe B-4-Verstoß auf der
  Wortebene und gehört in eine eigene Scheibe — er berührt alle vier Kanäle, das englische
  SMS-Kurzform-Vokabular und das Renderer-Commit-Gate. Ausdrücklich benannt, nicht vergessen.
  Empfehlung: Folge-Scheibe S4b.
- **Die Ausdehnungs-Aussage selbst** (die mit #2051 S2a neu entstehende Zusatzzeile): Eine
  Messlücke verzerrt sie heute in **beide** Richtungen, und beide sind eigenständig zu
  formulieren, sonst fängt ein Test nur die eine Hälfte.
  - *Zu klein:* nass, nass, **Lücke**, trocken → der trockene Punkt schließt die Zone, die
    Aussage endet am letzten nassen Punkt. Es steht „Nass km 0–2", obwohl bei km 4 niemand
    nachgesehen hat und der Regen dort weitergehen könnte.
  - *Zu groß:* nass, **Lücke**, nass → das `continue` schließt die laufende Zone nicht ab, beide
    nassen Punkte wachsen zu **einer** Zone zusammen. Der Text behauptet durchgehende Nässe über
    einen Kilometer, an dem nicht gemessen wurde.

  Beides ist in #2051 S2a spec-konform (E4: die Lücke zählt nicht selbst als Messwert) und
  getestet — die dortige Formulierung deckt nur nicht ab, dass eine Lücke zwei Zonen
  zusammenwachsen lässt. Die Korrektur ist Wortarbeit über alle vier Kanäle samt SMS-Kurzform
  und Renderer-Commit-Gate und hängt sich nicht an diese Protokoll-Scheibe. **Empfehlung:
  Folge-Scheibe S4b, zusammen mit der Gewitter-Beschriftung oben — mit Dringlichkeit, weil die
  Zusatzzeile mit dem #2051-S2a-Merge live geht.** Von #2051 S2a wird die Grenze als *Known
  Limitation* in der dortigen Spec nachgetragen (zugesagt 2026-08-23).
- **Dringlichkeit und Ereignis-Identität** bei ausgefallener Gewitterprüfung
  (`trip_alert.py:1577`, `:1917`, `:2042`): ebenfalls betroffen, aber dort wirkt das Merkmal
  priorisierend statt unterdrückend — ein anderer Entscheidungstyp, eigene Messung nötig.
- **Regionalquelle fällt aus, Ersatzquelle liefert echte Bilder:** kein Ausfall im Sinne von
  B-4, sondern der von ADR-0018 gewollte Zustand („beste verfügbare Daten statt Totalausfall").
- **Amtlicher Zweig und Abweichungs-Zweig** (Nebenbefunde im Context-Dokument) — Kandidaten für
  S4b/S4c.

## Ausgangslage

`NowcastResult.data_unavailable` existiert seit #1628 S1 und wird außerhalb von
`radar_service.py` in **keiner** Zeile Produktivcode gelesen (repoweiter grep: null Treffer).
Von den fünfzehn Ausstiegen des Radarblocks in `trip_alert.py` ist der stumme Ausstieg bei
`:1681` (`radar_alert_due() == False`) der einzige völlig ohne Protokoll — nicht einmal eine
Logger-Zeile. Ein echter Quellenausfall (`onset_minutes=None` wegen `frames=[]`) fällt
zwangsläufig genau in diesen Ausstieg. Herkunft: #1628, Karnischer Höhenweg, 2026-08-08 — 14 von
14 Radar-Prüfläufen scheiterten mit HTTP 503, ohne dass irgendwo sichtbar wurde, dass die
Datenlage fehlte.

## Abgrenzung zu bereits Geliefertem

| Was | Wo | Aus |
|---|---|---|
| Ausfall-Marker in den Daten, sauber getrennt von Kontingent-Drosselung | `radar_service.py:993-1003` | #1628 S1 |
| Ehrlicher Text im `/jetzt`-Kommando statt „Kein Niederschlag" | `radar_service.py:590-597` | #1628 S3 |
| Health-Journal für anhaltende Ausfälle (Betreiber-Sicht) | `radar_service.py:520-541` → `providers/enrichment_health.py` | #1581 |
| Ausweich-Zeitfenster der Radar-Prüfläufe | `internal/scheduler/` | #1628 S0 |

ADR-0018 führt den Radarpfad deshalb als erfüllt, formuliert die Invariante aber auf
**Daten-Marker + Betreiber-Health-Signal**. Die dritte Ebene — der Nutzer, dessen Alarm ausbleibt
— ist von ADR-0018 nicht abgedeckt und genau der Gegenstand dieser Scheibe. Neu ist allein der
Weg in die **Auslöseentscheidung und ins nutzerbezogene Protokoll**.

## Testnachweis

Jeder Test fährt über die **echte** Auslöseentscheidung (`check_radar_alerts` bzw.
`_check_one_preset`), nicht über einen Mock der geprüften Funktion — Vorbild
`tests/tdd/test_alert_suppression_reason.py` (S3b) und die Prüfstrecke
`tests/helpers/alarm_pruefstrecke.py` (`lauf(at=…, zweig="radar", radar_service=…)`, DI-Seam
bereits vorhanden). Ein gestubbter Radar-Service liefert einen vorgegebenen `NowcastResult`
durch den echten Pfad — Vorlagen: `tests/tdd/test_radar_cooldown_overtake.py`,
`tests/tdd/test_nowcast_suppression_logging.py`.

- **AC-1/AC-2/AC-6:** Prüflauf mit gestubbtem `data_unavailable=True` bzw. einem Radar-Service,
  dessen `get_nowcast()` eine Ausnahme wirft; Nachweis über `alert_log.read_undelivered()` — ein
  Eintrag, `gate_reason == REASON_DATA_UNAVAILABLE`, kein Versand über die Prüfstrecke.
- **AC-3/AC-4:** Kontroll-Läufe mit `data_unavailable=False` (trocken bzw. gedrosselt) —
  `read_undelivered()` bleibt für diesen Vorfall leer.
- **AC-5:** echte Briefing-Mail aus dem Test-Postfach über den Renderer-Commit-Gate-Validator
  (`briefing_mail_validator.py`) — „nicht zugestellt"-Block auf deutsche Beschriftung und
  Block-Zuordnung prüfen.
- **AC-7/AC-8:** Prüflauf mit gestubbtem `convective_checked=False` bzw. `True` bei sonst
  identischer, briefing-angekündigter Lage — Nachweis über tatsächlichen Versand (AC-7) bzw.
  ausbleibenden Versand (AC-8) über die Prüfstrecke.
- **AC-9:** derselbe Lauf wie AC-7, Nachweis über den geschriebenen Protokolleintrag — der
  Ausfall der Gewitterprüfung muss darin auffindbar sein.
- **AC-10:** Kontroll-Lauf ganz ohne Ausfall — echter Versand über die Prüfstrecke
  (Positivkontrolle für alle übrigen Tests dieser Scheibe).
- **AC-11:** zwei Nutzer, je ein Ausfall-Lauf im selben Testprozess — `read_undelivered()` je
  Nutzer geprüft, keine Vermischung.

**Nachweisfalle:** für AC-5 ist die Reihenfolge zwingend *Briefing senden → Eintrag schreiben →
zweites Briefing senden*; der Anker `last_briefing_at` macht den naiven Weg (Eintrag vor dem
ersten Briefing) blind für den neuen Grund.

## Known Limitations

- **Nur Nowcast/Radar.** Der amtliche Zweig (`check_official_alert_triggers`) kennt den
  Ausfall-Status seiner Quelle heute nicht im Alarmpfad — eigene Scheibe, s. „Nicht Ziel".
- **Kein neuer stiller Diagnosepfad.** `read_undelivered()` liest beide Listen vollständig;
  einzig `REASON_CHANNEL_DISABLED` wird herausgefiltert. Sichtbarkeit ist hier gerade der Zweck.
- **Flut-Sorge ist unbegründet.** Drei Bremsen greifen bereits im Briefing-Renderer
  (Zeitfilter `since=last_briefing_at`, Dedup, Gruppierung mit `MAX_LINES_PER_BLOCK = 5`) — viele
  Ausfallläufe eines Tages werden zu einer einzigen Zeile.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0018 (Nachtrag)
- **Rationale:** ADR-0018 führt den Radarpfad heute als erfüllt, formuliert die Invariante aber
  ausschließlich auf Daten-Marker und Betreiber-Health-Signal. Diese Scheibe ergänzt die vom ADR
  bislang nicht abgedeckte dritte Ebene — den Nutzer, dessen Alarm bei einem Fremdausfall
  ausbleibt — ohne die bestehende Entscheidung zu revidieren: dieselbe Trennung Drosselung
  (selbst gewählt) vs. Ausfall (fremd), jetzt zusätzlich in der Auslöseentscheidung und im
  nutzerbezogenen Protokoll wirksam statt nur in den Daten und im Betreiber-Journal.

## Changelog

- 2026-08-23: Initial spec created (aus `docs/context/feat-2050-s4a-radar-teilausfall.md`).
