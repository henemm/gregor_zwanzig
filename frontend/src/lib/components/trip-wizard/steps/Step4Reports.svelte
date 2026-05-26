<script lang="ts">
	// Step 4: Reports (Issue #300 — Wizard-Redesign).
	// Quelle: docs/specs/modules/issue_300_wizard_redesign.md §"Step 4 — Reports"
	//
	// Vier Report-Cards in einem 2×2-Grid:
	//   1. Abend-Briefing  (card-evening)  — Checkbox + Uhrzeit
	//   2. Morgen-Update   (card-morning)  — Checkbox + Uhrzeit
	//   3. Warnungen       (card-alerts)   — AUTARK-Badge
	//   4. Trend-Vorschau  (card-trend)    — disabled, Badge "Demnächst"
	//
	// State: getContext('trip-wizard-state'). Reports mutieren
	// wizard.briefings.reports.{morning|evening}.{enabled|time}. Save-Button
	// kommt aus TripWizardShell (state.save()).

	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { GCard } from '$lib/components/ui/g-card';
	import { Pill } from '$lib/components/ui/pill';
	import type { WizardState } from '../wizardState.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- Factory-Handler (Safari/Factory: benannte Handler) -----------------

	function makeEnabledHandler(report: 'morning' | 'evening') {
		return function handleToggleEnabled(e: Event) {
			wizard.briefings.reports[report].enabled = (e.target as HTMLInputElement).checked;
		};
	}
</script>

<div class="step4-reports py-4" data-testid="step4-reports">
	<div class="reports-grid grid gap-4 sm:grid-cols-2">
		<!-- Card 1: Abend-Briefing -->
		<GCard
			data-testid="card-evening"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Abend-Briefing</Eyebrow>
			<label class="flex items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={wizard.briefings.reports.evening.enabled}
					onchange={makeEnabledHandler('evening')}
				/>
				Aktiv
			</label>
			<label class="flex flex-col gap-1 text-sm">
				<span class="text-[var(--g-ink-muted)]">Uhrzeit</span>
				<input
					type="time"
					data-testid="evening-time"
					bind:value={wizard.briefings.reports.evening.time}
					class="h-9 w-28 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 font-mono outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
				/>
			</label>
		</GCard>

		<!-- Card 2: Morgen-Update -->
		<GCard
			data-testid="card-morning"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Morgen-Update</Eyebrow>
			<label class="flex items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={wizard.briefings.reports.morning.enabled}
					onchange={makeEnabledHandler('morning')}
				/>
				Aktiv
			</label>
			<label class="flex flex-col gap-1 text-sm">
				<span class="text-[var(--g-ink-muted)]">Uhrzeit</span>
				<input
					type="time"
					data-testid="morning-time"
					bind:value={wizard.briefings.reports.morning.time}
					class="h-9 w-28 rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 font-mono outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
				/>
			</label>
		</GCard>

		<!-- Card 3: Warnungen (autark) -->
		<GCard
			data-testid="card-alerts"
			class="rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3"
		>
			<Eyebrow>Warnungen</Eyebrow>
			<Pill tone="accent">AUTARK</Pill>
			<p class="text-sm text-[var(--g-ink-muted)]">
				Warnungen werden automatisch ausgelöst, sobald eine Alarmregel überschritten wird.
			</p>
		</GCard>

		<!-- Card 4: Trend-Vorschau (Platzhalter) -->
		<GCard
			data-testid="card-trend"
			class="disabled rounded-md border border-[var(--g-ink-faint)]/20 p-4 flex flex-col gap-3 opacity-60"
		>
			<Eyebrow>Trend-Vorschau</Eyebrow>
			<Pill tone="default">Demnächst</Pill>
		</GCard>
	</div>
</div>
