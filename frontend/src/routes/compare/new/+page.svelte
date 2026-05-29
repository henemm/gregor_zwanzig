<script lang="ts">
	// Issue #440 — Compare-Wizard Create-Modus Mount-Punkt.
	// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md §1
	//
	// Factory-Pattern: State im script-Block instanziiert (NICHT Top-Level-Modul-Singleton),
	// damit Svelte-5-Runes in Safari die Reaktivitaet behalten.

	import { setContext } from 'svelte';
	import { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import CompareWizard from '$lib/components/compare/CompareWizard.svelte';

	let { data } = $props();
	const state = new CompareWizardState();
	setContext('compare-wizard-state', state);
</script>

<CompareWizard locations={data.locations} />
