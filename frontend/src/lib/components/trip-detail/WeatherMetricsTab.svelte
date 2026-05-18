<script lang="ts">
	import { api } from '$lib/api.js';
	import type { Trip } from '$lib/types';

	interface MetricEntry {
		id: string;
		label: string;
		unit: string;
		category: string;
		default_enabled: boolean;
		has_friendly_format: boolean;
	}
	type MetricCatalog = Record<string, MetricEntry[]>;
	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}
	interface Props {
		trip: Trip;
	}

	let { trip }: Props = $props();

	const CATEGORY_LABELS: Record<string, string> = {
		temperature: 'Temperatur',
		wind: 'Wind',
		precipitation: 'Niederschlag',
		atmosphere: 'Atmosphäre',
		winter: 'Winter / Schnee'
	};
	const CATEGORY_ORDER = ['temperature', 'wind', 'precipitation', 'atmosphere', 'winter'];

	let catalog: MetricCatalog = $state({});
	let templates: Template[] = $state([]);
	let loading = $state(false);
	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError: string | null = $state(null);
	let enabledMap: Record<string, boolean> = $state({});
	let friendlyMap: Record<string, boolean> = $state({});
	let selectedTemplate = $state('');
	let lastAppliedTemplate = '';

	function sortedCategories(): string[] {
		const cats = Object.keys(catalog);
		return CATEGORY_ORDER.filter((c) => cats.includes(c)).concat(
			cats.filter((c) => !CATEGORY_ORDER.includes(c))
		);
	}

	function allMetricEntries(): MetricEntry[] {
		return sortedCategories().flatMap((cat) => catalog[cat] ?? []);
	}

	function initMaps(cat: MetricCatalog) {
		const eMap: Record<string, boolean> = {};
		const fMap: Record<string, boolean> = {};
		for (const metrics of Object.values(cat)) {
			for (const m of metrics) {
				eMap[m.id] = m.default_enabled;
				fMap[m.id] = true;
			}
		}
		const savedMetrics = trip.display_config?.metrics;
		if (savedMetrics) {
			for (const mc of savedMetrics) {
				eMap[mc.metric_id] = mc.enabled;
				fMap[mc.metric_id] = mc.use_friendly_format ?? true;
			}
		}
		const savedPreset = trip.display_config?.preset_name;
		selectedTemplate = (savedPreset && templates.some((t) => t.id === savedPreset))
			? savedPreset
			: '';
		enabledMap = eMap;
		friendlyMap = fMap;
	}

	async function load() {
		loading = true;
		try {
			const [catalogData, templateData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[])
			]);
			catalog = catalogData;
			templates = templateData;
			initMaps(catalogData);
		} catch (e: unknown) {
			saveError = (e as { error?: string })?.error ?? 'Fehler beim Laden';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (Object.keys(catalog).length === 0) load();
	});

	$effect(() => {
		const tmplKey = selectedTemplate;
		if (!Object.keys(catalog).length) return;
		if (!tmplKey || tmplKey === '__custom__' || tmplKey === lastAppliedTemplate) return;
		lastAppliedTemplate = tmplKey;
		const tpl = templates.find((t) => t.id === tmplKey);
		if (!tpl) return;
		const newMap: Record<string, boolean> = {};
		for (const metrics of Object.values(catalog)) {
			for (const m of metrics) {
				newMap[m.id] = tpl.metrics.includes(m.id);
			}
		}
		enabledMap = newMap;
	});

	function onCheckboxChange(id: string, checked: boolean) {
		enabledMap = { ...enabledMap, [id]: checked };
		if (selectedTemplate !== '__custom__') {
			selectedTemplate = '__custom__';
			lastAppliedTemplate = '__custom__';
		}
	}

	function setFormat(id: string, friendly: boolean) {
		friendlyMap = { ...friendlyMap, [id]: friendly };
	}

	async function handleSave() {
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			const metrics = allMetricEntries().map((m) => ({
				metric_id: m.id,
				enabled: enabledMap[m.id] ?? m.default_enabled,
				use_friendly_format: friendlyMap[m.id] ?? true
			}));
			const payload = {
				...(trip.display_config ?? {}),
				metrics,
				preset_name: selectedTemplate || undefined,
			};
			await api.put(`/api/trips/${trip.id}/weather-config`, payload);
			saveSuccess = true;
			setTimeout(() => {
				saveSuccess = false;
			}, 3000);
		} catch (e: unknown) {
			saveError = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}
</script>

<div data-testid="weather-metrics-tab" class="metrics-tab">
	{#if loading}
		<p class="loading-msg">Lade Metriken…</p>
	{:else}
		{#if templates.length > 0}
			<div class="template-row">
				<label for="metrics-tpl-sel" class="template-label">Template</label>
				<select
					id="metrics-tpl-sel"
					data-testid="weather-metrics-tab-template"
					bind:value={selectedTemplate}
					class="template-select"
				>
					<option value="">— Eigene Auswahl —</option>
					{#each templates as t}
						<option value={t.id}>{t.label}</option>
					{/each}
				</select>
			</div>
		{/if}

		<div class="categories">
			{#each sortedCategories() as cat}
				<section data-category={cat} class="category-section">
					<h3 class="category-heading">{CATEGORY_LABELS[cat] ?? cat}</h3>
					<ul class="metric-list">
						{#each (catalog[cat] ?? []) as metric}
							<li class="metric-row">
								<label class="metric-label">
									<input
										type="checkbox"
										data-testid="weather-metrics-tab-checkbox-{metric.id}"
										checked={enabledMap[metric.id] ?? metric.default_enabled}
										onchange={(e) =>
											onCheckboxChange(
												metric.id,
												(e.target as HTMLInputElement).checked
											)}
										class="metric-checkbox"
									/>
									<span class="metric-name">{metric.label}</span>
									{#if metric.unit}
										<span class="metric-unit">{metric.unit}</span>
									{/if}
								</label>
								{#if metric.has_friendly_format}
									<span class="format-toggle">
										<button
											data-testid="weather-metrics-tab-format-raw-{metric.id}"
											data-active={String(!(friendlyMap[metric.id] ?? true))}
											class="toggle-btn"
											class:active={!(friendlyMap[metric.id] ?? true)}
											onclick={() => setFormat(metric.id, false)}
											type="button">Roh</button
										>
										<button
											data-testid="weather-metrics-tab-format-indicator-{metric.id}"
											data-active={String(friendlyMap[metric.id] ?? true)}
											class="toggle-btn"
											class:active={friendlyMap[metric.id] ?? true}
											onclick={() => setFormat(metric.id, true)}
											type="button">Indikator</button
										>
									</span>
								{/if}
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		</div>

		<div class="save-row">
			{#if saveSuccess}
				<span data-testid="weather-metrics-tab-success" class="save-success"
					>Gespeichert ✓</span
				>
			{/if}
			{#if saveError}
				<span data-testid="weather-metrics-tab-error" class="save-error">{saveError}</span>
			{/if}
			<button
				data-testid="weather-metrics-tab-save"
				onclick={handleSave}
				disabled={saving}
				class="save-btn"
				type="button">{saving ? 'Speichern…' : 'Speichern'}</button
			>
		</div>
	{/if}
</div>

<style>
	.metrics-tab {
		padding: 1rem;
	}
	.template-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.25rem;
	}
	.template-label {
		font-size: 0.875rem;
		font-weight: 500;
	}
	.template-select {
		flex: 1;
		max-width: 280px;
		border: 1px solid var(--g-border, #ddd);
		border-radius: 4px;
		padding: 0.375rem 0.625rem;
		font-size: 0.875rem;
		background: var(--g-surface, #fff);
	}
	.categories {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}
	.category-heading {
		font-size: 0.8125rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--g-ink-faint, #888);
		margin-bottom: 0.5rem;
	}
	.metric-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.metric-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.25rem 0;
	}
	.metric-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		flex: 1;
		min-width: 0;
		font-size: 0.875rem;
	}
	.metric-checkbox {
		flex-shrink: 0;
	}
	.metric-name {
		flex: 1;
	}
	.metric-unit {
		font-size: 0.75rem;
		color: var(--g-ink-faint, #888);
		flex-shrink: 0;
	}
	.format-toggle {
		display: flex;
		border: 1px solid var(--g-border, #ddd);
		border-radius: 4px;
		overflow: hidden;
		flex-shrink: 0;
	}
	.toggle-btn {
		padding: 0.125rem 0.5rem;
		font-size: 0.75rem;
		background: var(--g-surface, #fff);
		border: none;
		cursor: pointer;
		color: var(--g-ink-faint, #888);
	}
	.toggle-btn.active {
		background: var(--g-accent, #c45a2a);
		color: #fff;
	}
	.save-row {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid var(--g-border, #ddd);
	}
	.save-success {
		font-size: 0.875rem;
		color: #16a34a;
	}
	.save-error {
		font-size: 0.875rem;
		color: #dc2626;
	}
	.save-btn {
		padding: 0.5rem 1.25rem;
		background: var(--g-accent, #c45a2a);
		color: #fff;
		border: none;
		border-radius: 4px;
		font-size: 0.875rem;
		font-weight: 500;
		cursor: pointer;
	}
	.save-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
</style>
