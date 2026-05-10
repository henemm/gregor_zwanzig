// Stepper-State-Helper fuer Epic #136 Sub-Spec #160.
// Quelle: docs/specs/modules/epic_136_step0_shell.md §3
//
// Pure-Function-Logik, ausgelagert aus Stepper.svelte, damit der Stepper-Test
// (node --experimental-strip-types) sie ohne Svelte-Compiler importieren kann.

export type StepperStepState = 'done' | 'active' | 'pending';

/**
 * Liefert den Status eines Stepper-Indikators.
 *
 * @param index   0-basierter Index des Steps im Stepper
 * @param current 1-basierter aktueller Step (1..4)
 *
 * - i + 1 < current  -> 'done'
 * - i + 1 === current -> 'active'
 * - i + 1 > current  -> 'pending'
 */
export function stepperStateOf(index: number, current: number): StepperStepState {
	if (index + 1 < current) return 'done';
	if (index + 1 === current) return 'active';
	return 'pending';
}
