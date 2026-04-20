<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { api } from '$lib/api.js';

	interface MetricEntry {
		id: string;
		label: string;
		unit: string;
		category: string;
		default_enabled: boolean;
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
	// Bound to the <select> via bind:value — updated by both user interaction and Playwright
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
			enabled
		}));
		displayConfig = { metrics };
	});

	onMount(async () => {
		try {
			const [catalogData, templateData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
			]);
			catalog = catalogData;
			templates = templateData;

			if (displayConfig?.metrics) {
				const metrics = displayConfig.metrics as { metric_id: string; enabled: boolean }[];
				const newMap: Record<string, boolean> = {};
				for (const m of metrics) {
					newMap[m.metric_id] = m.enabled;
				}
				for (const catMetrics of Object.values(catalog)) {
					for (const m of catMetrics) {
						if (!(m.id in newMap)) newMap[m.id] = false;
					}
				}
				enabledMap = newMap;
				for (const t of templates) {
					if (matchesTemplate(t.id)) {
						lastAppliedTemplate = t.id;
						selectedTemplate = t.id;
						break;
					}
				}
			} else {
				const newMap: Record<string, boolean> = {};
				for (const catMetrics of Object.values(catalog)) {
					for (const m of catMetrics) {
						newMap[m.id] = false;
					}
				}
				enabledMap = newMap;
			}
			catalogLoaded = true;
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Katalog nicht ladbar';
		}
	});
</script>

<div data-testid="wizard-step3-weather" class="space-y-6">
	<div>
		<label for="weather-template" class="block text-sm font-medium mb-1">Wetter-Profil</label>
		<!-- bind:value ensures Playwright's selectOption updates Svelte state directly -->
		<select
			id="weather-template"
			data-testid="weather-template-select"
			class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
			bind:value={selectedTemplate}
		>
			<option value="">Kein Profil</option>
			{#each templates as t}
				<option value={t.id}>{t.label}</option>
			{/each}
			{#if showCustom}
				<option value="__custom__" disabled>Benutzerdefiniert</option>
			{/if}
		</select>
	</div>

	{#if loadError}
		<p class="text-sm text-destructive">{loadError}</p>
	{:else if !catalogLoaded}
		<p class="text-sm text-muted-foreground">Lade Metriken...</p>
	{:else}
		<div class="space-y-5">
			{#each sortedCategories() as cat}
				<div class="space-y-2">
					<h4 class="text-sm font-semibold">{CATEGORY_LABELS[cat] ?? cat}</h4>
					<div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
						{#each catalog[cat] as metric}
							<label class="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/50">
								<input
									type="checkbox"
									data-testid="metric-checkbox-{metric.id}"
									class="rounded border-input"
									checked={enabledMap[metric.id] ?? false}
									onchange={(e) => toggleMetric(metric.id, (e.target as HTMLInputElement).checked)}
								/>
								<span>{metric.label}</span>
							</label>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
