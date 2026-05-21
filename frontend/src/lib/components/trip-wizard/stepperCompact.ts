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
