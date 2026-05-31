<script lang="ts">
	// Shell fuer den Compare-Wizard (Issue #440, Epic #438).
	// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md
	//
	// Konsumiert CompareWizardState via getContext('compare-wizard-state').
	// Die Instanziierung erfolgt im +page.svelte Mount-Punkt (Factory-Pattern,
	// Safari-Reaktivitaets-Fix).

	import { getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import { ConfirmDialog } from '$lib/components/molecules';
	import type { CompareWizardState } from './compareWizardState.svelte';
	import Stepper from '$lib/components/trip-wizard/Stepper.svelte';
	import Step1Vergleich from './steps/Step1Vergleich.svelte';
	import Step2Orte from './steps/Step2Orte.svelte';
	import Step3Idealwerte from './steps/Step3Idealwerte.svelte';
	import Step4Layout from './steps/Step4Layout.svelte';
	import Step5Versand from './steps/Step5Versand.svelte';
	import type { Location } from '$lib/types';

	interface Props {
		locations?: Location[];
	}
	let { locations = [] }: Props = $props();

	const wiz = getContext<CompareWizardState>('compare-wizard-state');

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
		wiz.isEditMode
			? 'ORTS-VERGLEICH · BEARBEITEN'
			: `SCHRITT ${wiz.currentStep} VON 5 · NEUER ORTS-VERGLEICH`
	);

	const saveLabel = $derived(wiz.saveStatus === 'saving' ? 'Speichern...' : 'Speichern');

	// Issue #492 — Modaler Bestätigungsdialog statt nativer Browser-Abfrage
	// (lässt sich in modernen Browsern ausblenden und bietet keine Gestaltung).
	let cancelDialogOpen = $state(false);
	let discardDialogOpen = $state(false);

	function handleCancel() {
		const isDirty =
			wiz.name !== '' ||
			wiz.pickedIds.length > 0 ||
			wiz.region !== '' ||
			wiz.activityProfile !== null;
		if (isDirty) {
			cancelDialogOpen = true;
		} else {
			void goto('/compare');
		}
	}

	function handleDiscard() {
		discardDialogOpen = true;
	}

	function handleNext() {
		wiz.nextStep();
	}

	function handleSave() {
		void wiz.save();
	}

	function handleStepClick(step: number) {
		wiz.goToStep(step);
	}

	function handleToggleEnabled() {
		void wiz.toggleEnabled();
	}
</script>

<div data-testid="compare-wizard-shell" class="max-w-3xl mx-auto py-6 px-4">
	<TopoBg opacity={0.4}>
		<div class="p-6 rounded-lg mb-6">
			<header class="space-y-1 mb-4">
				<Eyebrow data-testid="compare-wizard-header-eyebrow">{eyebrow}</Eyebrow>
				{#if wiz.isEditMode}
					<div class="flex items-center gap-2">
						<h1 data-testid="compare-wizard-header-h1" class="text-2xl font-bold">
							{wiz.name}
						</h1>
						<span
							data-testid="compare-wizard-header-status-pill"
							class={`text-xs font-mono px-2 py-0.5 rounded-full ${
								wiz.subscriptionEnabled
									? 'bg-[var(--g-success)]/15 text-[var(--g-success)]'
									: 'bg-[var(--g-ink-faint)]/20 text-[var(--g-ink-muted)]'
							}`}
						>
							{wiz.subscriptionEnabled ? 'aktiv' : 'pausiert'}
						</span>
					</div>
					<h2 class="text-base text-[var(--g-ink-muted)] mt-1">
						{stepTitles[wiz.currentStep]}
					</h2>
				{:else}
					<h1 data-testid="compare-wizard-header-h1" class="text-2xl font-bold">
						{stepTitles[wiz.currentStep]}
					</h1>
				{/if}
			</header>

			<Stepper
				current={wiz.currentStep}
				labels={stepLabels}
				subLabels={stepSubLabels}
				onStepClick={wiz.isEditMode ? handleStepClick : undefined}
				testidPrefix="compare-wizard"
			/>

			{#if wiz.isEditMode}
				<div class="flex gap-2 justify-end mt-3">
					<Btn variant="outline" size="sm" disabled>
						Briefing-Vorschau
					</Btn>
					<Btn variant="outline" size="sm" onclick={handleToggleEnabled}>
						{wiz.subscriptionEnabled ? 'Pausieren' : 'Aktivieren'}
					</Btn>
				</div>
			{/if}
		</div>
	</TopoBg>

	<div class="min-h-[300px] mt-6">
		{#if wiz.currentStep === 1}
			<Step1Vergleich />
		{:else if wiz.currentStep === 2}
			<Step2Orte {locations} />
		{:else if wiz.currentStep === 3}
			<Step3Idealwerte />
		{:else if wiz.currentStep === 4}
			<Step4Layout />
		{:else if wiz.currentStep === 5}
			<Step5Versand />
		{:else}
			<div class="text-[var(--g-ink-muted)] text-center py-12">
				Schritt {wiz.currentStep} — folgt in einem weiteren Issue.
			</div>
		{/if}
	</div>

	{#if wiz.saveStatus !== 'idle'}
		<div role="status" aria-live="polite" class="mt-4 min-h-[1.5rem] text-sm">
			{#if wiz.saveStatus === 'error'}
				<span class="text-[var(--g-danger)]">{wiz.saveError}</span>
			{:else if wiz.saveStatus === 'ok'}
				<span class="text-[var(--g-success)]">Gespeichert</span>
			{/if}
		</div>
	{/if}

	<div
		class="flex items-center justify-between mt-8 pt-4 border-t border-[var(--g-ink-faint)]/30"
	>
		{#if wiz.isEditMode}
			<Btn
				data-testid="compare-wizard-footer-discard"
				variant="ghost"
				size="md"
				onclick={handleDiscard}
			>
				Verwerfen
			</Btn>
			<div style:display="flex" style:gap="8px" style:align-items="center">
				{#if wiz.currentStep > 1}
					<Btn
						data-testid="compare-wizard-footer-prev"
						variant="outline"
						size="md"
						onclick={() => wiz.prevStep()}
					>
						← Zurück
					</Btn>
				{/if}
				{#if wiz.currentStep < 5}
					<Btn
						data-testid="compare-wizard-footer-next-edit"
						variant="outline"
						size="md"
						onclick={handleNext}
						disabled={!wiz.canAdvanceCurrent}
					>
						Weiter →
					</Btn>
				{/if}
				<Btn
					data-testid="compare-wizard-footer-save"
					variant="accent"
					size="md"
					onclick={handleSave}
					disabled={wiz.saveStatus === 'saving'}
				>
					{saveLabel}
				</Btn>
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
			{#if wiz.currentStep < 5}
				<Btn
					data-testid="compare-wizard-footer-next"
					variant="accent"
					size="md"
					onclick={handleNext}
					disabled={!wiz.canAdvanceCurrent}
				>
					Weiter →
				</Btn>
			{:else}
				<Btn
					data-testid="compare-wizard-footer-activate"
					variant="accent"
					size="md"
					onclick={handleSave}
					disabled={!wiz.canAdvanceStep5 || wiz.saveStatus === 'saving'}
				>
					Briefing aktivieren →
				</Btn>
			{/if}
		{/if}
	</div>

	<ConfirmDialog
		open={cancelDialogOpen}
		title="Wizard abbrechen?"
		description="Deine Eingaben gehen verloren."
		confirmLabel="Abbrechen"
		confirmVariant="destructive"
		cancelLabel="Weiter ausfüllen"
		onConfirm={() => {
			cancelDialogOpen = false;
			void goto('/compare');
		}}
		onCancel={() => (cancelDialogOpen = false)}
		onOpenChange={(open) => {
			if (!open) cancelDialogOpen = false;
		}}
	/>

	<ConfirmDialog
		open={discardDialogOpen}
		title="Änderungen verwerfen?"
		description="Alle Änderungen an diesem Vergleich werden verworfen."
		confirmLabel="Verwerfen"
		confirmVariant="destructive"
		cancelLabel="Weiter bearbeiten"
		onConfirm={() => {
			discardDialogOpen = false;
			void goto(
				wiz.isEditMode && wiz.subscriptionId
					? '/compare/' + wiz.subscriptionId
					: '/compare'
			);
		}}
		onCancel={() => (discardDialogOpen = false)}
		onOpenChange={(open) => {
			if (!open) discardDialogOpen = false;
		}}
	/>
</div>
