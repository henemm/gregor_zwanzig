# Context: Issue #375 — Vertagte Reste aus Epic #331

## Request Summary
Drei aus Epic #331 vertagte, voneinander unabhängige Reste (alle `priority:low`):
**(A)** volles Mobile-Akkordeon-Redesign des Wetter-Metriken-Editors,
**(B)** zwei Backend-Test-Lücken aus #363,
**(C)** kosmetische Vereinheitlichung des Detail-Zeilen-Clamps in der Vorschau.

## Drei Teil-Scopes

### A — Mobile-Akkordeon-Editor (Frontend, groß, optional)
Mockup `docs/design/epic_331_output_layout/screen-metrics-editor-mobile.jsx` skizziert einen
eigenständigen Mobile-Ansatz: Preset-Picker (H-Scroll) oben, 26 Metriken in **5 Kategorie-Akkordeons**
(Temperatur/Wind/Niederschlag/Wolken&Sicht/Sonstiges), Sticky-Save-Bar unten — also ein einfaches
An/Aus pro Metrik statt des Desktop-Bucket-Editors (Spalten/Detail/Aus + Reihenfolge).
In #365 wurde nur responsives **Stapeln** + reduzierte Vorschau geliefert (Editor selbst hat kein
Akkordeon). Begleit-Mockups: `screen-output-preview-mobile.jsx`, `screen-signal-cols-mobile.jsx`.

### B — 2 Test-Nits aus #363 (Backend, klein, reine Test-Ergänzungen)
Beide sind **Test-Lücken** — die Implementierung ist nachweislich korrekt, nur die Assertion fehlt:
- **Go:** `internal/handler/preview_proxy_test.go::TestPreviewProxyHandlerForwardsTelegramChannel`
  (Z. 140–155) dispatcht mit User `"default"` und assertet die `user_id`-Injektion **nicht** — der
  Signal-Test (Z. 120–138) tut es (`user_id=alice`). Fix: Telegram-Test mit Nicht-Default-User +
  `user_id=`-Assert ergänzen.
- **Python:** `tests/tdd/test_issue_363_signal_telegram_preview.py::test_ac3_signal_body_differs_from_sms_and_email`
  (Z. 128–150) vergleicht signal≠sms≠email, aber **nicht** explizit signal≠telegram. Fix: Telegram-Body
  zusätzlich holen + `signal_body != telegram_body` asserten.

### C — Fresh-Eyes-Kosmetik (Frontend, winzig)
Detail-Zeilen-Clamp uneinheitlich: In `ChannelPreviewCard.svelte` werden Detail-Metriken mit `' · '`
verbunden und per CSS `-webkit-line-clamp: 5` ohne sichtbares Ellipsis abgeschnitten; die **SMS**-Zeile
hängt dagegen manuell `" …"` an (`smsTruncated`). Ziel: einheitliches Abschneide-Verhalten („· …" vs.
abruptes Ende).

## Related Files
| Datei | Relevanz | Teil |
|------|----------|------|
| `docs/design/epic_331_output_layout/screen-metrics-editor-mobile.jsx` | Soll-Mockup Mobile-Akkordeon | A |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Haupt-Editor; nur 1 Breakpoint (899px: 2→1 Spalte) | A |
| `frontend/src/lib/components/trip-detail/BucketSection.svelte` | Bucket-Container (kein Mobile-BP) | A |
| `frontend/src/lib/components/trip-detail/ActiveMetricRow.svelte` | Editor-Zeile, festes Grid `30px 1fr 200px 150px 76px` (kein Mobile-BP) | A |
| `frontend/src/lib/components/trip-detail/BucketSectionOff.svelte` | „Nicht im Briefing", auto-fill-Grid | A |
| `frontend/src/lib/components/trip-detail/ChannelPreviewBlock.svelte` | 4-Kanal-Vorschau, Mobile-Dropdown (899px). **⚠ aktuell uncommittete Fremdarbeit im Tree** | A/C |
| `frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte` | Detail-Zeile + Clamp-Logik (Z. 72–82 Render, Z. 160–174 CSS) | C |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | Pure-Function-Helper (autoAssign/move/reorder/applyChannel/buildWeatherConfigMetrics) | A |
| `internal/handler/preview_proxy_test.go` | Go-Test-Nit (Telegram user_id-Assert) | B |
| `tests/tdd/test_issue_363_signal_telegram_preview.py` | Python-Test-Nit (AC-3 signal≠telegram) | B |

## Existing Patterns
- **Bucket-Editor (#364)** ist das Desktop-Pattern: Spalten/Detail/Aus + Reihenfolge + Roh/Skala. Das
  Mobile-Mockup (A) bricht bewusst damit (nur An/Aus, Kategorie-Akkordeons).
- **Responsiv:** Einziger Breakpoint `@media (max-width: 899px)` in `WeatherMetricsTab` + `ChannelPreviewBlock`;
  Akkordeon-Pattern existiert im Editor noch nicht.
- **Test-Pattern (B):** Beide Nits folgen exakt dem vorhandenen Schwester-Test im selben File — Go-Telegram
  spiegelt Go-Signal, Python-AC-3 erweitert um eine Zeile. Kein Produktionscode, keine Mocks (Python nutzt
  echten `TestClient` + Trip-Fixture `gr221-mallorca`, 200/503-tolerant).

## Dependencies
- **Upstream:** #360 (Kanal-Renderer), #363 (Vorschau-Endpoints), #364 (Bucket-Editor), #365 (4-Kanal-Vorschau) — alle live.
- **Downstream:** Keine; #375 ist Abschluss-Politur, nichts baut darauf auf.

## Existing Specs
- `docs/specs/modules/issue_363_signal_telegram_preview.md` — AC-Quelle für Teil B.
- Epic #331 / #364 / #365 — kein eigenes neues Modul nötig; A ist eine UI-Variante bestehender Komponenten.

## Risks & Considerations
1. **Parallel-Session-Contention (HOCH):** Der Hauptordner trägt uncommittete Fremdarbeit (#366:
   `comparison_engine.py`/`comparison_scoring.py`/Goldens; untracked #366/#369/#370-Docs) **inkl.
   `ChannelPreviewBlock.svelte`** — genau eine A/C-Datei. Bauen im Hauptordner würde auf fremden,
   uncommitteten Edits aufsetzen und beim Commit `git add -A`-Verschmutzung riskieren. → **#375 in
   isolierter `gz-workspace` bauen** (siehe [[reference_gz_workspace]], [[feedback_shared_index_commit]]).
2. **Pre-Commit-Gate / volle Backend-Suite (B):** Backend-Test-Edits triggern die volle pytest-Suite.
   Issue-Body nennt „5 fremde rote Tests auf main" — seit #355 jedoch grün
   ([[project_precommit_gate_full_suite_block]], [[project_issue_355_paused]]). Vor B-Commit Suite-Status
   im sauberen Workspace verifizieren; #366-WIP darf das Bild nicht verfälschen.
3. **Wert-Frage Teil A (strategisch):** Memory [[project_frontend_purpose]] — „Frontend = Desktop-Planungstool,
   unterwegs nur E-Mail/SMS". Ein volles Mobile-Redesign des Editors widerspricht dieser Linie; das Issue
   selbst markiert A als „optional und niedrig priorisiert". → PO-Entscheidung nötig, ob A überhaupt gebaut wird.
4. **Scope-Bündelung:** A (groß, Frontend) und B (winzig, Backend) sind technisch entkoppelt und sollten
   getrennte Workflows/Commits sein, nicht ein gemischter Backend+Frontend-Commit.

## PO-Entscheidung (2026-05-25)
**Scope = ausschließlich Teil B** (die zwei Backend-Test-Nits). Teil A (Mobile-Akkordeon) und Teil C
(Vorschau-Kosmetik) werden **nicht** umgesetzt — A widerspricht dem Desktop-Planungstool-Fokus, C ist
marginal. Damit ist #375 ein **reines, additives Backend-Test-Hardening** ohne Produktionscode-Änderung.

**Implikation TDD:** Es gibt keinen RED-Zustand — die Implementierung (#363) ist nachweislich korrekt;
die ergänzten Assertions bestätigen bestehend-korrektes Verhalten und sind sofort grün. Kein neues Modul,
daher kein Spec-Writer (Triviales). Bestehende Spec: `issue_363_signal_telegram_preview.md`.
