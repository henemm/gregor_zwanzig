---
entity_id: alert_nachtragsmeldung
type: bugfix
created: 2026-08-21
updated: 2026-08-21
status: implemented
version: "1.5"
tags: [alerts, trip, issue-2018, issue-1467, nachtrag, event-identity]
---

# Gerichtete Nachtragsmeldung statt Voll-Alarm bei Ereignis-Duplikat (Issue #2018)

## Approval

- [x] Approved — PO-'go' 2026-08-21; ausgeliefert mit `47c527ee`, Prod-Selftest PASS

## Purpose

`check_event_identity_gate()` (Issue #1467 S4b) erkennt korrekt, dass eine
Radar-Nowcast-Meldung und eine kurz zuvor zugestellte amtliche Warnung
**dasselbe Ereignis** betreffen — lässt die zweite Meldung aber über die
V2-Eskalations-Ausnahme als **vollen zweiten Alarm** durch, weil `HIGH`
(Radar, konstant) und `MODERATE` (amtlich ORANGE) fälschlich als zwei Punkte
**einer** Skala verglichen werden, obwohl es zwei Skalen mit gleichen
Etiketten sind. Ein Nutzer erhielt dadurch binnen 22 Minuten zwei
Gewitter-Alarme für dasselbe Segment (16:15 amtlich ORANGE, 16:37
Radar-Nowcast), obwohl die Mail selbst "Cooldown: höchstens einmal in 30
Minuten" versprach.

**PO-Entscheid 2026-08-21 (bindend, nicht erneut aufzurollen) — GERICHTET
UND MENGENERHALTEND:** Der PO wurde zu **einer** Richtung befragt: **amtliche
Warnung zuerst, Radar-Nowcast danach.** Nur dafür liegt ein Entscheid vor.
In dieser Richtung wird die zweite Meldung (der Nowcast) **nicht
unterdrückt, wenn sie heute ohnehin als voller zweiter Alarm zugestellt
würde** (V2-Eskalation — genau die gemeldete Fehlerursache). Statt eines
zweiten vollen Alarms wird sie **sofort** zugestellt, aber als **kurzer
Nachtrag mit Bezug auf die vorige Meldung** ("Ergänzung zur amtlichen
Warnung von 16:15: Radar zeigt Beginn ab 16:45"). **Der PO-Entscheid ändert
ausschließlich die FORM dieser einen Zustellung — nicht, OB überhaupt
zugestellt wird.** Eine Konstellation, die heute STILLE bleibt (keine
Eskalation, keine V1-Ausnahme), bleibt STILLE — dafür liegt kein
PO-Entscheid vor (s. Invarianten, "Zustellmenge bleibt identisch").

**Die Gegenrichtung (Nowcast zuerst, amtliche Warnung danach) ist NICHT
Teil dieses Entscheids** und bleibt **vollständig unverändert**: sie ist
durch #1467 S4b eigenständig PO-freigegeben und wird durch diese Scheibe
nicht stillschweigend mitgeändert. Der sachliche Grund für die Asymmetrie:
Ein Nachtrag lohnt nur, wenn die zweite Meldung etwas HINZUFÜGT. Ein
Radar-Nowcast nach einer amtlichen Warnung fügt Präzision hinzu (konkrete
Anfangszeit statt Stundenfenster) — das rechtfertigt den Nachtrag. Eine
amtliche Warnung nach einem Radar-Nowcast ist dagegen GRÖBER und fügt
nichts hinzu. Der ausschlaggebende Grund: eine Umstellung auch der
Gegenrichtung würde eine Nachricht ERZEUGEN, wo heute keine kommt — das
Ticket beschwert sich über zu VIELE Meldungen. Eine Erweiterung auf die
Gegenrichtung bräuchte eine eigene, künftige PO-Entscheidung (s.
Nicht-Ziele).

Diese Spec macht `check_event_identity_gate()` dreiwertig, aber **gerichtet
und mengenerhaltend** — der dritte Ausgang ("Nachtrag") ist ausschließlich
in der Richtung amtlich→Nowcast UND ausschließlich für die Konstellation
erreichbar, die heute ohnehin voll zugestellt würde (**Teil A**) — und
zieht das Ergebnis für den **Trip-Pfad, alle vier Kanäle** durch (**Teil
B**). Der Ortsvergleich bleibt in dieser Lieferung **vollständig
unverändert**. Teil C macht den bestehenden Cooldown-Satz ehrlich.

## Source

- **File:** `src/services/alert_gate.py` (Teil A: `check_event_identity_gate`,
  `record_event_identity`, `_find_matching_entry`, `GateResult`)
- **Files:** `src/services/trip_alert.py`, `src/output/renderers/alert/model.py`,
  `src/output/renderers/alert/render.py`, `src/output/renderers/alert/official_alerts.py`,
  `src/services/alert_log.py` (Teil B/C) — `src/services/compare_radar_alert.py`,
  `src/services/compare_official_alert.py` bekommen NUR eine minimale
  Bestandsschutz-Anpassung (s. Teil B, Korrektur 2), keine neue Logik.

Betroffene Schicht: ausschließlich **Python-Core** (`src/services/`,
`src/output/renderers/alert/`). Kein Go-Code, kein Frontend-Code.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `rework_1467_s4b_entdopplung` | module | Vorgänger-Scheibe (live) — liefert `check_event_identity_gate`, `GateResult`, `resolve_hazard_class`, das Register-Schema, UND die eigenständig freigegebene Gegenrichtung (Kernfall-Test), die diese Scheibe unangetastet lässt |
| `rework_1917_s4b2_compare_entdopplung` | module | Vorgänger-Scheibe (live) — verdrahtet `check_event_identity_gate` an den beiden Compare-Aufrufstellen. Diese Scheibe fasst die dortigen Aufrufstellen GAR NICHT an (B0, Korrektur 4) — Bestandsschutz rein testseitig |
| `services.alert_urgency` | module | geteilte Dringlichkeits-Skala `"LOW"/"MODERATE"/"HIGH"`, `exceeds()` — bleibt in JEDER Konstellation die maßgebliche Freigabe-Prüfung, inklusive der Nachtrags-Richtung (dort ändert sich nur die FORM des Ergebnisses, nicht die Prüfung selbst) |
| `services.alert_state.AlertStateService` | module | Register-Ablage (`event_identity:`-Präfix) — der neue Quellenvermerk ist ein zusätzliches Feld in der bestehenden Nutzlast, kein neuer Präfix |
| `services.radar_service.NOWCAST_HORIZON_MIN` | module | bestehende Konstante (180 Min seit #1945) — V1-Ausnahme unverändert, in beiden Zweigen |
| `output.metric_format.THUNDER_LABEL_DE` | module | einzige Quelle für Gewitterstufen-Wörter (#1948 S6); der Nachtragstext dieser Scheibe nennt bewusst KEINE Stufe (s. Implementation Details Teil B), falls eine künftige Änderung doch eine nennt, MUSS sie hierher importiert werden, nie lokal kopiert (Wächter #1480) |
| `utils.timezone.local_fmt` | module | bereits in `alert_gate.py` importiert — formatiert `reported_at` als lokale `"HH:MM"` für den Nachtragstext, keine zweite Zeitformatierung |
| `output.renderers.alert.model.AlertMessage` | module | bekommt additives Feld `addendum_reference` (Muster `reference_at`, #1916) |
| `output.renderers.alert.official_alerts.OfficialAlertNotice` | module | bekommt **kein** entsprechendes Feld — amtliche Meldungen können durch diese Scheibe strukturell nie zum Nachtrag werden |
| `services.alert_log` | module | `append_entry()` bekommt additive Parameter für die Nachtrags-Markierung; `append_suppressed_entry`/`REASON_EVENT_DUPLICATE` bleiben für den (weiterhin bestehenden, jetzt PRÄZISER abgegrenzten) Unterdrückungsfall unverändert |
| `services.notification_service` | module | **kein Eingriff nötig** — der Kurzstil-Telegram-Zweig sendet bereits den `sms_body`/den SMS-Renderer-Output 1:1 weiter (`notification_service.py:915-920`, `:1454-1469`); die Nachtrags-Kennzeichnung im SMS-Text erreicht Kurzstil-Telegram dadurch automatisch, ohne dass dieser Fan-out angefasst wird |
| `output.channels.premium_sms.PremiumSmsOutput` | module | **kein Eingriff nötig** — Premium-SMS liest denselben `sms_body`/`render_official_alert_sms(...)`-Output wie SMS (`notification_service.py:949`, `:1257`, `:1549`), die Kennzeichnung erreicht diesen Kanal aus demselben Grund automatisch mit |
| `fix_1948_s6_alarm_stufenwort` | module | **Reihenfolge-Abhängigkeit:** landete als `cba7ffa3` und fügte in `render.py` oberhalb der hier betroffenen Funktionen +132 Zeilen ein. Diese Scheibe rebased zwingend auf den gelandeten Stand, bevor `render.py`/`official_alerts.py` angefasst werden — sonst zwei Sitzungen im selben Renderer-Zweig |
| `fix_2009_nowcast_vorlauf` | module | landete als `d7fad756`, ebenfalls oberhalb der betroffenen Funktionen in `render.py` — dieselbe Rebase-Auflage gilt |

## Estimated Scope

- **LoC produktiv:** Teil A ~55-70/-15 (`alert_gate.py`), Teil B ~120-140/-15
  (`model.py`, `official_alerts.py`, `render.py`, `alert_log.py`,
  `trip_alert.py` — NUR EINE echte Aufrufstelle, der Trip-Nowcast-Pfad;
  die Compare-Dateien bleiben nach Korrektur 4 unangetastet),
  Teil C ~10-15/-2 (`render.py`, additiv). **Gesamt ~+185-225/-32
  produktiv.**
- **LoC Tests:** Teil A ~190-230 (inkl. der neuen Stille-Regressionsfälle
  und des Zählnachweis-Tests über die volle Konstellations-Matrix), Teil B
  ~260-330 (zwei Aufrufstellen × vier Kanäle, jeweils am gerenderten
  Kanaltext geprüft, PLUS ein Ortsvergleich-Regressionstest), Teil C
  ~15-30 (Golden-Update + neue Substring-Assertion). **Gesamt ~465-590
  Test-LoC — sprengt das 250er-Budget weiterhin, `loc_limit_override`
  erforderlich** (Präzedenz S4a/S4b: kritischer Alarmpfad, vier Kanäle,
  Mutations-Gegenproben Pflicht).
- **Files:** 0 neu, 5 produktiv geändert (`alert_gate.py`, `model.py`,
  `render.py`, `alert_log.py`, `trip_alert.py`) — `compare_radar_alert.py`
  und `compare_official_alert.py` bleiben nach Korrektur 4 UNVERÄNDERT —,
  1 ADR-Nachtrag, ~6-8 Testdateien geändert/neu.
- **Effort:** high.
- **Risiko:** HOCH — kritischer Alarmpfad, alle vier Kanäle im Trip-Pfad, ein
  bit-eingefrorenes Golden wird bewusst berührt.

## Implementation Details

### Teil A — Das Gate wird dreiwertig, gerichtet UND mengenerhaltend

#### A1. Warum ein drittes Boolean-Feld statt eines Enums

`GateResult` bleibt ein `NamedTuple(allowed: bool, reason: Optional[str])` —
alle bestehenden Aufrufstellen prüfen ausschließlich `.allowed`/`.reason`
per Attributzugriff, nie per Positions-Unpacking
(`trip_alert.py:1445/1817/1848`, `compare_radar_alert.py:229`,
`compare_official_alert.py:210`). Ein drittes, **additives**, defaultetes
Feld ist deshalb rückwärtskompatibel, ohne einen bestehenden Aufrufer
anzufassen — Muster identisch zu `AlertMessage.reference_at` (#1916).

```python
class GateResult(NamedTuple):
    allowed: bool
    reason: Optional[str] = None
    # Issue #2018: additiv. True = die Meldung geht raus, aber als
    # NACHTRAG (Bezug auf eine bereits zugestellte amtliche Warnung),
    # statt als voller Alarm -- AUSSCHLIESSLICH fuer eine Zustellung, die
    # ohnehin stattgefunden haette (s. A4). `allowed` bleibt "geht raus
    # oder nicht" -- bestehende `if not gate.allowed: ...`-Zweige
    # unveraendert.
    is_addendum: bool = False
    addendum_source: Optional[str] = None       # NUR "official" moeglich
    addendum_reported_at: Optional[datetime] = None
```

#### A2. Quellenvermerk in der Register-Nutzlast (ohne Signaturbruch)

`record_event_identity()` schreibt einen zusätzlichen Schlüssel `"source"`
in die bestehende Nutzlast (`alert_gate.py:643-651`), abgeleitet aus
derselben Fallunterscheidung, die T2/T4 bereits treffen: Nowcast setzt NUR
`point_at`, amtlich NUR `window_start`/`window_end`.

```python
source = "nowcast" if point_at is not None else "official"
state[key] = {
    "hazard_class": hazard_class, "segment_ids": segments,
    "severity": severity, "source": source,
    "point_at": ..., "window_start": ..., "window_end": ...,
    "reported_at": now.isoformat(),
}
```

Keine neue Funktionssignatur — `record_event_identity` bekommt keinen neuen
Parameter, `source` ist rein intern abgeleitet. Der Signatur-Wächter
(`tests/tdd/test_compare_radar_alert_event_identity.py:842-882`) bleibt
grün (AC-A11).

**Rückwärtskompatibilität (AC-A2):** Alt-Einträge ohne `"source"` (vor
dieser Scheibe geschrieben) fallen beim Lesen auf dieselbe Ableitung
zurück: `entry.get("source") or ("nowcast" if entry.get("point_at") else
"official")`. Ein Register-Eintrag verliert dadurch nie seine Quellen-
Zuordnung, unabhängig vom Alter.

#### A3. Stärkster statt erstbester Treffer (O-F)

`_find_matching_entry()` (`alert_gate.py:492-541`) gibt heute beim ERSTEN
Kandidaten zurück, der Segment- und Zeitüberlappung erfüllt. Der Nachtrag
verweist auf einen KONKRETEN Registereintrag (Quelle + Uhrzeit im Text) —
ein zufällig erstbester statt des stärksten Treffers würde einen falschen
oder einen schwächeren Bezug zitieren. Vorbild `official_alerts.py:509-513`
(`max(candidates, key=...)`): die Funktion sammelt jetzt ALLE fail-soft
gültigen Kandidaten und wählt den mit der höchsten Dringlichkeit, bei
Gleichstand den zuletzt gemeldeten (`reported_at`).

```python
candidates = [...]  # wie bisher, aber append() statt return im Loop
if not candidates:
    return None
return max(
    candidates,
    key=lambda c: (_RANK.get(c["severity"], 0), c["reported_at"] or _MIN_TS),
)
```

Der zurückgegebene Kandidat trägt neu `"source"` und `"reported_at"`
(geparst über `_parse_event_ts`, fail-soft `None` bei unparsbarem Feld —
ein fehlendes `reported_at` verhindert dann NICHT das Match selbst, aber
lässt `addendum_reported_at` leer).

#### A4. Die gerichtete, mengenerhaltende Entscheidung — DRITTE Korrektur (2026-08-21, Coordinator-Nachtrag)

**Erste Korrektur (Richtung, bereits eingearbeitet):** Der ursprüngliche
Entwurf machte den dritten Ausgang richtungs-symmetrisch erreichbar und
stellte dafür `tests/tdd/test_alert_gate.py:757-793` (Kernfall: Nowcast
zuerst, amtliche Warnung danach) von `allowed=False` auf `is_addendum=True`
um — eine Scope-Erweiterung über den PO-Entscheid hinaus (der PO wurde nur
zur Richtung amtlich→Nowcast befragt). **Korrigiert:** dieser Test bleibt
unangetastet und unverändert grün.

**Zweite Korrektur (Menge, NEU, aufgedeckt durch eine Rückfrage der
Parallelsitzung #2020):** Die erste korrigierte Fassung ließ im
Nachtrags-Zweig die V2-Prüfung (`exceeds`) ERSATZLOS entfallen und endete
bedingungslos mit `is_addendum=True`. Dadurch wäre JEDE Konstellation
amtlich→Nowcast zugestellt worden — auch solche, die HEUTE STILLE bleiben:

- ein **nicht-konvektiver** Nowcast (`urgency_from_radar(is_convective=
  False, ...)` liefert `MODERATE`/`LOW`) nach einer amtlichen Warnung
  gleicher oder höherer Stufe — `exceeds` ist `False`, V1 greift nicht ⇒
  heute Stille;
- ein konvektiver Nowcast (`HIGH`) nach einer amtlichen **ROT**-Warnung
  (`HIGH`) — `exceeds("HIGH","HIGH")` ist `False` ⇒ heute Stille.

In beiden Fällen hätte die (nun verworfene) Zwischenfassung eine Nachricht
erzeugt, wo heute keine kommt — eine Ausweitung über den PO-Entscheid
hinaus. **Der PO hat entschieden: aus zwei vollen Alarmen wird einer plus
ein Nachtrag. Er hat NICHT entschieden: aus Stille wird ein Nachtrag.**

**Korrigierte Struktur — minimal und zielgenau:** Der Nachtrag ändert
AUSSCHLIESSLICH die FORM einer Zustellung, die heute ohnehin stattfindet —
NIE, OB zugestellt wird. `exceeds` wird deshalb weiterhin ZUERST geprüft,
exakt wie in jeder anderen Konstellation; nur sein POSITIVES Ergebnis wird
in der amtlich→Nowcast-Richtung als Nachtrag statt als Voll-Alarm
ausgeliefert. Fällt `exceeds` negativ aus, entscheidet — unverändert — V1,
danach — unverändert — Stille:

```python
new_source = "nowcast" if point_at is not None else "official"
addendum_direction = (match["source"] == "official" and new_source == "nowcast")

if not addendum_direction:
    # UNVERAENDERTE Vor-#2018-Logik (S4b-1), byte-identisch: gleiche
    # Quelle ODER Nowcast-zuerst/amtlich-danach (Kernfall, PO-freigegeben,
    # NICHT Teil dieser Scheibe).
    if alert_urgency.exceeds(severity, match["severity"]):
        return _ALLOWED  # V2, unveraendert
    if _covers_materially_more(match["covered_until"], point_at, window_end):
        return _ALLOWED  # V1, unveraendert
    return GateResult(False, alert_log.REASON_EVENT_DUPLICATE)  # unveraendert

# amtlich -> Nowcast: NUR die Form aendert sich, nie das Ob.
if alert_urgency.exceeds(severity, match["severity"]):
    # Heute: VOLLER Alarm (die gemeldete Fehlerursache -- zwei Skalen,
    # gleiche Etiketten). Kuenftig: dieselbe Zustellung, als Nachtrag.
    return GateResult(
        True, None, is_addendum=True,
        addendum_source=match["source"], addendum_reported_at=match["reported_at"],
    )
if _covers_materially_more(match["covered_until"], point_at, window_end):
    return _ALLOWED          # V1: echte neue Zeitabdeckung, bleibt VOLLER Alarm (AC-A7)
return GateResult(False, alert_log.REASON_EVENT_DUPLICATE)   # unveraendert Stille (AC-A8, NEU)
```

**Ergebnis:**

| Konstellation | V2 (`exceeds`) | V1 (Abdeckung) | sonst |
|---|---|---|---|
| gleiche Quelle (beide Richtungen) | Voll-Alarm | Voll-Alarm | Unterdrückt (unverändert) |
| Nowcast zuerst, amtlich danach (Gegenrichtung) | Voll-Alarm | Voll-Alarm | Unterdrückt (unverändert, Kernfall-Test) |
| **amtlich zuerst, Nowcast danach** | **Nachtrag statt Voll-Alarm** (dieselbe Zustellung, andere Form) | Voll-Alarm (unverändert) | **Unterdrückt (unverändert — NICHT Nachtrag, AC-A8)** |

**Harte, prüfbare Invariante (prominent, s. Invarianten-Abschnitt):** Die
MENGE der zugestellten Meldungen ist vor und nach dieser Scheibe
IDENTISCH — es kommt keine Meldung hinzu und keine fällt weg,
ausschließlich die Darstellung GENAU EINER Meldungsart (amtlich→Nowcast MIT
Eskalation) ändert sich von Voll-Alarm zu Nachtrag. Begründung:
PO-Entscheid (Variante c) ändert die FORM der Zustellung, nicht die
ZUSTELLMENGE. AC-A13 (Zählnachweis) sichert das über eine vollständige
Konstellations-Matrix ab; AC-A8 sichert speziell die neu präzisierte
Stille-Erhaltung innerhalb der Nachtrags-Richtung ab.

**Strukturelle Konsequenz (unverändert gültig):** Weil `is_addendum=True`
weiterhin AUSSCHLIESSLICH innerhalb des `addendum_direction`-Zweigs UND nur
im `exceeds`-Treffer zurückgegeben werden kann, und dieser Zweig nur
erreichbar ist, wenn die NEUE Meldung ein Nowcast ist, kann eine amtliche
Meldung durch diese Scheibe NIE zum Nachtrag werden — unabhängig von ihrer
Dringlichkeit (AC-A9, Mutations-Gegenprobe PFLICHT).

#### A5. Kein Enum, kein zweiter Parameter

`resolve_hazard_class`, `check_event_identity_gate`, `record_event_identity`
behalten exakt ihre S4b-1-Signaturen (AC-A11, Signatur-Wächter). Die
Richtungsentscheidung (`addendum_direction`) ist reine interne Ableitung
aus bereits vorhandenen Werten (`match["source"]`, `point_at`/`window_*`),
kein neuer Parameter.

### Teil B — Die Nachtragsmeldung wird zugestellt (NUR Trip-Pfad)

#### B0. Ortsvergleich fliegt aus dieser Lieferung

`compare_radar_alert.py` und `compare_official_alert.py` bekommen in dieser
Scheibe **keine neue Logik**. Begründung: Ortsvergleich-Themen sind
PO-zurückgestellt, der Umfang sprengt sonst jedes vertretbare Liefermaß.

**Wichtiger technischer Befund, transparent gemacht:** Reines Nichtstun an
den beiden Compare-Aufrufstellen würde die geforderte Eigenschaft
"Ortsvergleich verhält sich exakt unverändert" NICHT von selbst
garantieren. Der Grund: das Gate ist ein GETEILTER Baustein — für die
Konstellation "amtlich registriert, Ortsvergleich-Nowcast prüft MIT
Eskalation" kippt `.allowed` durch die neue Logik zwar nicht (es war und
bleibt `True`), aber die FORM wechselt auf `is_addendum=True` — ein
Compare-Aufrufer, der weiterhin nur `.allowed` liest, würde diese Meldung
unverändert (unmarkiert) zustellen, was inhaltlich unverändert korrekt
bleibt. **Ein künftiger Compare-Umbau, der `is_addendum` auswertet, könnte
allerdings eine Ortsvergleich-eigene Nachtragsdarstellung erzeugen, ohne
dass dafür je eine PO-Entscheidung getroffen wurde — dagegen braucht es
einen Wächter.** Welcher, s. Korrektur 4 direkt unten: ein
Verhaltenswächter, KEINE Änderung der Freigabe-Bedingung.

**KORREKTUR 4 (2026-08-21, Coordinator-Entscheid — die zuvor hier
vorgesehene Bedingung ist ZURÜCKGENOMMEN):** Der frühere Entwurf sah vor,
beide Compare-Aufrufstellen künftig `identity_gate.allowed and not
identity_gate.is_addendum` statt bloß `identity_gate.allowed` prüfen zu
lassen. **Das war falsch und ist ersatzlos gestrichen.** Am Code
nachgewiesen: für die Konstellation "amtlich registriert (`MODERATE`),
Ortsvergleich-Nowcast danach MIT Eskalation (`HIGH`)" liefert das Gate
heute über `exceeds` ein `_ALLOWED` (`alert_gate.py:605`), der Ort landet
in `allowed_triggered` (`compare_radar_alert.py:229`) und **wird
zugestellt**. Nach Teil A trägt dasselbe Ergebnis zusätzlich
`is_addendum=True`; die vorgeschlagene Bedingung hätte den Ort damit in den
`else`-Zweig fallen lassen — inklusive `append_suppressed_entry` — und
diese heute zugestellte Meldung **künftig unterdrückt**. Das ist genau die
Mengenänderung, die die harte Invariante ("Die Menge der zugestellten
Meldungen ist vor und nach dieser Scheibe IDENTISCH", PO-Entscheid
Korrektur 3) verbietet. Die frühere Begründung ("sie IST ja eine
Voll-Zustellung, nur mit einem für Compare irrelevanten Zusatz-Flag")
beschrieb das Gegenteil dessen, was `not is_addendum` mechanisch tut.

**Verbindliche Fassung: der Ortsvergleich bekommt in dieser Scheibe NULL
Produktivänderung.** `compare_radar_alert.py:229` und
`compare_official_alert.py:210` behalten `identity_gate.allowed`
unverändert. Eine Nachtrag-Konstellation wird dort weiterhin als
gewöhnliche Voll-Zustellung behandelt — was sie ist —, und Compare liest
`is_addendum`/`addendum_reference` schlicht nie.

Der in B0 ursprünglich befürchtete Fall (ein künftiger Compare-Umbau
erzeugt eine Ortsvergleich-eigene Nachtragsdarstellung, ohne dass je eine
PO-Entscheidung dafür vorlag) wird stattdessen **am beobachtbaren
Verhalten** bewacht statt durch eine Bedingung, die eine Zustellung kostet
— s. AC-B15 (neue Fassung): taucht in einem Compare-Ausgabetext jemals
eine Nachtrags-Markierung auf, wird der Wächter rot. Dieser Schutz ist
ohne jede Mengenänderung zu haben.

AC-B14 und AC-B15 sichern das gemeinsam ab.

#### B1. Designentscheid: Kennzeichnung sitzt im SMS-Text

Der Kurzstil-Telegram-Zweig sendet **den SMS-Text**, nicht den Telegram-
Text (`notification_service.py:915-920` amtlich, `:1454-1469` generisch/
Nowcast — Fan-out bereits bestehend, kein Eingriff nötig). Daraus folgt
zwingend: die Nachtrags-Kennzeichnung MUSS im SMS-Text sitzen, sonst
erreicht sie weder Kurzstil-Telegram noch Premium-SMS (Garmin inReach) —
und Premium-SMS ist genau der Kanal, der auf der Hütte am Karnischen
Höhenweg als EINZIGER ankommt (CLAUDE.md). Eine Kennzeichnung nur im
reichen Telegram-Renderer wäre für diese Nutzergruppe unsichtbar.

**Konsequenz für den Entwurf:** EIN gemeinsames, kompaktes SMS-Token treibt
SMS + Kurzstil-Telegram + Premium-SMS; E-Mail und Voll-Telegram bekommen
zusätzlich eine ausformulierte Bezugszeile.

#### B2. Das Referenz-Feld — ein String, zwei Verwendungen

`AlertMessage` bekommt ein additives Feld (Muster `reference_at`, #1916):

```python
# model.py, nach `reference_at` (Zeile 132)
# Issue #2018: additiv, optional. Gesetzt NUR wenn check_event_identity_gate
# diese Meldung als Nachtrag zu einer bereits zugestellten AMTLICHEN
# Meldung einstuft. Traegt die AUSFORMULIERTE Bezugszeile fuer E-Mail/Voll-
# Telegram ("Ergaenzung zur amtlichen Warnung von 16:15"). Der SMS-Renderer
# liest nur die Wahrheitswert-Praesenz (nicht den Inhalt) fuer sein
# Kompakt-Token -- der Satz selbst passt nicht ins SMS-Budget.
addendum_reference: str | None = None
```

`OfficialAlertNotice` (`official_alerts.py:138-177`) bekommt **kein**
entsprechendes Feld — amtliche Meldungen können durch diese Scheibe nie
zum Nachtrag werden (A4), das Feld wäre auf diesem DTO strukturell tot
(Bestandsdaten-Sauberkeit).

Aufbau des Werts an der einen relevanten Aufrufstelle (Trip-Nowcast, nach
`check_event_identity_gate`, vor dem Versand):

```python
if identity_gate.is_addendum:
    addendum_reference = (
        f"Ergänzung zur amtlichen Warnung von "
        f"{local_fmt(identity_gate.addendum_reported_at, tz)}"
    )
```

`local_fmt` ist in `alert_gate.py` bereits importiert (`utils.timezone`,
Zeile 47) — keine zweite Zeitformatierung. Fehlt `addendum_reported_at`
(fail-soft-Fall aus A3), entfällt die Uhrzeit ersatzlos aus dem Satz
("Ergänzung zur amtlichen Warnung") statt eines erfundenen Platzhalters —
gleiche Fehlerrichtung wie die bestehenden F001-Fail-soft-Regeln.

#### B3. E-Mail und Voll-Telegram: ausformulierte Zeile (Nowcast-Onset only)

- **Nowcast-E-Mail** (`_render_email_onset` `render.py:431`, `_render_email_onset_multi`
  `render.py:377`): zusätzliche Zeile/Absatz analog zum bestehenden
  Cooldown-Hinweis, nur wenn `msg.addendum_reference` gesetzt ist — sonst
  unverändert (keine leere Zeile).
- **Voll-Telegram** (`_render_telegram_onset` `render.py:488`): zweite
  Zeile vor der bestehenden Detailzeile, additiv, `None` → unverändert.

Beide Fälle sind reine Add-on-Zeilen mit `if <feld>: ...`-Wächter — keine
bestehende Zeile wird umgebaut (Regressions-Invariante für den Normalfall,
AC-B8). Die amtlichen E-Mail-/Telegram-Renderer (`official_alerts.py`)
bleiben **unangetastet** — sie können `addendum_reference` (kein Feld auf
`OfficialAlertNotice`, s. B2) nie zu lesen bekommen.

#### B4. SMS/Kurzstil-Telegram/Premium-SMS: kompaktes Token, KEIN Satz

Neues Präfix in `render.py` (der amtliche SMS-Renderer
`render_official_alert_sms` bleibt **unangetastet** — amtliche Meldungen
werden nie zum Nachtrag, s. A4/B2):

```python
# render.py, neben den anderen SMS-Helfern
# Issue #2018: bewusst OHNE '-' -- die SMS-Grammatik ueberlaedt den
# Bindestrich bereits zweifach (LEVELS-Fallback fuer eine Stufe ausserhalb
# 0-3 UND der '->'-Pfeil bei Stufenaenderungen, real gemessen z.B.
# 'TH:M->-' und 'TH:-->-'). Eine dritte Bedeutung waere im Fliesstext nicht
# mehr auseinanderzuhalten.
_ADDENDUM_SMS_PREFIX = "Erg "
```

`render_sms()` bekommt einen zusätzlichen, defaultierten Parameter
(`addendum: bool = False`); ist er `True`, wird der Kern-Text mit
`limit=limit - len(_ADDENDUM_SMS_PREFIX)` gerendert (bestehende
`_sms_pack_with_fallback`-Kette unverändert) und danach das Präfix
vorangestellt — die 160-Zeichen-Zusicherung entsteht dadurch aus der
BESTEHENDEN Kürzungslogik, keine neue Längenprüfung. `render_sms` liest
`addendum` implizit aus `msg.addendum_reference is not None`.

Beispiel (Nowcast-Onset-Kopf `"Ziel: TH@16:45"` → `"Erg Ziel: TH@16:45"`).

#### B5. Neuer `alert_log`-Grund

`append_entry()` (`alert_log.py:275`) bekommt additive, defaultete
Parameter (`is_addendum: bool = False`, `addendum_reported_at`); sie
schreiben zusätzliche Felder NUR wenn `is_addendum=True` — Alt-Einträge und
Normalfälle bleiben byte-identisch (Bestandsinvariante, Muster
`capture_id`, `alert_log.py:368-371`). Damit sind Nachträge im Protokoll
auswertbar, ohne das bestehende Schema für den Regelfall zu verändern.

#### B6. Zwei Aufrufstellen werten den dritten Ausgang aus — Trip only

| Pfad | Position | Änderung |
|---|---|---|
| `trip_alert.py:1437-1445` (Trip-Nowcast) | nach `check_event_identity_gate`, vor `send_radar_alert` | bei `is_addendum`: `addendum_reference` bauen (B2), in `_radar_request`/`AlertMessage` setzen statt der bestehenden Suppression-Logik |
| `trip_alert.py:1838-1849` (Trip-amtlich, Batch) | pro Alert im Filter-Loop | **KEINE Änderung** — amtliche Meldungen können strukturell nie `is_addendum=True` bekommen (A4); der Filter-Loop bleibt exakt beim S4b-1-Verhalten (verwirft weiterhin nur bei `allowed=False`) |
| `compare_radar_alert.py:224-231` | pro getriggertem Ort | **KEINE Änderung** (B0, Korrektur 4) — `identity_gate.allowed` bleibt; `not is_addendum` hätte eine heute zugestellte Meldung unterdrückt und die Mengen-Invariante gebrochen. Bestandsschutz rein testseitig (AC-B14/B15) |
| `compare_official_alert.py:204-212` | pro Ort im Filter-Loop | **KEINE Änderung nötig** — amtliche Meldungen können strukturell nie `is_addendum=True` werden, die bestehende `identity_gate.allowed`-Prüfung bleibt für amtliche Meldungen bereits korrekt |

**Präzisierung:** Der amtliche Trip-Pfad (`trip_alert.py:1838-1849`) und
der amtliche Compare-Pfad (`compare_official_alert.py`) brauchen **gar
keine Code-Änderung** — sie prüfen amtliche Meldungen, und amtliche
Meldungen können den neuen Zweig per Konstruktion nie erreichen (A4). Nur
der Trip-Nowcast-Pfad bekommt echte neue Logik (B2-B4); der Compare-
Nowcast-Pfad bekommt nach Korrektur 4 GAR KEINE Änderung (B0) — sein
Bestandsschutz wird ausschließlich testseitig bewacht (AC-B14/B15).

### Teil C — Der Cooldown-Satz wird ehrlich

**Reihenfolge-Auflage (Pflicht, vor Beginn zu prüfen):** `render.py` trägt
seit `cba7ffa3` (#1948 S6) und `d7fad756` (#2009) +132 bzw. weitere Zeilen
oberhalb der hier zitierten Funktionen. Diese Teilscheibe rebased auf den
aktuellen `main`-Stand, BEVOR `render.py` angefasst wird — Zeilennummern in
diesem Dokument sind gegen den Arbeitsbaum zum Zeitpunkt der Spec-Erstellung
verifiziert (s. Changelog), nicht garantiert stabil bis zur Implementierung.

Aktuelle Fundstellen des Satzes "Cooldown: Du erhältst diese Warnung
höchstens einmal in …" (per Text-Suche verifiziert, nicht per Zeilennummer
aus einer älteren Analyse):

- `render.py:399` (`_render_email_onset_multi`, Bündel-Zweig)
- `render.py:454` (`_render_email_onset`, Einzel-Zweig)

**Additive Präzisierung**, bestehender Wortlaut unangetastet (die
bestehenden Substring-Wächter prüfen exakt "höchstens einmal in":
`tests/tdd/test_issue_919_radar_alert_canonical.py:114`,
`tests/tdd/test_952_onset_alert_fidelity.py:290`,
`tests/tdd/test_issue_822_radar_nowcast_segment.py:593`,
`tests/tdd/test_compare_radar_alert.py:246,491` — sie bleiben grün, weil
der Substring erhalten bleibt):

```python
cooldown = (
    f"Cooldown: Du erhältst diese Warnung höchstens einmal in "
    f"{msg.cooldown_display}. Bei Meldungen aus anderen Quellen "
    f"(amtliche Warnung/Radar) greift dieser Cooldown nicht."
    if msg.cooldown_display else ""
)
```

Der genaue Zusatztext ist beim Implementieren gegen die Zeichenbudget-
Praxis der E-Mail (kein hartes Limit, aber Lesbarkeit) zu prüfen; die
FACHLICHE Aussage — Cooldown gilt NUR quelleneigen — ist bindend.

**🔴 Auflage (bindend, Korrektur 5): der Zusatz steht in DERSELBEN
Klartext-Zeile wie der bestehende Satz, mit einem Leerzeichen als Fuge —
KEINE eigene Zeile, KEIN eigener Absatz.** `test_official_alert_plaintext_part.py:121`
und `test_alert_mail_body_alignment.py:135` klassifizieren den Mailkörper
zeilen-/blockweise per Substring; eine eigene Zeile kippt diese
Reihenfolge-Wächter. In der HTML-Fassung gilt dasselbe sinngemäß: der
Zusatz landet INNERHALB des bestehenden `<span …>`-Blocks, nicht als
eigener Block.

**Bewusst angefasstes Golden — EINE Datei, ZWEI Konstanten (Korrektur 5):**
`tests/tdd/test_multi_location_onset_alert.py` ist die einzige Testdatei,
die die Cooldown-Zeile als vollständigen String statt als Substring prüft.
Sie trägt den Satz allerdings ZWEIMAL: in `EXPECTED_PLAIN` (Zeile ~47) und
in `EXPECTED_HTML` (Zeile ~88); beide werden im selben Test byte-identisch
geprüft. **Beide Konstanten werden aktualisiert.** Die frühere Formulierung
("`EXPECTED_PLAIN` ist das einzige Golden mit der Cooldown-Zeile") war
sachlich falsch — am Code widerlegt. Das erweitert den freigegebenen Umfang
NICHT: es ist dieselbe eine Aussage in zwei Darstellungen derselben Datei,
und ein nur halb aktualisiertes Golden bliebe nach GREEN dauerhaft rot.
Kein weiteres Golden wird angefasst.

## Invarianten

- **🔴 Die Menge der zugestellten Meldungen ist vor und nach dieser Scheibe
  IDENTISCH.** Es kommt keine Meldung hinzu und keine fällt weg —
  ausschließlich die Darstellung GENAU EINER Meldungsart (amtlich→Nowcast
  MIT V2-Eskalation) ändert sich von Voll-Alarm zu Nachtrag. Begründung:
  PO-Entscheid (Variante c) ändert die FORM der Zustellung, nicht die
  ZUSTELLMENGE — er hat entschieden, dass aus zwei vollen Alarmen einer
  plus ein Nachtrag wird, NICHT, dass aus Stille ein Nachtrag wird.
  Abgesichert durch AC-A8 (Einzelfälle) UND AC-A13 (vollständiger
  Zählnachweis über die Konstellations-Matrix) — AC-A9 (strukturelle
  Richtungs-Garantie) allein reicht dafür NICHT aus, sie sichert nur die
  Richtung, nicht die Menge.
- **Der gefährlichste Fehler ist der ausbleibende Alarm.** Jede
  Unsicherheit entscheidet fail-soft Richtung Zustellung (unverändert aus
  S3-S4b übernommen).
- **Amtliche Meldungen können durch diese Scheibe NIE zum Nachtrag werden**
  — strukturelle Eigenschaft (A4), Mutations-Gegenprobe PFLICHT (AC-A9).
- **Die Gegenrichtung (Nowcast zuerst, amtlich danach) bleibt vollständig
  unverändert** — sie ist eigenständig durch #1467 S4b PO-freigegeben und
  NICHT Teil des #2018-Entscheids. `test_alert_gate.py:757-793` bleibt
  unangetastet grün.
- **Gleiche Quelle = unverändertes Verhalten** — V2 (Eskalation) und die
  Unterdrückung ohne Ausnahme bleiben in JEDER Konstellation außer
  amtlich→Nowcast exakt wie vor dieser Scheibe.
- **V1 (Abdeckungs-Ausnahme) bleibt quellenunabhängig und liefert weiterhin
  vollen Alarm**, nicht Nachtrag — eine wesentliche zeitliche Erweiterung
  ist neue Information, kein Duplikat. Gilt in BEIDEN Zweigen (alte Logik
  UND Nachtrags-Zweig).
- **`hazard_class=None`** (Gefahrenart außerhalb `wet`) lässt weiterhin
  IMMER durch, ohne das Register zu lesen (S4b-1 AC-4, unverändert).
- **Leere Segment-Menge erzeugt nie ein Match** (S4b-1 AC-5, unverändert).
- **Der Ortsvergleich verhält sich exakt unverändert** — er bekommt in
  dieser Scheibe NULL Produktivänderung (B0, Korrektur 4).
  `identity_gate.allowed` bleibt die Freigabe-Bedingung; die zwischenzeitlich
  erwogene Verschärfung auf `and not is_addendum` ist zurückgenommen, weil
  sie eine heute zugestellte Meldung unterdrückt und damit die Mengen-
  Invariante bricht. Bewacht wird das Verhalten (AC-B14: Zustellung bleibt;
  AC-B15: keine Nachtrags-Markierung in irgendeinem Compare-Ausgabetext).
- **Mandantentrennung:** jeder neue Verzweigungspfad (Nachtrag) mit ZWEI
  verschiedenen Nutzern verifiziert, `user_id` nie auf `"default"`
  zurückfallen lassen.
- **Der amtliche Pfad kennt weiterhin keine Sperrzeit** (`check_official_alert_gate`-
  Signatur bleibt exakt wie in S4a, S4a AC-3 unberührt).
- **Register-Schreiben ausschließlich nach erfolgreicher Zustellung**
  (F001-Symmetrie, unverändert).
- **Bestandsdaten:** Read-Modify-Write mit Merge, nie Replace; ein Alt-
  Registereintrag ohne `"source"`-Feld verliert nie seine Quellen-
  Zuordnung (fail-soft-Ableitung, A2).
- **Kein neuer Bindestrich-Overload** im SMS-Vokabular (B4) — `-` bleibt
  ausschließlich Stufen-Fallback und Pfeilbestandteil.
- **Gewitterstufen-Wörter ausschließlich aus `THUNDER_LABEL_DE`**, falls ein
  künftiger Nachtragstext doch eine Stufe nennt — nie lokal nachgebaut
  (#1480-Wächter).
- Testpolitik: kein Mock-Theater, keine Dateiinhalt-Checks als
  Verhaltensnachweis — jeder Kanal-AC wird am GERENDERTEN Kanaltext
  bewiesen, nicht am Funktionsaufruf.
- Testdateien nach VERHALTEN benennen, nie nach Issue-Nummer.

## Nicht-Ziele (ausdrücklich)

- **Nachtrag in der Gegenrichtung (amtliche Warnung nach Nowcast).** Der PO
  wurde ausschließlich zur Richtung amtlich→Nowcast befragt. Ein Nachtrag
  lohnt nur, wenn die zweite Meldung etwas HINZUFÜGT — ein Nowcast nach
  einer amtlichen Warnung fügt Präzision hinzu (konkrete Anfangszeit statt
  Stundenfenster), eine amtliche Warnung nach einem Nowcast ist GRÖBER und
  fügt nichts hinzu. Zusätzlich würde eine Umstellung dieser Richtung eine
  Nachricht erzeugen, wo heute keine kommt — das Ticket beschwert sich über
  zu VIELE Meldungen. Eine Erweiterung auf diese Richtung bräuchte eine
  eigene, künftige PO-Entscheidung und wird hier nicht vorweggenommen.
- **Nachtrag für Konstellationen, die heute Stille sind** (keine
  Eskalation, keine V1-Ausnahme, auch in der amtlich→Nowcast-Richtung).
  Der PO-Entscheid ändert die FORM einer ohnehin stattfindenden
  Zustellung, nicht das OB. Eine Erweiterung, die auch stille
  Konstellationen zu Nachträgen macht, bräuchte eine eigene,
  künftige PO-Entscheidung.
- **Ortsvergleich-Nachtrag.** Der geteilte Gate-Baustein ist bereits
  vorbereitet (er unterscheidet nicht zwischen Trip- und Compare-Aufrufern);
  eine Ortsvergleich-eigene Nachtragsmeldung (eigenes `addendum_reference`
  auf einem Compare-DTO, eigene Renderer-Anpassungen) ist NICHT Teil dieser
  Lieferung — Ortsvergleich-Themen sind PO-zurückgestellt. Eine Folge-
  Scheibe könnte den bereits gerichteten Gate-Ausgang für Compare
  auswerten, ohne Teil A erneut anzufassen.
- **`urgency_from_radar()` differenzieren** (O-C, verworfen) — Kollateral-
  schaden an `alert_channel_threshold.split_by_threshold()` (ADR-0046: die
  Schwelle regelt WIE, nie OB); eigenes Ticket, falls überhaupt verfolgt.
- **Ausweitung auf Gefahrenarten jenseits `wet`** (Wind, Schnee, Glatteis,
  Hitze, Wegsperrung, Waldbrand) — eigenes Ticket, dieselbe Fläche wie
  S4b-1 AC-4.
- **Änderungsalarm (Δ) als dritte Prüfrichtung** — S4b-3, in der
  Vorgänger-Spec bereits als offen vermerkt, hier nicht angefasst.
- **`get_nowcast`-Abrufstelle, Segment-Ende-Guard-Rückbau,
  `trip_report_scheduler.py:1809-1815`** — gehört #2017 Scheibe B.
- **Alarm-Uhrzeiten/Projektion** (#2020), **Alarm-Textformat als solches**
  jenseits der hier spezifizierten Nachtrags-Zusätze (#1948 S6, bereits
  gelandet und als Basis übernommen, nicht erneut verändert).
- **Karenz/Mindestpause (O-E)** — vom PO ausdrücklich abgelehnt, nicht
  wieder vorzulegen.
- **Reine Textkorrektur ohne Verhaltensänderung (O-A allein)** — vom PO
  abgelehnt zugunsten der Nachtragsmeldung; Teil C ist hier NUR die
  Cooldown-Satz-Präzisierung, kein Ersatz für Teil A/B.
- **Unterdrückung der zweiten Meldung** (in der amtlich→Nowcast-Richtung,
  im eskalierenden Fall) — vom PO ausdrücklich abgelehnt, nicht wieder
  vorzulegen.

## Reihenfolge der Arbeit

1. Rebase auf den aktuellen `main`-Stand (S6 `cba7ffa3` + #2009 `d7fad756`
   müssen bereits enthalten sein), Zeilennummern dieser Spec gegen den
   Arbeitsbaum neu verifizieren.
2. Teil A zuerst, isoliert in `alert_gate.py` fertigstellen und testen
   (A1-A5) — inklusive des Regressionsnachweises für die unangetastete
   Gegenrichtung UND des Stille-Regressionsnachweises innerhalb der
   Nachtrags-Richtung (AC-A8) UND des Zählnachweises (AC-A13). Teil B baut
   auf dem gerichteten, mengenerhaltenden Rückgabewert auf.
3. Teil B: `model.py`-Erweiterung zuerst, dann die zwei Trip-Nowcast-
   Renderer-Add-ons (E-Mail/Telegram voll), dann das SMS-Präfix (B4)
   zuletzt — es ist der Fall mit der härtesten Nebenbedingung
   (160-Zeichen).
4. Trip-Nowcast-Aufrufstelle verdrahten (B6) — die amtliche Trip-
   Aufrufstelle bleibt unangetastet (kein Nachtrag dort möglich).
5. Ortsvergleich: KEINE Produktivänderung (B0, Korrektur 4) — nur die
   beiden Bestandsschutz-Tests AC-B14/AC-B15 schreiben, unabhängig,
   kann parallel zu 3/4 entstehen.
6. `alert_log`-Erweiterung (B5) — unabhängig, kann parallel entstehen.
7. Teil C zuletzt, in derselben Datei wie B3/B4 — additiv, geringes Risiko,
   aber abhängig vom Rebase aus Schritt 1.
8. Mutations-Gegenproben (strukturelle Garantie "amtlich nie Nachtrag" UND
   "Stille bleibt Stille") und Mandantentrennung zuletzt, wenn das
   Verhalten feststeht.
9. ADR-0021-Nachtrag zuletzt.

## Wächter, die mitziehen müssen

| Test | Warum |
|---|---|
| `tests/tdd/test_alert_gate.py:757-793` (Kernfall, Gegenrichtung) | bleibt **UNANGETASTET UND UNVERÄNDERT GRÜN** — die Gegenrichtung ist eigenständig freigegeben |
| `tests/tdd/test_alert_gate.py:885-923` (V1-Ausnahme, Gegenrichtung, alte AC-9) | bleibt unverändert grün — Teil des unveränderten alten Zweigs |
| `tests/tdd/test_alert_gate.py:927-971` (V2 same-source, alte AC-10) | bleibt UNVERÄNDERT grün (Invariante "gleiche Quelle") |
| `tests/tdd/test_compare_radar_alert_event_identity.py:842-882` (Signatur-Wächter) | bleibt grün — kein neuer Parameter an `check_event_identity_gate`/`record_event_identity`/`resolve_hazard_class` |
| `tests/tdd/test_official_alert_cooldown_entkopplung.py` | bleibt grün — `check_official_alert_gate`-Signatur unverändert |
| bestehende Ortsvergleich-Nowcast-/-amtlich-Tests (S4b-2/#1917) | bleiben unverändert grün — der Ortsvergleich-Code wird nach Korrektur 4 überhaupt nicht angefasst; AC-B14/B15 bewachen das Verhalten zusätzlich |
| `tests/tdd/test_alert_stufenwort.py::test_ac14_sms_bleibt_unveraendert_regressionswaechter` | prüft den SMS-Text eines GEWÖHNLICHEN Alarms auf exakt `"km 0-4: TH:M->H@15"` — erscheint das neue Token hier, ist das ein Befund an der Implementierung (Token leckt in einen Fall ohne Treffer), NICHT am Test; die Erwartung wird nicht aufgeweicht |
| `tests/tdd/test_telegram_kurzstil_trip_alert.py:315` | prüft Byte-Identität Kurzstil-Telegram == SMS-Text bei einem gewöhnlichen Alarm — dieselbe Schärfe wie oben |
| S6-Wächter zu `AC-12` (Stand-Zeile nur Telegram, Kurzstil byte-identisch zur SMS) | das neue Token heißt nicht `Stand:` und sitzt im SMS-Text — es wird vom Kurzstil miterbt, die Byte-Identität bleibt gewahrt (eigenes Regressions-AC hier, AC-B10) |
| `tests/tdd/test_multi_location_onset_alert.py` (`EXPECTED_PLAIN` ~47 UND `EXPECTED_HTML` ~88) | EINZIGE bewusst angefasste Golden-Datei (Teil C) — beide Konstanten tragen den Cooldown-Satz und werden beide aktualisiert (Korrektur 5) |
| `tests/tdd/test_official_alert_plaintext_part.py:121`, `tests/tdd/test_alert_mail_body_alignment.py:135` | zeilen-/blockweise Reihenfolge-Wächter — bleiben grün, weil der Cooldown-Zusatz in DERSELBEN Zeile steht (Korrektur 5) |
| Alle übrigen Cooldown-Substring-Wächter (s. Teil C) | bleiben grün, weil der bestehende Substring erhalten bleibt |

## Test-Plan

Kern-Schicht (deterministisch, kein Netz), sofern nicht anders vermerkt.
Jeder Kanal-AC wird am GERENDERTEN Kanaltext bewiesen (E-Mail-HTML/Plain,
Telegram-Body, SMS-Body als echte Strings aus echten Renderer-Aufrufen),
nicht am bloßen Aufruf-Nachweis einer Funktion.

| AC | Datei | Schicht |
|---|---|---|
| AC-A1 (Nachtrag: amtlich→Nowcast MIT Eskalation) | `tests/tdd/test_alert_gate.py` (neu, Reproduktion des gemeldeten Falls) | Kern |
| AC-A2 (Quellenvermerk + Fallback-Ableitung für Alt-Einträge) | `tests/tdd/test_alert_gate.py` (neu) | Kern |
| AC-A3 (V2-Eskalation unverändert in JEDER Nicht-Nachtrags-Konstellation) | `test_alert_gate.py:927-971` unverändert + 1 neuer Fall (Nowcast zuerst, amtlich mit echter Eskalation danach) | Kern |
| AC-A4 (keine Eskalation/kein V1 → Unterdrückung unverändert, gleiche Quelle) | `test_alert_gate.py:855-882` unverändert grün | Kern |
| AC-A5 (Kernfall/Gegenrichtung bleibt UNANGETASTET) | `test_alert_gate.py:757-793`, **keine Änderung**, explizit gegengeprüft | Kern |
| AC-A6 (V1-Ausnahme in der unveränderten Gegenrichtung) | `test_alert_gate.py:885-923` unverändert grün | Kern |
| AC-A7 (V1-Ausnahme in der Nachtrags-Richtung bleibt Voll-Alarm) | `tests/tdd/test_alert_gate.py` (neu) | Kern |
| AC-A8 (Stille bleibt Stille innerhalb der Nachtrags-Richtung, NEU, Mutations-Gegenprobe) | `tests/tdd/test_alert_gate.py` (neu, zwei Testfälle) | Kern |
| AC-A9 (strukturelle Garantie: amtlich nie Nachtrag, Mutations-Gegenprobe) | `tests/tdd/test_alert_gate.py` (neu) | Kern |
| AC-A10 (stärkster statt erstbester Treffer) | `tests/tdd/test_alert_gate.py` (neu, mehrere Kandidaten) | Kern |
| AC-A11 (Signatur-Wächter) | `tests/tdd/test_compare_radar_alert_event_identity.py`, unverändert grün | Kern |
| AC-A12 (Mandantentrennung, Nachtrag-Fall) | `tests/tdd/test_alert_gate.py` (zwei Nutzer) | Kern |
| AC-A13 (Zählnachweis: Zustellmenge identisch, NEU) | `tests/tdd/test_alert_gate.py` (neu, parametrisiert über volle Konstellations-Matrix) | Kern |
| AC-B1 (Trip-Nowcast wertet dritten Ausgang aus) | `tests/tdd/test_issue_1088_official_alert_triggers.py`-Äquivalent für Nowcast | Kern |
| AC-B2 (E-Mail Nowcast trägt ausformulierte Zeile) | `tests/tdd/test_952_onset_alert_fidelity.py` (neuer Fall) | Kern |
| AC-B3 (Voll-Telegram Nowcast trägt ausformulierte Zeile) | Telegram-Renderer-Test, neuer Fall | Kern |
| AC-B4 (SMS trägt Kompakt-Token) | `tests/tdd/test_alert_stufenwort.py` oder neue Datei `test_alert_addendum_sms.py` | Kern |
| AC-B5 (Kennzeichnung erreicht Kurzstil-Telegram, byte-identisch zur SMS) | `tests/tdd/test_telegram_kurzstil_trip_alert.py` (neuer Fall) | Kern |
| AC-B6 (Kennzeichnung erreicht Premium-SMS) | Test gegen `render_sms` mit `addendum=True`, Aufruf-Nachweis, dass Premium-SMS-Dispatch denselben Text verwendet | Kern |
| AC-B7 (SMS bleibt ≤160 im längsten realistischen Fall) | `tests/tdd/test_alert_addendum_sms.py` (neu) | Kern |
| AC-B8 (Normalfall bleibt token-/zeilenfrei, Regression) | bestehende Golden/Substring-Wächter, unverändert | Kern |
| AC-B9 (kein Token bei gewöhnlichem Alarm — die beiden benannten Wächter) | `test_alert_stufenwort.py::test_ac14_...`, `test_telegram_kurzstil_trip_alert.py:315`, unverändert grün | Kern |
| AC-B10 (Verträglichkeit mit S6 AC-12) | S6-Wächter zu Stand-Zeile/Byte-Identität, unverändert grün + 1 neuer Fall mit gesetztem Token | Kern |
| AC-B11 (kein dritter `-`-Overload) | `tests/tdd/test_alert_addendum_sms.py` (Zeichen-Inspektion des Präfix-Literals) | Kern |
| AC-B12 (amtlicher Trip-Pfad bleibt unangetastet) | bestehende amtliche Trip-Batch-Tests, unverändert grün | Kern |
| AC-B13 (alert_log-Nachtrags-Markierung, additiv, Alt-Einträge unverändert) | `tests/tdd/test_alert_log_*.py` (neuer Fall) | Kern |
| AC-B14 (Ortsvergleich verhält sich exakt unverändert) | bestehende Ortsvergleich-Nowcast-/-amtlich-Tests (S4b-2/#1917), unverändert grün + 1 neuer Fall mit einer eskalierenden amtlich→Nowcast-Konstellation, die für Compare weiterhin als gewöhnliche Voll-Zustellung behandelt wird | Kern |
| AC-B15 (Bestandsschutz am VERHALTEN bewacht, Korrektur 4) | `tests/tdd/test_compare_radar_alert_event_identity.py` (neu: Rohergebnis `allowed=True` UND `is_addendum=True`, Compare stellt trotzdem voll zu, KEINE Nachtrags-Markierung in irgendeinem Compare-Ausgabetext) | Kern |
| AC-C1 (Cooldown-Satz-Präzisierung, additiv) | bestehende Substring-Wächter unverändert + neuer Substring-Test auf den Zusatz | Kern |
| AC-C2 (Golden bewusst aktualisiert) | `tests/tdd/test_multi_location_onset_alert.py:39-48` | Kern |
| AC-C3 (Reihenfolge-Nachweis: Rebase vor Renderer-Änderung) | `# doc-compliance-test` (Commit-Reihenfolge/Changelog) | Kern |
| AC-D1 (ADR-Nachtrag) | `tests/test_adr_index_drift.py` | Kern |

Live-E2E: keine eigenen Live-Marker-Tests — echte quellenübergreifende
Duplikate sind nicht auf Bestellung provozierbar (identische Begründung wie
S4b-1). Staging-Nachweis über gezielt gesetzte Registereinträge, danach
Sichtprüfung der vier Trip-Kanaltexte (E-Mail/Telegram/SMS/Premium-SMS) im
Test-Postfach bzw. Test-Chat.

## Acceptance Criteria

**Teil A — Gerichtetes, mengenerhaltendes dreiwertiges Gate**

- **AC-A1:** Given einen registrierten Registereintrag der Quelle
  `"official"` und eine neue Nowcast-Meldung (`point_at` gesetzt) mit ECHT
  HÖHERER Dringlichkeit (`exceeds(severity, match["severity"])` ist
  `True`) derselben Gefahrenklasse/desselben Orts/überlappenden
  Zeitfensters, When `check_event_identity_gate` geprüft wird, Then ist
  das Ergebnis `allowed=True, is_addendum=True`, mit `addendum_source ==
  "official"` und `addendum_reported_at` gleich dem `reported_at` des
  Registereintrags.
  - Test: amtliche Warnung `MODERATE` registrieren, Nowcast `HIGH`
    (konvektiv) mit überlappendem Zeitfenster prüfen — Reproduktion des
    gemeldeten Falls (16:15/16:37) — `is_addendum is True`.
  - Schicht: Kern.

- **AC-A2:** Given einen Registereintrag OHNE das Feld `"source"` (Alt-
  Format vor dieser Scheibe), When er als Kandidat geprüft wird, Then wird
  die Quelle korrekt aus der Anwesenheit von `point_at` (→ `"nowcast"`)
  bzw. `window_start`/`window_end` (→ `"official"`) abgeleitet — dieselbe
  Ableitung wie beim Schreiben neuer Einträge.
  - Test: Registereintrag ohne `"source"`-Schlüssel vorbelegen, Match
    liefert die korrekt abgeleitete Quelle, Gate-Entscheidung entspricht
    der eines gleichwertigen NEUEN Eintrags mit explizitem Feld.
  - Schicht: Kern.

- **AC-A3:** Given eine registrierte Meldung UND eine zweite Meldung mit
  höherer Dringlichkeit, When das Gate geprüft wird UND die Konstellation
  NICHT amtlich-zuerst/Nowcast-danach ist (gleiche Quelle ODER Nowcast
  zuerst/amtlich danach), Then bricht sie wie bisher als VOLLER Alarm durch
  (`is_addendum=False`) — die quellenblinde V2-Eskalation ist außerhalb der
  Nachtrags-Richtung vollständig unverändert.
  - Test: bestehender Test (`test_alert_gate.py:927-971`, gleiche Quelle)
    bleibt unverändert grün; NEUER Fall: Nowcast registriert (MODERATE),
    amtliche Warnung mit echt höherer Dringlichkeit (HIGH) danach prüft —
    `allowed=True, is_addendum=False`.
  - Schicht: Kern.

- **AC-A4:** Given eine registrierte Meldung UND eine zweite Meldung
  DERSELBEN Quelle ohne Eskalation und ohne V1-Erweiterung, When das Gate
  geprüft wird, Then bleibt sie UNTERDRÜCKT (`allowed=False`) —
  unverändert gegenüber S4b-1.
  - Test: bestehender Test (`test_alert_gate.py:855-882`, S4b-1 AC-8)
    bleibt unverändert grün.
  - Schicht: Kern.

- **AC-A5:** Given den Kernfall aus #1467 S4b (Nowcast 14:22 registriert,
  amtliche Warnung 8,2 Min später, gleiche Dringlichkeit, keine V1-
  Ausnahme), When das Gate geprüft wird, Then bleibt das Ergebnis
  UNVERÄNDERT `allowed=False` — diese Scheibe ändert an dieser Richtung
  NICHTS. Der Test, der das prüft, wird NICHT modifiziert.
  - Test: `test_alert_gate.py:757-793` unverändert, ohne jede Anpassung,
    ausgeführt.
  - Schicht: Kern.

- **AC-A6:** Given einen registrierten Nowcast-Eintrag (abgedeckt bis
  Onset+180 Min), When eine amtliche Warnung danach eintrifft, deren
  `valid_to` mehr als 180 Min über das bereits abgedeckte Ende
  hinausreicht, ohne höhere Dringlichkeit, Then wird sie zugestellt
  (V1-Ausnahme, Gegenrichtung, unverändert).
  - Test: bestehender Test (`test_alert_gate.py:885-923`, S4b-1 AC-9)
    bleibt unverändert grün.
  - Schicht: Kern.

- **AC-A7:** Given einen registrierten amtlichen Registereintrag UND einen
  neuen Nowcast OHNE höhere Dringlichkeit (`exceeds` ist `False`), dessen
  Zeitfenster aber wesentlich (`> NOWCAST_HORIZON_MIN`) über das bereits
  abgedeckte Ende hinausreicht, When das Gate geprüft wird, Then bricht er
  als VOLLER Alarm durch (`is_addendum=False`), NICHT als Nachtrag — die
  V1-Ausnahme bleibt auch in der Nachtrags-Richtung quellenunabhängig
  gültig und liefert echte neue Information voll aus.
  - Test: amtliche Warnung registrieren (`window_end` = T), Nowcast mit
    `onset` so, dass `onset + NOWCAST_HORIZON_MIN` deutlich über `T +
    NOWCAST_HORIZON_MIN` hinausreicht, ohne höhere Dringlichkeit,
    `allowed=True, is_addendum=False`.
  - Schicht: Kern.

- **AC-A8 (NEU, dritte Korrektur):** Given eine Konstellation
  amtlich→Nowcast, in der `exceeds(neu, registriert)` `False` ist UND die
  V1-Ausnahme NICHT greift, When das Gate geprüft wird, Then wird
  weiterhin UNTERDRÜCKT (`allowed=False`, `reason=REASON_EVENT_DUPLICATE`)
  und KEIN Nachtrag erzeugt (`is_addendum=False`) — die Zustellung bleibt
  Stille, exakt wie vor dieser Scheibe.
  - Test: ZWEI getrennte Fälle im selben Testmodul: (a) ein NICHT-
    konvektiver Nowcast (`severity` `MODERATE`/`LOW`) nach einer amtlichen
    Warnung gleicher oder höherer Stufe; (b) ein konvektiver Nowcast
    (`severity="HIGH"`) nach einer amtlichen ROT-Warnung
    (`severity="HIGH"`) — `exceeds("HIGH","HIGH")` ist `False`. Beide
    Fälle liefern `allowed=False, is_addendum=False`.
  - Mutations-Gegenprobe (PFLICHT): entfernt man die `exceeds`-Bedingung
    aus dem Nachtrags-Zweig (Rückfall auf den verworfenen bedingungslosen
    Nachtrag), MUSS dieses AC in BEIDEN Fällen rot werden — das ist die
    Absicherung gegen genau die Ausweitung, die durch die Rückfrage aus
    #2020 aufgedeckt wurde.
  - Schicht: Kern.

- **AC-A9:** Given die Gate-Logik nach Abschluss dieser Scheibe, When man
  JEDE erreichbare Kombination aus `match["source"]` und `new_source`
  durchprobiert, Then ist `is_addendum=True` AUSSCHLIESSLICH erreichbar,
  wenn `match["source"] == "official"` UND `new_source == "nowcast"` — in
  KEINER anderen Kombination.
  - Test: alle vier Kombinationen (official→official, official→nowcast,
    nowcast→official, nowcast→nowcast) im selben Testmodul, nur
    official→nowcast liefert (bei Eskalation) `is_addendum=True`.
  - Mutations-Gegenprobe (PFLICHT, **Testreferenz korrigiert 2026-08-21,
    Korrektur 6**): die Bedingung `match["source"] == "official"` aus
    `addendum_direction` entfernen (sodass JEDE Quelle als Vorgänger
    genügt) MUSS **den parametrisierten Fall dieses ACs** rot machen
    (`test_alert_gate.py::test_aca9_nachtrag_entsteht_ausschliesslich_von_amtlich_zu_nowcast[nowcast-nowcast-False]`)
    — er ist die Absicherung gegen die Scope-Erweiterung, die in dieser
    Spec bereits einmal versehentlich passiert ist.
  - **NICHT geeignet ist der Kernfall-Test aus AC-A5**
    (`test_ac6_kernfall_nowcast_gefolgt_von_amtlicher_warnung_8_2_min_spaeter`).
    Eine frühere Fassung dieses ACs verlangte genau das; am Code gemessen
    ist es **strukturell unerfüllbar**: dort sind beide Dringlichkeiten
    `HIGH`, `exceeds("HIGH","HIGH")` ist bereits `False`, der Code erreicht
    den `addendum_direction`-Zweig in diesem Fall also nie — gleich wie die
    Bedingung lautet. Der Test bleibt bei dieser Mutation zwangsläufig
    grün, ohne dass die Implementierung fehlerhaft wäre. Merksatz: **eine
    Mutations-Gegenprobe muss an einem Fall ansetzen, der den mutierten
    Zweig überhaupt erreicht.**
  - Schicht: Kern.

- **AC-A10:** Given mehrere gültige Registereinträge derselben
  Gefahrenklasse/desselben Orts mit UNTERSCHIEDLICHER Dringlichkeit, When
  `_find_matching_entry` aufgerufen wird, Then liefert sie den Eintrag mit
  der HÖCHSTEN Dringlichkeit als Treffer, nicht den zuerst im Register
  gefundenen.
  - Test: drei Kandidaten in nicht-sortierter Registrierungsreihenfolge
    (MODERATE, HIGH, LOW), Match liefert den HIGH-Eintrag.
  - Schicht: Kern.

- **AC-A11:** Given die Funktionssignaturen von `check_event_identity_gate`,
  `record_event_identity` und `resolve_hazard_class` nach Abschluss dieser
  Scheibe, When man sie inspiziert, Then sind sie UNVERÄNDERT gegenüber
  S4b-1 — kein neuer Parameter wurde ergänzt.
  - Test: bestehender Signatur-Wächter
    `test_compare_radar_alert_event_identity.py:842-882` bleibt
    unverändert grün.
  - Schicht: Kern.

- **AC-A12:** Given zwei verschiedene Nutzer mit je einem Trip gleicher
  Kennung, When Nutzer A eine amtliche Meldung registriert und Nutzer B
  unabhängig davon einen Nowcast desselben Ereignisses auslöst, Then wirkt
  A's Registereintrag NICHT auf B's Gate-Ergebnis — B erhält seine eigene,
  unabhängige Entscheidung (kein Rückfall auf `"default"`).
  - Test: zwei Datenverzeichnisse (`user_id` A/B), gleiche Trip-Kennung, A
    registriert amtlich, B's Nowcast-Gate-Aufruf liefert `allowed=True,
    is_addendum=False` (kein Treffer, weil kein B-eigener Registereintrag
    existiert).
  - Schicht: Kern.

- **AC-A13 (NEU, dritte Korrektur — Zählnachweis):** Given eine
  vollständige Konstellations-Matrix (4 Quellen-Kombinationen
  official/nowcast × official/nowcast, jeweils kombiniert mit
  eskalierend/nicht-eskalierend UND V1-greift/V1-greift-nicht), When man
  die Zahl der Ergebnisse mit `allowed=True` VOR dieser Scheibe
  (simulierte S4b-1-Logik) gegen die Zahl NACH dieser Scheibe vergleicht,
  Then ist sie GLEICH — ausschließlich die Zahl der Ergebnisse mit
  `is_addendum=True` steigt (von 0 auf die Zahl der amtlich→Nowcast-mit-
  Eskalation-Fälle in der Matrix); die Gesamtzahl der `allowed=True`- bzw.
  `allowed=False`-Ergebnisse bleibt unverändert.
  - Test: parametrisierter Testlauf über die volle Matrix, zwei Zähler
    (Alt-Logik-Simulation vs. Neu-Logik), Assertion, dass die Differenz
    ausschließlich im `is_addendum`-Zähler liegt, nicht im `allowed`-
    Zähler.
  - Schicht: Kern.

**Teil B — Nachtragsmeldung (Trip-Pfad) + Ortsvergleich-Bestandsschutz**

- **AC-B1:** Given ein Gate-Ergebnis mit `is_addendum=True` am Trip-
  Nowcast-Pfad (`trip_alert.py:1437-1445`), When der Versandpfad läuft,
  Then wird die Meldung ZUGESTELLT (nicht unterdrückt, kein Eintrag in
  `alert_log` unter `not_delivered` über `REASON_EVENT_DUPLICATE`), mit
  gesetztem `addendum_reference` auf dem `AlertMessage`.
  - Test: Nowcast-Nachtrag-Fall (Eskalation, s. AC-A1) auslösen,
    Zustellung erfolgt, `AlertMessage.addendum_reference` ist gesetzt.
  - Schicht: Kern.

- **AC-B2:** Given eine Nowcast-Onset-Meldung mit gesetztem
  `addendum_reference`, When `render_email` (Einzel- ODER Bündel-Zweig)
  aufgerufen wird, Then enthält der Plain-Text UND der HTML-Teil die
  ausformulierte Zeile "Ergänzung zur amtlichen Warnung von {HH:MM}" — bei
  `None` fehlt die Zeile vollständig, keine Leerzeile.
  - Test: zwei Fälle (gesetzt/ungesetzt) je Zweig, echte Renderer-Aufrufe,
    Assertion auf den vollständigen Zeileninhalt im Plain-Text.
  - Schicht: Kern.

- **AC-B3:** Given eine Nowcast-Onset-Meldung mit gesetztem
  `addendum_reference`, When `_render_telegram_onset` aufgerufen wird,
  Then enthält der Telegram-Body dieselbe ausformulierte Zeile als eigene
  Zeile vor dem bestehenden Detailtext.
  - Test: echter Renderer-Aufruf mit/ohne `addendum_reference`.
  - Schicht: Kern.

- **AC-B4:** Given eine Nowcast-Onset-Meldung mit gesetztem
  `addendum_reference`, When `render_sms` aufgerufen wird, Then beginnt der
  resultierende SMS-Text mit dem Präfix `"Erg "`, gefolgt vom sonst
  unveränderten Kern-Text.
  - Test: Vergleich mit dem Text OHNE `addendum_reference` (identischer
    Rest nach dem Präfix).
  - Schicht: Kern.

- **AC-B5:** Given eine Nowcast-Meldung mit gesetztem `addendum_reference`
  UND `telegram_style="kurzform"`, When der Versand über
  `NotificationService` läuft, Then ist der an Telegram gesendete
  Nachrichtentext BYTE-IDENTISCH zum SMS-Text — inklusive des `"Erg
  "`-Präfix.
  - Test: echter `NotificationService`-Lauf mit Telegram-/SMS-Stub
    (Muster `test_telegram_kurzstil_trip_alert.py`), Payload-Text-
    Vergleich.
  - Schicht: Kern.

- **AC-B6:** Given eine Nowcast-Meldung mit gesetztem `addendum_reference`
  UND aktiviertem Premium-SMS-Kanal, When der Versand läuft, Then trägt der
  an `PremiumSmsOutput` übergebene Text ebenfalls das `"Erg "`-Präfix
  (derselbe Renderer-Output wie SMS, kein separater Pfad).
  - Test: `PremiumSmsOutput`-Stub, Payload-Text enthält das Präfix,
    identisch zum parallel geprüften SMS-Text desselben Laufs.
  - Schicht: Kern.

- **AC-B7:** Given den längsten realistischen Nachtragsfall — eine
  Nowcast-Onset-Meldung mit maximaler Ortsbezeichnung und vollem
  Zeitstempel, plus dem `"Erg "`-Präfix, When `render_sms` aufgerufen wird,
  Then ist das Ergebnis `<= 160` Zeichen (hartes Produktlimit) UND `<=
  limit` (der übergebene Render-Parameter, Default 140).
  - Test: Fixture mit maximaler Ortsbezeichnung, `addendum=True`,
    Längenprüfung auf dem tatsächlichen String.
  - Schicht: Kern.

- **AC-B8:** Given eine gewöhnliche Nowcast-Meldung OHNE Registertreffer
  (kein `addendum_reference` gesetzt), When irgendein Kanal gerendert wird,
  Then bleibt die Ausgabe BYTE-IDENTISCH zum Stand vor dieser Scheibe —
  keine neue Zeile, kein Präfix.
  - Test: bestehende Golden-/Fixture-Tests aller vier Kanäle laufen
    unverändert grün.
  - Schicht: Kern.

- **AC-B9:** Given einen gewöhnlichen Alarm OHNE vorherige Meldung, When
  der SMS-Text UND der Kurzstil-Telegram-Text erzeugt werden, Then
  enthalten beide das Nachtrags-Token `"Erg "` NICHT und bleiben
  zeichengleich zum heutigen Stand. Wird `test_alert_stufenwort.py::
  test_ac14_sms_bleibt_unveraendert_regressionswaechter` ODER
  `test_telegram_kurzstil_trip_alert.py:315` durch diese Scheibe rot, ist
  das ein BEFUND AN DER IMPLEMENTIERUNG (Token leckt in einen Fall ohne
  Treffer), nicht am Test — die Erwartung wird nicht aufgeweicht, sondern
  die Auslösebedingung des Tokens wird geschärft.
  - Test: beide genannten Bestandstests unverändert grün ausgeführt.
  - Schicht: Kern.

- **AC-B10:** Given eine Nowcast-Meldung mit gesetztem `addendum_reference`
  UND `telegram_style="kurzform"`, When man den Kurzstil-Telegram-Text
  gegen die S6-Zusicherungen prüft (kein `"Stand:"` im SMS-/Kurzstil-Text,
  Byte-Identität zur SMS bleibt gewahrt), Then gelten beide S6-
  Zusicherungen UNVERÄNDERT weiter — das neue Token bricht keine von
  beiden.
  - Test: bestehende S6-Wächter zu `AC-12` unverändert grün + 1 neuer Fall
    mit gesetztem `addendum_reference`, dieselben zwei Zusicherungen
    geprüft.
  - Schicht: Kern.

- **AC-B11:** Given das SMS-Präfix-Literal `_ADDENDUM_SMS_PREFIX`, When man
  seinen Zeichenbestand inspiziert, Then enthält es KEIN `"-"` — der
  Bindestrich bleibt ausschließlich Stufen-Fallback (`LEVELS.get(...,
  "-")`) und Pfeilbestandteil (`"->"`), ohne dritte Bedeutung.
  - Test: `"-" not in _ADDENDUM_SMS_PREFIX`, plus ein End-to-End-Fall, der
    zeigt, dass ein Nachtrags-Token UND ein Stufen-Fallback im selben SMS-
    Text gleichzeitig eindeutig lesbar bleiben (keine Kollision).
  - Schicht: Kern.

- **AC-B12:** Given den amtlichen Trip-Pfad (`trip_alert.py:1838-1849`)
  nach Abschluss dieser Scheibe, When man ihn gegen den S4b-1-Stand
  vergleicht, Then ist er UNVERÄNDERT — kein `addendum_reference` wird
  jemals auf einem `OfficialAlertNotice` gesetzt, der Filter-Loop verwirft
  weiterhin ausschließlich bei `allowed=False`.
  - Test: bestehende amtliche Trip-Batch-Tests (S4b-1 AC-17-Nachfolger)
    unverändert grün.
  - Schicht: Kern.

- **AC-B13:** Given eine per Nachtrag zugestellte Nowcast-Meldung, When
  `alert_log.append_entry` aufgerufen wird, Then enthält der Protokoll-
  Eintrag die additiven Felder zur Nachtrags-Markierung (`is_addendum`,
  referenzierter Zeitpunkt) — ein Eintrag OHNE Nachtrag (Normalfall oder
  Alt-Eintrag) bleibt schema-identisch zum Bestand.
  - Test: zwei Fälle (Nachtrag/normal) im selben Testmodul, JSON-Struktur
    verglichen.
  - Schicht: Kern.

- **AC-B14:** Given eine Konstellation, die am Trip-Pfad zum Nachtrag
  würde (amtlich registriert, Nowcast danach MIT Eskalation), When
  dieselbe Konstellation über den Ortsvergleich-Nowcast-Pfad
  (`compare_radar_alert.py`) läuft, Then wird die Meldung wie eine
  gewöhnliche Voll-Zustellung behandelt — kein `addendum_reference` wird
  irgendwo gesetzt, kein Compare-Renderer zeigt einen Nachtrags-Hinweis,
  der Effekt ist identisch zum Stand vor dieser Scheibe.
  - Test: identische Registereintrag-/Anfrage-Parameter wie im Trip-
    Nachtrag-Fall (AC-B1), aber über den Compare-Aufruf, resultierender
    Zustellungs-Effekt ist byte-identisch zum Vor-#2018-Stand; PLUS
    bestehende Ortsvergleich-Nowcast-/-amtlich-Tests (S4b-2/#1917)
    unverändert grün.
  - Schicht: Kern.

- **AC-B15 (NEU GEFASST, vierte Korrektur):** Given das rohe Gate-Ergebnis
  für die in AC-B14 beschriebene Konstellation (`identity_gate.allowed=
  True`, `identity_gate.is_addendum=True`), When der Ortsvergleich-Nowcast-
  Pfad (`compare_radar_alert.py`) damit läuft, Then gilt alles drei: (a)
  das Rohergebnis trägt tatsächlich `allowed=True` UND `is_addendum=True`,
  (b) der Ort wird TROTZDEM voll zugestellt — er bleibt in
  `allowed_triggered`, es entsteht KEIN `append_suppressed_entry`-Eintrag,
  die Zahl der zugestellten Orte ist identisch zum Vor-#2018-Stand, und (c)
  in KEINEM Compare-Ausgabetext und auf keinem Compare-Objekt taucht eine
  Nachtrags-Markierung oder ein `addendum_reference` auf.
  - Test: echter Compare-Lauf mit präpariertem amtlichem Registereintrag;
    (a) ist bis zum Abschluss von Teil A rot, (b) und (c) sind
    Bestandsschutz-Wächter. Teilzusicherung (c) ist der eigentliche Schutz
    gegen einen künftigen Compare-Umbau, der `is_addendum` auswertet und
    eine Ortsvergleich-eigene Nachtragsdarstellung erzeugt — sie wird rot,
    sobald so etwas im Ausgabetext erscheint.
  - **Ausdrücklich NICHT geprüft wird die Freigabe-Bedingung als Literal.**
    Die frühere Fassung dieses AC verlangte `identity_gate.allowed and not
    identity_gate.is_addendum`; das ist zurückgenommen (B0, Korrektur 4),
    weil diese Bedingung eine heute zugestellte Meldung unterdrückt und
    damit die harte Mengen-Invariante bricht. Die Bedingung bleibt
    `identity_gate.allowed`.
  - Schicht: Kern.

**Teil C — Ehrlicher Cooldown-Satz**

- **AC-C1:** Given eine Onset-Meldung mit gesetztem `cooldown_display`,
  When `render_email` (Einzel- ODER Bündel-Zweig) aufgerufen wird, Then
  enthält der Plain-Text sowohl den bestehenden Substring "höchstens
  einmal in" ALS AUCH einen neuen Zusatz, der klarstellt, dass der
  Cooldown NICHT quellenübergreifend gilt.
  - Test: neuer Substring-Test auf den Zusatztext, PLUS alle vier
    bestehenden Substring-Wächter (S. Wächter-Tabelle) bleiben unverändert
    grün.
  - **Auflage (Korrektur 5, präzisiert durch Korrektur 6):** Der Zusatz
    steht in DERSELBEN Klartext-Zeile wie der bestehende Satz (Leerzeichen
    als Fuge), nicht als eigene Zeile.
    **Richtigstellung:** Korrektur 5 behauptete, eine eigene Zeile kippe
    BEIDE Reihenfolge-Wächter. Am Code gemessen (Adversary-Gegenprobe,
    2026-08-21) trifft das nur auf
    `test_alert_mail_body_alignment.py:135` zu.
    `test_official_alert_plaintext_part.py:113-126` bleibt grün, weil sein
    Klartext-Klassifizierer jede Zeile ignoriert, die keines seiner vier
    festen Muster trifft — unabhängig von der Zeilenposition. Die Auflage
    bleibt fachlich gültig; der fehlende Schutz wird durch einen eigenen
    Wächter im Klartext-Pfad ergänzt (die Zeile mit „höchstens einmal in"
    muss auch „greift dieser Cooldown nicht" enthalten), statt die Auflage
    abzuschwächen.
  - Schicht: Kern.

- **AC-C2 (präzisiert, Korrektur 5):** Given den bit-eingefrorenen
  Golden-Test `test_multi_location_onset_alert.py`, When diese Scheibe
  abgeschlossen ist, Then sind BEIDE Konstanten, die den Cooldown-Satz
  tragen, bewusst auf den neuen Wortlaut aktualisiert — `EXPECTED_PLAIN`
  (Zeile ~47) UND `EXPECTED_HTML` (Zeile ~88) — als EINZIGE angefasste
  Golden-Datei.
  - Test: `test_multi_location_onset_alert.py` grün mit beiden
    aktualisierten Konstanten. Ein nur in `EXPECTED_PLAIN` gepflegter
    Stand lässt den Test dauerhaft rot und gilt als unfertig.
  - Schicht: Kern.

- **AC-C3:** Given den Commit-Verlauf dieser Scheibe, When man ihn
  inspiziert, Then liegt der Rebase auf den gelandeten Stand von #1948 S6
  (`cba7ffa3`) und #2009 (`d7fad756`) VOR dem ersten Commit, der
  `render.py` inhaltlich ändert.
  - Test: `# doc-compliance-test` — Commit-Reihenfolge im Changelog dieser
    Spec dokumentiert.
  - Schicht: Kern.

**Dokumentation**

- **AC-D1:** Given den ADR-0021-Nachtrag aus S4b-1/S4b-2, When diese
  Scheibe abgeschlossen ist, Then trägt ADR-0021 einen weiteren, datierten
  Nachtrag mit Bezug auf "#2018", der festhält, dass die Ereignis-
  Identität-Prüfung seither einen dritten, GERICHTETEN UND
  MENGENERHALTENDEN Ausgang kennt (zustellen / als Nachtrag zustellen NUR
  amtlich→Nowcast MIT Eskalation / unterdrücken in jeder anderen
  Konstellation, einschließlich der stillen amtlich→Nowcast-Fälle) — ohne
  die S4b-1/S4b-2-Aussagen zu widerrufen (deren Beschreibung des Registers
  und der Ortsvergleich-Verdrahtung bleibt gültig; der Ortsvergleich
  bleibt zusätzlich explizit unverändert, s. Nicht-Ziele).
  - Test: `tests/test_adr_index_drift.py` plus manuelle Sichtprüfung des
    Nachtrag-Absatzes, datiert nach 2026-08-21.
  - Schicht: Kern.

## Known Limitations

- **Die Gegenrichtung (amtlich nach Nowcast) bleibt ungenauer als sie
  fachlich sein könnte** — eine amtliche Warnung, die auf einen präzisen
  Nowcast folgt, bleibt unterdrückt statt als (grobe) Bestätigung
  zugestellt zu werden. Bewusst so belassen (s. Nicht-Ziele) — eigene
  PO-Entscheidung nötig für eine Änderung.
- **Stille Konstellationen amtlich→Nowcast bleiben still** — ein nicht-
  konvektiver Nowcast nach einer gleich/höherstufigen amtlichen Warnung
  oder ein konvektiver Nowcast nach amtlich ROT bleibt weiterhin
  unterdrückt, bekommt KEINEN Nachtrag. Bewusst so belassen — der PO hat
  nur die Form einer ohnehin stattfindenden Zustellung geändert, nicht das
  Ob.
- **Ortsvergleich bekommt keine eigene Nachtragsmeldung** — sein Code
  bleibt unangetastet (Korrektur 4), die Wächter AC-B14/AC-B15 sichern
  das ab. Das löst das ursprüngliche Ticket-Problem für den Ortsvergleich
  NICHT (der ohnehin PO-zurückgestellt ist).
- **Der Nachtragstext nennt bewusst keine Gewitterstufe** — sollte eine
  künftige Iteration das ändern wollen, MUSS das Wort aus `THUNDER_LABEL_DE`
  kommen (#1480-Wächter), nie lokal kopiert werden.
- **Änderungsalarm (Δ) bleibt außerhalb dieser Scheibe** (S4b-3, weiterhin
  offen) — der bestehende Doppel-Alert-Guard bleibt die einzige Absicherung
  für diese Paarung.
- Ein Rückbau des dritten Ausgangs, eine versehentliche Ausweitung auf die
  Gegenrichtung, ODER eine versehentliche Ausweitung auf stille
  Konstellationen ist mit Verhaltenstests NICHT vollständig automatisch
  fangbar außerhalb der expliziten Mutations-Gegenproben (AC-A8, AC-A9) —
  struktureller Schutz liegt zusätzlich in Code-Review und PO-Bindung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0021 (geteilter Auswertungskern) bekommt
  einen weiteren Nachtrag im Anschluss an die S4b-1/S4b-2-Nachträge.
- **Rationale:** Die gerichtete, mengenerhaltende Ereignis-Identität-
  Prüfung ist konsequente Fortsetzung des in ADR-0021 etablierten Musters
  — derselbe geteilte Baustein bekommt einen dritten, differenzierteren
  Ausgang, statt eines zweiten Bausteins. Neu ist, dass die Entscheidung
  erstmals ASYMMETRISCH nach Richtung ist (amtlich→Nowcast anders
  behandelt als Nowcast→amtlich) UND dass der neue Ausgang strikt auf
  Zustellungen beschränkt ist, die ohnehin stattgefunden hätten (Form
  statt Menge) — eine bewusste fachliche Differenzierung, kein
  technischer Kompromiss. Der Ortsvergleich bleibt bewusst außen vor
  (Bestandsschutz statt Feature-Parität) — kein neues Architekturprinzip,
  aber eine Erweiterung des Rückgabewert-Vokabulars innerhalb des
  bestehenden Bausteins.

## Changelog

- 2026-08-21: Initiale Spec. Ursachenkette, Optionsbewertung und
  PO-Entscheid (Variante c, Nachtragsmeldung statt Unterdrückung) aus
  `docs/context/fix-2018-cooldown-quellenuebergreifend.md`. Design der
  SMS-Kompakt-Kennzeichnung, Bindestrich-Kollisionsvermeidung und der
  beiden Regressionswächter aus zwei Koordinator-Nachträgen eingearbeitet
  (Telegram-Kurzstil sendet SMS-Text, `_ADDENDUM_SMS_PREFIX` ohne `"-"`).
- 2026-08-21 (Korrektur 1+2, gleicher Tag): **Korrektur 1:** der dritte
  Ausgang ist GERICHTET — nur amtlich→Nowcast wird zum Nachtrag, die
  Gegenrichtung (Kernfall aus #1467 S4b, `test_alert_gate.py:757-793`)
  bleibt vollständig unangetastet, weil dafür kein PO-Entscheid vorliegt.
  Die dadurch überflüssig gewordene explizite "amtlich ROT bricht
  durch"-Regel (V2b) entfiel zugunsten einer strukturellen Garantie.
  **Korrektur 2:** Ortsvergleich fliegt aus der Lieferung —
  `compare_radar_alert.py`/`compare_official_alert.py` bekommen keine neue
  Nachtrags-Logik; eine minimale Bestandsschutz-Bedingung
  (`allowed and not is_addendum` statt `allowed`) wurde ergänzt, weil
  reines Nichtstun die geforderte Verhaltensgleichheit nicht garantiert
  hätte.
- 2026-08-21 (Korrektur 3, gleicher Tag, Version 1.2): **Ein echter Fehler**
  in der Fassung nach Korrektur 1+2, aufgedeckt durch eine Rückfrage der
  Parallelsitzung #2020 (Frage: ändert diese Scheibe die Zahl ausgelöster
  Meldungen?). Der Nachtrags-Zweig ließ die V2-Prüfung (`exceeds`)
  ersatzlos entfallen und lieferte bedingungslos `is_addendum=True` — das
  hätte auch STILLE Konstellationen (nicht-konvektiver Nowcast nach
  gleich/höherstufiger amtlicher Warnung; konvektiver Nowcast nach
  amtlicher ROT-Warnung, jeweils `exceeds` `False`) in Nachrichten
  verwandelt, wo heute keine kommen — eine unbeabsichtigte Ausweitung über
  den PO-Entscheid hinaus (der PO hat entschieden, dass aus zwei vollen
  Alarmen einer plus ein Nachtrag wird, nicht, dass aus Stille ein
  Nachtrag wird). Korrigiert: `exceeds` bleibt in JEDER Konstellation die
  maßgebliche erste Prüfung; in der Nachtrags-Richtung ändert ein
  positives Ergebnis nur noch die FORM (Nachtrag statt Voll-Alarm), nie
  mehr das OB. Neue Invariante "Zustellmenge bleibt identisch" (prominent),
  neues AC-A8 (Stille bleibt Stille, mit Mutations-Gegenprobe) und neues
  AC-A13 (Zählnachweis über die volle Konstellations-Matrix) ergänzt.
  Zeilennummern in `src/output/renderers/alert/render.py` per Text-Suche
  gegen den Arbeitsbaum (nach #1948 S6 `cba7ffa3` und #2009 `d7fad756`)
  neu verifiziert, alle übrigen Fundstellen gegen den Arbeitsbaum zum
  Zeitpunkt der Spec-Erstellung verifiziert.
- 2026-08-21 (Korrektur 4, gleicher Tag, Version 1.3, **während der
  TDD-RED-Phase**): **Zweiter echter Fehler**, aufgedeckt vom RED-Agenten
  beim Schreiben der Ortsvergleich-Tests und am Code gegengeprüft. Die in
  Korrektur 2 ergänzte Bestandsschutz-Bedingung
  (`identity_gate.allowed and not identity_gate.is_addendum`) bewirkt das
  GEGENTEIL ihrer eigenen Begründung: für die Konstellation "amtlich
  registriert, Ortsvergleich-Nowcast danach MIT Eskalation" liefert das
  Gate heute über `exceeds` ein `_ALLOWED` (`alert_gate.py:605`), der Ort
  landet in `allowed_triggered` (`compare_radar_alert.py:229`) und wird
  ZUGESTELLT. Nach Teil A trägt dasselbe Ergebnis zusätzlich
  `is_addendum=True`; `not is_addendum` hätte den Ort damit in den
  `else`-Zweig fallen lassen (inklusive `append_suppressed_entry`) und
  diese heute zugestellte Meldung künftig UNTERDRÜCKT — eine
  Mengenänderung im Ortsvergleich, also genau das, was die in Korrektur 3
  eingeführte harte Invariante ("Zustellmenge bleibt identisch",
  PO-Entscheid) verbietet, und ein direkter Widerspruch zu AC-B14
  ("Ortsvergleich verhält sich exakt unverändert"). Korrigiert: die
  Bedingung ist ersatzlos zurückgenommen, `compare_radar_alert.py:229` und
  `compare_official_alert.py:210` behalten `identity_gate.allowed`; der
  Ortsvergleich bekommt in dieser Scheibe NULL Produktivänderung. Der
  ursprünglich damit bezweckte Schutz (kein künftiger Compare-Umbau
  erzeugt unbemerkt eine Ortsvergleich-eigene Nachtragsdarstellung) wandert
  in AC-B15, neu gefasst als reiner VERHALTENS-Wächter: Rohergebnis trägt
  `is_addendum=True`, Compare stellt trotzdem voll zu, und in keinem
  Compare-Ausgabetext taucht je eine Nachtrags-Markierung auf. Damit ist
  derselbe Schutz ohne jede Mengenänderung zu haben. Entschieden vom
  Coordinator, nicht neu beim PO vorgelegt: der PO-Entscheid zur
  Zustellmenge (Korrektur 3) lag bereits vor und ist eindeutig — die
  AC-Formulierung verletzte ihn, nicht umgekehrt.
- 2026-08-21 (Korrektur 5, gleicher Tag, Version 1.4, **während der
  TDD-RED-Phase**): Zwei Ungenauigkeiten in Teil C, vom RED-Agenten am Code
  aufgedeckt und gegengeprüft. **(a)** Die Behauptung "`EXPECTED_PLAIN` ist
  das einzige Golden mit der Cooldown-Zeile" ist falsch:
  `tests/tdd/test_multi_location_onset_alert.py` trägt den Satz zweimal —
  `EXPECTED_PLAIN` (~47) und `EXPECTED_HTML` (~88) —, beide werden im
  selben Test byte-identisch geprüft. Beide werden aktualisiert; das
  erweitert den freigegebenen Umfang nicht (dieselbe Aussage, dieselbe
  Datei, zwei Darstellungen), ein halb gepflegtes Golden bliebe sonst nach
  GREEN dauerhaft rot. **(b)** Neue bindende Auflage: der Cooldown-Zusatz
  MUSS in derselben Klartext-Zeile stehen (Leerzeichen als Fuge) bzw. im
  bestehenden `<span>`-Block der HTML-Fassung — eine eigene Zeile kippt die
  zeilen-/blockweisen Reihenfolge-Wächter
  `test_official_alert_plaintext_part.py:121` und
  `test_alert_mail_body_alignment.py:135`. Beide als Wächter in die Tabelle
  aufgenommen. Ausserdem festgelegt: `alert_log`-Feldnamen für AC-B13 sind
  `is_addendum` (bool) und `addendum_reported_at` (ISO-String), genau
  diese zwei Felder kommen hinzu.
- 2026-08-21 (Korrektur 6, gleicher Tag, Version 1.5, **nach der
  Adversary-Prüfung**): Drei Befunde des `implementation-validator`
  eingearbeitet. **(a)** Die Mutations-Gegenprobe von AC-A9 nannte einen
  Test, der bei dieser Mutation **strukturell nie** rot werden kann (im
  Kernfall sind beide Dringlichkeiten `HIGH`, `exceeds` ist bereits
  `False`, der mutierte Zweig wird nie erreicht). Testreferenz auf den
  parametrisierten AC-A9-Fall `[nowcast-nowcast-False]` korrigiert, der
  den Zweig tatsächlich erreicht und bei der Mutation rot wird. Merksatz
  ergänzt: eine Gegenprobe muss an einem Fall ansetzen, der den mutierten
  Zweig überhaupt erreicht. **(b)** Die Korrektur-5-Behauptung, eine eigene
  Cooldown-Zeile kippe BEIDE Reihenfolge-Wächter, gilt nur für
  `test_alert_mail_body_alignment.py`; der Klartext-Wächter bleibt grün.
  Statt die Auflage abzuschwächen wird ein eigener Klartext-Wächter
  ergänzt. **(c)** AC-D1 (ADR-0021-Nachtrag) war nicht geliefert —
  `test_adr_index_drift.py` prüft nur Index↔Datei-Konsistenz, nicht
  Inhalt, und blieb deshalb grün. Nachgeholt. Zusätzlich geschlossen:
  der spec-mandierte Fail-soft-Vertrag aus B2 (`addendum_reported_at`
  fehlt ⇒ Uhrzeit entfällt ersatzlos) war am WIRKORT in `trip_alert.py`
  durch keinen Test bewacht — Entfernen des Wächters machte keinen von
  101 Tests rot; ein End-to-End-Regressionstest mit Gegenprobe ist
  ergänzt.
