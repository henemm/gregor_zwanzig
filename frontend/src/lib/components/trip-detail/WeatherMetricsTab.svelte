<script lang="ts">
	import { api } from '$lib/api.js';
	import type { Trip, MetricPreset } from '$lib/types';
	import { Pill } from '$lib/components/ui/pill/index.js';
	import PresetRow from './PresetRow.svelte';
	import MetricGroup from './MetricGroup.svelte';
	import MetricCheckbox from './MetricCheckbox.svelte';
	import TablePreview from './TablePreview.svelte';
	import SavePresetDialog from './SavePresetDialog.svelte';

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

	// Epic #138 Issue #175 — Frontend-INDICATOR_MAP (12 Metriken).
	// 9 backend-eligible + 3 frontend-erweitert (wind, gust, rain_probability).
	const INDICATOR_MAP: Record<string, string> = {
		wind_direction: 'N / O / S / W',
		thunder: 'keins / mittel / hoch / extrem',
		cape: 'niedrig / mittel / hoch / extrem',
		cloud_total: 'klar / teilw. / bewölkt / bedeckt',
		cloud_low: 'klar / teilw. / bewölkt / bedeckt',
		cloud_mid: 'klar / teilw. / bewölkt / bedeckt',
		cloud_high: 'klar / teilw. / bewölkt / bedeckt',
		visibility: 'gut / eingeschränkt / schlecht / sehr schlecht',
		sunshine: 'hell / wechselhaft / bedeckt',
		wind: 'ruhig / mäßig / stark / sturm',
		gust: 'harmlos / mäßig / stark / orkan',
		rain_probability: 'niedrig / mittel / hoch / sehr hoch',
	};
	function indicatorCapable(id: string): boolean {
		return id in INDICATOR_MAP;
	}

	let catalog: MetricCatalog = $state({});
	let templates: Template[] = $state([]);
	let userPresets: MetricPreset[] = $state([]);
	let loading = $state(false);
	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError: string | null = $state(null);
	let enabledMap: Record<string, boolean> = $state({});
	let friendlyMap: Record<string, boolean> = $state({});
	let selectedTemplate = $state('');
	let lastAppliedTemplate = '';
	let savedSnapshot = $state('');
	let showSavePresetDialog = $state(false);

	const isDirty = $derived(
		JSON.stringify({ enabledMap, friendlyMap }) !== savedSnapshot
	);

	function snapshot(eMap: Record<string, boolean>, fMap: Record<string, boolean>): string {
		return JSON.stringify({ enabledMap: eMap, friendlyMap: fMap });
	}

	function sortedCategories(): string[] {
		const cats = Object.keys(catalog);
		return CATEGORY_ORDER.filter((c) => cats.includes(c)).concat(
			cats.filter((c) => !CATEGORY_ORDER.includes(c))
		);
	}

	function allMetricEntries(): MetricEntry[] {
		return sortedCategories().flatMap((cat) => catalog[cat] ?? []);
	}

	function countActiveInCategory(cat: string): number {
		return (catalog[cat] ?? []).filter((m) => enabledMap[m.id]).length;
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
		savedSnapshot = snapshot(eMap, fMap);
	}

	async function load() {
		loading = true;
		try {
			const [catalogData, templateData, presetData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
				api.get<MetricPreset[]>('/api/metric-presets').catch(() => [] as MetricPreset[]),
			]);
			catalog = catalogData;
			templates = templateData;
			userPresets = presetData;
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

	function onSelect(id: string) {
		selectedTemplate = id;
	}

	function onCheckboxChange(id: string, checked: boolean) {
		enabledMap = { ...enabledMap, [id]: checked };
		if (selectedTemplate !== '__custom__') {
			selectedTemplate = '__custom__';
			lastAppliedTemplate = '__custom__';
		}
	}

	function onModeChange(id: string, useIndicator: boolean) {
		friendlyMap = { ...friendlyMap, [id]: useIndicator };
	}

	function handleDiscard() {
		try {
			const snap = JSON.parse(savedSnapshot);
			enabledMap = snap.enabledMap;
			friendlyMap = snap.friendlyMap;
		} catch {
			// Snapshot ungültig — auf Defaults zurücksetzen
			initMaps(catalog);
		}
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
			savedSnapshot = snapshot(enabledMap, friendlyMap);
			setTimeout(() => {
				saveSuccess = false;
			}, 3000);
		} catch (e: unknown) {
			saveError = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}

	function onPresetSaved(preset: MetricPreset) {
		// Neues User-Preset oben in der Liste anzeigen
		userPresets = [preset, ...userPresets];
	}
</script>

{#if loading && Object.keys(catalog).length === 0}
	<div class="metrics-tab loading-shell" aria-busy="true">
		<p class="loading-msg">Lade Metriken…</p>
	</div>
{:else}
	<div data-testid="weather-metrics-tab" class="metrics-tab">
		{#if userPresets.length > 0 || templates.length > 0}
			<section class="presets-section" data-testid="weather-metrics-preset-list">
				{#each userPresets as p}
					<PresetRow
						id={p.id}
						label={p.name}
						metricCount={p.metrics.length}
						isActive={selectedTemplate === p.id}
						{onSelect}
					/>
				{/each}
				{#each templates as t}
					<PresetRow
						id={t.id}
						label={t.label}
						metricCount={t.metrics.length}
						isActive={selectedTemplate === t.id}
						{onSelect}
					/>
				{/each}
			</section>
		{/if}

		<div class="categories">
			{#each sortedCategories() as cat}
				<MetricGroup
					slug={cat}
					label={CATEGORY_LABELS[cat] ?? cat}
					activeCount={countActiveInCategory(cat)}
					totalCount={(catalog[cat] ?? []).length}
				>
					{#each (catalog[cat] ?? []) as metric}
						<MetricCheckbox
							{metric}
							enabled={enabledMap[metric.id] ?? metric.default_enabled}
							useIndicator={friendlyMap[metric.id] ?? true}
							indicatorCapable={indicatorCapable(metric.id)}
							onToggle={onCheckboxChange}
							{onModeChange}
						/>
					{/each}
				</MetricGroup>
			{/each}
		</div>

		<TablePreview
			{catalog}
			{enabledMap}
			{friendlyMap}
			categoryOrder={CATEGORY_ORDER}
			{indicatorCapable}
		/>

		<div class="save-row">
			{#if isDirty}
				<Pill tone="warning" data-testid="weather-metrics-dirty-pill">Ungespeicherte Änderungen</Pill>
				<button
					data-testid="weather-metrics-discard"
					onclick={handleDiscard}
					type="button"
					class="discard-btn"
				>Verwerfen</button>
			{/if}
			{#if saveSuccess}
				<span data-testid="weather-metrics-tab-success" class="save-success">Gespeichert ✓</span>
			{/if}
			{#if saveError}
				<span data-testid="weather-metrics-tab-error" class="save-error">{saveError}</span>
			{/if}
			{#if !isDirty}
				<button
					type="button"
					class="preset-trigger"
					data-testid="save-preset-dialog-trigger"
					onclick={() => (showSavePresetDialog = true)}
				>Als Preset speichern</button>
			{/if}
			<button
				data-testid="weather-metrics-tab-save"
				onclick={handleSave}
				disabled={saving || !isDirty}
				class="save-btn"
				type="button">{saving ? 'Speichern…' : 'Speichern'}</button
			>
		</div>

		<SavePresetDialog
			bind:open={showSavePresetDialog}
			{enabledMap}
			{friendlyMap}
			{catalog}
			{indicatorCapable}
			onClose={() => (showSavePresetDialog = false)}
			onSaved={onPresetSaved}
		/>
	</div>
{/if}

<style>
	.metrics-tab {
		padding: 1rem;
	}
	.presets-section {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 1.25rem;
	}
	.categories {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}
	.save-row {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid var(--g-ink-faint);
		flex-wrap: wrap;
	}
	.save-success {
		font-size: 0.875rem;
		color: #16a34a;
	}
	.save-error {
		font-size: 0.875rem;
		color: #dc2626;
	}
	.save-btn, .preset-trigger, .discard-btn {
		padding: 0.5rem 1.25rem;
		border: none;
		border-radius: 4px;
		font-size: 0.875rem;
		font-weight: 500;
		cursor: pointer;
	}
	.save-btn {
		background: var(--g-accent);
		color: #fff;
	}
	.save-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.preset-trigger {
		background: var(--g-surface, #fff);
		border: 1px solid var(--g-ink-faint);
		color: var(--g-ink);
	}
	.discard-btn {
		background: transparent;
		color: var(--g-ink-faint);
		text-decoration: underline;
	}
</style>
