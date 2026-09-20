// Gemeinsamer Prüfstand der Versand-Speichertests im Ortsvergleich
// (Issue #2276 Scheibe S5, Epic #2345). KEINE Testdatei (kein `.test.ts`) —
// nur Aufbauhilfen.
//
// Bewusst OHNE Import der NEUEN Exporte aus
// `shared/versandVergleichSpeicherung.ts` (erstelleVersandVergleichSpeicherung,
// baueVersandNutzlast, versandSnapshotAus, rollbackVersandSnapshot, …) — der
// Prüfstand muss auch HEUTE laden, damit das Rot der Tests an den fehlenden
// neuen Exporten liegt und nicht hier (Muster wetterMetrikenVergleich-
// Pruefstand.ts, S4).
//
// Bewusst OHNE Umweg über `hydrateVersandFieldsFromPreset`: die Funktion zieht
// in dieser Scheibe gerade aus der Klebeschicht in das neue Modul um; ein
// Import würde den Prüfstand an die Seite binden, die er nicht prüft. Für die
// hier geprüften Snapshot-/Diff-/PUT-Mechanismen zählt nur, dass die Werte
// deterministisch aus dem Preset ableitbar sind (Defaults identisch zur
// Edit-Routen-Hydration; eigenes Testnetz: hub_versand_inline.test.ts).
//
// Transport: echtes `api` gegen `fakeTripServer.ts`. Echte `SaveStatus`-Instanz.

import { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import type { ComparePreset } from '../../../types.ts';

export function makePreset(id: string, overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id,
		name: 'Ortsvergleich Versand',
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
		morning_enabled: true,
		morning_time: '06:30:00',
		evening_enabled: false,
		evening_time: '18:00:00',
		end_date: '2026-08-01',
		// Die drei Legacy-Restfelder (Spec, Implementation Details Punkt 6):
		// kein Kontrollelement im Versand-Tab mutiert sie, der Versand-PUT muss
		// sie trotzdem tragen — sonst nullt er Alarm-Zustellungsfelder (AC-11).
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		alert_channel_thresholds: { email: 'gering', telegram: 'hoch', sms: 'gering' },
		hourly_enabled: true,
		outlook_enabled: true,
		day_window_start_hour: 4,
		day_window_end_hour: 19,
		corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
		display_config: {
			region: 'Tirol',
			ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
			active_metrics: ['snow_depth_cm'],
			metric_alert_levels: { snow_depth_cm: 'warn' },
			telegram_style: 'kurzform',
			hourly_metrics: ['snow_depth_cm'],
			outlook_metrics: ['snow_depth_cm'],
			outlook_metric_formats: { snow_depth_cm: true }
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

/** Wizard-Zustand, wie CompareTabs ihn nach der Versand-Hydration hält (die 10
 *  Snapshot-Felder + `sendEmail`, das `ComparePreset` nicht kennt). */
export function hydrierterWiz(preset: ComparePreset): Record<string, unknown> {
	return {
		sendEmail: true,
		sendTelegram: preset.send_telegram ?? false,
		sendSms: preset.send_sms ?? false,
		morningEnabled: preset.morning_enabled ?? true,
		morningTime: (preset.morning_time ?? '06:00').slice(0, 5),
		eveningEnabled: preset.evening_enabled ?? false,
		eveningTime: (preset.evening_time ?? '18:00').slice(0, 5),
		endDate: preset.end_date ?? null,
		alertCooldownMinutes: preset.alert_cooldown_minutes ?? undefined,
		alertQuietFrom: preset.alert_quiet_from ?? undefined,
		alertQuietTo: preset.alert_quiet_to ?? undefined
	};
}

/**
 * Nachbau der Bedienlogik von VersandTab.svelte im vergleich-Zweig OHNE
 * Svelte: direkte Feld-Mutation, wie die realen Handler
 * (makeWizChannelHandler/makeTimeHandler/makeToggleHandler, VTLaufzeit-
 * Vergleich-onChange) am Ende auch tun. Das Melden an die Speicherung
 * (`aenderungMelden()`) macht der Test selbst — genau das übernimmt nach der
 * Implementierung der reaktive `$effect`.
 */
export function versandBedienung(wiz: Record<string, unknown>) {
	return {
		toggleTelegram(): void {
			wiz.sendTelegram = !(wiz.sendTelegram as boolean);
		},
		toggleSms(): void {
			wiz.sendSms = !(wiz.sendSms as boolean);
		},
		setMorgenZeit(hhmm: string): void {
			wiz.morningTime = hhmm;
		},
		setAbendZeit(hhmm: string): void {
			wiz.eveningTime = hhmm;
		},
		toggleAbendBriefing(): void {
			wiz.eveningEnabled = !(wiz.eveningEnabled as boolean);
		},
		/** „Bis auf Weiteres" im Laufzeit-Control — reiner Button-Klick, ohne
		 *  begleitendes change-/focusout-Ereignis (AC-5). */
		bisAufWeiteres(): void {
			wiz.endDate = null;
		},
		setEnddatum(datum: string): void {
			wiz.endDate = datum;
		}
	};
}

export function dc(body: unknown): Record<string, unknown> {
	return ((body as Record<string, unknown>).display_config as Record<string, unknown>) ?? {};
}
