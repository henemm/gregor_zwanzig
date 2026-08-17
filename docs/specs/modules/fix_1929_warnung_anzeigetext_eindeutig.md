---
entity_id: fix_1929_warnung_anzeigetext_eindeutig
type: bugfix
created: 2026-08-17
updated: 2026-08-17
status: approved
version: "1.1"
tags: [alerts, sms, official-alerts]
workflow: fix-1929-warnung-anzeigetext-eindeutig
---

# Warnung: SMS-Kurz-Zeit-Token bekommt eindeutigen Anzeigetext (Scheibe 1)

> **Hinweis zur Fassung (2026-08-17):** Diese Datei ist eine **Rekonstruktion**. Der Worktree mit der
> Originalfassung wurde durch ein fremdes `git worktree remove --force` gelöscht, bevor der erste
> Commit erfolgt war (der Branch trug keine Commits und galt deshalb fälschlich als „merged"). Inhalt,
> ACs und alle Korrekturvermerke sind inhaltlich identisch wiederhergestellt; Formulierungen einzelner
> Fließtextpassagen können minimal abweichen. Der **Produktivstand** ist dagegen bitgenau
> wiederhergestellt (MD5-Abgleich gegen die externe Sicherungskopie).

## Approval

- [x] Approved — PO-Freigabe 2026-08-17 („approved"). Freigegeben wurden die 7 ACs, der PO-Entscheid
  „beide Lücken härten" (Minuten ≠ `:00` **und** Datum im Ganztags-Token) sowie die ausdrückliche
  Feststellung, dass diese Scheibe den Vorfall vom 2026-08-16 **nicht** behebt.
- [x] Nachtrags-Entscheid 2026-08-17 (F002): Das Ganztags-Token trägt **Tag und Monat** (`Sa14.02.`).
  Abgestimmt mit der #1948-Sitzung; die 7 ACs bleiben unverändert, AC-4 wird nur präzisiert.

## Purpose

Zwei amtliche Warnmeldungen mit **verschiedenen** Melde-Zeitfenstern dürfen innerhalb **einer**
SMS/Premium-SMS/Telegram-Kurzform-Nachricht nicht denselben Anzeigetext tragen. Der Kurz-Zeit-Token
`_tag_time()` formatierte bisher nur mit `%H` (Stunde) und im Ganztags-Fall nur mit dem
Wochentagsnamen — beides trug erreichbare Kollisionsquellen. Diese Spec härtet beide, ohne den
Zeichenpreis der Nachricht unnötig zu erhöhen.

Bezug: Issue **#1929**. Ursprung **#1657** (geschlossen — klammerte den Anzeigetext als „Aspekt (c)"
aus). Die Ursachenaufklärung des Vorfalls vom 2026-08-16 läuft unter **#1948** (dorthin ist das
frühere Folge-Issue #1944 als Teilscheibe aufgegangen).

## Was diese Spec NICHT löst

**Diese Scheibe behebt den gemeldeten Vorfall vom 2026-08-16 (Trip `5f534011`, KHW 403) NICHT.** Die
drei Fenster jenes Vorfalls (`13:00–14:00Z`, `14:00–15:00Z`, `11:00–20:00Z`) rendern bereits heute als
drei **verschiedene** Tokens. Der berichtete identische Text ist folglich **keine** Token-Kollision.
Scheibe 1 ist **vorbeugende Härtung**; die Ursachenaufklärung läuft getrennt unter #1948.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `_tag_hour(d)` (neu) und `_tag_time(alert, tz=None)`; Prüfung am Ausgabe-String von
  `render_official_alert_sms(...)`

## Betroffene Kanäle

Ein Renderer, drei Ausgaben — alle rufen `render_official_alert_sms` auf:

| Kanal | Kollisionsgefahr |
|---|---|
| SMS | ja |
| Premium-SMS (Garmin inReach, Satellit, kostenpflichtig) | ja |
| Telegram (Stil `kurzform`) | ja |

**Budget: 140 Zeichen** (`render_official_alert_sms(..., limit: int = 140)`), kein produktiver Aufrufer
übergibt einen abweichenden Wert.

**Nicht betroffen:** E-Mail (HTML + Plain) und Telegram-Standard nutzen `_format_validity` mit `%H:%M`
— dort sind Minuten bereits enthalten, keine Kollisionsgefahr, **nicht angefasst**.

## Implementation Details

**Regel 1 — Minuten nur wenn ≠ `:00`, in beiden Stundenzweigen:**

Zwei stundengleiche Fenster rendern nur dann identisch, wenn beide Grenzen auf volle Stunden fallen —
dann sind es aber dieselben Uhrzeiten, also dieselbe Warnung. Die Regel ist damit kontextfrei und pro
Token für sich entscheidbar (kein Vergleich mit anderen Tokens der Nachricht, kein Zustand über die
Token-Schleife). `15:00–21:00` bleibt `Sa15-21`; `15:20–21:40` wird `Sa15:20-21:40`. Gilt für **beide
Grenzen** in **beiden** Zweigen (gleicher Tag, Tagesübergang) — umgesetzt über die Hilfsfunktion
`_tag_hour`.

Verworfene Alternativen: Minuten unbedingt anhängen (bricht alle Stundenzweig-Pins ohne Zusatznutzen);
Minuten nur bei erkannter Kollision (braucht Zustand über die Token-Schleife, reihenfolgeabhängig ab
drei Tokens).

**Regel 2 — Ganztags-Token trägt Tag und Monat:**

Bei `(vf.hour, vf.minute, vt.hour, vt.minute) == (0, 0, 23, 59)` gab `_tag_time` bisher **nur** den
Wochentagsnamen zurück. Das Token trägt jetzt Tag **und** Monat: `Sa14.02.` statt `Sa` (+3 Zeichen
gegenüber der Tag-only-Variante, nur im Ganztags-Fall).

**Begründung — korrigiert nach dem Adversary-Finding F002:** Die ursprüngliche Fassung rechtfertigte
eine Tag-only-Angabe mit dem 15-Tage-Horizont von Open-Meteo. Das trägt **nicht**:

1. `valid_from`/`valid_to` amtlicher Warnungen stammen aus vier unabhängigen Quellen (Vigilance,
   MeteoAlarm, GeoSphere, DPC), nicht aus Open-Meteo. Der Alarm-Pfad prüft zudem die gesamte
   Restroute ohne Tagesdeckel (`trip_alert.py:1531-1538`, Fenstergrenze über
   `window_end_utc_exclusive()` in `src/app/day_window.py`).
2. Die Token-Kollision ist trotzdem kaum erreichbar, aber aus einem **anderen** Grund als gedacht:
   Zwei Ganztags-Tokens kollidieren nur bei gleichem Wochentag **und** gleichem Tag im Monat, also bei
   einem Abstand als Vielfaches von 7 Tagen — frühestens **28 Tage** (Februar→März; der Februar hat
   selbst 28 Tage und ist damit automatisch ein Vielfaches von 7).

**Folge:** Der Monat verhindert praktisch **keine** Kollision zweier Tokens in derselben Nachricht —
er macht das **einzelne** Token für den Leser eindeutig („welcher Samstag?"). Das war die
Entscheidungsgrundlage, abgestimmt mit #1948 („Eindeutigkeit schlägt Zeichenersparnis in vertretbarem
Rahmen"). Für die Referenztouren (KHW, GR20, bis ~15 Tage) ist die Kollision unerreichbar; für
mehrwöchige Touren bleibt sie selten, aber nicht strukturell ausgeschlossen.

**Nicht Teil dieser Spec:** Die #1948-Regel „Wochentag nur wenn Gültigkeit nicht heute" gilt laut
PO-Entscheid auch für amtliche Warnungen, wird hier aber **bewusst nicht** umgesetzt — sie kommt mit
der #1948-Scheibe und setzt auf dem hier gehärteten `_tag_time` auf.

**Wo die Zusicherung geprüft wird:**

Nicht an `_tag_time` isoliert — das liefert den Rohstring **vor** jeder Kürzung. Geprüft wird am
**fertigen Ausgabe-String** von `render_official_alert_sms`, weil danach die Kürzungskette greift
(`_sms_pack_with_fallback` mit vier Rückfallstufen; `_sms_pack` droppt ganze Tail-Tokens, sichtbar am
`+N`-Marker). Zu prüfende Eigenschaft: *für alle Zeit-Tokens, die im finalen SMS-String tatsächlich
erscheinen, ist kein Zeitabschnitt für zwei verschiedene Fenster identisch.* Per `+N` weggefallene
Tokens zählen ausdrücklich **nicht** als Verletzung.

## Out of Scope

- **Fall B — zwei getrennte, aufeinanderfolgende Nachrichten mit gleichem Text.** Nicht lösbar ohne
  Gedächtnis über den zuletzt gesendeten Text (`ThrottleStore.last_sent()` liefert nur ein `datetime`).
  Läuft unter #1948.
- **Sekunden:** `_tag_time` bezieht Sekunden nicht ein — folgenlos für dieses Token. Gebucht in #1199.
- **`None`-Fenster:** fehlendes `valid_from`/`valid_to` liefert `""` (vorbestehendes, gewolltes
  F003-Verhalten). Unverändert.
- **E-Mail und Telegram-Standard:** nutzen `_format_validity`, bereits minutengenau — nicht anfassen.

## Test Plan

Datei `tests/tdd/test_official_alert_time_token_uniqueness.py`, **12 Testfunktionen**:

1. **AC-1 Grundfall gleicher Tag** — `15:00–21:00` vs. `15:20–21:40`, Prüfung am finalen SMS-String.
   *Korrektur aus der RED-Messung:* Das ursprünglich vorgesehene Paar `15:20–20:50` taugt **nicht** —
   es rendert als `Sa15-20` gegen `Sa15-21` und kollidiert gar nicht. Die Kollision entsteht nur, wenn
   die **Stundenpaarung gleich bleibt**; „unterscheidet sich nur in den Minuten" ist notwendig, aber
   nicht hinreichend.
2. **AC-1 Einzelgrenzen** (2 Tests) — `vf` konstant/nur `vt` variiert und umgekehrt.
3. **AC-2 Tagesübergang** — `Fr22:15–Sa03:10` vs. `Fr22:30–Sa03:45`.
4. **AC-2 Einzelgrenzen** (2 Tests) — je eine Grenze konstant.
5. **AC-3 Nicht-Regression** — `15:00–21:00` bleibt bit-identisch `Sa15-21`.
6. **AC-4 Ganztags** — zwei Ganztags-Fenster am selben Wochentag verschiedener Wochen.
7. **F002 Monatsfall** — gleicher Tag im Monat in **verschiedenen** Monaten: `Sa 14.02.` gegen
   `Sa 14.03.2026` (beide Samstag). Vor der Änderung ergaben beide bit-identisch `Sa14.`.
8. **AC-5 Budgetdruck** — *Korrektur aus der RED-Messung:* mit nur **zwei** Warnungen ist AC-5
   strukturell nicht verletzbar, weil `_sms_pack` ein Token nur vollständig behält; bei Overflow
   bliebe höchstens eines übrig. Der stille Kollisions-Rest ist erst **ab drei** Warnungen erreichbar
   — das ist die Gefahrenzone.
9. **AC-6 Zeichengrenze** — kein Szenario über 140 Zeichen.
10. **AC-7 Bestandsverhalten** — `None`-Fenster liefert `""`, Sekunden weiterhin ignoriert.

**Einzelgrenzen-Tests sind Pflicht (Adversary-Finding F001):** Ein Test, der `vf` und `vt`
gleichzeitig variiert, verdeckt eine halbseitig kaputte Grenze vollständig — eine solche Mutation
blieb im Bestand über 223 Tests unsichtbar.

**Parser-Anforderung:** Die Token-Extraktion im Test muss altes **und** neues Format erfassen und eine
Positivkontrolle über die erwartete Tokenzahl führen — „nichts gefunden" muss ein Testfehler sein,
nie stilles Bestehen.

## Acceptance Criteria

- **AC-1:** Given zwei amtliche Warnungen mit identischem Hazard/Level/Label und Fenstern am gleichen
  Kalendertag, die sich nur in den Minuten unterscheiden (bei gleicher Stundenpaarung) / When
  `render_official_alert_sms` beide gemeinsam rendert / Then tragen die beiden Zeit-Tokens im finalen
  SMS-String unterscheidbare Minutenangaben.
- **AC-2:** Given zwei amtliche Warnungen mit Tagesübergangs-Fenstern (`vf.date() != vt.date()`), die
  sich nur in den Minuten unterscheiden / When gerendert wird / Then sind beide Zeit-Tokens im finalen
  String verschieden, nicht nur `_tag_time` isoliert betrachtet — und zwar auch dann, wenn sich **nur
  eine** der beiden Grenzen unterscheidet.
- **AC-3:** Given zwei volle-Stunden-Fenster ohne Minutenanteil (`:00` bei from und to) / When
  gerendert wird / Then bleibt der Kurz-Token unverändert im Format `<Tag><Std>-<Std>` ohne
  Minutenanhang, bit-identisch zum Bestand.
- **AC-4:** Given zwei Ganztags-Warnungen am selben Wochentag in unterschiedlichen Kalenderwochen /
  When gemeinsam gerendert wird / Then tragen beide Ganztags-Tokens im finalen String eine Tag-**und
  Monat**-Angabe (`Sa14.02.`) und sind textlich unterscheidbar.
- **AC-5:** Given eine Kollisionslage aus AC-1 mit **drei** Warnungen und einem überlangen Ortsnamen,
  der die Kürzungskette zum Droppen zwingt / When gerendert wird / Then ist im finalen Rückgabewert
  jedes verbliebene Zeit-Token eindeutig oder ein kollidierendes Token per `+N`-Marker vollständig
  entfernt, nie als kollidierender Rest sichtbar.
- **AC-6:** Given jedes der Szenarien aus AC-1, AC-2, AC-4 und AC-5 / When mit dem produktiven
  Default-Limit gerendert wird / Then überschreitet der zurückgegebene String niemals 140 Zeichen.
- **AC-7:** Given ein Fenster ohne `valid_from`/`valid_to` (DPC-Fall) oder mit Sekundenanteil ≠ 0 /
  When `_tag_time` aufgerufen wird / Then bleibt das bestehende Verhalten unverändert (leerer String
  bzw. Sekunden werden weiterhin ignoriert).

## Known Limitations

- Fall B (zwei getrennte Nachrichten, gleicher Text) bleibt ungelöst — #1948.
- Die Ganztags-Eindeutigkeit ist keine vom Code erzwungene Garantie: Zwei Ganztags-Fenster mit exakt
  einem Vielfachen von 28 Tagen Abstand *und* gleichem Tag im Monat kollidierten weiterhin. Für die
  Referenztouren unerreichbar, für mehrwöchige Touren selten, aber nicht ausgeschlossen.
- Sekunden-Ungenauigkeit (#1199) und der `None`-Fenster-Fall (F003) bleiben wie vorbestehend.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine dokumentierte Entscheidung legt das Weglassen von Minuten oder Datum im
  SMS-Kurz-Token fest; die archivierten Ursprungs-Specs definieren nur das Grobformat `<Tag>[<zeit>]`.
  Diese Änderung ist damit keine Abweichung von einer begründeten Architektur-Entscheidung und braucht
  kein Ablöse-ADR. Der Zeichenpreis wird hier erstmals explizit gemacht (AC-6).

## Bekannte Test-Auswirkung

Die Stundenzweig-Pins bleiben **unverändert grün**: alle Bestandsfixtures liegen auf `:00`-Minuten.

Die Datums-Regel verlängert jedes Ganztags-Token. **Real betroffen ist genau eine Stelle** —
`tests/tdd/test_official_alert_subject_label_fidelity.py` (`test_ac6_sms_unchanged`):
`"… HT ORANGE Fr ges.Route …"` → `"… HT ORANGE Fr10.07. ges.Route …"`. Die Assertion bleibt exakte
Volltext-Gleichheit; angepasst wurde nur der erwartete Text, kein Wächter aufgeweicht.

**Nicht betroffen** (entgegen der ursprünglichen Schätzung, die aus einem Zeilen-Grep statt einer
Messung stammte): `test_official_alert_channel_scope.py` (enthält **keine** Ganztags-Fixture,
`grep -c '23, 59'` → 0), `test_official_alert_template_render.py` (die genannten Zeilen gehören zum
Stundenzweig), `test_sms_official_alert_tokens.py` (prüft Gefahren-Kürzel, nicht den Zeit-Token).

## Abgrenzung zu #1948

`official_alerts.py` — `_tag_time` und der Zeit-Token-Pfad von `render_official_alert_sms` — gilt für
das #1948-Konzept als **durch diese Spec entschieden** und wird dort nicht neu aufgerollt. Das hier
festgelegte Format wird als „WANN"-Baustein amtlicher Warnungen **übernommen**; #1948 baut die
Struktur drumherum um (Kopf ohne Trip-Name, Behörden-Stufe auf die Briefing-Stufenleiter
`-`/`L`/`M`/`H`, Ortskopf vorne — Leitsatz „Format folgt Phänomen, nicht Quelle"). Abgestimmt mit der
#1948-Sitzung am 2026-08-17.

## Changelog

- 2026-08-17: Initial spec created
- 2026-08-17: Testplan-Korrekturen aus der RED-Messung (AC-1-Vergleichswert; AC-5 braucht drei Notices)
- 2026-08-17: F002-Entscheid — Ganztags-Token trägt Tag **und** Monat; Begründung korrigiert (28-Tage-
  Kalendermathematik statt Provider-Horizont); Einzelgrenzen-Tests aus F001 ergänzt
- 2026-08-17: Rekonstruktion nach Worktree-Verlust (siehe Hinweis am Dateikopf)
