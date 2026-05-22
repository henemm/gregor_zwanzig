<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { api } from '$lib/api.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Select } from '$lib/components/ui/select';
	import Segmented from '$lib/components/ui/segmented';

	interface MetricEntry {
		id: string;
		label: string;
		unit: string;
		category: string;
		default_enabled: boolean;
		has_friendly_format: boolean;
	}

	type MetricCatalog = Record<string, MetricEntry[]>;

	interface Props {
		displayConfig: Record<string, unknown> | undefined;
		mode?: 'create' | 'edit';
	}
	let { displayConfig = $bindable(), mode = 'create' }: Props = $props();

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}

	let templates: Template[] = $state([]);

	const CATEGORY_LABELS: Record<string, string> = {
		temperature: 'Temperatur',
		wind: 'Wind',
		precipitation: 'Niederschlag',
		atmosphere: 'Atmosphäre',
		winter: 'Winter / Schnee'
	};
	const CATEGORY_ORDER = ['temperature', 'wind', 'precipitation', 'atmosphere', 'winter'];

	let catalog: MetricCatalog = $state({});
	let catalogLoaded = $state(false);
	let loadError: string | null = $state(null);
	let enabledMap: Record<string, boolean> = $state({});
	let friendlyMap: Record<string, boolean> = $state({});
	// Bound to the Select-component via bind:value — updated by both user interaction and Playwright
	let selectedTemplate: string = $state('');
	let showCustom = $state(false);
	// Tracks which template was last applied to avoid re-applying in the $effect
	let lastAppliedTemplate = '';

	function allMetricIds(): string[] {
		const ids: string[] = [];
		for (const metrics of Object.values(catalog)) {
			for (const m of metrics) {
				ids.push(m.id);
			}
		}
		return ids;
	}

	function matchesTemplate(key: string): boolean {
		const tmpl = templates.find(t => t.id === key);
		if (!tmpl) return false;
		const ids = allMetricIds();
		return ids.every(id => enabledMap[id] === tmpl.metrics.includes(id));
	}

	function sortedCategories(): string[] {
		const cats = Object.keys(catalog);
		return CATEGORY_ORDER.filter(c => cats.includes(c)).concat(
			cats.filter(c => !CATEGORY_ORDER.includes(c))
		);
	}

	// Reactive effect: when selectedTemplate changes (via bind:value from user or Playwright),
	// apply the template's metrics to the checkboxes
	$effect(() => {
		const tmplKey = selectedTemplate;
		if (!catalogLoaded) return;
		if (tmplKey === '__custom__' || tmplKey === lastAppliedTemplate) return;
		lastAppliedTemplate = tmplKey;
		showCustom = false;
		if (!tmplKey) return;
		const tmpl = templates.find(t => t.id === tmplKey);
		if (!tmpl) return;
		const newMap: Record<string, boolean> = {};
		for (const id of allMetricIds()) {
			newMap[id] = tmpl.metrics.includes(id);
		}
		enabledMap = newMap;
	});

	function toggleMetric(metricId: string, checked: boolean) {
		enabledMap = { ...enabledMap, [metricId]: checked };
		if (selectedTemplate && selectedTemplate !== '__custom__' && !matchesTemplate(selectedTemplate)) {
			showCustom = true;
			lastAppliedTemplate = '__custom__';
			tick().then(() => { selectedTemplate = '__custom__'; });
		} else {
			showCustom = false;
		}
	}

	$effect(() => {
		if (!catalogLoaded) return;
		const metrics = Object.entries(enabledMap).map(([metric_id, enabled]) => ({
			metric_id,
			enabled,
			use_friendly_format: friendlyMap[metric_id] ?? true
		}));
		displayConfig = { metrics };
	});

	function setFormat(id: string, friendly: boolean) {
		friendlyMap = { ...friendlyMap, [id]: friendly };
	}

	onMount(async () => {
		try {
			const [catalogData, templateData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
			]);
			catalog = catalogData;
			templates = templateData;

			if (displayConfig?.metrics) {
				const metrics = displayConfig.metrics as { metric_id: string; enabled: boolean; use_friendly_format?: boolean }[];
				const newMap: Record<string, boolean> = {};
				const newFriendly: Record<string, boolean> = {};
				for (const m of metrics) {
					newMap[m.metric_id] = m.enabled;
					newFriendly[m.metric_id] = m.use_friendly_format ?? true;
				}
				for (const catMetrics of Object.values(catalog)) {
					for (const m of catMetrics) {
						if (!(m.id in newMap)) newMap[m.id] = false;
						if (!(m.id in newFriendly)) newFriendly[m.id] = true;
					}
				}
				enabledMap = newMap;
				friendlyMap = newFriendly;
				for (const t of templates) {
					if (matchesTemplate(t.id)) {
						lastAppliedTemplate = t.id;
						selectedTemplate = t.id;
						break;
					}
				}
			} else {
				const newMap: Record<string, boolean> = {};
				const newFriendly: Record<string, boolean> = {};
				for (const catMetrics of Object.values(catalog)) {
					for (const m of catMetrics) {
						newMap[m.id] = false;
						newFriendly[m.id] = true;
					}
				}
				enabledMap = newMap;
				friendlyMap = newFriendly;
			}
			catalogLoaded = true;
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Katalog nicht ladbar';
		}
	});
</script>

<div data-testid="edit-weather-section" class="space-y-6">
	<div>
		<label for="weather-template" class="block text-sm font-medium mb-1">Wetter-Profil</label>
		<!-- bind:value ensures Playwright's selectOption updates Svelte state directly -->
		<Select
			id="weather-template"
			data-testid="weather-template-select"
			class="w-full"
			bind:value={selectedTemplate}
		>
			<option value="">Kein Profil</option>
			{#each templates as t}
				<option value={t.id}>{t.label}</option>
			{/each}
			{#if showCustom}
				<option value="__custom__" disabled>Benutzerdefiniert</option>
			{/if}
		</Select>
	</div>

	{#if loadError}
		<p class="text-sm text-destructive">{loadError}</p>
	{:else if !catalogLoaded}
		<p class="text-sm text-muted-foreground">Lade Metriken...</p>
	{:else}
		<div class="space-y-5">
			{#each sortedCategories() as cat}
				<div class="space-y-2">
					<h4 class="category-heading">{CATEGORY_LABELS[cat] ?? cat}</h4>
					<div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
						{#each catalog[cat] as metric}
							<div class="metric-row">
								<div class="flex-1 min-w-0">
									<Checkbox
										data-testid="metric-checkbox-{metric.id}"
										checked={enabledMap[metric.id] ?? false}
										onchange={(e) => toggleMetric(metric.id, (e.target as HTMLInputElement).checked)}
									>{metric.label}</Checkbox>
								</div>
								{#if metric.has_friendly_format}
									<Segmented
										options={[{ value: 'raw', label: 'Roh' }, { value: 'indicator', label: 'Indikator' }]}
										selected={(friendlyMap[metric.id] ?? true) ? 'indicator' : 'raw'}
										onselect={(v) => setFormat(metric.id, v === 'indicator')}
									/>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.category-heading {
		color: var(--g-ink);
		font-size: var(--g-text-xs);
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		border-bottom: 1px solid var(--g-ink-faint);
		padding-bottom: 4px;
		margin-bottom: 4px;
	}
	.metric-row {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		padding: 0 var(--g-s-1);
		min-height: 28px;
		border-radius: var(--g-radius-sm);
	}
	.metric-row:hover {
		background: var(--g-surface-2);
	}
</style>
