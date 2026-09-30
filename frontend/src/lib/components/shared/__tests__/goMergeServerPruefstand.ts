// Gemeinsamer Prüfstand für den Ortsvergleich-Konfliktschutz (Issue #2375,
// löst #2381 mit). KEINE Testdatei (kein `.test.ts`) — nur Aufbauhilfen.
//
// Ersatz-Server für `globalThis.fetch`, der den Compare-Preset-PUT so
// behandelt wie der echte Go-Handler (`UpdateComparePresetHandler`,
// `internal/handler/compare_preset.go`):
//   - `If-Match` wird VOR dem Schreiben geprüft (Parser-Logik wie
//     `internal/handler/etag.go`); passt er nicht → 412 OHNE ETag-Header.
//   - Merge wie `mergeBriefingPatch` (`briefing_subscription.go:174-197`):
//     jedes Top-Level-Feld des Bodys überschreibt, fehlende Felder bleiben;
//     sind beide Seiten ein JSON-Objekt, wird eine Ebene tief gemergt
//     (`mergeConfigMap`, `config_merge.go:11-22` — ersetzt Schlüssel, löscht
//     nie einen). Arrays und alles unterhalb der zweiten Ebene werden ersetzt.
//   - Server-verwaltete Felder werden nach dem Merge aus dem Original
//     restauriert (`compare_preset.go:307-314`).
//   - Antwort = der gemergte GESAMTdatensatz mit neuem ETag.
//
// Der Unterschied zu `fakeTripServer.ts`: dort ERSETZT ein PUT den
// gespeicherten Rumpf komplett und `calls[].body` ist die ANTWORT. Für die
// Zusicherung „die fremde Änderung überlebt" und für exakte Schlüsselsätze
// braucht es den Merge und den mitgeschnittenen ANFRAGE-Rumpf — auch der
// abgelehnten (412) PUTs.
//
// Pfade werden über den `pathname` erkannt (relativ ODER absolut), damit auch
// ein Server-Loader mit `http://localhost:8090/api/...` hier landet.

export interface MitschnittEintrag {
	method: string;
	path: string;
	ifMatch: string | null;
	status: number;
	/** geparster ANFRAGE-Rumpf (bei PUT), sonst undefined */
	anfrage: unknown;
}

export interface GoMergeServer {
	handler: (input: unknown, init?: RequestInit) => Promise<Response>;
	mitschnitt: MitschnittEintrag[];
	/** alle PUT-Anfragerümpfe in Reihenfolge (inkl. 412-abgelehnter) */
	putRuempfe(): Record<string, unknown>[];
	/** der gespeicherte, gemergte Gesamtdatensatz */
	stand(id: string): Record<string, unknown>;
	etagOf(id: string): string;
	/** „anderes Gerät": schreibt direkt (ohne If-Match) über denselben Merge */
	fremdSchreiben(id: string, teil: Record<string, unknown>): void;
	install(): void;
	restore(): void;
}

const PRESET_RE = /^\/api\/compare\/presets\/([^/?#]+)$/;

const SERVER_VERWALTET = [
	'id',
	'user_id',
	'created_at',
	'paused_at',
	'archived_at',
	'kind',
	'letzter_versand',
	'top_ort_letzter_versand'
];

function istObjekt(v: unknown): v is Record<string, unknown> {
	return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function ifMatchAllows(header: string, current: string): boolean {
	const h = header.trim();
	if (h === '' || h === '*') return true;
	const cur = current.replace(/^"/, '').replace(/"$/, '');
	return h.split(',').some((part) => part.trim().replace(/^W\//, '').replace(/^"/, '').replace(/"$/, '') === cur);
}

/** Merge exakt nach Go-Regel (s. Kopfkommentar). */
export function goMerge(
	original: Record<string, unknown>,
	patch: Record<string, unknown>
): Record<string, unknown> {
	const out: Record<string, unknown> = JSON.parse(JSON.stringify(original));
	for (const [k, v] of Object.entries(patch)) {
		if (istObjekt(v) && istObjekt(out[k])) {
			out[k] = { ...(out[k] as Record<string, unknown>), ...JSON.parse(JSON.stringify(v)) };
		} else {
			out[k] = JSON.parse(JSON.stringify(v ?? null));
		}
	}
	for (const f of SERVER_VERWALTET) {
		if (f in original) out[f] = original[f];
		else delete out[f];
	}
	return out;
}

function pfadVon(input: unknown): string {
	const s = String(input);
	try {
		return new URL(s, 'http://gz.invalid').pathname;
	} catch {
		return s;
	}
}

export function createGoMergeServer(start: Record<string, Record<string, unknown>>): GoMergeServer {
	const daten = new Map<string, Record<string, unknown>>();
	const fps = new Map<string, number>();
	let seq = 0;
	for (const [id, doc] of Object.entries(start)) {
		daten.set(id, JSON.parse(JSON.stringify({ ...doc, id })));
		fps.set(id, ++seq);
	}
	const mitschnitt: MitschnittEintrag[] = [];
	const vorherige: Array<typeof globalThis.fetch> = [];

	const etagOf = (id: string): string => `"fp-${fps.get(id) ?? 0}"`;
	const bump = (id: string): void => {
		fps.set(id, ++seq);
	};

	const handler = async (input: unknown, init?: RequestInit): Promise<Response> => {
		const path = pfadVon(input);
		const method = (init?.method ?? 'GET').toUpperCase();
		const ifMatch = new Headers((init?.headers ?? {}) as HeadersInit).get('If-Match');
		const m = PRESET_RE.exec(path);
		const id = m ? decodeURIComponent(m[1]) : null;
		const eintrag: MitschnittEintrag = { method, path, ifMatch, status: 0, anfrage: undefined };
		mitschnitt.push(eintrag);
		const headers = new Headers({ 'Content-Type': 'application/json' });

		if (id === null || !daten.has(id)) {
			eintrag.status = id === null ? 200 : 404;
			return new Response(JSON.stringify(id === null ? [] : { error: 'not_found' }), {
				status: eintrag.status,
				headers
			});
		}
		if (method === 'GET') {
			eintrag.status = 200;
			headers.set('ETag', etagOf(id));
			return new Response(JSON.stringify(daten.get(id)), { status: 200, headers });
		}
		if (method === 'PUT') {
			let rumpf: unknown = undefined;
			if (typeof init?.body === 'string') {
				try {
					rumpf = JSON.parse(init.body);
				} catch {
					/* kein JSON */
				}
			}
			eintrag.anfrage = rumpf;
			if (ifMatch !== null && !ifMatchAllows(ifMatch, etagOf(id))) {
				eintrag.status = 412;
				return new Response(
					JSON.stringify({ error: 'precondition_failed', detail: 'Stand zwischenzeitlich geaendert' }),
					{ status: 412, headers }
				);
			}
			const neu = goMerge(daten.get(id)!, (rumpf as Record<string, unknown>) ?? {});
			daten.set(id, neu);
			bump(id);
			headers.set('ETag', etagOf(id));
			eintrag.status = 200;
			return new Response(JSON.stringify(neu), { status: 200, headers });
		}
		eintrag.status = 405;
		return new Response('{}', { status: 405, headers });
	};

	return {
		handler,
		mitschnitt,
		putRuempfe: () =>
			mitschnitt.filter((e) => e.method === 'PUT').map((e) => e.anfrage as Record<string, unknown>),
		stand: (id) => JSON.parse(JSON.stringify(daten.get(id))),
		etagOf,
		fremdSchreiben(id, teil) {
			daten.set(id, goMerge(daten.get(id)!, teil));
			bump(id);
		},
		install() {
			vorherige.push(globalThis.fetch);
			(globalThis as { fetch: unknown }).fetch = handler;
		},
		restore() {
			const f = vorherige.pop();
			if (f) (globalThis as { fetch: unknown }).fetch = f;
		}
	};
}

/** Ein Ortsvergleich, in dem JEDES Feld aller Reiter mit einem
 *  unterscheidbaren Wert belegt ist — nur so fällt ein Fremdfeld im Body auf. */
export function vollerVergleich(id: string): Record<string, unknown> {
	return {
		id,
		name: 'X',
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
		official_warnings: { enabled: true, sources: ['meteoalarm'] },
		radar_alert_enabled: false,
		send_telegram: true,
		send_sms: false,
		send_premium_sms: false,
		alert_channels: { email: true, telegram: true, sms: false, premium_sms: false },
		alert_channel_thresholds: { email: 'gering', telegram: 'hoch', sms: 'gering' },
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '07:00',
		morning_enabled: true,
		morning_time: '06:30:00',
		evening_enabled: false,
		evening_time: '18:00:00',
		end_date: '2026-12-01',
		hourly_enabled: true,
		outlook_enabled: true,
		day_window_start_hour: 5,
		day_window_end_hour: 18,
		corridors: [
			{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true },
			{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }
		],
		display_config: {
			region: 'Tirol',
			ideal_ranges: { wind_max_kmh: { min: 0, max: 40 }, snow_depth_cm: { min: 30, max: 200 } },
			active_metrics: ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c'],
			channel_active_metrics: {},
			metric_alert_levels: { wind_max_kmh: 'standard', snow_depth_cm: 'sensibel' },
			telegram_style: 'rich',
			hourly_metrics: ['wind_max_kmh', 'temp_max_c'],
			outlook_metrics: ['temp_max_c'],
			outlook_metric_formats: { temp_max_c: true }
		}
	};
}

/** Eigenfelder je Reiter laut Feld-Besitz-Tabelle
 *  (docs/specs/bugfix/compare_konfliktschutz_teilfelder.md, Abschnitt 2). */
export const EIGENFELDER = {
	alarme: {
		top: [
			'alert_channel_thresholds',
			'alert_channels',
			'alert_cooldown_minutes',
			'alert_quiet_from',
			'alert_quiet_to',
			'display_config',
			'official_warnings',
			'radar_alert_enabled'
		],
		display: ['metric_alert_levels', 'telegram_style']
	},
	versand: {
		top: [
			'end_date',
			'evening_enabled',
			'evening_time',
			'morning_enabled',
			'morning_time',
			'send_premium_sms',
			'send_sms',
			'send_telegram'
		],
		display: null
	},
	wertebereiche: {
		top: ['corridors', 'display_config'],
		display: ['active_metrics', 'ideal_ranges', 'metric_alert_levels']
	},
	wetterMetriken: {
		top: [
			'day_window_end_hour',
			'day_window_start_hour',
			'display_config',
			'hourly_enabled',
			'official_alerts_enabled',
			'outlook_enabled'
		],
		display: [
			'active_metrics',
			'channel_active_metrics',
			'hourly_metrics',
			'outlook_metric_formats',
			'outlook_metrics'
		]
	}
} as const;

export function schluessel(o: unknown): string[] {
	return Object.keys((o as Record<string, unknown>) ?? {}).sort();
}
