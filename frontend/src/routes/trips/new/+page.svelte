<script lang="ts">
	import { setContext } from 'svelte';
	import { WizardState } from '$lib/components/trip-wizard/wizardState.svelte';
	import TripWizardShell from '$lib/components/trip-wizard/TripWizardShell.svelte';

	// Factory-Pattern: pro Page-Mount eine eigene State-Instanz.
	// NIEMALS top-level: Safari-Reaktivitaetsrisiko mit Svelte-5-Runen.
	const state = new WizardState();
	setContext('trip-wizard-state', state);
</script>

<TripWizardShell />
