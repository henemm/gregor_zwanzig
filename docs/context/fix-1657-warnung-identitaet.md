# Context: fix-1657-warnung-identitaet

Issue: [#1657](https://github.com/henemm/gregor_zwanzig/issues/1657) — „Neu ausgestellte amtliche
Warnung gilt als neu und geht erneut raus (Zeitraum ist Teil der Identitaet)"

## Request Summary

Dieselbe amtliche Gefahr (z. B. „Gewitterwarnung Kirchbach") erreicht den Nutzer mehrfach, weil
der Melde-Schutz die zweite Fassung nicht als dieselbe Warnung erkennt. Am KHW-Trip `5f534011`
am 2026-08-16 kamen zwei Meldungen mit **byte-identischem** Kurztext (`KHW403 AMT GELB1/3: TH
So13-22, nur Ziel`) 30 Minuten auseinander an.

## Ausgangslage: ein Teil des Issues ist bereits erledigt

Der Issue-Text stammt vom 2026-08-09. Einen Tag spaeter wurde mit **#1685** (PO-Entscheidung
2026-08-10, live in `main` seit `6cc189ef`/`fdf22069`) genau die dort gestellte Frage teilweise
beantwortet: eine reine Fenster-Verschiebung oder -Verlaengerung **mit** zeitlicher Ueberlappung
gilt seitdem als dieselbe Warnung und bleibt still — ausser bei Stufenerhoehung oder einer
Vorverlegung des Beginns um >= 2h.

Der im Issue-Body genannte Trentino-Fall („gleiches Ende, vier Stunden verschobener Beginn")
ueberlappt und ist damit vom heutigen Stand erfasst. **Der Body beschreibt einen groesstenteils
geschlossenen Zustand — der belastbare offene Fall ist der KHW-Vorfall aus dem Kommentar vom
2026-08-16.**

## Der verbleibende Befund

### Aspekt 1 — aneinandergrenzende Fenster gelten als verschiedene Warnungen

Die Ueberlappungspruefung ist **strikt** (`official_alerts.py:485`):

```python
if alert_vf < cand_vt and cand_vf < alert_vt:
```

Die beiden KHW-Meldungen trugen die Fenster `13:00–14:00Z` und `14:00–15:00Z`. Sie grenzen
aneinander, ueberlappen aber nicht: `14:00 < 14:00` ist falsch. Es wird kein Kandidat gefunden,
die Funktion faellt auf den exakten Schluesselvergleich zurueck (`_exact_match_verdict`,
Zeile 464-466), findet unter dem neuen Schluessel nichts — und meldet.

Im Docstring der Testfaelle ist dieser Fall als `ac6-kein-zeit-ueberlapp-meldet` mit
`expect_report=True` **absichtlich** so festgehalten. Ob die Absicht den Fall
„luekenlos aneinandergereihte Teilfenster derselben durchgehenden Warnung" mitgemeint hat,
ist die zu klaerende Produktfrage.

### Aspekt 2 — der Anzeigetext unterscheidet die Meldungen nicht

`_tag_time()` (`official_alerts.py:1848-1870`) rendert ausschliesslich aus
`alert.valid_from`/`alert.valid_to`. Beide KHW-Meldungen zeigten `So13-22` — das **grobe
Gesamt-Warnfenster**, waehrend intern nach **stundenfeinen** Teilfenstern unterschieden wurde.

Das ist ein eigenstaendiger Widerspruch: Dedup-Granularitaet und Anzeige-Granularitaet stammen
nominell aus denselben zwei Feldern, liefern aber verschiedene Werte. **Offene Frage fuer die
Analyse:** Auf welchem Objekt laeuft die Anzeige, wenn der Melde-Schluessel ein anderes,
feineres Fenster traegt? Kandidat ist die Buendelung (`dedupe_official_alerts`,
`_bundle_by_hazard_level`) bzw. die fensterbezogene Abfrage
`get_official_alerts_for_location(..., window_start, window_end)` in `trip_alert.py:1480-1482`.

Selbst wenn Aspekt 1 als „sachlich berechtigte zweite Meldung" entschieden wird, bleibt fuer den
Nutzer eine ununterscheidbare Wiederholung stehen.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/official_alerts.py:383-399` | `official_alert_state_key` — baut die Identitaet inkl. Zeitraum |
| `src/output/renderers/alert/official_alerts.py:402-425` | `_identity_hazard_prefix` — Identitaet **ohne** Zeitraum, fuer die Kandidatensuche |
| `src/output/renderers/alert/official_alerts.py:428-520` | `official_alert_revision_verdict` — **die zu aendernde Kernregel** (Ueberlappung, Eskalation, Vorverlegung >= 2h) |
| `src/output/renderers/alert/official_alerts.py:523-534` | `official_alert_state_entry` — Schema des Gedaechtnis-Eintrags |
| `src/output/renderers/alert/official_alerts.py:1848-1870` | `_tag_time` — Anzeige-Zeitraum (Aspekt 2) |
| `src/services/trip_alert.py:1487-1511` | Trip-Aufrufstelle inkl. stiller Revision |
| `src/services/trip_alert.py:1513-1528` | `_record_official_alert_state` — Schreib-Wrapper |
| `src/services/compare_official_alert.py:255-284, 313-322` | Ortsvergleich-Pendant, strukturgleich gespiegelt |
| `src/services/alert_briefing_anchor.py:312-342` | `record_official_alerts_reported` — geteilte Schreib-Logik |
| `src/services/alert_state.py:36, 47-121` | Ablage + `reset()`, behaelt `official_alert:`-Eintraege beim Briefing-Reset (#1614) |

## Existing Patterns

- **Trip und Ortsvergleich teilen sich die drei Kernfunktionen** aus `official_alerts.py` —
  dupliziert sind nur die Aufrufstellen. Eine Regelaenderung wirkt automatisch in beiden Flaechen;
  das ist erwuenscht (Code-Teilung als Gate) und muss in beiden getestet werden.
- **Fail-soft:** fehlen `valid_from`/`valid_to`, entscheidet allein der exakte Schluesseltreffer —
  kein Interval-Vergleich. Alt-Eintraege ohne Zeitfelder werden uebersprungen.
- **Zeitstempel immer ueber `_as_aware_utc` normalisieren**, bevor verglichen wird (Adversary F001
  aus #1685: naiv-vs-aware wirft `TypeError`, und der Aufrufer faengt ihn nicht — der Trip
  verliert dann **alle** amtlichen Warnungen des Laufs).
- Stille Revision wird **sofort persistiert**, sonst vergleicht das dritte Kettenglied gegen das
  veraltete erste Fenster.

## Dependencies

- **Upstream:** `services.official_alerts.base._as_aware_utc`; die Warnquellen (MeteoAlarm,
  Vigilance, GeoSphere) liefern `valid_from`/`valid_to` teils naiv, teils aware;
  `get_official_alerts_for_location(window_start, window_end)` schneidet fensterbezogen zu.
- **Downstream:** `TripAlertService.check_official_alert_triggers`,
  `CompareOfficialAlertService._detect`, alle vier Ausgabekanaele (E-Mail, Telegram, SMS,
  Premium-SMS) haengen am Ergebnis.

## Existing Specs

- `docs/specs/modules/fix_1685_warnfenster_revision.md` — **die direkt vorausgehende
  Entscheidung**, Pflichtlektuere vor jedem Regelvorschlag
- `docs/specs/modules/fix_1614_briefing_warnfenster.md` — Doppelversand-Schutz nach Briefing
- `docs/specs/modules/compare_official_alert_channels.md` — Ortsvergleich-Flaeche
- `docs/adr/0016-amtliche-warnungen-additiver-typ.md`,
  `docs/adr/0041-zustaendigkeit-warn-quellen-drei-muster.md`

## Bestehende Zusicherungen, die gruen bleiben MUESSEN

| Test | Zusicherung |
|---|---|
| `tests/tdd/test_alert_state_briefing_reset.py:704` | Eskalierte Warnung geht trotz bereits gemeldeter unveraenderter Fassung erneut raus |
| `tests/tdd/test_alert_state_briefing_reset.py:344` | dasselbe Muster (AC-22b), aeltere Benennung |
| `tests/tdd/test_alert_state_briefing_reset.py:480` | Praefix-Konsistenz zwischen Schluesselbau und `reset()`-Filter |
| `tests/tdd/test_official_alert_revision_dedup.py:205` | Stufenerhoehung meldet trotz ueberlappendem Fenster (`ac5-stufe-gestiegen-meldet`) |
| `tests/tdd/test_official_alert_revision_dedup.py:211` | PO-Regel aus #1685 insgesamt (parametrisiert) |
| `tests/tdd/test_official_alert_revision_dedup.py:544, 615` | Mandantentrennung und Orts-Isolation im Ortsvergleich |
| `tests/tdd/test_official_alert_dedup_timespan.py:254` | Massiv-Eskalation ohne Zeitraum kollabiert weiterhin |

## Risks & Considerations

- **🔴 Die gefaehrliche Richtung ist Unterdrueckung, nicht Wiederholung.** Wird die Identitaet zu
  grob, verschwindet eine echte neue Gewitterwarnung. Auf dem KHW (Start 2026-08-20, Huette nur
  per Satellit erreichbar) ist eine ausgebliebene Warnung ungleich schwerer als eine doppelte.
  Jede Lockerung braucht eine ausdrueckliche Gegenprobe „neue Warnung nach Pause kommt durch".
- **Der Fall `ac6-kein-zeit-ueberlapp-meldet` ist heute eine bewusst freigegebene Zusicherung.**
  Ihn zu aendern heisst, eine bestehende AC zu revidieren — das braucht einen PO-Entscheid, keine
  stille Umdeutung (vgl. das analoge Muster bei #1599/#1584).
- **Zwei Aspekte, moeglicherweise zwei Tickets.** Aspekt 2 (Anzeige-Granularitaet) kann fachlich
  unabhaengig sein und eine eigene Loesung brauchen. Zuschnitt in der Analyse festlegen.
- **Parallelarbeit:** Sitzung `5c` bearbeitet #1714 am selben Melde-Gedaechtnis (Compare-Seite,
  `record_official_alerts_reported`-Pendant). Abgesprochen: Aenderungen am Schluesselformat oder
  Schreibpfad werden vorher gegenseitig angekuendigt.
- Die Kernstelle traegt dichte Adversary-Regressionskommentare (F001–F007) aus #1685. Diese
  Faelle sind bereits einmal teuer gelernt worden und duerfen nicht wegrefactort werden.

---

## Analysis

### Type

**Bug** — nutzersichtbares Fehlverhalten, an Produktionsdaten belegt.

### Der Vorfall war groesser als gemeldet

Gelesen aus `/var/lib/gregor/users/henning/alert_state/5f534011.json` (Produktion, nur lesend):

**Kirchbach, 2026-08-16, Gewitter, durchgehend Stufe 2.0 — drei Meldungen:**

| gemeldet (UTC) | Fenster | Ortszeit |
|---|---|---|
| 13:15:14 | `13:00–14:00Z` | 15:00–16:00 |
| 13:45:02 | `14:00–15:00Z` | 16:00–17:00 |
| 16:30:02 | `11:00–20:00Z` | 13:00–22:00 |

**Obertilliach, 2026-08-11, Gewitter, Stufe 2.0 — dasselbe Muster, ebenfalls drei Meldungen:**

| gemeldet (UTC) | Fenster |
|---|---|
| 14:30:14 | `15:00–16:00Z` |
| 15:45:22 | `17:00–18:00Z` |
| 17:45:09 | `13:00–19:00Z` |

Zwei unabhaengige Vorfaelle im Abstand von fuenf Tagen, gleiche Form: mehrere schmale Fenster,
danach ein breites Fenster, das sie umschliesst. **Das ist eine wiederkehrende Klasse, keine
Stichprobe** — und die im Issue gemeldeten „zwei" Meldungen waren in Wahrheit drei.

### Zwei bestaetigte Mechanismen, ein widerlegter

**(a) Aneinandergrenzende Schmalfenster — BESTAETIGT** (durch Ausfuehrung gegen die echte
Funktion). `official_alerts.py:485` prueft strikt `alert_vf < cand_vt and cand_vf < alert_vt`.
Bei `14:00 < 14:00` ist das falsch, `candidates` bleibt leer (490), Rueckfall auf
`_exact_match_verdict` (464-466), neuer Schluessel ⇒ meldet.

**(b) Das Breitfenster kippt die Vorverlegungs-Ausnahme — BESTAETIGT** (numerisch am
Kirchbach-Fall durchgerechnet). Das breite Fenster `11:00–20:00Z` ueberlappt beide Schmaleintraege,
wird also als Kandidat gefunden. Der Tie-Break (493-496, max nach `last_reported_value`, dann
`reported_at`) waehlt den zuletzt gemeldeten Schmaleintrag mit `valid_from = 14:00`. Zeile 498
rechnet `14:00 − 11:00 = 3h ≥ 2h` und wertet das als **Vorverlegung** ⇒ meldet.

Das breite Fenster **enthaelt** beide Kandidaten vollstaendig. Es ist keine frueher einsetzende
Gefahr, sondern eine Zusammenfassung. **Die Ausnahme fuer „die Gefahr kommt frueher" misst hier
einen Wechsel der Granularitaet.** Damit wendet (b) die #1685-Logik gegen ihren Zweck, statt sie
nur zu umgehen — der schwerwiegendere der beiden Mechanismen.

**(c) Anzeige-Granularitaet — WIDERLEGT als Buendelungs-Effekt.** Die Vermutung, eine Buendelung
rendere fuer alle Meldungen den Zeitraum eines gemeinsamen Repraesentanten, haelt dem Code nicht
stand: `dedupe_official_alerts` (270-323, Schluessel Zeile 315) und `_bundle_by_hazard_level`
(537-612) fuehren `valid_from`/`valid_to` ausdruecklich als **Schluessel**, nicht als Aggregat
(Docstring-Tabelle 567-570, abgesichert durch eine Adversary-Regression gegen Datenverlust).
`render_official_alert_sms` (2007-2025) ruft `_tag_time(n.alert, tz)` **pro Notice einzeln** auf.
Zwei Alerts mit verschiedenem Fenster koennen strukturell nicht auf einen gemeinsamen
Anzeige-Zeitraum kollabieren.

Der PO-Befund „beide Meldungen trugen `So13-22`" ist damit **nicht erklaert**. `So13-22` entspricht
exakt dem breiten Fenster `11:00–20:00Z`, also der dritten Meldung. Offen bleibt, ob die ersten
beiden Meldungen tatsaechlich einen anderen Text trugen (`So15-16`/`So16-17`) und die Beobachtung
Meldungen zusammenzieht, oder ob der tatsaechlich versendete Alert ein anderer war als der fuer
den State geprüfte. Zur Klaerung braeuchte es den rohen GeoSphere-Payload des Polls, der nicht im
State-File liegt.

### Affected Files (with changes)

| Datei | Change Type | Beschreibung |
|---|---|---|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Nur `official_alert_revision_verdict` (428-520): Beruehrung als Ueberlapp, Containment-Sonderfall vor der Vorverlegungs-Pruefung |
| `tests/tdd/test_official_alert_revision_dedup.py` | MODIFY | Revision von `ac6`, neue Faelle: Beruehrung, Containment, Zeitnaehe-Guard, Kirchbach/Obertilliach-Regression |
| `tests/tdd/test_official_alert_dedup_timespan.py` | MODIFY (evtl.) | Abgrenzung „echte Luecke meldet weiterhin" |
| `docs/specs/modules/fix_1657_warnfenster_identitaet.md` | CREATE | Spec analog zu `fix_1685_warnfenster_revision.md` |

**Trip und Ortsvergleich teilen den Kern** — `compare_official_alert.py` braucht keine Aenderung,
aber einen Isolationstest, der die Wirkung auch dort nachweist.

### Scope Assessment

- Dateien: 1 Produktionsdatei, 2–3 Testdateien, 1 Spec
- Geschaetzte LoC: Produktion +20–35, Tests +80–150
- Risk Level: **MEDIUM-HIGH** — schmale Aenderung an einer sicherheitsrelevanten Stelle

### Technical Approach (Empfehlung der Strategie-Bewertung)

Zwei Aenderungen, beide ausschliesslich in `official_alert_revision_verdict`:

1. **Beruehrung zaehlt als Ueberlapp** — Zeile 485 `<` → `<=`. Schliesst (a) ohne willkuerliche
   Toleranzspanne. Nur echte 0-Sekunden-Luecken werden erfasst; schon eine Sekunde Abstand bleibt
   eine eigene Warnung.
2. **Containment vor der Vorverlegungs-Pruefung** — neue Bedingung vor Zeile 498: umschliesst das
   neue Fenster den Kandidaten vollstaendig (`alert_vf <= kand_vf and alert_vt >= kand_vt`), gilt
   die ≥2h-Ausnahme **nicht**, sondern stille Revision. Schliesst (b).

Durchgerechnet am Kirchbach-Fall ergibt die Kombination: **nur die erste Meldung geht raus**,
die zweite und dritte werden still fortgeschrieben. Gleiches Ergebnis fuer Obertilliach.

**Verworfene Richtungen:** Identitaet ohne Zeitraum (zu grob, verletzt AC-4 aus #1245 direkt —
die gefaehrlichste Richtung). Praezisierung der Vorverlegung per Minimum statt Tie-Break (reicht
rechnerisch nicht: `13:00 − 11:00 = 2h` bleibt exakt auf der Schwelle und meldet weiter).
Fix im GeoSphere-Adapter (wirkt nur fuer eine Quelle, verletzt den geteilten Kern und zerstoert
die Rohdatenspur, die fuer (c) noch gebraucht wird).

### 🔴 Das Unterdrueckungs-Risiko des Containment-Fixes

`AlertStateService.reset()` (`alert_state.py:47-121`) behaelt `official_alert:`-Eintraege ueber
den Briefing-Reset hinweg (#1614), und es gibt **keine Bereinigung abgelaufener Eintraege anhand
von `valid_to`**. Daraus folgt ein konkretes Schluck-Szenario:

> Ein Alt-Eintrag von gestern (`10:00–11:00Z`) liegt unberuehrt im Gedaechtnis. Tage spaeter kommt
> eine **voellig neue, unabhaengige** Gewitterwarnung derselben Region mit breitem Fenster
> (`08:00–18:00Z`). Containment wuerde sie als stille Revision des Alt-Eintrags werten und
> **nicht melden**.

**Pflicht-Gegenmassnahme:** Containment nur anwenden, wenn der Kandidat zeitlich nahe ist
(`reported_at` innerhalb eines engen Fensters). Sonst faellt der Fall auf `_exact_match_verdict`
zurueck und meldet. Das braucht einen eigenen Adversary-Testfall, **bevor** die Richtung
freigegeben wird.

### Dependencies

Unveraendert gegenueber dem Abschnitt oben. Betroffene Quelle in der Praxis: **GeoSphere**
(Oesterreich) — als einzige koordinaten-scoped Quelle mit kurzer TTL strukturell fuer haeufig
revidierte Fenster exponiert (`geosphere_warn.py:134-148`). Vigilance (12h-Bloecke) und MeteoAlarm
(Bulletin-Ebene) arbeiten grob. Der Fix sitzt dennoch in der geteilten Identitaetsregel, damit er
fuer kuenftige Quellen gleicher Form ebenfalls greift.

### PO-Entscheidungen (2026-08-17, verbindlich)

- [x] **Beruehrende Fenster gelten als dieselbe Warnung.** Der Touching-Teilfall von
      `ac6-kein-zeit-ueberlapp-meldet` wird revidiert: „exakt aneinandergrenzend" ist kuenftig
      dieselbe Warnung. **Unveraendert bleibt:** eine echte Luecke — schon eine Sekunde — ist eine
      eigene, neue Warnung und meldet. Das ist die ausdrueckliche Grenze der Revision.
- [x] **Zuschnitt: zwei Tickets.** #1657 loest die bestaetigten Mechanismen (a) und (b) und wird
      damit fertig. Aspekt (c) (identischer Anzeigetext, mechanisch widerlegt, braucht zuerst
      rohe GeoSphere-Payload-Evidenz) wird als eigenes Issue abgetrennt.
- [x] **Zeitnaehe-Guard beim Containment: 6 Stunden.** Ein Bestandseintrag darf eine neue Warnung
      nur dann still schlucken, wenn sein `reported_at` hoechstens 6h zurueckliegt. Aeltere
      Eintraege zaehlen nicht als Kandidat fuer stille Revision — der Fall faellt dann auf
      `_exact_match_verdict` zurueck und meldet. Begruendung: bei Kirchbach lagen zwischen erster
      und letzter Meldung gut 3h; 6h deckt das mit Reserve ab, ohne das Unterdrueckungsfenster
      unnoetig zu weiten.
