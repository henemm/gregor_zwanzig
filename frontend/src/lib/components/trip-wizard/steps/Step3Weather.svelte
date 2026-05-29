<script lang="ts">
	// Step 3: Wetter (Issue #432 — Wizard-Wetter-Umbau).
	// Quelle: docs/specs/modules/issue_432_step3_step5_polish.md §A
	//
	// Dedizierter Wetter-Konfigurations-Schritt:
	//   - Aktivitätsprofil-Dropdown (schreibt wizard.activity)
	//   - Metrik-Tabelle aus /api/metrics-Katalog (5 Kategorien-Gruppen)
	//   - Pro Metrik: Checkbox (enabled) + Format-Dropdown (raw/scale/simplified/symbol)
	//   - Sticky-Header pro Gruppe, Fade-Indikator unten
	//   - Zähler-Header „METRIKEN · N AKTIV VON M"
	//
	// State: getContext('trip-wizard-state'). Metrik-Änderungen mutieren
	// wizard.weatherMetrics. `formatModeMap` ist UI-only (4 Optionen) und wird
	// beim Save auf use_friendly_format: boolean reduziert (raw→false, sonst true).
	// Issue #435 bringt das echte 4-Optionen-Datenmodell.

	import { getContext, onMount } from 'svelte';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { Field } from '$lib/components/molecules';
	import { Select } from '$lib/components/ui/select';
	import { api } from '$lib/api';
	import {
		CATEGORY_ORDER,
		CATEGORY_LABELS,
		type MetricCatalog,
		type MetricEntry
	} from '$lib/components/trip-detail/metricsEditor';
	import type { ActivityType, WeatherConfigMetric } from '$lib/types';
	import type { WizardState } from '../wizardState.svelte';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- Aktivitätsprofil ---------------------------------------------------
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

	let selectedOption = $state<string>(
		wizard.activity ? (ACTIVITY_TO_OPTION[wizard.activity] ?? '') : ''
	);

	function handleActivityChange() {
		const mapped = OPTION_TO_ACTIVITY[selectedOption];
		wizard.activity = mapped ?? null;
	}

	// --- Metrik-Katalog laden ----------------------------------------------
	let catalog = $state<MetricCatalog>({});
	let loading = $state(true);

	// Format-Modus pro Metrik. Werte: raw / scale / simplified / symbol.
	// Issue #435: persistiert jetzt in WeatherConfigMetric.format_mode parallel
	// zu use_friendly_format (Backward-Compat). Dropdown-Optionen werden pro
	// Metrik aus m.format_modes (Katalog) iteriert.
	type FormatMode = 'raw' | 'scale' | 'simplified' | 'symbol';
	let formatModeMap = $state<Record<string, FormatMode>>({});

	// Issue #435: Label-Map für die Dropdown-Anzeige.
	const FORMAT_MODE_LABELS: Record<string, string> = {
		raw: 'Roh',
		scale: 'Skala',
		simplified: 'Vereinfacht',
		symbol: 'Symbol'
	};

	onMount(async () => {
		try {
			catalog = await api.get<MetricCatalog>('/api/metrics');
		} catch {
			catalog = {};
		} finally {
			loading = false;
		}
		initFromCatalog();
	});

	function initFromCatalog() {
		// Issue #435: Initial-Modus pro Metrik = default_format_mode aus Katalog
		// (Fallback raw, wenn Backend-Katalog noch alt ist).
		const modes: Record<string, FormatMode> = {};
		for (const cat of Object.values(catalog)) {
			for (const m of cat) {
				const def = (m.default_format_mode ?? (m.has_friendly_format ? 'scale' : 'raw')) as FormatMode;
				modes[m.id] = def;
			}
		}
		// Bereits persistierten format_mode (oder Legacy-Bool) zurückspiegeln.
		for (const m of wizard.weatherMetrics) {
			if (modes[m.metric_id] !== undefined) {
				if (m.format_mode) {
					modes[m.metric_id] = m.format_mode as FormatMode;
				} else if (m.use_friendly_format === false) {
					modes[m.metric_id] = 'raw';
				}
				// (use_friendly_format=true ohne format_mode → Katalog-Default)
			}
		}
		formatModeMap = modes;

		// wizard.weatherMetrics aus Katalog befüllen, wenn noch leer
		if (wizard.weatherMetrics.length === 0) {
			const all: WeatherConfigMetric[] = [];
			for (const catKey of CATEGORY_ORDER) {
				for (const m of catalog[catKey] ?? []) {
					const def = (m.default_format_mode ?? (m.has_friendly_format ? 'scale' : 'raw'));
					all.push({
						metric_id: m.id,
						enabled: true,
						use_friendly_format: def !== 'raw',
						format_mode: def
					});
				}
			}
			if (all.length > 0) wizard.weatherMetrics = all;
		}
	}

	// --- Reaktive Zähler ----------------------------------------------------
	const activeCount = $derived(wizard.weatherMetrics.filter((m) => m.enabled).length);
	const totalCount = $derived(wizard.weatherMetrics.length);

	function metricsForCategory(catKey: string): MetricEntry[] {
		return catalog[catKey] ?? [];
	}

	function findMetric(id: string): WeatherConfigMetric | undefined {
		return wizard.weatherMetrics.find((m) => m.metric_id === id);
	}

	// --- Factory-Handler (Safari/Factory: benannte Handler) -----------------

	function makeToggleEnabled(metricId: string) {
		return function handleToggleEnabled(e: Event) {
			const m = findMetric(metricId);
			if (m) m.enabled = (e.target as HTMLInputElement).checked;
		};
	}

	function makeFormatChange(metricId: string) {
		return function handleFormatChange(e: Event) {
			const mode = (e.target as HTMLSelectElement).value as FormatMode;
			formatModeMap[metricId] = mode;
			const m = findMetric(metricId);
			if (m) {
				// Issue #435: schreibe format_mode (neu) UND use_friendly_format (BC).
				m.format_mode = mode;
				m.use_friendly_format = mode !== 'raw';
			}
		};
	}
</script>

<div class="step3-weather flex flex-col gap-6 py-4" data-testid="step3-weather">
	<section class="flex flex-col gap-2">
		<Field label="AKTIVITÄTSPROFIL">
			<Select
				data-testid="activity-dropdown"
				bind:value={selectedOption}
				onchange={handleActivityChange}
				class="max-w-xs"
			>
				{#each ACTIVITY_OPTIONS as opt (opt.value)}
					<option value={opt.value}>{opt.label}</option>
				{/each}
			</Select>
		</Field>

		{#if wizard.activity === null}
			<p class="text-sm text-[var(--g-ink-muted)]" data-testid="activity-hint">
				Standard-Metriken werden verwendet.
			</p>
		{/if}
	</section>

	<section class="flex flex-col gap-2">
		<div class="flex items-center justify-between">
			<Eyebrow data-testid="metrics-header">
				METRIKEN · {activeCount} AKTIV VON {totalCount}
			</Eyebrow>
		</div>

		{#if loading}
			<p class="text-sm text-[var(--g-ink-muted)]" data-testid="metrics-loading">
				Metriken laden...
			</p>
		{:else}
			<div
				class="metrics-scroll relative max-h-[480px] overflow-y-auto"
				data-testid="step3-metrics-scroll"
			>
				{#each CATEGORY_ORDER as catKey (catKey)}
					{@const catMetrics = metricsForCategory(catKey)}
					{#if catMetrics.length > 0}
						<div class="metric-group" data-testid={`metric-group-${catKey}`}>
							<div class="sticky-header" data-testid={`metric-group-header-${catKey}`}>
								<Eyebrow>{CATEGORY_LABELS[catKey] ?? catKey}</Eyebrow>
							</div>

							{#each catMetrics as m (m.id)}
								{@const wm = findMetric(m.id)}
								<div
									data-testid={`metric-row-${m.id}`}
									class="flex flex-wrap items-center gap-3 rounded-md border border-[var(--g-ink-faint)]/20 px-3 py-2 mb-1"
								>
									<label class="flex items-center gap-2 text-sm min-w-[10rem]">
										<input
											type="checkbox"
											checked={wm?.enabled ?? false}
											onchange={makeToggleEnabled(m.id)}
										/>
										<span>{m.label}</span>
									</label>

									<Select
										data-testid={`metric-format-select-${m.id}`}
										value={formatModeMap[m.id] ?? (m.default_format_mode ?? 'raw')}
										onchange={makeFormatChange(m.id)}
									>
										{#each (m.format_modes ?? ['raw']) as mode (mode)}
											<option value={mode}>{FORMAT_MODE_LABELS[mode] ?? mode}</option>
										{/each}
									</Select>
								</div>
							{/each}
						</div>
					{/if}
				{/each}

				<div
					class="scroll-fade"
					data-testid="step3-scroll-fade"
					aria-hidden="true"
				></div>
			</div>
		{/if}
	</section>
</div>

<style>
	.metrics-scroll {
		/* Scrollbarer Container für die Metrik-Gruppen. */
		position: relative;
	}

	.sticky-header {
		position: sticky;
		top: 0;
		z-index: 2;
		background: var(--g-paper);
		padding: var(--g-s-2, 0.5rem) 0;
	}

	.scroll-fade {
		/* Fade-Indikator am unteren Rand zum Andeuten von weiterem Inhalt. */
		position: sticky;
		bottom: 0;
		height: 1.5rem;
		margin-top: -1.5rem;
		pointer-events: none;
		background: linear-gradient(to bottom, transparent, var(--g-paper));
	}
</style>
