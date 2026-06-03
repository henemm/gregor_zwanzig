<script lang="ts">
	import { setContext } from 'svelte';
	import { WizardState } from '$lib/components/trip-wizard/wizardState.svelte';
	import { TripWizardShell } from '$lib/components/organisms';

	let { data } = $props();

	// Factory-Pattern: pro Page-Mount eine eigene State-Instanz.
	// NIEMALS top-level: Safari-Reaktivitaetsrisiko mit Svelte-5-Runen.
	const state = new WizardState();
	if (data.templateTrip) {
		state.fromTemplate(data.templateTrip);
	}
	setContext('trip-wizard-state', state);

	// Issue #412 — Profil (Kontaktdaten je Kanal) fuer Step 4 bereitstellen.
	// null-tolerant: bei fehlgeschlagenem Loader bleibt das Profil null.
	// Wert einmal lokal lesen (profile ist beim Page-Mount statisch) — vermeidet
	// die Svelte-5-Warnung "captures the initial value of data".
	const profile = data.profile ?? null;
	setContext('trip-wizard-profile', profile);
</script>

{#if data.templateTrip}
	<p class="template-hint">Vorlage: {data.templateTrip.name}</p>
{/if}

<TripWizardShell />

<style>
	.template-hint {
		text-align: center;
		color: var(--g-ink-3);
		font-size: 0.85rem;
		margin: 0.5rem 0 0;
	}
</style>
