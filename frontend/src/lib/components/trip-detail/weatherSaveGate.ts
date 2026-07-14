// Issue #1234 — Auto-Save-Gate für den Inhalt-Tab (WeatherMetricsTab).
// Spec: docs/specs/modules/issue_1234_autosave_hydration_gate.md
//   § Implementation Details (Entscheidungstabelle), § Acceptance Criteria
// Vorbild-Muster (Daten-Gate statt Timing-Guard):
//   shared/corridor-editor/corridorEditorState.ts:517-519 `saveGateDecision()`
//
// Reine Entscheidungsfunktion — kein DOM, kein Svelte-State, unit-testbar
// ohne Mocks (weatherSaveGate.test.ts).
//
// Spec-Changelog v1.2 (Adversary-Finding F001, Verdict BROKEN): die frühere
// Fassung dieser Datei entschied zusätzlich nach Datenlage ("würde der Payload
// leeren?" über `nextMetricIds`/`savedMetricIds`). Das erlaubte einen Schreib-
// zugriff ohne Nutzeraktion immer dann, wenn der Payload NICHT leerte — genau
// der Fall, wenn `EditReportConfigSection` beim Mounten die Report-Konfiguration
// normalisiert und zurückschreibt. Die Datenlage-Prüfung war der Versuch, den
// Bug an seinen Symptomen zu erkennen statt an seiner Ursache.
//
// Neue, vollständige Regel: jeder legitime Speichervorgang folgt einer echten
// Nutzergeste. Es gibt keinen Fall, in dem ohne Zutun des Nutzers geschrieben
// werden müsste — daher genügt ein einziges Absichts-Flag, unabhängig davon,
// ob der Payload leer wäre oder nicht. AC-4 (bewusst alles abwählen) bleibt
// möglich, weil das Abwählen selbst die Geste IST.
//
// Entscheidungstabelle (Spec § Implementation Details, v1.2):
//
//   Katalog geladen | Nutzer hat im Tab etwas getan | Entscheidung
//   ----------------|-------------------------------|-------------
//   nein            | —                             | skip
//   ja              | nein                          | skip (BUG #1234 / AC-6)
//   ja              | ja                             | save (AC-4 / AC-5)

export interface WeatherSaveGateInput {
	/** true nur nach erfolgreichem Katalog-Fetch (nicht im finally-Block). */
	catalogLoaded: boolean;
	/** Ausschließlich aus echten DOM-Ereignissen gesetzt — nie in einem $effect. */
	userTouched: boolean;
}

export function weatherSaveGate(input: WeatherSaveGateInput): 'save' | 'skip' {
	if (!input.catalogLoaded) return 'skip';
	if (!input.userTouched) return 'skip';
	return 'save';
}
