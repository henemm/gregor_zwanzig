# Kontext: feat-1481-pendant-sperre

Issue: [#1481](https://github.com/henemm/gregor_zwanzig/issues/1481) — letzte offene Scheibe.

## Worum es geht

Eine **neu angelegte** Datei in einem einseitigen Bereich (nur Vergleich **oder** nur Trip)
blockiert den Commit. Zwei Auswege, beide ohne Rückfrage: die Datei liegt in einem geteilten
Bereich, **oder** sie trägt im Kopf eine Begründungszeile `gz-eigenstaendig: <fachlicher Grund>`.

Der Ausweg verhindert nichts. Er macht die Entscheidung **im Änderungssatz zitierbar** — bei
#1459 D3 hätte dort stehen müssen „zwei getrennte Felder, weil sonst die Go-Seite mit angefasst
werden müsste"; genau dieser Satz blieb unausgesprochen, und die Doppelung fiel erst Wochen
später auf.

## Stand des Tickets

| Scheibe | Stand |
|---|---|
| A — Commit blockiert bei roten Tests der berührten Dateien | geliefert, `102451fe`, live |
| **Pendant-Sperre** | **diese Arbeit** |
| Abschluss-Hook nach dem PO-Kurzbefehl | vom PO gestrichen (2026-08-04) |
| Klon-Detektor (jscpd) | bewusst zurückgestellt bis A/B einen belegten Fang haben |

## Relevante Dateien

| Datei | Bedeutung |
|---|---|
| `.claude/hooks/touched_tests_gate.py` (389 Z.) | Scheibe A. Nächster Verwandter: Commit-Wächter, gleicher Exit-Vertrag, gleiche Fail-open-Regel |
| `.claude/hooks/test_naming_gate.py` (52 Z.) | **Nächstes Vorbild dem Umfang nach.** Sperrt ebenfalls nur NEUE Dateien nach Pfadmuster, mit Prüfdatum und fail-open. 52 Zeilen |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py:346` | Herkunft des Ausnahme-Musters: `_MARKER = re.compile(r"#\s*gz-main-path:(.*)$")`, Mindestlänge der Begründung |
| `.claude/settings.json:60-75` | Verdrahtung. `PreToolUse`-Einträge, getrennt nach `Bash` (Commit-Wächter) und `Write\|Edit` |
| `.claude/hooks/hook_utils.py` → Plugin | Liefert `is_git_subcommand` / `is_pure_git_command` |
| `docs/context/fix-1431b-rueckfall-entfernen.md` | Warum die Commit-Erkennung tokenbasiert sein muss |

## Bestehende Muster

**Commit erkennen: Aufrufform, nicht Wortlaut.** Seit #1431 (`65a0ea1e`) gibt es
`hook_utils.is_git_subcommand`. Die naive Prüfung `"git commit" in befehl` fällt auf
`grep -rn "git commit" …` herein und lässt sich mit `git -C <pfad> commit` umgehen.
Merkposten: **Scheibe A benutzt bei `touched_tests_gate.py:256` noch die naive Form.** Für die
neue Sperre ist `is_git_subcommand` gesetzt; die Nachbesserung an Scheibe A ist ein
Nebenbefund (#1199), kein Teil dieser Arbeit.

**Nur neue Dateien sperren, Bestand unangetastet.** `test_naming_gate.py:37` prüft schlicht
`os.path.exists(file_path)`. Für einen Commit-Wächter ist das Gegenstück
`git diff --cached --name-status --diff-filter=A` — mit `-M`, sonst zählt jede Verschiebung als
Neuanlage (das war Adversary-Fund F003 in Scheibe A).

**Ausnahme mit Begründungszwang.** `gz-main-path:` verlangt mindestens 15 sinnvolle Zeichen und
steht als Kommentar an der Stelle. `gz-eigenstaendig:` soll dasselbe leisten, im Dateikopf.

**Eigene Störung blockiert nie.** In Scheibe A an acht Stellen durchgehalten und einmal
verletzt (Fund F007, CRITICAL). Ein defektes Gate darf nie die Ursache sein, dass niemand mehr
arbeiten kann.

## Die betroffenen Flächen — gemessener Bestand

| Bereich | Dateien heute |
|---|---|
| `components/compare/` | 79 |
| `components/trip-detail/` | 61 |
| `components/edit/` | 28 |
| `components/compare-new/` | 4 |
| `components/trip-new/` | 4 |
| `components/shared/` (Ausweg) | 105 |

Python-Renderer: `compare_hourly_metric_ids.py`, `compare_metric_catalog.py`,
`compare_metric_ids.py`, `compare_outlook_metric_ids.py`, `trip_metric_ids.py`,
`trip_report.py`. Ein `renderers/shared/` gibt es **nicht** — dort ist der geteilte Ort schlicht
ein Name ohne Präfix (`comparison.py`, `channel_layout.py`, `day_window.py`).

## Wie oft die Sperre gegriffen hätte (60 Tage, gemessen)

~120 neu angelegte Dateien in den einseitigen Flächen, davon **rund 37 kein Testcode** — also
etwa alle anderthalb Tage einmal. Darunter Fälle, die genau die Zielklasse treffen:
`compare/RangeSlider.svelte` (ein allgemeiner Regler unter „Vergleich"),
`compare/LayoutPreview.svelte`, `trip-detail/AlarmeScheduleTab.svelte` +
`trip-detail/BriefingScheduleTab.svelte`.

**Wichtiger Nebenfund für den Zuschnitt:** Testdateien liegen in diesen Bereichen **nicht
durchgängig** unter `__tests__/`. Rund die Hälfte liegt direkt daneben
(`compare/channelChipCount.test.ts`, `edit/issue_619_report_config_write.test.ts`). Die im Issue
genannte Ausnahme `frontend/**/__tests__/**` allein greift zu kurz — sonst blockiert die Sperre
massenhaft Testdateien. Die Ausnahme muss an `*.test.ts` / `*.spec.ts` hängen, nicht am
Verzeichnis.

## Abhängigkeiten

- **Aufwärts:** `hook_utils` aus dem Plugin (`agent-os-openspec 3.10.0`), `git`, `settings.json`
- **Abwärts:** jeder `git commit` in jeder Sitzung und jedem Worktree — inklusive der
  parallel laufenden

## Risiken

1. **Ein Wächter, der jeden Commit anfasst.** Fehlzündung heißt: keine Sitzung kann mehr
   committen. Fail-open ist nicht verhandelbar (AC-Klasse aus Scheibe A).
2. **Der Wächter misst das Verzeichnis, aus dem der Befehl kommt** — nicht das Repo, in dem
   committet wird. Das hat am 2026-08-04 zweimal blockiert und beide Male anders ausgesehen,
   als es war.
3. **Umbenennung/Verschiebung darf nicht als Neuanlage gelten** — sonst blockiert ausgerechnet
   das Verschieben nach `shared/`, also genau der erwünschte Weg.
4. **Zu grober Zuschnitt macht die Sperre zum Rauschen.** Bei ~37 echten Treffern in 60 Tagen
   ist eine Fehlerquote von einem Drittel schon zu viel — dann wird die Begründungszeile
   reflexhaft gesetzt und die Regel wertlos.
5. **`.claude/hooks/` ist geschützt.** Für das Anlegen der Datei braucht es eine PO-Freigabe
   (Ausnahme-Eintrag, Laufzeit 1 Stunde, hängt am Workflow-Namen `feat-1481-pendant-sperre`).
   Der Vorgang darf danach **nicht** neu angelegt werden, sonst ist die Freigabe weg.

## Verwandte Specs

- `docs/specs/modules/feat_1481a_touched_tests_gate.md` — Scheibe A
- `docs/specs/modules/fix_1409b_repo_path_ratchet.md` — Herkunft des Ausnahme-Musters,
  Abschnitt „Known Limitations"
- CLAUDE.md → „Trip/Ortsvergleich-Code-Teilung" — die Regel, die hier mechanisch wird

## Regel-Budget

Neue Pflicht-Regel → **Prüfdatum 2026-11-03** (aus dem Issue). Ohne belegten Fang bis dahin:
Rückbau (#1197). Bestand zum Vergleich: 31 Hooks in `.claude/hooks/`.

---

# Analyse

**Typ:** Feature (neuer Wächter). Kein Bug.

## Drei belegte Pendant-Paare — die Regel hat einen realen Gegenstand

| Vergleichs-Seite | Trip-Seite | Beleg |
|---|---|---|
| `compare-new/CompareNewEditor.svelte` | `trip-new/TripNewEditor.svelte` | gleicher Name bis aufs Präfix; #1301 F2 verlangt ausdrücklich geteilte Bausteine |
| `compare-new/compareNewLogic.ts` | `trip-new/tripNewLogic.ts` | dito |
| `compare/CompareTabs.svelte` | `trip-detail/TripTabs.svelte` | dito |
| `renderers/email/compare_html.py` | `renderers/email/html.py` | **im Code selbst dokumentiert:** `compare_html.py:3` „analog zu ``html.py`` (Trip-Mail)" |

## Fünf Entscheidungen

### 1. Commit-Wächter, nicht Write/Edit-Wächter

Bei `Write` entsteht die Datei mit Rumpf-Inhalt; der Kopfkommentar kommt konventionell erst im
folgenden `Edit`. Ein Write-Wächter würde also praktisch **jede** Neuanlage im ersten Anlauf
blockieren und die Begründung verlangen, bevor überhaupt feststeht, ob die Datei einseitig
bleibt. Beim Commit ist die Entscheidung gefallen. Deckt sich mit dem Issue und mit Scheibe A
(gleicher Verdrahtungstyp, kein zweiter daneben).

### 2. „Neu angelegt" — vier Fälle statt zwei

Das Issue nennt zwei Wege; gemessen sind es vier. Die Lücke: eine Datei kann per Verschiebung
**direkt von einer Seite auf die andere** wandern, ohne den Umweg über `shared/`.

| Ziel | Herkunft | Verhalten |
|---|---|---|
| geteilter Bereich | egal | **immer durchlassen** — auch dann, wenn die Ähnlichkeit unter die Erkennungsschwelle fällt und aus einer Verschiebung ein Löschen+Anlegen wird |
| einseitig | neu angelegt | Begründung nötig |
| einseitig | **dieselbe** Seite (reine Umbenennung) | durchlassen |
| einseitig | **andere** Seite oder geteilter Bereich | Begründung nötig |

Der letzte Fall fehlt im Issue und wäre der bequemste Weg an der Sperre vorbei.

### 3. Zuschnitt: `edit/` raus, Renderer rekursiv

**`edit/` streichen.** Nachgemessen: die 16 Nicht-Testdateien sind durchweg Etappen-, Routen-
und Kartenwerk (`EditStagesSection.svelte`, `EditRouteSection.svelte`, `StageDateField.svelte`,
`MapControl.svelte`). Kein Bauteil unter `compare/` importiert etwas daraus. Laut CLAUDE.md darf
Compare-eigen ohnehin nur der Orte-Tab, die transponierte Übersicht und das Compare-Mail-Muster
sein — Etappen sind dort gar nicht vorgesehen. Ein Pendant kann hier strukturell nicht entstehen;
die Sperre erzeugte reines Rauschen.

**Renderer rekursiv.** Das Muster aus dem Issue (`src/output/renderers/{compare_*,trip_*}.py`)
verfehlt ausgerechnet den bestbelegten Fall: `email/compare_html.py` liegt eine Ebene tiefer.
Also `src/output/renderers/**/{compare_*,trip_*}.py`.

**Bekannte Grenze, bewusst:** Das Trip-Gegenstück `email/html.py` trägt gar kein Präfix und ist
mechanisch nicht als einseitig erkennbar. Ein Namenskonventions-Problem, das dieser Wächter
nicht löst. Ebenso außen vor: **Go** — #1459 D3 spielte auf der Go-Seite, dort greift die Sperre
nicht.

### 4. Der Marker: erste 20 Zeilen, drei Kommentarformen

Gemessene Kopfformen:

| Dateityp | Kopfform | Beleg |
|---|---|---|
| `.svelte` | `<script lang="ts">` in Zeile 1, `//`-Block ab Zeile 2 | `shared/AlarmeTab.svelte:2`, `shared/AlertChannelPicker.svelte:2` |
| `.ts` | `//`-Block ab Zeile 1 | `tripNewLogic.ts:1` |
| `.py` | **Modul-Docstring** `"""…"""`, kein `#` | `trip_metric_ids.py:1`, `trip_report.py:1` |

Daraus folgt zwingend: Ein reiner `#`-Ausdruck wie bei `gz-main-path` **trifft in Python-Renderern
nie**, weil dort gar keine `#`-Kommentare stehen. Der Ausdruck muss `#`, `//` **und die bloße
Zeile im Docstring** akzeptieren. Fenster: erste 20 Zeilen — deckt den längsten gemessenen
Kopf-Docstring (`trip_report.py`, 13 Zeilen) ab.

Mindestlänge 15 sinnvolle Zeichen, gemessen wie beim Vorbild: Länge nach `re.sub(r"[\W_]+", "")`.

### 5. Störungspfad: nur Auslassungen, nie Fehlalarm

Der Wächter läuft in jeder Sitzung und jedem Arbeitsordner. Leitsatz aus Scheibe A: eine eigene
Störung führt zu „durchlassen und sagen", nie zu „blockieren".

Der Wächter liest die vorgemerkten Dateien im Verzeichnis, aus dem der Befehl kommt. Trägt der
Befehl ein `-C <pfad>`, ist das nicht zwangsläufig dasselbe Repo — dann wird **durchgelassen mit
Hinweis**. Das kostet einen möglichen Fang und schließt einen Fehlalarm aus; in dieser Richtung
ist der Handel eindeutig.

**Ausdrücklich nicht:** das Kommando frei zerlegen, um das Zielverzeichnis zu rekonstruieren.
Genau dieser Weg hat in #1431 zweimal zu einem BROKEN-Urteil geführt.

**Nachtrag — der Erwartungsstand ist bereits festgeschrieben.** `tests/tdd/test_commit_gate_invocation_forms.py`
(aus #1431) verlangt von Commit-Wächtern, dass sie **auch** bei `git -C <pfad> commit`,
`cd /tmp && git -C <pfad> commit` und der mehrzeiligen Form greifen — und bei
`grep -rn "git commit" …` gerade nicht. Für den neuen Wächter heißt das: einfaches Durchlassen
bei `-C` widerspricht dem Bestand.

Auflösung, ohne ins freie Zerlegen zu geraten: **ein einziges** Flag auswerten. Trägt der Befehl
ein `-C <pfad>` und ist das ein anderes Repo als das aktuelle Verzeichnis, wird der dortige
Vormerk-Stand gelesen. Lässt sich der Pfad nicht auflösen → durchlassen mit Hinweis. Ein Flag ist
begrenzt; die Sackgasse von #1431 war das Nachbauen einer Kommandozeilen-Zerlegung.

Wiederverwendbar: `test_commit_gate_invocation_forms.py` liefert das fertige Prüfmuster
(Wegwerf-Repo, echter Unterprozess, parametrisierte Aufrufformen). Die Aufrufform-ACs des neuen
Wächters gehören dort hinein, nicht in eine eigene Datei.

## Ein Zusatz, der die Begründung konkret macht

Die Mindestlänge prüft Textlänge, nicht Substanz — `gz-eigenstaendig: aus Zeitgruenden getrennt`
kommt durch. Dagegen hilft kein Automat. Was hilft: **der Wächter benennt in seiner Meldung die
namensähnliche Datei auf der anderen Seite**, wenn es eine gibt. Dann beantwortet die Begründung
eine konkrete Frage statt ins Leere zu schreiben. Kostet ~10 Zeilen (Präfix vom Dateinamen
abschneiden, Gegenseite absuchen) und trifft die drei belegten Paare.

## Geänderte Dateien

| Datei | Art | Beschreibung |
|---|---|---|
| `.claude/hooks/pendant_gate.py` | ANLEGEN | Der Wächter, ~130 Zeilen |
| `tests/tdd/test_pendant_gate.py` | ANLEGEN | Verhaltensnachweis gegen Wegwerf-Repos, ~250 Zeilen |
| `.claude/settings.json` | ÄNDERN | 8 Zeilen Verdrahtung |
| `docs/specs/modules/feat_1481b_pendant_gate.md` | ANLEGEN | Spec (zählt nicht ins Zeilen-Limit) |
| `CLAUDE.md` | ÄNDERN | Regel + Prüfdatum (zählt nicht) |

**Umfang:** ~400 Zeilen Code+Test. Über dem Standard-Limit von 250 → Anhebung auf 500 nötig,
mit PO-Freigabe.

**Risiko: mittel.** Die Kernlogik ist einfach (Pfadabgleich + Zeilensuche). Das Risiko liegt
im Störungspfad und in der Verdrahtung — bei Scheibe A lagen dort alle drei kritischen Funde.

## Offene Punkte

- [ ] `.claude/hooks/` ist geschützt — PO-Freigabe zum Anlegen der Datei nötig (Laufzeit 1 Stunde,
      hängt am Workflow-Namen; Vorgang danach nicht neu anlegen)
- [ ] Zeilen-Limit von 250 auf 500 anheben — braucht PO-Freigabe
- [ ] Nebenbefund für #1199: `touched_tests_gate.py:256` erkennt den Commit noch per Wortlaut
      statt per Aufrufform
