<script lang="ts">
	import type { Trip, Stage } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button/index.js';
	import WizardStepper from './WizardStepper.svelte';
	import WizardStep1Route from './WizardStep1Route.svelte';
	import WizardStep2Stages from './WizardStep2Stages.svelte';
	import WizardStep3Weather from './WizardStep3Weather.svelte';

	interface Props {
		mode: 'create' | 'edit';
		existingTrip?: Trip;
	}
	let { mode, existingTrip }: Props = $props();

	const stepLabels = ['Route', 'Etappen', 'Wetter', 'Reports'];

	let currentStep = $state(1);
	let tripName = $state(existingTrip?.name ?? '');
	let tripId = $state(existingTrip?.id ?? '');
	let stages: Stage[] = $state(
		existingTrip ? JSON.parse(JSON.stringify(existingTrip.stages)) : []
	);
	let displayConfig: Record<string, unknown> | undefined = $state(existingTrip?.display_config);
	let saveError: string | null = $state(null);
	let saving = $state(false);

	function canProceed(): boolean {
		if (currentStep === 1) return tripName.trim().length > 0;
		if (currentStep === 2) return stages.length > 0 && stages.every(s => s.waypoints.length > 0);
		return true;
	}

	function next() {
		if (canProceed() && currentStep < 4) {
			currentStep++;
		}
	}

	function back() {
		if (currentStep > 1) {
			currentStep--;
		}
	}

	function cancel() {
		goto('/trips');
	}

	async function save() {
		saveError = null;
		saving = true;
		const trip: Trip = {
			id: tripId || crypto.randomUUID().slice(0, 8),
			name: tripName.trim(),
			stages,
			display_config: displayConfig,
			...(existingTrip && {
				avalanche_regions: existingTrip.avalanche_regions,
				aggregation: existingTrip.aggregation,
				weather_config: existingTrip.weather_config,
				report_config: existingTrip.report_config
			})
		};
		try {
			if (mode === 'create') {
				await api.post('/api/trips', trip);
			} else {
				await api.put(`/api/trips/${trip.id}`, trip);
			}
			goto('/trips');
		} catch (e: unknown) {
			saveError = (e as { error?: string; detail?: string })?.detail
				?? (e as { error?: string })?.error
				?? (e instanceof Error ? e.message : 'Unbekannter Fehler');
		} finally {
			saving = false;
		}
	}

	let proceedable = $derived(canProceed());
</script>

<div data-testid="trip-wizard" class="max-w-3xl mx-auto py-6 px-4">
	<h1 class="text-2xl font-bold mb-6">
		{mode === 'create' ? 'Neuer Trip' : 'Trip bearbeiten'}
	</h1>

	<WizardStepper steps={stepLabels} current={currentStep - 1} />

	<div class="min-h-[300px]">
		{#if currentStep === 1}
			<WizardStep1Route bind:tripName bind:stages {mode} />
		{:else if currentStep === 2}
			<WizardStep2Stages bind:stages />
		{:else if currentStep === 3}
			<WizardStep3Weather bind:displayConfig {mode} />
		{:else if currentStep === 4}
			<div class="flex items-center justify-center h-48 text-muted-foreground">
				<p>Kommt in W3 -- Report-Konfiguration</p>
			</div>
		{/if}
	</div>

	{#if saveError}
		<div class="mt-4 p-3 rounded-md bg-destructive/10 text-destructive text-sm">
			{saveError}
		</div>
	{/if}

	<div class="flex items-center justify-between mt-8 pt-4 border-t">
		<div>
			{#if currentStep > 1}
				<Button data-testid="wizard-back" variant="outline" onclick={back}>Zurueck</Button>
			{/if}
		</div>
		<div class="flex items-center gap-2">
			<Button data-testid="wizard-cancel" variant="ghost" onclick={cancel}>Abbrechen</Button>
			{#if currentStep < 4}
				<Button data-testid="wizard-next" onclick={next} disabled={!proceedable}>Weiter</Button>
			{:else}
				<Button data-testid="wizard-save" onclick={save} disabled={saving}>
					{saving ? 'Speichern...' : 'Speichern'}
				</Button>
			{/if}
		</div>
	</div>
</div>
