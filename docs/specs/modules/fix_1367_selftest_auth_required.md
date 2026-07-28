---
entity_id: fix_1367_selftest_auth_required
type: module
created: 2026-07-24
updated: 2026-07-28
status: implemented
version: "1.0"
tags: [gate, deploy, selftest, honesty, auth]
---

# Fix #1367 — Post-Deploy-Selbsttest: 401/403 auf geschützten Endpoints ist kein Fehlschlag

## Approval

- [x] Approved

## Purpose

Der Post-Deploy-Selbsttest (`prod_selftest.py`) probt jedes Acceptance Criterion mit einer
**unangemeldeten GET-Anfrage** gegen die Prod-URL. Antwortet ein Endpoint mit `401`/`403` —
also korrekt, weil er hinter der Auth-Middleware liegt — fällt das in den Sammel-Zweig
`else: FAIL`. Ergebnis: Verdict `PARTIAL`, Exit 1, Issue-Close blockiert, obwohl der Deploy
in Ordnung ist.

Dieser Fix behandelt den Fall „Anmeldung erforderlich" genauso wie die bereits vorhandenen
Fälle „nur Schreibanfragen" (`405` → `SKIPPED_METHOD_NOT_PROBEABLE`) und „Weiterleitung zur
Anmeldeseite" (`SKIPPED_AUTH_REDIRECT`): als **strukturell nicht per unangemeldetem GET
prüfbar**, nicht als Fehlschlag.

## Source

- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `_probe_ac` (Statusklassifikation, Z. 309-317), `_derive_verdict` (Z. 490-509),
  Berichts-Renderer (Z. 422-431)

## Estimated Scope

- **LoC:** ~+35 / -5 (Kern-Datei), Test separat
- **Files:** 1 Quelldatei + 1 Testdatei
- **Effort:** low — kleiner Diff, aber Deploy-Gate = kritischer Pfad

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/prod_selftest.py::_probe_ac` | Funktion | Klassifiziert die Prod-Antwort je AC |
| `.claude/hooks/prod_selftest.py::_derive_verdict` | Funktion | Leitet die Gesamtnote ab; bestimmt den Exit-Code |
| `internal/middleware/auth.go:31-50` | Referenz | Erzeugt die `401`-Antwort für nicht-freigelistete Routen |
| `docs/specs/modules/fix_1353_selftest_auth_redirect.md` | Vorgänger | Führte `SKIPPED_AUTH_REDIRECT` + die „alles übersprungen"-Regel ein |
| Deploy-Schritt 4b (`CLAUDE.md`) | Konsument | Exit 0 ist die einzige Freigabe für `gh issue close` |

## Implementation Details

```
1. _probe_ac — neue Fallunterscheidung VOR dem else-Zweig:
     status in (401, 403) → prod_status = "SKIPPED_AUTH_REQUIRED"
   Alle übrigen Codes (404, 5xx, …) behalten "FAIL".

2. _derive_verdict — die bestehende "alles übersprungen"-Regel aus #1353 darf nicht
   pro Skip-Art getrennt greifen. Beide Auth-Skips werden gemeinsam betrachtet:
     - alle geprobten PASS-Findings ∈ {SKIPPED_AUTH_REDIRECT, SKIPPED_AUTH_REQUIRED}
       → Verdict "SKIPPED_AUTH" (kein inhaltlicher Prod-Nachweis)
     - sonst unverändert: mind. ein FAIL → PARTIAL, sonst PASS
   Ohne diese Zusammenfassung würde eine MISCHUNG aus beiden Skip-Arten durch die
   bestehende all()-Prüfung fallen und fälschlich als PASS gelten — der Bug, den #1353
   beseitigt hat, käme über die Hintertür zurück.

3. Exit-Code: "SKIPPED_AUTH" wird wie "SKIPPED_AUTH_REDIRECT" behandelt (Exit 0), damit
   die Präzedenz aus #1353 erhalten bleibt. Der Bericht benennt unmissverständlich, dass
   in Prod nur die Anmelde-Schranke gesehen wurde und kein inhaltlicher Nachweis vorliegt.

4. Bericht: eigene Zeile je Skip-Art, damit im Bericht ablesbar bleibt, WARUM ein AC
   nicht geprüft werden konnte (Anmelde-Weiterleitung vs. direkte Abweisung).
```

## Expected Behavior

- **Input:** `e2e_verified.json` mit `findings[]` (je `ac`, `status`, `url`, `evidence`),
  dazu die tatsächlichen HTTP-Antworten der Prod-Instanz.
- **Output:** Bericht `docs/artifacts/<workflow>/prod-selftest.md` mit einer Zeile je AC
  (Prod-HTTP + Prod-Status) sowie ein Verdict und ein Exit-Code.
- **Side effects:** Keine. Der Selbsttest schreibt ausschließlich den Bericht; er verändert
  weder Daten noch Dienste.

## Acceptance Criteria

- **AC-1:** Given ein Acceptance Criterion verweist auf einen Endpoint, der unangemeldet mit
  „Anmeldung erforderlich" antwortet / When der Post-Deploy-Selbsttest läuft / Then wird dieses
  Kriterium als „nicht prüfbar" ausgewiesen und nicht als fehlgeschlagen, und der Selbsttest
  blockiert den Abschluss nicht mehr allein deswegen.
  - Test: Selbsttest gegen eine Attestation laufen lassen, deren Endpoint mit 401 antwortet;
    das Ergebnis für dieses Kriterium ist nicht „FAIL" und der Exit-Code ist 0.

- **AC-2:** Given ein Endpoint antwortet mit einem echten Fehler wie „nicht gefunden" oder einem
  Serverfehler / When der Selbsttest läuft / Then bleibt dieses Kriterium ein Fehlschlag und der
  Abschluss bleibt blockiert — auch dann, wenn das Kriterium zu einem geschützten Endpoint
  gehört. Die Ausnahme gilt **ausschliesslich** für die Antwort „Anmeldung erforderlich", nicht
  für Fehlerantworten allgemein.
  - Test: Attestation mit einem Endpoint, der 404 bzw. 500 liefert; Ergebnis „FAIL",
    Gesamtnote PARTIAL, Exit-Code 1. Zusätzlich: derselbe geschützte Pfad, der statt 401 ein
    404 liefert (weggebrochene Route), ist ebenfalls „FAIL".

- **AC-3:** Given in einem Lauf konnte kein einziges Kriterium inhaltlich geprüft werden, weil
  alle Endpoints nur die Anmelde-Schranke zeigten — teils als Weiterleitung, teils als direkte
  Abweisung / When die Gesamtnote gebildet wird / Then wird der Lauf **nicht** als „bestanden"
  ausgewiesen, sondern benennt, dass kein inhaltlicher Nachweis vorliegt.
  - Test: Attestation mit gemischten Endpoints (einer antwortet mit Weiterleitung zur Anmeldung,
    einer mit direkter Abweisung); die Gesamtnote ist nicht „PASS", der Bericht sagt, dass kein
    inhaltlicher Prod-Nachweis erbracht wurde.

- **AC-4:** Given ein Lauf enthält sowohl inhaltlich geprüfte als auch nicht prüfbare Kriterien
  / When die Gesamtnote gebildet wird / Then zählt der erbrachte Nachweis, und der Lauf gilt als
  bestanden, solange kein Kriterium fehlgeschlagen ist.
  - Test: Attestation mit einem erreichbaren Endpoint (200) und einem geschützten (401);
    Gesamtnote PASS, Exit-Code 0.

- **AC-5:** Given der Bericht wird geschrieben / When ein Kriterium nicht geprüft werden konnte
  / Then ist im Bericht ablesbar, **warum** es nicht geprüft werden konnte — Weiterleitung zur
  Anmeldung und direkte Abweisung sind unterscheidbar.
  - Test: Bericht eines Laufs mit beiden Fällen enthält für die beiden Kriterien
    unterschiedliche, sprechende Statusangaben.

- **AC-6 (Worktree-Korrektheit, PO-Auftrag 2026-07-24; korrigiert nach Adversary-Befund F001):**
  **AUSGEGLIEDERT (PO-Entscheidung 2026-07-28): nicht Teil dieser Umsetzung — siehe Sammel-Issue #1199.**
  Given der Selbsttest wird aus einem isolierten Arbeitsbaum (Worktree) heraus aufgerufen / When er
  den Bericht schreibt und den Änderungsumfang bestimmt / Then bezieht er sich dafür auf **diesen**
  Arbeitsbaum — der Bericht landet im Artefakt-Ordner desselben Arbeitsbaums, die Umfangserkennung
  liest dessen Git-Stand. Die geteilte Freigabe-Ablage (Attestation) und die Produktions-Konfiguration
  (Deploy-Wurzel: `.env`, Kanal-Quelldateien) werden weiterhin an ihrer gemeinsamen,
  arbeitsbaum-übergreifenden Stelle gelesen.
  - Test: Der Selbsttest aus einem Arbeitsbaum-Pfad heraus schreibt seinen Bericht **nicht** in das
    Hauptrepo, sondern in den Artefakt-Ordner des Arbeitsbaums; ein bestehender Test, der den
    Selbsttest mit Arbeitsverzeichnis = Hauptrepo als Unterprozess fährt, findet seinen Bericht
    weiterhin dort (Rückwärtskompatibilität).

- **AC-7 (Commit-Attestation prüft die ausgelieferte Produktion, NICHT den Arbeitsbaum;
  Adversary-Befund F001):**
  **AUSGEGLIEDERT (PO-Entscheidung 2026-07-28): nicht Teil dieser Umsetzung — siehe Sammel-Issue #1199.**
  Given ein Deploy ist fehlgeschlagen oder nicht gelaufen, sodass die
  laufende Produktion **nicht** auf dem freigegebenen Commit steht, während der aufrufende
  Arbeitsbaum diesen Commit lokal bereits hat / When der Selbsttest aus dem Arbeitsbaum heraus läuft
  / Then meldet er einen Fehlschlag (der freigegebene Commit ist nicht in der Historie der
  ausgelieferten Produktion) und gibt den Abschluss **nicht** frei.
  - Test: Ein Wegwerf-Verbund aus geteiltem Hauptrepo (steht auf altem Commit) und Arbeitsbaum
    (steht auf dem freigegebenen Commit); der Selbsttest aus dem Arbeitsbaum aufgerufen liefert
    Fehlschlag/Exit 1. Kontrolle: steht das geteilte Hauptrepo auf dem freigegebenen Commit (oder
    einem Nachfahren davon), gibt derselbe Aufruf frei (Exit 0).
  - **Begründung:** Die Commit-Attestation ist die einzige Prüfung, die „ist dieser Stand wirklich
    ausgeliefert?" beantwortet — besonders für Änderungen ohne HTTP-prüfbare AC-URL (Gate-/Tooling-/
    reine Backend-Fixes), wo Health-Check und AC-Proben kein zweites Netz bieten. Sie MUSS gegen den
    **geteilten** Repo-Stand (`_shared_repo_dir()`-HEAD = Deploy-Wurzel = Produktion) prüfen, nicht
    gegen den Arbeitsbaum-HEAD — sonst vergleicht sie den vom selben Arbeitsbaum geschriebenen
    `verified_commit` mit dem Arbeitsbaum-HEAD und wird zur Tautologie.

## PO-Entscheidung 2026-07-24

Vorgelegt wurden drei Wege: (a) ehrlich benennen und die Schranke prüfen, (b) einen Lauf ohne
inhaltlichen Nachweis hart blockieren, (c) den Selbsttest mit einem echten Konto anmelden.

**Gewählt: (a).** Begründung, die die Wahl trägt:

- Der Funktionsnachweis ist bereits **hart abgesichert** — der Prod-Deploy blockiert ohne frische
  Staging-Freigabe für exakt denselben Commit. Diese Freigabe entsteht angemeldet und über den
  echten Nutzerweg. Der Selbsttest muss den Nachweis nicht wiederholen; er kann es unangemeldet
  auch gar nicht.
- Aufgabenteilung: Staging beweist „die Funktion stimmt", der Prod-Selbsttest beweist „genau
  dieser Stand ist ausgeliefert und gesund". Ein Exit-Code, der beides tragen soll, erzeugt nur
  den Druck, das Gate zu umgehen — Weg (b) hätte künftig fast jede Backend-Arbeit getroffen.
- Weg (c) wäre der stärkste Nachweis, holt sich aber Zugangsdaten in die Deploy-Kette und
  Testdaten in den echten Bestand — ein zusätzliches bewegliches Teil, das selbst ausfallen kann.
  Solange Staging denselben Code fährt, ist der Zugewinn den Tausch nicht wert.

**Die Ausnahme bleibt eng:** Übersprungen wird nur die Antwort „Anmeldung erforderlich"
(401/403). Damit prüft der Selbsttest weiterhin etwas Belastbares — nämlich dass die Route
existiert und bewacht ist. Eine weggebrochene Route (404) oder ein Serverfehler bleibt ein
Fehlschlag (AC-2).

## PO-Entscheidung 2026-07-28 (Salvage/Port)

AC-6 und AC-7 wurden aus dieser Umsetzung ausgegliedert (Sammel-Issue #1199). Grund: Die
Original-Sitzung vom 2026-07-25 hatte mit genau dieser Fläche (Commit-Attestation gegen
Arbeitsbaum- statt geteilten Repo-Stand) bereits einmal das Deploy-Sicherheitsnetz entkernt
(Adversary-Befund F001 — ein nicht gelaufener Deploy hätte trotzdem freigegeben). Diese Fläche
bleibt für diese Portierung unangetastet: `REPO_DIR`, Phase-1-Commit-Attestation,
`_nearest_verified_ancestor`, `_head_sha`, `report_path` und die Scope-Erkennung sind
ausschliesslich AC-1 bis AC-5 betreffend geändert worden. Fix #1382 (Ablösung der
Sammel-Nachweisdatei durch eine Nachweisdatei je Commit) ist davon unberührt geblieben.

## Known Limitations

- Der Selbsttest prüft weiterhin **unangemeldet**. Für geschützte Endpoints heißt „nicht
  fehlgeschlagen" daher ausdrücklich **nicht** „fachlich bewiesen" — der inhaltliche Nachweis
  bleibt Sache der Staging-Verifikation, die sich anmeldet und den echten Nutzerpfad geht.
- Antwortet eine Route, die **öffentlich** sein müsste, fälschlich mit 401, wird das jetzt als
  Skip statt als Fehlschlag gewertet. Dieses Restrisiko besteht bereits seit #1353 für den
  Weiterleitungs-Fall und wird hier bewusst gleich behandelt; erkannt würde so ein Fall über
  den Smoke-Test und die Staging-Verifikation.
- Ein Lauf ohne jeden inhaltlichen Nachweis bleibt bei Exit 0 (Präzedenz #1353). Die Ehrlichkeit
  liegt im Verdict-Namen und im Bericht, nicht im Exit-Code.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt die mit #1353 dokumentierte Linie fort („der Selbsttest benennt, was er
  nicht prüfen konnte, statt es zu erraten") und ändert keine Grundsatzentscheidung. Der
  Exit-Code-Umgang mit vollständig übersprungenen Läufen bleibt unverändert.

## Changelog

- 2026-07-24: Initial spec (Issue #1367)
- 2026-07-24: AC-6 ergänzt — Worktree-Korrektheit der Pfadauflösung (PO-Auftrag). Der Selbsttest
  wird auf dasselbe geteilte-vs-Worktree-Muster gezogen, das `staging_gate.py` seit #665 nutzt
  (`_e2e_paths.shared_repo_dir()` / `worktree_repo_dir()`), statt `REPO_DIR` fest zu verdrahten.
  Der `REPO_DIR`-Sentinel bleibt als Test-Override erhalten.
- 2026-07-25: AC-6 korrigiert + AC-7 ergänzt nach Adversary-Befund F001 (VERDICT BROKEN). Die
  erste AC-6-Fassung ließ die Commit-Attestation gegen den Arbeitsbaum-HEAD prüfen — live belegt:
  Arbeitsbaum `d2838c6` vs. Produktion `a13aa39`. Das machte die Deploy-Verifikation zur Tautologie
  (ein nicht gelaufener Deploy hätte trotzdem freigegeben). Korrektur: Bericht + Umfangserkennung
  bleiben arbeitsbaum-bezogen, die Commit-Attestation prüft gegen `_shared_repo_dir()`-HEAD
  (ausgelieferte Produktion).
- 2026-07-28: Salvage-Portierung auf aktuellen Stand (Ausgangs-Session vom 2026-07-25 war
  abgestürzt, nie eingecheckt). Status auf `implemented` gesetzt. AC-6/AC-7 als AUSGEGLIEDERT
  markiert (PO-Entscheidung, Sammel-Issue #1199) — siehe PO-Entscheidung 2026-07-28 oben.
  AC-4 stellte sich beim RED-Lauf gegen den heutigen Stand als tatsächlich rot heraus (nicht wie
  ursprünglich angenommen bereits grün): 401 zählt vor dem Fix als FAIL, wodurch der Misch-Fall
  200+401 PARTIAL statt PASS ergab.
