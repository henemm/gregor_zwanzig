<script lang="ts">
	// Issue #364 (Schritt B von #361) — Bucket-Editor: Spalten / Detail-Werte /
	// Nicht im Briefing + Reihenfolge + Roh/Skala. Ersetzt den Kategorie-Checkbox-
	// Editor. bucket/order reisen additiv durch die Go-API in display_config und
	// werden vom Python-Loader (#360) gelesen — kein Backend-Umbau.
	// Spec: docs/specs/modules/issue_364_metrics_editor_buckets.md
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx
	import { api } from '$lib/api.js';
	import type { Trip, MetricPreset, Horizons } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import { Btn, Eyebrow, Pill } from '$lib/components/atoms';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import PresetRow from './PresetRow.svelte';
	import SavePresetDialog from './SavePresetDialog.svelte';
	import AboutOutputLayout from './AboutOutputLayout.svelte';
	import ChannelPreviewBlock from './ChannelPreviewBlock.svelte';
	import WeatherMetricsMobileView from './WeatherMetricsMobileView.svelte';
	// Issue #431: Bucket-Editor wandert in `shared/` (siehe Import unten) —
	// dieser Tab wird zum duennen Wrapper (channel="email" fix), Wizard nutzt
	// dieselbe Komponente mit 4 Kanal-Tabs.
	import { OutputLayoutEditor } from '$lib/components/organisms';
	// Issue #587: TablePreview einbinden (war ungenutzt nach #343).
	import TablePreview from './TablePreview.svelte';
	// Issue #433: leitet `onDndReorder` an die Shared-Komponente durch.
	import {
		autoAssign, bucketsToColumns, move, reorder, buildWeatherConfigMetrics,
		CATEGORY_LABELS, CATEGORY_ORDER, INDICATOR_MAP, indicatorCapable,
		type Buckets, type MetricEntry, type MetricCatalog,
	} from './metricsEditor.ts';

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}
	interface Props {
		trip: Trip;
	}
	let { trip }: Props = $props();

	let catalog: MetricCatalog = $state({});
	let templates: Template[] = $state([]);
	let userPresets: MetricPreset[] = $state([]);
	let loading = $state(false);
	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError: string | null = $state(null);

	// Bucket-State (ersetzt enabledMap). friendlyMap = Roh/Skala, horizonsMap bleibt.
	let buckets: Buckets = $state({ primary: [], secondary: [], off: [] });
	let friendlyMap: Record<string, boolean> = $state({});
	let horizonsMap: Record<string, Horizons> = $state({});
	let selectedTemplate = $state('');
	// Issue #614: Telegram Kurzform-Toggle (SMS-Tages-Max als Anhang).
	let telegramKurzform = $state<boolean>(trip.display_config?.telegram_kurzform ?? false);
	let savedSnapshot = $state('');
	let showSavePresetDialog = $state(false);
	let showAbout = $state(false);
	let pendingPreset: string | null = $state(null);
	let showMobileView = $state(false);

	// Abgeleitete Lookups für die Komponenten.
	const metricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		for (const ms of Object.values(catalog)) for (const m of ms) map[m.id] = m;
		return map;
	});
	// Kürzel (Design "Kürzel"): aus dem Label abgeleitet — kein Backend-Feld.
	const shortById = $derived.by(() => {
		const map: Record<string, string> = {};
		for (const id of Object.keys(metricById)) {
			const label = metricById[id].label;
			map[id] = label.length > 6 ? label.slice(0, 6) : label;
		}
		return map;
	});

	const isDirty = $derived(
		JSON.stringify({ buckets, friendlyMap, horizonsMap, telegramKurzform }) !== savedSnapshot,
	);

	function snapshot(b: Buckets, f: Record<string, boolean>, h: Record<string, Horizons>, tk: boolean): string {
		return JSON.stringify({ buckets: b, friendlyMap: f, horizonsMap: h, telegramKurzform: tk });
	}

	function allCatalogIds(): string[] {
		return CATEGORY_ORDER.filter((c) => c in catalog)
			.concat(Object.keys(catalog).filter((c) => !CATEGORY_ORDER.includes(c)))
			.flatMap((c) => (catalog[c] ?? []).map((m) => m.id));
	}

	function initFromTrip() {
		const fMap: Record<string, boolean> = {};
		const hMap: Record<string, Horizons> = {};
		for (const id of allCatalogIds()) {
			fMap[id] = true;
			hMap[id] = { ...HORIZONS_ALL };
		}

		const savedMetrics = trip.display_config?.metrics;
		let b: Buckets;
		const hasBuckets = savedMetrics?.some((m) => m.bucket || m.order !== undefined);

		if (savedMetrics && hasBuckets) {
			// bucket/order vorhanden → direkt übernehmen (order-sortiert).
			const prim = savedMetrics
				.filter((m) => m.enabled && m.bucket === 'primary')
				.sort((a, b2) => (a.order ?? 0) - (b2.order ?? 0));
			const sec = savedMetrics
				.filter((m) => m.enabled && m.bucket === 'secondary')
				.sort((a, b2) => (a.order ?? 0) - (b2.order ?? 0));
			// enabled ohne expliziten bucket → secondary (defensiv), wie #360-Loader.
			const looseActive = savedMetrics.filter(
				(m) => m.enabled && m.bucket !== 'primary' && m.bucket !== 'secondary',
			);
			const activeIds = new Set([...prim, ...sec, ...looseActive].map((m) => m.metric_id));
			b = {
				primary: prim.map((m) => m.metric_id),
				secondary: [...sec.map((m) => m.metric_id), ...looseActive.map((m) => m.metric_id)],
				off: allCatalogIds().filter((id) => !activeIds.has(id)),
			};
		} else if (savedMetrics && savedMetrics.length) {
			// Legacy ohne bucket/order → autoAssign auf aktive IDs.
			const activeIds = savedMetrics.filter((m) => m.enabled).map((m) => m.metric_id);
			b = autoAssign(activeIds, catalog);
		} else {
			// Kein gespeicherter Stand → Default-enabled aus Katalog.
			const activeIds = allCatalogIds().filter((id) => metricById[id]?.default_enabled);
			b = autoAssign(activeIds, catalog);
		}

		if (savedMetrics) {
			for (const m of savedMetrics) {
				fMap[m.metric_id] = m.use_friendly_format ?? true;
				hMap[m.metric_id] = m.horizons ? { ...m.horizons } : { ...HORIZONS_ALL };
			}
		}

		// Issue #587: WeatherMetricsTab arbeitet ohne Detail-Bucket (hideDetailBucket=true).
		// Bestehende secondary-Metriken werden verlustfrei nach primary migriert
		// (bucketsToColumns: primary zuerst, dann secondary, Duplikate entfernt).
		const mergedColumns = bucketsToColumns(b);
		b = { primary: mergedColumns, secondary: [], off: b.off };

		const savedPreset = trip.display_config?.preset_name;
		selectedTemplate = savedPreset ?? '';
		buckets = b;
		friendlyMap = fMap;
		horizonsMap = hMap;
		savedSnapshot = snapshot(b, fMap, hMap, telegramKurzform);
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
			initFromTrip();
		} catch (e: unknown) {
			console.error(e);
			saveError = (e as { error?: string })?.error ?? 'Fehler beim Laden';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (Object.keys(catalog).length === 0) load();
	});

	// --- Preset-Auswahl: autoAssign überschreibt Buckets (Confirm wenn dirty) ---
	function applyPreset(id: string) {
		const userP = userPresets.find((p) => p.id === id);
		const tmpl = templates.find((t) => t.id === id);
		const activeIds = userP
			? userP.metrics.filter((m) => m.enabled).map((m) => m.metric_id)
			: (tmpl ? tmpl.metrics : []);
		buckets = autoAssign(activeIds, catalog);
		// Issue #587: WeatherMetricsTab hat keinen Detail-Bucket — secondary nach primary migrieren.
		buckets = { primary: bucketsToColumns(buckets), secondary: [], off: buckets.off };
		if (userP) {
			for (const m of userP.metrics) {
				friendlyMap = { ...friendlyMap, [m.metric_id]: m.use_friendly_format };
			}
		}
		selectedTemplate = id;
	}

	function onSelectPreset(id: string) {
		if (isDirty) {
			pendingPreset = id;
			return;
		}
		applyPreset(id);
	}

	function confirmPreset() {
		if (pendingPreset) applyPreset(pendingPreset);
		pendingPreset = null;
	}

	function onMode(id: string, useIndicator: boolean) {
		friendlyMap = { ...friendlyMap, [id]: useIndicator };
	}

	// Issue #415 — Mobile-Toggle: aktiviert -> primary-Bucket, deaktiviert -> off.
	// Issue #587: Ziel war früher 'secondary', jetzt 'primary' (kein Detail-Bucket).
	function onToggleMetric(id: string, active: boolean) {
		const from: keyof Buckets = buckets.primary.includes(id)
			? 'primary'
			: buckets.secondary.includes(id) ? 'secondary' : 'off';
		const to: keyof Buckets = active ? 'primary' : 'off';
		if (from !== to) buckets = move(buckets, id, from, to);
		if (selectedTemplate) selectedTemplate = '';
	}

	function onMove(id: string, target: 'primary' | 'secondary' | 'off') {
		const from: keyof Buckets = buckets.primary.includes(id)
			? 'primary'
			: buckets.secondary.includes(id) ? 'secondary' : 'off';
		buckets = move(buckets, id, from, target);
		if (selectedTemplate) selectedTemplate = '';
	}

	function onReorder(bucket: keyof Buckets, id: string, dir: -1 | 1) {
		buckets = reorder(buckets, bucket, id, dir);
	}

	function onDndReorder(bucket: 'primary' | 'secondary', newOrder: string[]) {
		buckets = { ...buckets, [bucket]: newOrder };
	}

	function handleDiscard() {
		try {
			const snap = JSON.parse(savedSnapshot);
			buckets = snap.buckets;
			friendlyMap = snap.friendlyMap;
			horizonsMap = snap.horizonsMap ?? {};
			telegramKurzform = snap.telegramKurzform ?? false;
		} catch (e) {
			console.error(e);
			initFromTrip();
			telegramKurzform = trip.display_config?.telegram_kurzform ?? false;
		}
	}

	async function handleSave() {
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			const metrics = buildWeatherConfigMetrics(buckets, friendlyMap, horizonsMap, catalog);
			const payload = {
				...(trip.display_config ?? {}),
				metrics,
				preset_name: selectedTemplate || undefined,
				telegram_kurzform: telegramKurzform,
			};
			await api.put(`/api/trips/${trip.id}/weather-config`, payload);
			saveSuccess = true;
			savedSnapshot = snapshot(buckets, friendlyMap, horizonsMap, telegramKurzform);
			setTimeout(() => { saveSuccess = false; }, 3000);
		} catch (e: unknown) {
			saveError = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}

	function onPresetSaved(preset: MetricPreset) {
		userPresets = [preset, ...userPresets];
	}

	// Für SavePresetDialog (erwartet enabledMap): aktive = primary+secondary.
	const enabledMap = $derived.by(() => {
		const map: Record<string, boolean> = {};
		for (const id of allCatalogIds()) map[id] = false;
		for (const id of [...buckets.primary, ...buckets.secondary]) map[id] = true;
		return map;
	});
</script>

{#if loading && Object.keys(catalog).length === 0}
	<div class="metrics-tab loading-shell" aria-busy="true">
		<p class="loading-msg">Lade Metriken…</p>
	</div>
{:else}
	<div data-testid="weather-metrics-tab" class="metrics-tab">
		<button class="mobile-metrics-trigger" data-testid="mobile-metrics-trigger" onclick={() => (showMobileView = true)}>
			Metriken konfigurieren ({buckets.primary.length + buckets.secondary.length} aktiv)
		</button>
		<header class="tab-head">
			<div class="intro">
				<Eyebrow>Wetter-Metriken</Eyebrow>
				<h2 class="h1">Welche Werte gehen in das Briefing — und wie?</h2>
				<p class="lede">
					Jede Metrik landet als <strong>eigene Spalte</strong> in der Tabelle oder als
					<strong>Detail-Wert</strong> in einer kompakten Zeile darunter. Email zeigt beides
					vollständig; Telegram hat Spalten-Limits — was nicht passt, wandert
					automatisch in die Detail-Zeile.
					<button type="button" class="link-btn" data-testid="about-trigger" onclick={() => (showAbout = true)}>
						Wie funktioniert das genau?
					</button>
				</p>
			</div>
			<div class="actions">
				{#if isDirty}
					<Pill tone="warning" data-testid="weather-metrics-dirty-pill">Ungespeicherte Änderungen</Pill>
					<Btn variant="ghost" size="sm" data-testid="weather-metrics-discard" onclick={handleDiscard}>Verwerfen</Btn>
				{/if}
				{#if saveSuccess}
					<span data-testid="weather-metrics-tab-success" class="save-success">Gespeichert</span>
				{/if}
				{#if saveError}
					<span data-testid="weather-metrics-tab-error" class="save-error">{saveError}</span>
				{/if}
				<Btn variant="primary" size="sm" data-testid="weather-metrics-tab-save" disabled={saving || !isDirty} onclick={handleSave}>
					{saving ? 'Speichern…' : 'Speichern'}
				</Btn>
			</div>
		</header>

		<div class="layout">
			<!-- Preset-Spalte -->
			<aside class="preset-col">
				<Eyebrow>Preset-Auswahl</Eyebrow>
				<div class="preset-list" data-testid="weather-metrics-preset-list">
					{#each userPresets as p}
						<PresetRow id={p.id} label={p.name} metricCount={p.metrics.length} isActive={selectedTemplate === p.id} onSelect={onSelectPreset} />
					{/each}
					{#each templates as t}
						<PresetRow id={t.id} label={t.label} metricCount={t.metrics.length} isActive={selectedTemplate === t.id} onSelect={onSelectPreset} />
					{/each}
				</div>
				<div class="preset-save-box">
					<Eyebrow>Eigenes Preset</Eyebrow>
					<p class="preset-save-hint">
						Aktuelle Auswahl ({buckets.primary.length + buckets.secondary.length} Metriken)
						speichern und auf andere Trips anwenden.
					</p>
					<Btn variant="ghost" size="sm" class="full" data-testid="save-preset-dialog-trigger" onclick={() => (showSavePresetDialog = true)}>
						+ Als Preset speichern
					</Btn>
				</div>
			</aside>

			<!-- Editor — Issue #431: shared OutputLayoutEditor (channel="email" fix).
			     Preset-Liste (Templates + User-Presets) bleibt links in der
			     preset-col oben — wir geben hier KEINE preset-Daten an den
			     Editor weiter, damit es keine doppelte Preset-Anzeige gibt. -->
			<div class="editor-col">
				<OutputLayoutEditor
					channel="email"
					{catalog}
					bind:buckets
					bind:friendlyMap
					bind:selectedTemplate
					categoryLabels={CATEGORY_LABELS}
					hideDetailBucket={true}
					onReorder={(bucket, id, dir) => onReorder(bucket, id, dir)}
					onMove={(id, target) => onMove(id, target)}
					{onMode}
					{onDndReorder}
				/>
				<!-- Issue #587: TablePreview einbinden nach BucketSection "Detail-Werte",
				     vor ChannelPreviewBlock. Alle Props als State-Variablen vorhanden. -->
				<TablePreview
					{catalog}
					{enabledMap}
					{friendlyMap}
					{horizonsMap}
					categoryOrder={CATEGORY_ORDER}
					{indicatorCapable}
				/>
				<!-- Issue #614: Telegram-Optionen (kanal-spezifische Einstellungen). -->
				<div class="telegram-options" data-testid="telegram-options">
					<Eyebrow>Telegram-Optionen</Eyebrow>
					<div class="telegram-option-row">
						<Checkbox
							id="telegram-kurzform"
							data-testid="telegram-kurzform-toggle"
							checked={telegramKurzform}
							onchange={(e) => { telegramKurzform = (e.target as HTMLInputElement).checked; }}
						>Kurzform anhängen (Tages-Max)</Checkbox>
						<p class="option-hint">
							Hängt nach der Tabelle eine kompakte SMS-Kurzform mit allen Metriken an —
							auch jene, die über das Spalten-Limit hinausgehen.
						</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Issue #496 Layout-Fix: ChannelPreviewBlock außerhalb des `.layout`-Grids,
		     damit der Block volle Tab-Breite nutzt statt nur die schmale editor-col. -->
		<div class="preview-row">
			<ChannelPreviewBlock
				primary={buckets.primary}
				secondary={buckets.secondary}
				{metricById}
				{shortById}
			/>
		</div>

		<SavePresetDialog
			bind:open={showSavePresetDialog}
			{enabledMap}
			{friendlyMap}
			{horizonsMap}
			{catalog}
			{indicatorCapable}
			{buckets}
			onClose={() => (showSavePresetDialog = false)}
			onSaved={onPresetSaved}
		/>

		<AboutOutputLayout bind:open={showAbout} onClose={() => (showAbout = false)} />

		{#if pendingPreset}
			<div class="confirm-overlay" role="dialog" aria-modal="true" data-testid="preset-confirm">
				<div class="confirm-box">
					<Eyebrow>Preset anwenden</Eyebrow>
					<p>Du hast ungespeicherte Änderungen. Das Preset überschreibt die aktuelle Auswahl.</p>
					<div class="confirm-actions">
						<Btn variant="ghost" size="sm" data-testid="preset-confirm-cancel" onclick={() => (pendingPreset = null)}>Abbrechen</Btn>
						<Btn variant="primary" size="sm" data-testid="preset-confirm-ok" onclick={confirmPreset}>Überschreiben</Btn>
					</div>
				</div>
			</div>
		{/if}

		{#if showMobileView}
			<WeatherMetricsMobileView
				{trip}
				{catalog}
				{templates}
				{userPresets}
				{buckets}
				{friendlyMap}
				{metricById}
				{selectedTemplate}
				{savedSnapshot}
				{isDirty}
				{saving}
				{onToggleMetric}
				onSelectPreset={applyPreset}
				onSave={handleSave}
				onDiscard={handleDiscard}
				onClose={() => (showMobileView = false)}
				onOpenSavePresetDialog={() => (showSavePresetDialog = true)}
			/>
		{/if}
	</div>
{/if}

<style>
	.metrics-tab {
		padding: var(--g-s-4);
	}
	.tab-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: var(--g-s-6);
		margin-bottom: var(--g-s-6);
		flex-wrap: wrap;
	}
	.intro {
		max-width: 760px;
	}
	.h1 {
		font-size: var(--g-text-2xl);
		font-weight: 600;
		letter-spacing: var(--g-track-tight);
		margin: var(--g-s-1) 0 var(--g-s-2);
	}
	.lede {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.55;
	}
	.link-btn {
		margin-left: var(--g-s-1);
		color: var(--g-accent);
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		font-size: var(--g-text-sm);
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.actions {
		display: flex;
		gap: var(--g-s-2);
		align-items: center;
		flex-wrap: wrap;
	}
	.save-success {
		font-size: var(--g-text-sm);
		color: var(--g-success);
	}
	.save-error {
		font-size: var(--g-text-sm);
		color: var(--g-danger);
	}
	.layout {
		display: grid;
		grid-template-columns: 300px 1fr;
		gap: var(--g-s-8);
		align-items: start;
	}
	.preset-list {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
		margin-top: var(--g-s-2);
	}
	.preset-save-box {
		margin-top: var(--g-s-6);
		padding: var(--g-s-4);
		background: var(--g-surface-1);
		border-radius: var(--g-radius-sm);
		border: 1px dashed var(--g-ink-faint);
	}
	.preset-save-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin: var(--g-s-2) 0;
		line-height: 1.4;
	}
	:global(.preset-save-box .full) {
		width: 100%;
	}
	.editor-col {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-6);
	}
	.preview-row {
		margin-top: var(--g-s-6);
	}
	.confirm-overlay {
		position: fixed;
		inset: 0;
		background: color-mix(in srgb, var(--g-ink) 45%, transparent);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
	}
	.confirm-box {
		width: 420px;
		max-width: 90vw;
		background: var(--g-paper);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
		padding: var(--g-s-5);
		box-shadow: var(--g-elev-3);
	}
	.confirm-box p {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin: var(--g-s-2) 0 var(--g-s-4);
		line-height: 1.5;
	}
	.confirm-actions {
		display: flex;
		justify-content: flex-end;
		gap: var(--g-s-2);
	}
	.mobile-metrics-trigger {
		display: none;
	}
	@media (max-width: 899px) {
		.layout {
			grid-template-columns: 1fr;
			gap: var(--g-s-6);
		}
		.mobile-metrics-trigger {
			display: flex;
			align-items: center;
			justify-content: space-between;
			width: 100%;
			padding: var(--g-s-3) var(--g-s-4);
			background: var(--g-paper);
			border: 1px solid var(--g-ink-faint);
			border-radius: var(--g-radius-md);
			font-size: var(--g-text-sm);
			font-weight: 500;
			cursor: pointer;
			color: var(--g-ink);
			margin-bottom: var(--g-s-4);
		}
	}
	/* Issue #614: Telegram-Optionen-Block */
	.telegram-options {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	.telegram-option-row {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.option-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
		margin: 0;
		padding-left: calc(var(--g-s-4) + 2px); /* align under checkbox label */
	}
</style>
