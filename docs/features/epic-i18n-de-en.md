# Epic 2644: Zweisprachigkeit Deutsch/Englisch

**Status:** Geplant (2026-10-30) — Umsetzung durch Agenten, Phase 0 mit Sonnet, Migrationspakete mit Haiku
**Epic Scope:** Web-UI, E-Mail, Telegram, SMS-/Premium-SMS-Freitext, Inbound-Befehle und -Antworten, Go-API-Meldungen, Konto-/Transaktions-Mails sprechen Deutsch **und** Englisch. Die Sprache ist eine Konto-Einstellung (`language`), vorbelegt aus dem Browser. Protokoll-Token, Kurzformen und Eigennamen werden nie übersetzt.
**Grundsatz:** `docs/adr/0104-zweisprachigkeit-de-en.md` · **Glossar:** `docs/reference/i18n_glossar.md` · **Issues:** Epic #2644 mit 32 Sub-Issues (#2645–#2681)
**PO-Auftrag:** 2026-10-30 („Erstelle einen Plan, wie du Gregor Zwanzig multilingual erstellst … Umsetzung später durch Agenten mit Haiku, wenn ausreichend"); Rückfragen per `AskUserQuestion` beantwortet (Sprachwahl, Umfang, Technik, Ablage).

---

## Leitbild

Ein Nutzer wählt einmal seine Sprache; danach spricht **jede** Fläche und **jeder** Kanal diese
Sprache mit demselben Inhalt (Kanal-Parität ADR-0095). Was Maschinen lesen oder was in 160 Zeichen
passen muss (`sms_code`, `compact_label`, Kürzel, `col_label`), bleibt unverändert (ADR-0042
Klasse 1 und Kurzform). Deutsch bleibt byte-gleich zur heutigen Ausgabe.

## Architektur der Lösung

```
user.json: language ─┬─> Go     internal/i18n      T(lang,key)   Handler, Konto-Mails, Fehler {code,message}
                     ├─> Python src/i18n           t(key,lang)   Renderer aller Kanäle, Inbound, API-detail
                     └─> Svelte $lib/i18n           t(key)        locale-Store aus +layout (user > Cookie > Accept-Language > de)
Metrik-Register: label_de / label_en · alert_label / alert_label_en   (col_label, sms_code, compact_label eingefroren)
Mail: Header X-GZ-Lang ──> Validatoren bilden Erwartungen aus dem Python-Katalog
```

- **Ein Auflösungsweg je Schicht:** `resolve_user_lang(user_id)` (Python), `i18n.FromContext(ctx)` (Go), `locals.lang` (SvelteKit). Kein zweiter Weg, kein globaler Zustand (zwei Nutzer im selben Scheduler-Lauf).
- **Kataloge:** flache, bereichs-präfixierte Schlüssel in JSON je Sprache **und Bereich**, damit Migrationspakete parallel ohne Dateikonflikt arbeiten. Platzhalter `{name}`, Plural `.one`/`.other`, Fallback Deutsch mit einmaligem Log. Paritätstest je Katalog.
- **Ratschen:** je Schicht ein Test gegen hartkodierte Nutzertexte mit schrumpfender Allowlist (S4, P11, G5).
- **Kurzform ist Platzform:** Telegram-Kurzstil und Premium-SMS behalten Kürzel + englische Befehlswörter unabhängig von der Sprache; nur Kürzel-Auflösung und Antworten folgen dem Nutzer (#2417 bleibt).

## Ist-Stand (gemessen 2026-10-30)

| Schicht | Befund |
|---|---|
| Frontend | 256 Svelte-Dateien; Katalog #2520 (`frontend/src/lib/i18n`, 112 Schlüssel, nur `de`, 9 Importeure); `app.html` fest `lang="de"`; deutsche Textzeilen: `components/shared/` ≈ 4.800, `compare/` ≈ 1.280, `routes/` ≈ 1.150, `trip-detail/` ≈ 700, `utils`+`stores` ≈ 700, Rest < 300 je Bereich |
| Python | 535 deutsche Literale in `src/output` + `src/services`; `trip_report_scheduler.py` 171 · `trip_command_processor.py` 146 · `channels/email.py` 122 · `metric_catalog.py` 80 · `alert/official_alerts.py` 79 · `notification_service.py` 78 · `email/html.py` 71; 40× `%d.%m.`; `UserPreferences.language` ungenutzt |
| Go | 471 deutsche Literale: `handler/` 282 · `mail/` 67 · `store/` 37 · `scheduler/` 30; `model.User` ohne Sprachfeld |
| Inbound | #2417: `wort_en`, `kuerzel_bedeutung_en` vorhanden; `self._en` = Kurzform-Kanal |
| Validatoren | 4 Mail-Validatoren mit 31 deutschen Literal-Erwartungen |
| Entscheidungen | #94 gestrichen 2026-08-04 („lebt in ADR-0042 weiter"); #2520: eigener Katalog, kein Paraglide (2026-10-07) |

## Phasen, Pakete, Abhängigkeiten

| Phase | Paket | Issue | Modell | Abhängig von |
|---|---|---|---|---|
| 0 Fundament | S0 ADR-0104 freigeben, Glossar, api_contract | #2645 | Sonnet | — |
| 0 | S1 Sprachfeld `language` am Nutzer (Go+Python) | #2646 | Sonnet | S0 |
| 0 | S2 Frontend-Sprachkern | #2647 | Sonnet | S1 |
| 0 | S3 Sprachumschalter + Konto | #2648 | Haiku | S1, S2 |
| 0 | S4 Ratsche Frontend | #2649 | Sonnet | S2 |
| 1 Web-UI | F1 Auth-Routen | #2650 | Haiku | S2, S4 |
| 1 | F2 Hilfe, Onboarding, Begriffserklärungen | #2651 | Haiku | S2, S4 |
| 1 | F3 Home/Cockpit, Listen | #2652 | Haiku | S2, S4 |
| 1 | F4 Konto, Admin, Sidebar | #2653 | Haiku | S3, S4 |
| 1 | F5 Wertebereiche-Tab | #2654 | Haiku | S4, P1 |
| 1 | F6 Versand-Tab | #2655 | Haiku | S4 |
| 1 | F7 Alarme-Tab | #2656 | Haiku | F5 |
| 1 | F8 Layout-Tab, Korridor | #2657 | Haiku | S4 |
| 1 | F9 Trip-Flächen | #2658 | Haiku | F5–F8 |
| 1 | F10 Ortsvergleich-Flächen | #2659 | Haiku | F9 |
| 1 | F11 Bausteine, TS-Texte, Fehlercodes | #2660 | Haiku | S4 |
| 1 | F12 Frontend-Abschluss (E2E, Screenshots) | #2661 | Sonnet | F1–F11 |
| 2 Python | P1 i18n-Kern, Metrik-Register, `/api/metrics` | #2662 | Sonnet | S1 |
| 2 | PV Mail-Validatoren sprachfähig | #2663 | Sonnet | P1 |
| 2 | P2 Trip-Briefing-Mail HTML | #2664 | Haiku | PV |
| 2 | P3 Trip-Briefing compact/plain + Hinweise | #2665 | Haiku | P2 |
| 2 | P4 Vergleichs-Mail | #2666 | Haiku | PV |
| 2 | P5 Abweichungs-/Radar-Alarme | #2667 | Haiku | PV |
| 2 | P6 Amtliche Warnungen | #2668 | Haiku | PV |
| 2 | P7 Telegram | #2669 | Haiku | P1 |
| 2 | P8 SMS/Premium-SMS-Freitext | #2670 | Haiku | P1 |
| 2 | P9a Versand-Schicht | #2671 | Haiku | PV |
| 2 | P9b Scheduler/Alarm-Orchestrierung | #2672 | Haiku | P2–P8 |
| 2 | P10 Inbound | #2673 | Sonnet | P1 |
| 2 | P11 API-Meldungen + Ratsche Python | #2674 | Haiku | P1 / P2–P10 |
| 3 Go | G1 i18n-Kern, Kontext, `code`+`message` | #2675 | Sonnet | S1 |
| 3 | G2 Handler Auth/Konto | #2676 | Haiku | G1 |
| 3 | G3 Handler Fachlogik, store/middleware | #2677 | Haiku | G1 |
| 3 | G4 Konto-Mails, notify, scheduler | #2678 | Haiku | G1 |
| 3 | G5 Ratsche Go | #2679 | Haiku | G1 |
| 4 Abschluss | A1 Doku, CLAUDE.md-Zeile | #2680 | Haiku | F12, P11, G5 |
| 4 | A2 E2E zweisprachig, Marker Pflicht | #2681 | Sonnet | A1 |

**Kritischer Pfad:** S0 → S1 → {S2 → S4 → F…; P1 → PV → P2… → P9b; G1 → G…} → A1 → A2.
**Parallelität:** drei Worktrees (Frontend, Python, Go) nach Phase 0; Querbezug nur F5/F7 ← P1.
**Modellwahl:** Sonnet für Kern, Validatoren, Inbound, E2E (10 Pakete); Haiku für 22 Migrationspakete. Adversary (`implementation-validator`) bleibt Sonnet. Haiku scheitert zweimal → Sonnet (Workflow-Regel).

## Was jedes Haiku-Paket im Briefing braucht

1. Issue-Nummer, `OPENSPEC_ACTIVE_WORKFLOW`, freigegebene Spec mit ACs.
2. Zielbereich (Dateiliste) und Katalog-Namensraum; Allowlist-Eintrag, der zu entfernen ist.
3. Eine **Beispiel-Umstellung** aus dem Kern-Paket (vorher/nachher, Platzhalter, Plural).
4. Glossar-Pfad und das Verbot „Tour".
5. Golden-Regel: deutsche Ausgabe byte-gleich; Token-Wächter grün; Validator in beiden Sprachen.

## Risiken und Gegenmittel

| Risiko | Gegenmittel |
|---|---|
| Englische Texte länger → Layout-Brüche, SMS > 160 Zeichen | F12 Screenshot-Paare + Fresh-Eyes; P8 Längen-Test je Klartext |
| Validatoren brechen bei erster englischer Mail (Lehre #1381/#1404/#1420) | PV **vor** allen Mail-Renderer-Paketen; Marker `X-GZ-Lang` |
| Parallel-Pakete kollidieren im Katalog | Katalog je Bereich (eigene Datei je Paket) |
| Haiku übersetzt frei oder uneinheitlich | Glossar bindend; Adversary prüft Glossar-Konformität; Paritätstest |
| Zweiter Auflösungsweg / globaler Sprachzustand → falsche Sprache bei zweitem Nutzer | Eine Funktion je Schicht; Cross-User-Test in S1, P9a, P9b, G1 |
| Token unbemerkt verändert | Eingefrorene Fixture `metric_tokens_frozen.json` (P1) |
| CLAUDE.md-Budget | A1: eine Zeile, Budget-Test |

## Nicht Teil dieses Epics

Weitere Sprachen (neues ADR), Übersetzung amtlicher Warntexte (nur Quell-Block-Wahl), Übersetzung der Dokumentation (`docs/` bleibt deutsch), Übersetzung von Orts-/Regionsnamen, Admin-Mails an den Betreiber (bleiben deutsch).
