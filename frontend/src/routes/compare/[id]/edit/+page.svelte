<script lang="ts">
	// Issue #440 — Compare-Wizard Edit-Modus Mount-Punkt.
	// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md §1
	//
	// Factory-Pattern: State im script-Block instanziiert + aus Subscription prefilled.

	import { setContext } from 'svelte';
	import { CompareWizardState } from '$lib/components/compare/compareWizardState.svelte';
	import CompareWizard from '$lib/components/compare/CompareWizard.svelte';
	import type { ActivityProfile } from '$lib/types';

	let { data } = $props();

	const state = new CompareWizardState();
	state.isEditMode = true;
	state.subscriptionId = data.subscription.id;
	state.name = data.subscription.name;
	state.activityProfile =
		(data.subscription.activity_profile as ActivityProfile | null) ?? null;
	state.pickedIds = data.subscription.locations ?? [];
	state.subscriptionEnabled = data.subscription.enabled;
	state.existingDisplayConfig =
		(data.subscription.display_config as Record<string, unknown>) ?? {};
	state.region = (state.existingDisplayConfig.region as string) ?? '';

	setContext('compare-wizard-state', state);
</script>

<CompareWizard locations={data.locations} />
