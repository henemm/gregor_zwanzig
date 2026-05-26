<script lang="ts">
	// Step 1 (Issue #300: "Route"): Eckdaten des Trips.
	// Quelle: docs/specs/modules/issue_300_wizard_redesign.md
	//
	// Verantwortlich fuer:
	//   - 4 Eingabefelder: Name (Pflicht), Kuerzel (optional, max 20),
	//     Region (optional, max 50), Startdatum (Pflicht, type=date)
	//   - Bindung an WizardState (via getContext)
	//   - Hilfetext zum Enddatum (wird in Schritt 2 berechnet)
	//
	// AC-2 #300: Aktivitaetsprofil ist KEIN Pflichtfeld mehr — es wird in
	// Step 3 (Wetter) gewaehlt. Die Activity-Chips wurden hier entfernt.
	//
	// Validierungs-/Disabled-Logik liegt zentral in WizardState.canAdvanceStep1
	// und wird vom Shell-Footer ausgelesen.

	import { getContext } from 'svelte';
	import type { WizardState } from '../wizardState.svelte';

	const state = getContext<WizardState>('trip-wizard-state');
</script>

<div data-testid="trip-wizard-step1-profile" class="flex flex-col gap-6 py-4">
	<section class="flex flex-col gap-4">
		<span class="text-xs uppercase tracking-wide text-[var(--g-ink-muted)]">Eckdaten</span>

		<label class="flex flex-col gap-1 text-sm">
			<span>Name <span class="text-[var(--g-accent-deep)]">*</span></span>
			<input
				type="text"
				data-testid="trip-wizard-step1-name"
				bind:value={state.name}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</label>

		<label class="flex flex-col gap-1 text-sm">
			<span>Kuerzel <span class="text-[var(--g-ink-muted)]">(optional)</span></span>
			<input
				type="text"
				data-testid="trip-wizard-step1-shortcode"
				maxlength="20"
				bind:value={state.shortcode}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</label>

		<label class="flex flex-col gap-1 text-sm">
			<span>Region <span class="text-[var(--g-ink-muted)]">(optional)</span></span>
			<input
				type="text"
				data-testid="trip-wizard-step1-region"
				maxlength="50"
				placeholder="z.B. Korsika, Mallorca"
				bind:value={state.region}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
		</label>

		<label class="flex flex-col gap-1 text-sm">
			<span>Startdatum <span class="text-[var(--g-accent-deep)]">*</span></span>
			<input
				type="date"
				data-testid="trip-wizard-step1-startdate"
				bind:value={state.startDate}
				class="h-9 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
			/>
			<span class="text-xs text-[var(--g-ink-muted)]"
				>Das Enddatum wird in Schritt 2 aus den Etappen berechnet.</span
			>
		</label>
	</section>
</div>
