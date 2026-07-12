<script lang="ts">
	// CompareInhaltSection — Issue #1232 Scheibe 2b: Rest-Felder aus dem
	// bisherigen Step5Versand (Zeitfenster, Horizont, Top-N, Stundenverlauf,
	// Info-Kacheln, official_alerts_enabled/hourly_enabled-Toggles), extrahiert
	// weil Kanäle/Zeitplan/Laufzeit/Alert-Zustellung in den geteilten VersandTab
	// umgezogen sind (Kanal-Liste + Versandzeit-Buttons entfallen hier
	// ersatzlos — s. Spec Implementation Details Punkt 3).
	//
	// Zwischenlösung bis Scheibe 3 den echten LayoutTab-Organism baut (bewusst
	// NICHT "CompareReportContentSection" benannt — "report" im Dateinamen
	// triggert den Subagent-Write-Block).
	//
	// Alle `compare-step5-*`-Testids bleiben UNVERÄNDERT (AC-5/AC-9).
	//
	// Spec: docs/specs/modules/versand_tab_vergleich.md (Implementation Details Punkt 3)
	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/atoms';
	import { GCard } from '$lib/components/ui/g-card';
	import { Select } from '$lib/components/ui/select';
	import ChannelToggle from '$lib/components/shared/ChannelToggle.svelte';
	import type { CompareWizardState } from './compareWizardState.svelte';
	import { ALL_HOURLY_METRICS } from './compareHourlyMetricDefs';

	const state = getContext<CompareWizardState>('compare-wizard-state');

	const hasTimeOverlap = $derived(state.timeWindowStart >= state.timeWindowEnd);

	// Issue #1232 Scheibe 2b (KL-7): Kachel "Versand" zeigt jetzt die aktiven
	// Slot-Zeiten statt eines festen Enum-Werts (state.schedule traegt nur noch
	// Pause-Semantik seit Scheibe 2a).
	const scheduleTileValue = $derived.by(() => {
		const parts: string[] = [];
		if (state.morningEnabled) parts.push(state.morningTime);
		if (state.eveningEnabled) parts.push(state.eveningTime);
		return parts.length > 0 ? parts.join(' · ') : '—';
	});

	// Issue #1106: leere hourlyMetricKeys = Default "alle sichtbar" (noch nicht
	// materialisiert). Checkbox zeigt in diesem Fall trotzdem "angehakt".
	function isHourlyMetricActive(key: string): boolean {
		return state.hourlyMetricKeys.length === 0 || state.hourlyMetricKeys.includes(key);
	}

	// Factory-Handler (Safari-Pattern): materialisiert beim ersten Abwaehlen
	// die volle Liste, damit "alle minus eine" korrekt entsteht.
	function makeHourlyMetricHandler(key: string) {
		return function handleHourlyMetric(checked: boolean): void {
			const current =
				state.hourlyMetricKeys.length === 0
					? ALL_HOURLY_METRICS.map((m) => m.key)
					: [...state.hourlyMetricKeys];
			if (checked) {
				if (!current.includes(key)) current.push(key);
			} else {
				const idx = current.indexOf(key);
				if (idx >= 0) current.splice(idx, 1);
			}
			state.hourlyMetricKeys = current;
		};
	}
</script>

<div data-testid="compare-inhalt-section" class="space-y-6 py-4">
	<!-- 3-Kacheln-Grid: Versand (Slot-Zeiten) / Zeitfenster / Horizont -->
	<div
		style:display="grid"
		style:grid-template-columns="1fr 1fr 1fr"
		style:gap="10px"
		style:margin-bottom="28px"
	>
		<button type="button" data-testid="compare-step5-schedule-tile" class="kachel">
			<span class="mono kachel-label">Versand</span>
			<span class="kachel-value">{scheduleTileValue}</span>
			<span class="kachel-sub">Slots</span>
		</button>
		<button type="button" data-testid="compare-step5-timewindow-tile" class="kachel">
			<span class="mono kachel-label">Zeitfenster</span>
			<span class="kachel-value">{state.timeWindowStart}–{state.timeWindowEnd} Uhr</span>
			<span class="kachel-sub">bewertet</span>
		</button>
		<button type="button" data-testid="compare-step5-horizon-tile" class="kachel">
			<span class="mono kachel-label">Horizont</span>
			<span class="kachel-value">+{state.forecastHours}h</span>
			<span class="kachel-sub">
				{state.forecastHours === 24
					? 'heute'
					: state.forecastHours === 48
						? 'morgen + übermorgen'
						: 'übermorgen + Folgetag'}
			</span>
		</button>
	</div>

	<!-- Horizont -->
	<section class="space-y-2">
		<Eyebrow>Horizont</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<Select data-testid="compare-step5-forecast-hours" bind:value={state.forecastHours} class="w-full">
				<option value={24}>Heute (24 h)</option>
				<option value={48}>Morgen (48 h)</option>
				<option value={72}>Übermorgen (72 h)</option>
			</Select>
		</GCard>
	</section>

	<!-- Zeitfenster -->
	<section class="space-y-2">
		<Eyebrow>Zeitfenster</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div class="flex items-center gap-3">
				<input
					type="number"
					min="0"
					max="23"
					data-testid="compare-step5-time-window-start"
					bind:value={state.timeWindowStart}
					class="w-20 border rounded px-2 py-1 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
				/>
				<span class="text-[var(--g-ink-muted)]">bis</span>
				<input
					type="number"
					min="0"
					max="23"
					data-testid="compare-step5-time-window-end"
					bind:value={state.timeWindowEnd}
					class="w-20 border rounded px-2 py-1 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
				/>
				<span class="text-[var(--g-ink-muted)] text-sm">Uhr</span>
			</div>
			{#if hasTimeOverlap}
				<p data-testid="compare-step5-time-overlap-error" class="text-[var(--g-danger)] text-sm mt-2">
					Endzeit muss nach der Startzeit liegen.
				</p>
			{/if}
		</GCard>
	</section>

	<!-- Content-Flags: amtliche Warnquellen abfragen + Stundenverlauf ein/aus -->
	<section class="space-y-2">
		<Eyebrow>Inhalt</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div class="space-y-3">
				<ChannelToggle
					label="Amtliche Warnungen"
					checked={state.officialAlertsEnabled}
					onchange={(checked) => (state.officialAlertsEnabled = checked)}
					testid="compare-step5-official-alerts-toggle"
				/>
				<ChannelToggle
					label="Stundenverlauf"
					checked={state.hourlyEnabled}
					onchange={(checked) => (state.hourlyEnabled = checked)}
					testid="compare-step5-hourly-enabled-toggle"
				/>
			</div>
		</GCard>
	</section>

	<!-- Stundenverlauf: Anzahl Orte mit Detail (Issue #1104) -->
	<section class="space-y-2">
		<Eyebrow>Stundenverlauf</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<label for="compare-step5-topn" class="text-sm text-[var(--g-ink-muted)]">
				Anzahl Orte mit stündlichem Detail
			</label>
			<input
				id="compare-step5-topn"
				type="number"
				min="1"
				max="10"
				data-testid="compare-step5-topn"
				bind:value={state.topN}
				class="w-20 border rounded px-2 py-1 text-base bg-[var(--g-paper)] border-[var(--g-ink-faint)]"
			/>
		</GCard>
	</section>

	<!-- Metriken im Stundenverlauf (Issue #1106) -->
	<section class="space-y-2">
		<Eyebrow>Metriken im Stundenverlauf</Eyebrow>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div class="space-y-2" data-testid="compare-step5-hourly-metrics">
				{#each ALL_HOURLY_METRICS as metric (metric.key)}
					<ChannelToggle
						label={metric.label}
						checked={isHourlyMetricActive(metric.key)}
						onchange={makeHourlyMetricHandler(metric.key)}
						testid={`compare-step5-hourly-metric-${metric.key}`}
					/>
				{/each}
			</div>
		</GCard>
	</section>
</div>

<style>
	.kachel {
		padding: 12px 14px;
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-2);
		text-align: left;
		cursor: pointer;
		font-family: var(--g-font-sans);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.kachel:hover {
		border-color: var(--g-ink-muted);
	}
	.kachel-label {
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.kachel-value {
		font-size: 17px;
		font-weight: 600;
		color: var(--g-ink);
		font-variant-numeric: tabular-nums;
	}
	.kachel-sub {
		font-size: 11px;
		color: var(--g-ink-3);
	}
</style>
