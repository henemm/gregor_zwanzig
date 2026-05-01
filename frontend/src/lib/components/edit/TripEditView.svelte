<script lang="ts">
	import type { Trip, Stage } from '$lib/types.js';
	import { api } from '$lib/api.js';
	import { goto } from '$app/navigation';
	import AccordionSection from './AccordionSection.svelte';
	import WizardStep1Route from '$lib/components/wizard/WizardStep1Route.svelte';
	import WizardStep2Stages from '$lib/components/wizard/WizardStep2Stages.svelte';
	import WizardStep3Weather from '$lib/components/wizard/WizardStep3Weather.svelte';
	import WizardStep4ReportConfig from '$lib/components/wizard/WizardStep4ReportConfig.svelte';

	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();

	// State: tiefe Kopie damit Cancel ohne Persistenz auch State verwirft
	let tripName = $state(trip.name);
	let stages: Stage[] = $state(JSON.parse(JSON.stringify(trip.stages ?? [])));
	let displayConfig: Record<string, unknown> | undefined = $state(
		trip.display_config ? JSON.parse(JSON.stringify(trip.display_config)) : undefined
	);
	let reportConfig: Record<string, unknown> | undefined = $state(
		trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : undefined
	);

	type SectionId = 'route' | 'etappen' | 'wetter' | 'reports';
	let openSection: SectionId | null = $state('etappen');

	let saveError: string | null = $state(null);
	let saving = $state(false);

	// Factory Pattern fuer onToggle (Safari-Closure-Binding-Schutz, siehe CLAUDE.md)
	function makeToggleHandler(section: SectionId) {
		return function doToggle() {
			openSection = openSection === section ? null : section;
		};
	}

	function makeSaveHandler() {
		return async function doSave() {
			saveError = null;
			saving = true;
			try {
				const updated: Trip = {
					...trip,
					name: tripName,
					stages,
					display_config: displayConfig,
					report_config: reportConfig,
				};
				await api.put(`/api/trips/${trip.id}`, updated);
				goto('/trips');
			} catch (e: unknown) {
				saveError = (e as { detail?: string })?.detail
					?? (e as { error?: string })?.error
					?? (e instanceof Error ? e.message : 'Speichern fehlgeschlagen');
			} finally {
				saving = false;
			}
		};
	}

	function makeCancelHandler() {
		return function doCancel() {
			goto('/trips');
		};
	}

	const onSave = makeSaveHandler();
	const onCancel = makeCancelHandler();
</script>

<div data-testid="trip-edit-view" class="max-w-3xl mx-auto p-4 pb-24">
	<h1 class="text-xl font-semibold mb-4">Trip bearbeiten: {trip.name}</h1>

	<AccordionSection
		id="route"
		title="Route"
		open={openSection === 'route'}
		onToggle={makeToggleHandler('route')}
	>
		<WizardStep1Route bind:tripName bind:stages mode="edit" />
	</AccordionSection>

	<AccordionSection
		id="etappen"
		title="Etappen"
		open={openSection === 'etappen'}
		onToggle={makeToggleHandler('etappen')}
	>
		<WizardStep2Stages bind:stages />
	</AccordionSection>

	<AccordionSection
		id="wetter"
		title="Wetter"
		open={openSection === 'wetter'}
		onToggle={makeToggleHandler('wetter')}
	>
		<WizardStep3Weather bind:displayConfig mode="edit" />
	</AccordionSection>

	<AccordionSection
		id="reports"
		title="Reports"
		open={openSection === 'reports'}
		onToggle={makeToggleHandler('reports')}
	>
		<WizardStep4ReportConfig bind:reportConfig mode="edit" />
	</AccordionSection>

	{#if saveError}
		<div class="mt-4 p-3 rounded bg-destructive/10 text-destructive text-sm">
			{saveError}
		</div>
	{/if}

	<div class="fixed bottom-0 left-0 right-0 bg-background border-t p-3
	            flex gap-2 justify-end">
		<div class="max-w-3xl mx-auto w-full flex gap-2 justify-end">
			<button
				type="button"
				data-testid="edit-cancel-btn"
				class="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 min-h-[44px] text-sm font-medium hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
				onclick={onCancel}
				disabled={saving}
			>
				Abbrechen
			</button>
			<button
				type="button"
				data-testid="edit-save-btn"
				class="inline-flex items-center justify-center rounded-md bg-primary px-4 min-h-[44px] text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
				onclick={onSave}
				disabled={saving}
			>
				{saving ? 'Speichere…' : 'Speichern'}
			</button>
		</div>
	</div>
</div>
