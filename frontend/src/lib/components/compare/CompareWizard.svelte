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
	import Step1Vergleich from './steps/Step1Vergleich.svelte';
	import Step2Orte from './steps/Step2Orte.svelte';
	import Step3Idealwerte from './steps/Step3Idealwerte.svelte';
	import Step4Layout from './steps/Step4Layout.svelte';
	import Step5Versand from './steps/Step5Versand.svelte';
	import type { ActivityProfile, Location } from '$lib/types';

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

	// Issue #547 AC-8: Override-Flag — true wenn Nutzer das Profil in Step 1
	// manuell gewählt hat. Blockiert den Auto-Apply-$effect bis pickedIds sich
	// erneut ändert (AC-9 Reset).
	let profileManuallyOverridden = $state(false);

	// Issue #547 AC-6/7: dominantProfile — das Aktivitätsprofil, das von mehr
	// als 50 % der ausgewählten Locations getragen wird. "allgemein" und
	// Locations ohne Profil zählen nicht zur Mehrheit. Bei 50/50 oder leerer
	// Auswahl: null (kein Auto-Set).
	const dominantProfile = $derived.by((): ActivityProfile | null => {
		const profiled = wiz.pickedIds
			.map((id) => locations.find((l) => l.id === id)?.activity_profile)
			.filter((p): p is ActivityProfile => Boolean(p) && p !== 'allgemein');
		if (profiled.length === 0) return null;
		const counts = new Map<ActivityProfile, number>();
		for (const p of profiled) counts.set(p, (counts.get(p) ?? 0) + 1);
		const [top] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
		return top[1] / profiled.length > 0.5 ? top[0] : null;
	});

	// Issue #547 AC-6: Auto-Apply — setzt wiz.activityProfile auf dominantProfile,
	// solange kein manuelles Override aktiv ist und keine Idealwerte bereits
	// konfiguriert wurden (Edit-Schutz: laufende Step-3-Konfiguration bleibt
	// unberührt).
	$effect(() => {
		if (
			!profileManuallyOverridden &&
			!wiz.isEditMode &&
			dominantProfile &&
			wiz.activityProfile !== dominantProfile &&
			Object.keys(wiz.idealRanges).length === 0
		) {
			wiz.activityProfile = dominantProfile;
		}
	});

	// Issue #547 AC-9: Override-Reset — wenn der Nutzer in Step 2 die
	// Location-Auswahl ändert, wird das manuelle Override verworfen und der
	// Auto-Apply-$effect kann beim nächsten dominantProfile-Wechsel wieder
	// greifen.
	$effect(() => {
		wiz.pickedIds; // Abhängigkeit tracken
		profileManuallyOverridden = false;
	});

	function handleManualProfileChange() {
		profileManuallyOverridden = true;
	}

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
			<!-- Edit-Header (Issue #582 — CW_EditHeader) -->
			{#if wiz.isEditMode}<!-- Edit-Header: Speichern + Abbrechen -->
				<div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px">
					<div style="min-width: 0; flex: 1">
						<Eyebrow data-testid="compare-wizard-header-eyebrow" style="margin-bottom: 6px">ORTS-VERGLEICH · BEARBEITEN</Eyebrow>
						<div style="display: flex; align-items: center; gap: 10px">
							<h1 data-testid="compare-wizard-header-h1" style="font-size: 30px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.1; margin: 0">{wiz.name || 'Unbenannt'}</h1>
						</div>
					</div>
					<div style="display: flex; gap: 8px; flex-shrink: 0">
						<Btn variant="ghost" size="md" onclick={handleCancel}>Abbrechen</Btn>
						<Btn variant="primary" size="md" onclick={handleSave}>{saveLabel}</Btn>
					</div>
				</div>
			{:else}
				<Eyebrow data-testid="compare-wizard-header-eyebrow" style="margin-bottom: 8px">Schritt {wiz.currentStep} von 5 · Neuer Orts-Vergleich</Eyebrow>
				<div data-testid="compare-wizard-header-h1" style="font-size: 30px; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 28px; color: var(--g-ink); text-wrap: balance">
					{stepTitles[wiz.currentStep]}
				</div>
			{/if}

			<!-- Custom Stepper (Issue #582 — CW_Stepper, eigene Implementierung) -->
			<div style="display: flex; align-items: flex-start; gap: 0; padding: 8px 0; margin-bottom: {wiz.isEditMode ? 4 : 40}px">
				{#each stepLabels as label, i}
					{@const n = i + 1}
					{@const state = wiz.isEditMode ? (n === wiz.currentStep ? 'current' : 'done') : (n < wiz.currentStep ? 'done' : n === wiz.currentStep ? 'current' : 'upcoming')}
					{@const clickable = wiz.isEditMode || n <= wiz.currentStep}
					<button
						data-testid="compare-wizard-step-{n}"
						onclick={() => clickable && wiz.goToStep(n)}
						disabled={!clickable}
						style="display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 0; background: none; border: none; cursor: {clickable ? 'pointer' : 'default'}; flex-shrink: 0; width: 80px"
					>
						<div style="width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; font-family: var(--g-font-sans); background: {state === 'upcoming' ? 'var(--g-rule)' : 'var(--g-accent)'}; color: {state === 'upcoming' ? 'var(--g-ink-3)' : 'white'}">
							{#if state === 'done'}✓{:else}{n}{/if}
						</div>
						<span style="font-size: 11px; font-weight: {state === 'current' ? 600 : 500}; color: {state === 'current' ? 'var(--g-ink)' : 'var(--g-ink-3)'}; font-family: var(--g-font-sans); text-align: center">{label}</span>
					</button>
					{#if i < stepLabels.length - 1}
						<div style="flex: 1; height: 1px; margin-top: 16px; min-width: 24px; background: {(wiz.isEditMode || i + 1 < wiz.currentStep) ? 'var(--g-ink-3)' : 'var(--g-rule)'}; opacity: {(wiz.isEditMode || i + 1 < wiz.currentStep) ? 0.5 : 1}">
						</div>
					{/if}
				{/each}
			</div>

			{#if wiz.isEditMode}
				<div style="margin-top: 24px; margin-bottom: 4px; font-size: 22px; font-weight: 600; letter-spacing: -0.02em; color: var(--g-ink)">
					{stepTitles[wiz.currentStep]}
				</div>
			{/if}
		</div>
	</TopoBg>

	<div class="min-h-[300px] mt-6">
		{#if wiz.currentStep === 1}
			<Step1Vergleich onManualProfileChange={handleManualProfileChange} />
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
