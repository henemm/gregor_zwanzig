// TDD RED — Issue #2682 (Epic #2345): Modell der geteilten Hub-Uebersicht.
// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
//   Entscheidungen 2/3/5/6/7, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9, AC-15
//
// Pruefling: shared/hub-uebersicht/hubUebersichtModell.ts (reine Funktionen,
// kein Netz, kein DOM). Wird JE TEST dynamisch importiert (`ladeModell()`),
// damit in RED jeder Fall mit eigener Meldung scheitert statt die ganze Datei
// mit EINEM Ladefehler.
//
// ── VERTRAG (hier festgelegt, Phase 6 baut danach) ──────────────────────────
//
//   export type KennzahlId = 'status' | 'naechster-versand' | 'briefings' | 'zuletzt-raus' | 'kanaele';
//   export interface Kennzahl {
//     id: KennzahlId;
//     label: string;            // 'Status' | 'Nächster Versand' | 'Briefings' | 'Zuletzt raus' | 'Kanäle'
//     kurz: string;             // Text mobil (2×2-Raster)
//     lang: string;             // Text Desktop (Leiste)
//     mobil: boolean;           // erscheint im mobilen 2×2-Raster (Briefings: false)
//     testid?: string;          // testid des Wert-Knotens Desktop (Vergleich: nur briefings/kanaele)
//     testidMobil?: string;     // testid des Wert-Knotens mobil (Vergleich: nur kanaele)
//     sprungziel: { tab: string; anchor?: 'versand' } | null;
//   }
//   export interface VersandKarte {
//     titelKurz: string; titelLang: string;              // Draft: 'Nicht geplant' / 'Noch nicht geplant'
//     beschreibungKurz: string; beschreibungLang: string;
//     testid: string;                                     // 'compare-hub-versand-edit' | 'hub-uebersicht-versand-edit'
//     sprungziel: { tab: 'wetter-metriken'; anchor: 'versand' };
//   }
//   export interface HubUebersichtModell {
//     kennzahlen: Kennzahl[];   // Reihenfolge: status, naechster-versand, briefings, zuletzt-raus, kanaele
//     versandKarte: VersandKarte;
//     testidPraefix: 'compare' | 'hub-uebersicht';
//     rasterTestid: string;     // mobiles 2×2-Raster: 'compare-detail-monitoring-mobile' | 'hub-uebersicht-monitoring-mobile'
//     stapelTestid: string;     // mobiler Pfeil-Zeilen-Stapel: 'compare-detail-summary-mobile' | 'hub-uebersicht-summary-mobile'
//     orteKarte?: { titel: string; namen: string[] };    // nur Vergleich
//   }
//
//   /** Stand der Versand-Historie — strukturell gleich dem Lader
//    *  (shared/briefingHistoryLader.svelte.ts), der Lader kann direkt uebergeben werden. */
//   export type LetzterVersandStand = {
//     zustand: 'laedt' | 'geladen' | 'fehler';
//     eintraege: BriefingHistoryEntry[];   // chronologisch wie vom Server (aelteste zuerst)
//   };
//
//   /** EINE Regel fuer „Zuletzt raus" (Entscheidung 3): neuester Eintrag mit
//    *  on_demand !== true, sonst null. Der Lader nutzt dieselbe Funktion. */
//   export function neuesterPlanmaessigerEintrag(e: BriefingHistoryEntry[]): BriefingHistoryEntry | null;
//
//   export function deriveRouteKennzahlen(
//     trip: Trip, status: TripStatus, briefing: NextBriefing | null | undefined,
//     letzterVersand: LetzterVersandStand
//   ): HubUebersichtModell;
//
//   export function deriveVergleichKennzahlen(
//     preset: ComparePreset, status: CompareStatus, briefing: NextBriefing | null | undefined,
//     aufgeloesteOrte: Array<{ rank: number; loc?: { id: string; name: string } }>   // Form von resolvedLocations in CompareTabs
//   ): HubUebersichtModell;
//
// Quellen, an denen die Erwartungen ausgerichtet sind (nicht erfunden):
//   formatLastSent / channelNamesLabel / presetBriefingTimesLabel (compare/subscriptionHelpers.ts),
//   formatNextBriefing (shared/versand-tab/nextBriefingText.ts), deriveTripStatus
//   (utils/tripStatus.ts), reportSlotAktiv (utils/reportSlotAktiv.ts), Status-Wortlaut
//   des Trip-Kopfs = TripStatusBadge.svelte (per SSR gerendert, nicht abgeschrieben).
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/hub-uebersicht/__tests__/hub_uebersicht_modell.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

process.env.TZ = 'Europe/Berlin';

const HIER = dirname(fileURLToPath(import.meta.url));
// __tests__ -> hub-uebersicht -> shared -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..', '..');
const COMPONENTS = resolve(HIER, '..', '..', '..');
const MODELL = join(HIER, '..', 'hubUebersichtModell.ts');
const basis = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);

const { render } = await import('svelte/server');
const { formatLastSent, channelNamesLabel, presetBriefingTimesLabel } = await import(
	pathToFileURL(join(COMPONENTS, 'compare', 'subscriptionHelpers.ts')).href
);
const { formatNextBriefing } = await import(
	pathToFileURL(join(COMPONENTS, 'shared', 'versand-tab', 'nextBriefingText.ts')).href
);
const { deriveTripStatus } = await import(pathToFileURL(join(FRONTEND, 'src', 'lib', 'utils', 'tripStatus.ts')).href);

type Modul = Record<string, any>;

async function ladeModell(): Promise<Modul> {
	assert.ok(
		existsSync(MODELL),
		'shared/hub-uebersicht/hubUebersichtModell.ts fehlt (RED) — Spec „Affected Files": reine Ableiter deriveRouteKennzahlen/deriveVergleichKennzahlen'
	);
	return (await import(pathToFileURL(MODELL).href)) as Modul;
}

function kennzahl(modell: any, id: string): any {
	assert.ok(Array.isArray(modell?.kennzahlen), 'Modell traegt kein Feld kennzahlen[]');
	const k = modell.kennzahlen.find((x: any) => x.id === id);
	assert.ok(k, `Kennzahl „${id}" fehlt; vorhanden: ${modell.kennzahlen.map((x: any) => x.id).join(', ')}`);
	return k;
}

// ── Fixtures ────────────────────────────────────────────────────────────────

const NB = (local_time: string) => ({
	at: `2026-10-22T${local_time}:00+02:00`,
	local_date: '2026-10-22',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
});

const GELADEN_LEER = { zustand: 'geladen', eintraege: [] };

/** Trip mit Kanal-Flags NUR in report_config — die flachen Felder tragen bewusst das
 *  GEGENTEIL (types.ts: report_config ist die einzige Wahrheit). */
function trip(rc: Record<string, unknown>, extra: Record<string, unknown> = {}) {
	const gegenteil = (k: string) => (k in rc ? !rc[k] : undefined);
	return {
		id: 't-2682',
		name: 'Testtrip',
		stages: [
			{ id: 's1', name: 'E1', date: '2099-07-01', waypoints: [] },
			{ id: 's2', name: 'E2', date: '2099-07-02', waypoints: [] }
		],
		report_config: { enabled: true, morning_time: '07:00:00', evening_time: '18:00:00', ...rc },
		send_email: gegenteil('send_email'),
		send_telegram: gegenteil('send_telegram'),
		send_sms: gegenteil('send_sms'),
		send_premium_sms: gegenteil('send_premium_sms'),
		display_config: {},
		...extra
	};
}

function preset(extra: Record<string, unknown> = {}) {
	return {
		id: 'cp-2682',
		name: 'Vergleich',
		location_ids: ['l1', 'l2', 'l3'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 18,
		empfaenger: [],
		forecast_hours: 48,
		created_at: '2026-10-01T00:00:00Z',
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: true,
		evening_time: '18:30:00',
		letzter_versand: '2026-10-28T10:00:00Z',
		send_telegram: true,
		send_premium_sms: true,
		...extra
	};
}

const ORTE3 = [
	{ rank: 1, loc: { id: 'l1', name: 'Alpha' } },
	{ rank: 2, loc: { id: 'l2', name: 'Beta' } },
	{ rank: 3, loc: { id: 'l3', name: 'Gamma' } }
];

const route = async (t: any, status = 'planned', nb: any = undefined, lv: any = GELADEN_LEER) =>
	(await ladeModell()).deriveRouteKennzahlen(t, status, nb, lv);
const vergleich = async (p: any, status = 'active', nb: any = undefined, orte: any = ORTE3) =>
	(await ladeModell()).deriveVergleichKennzahlen(p, status, nb, orte);

// ── Kanaele (AC-9, Entscheidung 7, ADR-0095) ────────────────────────────────

describe('AC-9: Kanal-Kennzahl des Trips folgt report_config.send_*', () => {
	test('send_premium_sms=true ⇒ „Premium-SMS" neben E-Mail (Desktop und mobil)', async () => {
		const k = kennzahl(await route(trip({ send_premium_sms: true })), 'kanaele');
		for (const text of [k.lang, k.kurz]) {
			assert.match(text, /Premium-SMS/, `Premium-SMS fehlt: ${text}`);
			assert.match(text, /E-?Mail/i, `E-Mail fehlt: ${text}`);
		}
	});

	test('alle vier Kanaele an ⇒ alle vier genannt', async () => {
		const k = kennzahl(
			await route(trip({ send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true })),
			'kanaele'
		);
		for (const name of [/E-?Mail/i, /Telegram/, /(^|[^-])SMS/, /Premium-SMS/]) assert.match(k.lang, name, k.lang);
	});

	test('send_email fehlt ⇒ E-Mail gilt als aktiv (send_email !== false)', async () => {
		const k = kennzahl(await route(trip({})), 'kanaele');
		assert.match(k.lang, /E-?Mail/i, k.lang);
	});

	test('AC-15: send_email=false, nur Telegram ⇒ kein E-Mail, Telegram genannt (Anzeige folgt der Eingabe)', async () => {
		const k = kennzahl(await route(trip({ send_email: false, send_telegram: true })), 'kanaele');
		assert.doesNotMatch(k.lang, /E-?Mail/i, `fest eingetragene E-Mail: ${k.lang}`);
		assert.match(k.lang, /Telegram/, k.lang);
		assert.doesNotMatch(k.lang, /Premium-SMS/, k.lang);
	});

	test('Vergleich: Kanal-Kennzahl wortgleich channelNamesLabel(preset) (verhaltensgleicher Umzug)', async () => {
		const p = preset();
		const k = kennzahl(await vergleich(p), 'kanaele');
		assert.equal(k.lang, channelNamesLabel(p));
		assert.equal(k.kurz, channelNamesLabel(p));
	});
});

// ── Umfang Desktop 5 / mobil 4 (Entscheidung 7) ─────────────────────────────

describe('Entscheidung 7: Desktop fuenf, mobil vier Kennzahlen — fuer beide Arten', () => {
	for (const art of ['route', 'vergleich'] as const) {
		test(`${art}: Reihenfolge und mobiler Umfang`, async () => {
			const m = art === 'route' ? await route(trip({})) : await vergleich(preset());
			assert.deepEqual(
				m.kennzahlen.map((k: any) => k.id),
				['status', 'naechster-versand', 'briefings', 'zuletzt-raus', 'kanaele']
			);
			assert.deepEqual(
				m.kennzahlen.map((k: any) => k.label),
				['Status', 'Nächster Versand', 'Briefings', 'Zuletzt raus', 'Kanäle']
			);
			assert.deepEqual(
				m.kennzahlen.filter((k: any) => k.mobil).map((k: any) => k.id),
				['status', 'naechster-versand', 'zuletzt-raus', 'kanaele']
			);
		});
	}
});

// ── Zuletzt raus (AC-6, AC-7, Entscheidung 3/6) ─────────────────────────────

const PLANMAESSIG_28 = { sent_at: '2026-10-28T05:00:00Z', kind: 'morning', channels: ['email'], on_demand: false };
const VON_HAND_30 = { sent_at: '2026-10-30T10:00:00Z', kind: 'morning', channels: ['email'], on_demand: true };

describe('AC-6: „Zuletzt raus" = neuester PLANMAESSIGER Log-Eintrag (on_demand !== true)', () => {
	test('planmaessig 28.10.2026 + spaeter von Hand 30.10.2026 ⇒ „28.10.2026"', async () => {
		const k = kennzahl(
			await route(trip({}), 'active', undefined, { zustand: 'geladen', eintraege: [PLANMAESSIG_28, VON_HAND_30] }),
			'zuletzt-raus'
		);
		assert.equal(k.lang, '28.10.2026', `on_demand-Eintrag zaehlt als „Zuletzt raus": ${k.lang}`);
		assert.equal(k.kurz, '28.10.2026');
		assert.equal(k.lang, formatLastSent(PLANMAESSIG_28.sent_at), 'Format wie der Vergleich (formatLastSent)');
	});

	test('zwei planmaessige Eintraege ⇒ der neueste (letzter im chronologischen Log)', async () => {
		const p29 = { ...PLANMAESSIG_28, sent_at: '2026-10-29T16:00:00Z', kind: 'evening' };
		const k = kennzahl(
			await route(trip({}), 'active', undefined, { zustand: 'geladen', eintraege: [PLANMAESSIG_28, p29] }),
			'zuletzt-raus'
		);
		assert.equal(k.lang, '29.10.2026');
	});

	test('on_demand fehlt im Eintrag ⇒ zaehlt als planmaessig (!== true)', async () => {
		const { on_demand: _weg, ...ohneFlag } = PLANMAESSIG_28;
		const k = kennzahl(
			await route(trip({}), 'active', undefined, { zustand: 'geladen', eintraege: [ohneFlag] }),
			'zuletzt-raus'
		);
		assert.equal(k.lang, '28.10.2026');
	});

	test('neuesterPlanmaessigerEintrag: EINE Regel, vom Lader mitbenutzt', async () => {
		const { neuesterPlanmaessigerEintrag } = await ladeModell();
		assert.equal(typeof neuesterPlanmaessigerEintrag, 'function', 'neuesterPlanmaessigerEintrag fehlt');
		assert.equal(neuesterPlanmaessigerEintrag([PLANMAESSIG_28, VON_HAND_30])?.sent_at, PLANMAESSIG_28.sent_at);
		assert.equal(neuesterPlanmaessigerEintrag([VON_HAND_30]), null);
		assert.equal(neuesterPlanmaessigerEintrag([]), null);
	});
});

describe('AC-7: Lade-, Leer- und Fehlerzustand — nie ein erfundenes Datum', () => {
	test('noch nicht geladen ⇒ „—"', async () => {
		const k = kennzahl(await route(trip({}), 'active', undefined, { zustand: 'laedt', eintraege: [] }), 'zuletzt-raus');
		assert.equal(k.lang, '—');
		assert.equal(k.kurz, '—');
	});

	test('geladen, leer ⇒ „Noch kein Versand" (Wortlaut formatLastSent)', async () => {
		const k = kennzahl(await route(trip({}), 'active', undefined, GELADEN_LEER), 'zuletzt-raus');
		assert.equal(k.lang, formatLastSent(undefined));
		assert.equal(k.lang, 'Noch kein Versand');
	});

	test('geladen, nur Eintraege von Hand ⇒ „Noch kein Versand"', async () => {
		const k = kennzahl(
			await route(trip({}), 'active', undefined, { zustand: 'geladen', eintraege: [VON_HAND_30] }),
			'zuletzt-raus'
		);
		assert.equal(k.lang, 'Noch kein Versand');
	});

	test('Ladefehler ⇒ „—" (auch wenn veraltete Eintraege mitkommen)', async () => {
		const k = kennzahl(
			await route(trip({}), 'active', undefined, { zustand: 'fehler', eintraege: [PLANMAESSIG_28] }),
			'zuletzt-raus'
		);
		assert.equal(k.lang, '—');
	});

	test('Vergleich: „Zuletzt raus" aus preset.letzter_versand (formatLastSent)', async () => {
		assert.equal(kennzahl(await vergleich(preset()), 'zuletzt-raus').lang, '28.10.2026');
		assert.equal(
			kennzahl(await vergleich(preset({ letzter_versand: undefined })), 'zuletzt-raus').lang,
			'Noch kein Versand'
		);
	});
});

// ── Naechster Versand / Briefings (Entscheidung 7) ──────────────────────────

describe('Naechster Versand und Briefings-Zeiten aus echten Quellen', () => {
	test('route: Naechster Versand = formatNextBriefing(wert, "route"); nicht geladen ⇒ „—"', async () => {
		const nb = NB('07:00');
		assert.equal(kennzahl(await route(trip({}), 'planned', nb), 'naechster-versand').lang, formatNextBriefing(nb, 'route'));
		assert.equal(kennzahl(await route(trip({}), 'planned', nb), 'naechster-versand').lang, 'Do 07:00 (CEST)');
		assert.equal(kennzahl(await route(trip({}), 'planned', undefined), 'naechster-versand').lang, '—');
	});

	test('vergleich: Naechster Versand = formatNextBriefing(wert, "vergleich")', async () => {
		const nb = { at: null, reason: 'ended' };
		assert.equal(kennzahl(await vergleich(preset(), 'active', nb), 'naechster-versand').lang, 'Ortsvergleich beendet');
	});

	test('route: Briefings folgen report_config + reportSlotAktiv (Abend aus ⇒ nicht genannt)', async () => {
		const beide = kennzahl(await route(trip({ morning_enabled: true, evening_enabled: true })), 'briefings').lang;
		assert.match(beide, /07:00/, beide);
		assert.match(beide, /18:00/, beide);
		const nurMorgen = kennzahl(await route(trip({ morning_enabled: true, evening_enabled: false })), 'briefings').lang;
		assert.match(nurMorgen, /07:00/, nurMorgen);
		assert.doesNotMatch(nurMorgen, /18:00/, `abgeschalteter Abend-Slot genannt: ${nurMorgen}`);
		const andereZeit = kennzahl(
			await route(trip({ morning_time: '09:00:00', morning_enabled: true, evening_enabled: false })),
			'briefings'
		).lang;
		assert.match(andereZeit, /09:00/, `AC-15: Zeit folgt nicht der Eingabe: ${andereZeit}`);
		const keiner = kennzahl(await route(trip({ morning_enabled: false, evening_enabled: false })), 'briefings').lang;
		assert.equal(keiner, '—', `beide Slots aus ⇒ „—" wie im Vergleich (presetBriefingTimesLabel): ${keiner}`);
		const gesamtAus = kennzahl(await route(trip({ enabled: false })), 'briefings').lang;
		assert.equal(gesamtAus, '—', `Gesamtschalter aus (reportSlotAktiv) ⇒ „—": ${gesamtAus}`);
	});

	test('vergleich: Briefings = presetBriefingTimesLabel(preset), testid compare-detail-stat-briefings', async () => {
		const p = preset();
		const k = kennzahl(await vergleich(p), 'briefings');
		assert.equal(k.lang, presetBriefingTimesLabel(p));
		assert.equal(k.testid, 'compare-detail-stat-briefings');
		assert.equal(k.mobil, false);
	});
});

// ── Status (AC-3, AC-5, Entscheidung 2) ─────────────────────────────────────

describe('AC-3: Vergleich behaelt Status-Kurz-/Langform', () => {
	test('active ⇒ kurz „Läuft autom.", lang „Läuft automatisch"', async () => {
		const k = kennzahl(await vergleich(preset(), 'active'), 'status');
		assert.equal(k.kurz, 'Läuft autom.');
		assert.equal(k.lang, 'Läuft automatisch');
	});

	test('draft ⇒ kurz „Entwurf", lang „Entwurf · nicht aktiv"; paused ⇒ „Pausiert"', async () => {
		const d = kennzahl(await vergleich(preset(), 'draft'), 'status');
		assert.equal(d.kurz, 'Entwurf');
		assert.equal(d.lang, 'Entwurf · nicht aktiv');
		const p = kennzahl(await vergleich(preset(), 'paused'), 'status');
		assert.equal(p.kurz, 'Pausiert');
		assert.equal(p.lang, 'Pausiert');
	});
});

describe('AC-5: Trip-Status wortgleich zum Status-Badge im Trip-Kopf', () => {
	const JETZT = new Date('2026-11-01T12:00:00Z');
	const FAELLE: Record<string, Record<string, unknown>> = {
		draft: { stages: [{ id: 's1', name: 'E1', waypoints: [] }] },
		planned: { stages: [{ id: 's1', name: 'E1', date: '2099-07-01', waypoints: [] }] },
		active: { stages: [{ id: 's1', name: 'E1', date: '2026-10-30', waypoints: [] }, { id: 's2', name: 'E2', date: '2026-11-05', waypoints: [] }] },
		paused: { paused_at: '2026-10-31T08:00:00Z' },
		finished: { stages: [{ id: 's1', name: 'E1', date: '2026-01-01', waypoints: [] }] },
		archived: { archived_at: '2026-10-31T08:00:00Z' }
	};

	for (const [erwartet, extra] of Object.entries(FAELLE)) {
		test(`${erwartet}: Kennzahl-Text = gerenderter TripStatusBadge-Text, Kurz = Lang`, async () => {
			const t = trip({}, extra);
			const status = deriveTripStatus(t, JETZT);
			assert.equal(status, erwartet, 'Messaufbau: deriveTripStatus');
			const Badge = (await import(pathToFileURL(join(COMPONENTS, 'trip-detail', 'TripStatusBadge.svelte')).href)).default;
			const badgeText = render(Badge, { props: { trip: t, now: JETZT } })
				.body.replace(/<!--[\s\S]*?-->/g, '')
				.replace(/<[^>]*>/g, ' ')
				.replace(/\s+/g, ' ')
				.trim();
			const k = kennzahl(await route(t, status), 'status');
			assert.equal(k.lang, badgeText, 'zweites Status-Vokabular neben dem Kopf-Badge');
			assert.equal(k.kurz, k.lang, 'Trip: Kurz- und Langform gleich (Entscheidung 2)');
		});
	}
});

// ── Versand-Karte (AC-8) ────────────────────────────────────────────────────

describe('AC-8: Versand-Karte mit Sprung in Wetter-Metriken › Versand', () => {
	test('route Entwurf ⇒ „Noch nicht geplant"; testid hub-uebersicht-versand-edit', async () => {
		const m = await route(trip({}, { stages: [{ id: 's1', name: 'E1', waypoints: [] }] }), 'draft');
		assert.equal(m.versandKarte?.titelLang, 'Noch nicht geplant');
		assert.equal(m.versandKarte.testid, 'hub-uebersicht-versand-edit');
		assert.deepEqual(m.versandKarte.sprungziel, { tab: 'wetter-metriken', anchor: 'versand' });
	});

	test('route geplant ⇒ Karte nennt die Briefing-Zeiten, nicht „Noch nicht geplant"', async () => {
		const m = await route(trip({ morning_enabled: true, evening_enabled: false }), 'planned');
		assert.notEqual(m.versandKarte.titelLang, 'Noch nicht geplant');
		assert.match(m.versandKarte.titelLang, /07:00/, m.versandKarte.titelLang);
	});

	test('vergleich Entwurf ⇒ lang „Noch nicht geplant", kurz „Nicht geplant"; testid compare-hub-versand-edit', async () => {
		const m = await vergleich(preset(), 'draft');
		assert.equal(m.versandKarte.titelLang, 'Noch nicht geplant');
		assert.equal(m.versandKarte.titelKurz, 'Nicht geplant');
		assert.equal(m.versandKarte.testid, 'compare-hub-versand-edit');
		assert.deepEqual(m.versandKarte.sprungziel, { tab: 'wetter-metriken', anchor: 'versand' });
	});

	test('vergleich aktiv ⇒ Titel = presetBriefingTimesLabel', async () => {
		const p = preset();
		assert.equal((await vergleich(p, 'active')).versandKarte.titelLang, presetBriefingTimesLabel(p));
	});
});

// ── Orte-Zahl (AC-4, Entscheidung 5) ────────────────────────────────────────

describe('AC-4: Orte-Karte nennt die Zahl der AUFLOESBAREN Orte', () => {
	test('drei Kennungen, zwei aufloesbar ⇒ „2 Kandidaten", Namen nur der aufloesbaren', async () => {
		const p = preset({ location_ids: ['l1', 'geloescht', 'l3'] });
		const orte = [
			{ rank: 1, loc: { id: 'l1', name: 'Alpha' } },
			{ rank: 2, loc: undefined },
			{ rank: 3, loc: { id: 'l3', name: 'Gamma' } }
		];
		const m = await vergleich(p, 'active', undefined, orte);
		assert.equal(m.orteKarte?.titel, '2 Kandidaten', `gespeicherte Kennungszahl statt aufloesbarer: ${m.orteKarte?.titel}`);
		assert.deepEqual(m.orteKarte.namen, ['Alpha', 'Gamma']);
	});

	test('alle aufloesbar ⇒ Zahl wie bisher', async () => {
		const m = await vergleich(preset(), 'active', undefined, ORTE3);
		assert.equal(m.orteKarte?.titel, '3 Kandidaten');
	});
});

// ── testid-Praefix (Stabile testids) ────────────────────────────────────────

describe('Stabile testids: Praefix kommt aus dem Modell', () => {
	test('vergleich behaelt compare-*, route bekommt hub-uebersicht-*', async () => {
		const v = await vergleich(preset());
		const r = await route(trip({}));
		assert.equal(v.testidPraefix, 'compare');
		assert.equal(r.testidPraefix, 'hub-uebersicht');
		assert.equal(kennzahl(v, 'kanaele').testid, 'compare-detail-stat-kanaele');
		assert.equal(kennzahl(v, 'kanaele').testidMobil, 'compare-detail-stat-kanaele-mobile');
		assert.equal(kennzahl(r, 'kanaele').testid, 'hub-uebersicht-stat-kanaele');
		assert.equal(kennzahl(r, 'zuletzt-raus').testid, 'hub-uebersicht-stat-zuletzt-raus');
		assert.equal(kennzahl(r, 'briefings').testid, 'hub-uebersicht-stat-briefings');
	});

	test('mobile Container-testids je Art (E2E HT-10 / s8c laufen per HUB_KINDS)', async () => {
		const v = await vergleich(preset());
		const r = await route(trip({}));
		assert.equal(v.rasterTestid, 'compare-detail-monitoring-mobile');
		assert.equal(v.stapelTestid, 'compare-detail-summary-mobile');
		assert.equal(r.rasterTestid, 'hub-uebersicht-monitoring-mobile');
		assert.equal(r.stapelTestid, 'hub-uebersicht-summary-mobile');
	});

	test('route: kein testid traegt den Vergleichs-Praefix (keine Kollision in E2E-Zaehlungen)', async () => {
		const r = await route(trip({}));
		const ids = [...r.kennzahlen.flatMap((k: any) => [k.testid, k.testidMobil]), r.versandKarte.testid].filter(Boolean);
		assert.ok(ids.length >= 3, `zu wenige testids: ${ids.join(', ')}`);
		for (const id of ids) assert.ok(id.startsWith('hub-uebersicht-'), `fremder Praefix: ${id}`);
	});
});
