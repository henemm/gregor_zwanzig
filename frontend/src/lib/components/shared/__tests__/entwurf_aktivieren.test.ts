// TDD RED — Issue #3443 (S5d aus #2797, Epic #2791): Entwurf aktivieren über Knopf im Kopf und Kebab.
// Spec: docs/specs/modules/feat_3443_entwurf_aktivieren.md — AC-3, AC-4, AC-5, AC-8, AC-9, AC-11 (Kern-Schicht).
//
// VERTRAG für den Developer — frontend/src/lib/components/shared/entwurfAktivieren.ts (reine Funktionen,
// node:testbar, ohne DOM/Netz; Texte nur über den Katalog in der AKTUELLEN Sprache per `tr()`, wie
// kebabBestaetigung.ts; EIN Code für Trip und Orts-Vergleich, kein Zweig nach `context` außer Datentabellen):
//
//   export type AktivierungsTeil = 'etappen_datum' | 'name' | 'orte';
//   export function fehltFuerAktivierung(kind: SubscriptionKind, objekt: Trip | ComparePreset): AktivierungsTeil[];
//       // 'trip'      → ['etappen_datum'], wenn keine Etappe ein Datum trägt (Regel deriveTripStatus), sonst []
//       // 'vergleich' → 'name', wenn !p.name (genau die Regel von deriveStatusFromPreset),
//       //               'orte', wenn location_ids leer; Reihenfolge immer ['name', 'orte']
//   export function hinweisFuer(teile: readonly AktivierungsTeil[]): string | null;   // null bei leerer Liste
//       // ganze Sätze aus dem Katalog (aktionen.aktivieren.hinweis_*), unabhängig von der Reihenfolge der Teile
//   export function zielFuer(kind: SubscriptionKind, teile: readonly AktivierungsTeil[]): string | null;
//       // Trip mit etappen_datum → '?tab=etappen'; Vergleich mit 'orte' (auch mit 'name') → '?tab=orte';
//       // nur 'name' bzw. leer → null (keine Navigation, der Name wird im Kopf bearbeitet)
//   export function warAktivierung(vorher: SubscriptionLifecycle | undefined, nachher: SubscriptionLifecycle): boolean;
//       // genau draft → active; undefined (erstes Lesen) nie
//   export function aktiviertText(nb: NextBriefing | null | undefined, context: 'route' | 'vergleich'): string;
//       // nb.at != null und formatNextBriefing(nb, context) !== '—' → aktionen.aktivieren.erfolg_mit_zeit {wann}
//       // sonst (null, undefined, at == null, kaputtes Objekt) → aktionen.aktivieren.erfolg — nie erfundene Zeit
//
// Neue Katalogschlüssel (aktionen.json, DE und EN, ADR-0104):
//   aktionen.aktivieren.hinweis_etappen_datum  „Zum Aktivieren fehlt noch: Datum der Etappen.“
//   aktionen.aktivieren.hinweis_orte           „Zum Aktivieren fehlen noch: Orte.“
//   aktionen.aktivieren.hinweis_name           „Zum Aktivieren fehlt noch: ein Name.“
//   aktionen.aktivieren.hinweis_name_orte      „Zum Aktivieren fehlen noch: Name und Orte.“
//   aktionen.aktivieren.erfolg                 „Aktiviert.“ / „Activated.“
//   aktionen.aktivieren.erfolg_mit_zeit        „Aktiviert. Das erste Briefing kommt {wann}.“ / „Activated. The first briefing arrives {wann}.“
// EN-Wortlaut der vier Hinweise wählt der Developer (englisch, ohne Umlaute, je Fall verschieden).
//
// Objekte sind ECHTE Trip-/ComparePreset-Formen (wie aus GET /api/trips/{id} bzw. /api/compare/presets/{id}),
// die Konsistenz wird gegen die ECHTEN Ableitungen deriveTripStatus/deriveStatusFromPreset geprüft.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/entwurf_aktivieren.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, trFor } from '../../../i18n/index.ts';
import { de } from '../../../i18n/messages/de/index.ts';
import { en } from '../../../i18n/messages/en/index.ts';
import { deriveTripStatus } from '../../../utils/tripStatus.ts';
import { deriveStatusFromPreset } from '../../compare/subscriptionHelpers.ts';
import { resolveTab } from '../subscriptionTabs.ts';
import { formatNextBriefing } from '../versand-tab/nextBriefingText.ts';
import type { ComparePreset, Trip } from '../../../types.ts';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

afterEach(() => locale.set('de'));

async function modul(): Promise<Json> {
	try {
		return await import('../entwurfAktivieren.ts');
	} catch (e) {
		assert.fail(`TDD RED: shared/entwurfAktivieren.ts fehlt oder lädt nicht (${(e as Error).message})`);
	}
}

const JETZT = new Date('2026-10-17T12:00:00Z');

// ── Echte Objekte ─────────────────────────────────────────────────────────────────────
const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });
const etappe = (id: string, date: string) => ({ id, name: `Etappe ${id}`, date, waypoints: [wp(`${id}a`, 42.0), wp(`${id}b`, 42.05)] });
const trip = (extra: Partial<Trip> = {}): Trip =>
	({
		id: 't-3443',
		name: 'GR20 Nord',
		region: 'Korsika',
		stages: [etappe('s1', '2026-10-20'), etappe('s2', '2026-10-21')],
		...extra
	}) as Trip;
const preset = (extra: Partial<ComparePreset> = {}): ComparePreset =>
	({
		id: 'c-3443',
		name: 'Skitouren Tirol',
		location_ids: ['l-a', 'l-b'],
		schedule: 'daily',
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 18,
		empfaenger: [],
		forecast_hours: 48,
		created_at: '2026-10-01T08:00:00Z',
		...extra
	}) as ComparePreset;

const TRIPS: Record<string, Trip> = {
	ohne_datum: trip({ stages: [etappe('s1', ''), etappe('s2', '')] }),
	ohne_etappen: trip({ stages: [] }),
	mit_datum: trip(),
	teilweise_datiert: trip({ stages: [etappe('s1', ''), etappe('s2', '2026-10-21')] }),
	vergangen: trip({ stages: [etappe('s1', '2026-05-01')] })
};
const PRESETS: Record<string, ComparePreset> = {
	vollstaendig: preset(),
	ohne_orte: preset({ location_ids: [] }),
	ohne_name: preset({ name: '' }),
	ohne_beides: preset({ name: '', location_ids: [] }),
	pausiert: preset({ schedule: 'manual', previous_schedule: 'daily', paused_at: '2026-10-10T08:00:00Z' })
};

// ═══ fehltFuerAktivierung ═══════════════════════════════════════════════════════════

describe('AC-3: Trip — was fehlt (Regel deriveTripStatus, unverändert)', () => {
	test('ohne Datum an den Etappen bzw. ohne Etappen ⇒ [etappen_datum]', async () => {
		const m = await modul();
		assert.deepEqual(m.fehltFuerAktivierung('trip', TRIPS.ohne_datum), ['etappen_datum']);
		assert.deepEqual(m.fehltFuerAktivierung('trip', TRIPS.ohne_etappen), ['etappen_datum']);
	});
	test('mindestens eine datierte Etappe ⇒ nichts fehlt (auch teilweise datiert, auch vergangen)', async () => {
		const m = await modul();
		for (const k of ['mit_datum', 'teilweise_datiert', 'vergangen'])
			assert.deepEqual(m.fehltFuerAktivierung('trip', TRIPS[k]), [], k);
	});
});

describe('AC-4/AC-5: Orts-Vergleich — was fehlt (Regel deriveStatusFromPreset, unverändert)', () => {
	test('ohne Orte ⇒ [orte]; ohne Namen ⇒ [name]; beides ⇒ [name, orte]; vollständig/pausiert ⇒ []', async () => {
		const m = await modul();
		assert.deepEqual(m.fehltFuerAktivierung('vergleich', PRESETS.ohne_orte), ['orte']);
		assert.deepEqual(m.fehltFuerAktivierung('vergleich', PRESETS.ohne_name), ['name']);
		assert.deepEqual(m.fehltFuerAktivierung('vergleich', PRESETS.ohne_beides), ['name', 'orte']);
		assert.deepEqual(m.fehltFuerAktivierung('vergleich', PRESETS.vollstaendig), []);
		assert.deepEqual(m.fehltFuerAktivierung('vergleich', PRESETS.pausiert), [], 'pausiert ist kein Entwurf');
	});
});

describe('Konsistenz mit den bestehenden Ableitungen: Entwurf ⇔ Liste nicht leer', () => {
	test('Trip (nicht archiviert, nicht pausiert): deriveTripStatus === draft ⇔ fehlt nicht leer', async () => {
		const m = await modul();
		for (const [k, t] of Object.entries(TRIPS))
			assert.equal(m.fehltFuerAktivierung('trip', t).length > 0, deriveTripStatus(t, JETZT) === 'draft', k);
	});
	test('Orts-Vergleich: deriveStatusFromPreset === draft ⇔ fehlt nicht leer', async () => {
		const m = await modul();
		for (const [k, p] of Object.entries(PRESETS))
			assert.equal(m.fehltFuerAktivierung('vergleich', p).length > 0, deriveStatusFromPreset(p) === 'draft', k);
	});
	test('das Modell ändert die Objekte nicht (rein)', async () => {
		const m = await modul();
		const t = structuredClone(TRIPS.ohne_datum);
		const p = structuredClone(PRESETS.ohne_beides);
		m.fehltFuerAktivierung('trip', t);
		m.fehltFuerAktivierung('vergleich', p);
		assert.deepEqual(t, TRIPS.ohne_datum);
		assert.deepEqual(p, PRESETS.ohne_beides);
	});
});

// ═══ hinweisFuer ════════════════════════════════════════════════════════════════════

const HINWEIS_DE: Array<[string[], string, string]> = [
	[['etappen_datum'], 'Zum Aktivieren fehlt noch: Datum der Etappen.', 'aktionen.aktivieren.hinweis_etappen_datum'],
	[['orte'], 'Zum Aktivieren fehlen noch: Orte.', 'aktionen.aktivieren.hinweis_orte'],
	[['name'], 'Zum Aktivieren fehlt noch: ein Name.', 'aktionen.aktivieren.hinweis_name'],
	[['name', 'orte'], 'Zum Aktivieren fehlen noch: Name und Orte.', 'aktionen.aktivieren.hinweis_name_orte']
];

describe('AC-3/AC-4/AC-5: Hinweistext je Fall (ganze Sätze aus dem Katalog)', () => {
	for (const [teile, soll] of HINWEIS_DE) {
		test(`DE ${JSON.stringify(teile)} ⇒ „${soll}“`, async () => {
			const m = await modul();
			assert.equal(m.hinweisFuer(teile), soll);
		});
	}
	test('Reihenfolge der Teile ist egal: [orte, name] ⇒ „… Name und Orte.“', async () => {
		const m = await modul();
		assert.equal(m.hinweisFuer(['orte', 'name']), 'Zum Aktivieren fehlen noch: Name und Orte.');
	});
	test('nichts fehlt ⇒ kein Hinweis (null)', async () => {
		const m = await modul();
		assert.equal(m.hinweisFuer([]), null);
	});
	test('EN: Text kommt aus dem Katalog in der aktuellen Sprache, englisch und je Fall verschieden', async () => {
		const m = await modul();
		locale.set('en');
		const texte = HINWEIS_DE.map(([teile, , key]) => {
			const t = m.hinweisFuer(teile);
			assert.equal(t, trFor('en', key as never), `EN ${JSON.stringify(teile)} nicht aus ${key}`);
			assert.doesNotMatch(t, /[äöüßÄÖÜ]|Zum Aktivieren|fehlt|fehlen/, t);
			return t;
		});
		assert.equal(new Set(texte).size, texte.length, `EN-Hinweise nicht je Fall verschieden: ${JSON.stringify(texte)}`);
	});
	test('Ende-zu-Ende über das Modell: Objekt → Teile → Text (DE und EN gleich gebaut)', async () => {
		const m = await modul();
		assert.equal(m.hinweisFuer(m.fehltFuerAktivierung('trip', TRIPS.ohne_datum)), 'Zum Aktivieren fehlt noch: Datum der Etappen.');
		assert.equal(m.hinweisFuer(m.fehltFuerAktivierung('vergleich', PRESETS.ohne_orte)), 'Zum Aktivieren fehlen noch: Orte.');
		assert.equal(m.hinweisFuer(m.fehltFuerAktivierung('vergleich', PRESETS.ohne_name)), 'Zum Aktivieren fehlt noch: ein Name.');
		assert.equal(m.hinweisFuer(m.fehltFuerAktivierung('vergleich', PRESETS.ohne_beides)), 'Zum Aktivieren fehlen noch: Name und Orte.');
		assert.equal(m.hinweisFuer(m.fehltFuerAktivierung('vergleich', PRESETS.vollstaendig)), null);
		locale.set('en');
		assert.equal(m.hinweisFuer(m.fehltFuerAktivierung('vergleich', PRESETS.ohne_orte)), trFor('en', 'aktionen.aktivieren.hinweis_orte' as never));
	});
});

// ═══ zielFuer ═══════════════════════════════════════════════════════════════════════

describe('AC-3/AC-4/AC-5: Ziel der Navigation', () => {
	test('Trip ohne Datum ⇒ ?tab=etappen', async () => {
		const m = await modul();
		assert.equal(m.zielFuer('trip', ['etappen_datum']), '?tab=etappen');
	});
	test('Vergleich ohne Orte ⇒ ?tab=orte (auch wenn zusätzlich der Name fehlt)', async () => {
		const m = await modul();
		assert.equal(m.zielFuer('vergleich', ['orte']), '?tab=orte');
		assert.equal(m.zielFuer('vergleich', ['name', 'orte']), '?tab=orte');
	});
	test('nur der Name fehlt ⇒ keine Navigation (null); nichts fehlt ⇒ null', async () => {
		const m = await modul();
		assert.equal(m.zielFuer('vergleich', ['name']), null);
		assert.equal(m.zielFuer('vergleich', []), null);
		assert.equal(m.zielFuer('trip', []), null);
	});
	test('die Reiter-Kennungen sind die des Hubs (resolveTab erkennt sie ohne Umleitung)', async () => {
		const m = await modul();
		for (const [kind, teile] of [['trip', ['etappen_datum']], ['vergleich', ['orte']]] as const) {
			const ziel = m.zielFuer(kind, teile) as string;
			const tab = new URLSearchParams(ziel.replace(/^\?/, '')).get('tab');
			const r = resolveTab(kind, tab);
			assert.deepEqual([r.tab, r.known, r.legacy], [tab, true, false], `${kind}: ${ziel} ist keine aktuelle Reiter-Kennung`);
		}
	});
});

// ═══ warAktivierung ═════════════════════════════════════════════════════════════════

describe('AC-9: warAktivierung nur für draft → active', () => {
	const ZUSTAENDE = ['draft', 'active', 'paused', 'archived'] as const;
	test('alle Zustandspaare (inkl. erstes Lesen = undefined)', async () => {
		const m = await modul();
		for (const vorher of [undefined, ...ZUSTAENDE])
			for (const nachher of ZUSTAENDE)
				assert.equal(m.warAktivierung(vorher, nachher), vorher === 'draft' && nachher === 'active', `${vorher} → ${nachher}`);
	});
});

// ═══ aktiviertText ══════════════════════════════════════════════════════════════════

const NB = (extra: Record<string, unknown> = {}) => ({
	at: '2026-10-22T07:00:00+02:00',
	local_date: '2026-10-22',
	local_time: '07:00',
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning',
	...extra
});

describe('AC-7: „Aktiviert. Das erste Briefing kommt {wann}.“ mit dem Termin der Zustellung', () => {
	test('DE Trip: Wortlaut mit Wochentag, Datum, Uhrzeit, Zonenkürzel (= formatNextBriefing)', async () => {
		const m = await modul();
		assert.equal(m.aktiviertText(NB(), 'route'), 'Aktiviert. Das erste Briefing kommt Do 22.10. 07:00 (CEST).');
		assert.equal(m.aktiviertText(NB(), 'route'), `Aktiviert. Das erste Briefing kommt ${formatNextBriefing(NB() as never, 'route')}.`);
	});
	test('DE Vergleich: anderer Termin ⇒ anderer Text (Zeit kommt aus der Quelle)', async () => {
		const m = await modul();
		const nb = NB({ at: '2026-10-23T18:30:00+02:00', local_date: '2026-10-23', local_time: '18:30', slot: 'evening' });
		assert.equal(m.aktiviertText(nb, 'vergleich'), `Aktiviert. Das erste Briefing kommt ${formatNextBriefing(nb as never, 'vergleich')}.`);
		assert.match(m.aktiviertText(nb, 'vergleich'), /Fr 23\.10\. 18:30 \(CEST\)\.$/);
	});
	test('EN: „Activated. The first briefing arrives {wann}.“ mit dem EN-Format', async () => {
		const m = await modul();
		locale.set('en');
		assert.equal(m.aktiviertText(NB(), 'route'), `Activated. The first briefing arrives ${formatNextBriefing(NB() as never, 'route')}.`);
		assert.doesNotMatch(m.aktiviertText(NB(), 'route'), /Aktiviert|kommt|Do /);
	});
});

describe('AC-8: ohne Termin nur „Aktiviert.“ — nie eine erfundene Uhrzeit', () => {
	const OHNE: Array<[string, unknown]> = [
		['null', null],
		['undefined', undefined],
		['at null, reason none', { at: null, reason: 'none' }],
		['at null, reason manual', { at: null, reason: 'manual' }],
		['kaputtes Objekt (kein local_date)', { at: '2026-10-22T07:00:00+02:00' }],
		['kaputtes Datum', NB({ local_date: '2026-13-99' })],
		['kaputte Uhrzeit', NB({ local_time: '7 Uhr' })],
		['kein Objekt', 'kaputt']
	];
	for (const [was, nb] of OHNE) {
		test(`${was} ⇒ DE „Aktiviert.“, EN „Activated.“`, async () => {
			const m = await modul();
			assert.equal(m.aktiviertText(nb, 'route'), 'Aktiviert.');
			assert.equal(m.aktiviertText(nb, 'vergleich'), 'Aktiviert.');
			locale.set('en');
			assert.equal(m.aktiviertText(nb, 'route'), 'Activated.');
		});
	}
});

// ═══ Katalog (AC-11) ═════════════════════════════════════════════════════════════════

describe('AC-11: Katalog aktionen.aktivieren.* in DE und EN', () => {
	const K = (x: Record<string, string>) => Object.keys(x).filter((k) => k.startsWith('aktionen.aktivieren.')).sort();
	test('Schlüsselmengen gleich, genau die sechs neuen Schlüssel, Platzhalter gleich, nicht leer', () => {
		const d = K(de as Record<string, string>);
		const e = K(en as Record<string, string>);
		assert.deepEqual(d, [
			'aktionen.aktivieren.erfolg',
			'aktionen.aktivieren.erfolg_mit_zeit',
			'aktionen.aktivieren.hinweis_etappen_datum',
			'aktionen.aktivieren.hinweis_name',
			'aktionen.aktivieren.hinweis_name_orte',
			'aktionen.aktivieren.hinweis_orte'
		]);
		assert.deepEqual(e, d, 'Schlüsselmengen aktionen.aktivieren.* in de/en verschieden');
		const ph = (s: string) => [...s.matchAll(/\{([a-z0-9_]+)\}/g)].map((x) => x[1]).sort();
		for (const k of d) {
			const dv = (de as Record<string, string>)[k];
			const ev = (en as Record<string, string>)[k];
			assert.ok(dv?.trim() && ev?.trim(), `${k}: leer`);
			assert.deepEqual(ph(ev), ph(dv), `${k}: Platzhalter de/en verschieden`);
		}
	});
	test('DE-Wortlaut laut Spec; Termin als Platzhalter {wann}', () => {
		const d = de as Record<string, string>;
		for (const [, soll, key] of HINWEIS_DE) assert.equal(d[key], soll, key);
		assert.equal(d['aktionen.aktivieren.erfolg'], 'Aktiviert.');
		assert.equal(d['aktionen.aktivieren.erfolg_mit_zeit'], 'Aktiviert. Das erste Briefing kommt {wann}.');
	});
	test('EN-Wortlaut der Erfolgsmeldungen laut Spec; Knopf/Menütext bleibt aktionen.kopf.aktivieren', () => {
		const e = en as Record<string, string>;
		assert.equal(e['aktionen.aktivieren.erfolg'], 'Activated.');
		assert.equal(e['aktionen.aktivieren.erfolg_mit_zeit'], 'Activated. The first briefing arrives {wann}.');
		assert.equal(trFor('de', 'aktionen.kopf.aktivieren'), 'Aktivieren');
		assert.equal(trFor('en', 'aktionen.kopf.aktivieren'), 'Activate');
	});
});
