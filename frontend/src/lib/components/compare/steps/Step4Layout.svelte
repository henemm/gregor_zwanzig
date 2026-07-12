<script lang="ts">
	// Compare-Wizard Step 4: Layout (Issue #442).
	// Spec: docs/specs/modules/issue_442_compare_wizard_step4_layout.md
	//
	// Direkte Adaption von trip-wizard/steps/Step4Layout.svelte mit drei
	// Abweichungen:
	//   - State-Klasse CompareWizardState statt WizardState
	//   - Context-Key 'compare-wizard-state' statt 'trip-wizard-state'
	//   - Kein wizard.weatherMetrics-Fallback — neue Subscriptions starten leer
	//     (autoAssign([], catalog)).
	//
	// Kein Gate: canAdvanceStep4 bleibt true im CompareWizardState — Weiter-Button
	// immer aktiv.

	import { getContext, onMount } from 'svelte';
	import { api } from '$lib/api';
	import { Eyebrow } from '$lib/components/atoms';
	import { OutputLayoutEditor } from '$lib/components/organisms';
	import LayoutPreview from '../LayoutPreview.svelte';
	import {
		autoAssign,
		buildWeatherConfigMetrics,
		move,
		reorder,
		type Buckets,
		type MetricCatalog,
		type MetricEntry,
	} from '$lib/components/trip-detail/metricsEditor';
	import type {
		ChannelLayouts,
		Horizons,
		MetricPreset,
		WeatherConfigMetric,
	} from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import type { CompareWizardState } from '../compareWizardState.svelte';
	import CompareInhaltSection from '../CompareInhaltSection.svelte';

	type ChannelId = 'email' | 'telegram' | 'sms';
	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}

	const wizard = getContext<CompareWizardState>('compare-wizard-state');

	// CE_CHANNELS: Kanaldefinitionen mit maxCols (Issue #681).
	const CE_CHANNELS: { id: ChannelId; label: string; maxCols: number | typeof Infinity; hint: string }[] = [
		{ id: 'email',    label: 'Email',    maxCols: Infinity, hint: 'alles · Empfehlung + Tabelle + Detail' },
		{ id: 'telegram', label: 'Telegram', maxCols: 8,        hint: 'max 8 Spalten' },
		{ id: 'sms',      label: 'SMS',      maxCols: 0,        hint: 'flach · ≤ 140 Zeichen' },
	];

	let catalog: MetricCatalog = $state({});
	let templates: Template[] = $state([]);
	let userPresets: MetricPreset[] = $state([]);
	let loading = $state(true);
	let loadError: string | null = $state(null);

	let activeChannel = $state<ChannelId>('email');

	// Pro-Kanal-State: jeder Kanal traegt seine eigenen Buckets + friendlyMap.
	let channelBuckets: Record<ChannelId, Buckets> = $state({
		email: { primary: [], secondary: [], off: [] },
		telegram: { primary: [], secondary: [], off: [] },
		sms: { primary: [], secondary: [], off: [] },
	});
	let channelFriendly: Record<ChannelId, Record<string, boolean>> = $state({
		email: {},
		telegram: {},
		sms: {},
	});
	let channelHorizons: Record<ChannelId, Record<string, Horizons>> = $state({
		email: {},
		telegram: {},
		sms: {},
	});
	let channelSelectedPreset: Record<ChannelId, string> = $state({
		email: '',
		telegram: '',
		sms: '',
	});

	// Lookup-Maps fuer ChannelPreviewBlock.
	const metricById = $derived.by(() => {
		const map: Record<string, MetricEntry> = {};
		for (const ms of Object.values(catalog)) for (const m of ms) map[m.id] = m;
		return map;
	});
	const shortById = $derived.by(() => {
		const map: Record<string, string> = {};
		for (const id of Object.keys(metricById)) {
			const label = metricById[id].label;
			map[id] = label.length > 6 ? label.slice(0, 6) : label;
		}
		return map;
	});

	function allCatalogIds(): string[] {
		return Object.values(catalog).flatMap((arr) => arr.map((m) => m.id));
	}

	// Buckets fuer einen Kanal aus wizard.channelLayouts oder leer ableiten.
	// Unterschied zum Trip-Wizard: kein weatherMetrics-Fallback im Compare-Kontext.
	function bucketsForChannel(ch: ChannelId): Buckets {
		const saved = wizard.channelLayouts?.[ch];
		if (saved && saved.length > 0) {
			const prim = saved
				.filter((m) => m.enabled && m.bucket === 'primary')
				.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
				.map((m) => m.metric_id);
			const sec = saved
				.filter((m) => m.enabled && m.bucket === 'secondary')
				.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
				.map((m) => m.metric_id);
			const active = new Set([...prim, ...sec]);
			const off = allCatalogIds().filter((id) => !active.has(id));
			return { primary: prim, secondary: sec, off };
		}
		// AC-2: Alle Katalog-Metriken als Standard aktiv — damit ↳ Detail-Pills für
		// Telegram sichtbar sind (>8 aktive Spalten nötig für pill-8).
		return autoAssign(allCatalogIds(), catalog);
	}

	function friendlyMapForChannel(ch: ChannelId): Record<string, boolean> {
		const fMap: Record<string, boolean> = {};
		for (const id of allCatalogIds()) fMap[id] = true;
		const saved = wizard.channelLayouts?.[ch];
		if (saved) {
			for (const m of saved) {
				fMap[m.metric_id] = m.use_friendly_format ?? true;
			}
		}
		// Kein weatherMetrics-Fallback im Compare-Kontext — Defaults bleiben true.
		return fMap;
	}

	function horizonsMapForChannel(ch: ChannelId): Record<string, Horizons> {
		const hMap: Record<string, Horizons> = {};
		for (const id of allCatalogIds()) hMap[id] = { ...HORIZONS_ALL };
		const saved = wizard.channelLayouts?.[ch];
		if (saved) {
			for (const m of saved) {
				if (m.horizons) hMap[m.metric_id] = { ...m.horizons };
			}
		}
		// Kein weatherMetrics-Fallback im Compare-Kontext — Defaults aus Katalog.
		return hMap;
	}

	function initChannelState(): void {
		const next: Record<ChannelId, Buckets> = { ...channelBuckets };
		const nextFriendly: Record<ChannelId, Record<string, boolean>> = { ...channelFriendly };
		const nextHorizons: Record<ChannelId, Record<string, Horizons>> = { ...channelHorizons };
		for (const c of CE_CHANNELS) {
			next[c.id] = bucketsForChannel(c.id);
			nextFriendly[c.id] = friendlyMapForChannel(c.id);
			nextHorizons[c.id] = horizonsMapForChannel(c.id);
		}
		channelBuckets = next;
		channelFriendly = nextFriendly;
		channelHorizons = nextHorizons;
	}

	onMount(async () => {
		try {
			const [catalogData, templateData, presetData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
				api.get<MetricPreset[]>('/api/metric-presets').catch(() => [] as MetricPreset[]),
			]);
			catalog = catalogData;
			templates = templateData;
			userPresets = presetData;
			initChannelState();
		} catch (e: unknown) {
			loadError = (e as { error?: string })?.error ?? 'Fehler beim Laden';
		} finally {
			loading = false;
		}
	});

	// Sync: channelBuckets/Friendly -> wizard.channelLayouts (kompletter Replace).
	// KRITISCHER Timing-Guard: wird erst aktiv sobald Katalog geladen ist —
	// sonst werden leere Buckets in den State geschrieben und neue Subscriptions
	// starten mit leerem Editor.
	$effect(() => {
		if (loading || Object.keys(catalog).length === 0) return;
		const layouts: ChannelLayouts = {};
		for (const c of CE_CHANNELS) {
			const metrics: WeatherConfigMetric[] = buildWeatherConfigMetrics(
				channelBuckets[c.id],
				channelFriendly[c.id],
				channelHorizons[c.id],
				catalog,
			);
			layouts[c.id] = metrics;
		}
		wizard.channelLayouts = layouts;
	});

	// --- Detail-Pill und Hinweis-Text (AC-2, Issue #681) --------------------

	// Aktive Spalten des gewählten Kanals — explizit per Kanal um Svelte-5-Cache zu umgehen
	const activeAllCols = $derived.by(() => {
		if (activeChannel === 'email') {
			return [...channelBuckets.email.primary, ...channelBuckets.email.secondary];
		} else if (activeChannel === 'telegram') {
			return [...channelBuckets.telegram.primary, ...channelBuckets.telegram.secondary];
		}
		return [...channelBuckets.sms.primary, ...channelBuckets.sms.secondary];
	});

	// Hinweis-Text unter der Spalten-Liste
	const activeChHint = $derived.by(() => {
		const ch = CE_CHANNELS.find(c => c.id === activeChannel);
		if (!ch) return '';
		if (ch.maxCols === Infinity) return 'Email zeigt alles · keine Begrenzung';
		if (ch.maxCols === 0) return 'SMS hat keine Tabelle — nur Empfehlung + Fließtext';
		return `Max ${ch.maxCols} Spalten für ${ch.label}`;
	});

	// --- Benannte Handler (Safari/Factory-Pattern) ---------------------------

	function handleSelectChannel(ch: ChannelId) {
		activeChannel = ch;
	}

	function handleMove(id: string, target: 'primary' | 'secondary' | 'off') {
		const b = channelBuckets[activeChannel];
		const from: keyof Buckets = b.primary.includes(id)
			? 'primary'
			: b.secondary.includes(id)
				? 'secondary'
				: 'off';
		channelBuckets = {
			...channelBuckets,
			[activeChannel]: move(b, id, from, target),
		};
		channelSelectedPreset = { ...channelSelectedPreset, [activeChannel]: '' };
	}

	function handleReorder(bucket: 'primary' | 'secondary', id: string, dir: -1 | 1) {
		channelBuckets = {
			...channelBuckets,
			[activeChannel]: reorder(channelBuckets[activeChannel], bucket, id, dir),
		};
	}

	function handleDndReorder(bucket: 'primary' | 'secondary', newOrder: string[]) {
		channelBuckets = {
			...channelBuckets,
			[activeChannel]: { ...channelBuckets[activeChannel], [bucket]: newOrder },
		};
	}

	function handleMode(id: string, useIndicator: boolean) {
		channelFriendly = {
			...channelFriendly,
			[activeChannel]: { ...channelFriendly[activeChannel], [id]: useIndicator },
		};
	}

	function handleSelectPreset(id: string) {
		const userP = userPresets.find((p) => p.id === id);
		const tmpl = templates.find((t) => t.id === id);
		const activeIds = userP
			? userP.metrics.filter((m) => m.enabled).map((m) => m.metric_id)
			: tmpl
				? tmpl.metrics
				: [];
		channelBuckets = {
			...channelBuckets,
			[activeChannel]: autoAssign(activeIds, catalog),
		};
		if (userP) {
			const fMap = { ...channelFriendly[activeChannel] };
			for (const m of userP.metrics) fMap[m.metric_id] = m.use_friendly_format;
			channelFriendly = { ...channelFriendly, [activeChannel]: fMap };
		}
		channelSelectedPreset = { ...channelSelectedPreset, [activeChannel]: id };
	}
</script>

<div class="step4-layout" data-testid="step4-layout">
	<header class="intro">
		<Eyebrow>Layout pro Kanal</Eyebrow>
		<p class="lede">
			Lege je Kanal fest, welche Werte als Spalten in der Tabelle erscheinen und
			welche als Detail-Zeile darunter. SMS hat ein Zeichen-Budget — dort
			priorisierst du eine flache Liste.
		</p>
	</header>

	{#if loading}
		<p class="loading" data-testid="step4-loading">Lade Metriken-Katalog…</p>
	{:else if loadError}
		<p class="error" data-testid="step4-error">{loadError}</p>
	{:else}
		<div
			class="channel-tabs"
			role="tablist"
			aria-label="Kanal-Auswahl"
			data-testid="channel-tabs"
		>
			{#each CE_CHANNELS as ch (ch.id)}
				<button
					type="button"
					role="tab"
					aria-selected={activeChannel === ch.id}
					aria-pressed={activeChannel === ch.id}
					data-channel={ch.id}
					data-testid={`channel-tab-${ch.id}`}
					class="channel-tab"
					class:active={activeChannel === ch.id}
					onclick={() => handleSelectChannel(ch.id)}
				>
					<div class="ch-tab-inner">
						<span class="ch-label">{ch.label}</span>
						<span
							class="ch-badge mono"
							style:color={activeChannel === ch.id ? 'var(--g-accent-deep)' : 'var(--g-ink-4)'}
							style:font-size="11px"
							style:font-weight="600"
						>{ch.maxCols === Infinity ? '∞' : ch.maxCols === 0 ? '—' : ch.maxCols}</span>
					</div>
					<span class="ch-hint mono">{ch.hint}</span>
				</button>
			{/each}
		</div>

		<div class="editor-row">
			<div class="editor-col" data-testid="layout-editor">
				<OutputLayoutEditor
					{catalog}
					bind:buckets={channelBuckets[activeChannel]}
					bind:friendlyMap={channelFriendly[activeChannel]}
					bind:selectedTemplate={channelSelectedPreset[activeChannel]}
					channel={activeChannel}
					{templates}
					{userPresets}
					onReorder={handleReorder}
					onMove={handleMove}
					onMode={handleMode}
					onSelectPreset={handleSelectPreset}
					onDndReorder={handleDndReorder}
				/>

				<!-- ↳ Detail-Pills für Telegram-Überlauf (AC-2) -->
				{#if (CE_CHANNELS.find(c => c.id === activeChannel)?.maxCols ?? Infinity) !== Infinity && (CE_CHANNELS.find(c => c.id === activeChannel)?.maxCols ?? 0) !== 0 && activeAllCols.length > (CE_CHANNELS.find(c => c.id === activeChannel)?.maxCols ?? Infinity)}
					{@const _maxCols = CE_CHANNELS.find(c => c.id === activeChannel)!.maxCols as number}
					<div class="detail-pills">
						{#each activeAllCols as _id, _i}
							{#if _i >= _maxCols}
								<span
									data-testid="compare-step4-detail-pill-{_i}"
									class="mono detail-pill"
									style:font-size="9.5px"
									style:color="var(--g-warn)"
									style:font-weight="600"
									style:letter-spacing="0.06em"
									style:text-transform="uppercase"
								>↳ Detail</span>
							{/if}
						{/each}
					</div>
				{/if}

				<!-- Hinweis-Text unter der Spalten-Liste -->
				<div class="mono ch-hint-text">{activeChHint}</div>
			</div>
			<aside class="preview-col" data-testid="layout-preview-col">
				<LayoutPreview channel={activeChannel} pickedIds={[...wizard.pickedIds]} />
			</aside>
		</div>
	{/if}

	<!-- Issue #1232 Scheibe 2b: Rest-Felder aus dem bisherigen Step5Versand
	     (Zeitfenster, Horizont, Top-N, Stundenverlauf) — Zwischenlösung bis
	     Scheibe 3 den echten LayoutTab-Organism baut. -->
	<CompareInhaltSection />
</div>

<style>
	.step4-layout {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-5);
	}
	.intro {
		max-width: 760px;
	}
	.lede {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-1);
		line-height: 1.55;
	}
	.loading,
	.error {
		padding: var(--g-s-4);
		text-align: center;
		font-size: var(--g-text-sm);
	}
	.error {
		color: var(--g-danger);
	}
	.channel-tabs {
		display: flex;
		gap: var(--g-s-2);
		overflow-x: auto;
		padding-bottom: var(--g-s-1);
	}
	.channel-tab {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		min-width: 160px;
		padding: var(--g-s-3) var(--g-s-4);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-md);
		background: var(--g-paper);
		cursor: pointer;
		text-align: left;
		font-family: inherit;
		min-height: 44px;
		transition:
			border-color 0.15s,
			background 0.15s;
	}
	.channel-tab:hover {
		border-color: var(--g-ink-muted);
	}
	.channel-tab.active {
		border-color: var(--g-accent);
		background: color-mix(in srgb, var(--g-accent) 8%, transparent);
	}
	.ch-tab-inner {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: 100%;
	}
	.ch-label {
		font-size: var(--g-text-base);
		font-weight: 600;
		color: var(--g-ink);
	}
	.ch-badge {
		flex-shrink: 0;
	}
	.ch-hint {
		font-size: 10.5px;
		color: var(--g-ink-3);
		margin-top: 2px;
	}
	.detail-pills {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 6px;
	}
	.detail-pill {
		background: rgba(192,138,26,0.08);
		border-radius: 3px;
		padding: 2px 6px;
	}
	.ch-hint-text {
		margin-top: 8px;
		font-size: 11px;
		color: var(--g-ink-4);
		letter-spacing: 0.04em;
	}
	.editor-row {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
		gap: var(--g-s-5);
		align-items: start;
	}
	.editor-col,
	.preview-col {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-4);
		min-width: 0;
	}
	@media (max-width: 899px) {
		.editor-row {
			grid-template-columns: 1fr;
		}
		.preview-col {
			order: -1;
		}
		.channel-tabs {
			margin-left: calc(var(--g-s-4) * -1);
			margin-right: calc(var(--g-s-4) * -1);
			padding-left: var(--g-s-4);
			padding-right: var(--g-s-4);
		}
	}
</style>
