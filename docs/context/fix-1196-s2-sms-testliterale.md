# Kontext: fix-1196-s2-sms-testliterale

Scheibe 2 von #1196 (Testsuite-Sanierung). Nachfolger von Scheibe 1 (Commit `10394e10`,
21 Tests, danach 18 rot).

## Analysis

### Type

Bug-Meldung — **widerlegt**. Ergebnis ist Test-Wartung, kein Produktivfehler.

Gemeldet war: Die Trip-SMS zeige bei einer Datenlücke im Zielzeitfenster `-`
("nichts los") statt `?` ("unbekannt") — eine Fehl-Entwarnung.

**Gemessen am 2026-08-03:** Die `?`-Umstellung funktioniert in allen fünf Fällen
korrekt. Sie wurde im Juli mit #1328 und #1331 eingebaut. Die Fehlermeldungen der
Tests belegen es selbst — `R? PR? W? G? TH:?` erscheint genau wie erwartet.

```
Test erwartet:   E7: D20 R? PR? W? G? TH:? TH+:-
SMS liefert:     E7: K15 D15 FK- FD- R? PR? W? G? TH:? TH+:-
                      ^^^^^^^^^^^^^^ hieran scheitert der literale Vergleich
```

Ursache: `K` (#1417) und `FN`/`FK`/`FD` (#1410) kamen Ende Juli **spezifiziert** dazu
(`docs/reference/sms_format.md` Changelog v2.12/v2.13). Die literalen
Erwartungsstrings der Tests wurden nie nachgezogen. Kein neues Issue.

### Gemessener Konfigurations-Stand

`build_default_display_config()` liefert: `temperature` an, `wind_chill` an,
`precipitation` an, `rain_probability` aus.

| Kürzel | Folgt der Metrik-Auswahl? | Beleg |
|---|---|---|
| `FN`/`FK`/`FD` (gefühlt) | **ja, korrekt** | `trip_report.py:277-287`, #1410 §6 |
| `K`/`D` (gemessen) | **nein, unbedingt** | `builder.py:237-238` → **#1415**, offen |

#1415 ist PO-bekannt und am 2026-07-29 mit einer echt zugestellten Nachricht belegt
(`E3: K13 D16 FK13 FD16 …` bei abgewählter Temperatur). PO-Entscheidung damals: kein
großer Umbau. **Ausdrücklich nicht Teil dieser Scheibe** — als Weg B danach geplant.

Folge für die Testreparatur: Solange #1415 offen ist, müssen die Erwartungsstrings
`K`/`D` enthalten, unabhängig von der Konfiguration.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `tests/tdd/test_sms_daywindow_aggregation.py` | MODIFY | 4 Assertions (767, 880, 953, 981) + Docstring `_dc()` (236-239, nennt falsche Defaults) |
| `tests/tdd/test_sms_unknown_on_missing_data.py` | MODIFY | 1 Assertion (163); ruft die Low-Level-API `SMSTripFormatter().format_sms()` ohne `display_config` auf — dort sind alle Kürzel vertragsgemäß ungegated |

**Kein Produktivcode.** Der ist spec-konform (sms_format.md v2.13).

### Scope Assessment

- Dateien: 2
- Geschätzte LoC: ~+15/-10
- Risiko: **LOW** — reine Testdateien, keine Laufzeitwirkung

### Technical Approach

PO-Vorgabe (wörtlich, 2026-08-03): *„Es soll doch getestet werden, was konfiguriert
wurde. Gefühlte Temperatur soll nur in der SMS erscheinen, wenn sie konfiguriert
wurde."*

Daraus folgt der bessere Schnitt: Die Tests setzen ihre Konfiguration **ausdrücklich**
und prüfen, dass genau das erscheint — statt das Literal bloß um `K15 D15 FK- FD-` zu
verlängern. Wer die gefühlte Temperatur nicht braucht, schaltet sie ab; dass sie dann
verschwindet, ist selbst eine Zusicherung.

Der Prüfgegenstand bleibt die Datenlücken-Kennzeichnung (`?` statt `-`). Diese
Zusicherung darf durch die Reparatur **nicht schwächer** werden.

### Open Questions

Keine. PO hat die Reihenfolge entschieden: erst diese Scheibe (A), danach #1415 (B).
