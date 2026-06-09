<script lang="ts">
	// Issue #678 (Epic #677) — Compare-Editor Create-Modus Mount-Punkt.
	// Ersetzt die Stepper-Shell (CompareWizard) durch den Progressive-Tab-Editor.
	// Spec: docs/specs/modules/issue_678_compare_editor_shell.md
	//
	// Factory-Pattern: State im script-Block instanziiert (NICHT Top-Level-Modul-Singleton),
	// damit Svelte-5-Runes in Safari die Reaktivitaet behalten. Beide Contexts bleiben
	// gesetzt: 'compare-wizard-state' (Editor + gemountete Steps) und
	// 'compare-wizard-profile' (Step5Versand-Kanal-Hints).

	import { setContext } from 'svelte';
	import { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import CompareEditor from '$lib/components/compare/CompareEditor.svelte';

	let { data } = $props();
	const state = new CompareWizardState();
	setContext('compare-wizard-state', state);
	setContext('compare-wizard-profile', data.profile ?? null);
</script>

<CompareEditor mode="create" locations={data.locations} />
