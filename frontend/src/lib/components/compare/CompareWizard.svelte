<script lang="ts">
	// Shell fuer den Compare-Wizard (Issue #440, Epic #438).
	// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
	//
	// Konsumiert CompareWizardState via getContext('compare-wizard-state').
	// Die Instanziierung erfolgt im +page.svelte Mount-Punkt (Factory-Pattern,
	// Safari-Reaktivitaets-Fix).

	import { getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { Btn } from '$lib/components/ui/btn';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { TopoBg } from '$lib/components/ui/topo';
	import type { CompareWizardState } from './compareWizardState.svelte';
	import Stepper from '$lib/components/trip-wizard/Stepper.svelte';
	import Step1Vergleich from './steps/Step1Vergleich.svelte';
	import Step2Orte from './steps/Step2Orte.svelte';
	import Step5Versand from './steps/Step5Versand.svelte';
	import type { Location } from '$lib/types';

	interface Props {
		locations?: Location[];
	}
	let { locations = [] }: Props = $props();

	const state = getContext<CompareWizardState>('compare-wizard-state');

	const stepLabels = ['Vergleich', 'Orte', 'Idealwerte', 'Layout', 'Versand'];
	const stepSubLabels = [
		'Name & Profil',
		'Standorte auswählen',
		'Metriken konfigurieren',
		'Ausgabe gestalten',
		'Briefings aktivieren'
	];

	const stepTitles: Record<number, string> = {
		1: 'Vergleich — wie heißt dein Briefing?',
		2: 'Orte wählen',
		3: 'Idealwerte — was ist gutes Wetter für dich?',
		4: 'Layout — wie sieht das Briefing aus?',
		5: 'Versand — wann und wohin?'
	};

	const eyebrow = $derived(
		state.isEditMode
			? 'ORTS-VERGLEICH · BEARBEITEN'
			: `SCHRITT ${state.currentStep} VON 5 · NEUER ORTS-VERGLEICH`
	);

	const saveLabel = $derived(state.saveStatus === 'saving' ? 'Speichern...' : 'Speichern');

	function handleCancel() {
		const isDirty =
			state.name !== '' ||
			state.pickedIds.length > 0 ||
			state.region !== '' ||
			state.activityProfile !== null;
		if (isDirty && !confirm('Änderungen verwerfen?')) return;
		void goto('/compare');
	}

	function handleDiscard() {
		if (!confirm('Alle Änderungen verwerfen?')) return;
		void goto('/compare');
	}

	function handleNext() {
		state.nextStep();
	}

	function handleSave() {
		void state.save();
	}

	function handleStepClick(step: number) {
		state.goToStep(step);
	}

	function handleToggleEnabled() {
		void state.toggleEnabled();
	}
</script>

<div data-testid="compare-wizard-shell" class="max-w-3xl mx-auto py-6 px-4">
	<TopoBg opacity={0.4}>
		<div class="p-6 rounded-lg mb-6">
			<header class="space-y-1 mb-4">
				<Eyebrow data-testid="compare-wizard-header-eyebrow">{eyebrow}</Eyebrow>
				{#if state.isEditMode}
					<div class="flex items-center gap-2">
						<h1 data-testid="compare-wizard-header-h1" class="text-2xl font-bold">
							{state.name}
						</h1>
						<span
							data-testid="compare-wizard-header-status-pill"
							class={`text-xs font-mono px-2 py-0.5 rounded-full ${
								state.subscriptionEnabled
									? 'bg-[var(--g-success)]/15 text-[var(--g-success)]'
									: 'bg-[var(--g-ink-faint)]/20 text-[var(--g-ink-muted)]'
							}`}
						>
							{state.subscriptionEnabled ? 'aktiv' : 'pausiert'}
						</span>
					</div>
					<h2 class="text-base text-[var(--g-ink-muted)] mt-1">
						{stepTitles[state.currentStep]}
					</h2>
				{:else}
					<h1 data-testid="compare-wizard-header-h1" class="text-2xl font-bold">
						{stepTitles[state.currentStep]}
					</h1>
				{/if}
			</header>

			<Stepper
				current={state.currentStep}
				labels={stepLabels}
				subLabels={stepSubLabels}
				onStepClick={state.isEditMode ? handleStepClick : undefined}
				testidPrefix="compare-wizard"
			/>

			{#if state.isEditMode}
				<div class="flex gap-2 justify-end mt-3">
					<Btn variant="outline" size="sm" disabled>
						Briefing-Vorschau
					</Btn>
					<Btn variant="outline" size="sm" onclick={handleToggleEnabled}>
						{state.subscriptionEnabled ? 'Pausieren' : 'Aktivieren'}
					</Btn>
				</div>
			{/if}
		</div>
	</TopoBg>

	<div class="min-h-[300px] mt-6">
		{#if state.currentStep === 1}
			<Step1Vergleich />
		{:else if state.currentStep === 2}
			<Step2Orte {locations} />
		{:else if state.currentStep === 5}
			<Step5Versand />
		{:else}
			<div class="text-[var(--g-ink-muted)] text-center py-12">
				Schritt {state.currentStep} — folgt in einem weiteren Issue.
			</div>
		{/if}
	</div>

	{#if state.saveStatus !== 'idle'}
		<div role="status" aria-live="polite" class="mt-4 min-h-[1.5rem] text-sm">
			{#if state.saveStatus === 'error'}
				<span class="text-[var(--g-danger)]">{state.saveError}</span>
			{:else if state.saveStatus === 'ok'}
				<span class="text-[var(--g-success)]">Gespeichert</span>
			{/if}
		</div>
	{/if}

	<div
		class="flex items-center justify-between mt-8 pt-4 border-t border-[var(--g-ink-faint)]/30"
	>
		{#if state.isEditMode}
			<Btn
				data-testid="compare-wizard-footer-discard"
				variant="ghost"
				size="md"
				onclick={handleDiscard}
			>
				Verwerfen
			</Btn>
			<div class="flex flex-col items-center gap-1">
				<Btn
					data-testid="compare-wizard-footer-save"
					variant="accent"
					size="md"
					onclick={handleSave}
					disabled={state.saveStatus === 'saving'}
				>
					{saveLabel}
				</Btn>
				<p class="text-xs text-[var(--g-ink-muted)]">
					Änderungen werden beim Speichern übernommen
				</p>
			</div>
		{:else}
			<Btn
				data-testid="compare-wizard-footer-cancel"
				variant="ghost"
				size="md"
				onclick={handleCancel}
			>
				Abbrechen
			</Btn>
			{#if state.currentStep < 5}
				<Btn
					data-testid="compare-wizard-footer-next"
					variant="accent"
					size="md"
					onclick={handleNext}
					disabled={!state.canAdvanceCurrent}
				>
					Weiter →
				</Btn>
			{:else}
				<Btn
					data-testid="compare-wizard-footer-activate"
					variant="accent"
					size="md"
					onclick={handleSave}
					disabled={!state.canAdvanceStep5 || state.saveStatus === 'saving'}
				>
					Briefing aktivieren →
				</Btn>
			{/if}
		{/if}
	</div>
</div>
