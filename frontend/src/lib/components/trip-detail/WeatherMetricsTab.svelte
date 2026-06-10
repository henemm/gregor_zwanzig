<script lang="ts">
	// Issue #587 v2 — Wetter-Metriken-Tab: 4-Abschnitte-Editor + Live-Mail-Vorschau (Desktop).
	// Issue #618 — Mobile: 4 Abschnitte vertikal + Mail-Bottom-Sheet (Legacy #415 entfernt).
	// LÖST AB: OutputLayoutEditor-basiertes Layout (Issue #364/#431).
	// BEWAHRT: initFromTrip, handleSave, bucketsToColumns-Migration, telegramKurzform,
	//          read-modify-write-Payload, SavePresetDialog.
	// SCHÜTZT: OutputLayoutEditor, BucketSection*, ActiveMetricRow bleiben UNVERÄNDERT
	//          (Wizard + Orts-Vergleich nutzen sie).
	// Spec: docs/specs/modules/issue_587_weather_tab_v2.md
	// Spec: docs/specs/modules/issue_618_mobile_weather_tab.md
	import { api } from '$lib/api.js';
	import type { Trip, MetricPreset, Horizons } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import { Btn, Card, Eyebrow, Pill } from '$lib/components/atoms';
	import SavePresetDialog from './SavePresetDialog.svelte';
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	// v2 Sub-Komponenten (neu, standalone, keine Abhängigkeit von OutputLayoutEditor)
	import WeatherV2PresetBar from './WeatherV2PresetBar.svelte';
	import WeatherV2Grundauswahl from './WeatherV2Grundauswahl.svelte';
	import WeatherV2Reihenfolge from './WeatherV2Reihenfolge.svelte';
	import WeatherV2Kanaele from './WeatherV2Kanaele.svelte';
	import WeatherV2MailPreview from './WeatherV2MailPreview.svelte';
	import {
		autoAssign, bucketsToColumns, move, reorder, buildWeatherConfigMetrics,
		diffHighlight,
		CATEGORY_LABELS, CATEGORY_ORDER, indicatorCapable,
		type Buckets, type MetricEntry, type MetricCatalog, type Highlight, type WeatherSnapshot,
	} from './metricsEditor.ts';

	interface Template {
		id: string;
		label: string;
		metrics: string[];
	}
	interface ChannelConfig {
		email: boolean;
		telegram: boolean;
		sms: boolean;
	}
	interface Props {
		trip: Trip;
		/** Issue #622: Create-Modus — kein PUT; Kanäle per onChannelsChange nach oben emittieren */
		createMode?: boolean;
		onChannelsChange?: (c: ChannelConfig) => void;
		/** Issue #694: Trip-State in +page.svelte nach erfolgreichem PUT aktualisieren */
		onTripUpdate?: (t: Trip) => void;
	}
	let { trip, createMode = false, onChannelsChange, onTripUpdate }: Props = $props();

	let catalog: MetricCatalog = $state({});
	let templates: Template[] = $state([]);
	let userPresets: MetricPreset[] = $state([]);
	let loading = $state(false);
	let saving = $state(false);
	let saveSuccess = $state(false);
	let saveError: string | null = $state(null);

	// Bucket-State (secondary IMMER leer nach #587 — kein Detail-Bucket).
	let buckets: Buckets = $state({ primary: [], secondary: [], off: [] });
	let friendlyMap: Record<string, boolean> = $state({});
	let horizonsMap: Record<string, Horizons> = $state({});
	let selectedTemplate = $state('');
	// Issue #587: Kanal-Konfiguration (kein Signal). display_config ist additiv
	// — channels wird als unbekanntes Feld durchgereicht, daher Cast über unknown.
	let channels: ChannelConfig = $state(
		((trip.display_config as unknown as Record<string, unknown>)?.channels as ChannelConfig | undefined)
			?? { email: true, telegram: true, sms: false }
	);
	// Issue #614: Telegram Kurzform-Toggle (SMS-Tages-Max als Anhang).
	let telegramKurzform = $state<boolean>(trip.display_config?.telegram_kurzform ?? false);
	// Issue #624: konfigurierbare Schwellwerte pro Metrik (nur threshold-fähige).
	const SMS_THRESHOLD_METRIC_IDS = ['precipitation', 'rain_probability', 'wind', 'gust'];
	let smsThresholds = $state<Record<string, string>>({});
	let savedSnapshot = $state('');
	let showSavePresetDialog = $state(false);
	let mailSheetOpen = $state(false);
	let pendingPreset: string | null = $state(null);

	// AC-2 Diff-Highlight: 2,5s Aufleuchten nach jeder Änderung.
	let highlight: Highlight | null = $state(null);
	let highlightTimer: ReturnType<typeof setTimeout> | null = null;

	function flash(h: Highlight | null) {
		if (highlightTimer) clearTimeout(highlightTimer);
		highlight = h;
		if (h) {
			highlightTimer = setTimeout(() => { highlight = null; highlightTimer = null; }, 2500);
		}
	}

	function prevSnapshot(): WeatherSnapshot {
		return {
			columns: [...buckets.primary],
			mode: Object.fromEntries(
				buckets.primary.map(id => [id, friendlyMap[id] === true ? 'indicator' : 'raw'])
			) as Record<string, 'raw' | 'indicator'>,
			presetId: selectedTemplate,
		};
	}

	function applyDiff(nextCols: string[], nextMode: Record<string, boolean>, nextPresetId: string) {
		const prev = prevSnapshot();
		const next: WeatherSnapshot = {
			columns: nextCols,
			mode: Object.fromEntries(nextCols.map(id => [id, nextMode[id] === true ? 'indicator' : 'raw'])) as Record<string, 'raw' | 'indicator'>,
			presetId: nextPresetId,
		};
		flash(diffHighlight(prev, next));
	}

	// Abgeleitete Lookups.
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

	// Conflict 1 resolved: BEIDE Felder in isDirty + snapshot.
	const isDirty = $derived(
		JSON.stringify({ buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, channels }) !== savedSnapshot,
	);

	function snapshot(
		b: Buckets, f: Record<string, boolean>, h: Record<string, Horizons>,
		tk: boolean, st: Record<string, string>, ch: ChannelConfig
	): string {
		return JSON.stringify({ buckets: b, friendlyMap: f, horizonsMap: h, telegramKurzform: tk, smsThresholds: st, channels: ch });
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
			const prim = savedMetrics
				.filter((m) => m.enabled && m.bucket === 'primary')
				.sort((a, b2) => (a.order ?? 0) - (b2.order ?? 0));
			const sec = savedMetrics
				.filter((m) => m.enabled && m.bucket === 'secondary')
				.sort((a, b2) => (a.order ?? 0) - (b2.order ?? 0));
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
			const activeIds = savedMetrics.filter((m) => m.enabled).map((m) => m.metric_id);
			b = autoAssign(activeIds, catalog);
		} else {
			const activeIds = allCatalogIds().filter((id) => metricById[id]?.default_enabled);
			b = autoAssign(activeIds, catalog);
		}

		const thrMap: Record<string, string> = {};
		if (savedMetrics) {
			for (const m of savedMetrics) {
				fMap[m.metric_id] = m.use_friendly_format ?? true;
				hMap[m.metric_id] = m.horizons ? { ...m.horizons } : { ...HORIZONS_ALL };
				// Issue #624: sms_threshold laden (nur threshold-fähige Metriken).
				if (SMS_THRESHOLD_METRIC_IDS.includes(m.metric_id) && m.sms_threshold != null) {
					thrMap[m.metric_id] = String(m.sms_threshold);
				}
			}
		}

		// Issue #587: WeatherMetricsTab arbeitet ohne Detail-Bucket (hideDetailBucket=true).
		// Bestehende secondary-Metriken werden verlustfrei nach primary migriert.
		const mergedColumns = bucketsToColumns(b);
		b = { primary: mergedColumns, secondary: [], off: b.off };

		const savedPreset = trip.display_config?.preset_name;
		selectedTemplate = savedPreset ?? '';
		buckets = b;
		friendlyMap = fMap;
		horizonsMap = hMap;
		// Conflict 2 resolved: BEIDE Zuweisungen.
		smsThresholds = thrMap;
		savedSnapshot = snapshot(b, fMap, hMap, telegramKurzform, thrMap, channels);
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

	// Issue #622: Create-Modus — Kanal-Änderungen nach oben propagieren.
	$effect(() => {
		if (createMode && onChannelsChange) {
			onChannelsChange({ ...channels });
		}
	});

	// Preset-Auswahl
	function applyPreset(id: string) {
		const userP = userPresets.find((p) => p.id === id);
		const tmpl = templates.find((t) => t.id === id);
		const activeIds = userP
			? userP.metrics.filter((m) => m.enabled).map((m) => m.metric_id)
			: (tmpl ? tmpl.metrics : []);
		let newBuckets = autoAssign(activeIds, catalog);
		newBuckets = { primary: bucketsToColumns(newBuckets), secondary: [], off: newBuckets.off };
		const newFriendly = { ...friendlyMap };
		if (userP) {
			for (const m of userP.metrics) {
				newFriendly[m.metric_id] = m.use_friendly_format;
			}
		}
		applyDiff(newBuckets.primary, newFriendly, id);
		buckets = newBuckets;
		friendlyMap = newFriendly;
		selectedTemplate = id;
	}

	function onSelectPreset(id: string) {
		if (isDirty) { pendingPreset = id; return; }
		applyPreset(id);
	}

	function confirmPreset() {
		if (pendingPreset) applyPreset(pendingPreset);
		pendingPreset = null;
	}

	function onMode(id: string, useIndicator: boolean) {
		const newFriendly = { ...friendlyMap, [id]: useIndicator };
		applyDiff(buckets.primary, newFriendly, selectedTemplate);
		friendlyMap = newFriendly;
	}

	// Toggle: Metrik aktivieren (→ primary) oder deaktivieren (→ off).
	// secondary ist nach #587 immer leer — kein secondary-Zweig nötig (F002).
	function onToggleMetric(id: string, wasOn: boolean) {
		const from: keyof Buckets = buckets.primary.includes(id) ? 'primary' : 'off';
		const to: keyof Buckets = wasOn ? 'off' : 'primary';
		if (from !== to) {
			const newBuckets = move(buckets, id, from, to);
			applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
			buckets = newBuckets;
		}
		if (selectedTemplate) selectedTemplate = '';
	}

	// Aus Abschnitt 3 entfernen (→ off).
	function onRemove(id: string) {
		const newBuckets = move(buckets, id, 'primary', 'off');
		applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
		buckets = newBuckets;
		if (selectedTemplate) selectedTemplate = '';
	}

	// Reihenfolge ▲▼.
	function onReorder(id: string, dir: -1 | 1) {
		const newBuckets = reorder(buckets, 'primary', id, dir);
		applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
		buckets = newBuckets;
	}

	function handleDiscard() {
		try {
			const snap = JSON.parse(savedSnapshot);
			buckets = snap.buckets;
			friendlyMap = snap.friendlyMap;
			horizonsMap = snap.horizonsMap ?? {};
			telegramKurzform = snap.telegramKurzform ?? false;
			// Conflict 3 resolved: BEIDE Felder wiederherstellen.
			smsThresholds = snap.smsThresholds ?? {};
			channels = snap.channels ?? { email: true, telegram: true, sms: false };
		} catch (e) {
			console.error(e);
			initFromTrip();
			telegramKurzform = trip.display_config?.telegram_kurzform ?? false;
			smsThresholds = {};
		}
	}

	async function handleSave() {
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			const baseMetrics = buildWeatherConfigMetrics(buckets, friendlyMap, horizonsMap, catalog);
			// Issue #624: sms_threshold pro Metrik in Payload schreiben (additiv, Read-Modify-Write).
			const metrics = baseMetrics.map((m) => {
				if (!SMS_THRESHOLD_METRIC_IDS.includes(m.metric_id)) return m;
				const rawThr = smsThresholds[m.metric_id];
				const parsed = rawThr !== undefined && rawThr !== '' ? parseFloat(rawThr) : null;
				if (parsed !== null && !isNaN(parsed)) {
					return { ...m, sms_threshold: parsed };
				}
				return m;
			});
			const payload = {
				...(trip.display_config ?? {}),
				metrics,
				preset_name: selectedTemplate || undefined,
				telegram_kurzform: telegramKurzform,
				channels,
			};
			// Issue #622: Create-Modus — kein PUT, State per Binding gehalten.
			if (!createMode) {
				await api.put(`/api/trips/${trip.id}/weather-config`, payload);
				onTripUpdate?.({ ...trip, display_config: payload });
			}
			saveSuccess = true;
			// Conflict 4 resolved: BEIDE Felder im snapshot-Aufruf.
			savedSnapshot = snapshot(buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, channels);
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

	// Für SavePresetDialog (erwartet enabledMap): aktive = primary.
	const enabledMap = $derived.by(() => {
		const map: Record<string, boolean> = {};
		for (const id of allCatalogIds()) map[id] = false;
		for (const id of buckets.primary) map[id] = true;
		return map;
	});
</script>

{#if loading && Object.keys(catalog).length === 0}
	<div class="metrics-tab loading-shell" aria-busy="true">
		<p class="loading-msg">Lade Metriken…</p>
	</div>
{:else}
	<div data-testid="weather-metrics-tab" class="metrics-tab">
		<!-- Save-Bar (oben, schmal) -->
		<div class="save-bar">
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

		<!-- Desktop 2-Spalten-Layout -->
		<!-- Conflict 5 resolved: v2-Struktur erhalten, SMS-Schwellwerte als neue Card nach 04. -->
		<div class="v2-layout">
			<!-- LINKS: Abschnitte -->
			<div class="editor-col">
				<!-- 01 Profil -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:10px">01 — Profil</Eyebrow>
					<WeatherV2PresetBar
						{selectedTemplate}
						dirty={isDirty}
						{templates}
						{userPresets}
						onSelectPreset={onSelectPreset}
						onOpenSaveDialog={() => (showSavePresetDialog = true)}
					/>
				</Card>

				<!-- 02 Grundauswahl -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:4px">02 — Grundauswahl</Eyebrow>
					<WeatherV2Grundauswahl
						{catalog}
						primaryColumns={buckets.primary}
						{highlight}
						onToggle={(id, wasOn) => onToggleMetric(id, wasOn)}
					/>
				</Card>

				<!-- 03 Reihenfolge & Darstellung -->
				<Card padding={0}>
					<div class="card-head">
						<Eyebrow>03 — Reihenfolge & Darstellung</Eyebrow>
						<div class="card-subhead">Reihenfolge · Roh/Einfach</div>
					</div>
					<WeatherV2Reihenfolge
						primaryColumns={buckets.primary}
						{metricById}
						{friendlyMap}
						activeChannel="telegram"
						{highlight}
						onRemove={onRemove}
						onReorder={onReorder}
						{onMode}
					/>
				</Card>

				<!-- 04 Kanäle -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:4px">04 — Kanäle</Eyebrow>
					<div class="kanaele-subhead">Wohin geht das Briefing?</div>
					<WeatherV2Kanaele
						{channels}
						primaryCount={buckets.primary.length}
						{telegramKurzform}
						onChange={(ch) => { channels = ch; }}
						onKurzformChange={(v) => { telegramKurzform = v; }}
					/>
				</Card>

				<!-- 05 SMS-Schwellwerte (Issue #624) -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:8px">SMS-Schwellwerte</Eyebrow>
					<p class="option-hint">
						Ab welchem Wert gilt eine Metrik in der Kurzform als „erste Überschreitung"?
						Leer = Standard-Schwellwert.
					</p>
					<div class="sms-thresholds" data-testid="sms-thresholds">
						<div class="sms-threshold-fields">
							<div class="sms-threshold-row">
								<label class="sms-threshold-label" for="sms-thr-wind">Wind (km/h)</label>
								<input
									id="sms-thr-wind"
									data-testid="sms-threshold-wind"
									type="number"
									min="0"
									step="1"
									class="sms-threshold-input"
									placeholder="Standard"
									value={smsThresholds['wind'] ?? ''}
									oninput={(e) => { smsThresholds = { ...smsThresholds, wind: (e.target as HTMLInputElement).value }; }}
								/>
							</div>
							<div class="sms-threshold-row">
								<label class="sms-threshold-label" for="sms-thr-gust">Böen (km/h)</label>
								<input
									id="sms-thr-gust"
									data-testid="sms-threshold-gust"
									type="number"
									min="0"
									step="1"
									class="sms-threshold-input"
									placeholder="Standard"
									value={smsThresholds['gust'] ?? ''}
									oninput={(e) => { smsThresholds = { ...smsThresholds, gust: (e.target as HTMLInputElement).value }; }}
								/>
							</div>
							<div class="sms-threshold-row">
								<label class="sms-threshold-label" for="sms-thr-precip">Niederschlag (mm)</label>
								<input
									id="sms-thr-precip"
									data-testid="sms-threshold-precipitation"
									type="number"
									min="0"
									step="0.1"
									class="sms-threshold-input"
									placeholder="Standard"
									value={smsThresholds['precipitation'] ?? ''}
									oninput={(e) => { smsThresholds = { ...smsThresholds, precipitation: (e.target as HTMLInputElement).value }; }}
								/>
							</div>
							<div class="sms-threshold-row">
								<label class="sms-threshold-label" for="sms-thr-rain-prob">Regenw. (%)</label>
								<input
									id="sms-thr-rain-prob"
									data-testid="sms-threshold-rain-probability"
									type="number"
									min="0"
									max="100"
									step="1"
									class="sms-threshold-input"
									placeholder="Standard"
									value={smsThresholds['rain_probability'] ?? ''}
									oninput={(e) => { smsThresholds = { ...smsThresholds, rain_probability: (e.target as HTMLInputElement).value }; }}
								/>
							</div>
						</div>
					</div>
				</Card>
			</div>

			<!-- RECHTS: Live-Mail-Vorschau (sticky) -->
			<div class="preview-col">
				<WeatherV2MailPreview
					primaryColumns={buckets.primary}
					{metricById}
					{friendlyMap}
					{telegramKurzform}
					{highlight}
				/>
			</div>
		</div>

		<!-- Mobile: fixierter "So kommt es an"-Button → Mail-Vorschau als Bottom-Sheet (#618) -->
		<button class="mobile-mail-fab" data-testid="mobile-mail-fab" onclick={() => (mailSheetOpen = true)}>
			<span>So kommt es an</span>
			<span class="mobile-mail-fab__badge">{buckets.primary.length + (buckets.secondary?.length ?? 0)} Metriken</span>
		</button>
		<Sheet open={mailSheetOpen} onClose={() => (mailSheetOpen = false)} title="So kommt es an">
			<div data-testid="mobile-mail-sheet" style="padding: 4px 16px 24px;">
				<WeatherV2MailPreview
					primaryColumns={buckets.primary}
					{metricById}
					{friendlyMap}
					{telegramKurzform}
					{highlight}
				/>
			</div>
		</Sheet>

		<!-- Dialoge & Overlays -->
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
	</div>
{/if}

<style>
	.loading-shell {
		padding: var(--g-s-4);
	}
	/* Issue #618: FAB auf Desktop versteckt */
	.mobile-mail-fab {
		display: none;
	}
	.save-bar {
		display: flex;
		gap: var(--g-s-2);
		align-items: center;
		flex-wrap: wrap;
		padding: var(--g-s-3) var(--g-s-10);
		border-bottom: 1px solid var(--g-rule-soft);
		margin-bottom: 0;
	}
	.save-success {
		font-size: var(--g-text-sm);
		color: var(--g-success);
	}
	.save-error {
		font-size: var(--g-text-sm);
		color: var(--g-danger);
	}
	/* Desktop 2-Spalten-Layout (1:1 nach JSX WetterMetrikenTabV2) */
	.v2-layout {
		display: grid;
		grid-template-columns: minmax(460px, 1fr) minmax(420px, 1fr);
		gap: 36px;
		padding: 28px 40px 60px;
		max-width: 1480px;
		align-items: start;
	}
	.editor-col {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}
	.card-head {
		padding: 14px 16px 10px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.card-subhead {
		font-size: 15px;
		font-weight: 600;
		margin-top: 2px;
		color: var(--g-ink);
	}
	.kanaele-subhead {
		font-size: 15px;
		font-weight: 600;
		margin-bottom: 14px;
		color: var(--g-ink);
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
	/* Conflict 6 resolved: v2-CSS + #624-Klassen, ohne telegram-options */
	.option-hint {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		line-height: 1.5;
		margin: 0 0 var(--g-s-3);
	}
	/* Issue #624: SMS-Schwellwerte */
	.sms-thresholds {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	.sms-threshold-fields {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}
	.sms-threshold-row {
		display: flex;
		align-items: center;
		gap: var(--g-s-3);
	}
	.sms-threshold-label {
		font-size: var(--g-text-sm);
		color: var(--g-ink);
		min-width: 160px;
	}
	.sms-threshold-input {
		width: 100px;
		padding: var(--g-s-1) var(--g-s-2);
		font-size: var(--g-text-sm);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-radius-sm);
		background: var(--g-card);
		color: var(--g-ink);
	}
	.sms-threshold-input:focus {
		outline: 2px solid var(--g-accent);
		outline-offset: 1px;
		border-color: var(--g-accent);
	}
	@media (max-width: 899px) {
		.v2-layout {
			grid-template-columns: 1fr;
			gap: var(--g-s-6);
			padding: var(--g-s-4);
			padding-bottom: 88px;
		}
		.save-bar {
			padding: var(--g-s-3) var(--g-s-4);
		}
		/* Inline-Vorschau auf Mobil verstecken (kommt stattdessen als Sheet) */
		.preview-col {
			display: none;
		}
		/* Issue #618: Floating FAB mobil */
		.mobile-mail-fab {
			position: fixed;
			bottom: 16px;
			left: 14px;
			right: 14px;
			z-index: 20;
			display: flex;
			align-items: center;
			justify-content: center;
			gap: 10px;
			padding: 14px;
			border: none;
			border-radius: var(--g-r-pill);
			background: var(--g-ink);
			color: var(--g-paper);
			font-size: 14px;
			font-weight: 600;
			cursor: pointer;
			box-shadow: 0 4px 20px rgba(26, 26, 24, 0.25);
		}
		.mobile-mail-fab__badge {
			font-family: var(--g-font-mono);
			font-size: 11px;
			opacity: 0.7;
			background: rgba(255, 255, 255, 0.15);
			padding: 2px 8px;
			border-radius: 999px;
		}
	}
</style>
