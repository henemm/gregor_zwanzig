<script lang="ts">
	// Step 3: Wetter (Issue #432 — Wizard-Wetter-Umbau).
	// Quelle: docs/specs/modules/issue_432_step3_step5_polish.md §A
	//
	// Dedizierter Wetter-Konfigurations-Schritt:
	//   - Aktivitätsprofil-Dropdown (schreibt wizard.activity)
	//   - Metrik-Tabelle aus /api/metrics-Katalog (5 Kategorien-Gruppen)
	//   - Pro Metrik: Checkbox (enabled) + Boolean-Toggle Roh/Einfach (Issue #629)
	//   - Sticky-Header pro Gruppe, Fade-Indikator unten
	//   - Zähler-Header „METRIKEN · N AKTIV VON M"
	//
	// State: getContext('trip-wizard-state'). Metrik-Änderungen mutieren
	// wizard.weatherMetrics. Issue #629: Darstellung ist nur noch Boolean
	// Roh/Einfach (use_friendly_format), kein 4-Wert-format_mode mehr in der UI.
	// Toggle nur für indicatorCapable-Metriken; alle übrigen zeigen „nur Rohwert".

	import { getContext, onMount } from 'svelte';
	import { Eyebrow, Segmented } from '$lib/components/atoms';
	import Checkbox from '$lib/components/ui/checkbox/Checkbox.svelte';
	import { Select } from '$lib/components/ui/select';
	import { api } from '$lib/api';
	import {
		CATEGORY_ORDER,
		CATEGORY_LABELS,
		indicatorCapable,
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

	// Issue #629: Darstellung pro Metrik ist nur noch Boolean Roh/Einfach
	// (use_friendly_format). Kein 4-Wert-format_mode mehr in der UI.
	let friendlyMap = $state<Record<string, boolean>>({});

	onMount(async () => {
		try {
			catalog = await api.get<MetricCatalog>('/api/metrics');
		} catch (e) {
			console.error(e);
			catalog = {};
		} finally {
			loading = false;
		}
		initFromCatalog();
	});

	function initFromCatalog() {
		// Issue #629: Initial-Darstellung = Einfach (true), außer persistiert.
		const friendly: Record<string, boolean> = {};
		for (const cat of Object.values(catalog)) {
			for (const m of cat) {
				friendly[m.id] = true;
			}
		}
		for (const m of wizard.weatherMetrics) {
			if (friendly[m.metric_id] !== undefined) {
				friendly[m.metric_id] = m.use_friendly_format ?? true;
			}
		}
		friendlyMap = friendly;

		// wizard.weatherMetrics aus Katalog befüllen, wenn noch leer
		if (wizard.weatherMetrics.length === 0) {
			const all: WeatherConfigMetric[] = [];
			for (const catKey of CATEGORY_ORDER) {
				for (const m of catalog[catKey] ?? []) {
					all.push({
						metric_id: m.id,
						enabled: true,
						use_friendly_format: true
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
		return function handleFormatChange(useIndicator: boolean) {
			// Issue #629: nur noch Boolean use_friendly_format (Roh/Einfach).
			friendlyMap[metricId] = useIndicator;
			const m = findMetric(metricId);
			if (m) m.use_friendly_format = useIndicator;
		};
	}
</script>

<div class="step3-weather" data-testid="step3-weather" style="max-width: 920px; margin: 0 auto;">
	<!-- AC-5 #584: 2-Spalten-Grid für Aktivitätsprofil + Beschreibungstext (260px 1fr) -->
	<div style="display: grid; grid-template-columns: 260px 1fr; gap: 32px; align-items: start; margin-bottom: 24px;">
		<div>
			<Eyebrow style="margin-bottom: 8px;">Aktivitätsprofil</Eyebrow>
			<Select
				data-testid="activity-dropdown"
				bind:value={selectedOption}
				onchange={handleActivityChange}
			>
				{#each ACTIVITY_OPTIONS as opt (opt.value)}
					<option value={opt.value}>{opt.label}</option>
				{/each}
			</Select>
		</div>
		<div style="padding-top: 22px;">
			<!-- Beschreibungstext rechts: fontSize 13, ink-2, lineHeight 1.55 -->
			<div style="font-size: 13px; color: var(--g-ink-2); line-height: 1.55;" data-testid="activity-hint">
				{#if wizard.activity === null || wizard.activity === undefined}
					Standard-Metriken werden verwendet. Wähle ein Profil für eine kuratierte Auswahl — du kannst sie unten frei anpassen.
				{:else}
					Profil geladen. Anpassbar.
				{/if}
			</div>
		</div>
	</div>

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
				class="metrics-scroll relative"
				style="max-height: 540px; overflow-y: auto; border: 1px solid var(--g-rule); border-radius: var(--g-r-2); background: var(--g-paper);"
				data-testid="step3-metrics-scroll"
			>
				{#each CATEGORY_ORDER as catKey (catKey)}
					{@const catMetrics = metricsForCategory(catKey)}
					{#if catMetrics.length > 0}
						<div class="metric-group" data-testid={`metric-group-${catKey}`}>
							<!-- AC-6 #584: Gruppen-Header mit g-card-alt, sticky, g-rule-soft border -->
							<div
								class="mono"
								data-testid={`metric-group-header-${catKey}`}
								style="padding: 10px 16px 6px; font-size: 10px; font-weight: 600;
								       color: var(--g-ink-3); letter-spacing: 0.08em; text-transform: uppercase;
								       background: var(--g-card-alt); border-bottom: 1px solid var(--g-rule-soft);
								       position: sticky; top: 0; z-index: 1;"
							>
								{CATEGORY_LABELS[catKey] ?? catKey}
							</div>

							{#each catMetrics as m (m.id)}
								{@const wm = findMetric(m.id)}
								<!-- AC-6 #584: g-card wenn enabled, opacity 0.55 wenn disabled -->
								<div
									data-testid={`metric-row-${m.id}`}
									style="display: grid; grid-template-columns: 28px 1fr 220px;
									       gap: 16px; padding: 10px 16px; align-items: center;
									       background: {wm?.enabled ? 'var(--g-card)' : 'transparent'};
									       border-bottom: 1px solid var(--g-rule-soft);
									       opacity: {wm?.enabled ? 1 : 0.55};
									       transition: opacity 120ms, background 120ms;"
								>
									<Checkbox
										checked={wm?.enabled ?? false}
										onchange={makeToggleEnabled(m.id)}
									/>
									<span style="font-size: 14px; font-weight: 500;">{m.label}</span>

									{#if indicatorCapable(m.id)}
										<!-- Issue #629: Boolean-Toggle Roh/Einfach (wie v2-Tab). -->
										<Segmented
											size="sm"
											value={(friendlyMap[m.id] ?? true) ? 'indicator' : 'raw'}
											onChange={(v: string) => makeFormatChange(m.id)(v === 'indicator')}
											items={[{ id: 'raw', label: 'Roh' }, { id: 'indicator', label: 'Einfach' }]}
										/>
									{:else}
										<span
											data-testid={`metric-format-rawonly-${m.id}`}
											style="font-size: 12px; color: var(--g-ink-4);"
										>nur Rohwert</span>
									{/if}
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
		position: relative;
	}

	.scroll-fade {
		position: sticky;
		bottom: 0;
		height: 1.5rem;
		margin-top: -1.5rem;
		pointer-events: none;
		background: linear-gradient(to bottom, transparent, var(--g-paper));
	}
</style>
