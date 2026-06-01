<script lang="ts">
	// Wizard-Shell fuer Epic #136 Sub-Spec #160.
	// Quelle: docs/specs/modules/epic_136_step0_shell.md §5
	//
	// Verantwortlich fuer:
	//   - Header (h1 + Eyebrow "Schritt N von 4")
	//   - Stepper-Render
	//   - Dynamischer Step-Slot via {#if state.currentStep === N}
	//   - Save-Status-Region (role="status", aria-live="polite")
	//   - Footer mit Btn-Atomen (Zurueck/Abbrechen/Weiter/Speichern)
	//
	// Konsumiert WizardState via getContext('trip-wizard-state').
	// Die Instanziierung erfolgt im +page.svelte Mount-Punkt (Factory-Pattern).

	import { getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { Btn, Eyebrow, TopoBg } from '$lib/components/atoms';
	import type { WizardState } from './wizardState.svelte';
	import Stepper from './Stepper.svelte';
	import Step1Profile from './steps/Step1Profile.svelte';
	import Step2Stages from './steps/Step2Stages.svelte';
	import Step3Weather from './steps/Step3Weather.svelte';
	import Step4Layout from './steps/Step4Layout.svelte';
	// Issue #432 (PR 4/Epic #428): Step4Reports.svelte wurde nach Step5Reports.svelte
	// umbenannt; bei currentStep === 5 gemountet.
	import Step5Reports from './steps/Step5Reports.svelte';

	const state = getContext<WizardState>('trip-wizard-state');

	// Issue #430: Wizard-spezifische Step-Texte fuer 5 Steps (Layout zwischen Wetter und Reports).
	const stepLabels = ['Route', 'Etappen', 'Wetter', 'Layout', 'Reports'];
	const stepSubLabels = [
		'Name & GPX hochladen',
		'Etappen prüfen',
		'Metriken konfigurieren',
		'Reihenfolge pro Kanal',
		'Briefings einrichten'
	];

	// Issue #391 / #430: sprechende H1-Titel + step-spezifische Footer-Hinweise.
	const stepTitles: Record<number, string> = {
		1: 'Route — wie kennt das System deinen Weg?',
		2: 'Etappen — stimmt die Tagesaufteilung?',
		3: 'Wetter — welche Daten gehen ins Briefing?',
		4: 'Layout — wie sieht das Briefing aus?',
		5: 'Reports — wann und wohin?'
	};

	const stepHints: Record<number, string | null> = {
		1: 'GPX-Upload empfohlen — manuelle Eingabe geht auch.',
		2: null,
		3: null,
		4: null,
		5: 'Unterwegs läuft alles autark. Kein Eingreifen nötig.'
	};

	const saveLabel = $derived(
		state.saveStatus === 'saving'
			? 'Speichern...'
			: state.saveStatus === 'ok'
				? 'Gespeichert'
				: 'Trip speichern'
	);

	// Factory-Handler (CLAUDE.md NiceGUI/Safari-Pattern auf Svelte-Klassen erweitert):
	// expliziter benannter Handler statt anonymer Closure.
	function handleBack() {
		state.prevStep();
	}

	function handleCancel() {
		void goto('/');
	}

	function handleNext() {
		state.nextStep();
	}

	function handleSave() {
		void state.save();
	}
</script>

<div data-testid="trip-wizard-shell" class="max-w-3xl mx-auto py-6 px-4">
	<TopoBg opacity={0.4}>
		<div class="p-6 rounded-lg mb-6">
			<header class="space-y-1 mb-4">
				<Eyebrow>SCHRITT {state.currentStep} VON 5 · NEUER TRIP</Eyebrow>
				<h1 class="text-2xl font-bold">{stepTitles[state.currentStep]}</h1>
			</header>

			<Stepper current={state.currentStep} labels={stepLabels} subLabels={stepSubLabels} />
		</div>
	</TopoBg>

	<div class="min-h-[300px] mt-6">
		{#if state.currentStep === 1}
			<Step1Profile />
		{:else if state.currentStep === 2}
			<Step2Stages />
		{:else if state.currentStep === 3}
			<Step3Weather />
		{:else if state.currentStep === 4}
			<Step4Layout />
		{:else if state.currentStep === 5}
			<Step5Reports />
		{/if}
	</div>

	{#if state.saveStatus !== 'idle'}
		<div
			data-testid="trip-wizard-save-status"
			role="status"
			aria-live="polite"
			class="mt-4 min-h-[1.5rem] text-sm"
		>
			{#if state.saveStatus === 'saving'}
				<span>Speichern...</span>
			{:else if state.saveStatus === 'error'}
				<span class="text-[var(--g-danger)]">{state.saveError}</span>
			{:else if state.saveStatus === 'ok'}
				<span class="text-[var(--g-success)]">Gespeichert</span>
			{/if}
		</div>
	{/if}

	<div
		class="flex items-center justify-between mt-8 pt-4 border-t border-[var(--g-ink-faint)]/30
		       sticky bottom-0 bg-[var(--g-paper)] mobile:py-3 mobile:px-4 mobile:mx-[-1rem]"
		style="padding-bottom: env(safe-area-inset-bottom, 0px);"
	>
		<div>
			{#if state.currentStep > 1}
				<Btn
					data-testid="trip-wizard-back"
					variant="outline"
					size="md"
					onclick={handleBack}
					class="mobile:min-h-[44px]"
				>
					Zurück
				</Btn>
			{/if}
		</div>
		<div class="flex items-center gap-2">
			<Btn
				data-testid="trip-wizard-cancel"
				variant="ghost"
				size="md"
				onclick={handleCancel}
				class="mobile:min-h-[44px]"
			>
				Abbrechen
			</Btn>
			{#if state.currentStep < 5}
				<Btn
					data-testid="trip-wizard-next"
					variant="accent"
					size="md"
					onclick={handleNext}
					disabled={!state.canAdvanceCurrent}
					class="mobile:min-h-[44px]"
				>
					Weiter
				</Btn>
			{:else}
				<Btn
					data-testid="trip-wizard-save"
					variant="accent"
					size="md"
					onclick={handleSave}
					disabled={state.saveStatus === 'saving'}
					class="mobile:min-h-[44px]"
				>
					{saveLabel}
				</Btn>
			{/if}
		</div>
	</div>

	{#if stepHints[state.currentStep]}
		<p
			data-testid="trip-wizard-step-hint"
			class="mt-3 text-center text-sm italic text-[var(--g-ink-muted)]"
		>
			{stepHints[state.currentStep]}
		</p>
	{/if}
</div>
