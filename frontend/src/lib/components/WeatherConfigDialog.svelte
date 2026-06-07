<script lang="ts">
	import { api } from '$lib/api.js';
	import { Btn, Segmented } from '$lib/components/atoms';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Select } from '$lib/components/ui/select';
	import { buildScoreMap } from '$lib/utils/scoreToggleHelpers.js';
	import { CATEGORY_LABELS, CATEGORY_ORDER, indicatorCapable } from '$lib/components/trip-detail/metricsEditor';
	// Issue #435 — Single Source of Truth in $lib/types.ts (Adversary F002).
	import type { MetricEntry } from '$lib/types';

	type MetricCatalog = Record<string, MetricEntry[]>;

	interface Props {
		open: boolean;
		entityName: string;
		currentConfig: Record<string, unknown> | undefined;
		entityType?: 'location' | 'subscription' | 'trip';
		onsave: (config: Record<string, unknown>) => void;
		onclose: () => void;
	}

	let { open, entityName, currentConfig, entityType = 'trip', onsave, onclose }: Props = $props();

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
	// Map of metric_id -> use_friendly_format (Default: true)
	// Issue #629: Darstellung ist nur noch Boolean Roh/Einfach (kein 4-Wert-format_mode).
	let friendlyMap: Record<string, boolean> = $state({});
	// Map of metric_id -> score_member (Default: true) — Issue #362
	let scoreMap: Record<string, boolean> = $state({});
	const showScoreToggle = $derived(entityType === 'location' || entityType === 'subscription');

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

	function buildFriendlyMap(cat: MetricCatalog, cfg: Record<string, unknown> | undefined) {
		const map: Record<string, boolean> = {};
		for (const metrics of Object.values(cat)) {
			for (const m of metrics) {
				map[m.id] = true;
			}
		}
		if (cfg && Array.isArray(cfg.metrics)) {
			for (const entry of cfg.metrics as Array<{ metric_id: string; enabled: boolean; use_friendly_format?: boolean }>) {
				map[entry.metric_id] = entry.use_friendly_format ?? true;
			}
		}
		return map;
	}

	$effect(() => {
		if (open && Object.keys(catalog).length === 0) {
			loadCatalog();
		} else if (open && Object.keys(catalog).length > 0) {
			enabledMap = buildEnabledMap(catalog, currentConfig);
			friendlyMap = buildFriendlyMap(catalog, currentConfig);
			scoreMap = buildScoreMap(catalog, currentConfig);
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
			friendlyMap = buildFriendlyMap(catalog, currentConfig);
			scoreMap = buildScoreMap(catalog, currentConfig);
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
		// Issue #629: nur noch Boolean use_friendly_format (Roh/Einfach) persistieren,
		// kein explizites format_mode=scale|symbol mehr.
		const metricsArr = Object.entries(enabledMap).map(([metric_id, enabled]) => ({
			metric_id,
			enabled,
			use_friendly_format: friendlyMap[metric_id] ?? true,
			...(showScoreToggle ? { score_member: scoreMap[metric_id] ?? true } : {})
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
					<Select
						id="template-select"
						class="w-full"
						onchange={applyTemplate}
					>
						<option value="">-- Kein Template --</option>
						{#each templates as t}
							<option value={t.id}>{t.label}</option>
						{/each}
					</Select>
				</div>
			{/if}
			<div class="space-y-5 py-2">
				{#each sortedCategories() as cat}
					<div class="space-y-2">
						<p class="text-sm font-semibold">{CATEGORY_LABELS[cat] ?? cat}</p>
						<div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
							{#each catalog[cat] as metric}
								<div class="metric-row flex items-center gap-2 rounded px-1 py-0.5 text-sm">
									<div class="flex items-center gap-2 flex-1 min-w-0">
										<Checkbox
											checked={enabledMap[metric.id] ?? false}
											onchange={(e) => {
												enabledMap = {
													...enabledMap,
													[metric.id]: (e.target as HTMLInputElement).checked
												};
											}}
										>
											{metric.label}{#if metric.unit}<span class="ml-2 text-xs text-muted-foreground">{metric.unit}</span>{/if}
										</Checkbox>
									</div>
									{#if indicatorCapable(metric.id)}
										<!-- Issue #629: Boolean-Toggle Roh/Einfach (wie v2-Tab). -->
										<Segmented
											size="sm"
											value={(friendlyMap[metric.id] ?? true) ? 'indicator' : 'raw'}
											onChange={(v: string) => { friendlyMap = { ...friendlyMap, [metric.id]: v === 'indicator' }; }}
											items={[{ id: 'raw', label: 'Roh' }, { id: 'indicator', label: 'Einfach' }]}
										/>
									{/if}
									{#if showScoreToggle && enabledMap[metric.id]}
										<Segmented
											options={[{ value: 'score', label: 'Im Score' }, { value: 'noscore', label: 'Nicht im Score' }]}
											selected={(scoreMap[metric.id] ?? true) ? 'score' : 'noscore'}
											onselect={(v) => { scoreMap = { ...scoreMap, [metric.id]: v === 'score' }; }}
										/>
									{/if}
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}

		<Dialog.Footer>
			<Btn variant="outline" onclick={onclose}>Abbrechen</Btn>
			<Btn variant="primary" onclick={handleSave} disabled={loading || saving}>
				{saving ? 'Speichern…' : 'Speichern'}
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<style>
	.metric-row:hover {
		background: var(--g-surface-2);
	}
</style>
