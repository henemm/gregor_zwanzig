<script lang="ts">
	import { api } from '$lib/api.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';

	interface MetricEntry {
		id: string;
		label: string;
		unit: string;
		category: string;
		default_enabled: boolean;
	}

	type MetricCatalog = Record<string, MetricEntry[]>;

	interface Props {
		open: boolean;
		entityName: string;
		currentConfig: Record<string, unknown> | undefined;
		onsave: (config: Record<string, unknown>) => void;
		onclose: () => void;
	}

	let { open, entityName, currentConfig, onsave, onclose }: Props = $props();

	const CATEGORY_LABELS: Record<string, string> = {
		temperature: 'Temperatur',
		wind: 'Wind',
		precipitation: 'Niederschlag',
		atmosphere: 'Atmosphäre',
		winter: 'Winter/Schnee'
	};

	const CATEGORY_ORDER = ['temperature', 'wind', 'precipitation', 'atmosphere', 'winter'];

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}

	let catalog: MetricCatalog = $state({});
	let templates: Template[] = $state([]);
	let loading = $state(false);
	let saving = $state(false);
	let errorMsg: string | null = $state(null);

	// Map of metric_id -> enabled
	let enabledMap: Record<string, boolean> = $state({});

	function buildEnabledMap(cat: MetricCatalog, cfg: Record<string, unknown> | undefined) {
		const map: Record<string, boolean> = {};
		// Pre-fill defaults from catalog
		for (const metrics of Object.values(cat)) {
			for (const m of metrics) {
				map[m.id] = m.default_enabled;
			}
		}
		// Override from currentConfig if available
		if (cfg && Array.isArray(cfg.metrics)) {
			for (const entry of cfg.metrics as Array<{ metric_id: string; enabled: boolean }>) {
				map[entry.metric_id] = entry.enabled;
			}
		}
		return map;
	}

	$effect(() => {
		if (open && Object.keys(catalog).length === 0) {
			loadCatalog();
		} else if (open && Object.keys(catalog).length > 0) {
			enabledMap = buildEnabledMap(catalog, currentConfig);
		}
	});

	async function loadCatalog() {
		loading = true;
		errorMsg = null;
		try {
			const [catalogData, templateData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
			]);
			catalog = catalogData;
			templates = templateData;
			enabledMap = buildEnabledMap(catalog, currentConfig);
		} catch (e: unknown) {
			errorMsg = (e as { error?: string })?.error ?? 'Fehler beim Laden der Metriken';
		} finally {
			loading = false;
		}
	}

	function applyTemplate(event: Event) {
		const templateId = (event.target as HTMLSelectElement).value;
		if (!templateId) return;
		const tpl = templates.find(t => t.id === templateId);
		if (!tpl) return;
		const newMap: Record<string, boolean> = {};
		for (const metrics of Object.values(catalog)) {
			for (const m of metrics) {
				newMap[m.id] = tpl.metrics.includes(m.id);
			}
		}
		enabledMap = newMap;
	}

	function handleSave() {
		saving = true;
		const metricsArr = Object.entries(enabledMap).map(([metric_id, enabled]) => ({
			metric_id,
			enabled
		}));
		const config: Record<string, unknown> = { metrics: metricsArr };
		onsave(config);
		saving = false;
	}

	function sortedCategories(): string[] {
		const cats = Object.keys(catalog);
		return CATEGORY_ORDER.filter((c) => cats.includes(c)).concat(
			cats.filter((c) => !CATEGORY_ORDER.includes(c))
		);
	}
</script>

<Dialog.Root
	{open}
	onOpenChange={(o) => {
		if (!o) onclose();
	}}
>
	<Dialog.Content class="max-h-[85vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Wetter-Metriken — {entityName}</Dialog.Title>
			<Dialog.Description>Welche Metriken sollen im Report angezeigt werden?</Dialog.Description>
		</Dialog.Header>

		{#if loading}
			<p class="py-4 text-sm text-muted-foreground">Lade Metriken…</p>
		{:else if errorMsg}
			<p class="py-4 text-sm text-destructive">{errorMsg}</p>
		{:else}
			{#if templates.length > 0}
				<div class="py-2">
					<label for="template-select" class="block text-sm font-medium mb-1">Template laden</label>
					<select
						id="template-select"
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
						onchange={applyTemplate}
					>
						<option value="">-- Kein Template --</option>
						{#each templates as t}
							<option value={t.id}>{t.label}</option>
						{/each}
					</select>
				</div>
			{/if}
			<div class="space-y-5 py-2">
				{#each sortedCategories() as cat}
					<div class="space-y-2">
						<p class="text-sm font-semibold">{CATEGORY_LABELS[cat] ?? cat}</p>
						<div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
							{#each catalog[cat] as metric}
								<label
									class="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/50"
								>
									<input
										type="checkbox"
										class="rounded border-input"
										checked={enabledMap[metric.id] ?? false}
										onchange={(e) => {
											enabledMap = {
												...enabledMap,
												[metric.id]: (e.target as HTMLInputElement).checked
											};
										}}
									/>
									<span>{metric.label}</span>
									{#if metric.unit}
										<span class="ml-auto text-xs text-muted-foreground">{metric.unit}</span>
									{/if}
								</label>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}

		<Dialog.Footer>
			<Button variant="outline" onclick={onclose}>Abbrechen</Button>
			<Button onclick={handleSave} disabled={loading || saving}>
				{saving ? 'Speichern…' : 'Speichern'}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
