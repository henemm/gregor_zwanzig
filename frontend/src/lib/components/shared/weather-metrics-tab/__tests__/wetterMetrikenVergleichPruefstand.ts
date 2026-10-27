// Gemeinsamer Prüfstand der Wetter-Metriken/Layout-Speichertests im
// Ortsvergleich (Issue #2276 Scheibe S4, Epic #2345). KEINE Testdatei (kein
// `.test.ts`) — nur Aufbauhilfen.
//
// Bewusst OHNE Import der NEUEN kombinierten Exporte aus
// `weatherMetricsCompareSave.ts` (erstelleWetterMetrikenVergleichSpeicherung,
// baueWetterMetrikenNutzlast, wetterMetrikenSnapshotAus, ...) — der Prüfstand
// muss auch heute laden, damit das Rot der Tests an den fehlenden neuen
// Exporten liegt, nicht hier (Muster wertebereicheVergleichPruefstand.ts, S3).
//
// Bewusst OHNE Umweg über die echten Hydrations-Funktionen
// (hydrateWeatherMetricsFromPreset/hydrateLayoutFieldsFromPreset): deren
// Katalog-Abhängigkeit (registeredCompareMetricCatalog) macht Werte instabil,
// wenn andere Tests im selben Prozess zuvor einen Katalog registriert haben.
// Für die hier geprüften Snapshot-/Diff-/PUT-Mechanismen zählt nur, dass die
// Werte deterministisch und aus dem Preset ableitbar sind — nicht, dass die
// Katalog-Rückübersetzung (eigenes Testnetz: compareMetricSelection u. a.)
// exakt nachgebaut wird.
//
// Transport: echtes `api` gegen `fakeTripServer.ts`. Echte `SaveStatus`-Instanz.

import { SaveStatus } from '../../../../stores/saveStatusStore.svelte.ts';
import type { ComparePreset } from '../../../../types.ts';

export function makePreset(id: string, overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id,
		name: 'Ortsvergleich Wetter-Metriken',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'daily',
		previous_schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_alerts_enabled: true,
		official_warnings: { enabled: true },
		radar_alert_enabled: false,
		send_telegram: true,
		send_sms: false,
		send_premium_sms: false,
		alert_cooldown_minutes: 30,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		hourly_enabled: true,
		outlook_enabled: true,
		day_window_start_hour: 4,
		day_window_end_hour: 19,
		corridors: [
			{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true },
			{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }
		],
		display_config: {
			metric_alert_levels: { wind_max_kmh: 'standard', snow_depth_cm: 'sensibel' },
			ideal_ranges: { wind_max_kmh: { min: 0, max: 40 }, snow_depth_cm: { min: 30, max: 200 } },
			active_metrics: ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c'],
			channel_active_metrics: {},
			telegram_style: 'rich',
			hourly_metrics: ['wind_max_kmh', 'temp_max_c'],
			outlook_metrics: ['temp_max_c'],
			outlook_metric_formats: { temp_max_c: true }
		},
		...overrides
	} as ComparePreset;
}

/** Echte SaveStatus-Instanz ohne Konstruktor (Runen-Felder), MIT Kennung
 *  {typ:'vergleich', id} — sonst läuft `retryConflict()` leer. */
export function createController(id: string): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._lastFailed = null;
	f._unresolvedError = null;
	f._tripId = id;
	f._resourceKind = 'vergleich';
	return inst;
}

/** EIN Wizard-Zustand für den ganzen Reiter: BEIDE Domänen (Wetter-Metriken +
 *  Layout) bereits hydriert — wie CompareTabs es nach der zusammengeführten
 *  Hydration (Design-Entscheidung 4 der Spec) liefern wird. Direkt aus dem
 *  Preset gelesen (kein Katalog-Umweg, s. Kopfkommentar). */
export function hydrierterWs(preset: ComparePreset): Record<string, unknown> {
	const dc = (preset.display_config as Record<string, unknown>) ?? {};
	return {
		activeMetricKeys: [...((dc.active_metrics as string[] | undefined) ?? [])],
		channelActiveMetricKeys: {
			email: null,
			telegram: null,
			sms: null,
			...((dc.channel_active_metrics as Record<string, string[] | null>) ?? {})
		},
		officialAlertsEnabled: preset.official_alerts_enabled ?? true,
		dayWindowStartHour: preset.day_window_start_hour ?? 4,
		dayWindowEndHour: preset.day_window_end_hour ?? 19,
		hourlyMetricKeys: (dc.hourly_metrics as string[] | null | undefined) ?? null,
		hourlyEnabled: preset.hourly_enabled ?? true,
		outlookMetricKeys: (dc.outlook_metrics as string[] | null | undefined) ?? null,
		outlookMetricFormats: (dc.outlook_metric_formats as Record<string, boolean> | undefined) ?? null,
		outlookEnabled: preset.outlook_enabled ?? true
	};
}

/**
 * Nachbau der Bedienlogik von WeatherMetricsTab.svelte im vergleich-Kontext
 * OHNE Svelte: direkte Feld-Mutation, wie die realen Handler
 * (toggleCompareMetric/onToggleVergleichOfficialAlerts/DayWindowCard-Handler/
 * Drag-Ende der Stundenverlauf-/Ausblick-Steuerung) am Ende auch tun. Das
 * Melden an die Speicherung (`aenderungMelden()`) macht der Test selbst —
 * genau das übernimmt nach der Implementierung der reaktive `$effect`.
 */
export function wetterMetrikenBedienung(ws: Record<string, unknown>) {
	return {
		toggleMetric(key: string): void {
			const cur = ws.activeMetricKeys as string[];
			ws.activeMetricKeys = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
		},
		reorderMetrics(order: string[]): void {
			ws.activeMetricKeys = [...order];
		},
		toggleOfficialAlerts(): void {
			ws.officialAlertsEnabled = !(ws.officialAlertsEnabled as boolean);
		},
		setDayWindow(start: number, end: number): void {
			ws.dayWindowStartHour = start;
			ws.dayWindowEndHour = end;
		},
		hourlyDragEnd(order: string[]): void {
			ws.hourlyMetricKeys = [...order];
		},
		outlookSelect(order: string[]): void {
			ws.outlookMetricKeys = [...order];
		},
		outlookFormatToggle(metric: string, roh: boolean): void {
			ws.outlookMetricFormats = {
				...((ws.outlookMetricFormats as Record<string, boolean>) ?? {}),
				[metric]: roh
			};
		}
	};
}

export function dc(body: unknown): Record<string, unknown> {
	return ((body as Record<string, unknown>).display_config as Record<string, unknown>) ?? {};
}
