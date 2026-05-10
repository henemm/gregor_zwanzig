<script lang="ts">
	// Step 1: Aktivitaetsprofil + Eckdaten (Epic #136 Sub-Spec #161).
	// Quelle: docs/specs/modules/epic_136_step1_profile.md §1–§5
	//
	// Verantwortlich fuer:
	//   - 5 ProfileChips (Trekking, Skitour, Hochtour, Klettersteig, MTB) als
	//     <button>-Wrapper um <Pill> mit aria-pressed-Toggle-Semantik
	//   - 3 Eingabefelder: Name (Pflicht), Kuerzel (optional, max 20),
	//     Startdatum (Pflicht, type=date)
	//   - Bindung an WizardState (via getContext)
	//   - Hilfetext zum Enddatum (wird in Schritt 2 berechnet)
	//
	// Validierungs-/Disabled-Logik liegt zentral in WizardState.canAdvanceStep1
	// und wird vom Shell-Footer ausgelesen.

	import { getContext } from 'svelte';
	import { Pill } from '$lib/components/ui/pill';
	import type { ActivityType } from '$lib/types';
	import type { WizardState } from '../wizardState.svelte';

	const state = getContext<WizardState>('trip-wizard-state');

	// Reihenfolge gemaess Sub-Spec §3.
	const PROFILES: { activity: ActivityType; label: string }[] = [
		{ activity: 'trekking', label: 'Trekking' },
		{ activity: 'skitour', label: 'Skitour' },
		{ activity: 'hochtour', label: 'Hochtour' },
		{ activity: 'klettersteig', label: 'Klettersteig' },
		{ activity: 'mtb', label: 'MTB' }
	];

	// Factory-Handler (CLAUDE.md Safari-Pattern): benannter Handler mit
	// gebundener Activity statt anonymer Closure pro Render.
	function makeSelectHandler(activity: ActivityType) {
		return function handleSelectActivity() {
			state.activity = activity;
		};
	}
</script>

<div data-testid="trip-wizard-step1-profile" class="flex flex-col gap-6 py-4">
	<section class="flex flex-col gap-2">
		<span class="text-xs uppercase tracking-wide text-[var(--g-ink-faint)]">Aktivitaet</span>
		<div class="flex flex-wrap gap-2">
			{#each PROFILES as profile (profile.activity)}
				{@const selected = state.activity === profile.activity}
				<button
					type="button"
					data-testid={`trip-wizard-step1-chip-${profile.activity}`}
					aria-pressed={selected}
					onclick={makeSelectHandler(profile.activity)}
					class="focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)] rounded-full"
				>
					<Pill tone={selected ? 'accent' : 'default'}>{profile.label}</Pill>
				</button>
			{/each}
		</div>
	</section>

	<section class="flex flex-col gap-4">
		<span class="text-xs uppercase tracking-wide text-[var(--g-ink-faint)]">Eckdaten</span>

		<label class="flex flex-col gap-1 text-sm">
			<span>Name <span class="text-[var(--g-accent)]">*</span></span>
			<input
				type="text"
				data-testid="trip-wizard-step1-name"
				bind:value={state.name}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</label>

		<label class="flex flex-col gap-1 text-sm">
			<span>Kuerzel <span class="text-[var(--g-ink-faint)]">(optional)</span></span>
			<input
				type="text"
				data-testid="trip-wizard-step1-shortcode"
				maxlength="20"
				bind:value={state.shortcode}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</label>

		<label class="flex flex-col gap-1 text-sm">
			<span>Startdatum <span class="text-[var(--g-accent)]">*</span></span>
			<input
				type="date"
				data-testid="trip-wizard-step1-startdate"
				bind:value={state.startDate}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
			<span class="text-xs text-[var(--g-ink-faint)]"
				>Das Enddatum wird in Schritt 2 aus den Etappen berechnet.</span
			>
		</label>
	</section>
</div>
