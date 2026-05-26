<script lang="ts">
	// Step 3: Wetter (Issue #300 — Wizard-Redesign).
	// Quelle: docs/specs/modules/issue_300_wizard_redesign.md §"Step 3 — Wetter"
	//
	// Dedizierter Wetter-Konfigurations-Schritt (ersetzt den alten Wegpunkte-Step):
	//   - Aktivitätsprofil-Dropdown (schreibt wizard.activity)
	//   - Hinweistext "Standard-Metriken werden verwendet." wenn activity null
	//   - Metrik-Tabelle: pro Metrik Checkbox + Name + 3 HorizonChips
	//
	// State: getContext('trip-wizard-state'). Metrik-Änderungen werden in
	// wizard.weatherMetrics gehalten und beim Save als display_config.metrics
	// persistiert (siehe WizardState.toTripPayload).
	//
	// Kein Gate: canAdvanceStep3 bleibt true — Weiter-Button immer aktiv.

	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { HorizonChip } from '$lib/components/ui/horizon-chip';
	import type { ActivityType, Horizons, WeatherConfigMetric } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import type { WizardState } from '../wizardState.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// Dropdown-Optionen → ActivityType-Mapping. Leerer Wert = kein Profil (null).
	// Die UI-Werte folgen dem Spec-/E2E-Inventar (ski_touring, trekking, …); das
	// Mapping hält wizard.activity typsicher (ActivityType-Union).
	type ActivityOption = { value: string; label: string };
	const ACTIVITY_OPTIONS: ActivityOption[] = [
		{ value: '', label: 'Standard (kein Profil)' },
		{ value: 'trekking', label: 'Alpen-Trekking' },
		{ value: 'ski_touring', label: 'Skitouren' },
		{ value: 'hiking', label: 'Wandern' },
		{ value: 'mountaineering', label: 'Hochtour' }
	];

	const OPTION_TO_ACTIVITY: Record<string, ActivityType> = {
		trekking: 'trekking',
		ski_touring: 'skitour',
		hiking: 'trekking',
		mountaineering: 'hochtour'
	};

	const ACTIVITY_TO_OPTION: Record<ActivityType, string> = {
		trekking: 'trekking',
		skitour: 'ski_touring',
		hochtour: 'mountaineering',
		klettersteig: '',
		mtb: ''
	};

	// Lokaler Select-Wert, abgeleitet aus wizard.activity (typsicher gebunden).
	let selectedOption = $state<string>(
		wizard.activity ? (ACTIVITY_TO_OPTION[wizard.activity] ?? '') : ''
	);

	function handleActivityChange() {
		const mapped = OPTION_TO_ACTIVITY[selectedOption];
		wizard.activity = mapped ?? null;
	}

	// --- Metrik-Tabelle -----------------------------------------------------
	// Standard-Metriken (Hard-coded; kein API-Call für Basisimplementierung).
	const DEFAULT_METRICS: { id: string; label: string }[] = [
		{ id: 'temperature', label: 'Temperatur' },
		{ id: 'wind_speed', label: 'Wind' },
		{ id: 'precipitation', label: 'Niederschlag' },
		{ id: 'snow_line', label: 'Schneefallgrenze' },
		{ id: 'thunder_level', label: 'Gewitter' },
		{ id: 'sunshine_hours', label: 'Sonnenstunden' }
	];

	function cloneHorizons(h: Horizons): Horizons {
		return { today: h.today, tomorrow: h.tomorrow, day_after: h.day_after };
	}

	// wizard.weatherMetrics initialisieren, falls noch leer — pro Metrik ein
	// WeatherConfigMetric mit allen Horizonten aktiv.
	if (wizard.weatherMetrics.length === 0) {
		wizard.weatherMetrics = DEFAULT_METRICS.map((m) => ({
			metric_id: m.id,
			enabled: true,
			use_friendly_format: false,
			horizons: cloneHorizons(HORIZONS_ALL)
		}));
	}

	function labelFor(metricId: string): string {
		return DEFAULT_METRICS.find((m) => m.id === metricId)?.label ?? metricId;
	}

	function ensureHorizons(metric: WeatherConfigMetric): Horizons {
		if (!metric.horizons) {
			metric.horizons = cloneHorizons(HORIZONS_ALL);
		}
		return metric.horizons;
	}

	// --- Factory-Handler (Safari/Factory: benannte Handler) -----------------

	function makeToggleEnabled(metric: WeatherConfigMetric) {
		return function handleToggleEnabled(e: Event) {
			metric.enabled = (e.target as HTMLInputElement).checked;
		};
	}

	function makeToggleHorizon(metric: WeatherConfigMetric, day: keyof Horizons) {
		return function handleToggleHorizon() {
			const h = ensureHorizons(metric);
			h[day] = !h[day];
		};
	}
</script>

<div class="step3-weather flex flex-col gap-6 py-4" data-testid="step3-weather">
	<section class="flex flex-col gap-2">
		<Eyebrow>Aktivitätsprofil</Eyebrow>
		<select
			data-testid="activity-dropdown"
			bind:value={selectedOption}
			onchange={handleActivityChange}
			class="h-9 max-w-xs rounded-lg border border-[var(--g-ink-faint)]/40 bg-transparent px-2.5 outline-none focus-visible:ring-2 focus-visible:ring-[var(--g-accent)]"
		>
			{#each ACTIVITY_OPTIONS as opt (opt.value)}
				<option value={opt.value}>{opt.label}</option>
			{/each}
		</select>

		{#if wizard.activity === null}
			<p class="text-sm text-[var(--g-ink-muted)]" data-testid="activity-hint">
				Standard-Metriken werden verwendet.
			</p>
		{/if}
	</section>

	<section class="flex flex-col gap-3">
		<Eyebrow>Metriken</Eyebrow>
		<div class="flex flex-col gap-1">
			{#each wizard.weatherMetrics as metric (metric.metric_id)}
				{@const horizons = ensureHorizons(metric)}
				<div
					data-testid={`metric-row-${metric.metric_id}`}
					class="flex flex-wrap items-center gap-3 rounded-md border border-[var(--g-ink-faint)]/20 px-3 py-2"
				>
					<label class="flex items-center gap-2 text-sm min-w-[10rem]">
						<input
							type="checkbox"
							checked={metric.enabled}
							onchange={makeToggleEnabled(metric)}
						/>
						<span>{labelFor(metric.metric_id)}</span>
					</label>
					<div class="flex flex-wrap items-center gap-1">
						<HorizonChip
							day="today"
							active={horizons.today}
							onclick={makeToggleHorizon(metric, 'today')}
						/>
						<HorizonChip
							day="tomorrow"
							active={horizons.tomorrow}
							onclick={makeToggleHorizon(metric, 'tomorrow')}
						/>
						<HorizonChip
							day="day_after"
							active={horizons.day_after}
							onclick={makeToggleHorizon(metric, 'day_after')}
						/>
					</div>
				</div>
			{/each}
		</div>
	</section>
</div>
