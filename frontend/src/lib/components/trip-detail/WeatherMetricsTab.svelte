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
	import type { Trip, MetricPreset, Horizons, ReportConfig } from '$lib/types';
	import { HORIZONS_ALL } from '$lib/types';
	import { Btn, Card, Eyebrow, Pill } from '$lib/components/atoms';
	import SavePresetDialog from './SavePresetDialog.svelte';
	import Sheet from '$lib/components/mobile/Sheet.svelte';
	// v2 Sub-Komponenten (neu, standalone, keine Abhängigkeit von OutputLayoutEditor)
	import WeatherV2PresetBar from './WeatherV2PresetBar.svelte';
	import WeatherV2Grundauswahl from './WeatherV2Grundauswahl.svelte';
	import WeatherV2Reihenfolge from './WeatherV2Reihenfolge.svelte';
	// WeatherV2Kanaele entfernt in Issue #736 (Kanal-Config → Versand-Reiter)
	import WeatherV2MailPreview from './WeatherV2MailPreview.svelte';
	import ThresholdMetricRow from './ThresholdMetricRow.svelte';
	import EditReportConfigSection from '$lib/components/edit/EditReportConfigSection.svelte';
	import {
		autoAssign, bucketsToColumns, move, buildWeatherConfigMetrics,
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
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	interface Props {
		trip: Trip;
		/** Issue #622: Create-Modus — kein PUT; Kanäle per onChannelsChange nach oben emittieren */
		createMode?: boolean;
		onChannelsChange?: (c: ChannelConfig) => void;
		/** Issue #694: Trip-State in +page.svelte nach erfolgreichem PUT aktualisieren */
		onTripUpdate?: (t: Trip) => void;
		/** Issue #758: SaveStatus controller — wenn gesetzt, entfällt der explizite Speichern-Button. */
		saveController?: SaveStatus;
	}
	let { trip, createMode = false, onChannelsChange, onTripUpdate, saveController }: Props = $props();

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
	const SMS_THRESHOLD_METRIC_IDS = ['precipitation', 'rain_probability', 'wind', 'gust', 'thunder'];
	let smsThresholds = $state<Record<string, string>>({});
	let savedSnapshot = $state('');
	let showSavePresetDialog = $state(false);
	let mailSheetOpen = $state(false);
	let pendingPreset: string | null = $state(null);
	let profile = $state<{ mail_to?: string; telegram_chat_id?: string; sms_to?: string } | null>(null);
	// Issue #736: E-Mail-Inhalt-Karte im Inhalt-Reiter (analog BriefingScheduleTab).
	let reportConfig = $state<ReportConfig>(
		trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : {}
	);

	// availableChannels entfernt in Issue #736 (WeatherV2Kanaele nicht mehr im Inhalt-Reiter)

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

	// Issue #736: channels aus isDirty + snapshot entfernt (Kanal-Config lebt jetzt im Versand-Reiter).
	// Issue #776/#774: reportConfig in isDirty einschliessen (Toggle-Persistenz, Checkbox-Änderung macht Tab dirty).
	const isDirty = $derived(
		JSON.stringify({ buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, reportConfig }) !== savedSnapshot,
	);

	function snapshot(
		b: Buckets, f: Record<string, boolean>, h: Record<string, Horizons>,
		tk: boolean, st: Record<string, string>, rc: ReportConfig | undefined
	): string {
		return JSON.stringify({ buckets: b, friendlyMap: f, horizonsMap: h, telegramKurzform: tk, smsThresholds: st, reportConfig: rc ?? {} });
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
		// Issue #736: channels nicht mehr im snapshot (Conflict 2 entfällt).
		// Issue #774: reportConfig in snapshot aufnehmen.
		smsThresholds = thrMap;
		savedSnapshot = snapshot(b, fMap, hMap, telegramKurzform, thrMap, reportConfig);
	}

	async function load() {
		loading = true;
		try {
			const [catalogData, templateData, presetData, profileData] = await Promise.all([
				api.get<MetricCatalog>('/api/metrics'),
				api.get<Template[]>('/api/templates').catch(() => [] as Template[]),
				api.get<MetricPreset[]>('/api/metric-presets').catch(() => [] as MetricPreset[]),
				fetch('/api/auth/profile', { credentials: 'same-origin' })
					.then((r) => (r.ok ? r.json() : null))
					.catch(() => null),
			]);
			catalog = catalogData;
			templates = templateData;
			userPresets = presetData;
			profile = profileData;
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
		scheduleAutoSave();
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
		scheduleAutoSave();
	}

	// Aus Abschnitt 3 entfernen (→ off).
	function onRemove(id: string) {
		const newBuckets = move(buckets, id, 'primary', 'off');
		applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
		buckets = newBuckets;
		if (selectedTemplate) selectedTemplate = '';
		scheduleAutoSave();
	}

	// Reihenfolge per Drag & Drop (#848).
	function onDndReorder(fromId: string, toId: string) {
		const list = [...buckets.primary];
		const fromIdx = list.indexOf(fromId);
		const toIdx = list.indexOf(toId);
		if (fromIdx === -1 || toIdx === -1) return;
		list.splice(fromIdx, 1);
		list.splice(toIdx, 0, fromId);
		const newBuckets = { ...buckets, primary: list };
		applyDiff(newBuckets.primary, friendlyMap, selectedTemplate);
		buckets = newBuckets;
		scheduleAutoSave();
	}

	function handleDiscard() {
		try {
			const snap = JSON.parse(savedSnapshot);
			buckets = snap.buckets;
			friendlyMap = snap.friendlyMap;
			horizonsMap = snap.horizonsMap ?? {};
			telegramKurzform = snap.telegramKurzform ?? false;
			// Issue #736: channels nicht mehr im snapshot (Conflict 3 entfällt).
			smsThresholds = snap.smsThresholds ?? {};
			// Issue #774: reportConfig wiederherstellen (sonst bleibt Tab dirty nach Verwerfen).
			reportConfig = snap.reportConfig ?? {};
		} catch (e) {
			console.error(e);
			initFromTrip();
			telegramKurzform = trip.display_config?.telegram_kurzform ?? false;
			smsThresholds = {};
			reportConfig = trip.report_config ? JSON.parse(JSON.stringify(trip.report_config)) : {};
		}
	}

	function buildWeatherPayload() {
		const baseMetrics = buildWeatherConfigMetrics(buckets, friendlyMap, horizonsMap, catalog);
		const metrics = baseMetrics.map((m) => {
			if (!SMS_THRESHOLD_METRIC_IDS.includes(m.metric_id)) return m;
			const rawThr = smsThresholds[m.metric_id];
			const parsed = rawThr !== undefined && rawThr !== '' ? parseFloat(rawThr) : null;
			if (parsed !== null && !isNaN(parsed)) {
				return { ...m, sms_threshold: parsed };
			}
			return m;
		});
		return {
			...(trip.display_config ?? {}),
			metrics,
			preset_name: selectedTemplate || undefined,
			telegram_kurzform: telegramKurzform,
		};
	}

	async function handleSave() {
		saving = true;
		saveSuccess = false;
		saveError = null;
		try {
			const payload = buildWeatherPayload();
			// Issue #622: Create-Modus — kein PUT, State per Binding gehalten.
			if (!createMode) {
				await api.put(`/api/trips/${trip.id}/weather-config`, payload);
				// Issue #776/#774: report_config separat persistieren (zweiter PUT, Read-Modify-Write im Backend).
				// Issue #850: Server-Response enthält aktualisierte alert_rules (via SyncAlertRules) — nie manuell konstruieren.
				const updated = await api.put<Trip>(`/api/trips/${trip.id}`, { report_config: reportConfig });
				onTripUpdate?.(updated);
			}
			saveSuccess = true;
			// Issue #736: channels aus snapshot entfernt (Conflict 4 entfällt).
			savedSnapshot = snapshot(buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, reportConfig);
			setTimeout(() => { saveSuccess = false; }, 3000);
		} catch (e: unknown) {
			console.error(e);
			saveError = (e as { error?: string })?.error ?? 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}

	// Issue #758: schedule auto-save via controller when metrics change.
	function scheduleAutoSave() {
		if (!saveController || createMode) return;
		const payload = buildWeatherPayload();
		saveController.schedule(async () => {
			await api.put(`/api/trips/${trip.id}/weather-config`, payload);
			// Issue #850: Server-Response enthält aktualisierte alert_rules — nie manuell konstruieren.
			const updated = await api.put<Trip>(`/api/trips/${trip.id}`, { report_config: reportConfig });
			onTripUpdate?.(updated);
			savedSnapshot = snapshot(buckets, friendlyMap, horizonsMap, telegramKurzform, smsThresholds, reportConfig);
		});
	}

	// Issue #774: reportConfig-Änderungen (Checkboxen) triggern Auto-Save.
	// Nicht-reaktive Vergleichsvariable vermeidet Rekursion.
	let _lastReportConfigJson = JSON.stringify(reportConfig);
	$effect(() => {
		const cur = JSON.stringify(reportConfig);
		if (cur !== _lastReportConfigJson) {
			_lastReportConfigJson = cur;
			scheduleAutoSave();
		}
	});

	async function onPresetSaved(preset: MetricPreset) {
		userPresets = [preset, ...userPresets];
		applyPreset(preset.id);
		// F004: wenn saveController vorhanden, über scheduleAutoSave routen,
		// damit der Indikator korrekt Feedback gibt (handleSave kennt den Controller nicht).
		if (saveController && !createMode) {
			scheduleAutoSave();
		} else {
			await handleSave();
		}
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
		<!-- Save-Bar (oben, schmal) — expliziter Button nur ohne saveController (#758) -->
		<div class="save-bar">
			{#if isDirty && !saveController}
				<Pill tone="warning" data-testid="weather-metrics-dirty-pill">Ungespeicherte Änderungen</Pill>
				<Btn variant="ghost" size="sm" data-testid="weather-metrics-discard" onclick={handleDiscard}>Verwerfen</Btn>
			{/if}
			{#if saveSuccess && !saveController}
				<span data-testid="weather-metrics-tab-success" class="save-success">Gespeichert</span>
			{/if}
			{#if saveError && !saveController}
				<span data-testid="weather-metrics-tab-error" class="save-error">{saveError}</span>
			{/if}
			{#if !saveController}
				<Btn variant="primary" size="sm" data-testid="weather-metrics-tab-save" disabled={saving || !isDirty} onclick={handleSave}>
					{saving ? 'Speichern…' : 'Speichern'}
				</Btn>
			{/if}
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
						onDndReorder={onDndReorder}
						{onMode}
					/>
				</Card>

				<!-- 04 Schwellwerte (Issue #624, umbenannt in #736) -->
				<Card padding={18}>
					<Eyebrow style="margin-bottom:8px">04 — Schwellwerte</Eyebrow>
					<p class="option-hint">
						Gelten für SMS-Token, Telegram-Kurzform und den E-Mail-Ausblick/Trend-Block
					</p>
					<div class="sms-thresholds" data-testid="sms-thresholds">
						<table class="threshold-table">
							<tbody>
								<ThresholdMetricRow
									metricId="wind"
									label="Wind (km/h)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 15 },
										{ id: 'standard', label: 'Standard', float: 20 },
										{ id: 'robust', label: 'Robust', float: 30 }
									]}
									currentFloat={smsThresholds['wind'] !== undefined && smsThresholds['wind'] !== '' ? parseFloat(smsThresholds['wind']) : null}
									onChange={(id, f) => { smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								<ThresholdMetricRow
									metricId="gust"
									label="Böen (km/h)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 30 },
										{ id: 'standard', label: 'Standard', float: 40 },
										{ id: 'robust', label: 'Robust', float: 50 }
									]}
									currentFloat={smsThresholds['gust'] !== undefined && smsThresholds['gust'] !== '' ? parseFloat(smsThresholds['gust']) : null}
									onChange={(id, f) => { smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								<ThresholdMetricRow
									metricId="precipitation"
									label="Niederschlag (mm)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 0.3 },
										{ id: 'standard', label: 'Standard', float: 0.8 },
										{ id: 'robust', label: 'Robust', float: 1.5 }
									]}
									currentFloat={smsThresholds['precipitation'] !== undefined && smsThresholds['precipitation'] !== '' ? parseFloat(smsThresholds['precipitation']) : null}
									onChange={(id, f) => { smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								<ThresholdMetricRow
									metricId="rain_probability"
									label="Regenwahrsch. (%)"
									levels={[
										{ id: 'sensibel', label: 'Sensibel', float: 25 },
										{ id: 'standard', label: 'Standard', float: 40 },
										{ id: 'robust', label: 'Robust', float: 60 }
									]}
									currentFloat={smsThresholds['rain_probability'] !== undefined && smsThresholds['rain_probability'] !== '' ? parseFloat(smsThresholds['rain_probability']) : null}
									onChange={(id, f) => { smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
								<ThresholdMetricRow
									metricId="thunder"
									label="Gewitter"
									levels={[
										{ id: 'med', label: 'MED', float: 1.0 },
										{ id: 'high', label: 'HIGH', float: 2.0 }
									]}
									currentFloat={smsThresholds['thunder'] !== undefined && smsThresholds['thunder'] !== '' ? parseFloat(smsThresholds['thunder']) : null}
									onChange={(id, f) => { smsThresholds = { ...smsThresholds, [id]: String(f) }; scheduleAutoSave(); }}
								/>
							</tbody>
						</table>
					</div>
				</Card>

				<!-- Issue #736: E-Mail-Inhalt-Karte im Inhalt-Reiter, kein Kanal-Toggle -->
				<EditReportConfigSection bind:reportConfig mode="edit" showMailContent={true} showChannels={false} />
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
			existingNames={userPresets.map(p => p.name)}
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
	.threshold-table {
		width: 100%;
		border-collapse: collapse;
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
