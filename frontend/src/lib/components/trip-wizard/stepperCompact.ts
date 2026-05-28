// Compact-Stepper-Formatter fuer bug_271_wizard_mobile_stepper.
// Spec: docs/specs/modules/bug_271_wizard_mobile_stepper.md
//
// Pure-Function-Logik, ausgelagert damit der Stepper-Test
// (node --experimental-strip-types) sie ohne Svelte-Compiler importieren kann.

/**
 * Liefert den kompakten Stepper-Text fuer Mobile-Viewports.
 *
 * Format: "{current} / {labels.length} · {labels[current - 1]}"
 *
 * @param current 1-basierter aktueller Step
 * @param labels  Array der Step-Labels (1-basiert via current - 1 indiziert)
 */
export function compactStepperText(current: number, labels: string[]): string {
	return `${current} / ${labels.length} · ${labels[current - 1]}`;
}

// =============================================================================
// Issue #430 — Mobile-Progressbar mit 5 Segmenten
// =============================================================================

export type SegmentState = 'done' | 'active' | 'pending';

/**
 * Liefert den Zustand jedes Progressbar-Segments fuer den Mobile-Stepper.
 *
 * - Segment-Index < current  → 'done'
 * - Segment-Index === current → 'active'
 * - Segment-Index > current  → 'pending'
 *
 * @param current 1-basierter aktueller Step (1..total)
 * @param total   Gesamtanzahl Steps
 * @returns Array der Laenge `total` mit 'done' | 'active' | 'pending'
 */
export function progressBarSegments(current: number, total: number): SegmentState[] {
	const result: SegmentState[] = [];
	for (let i = 0; i < total; i++) {
		const step = i + 1;
		if (step < current) {
			result.push('done');
		} else if (step === current) {
			result.push('active');
		} else {
			result.push('pending');
		}
	}
	return result;
}
