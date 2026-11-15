// TDD RED — Issue #3031 (Inhalt je Kanal A1): Zeilenmodell, Normalisierung, Adapter, Beispiele.
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md — Test Plan 1, 2, 7 (AC-1, AC-4, AC-8),
// Implementation Details 1, 3, 4, 5, 6, 7, 9.
//
// Erwartete Schnittstelle (hier festgelegt, /50 baut danach):
//
//   frontend/src/lib/components/organisms/wetter-tab/kanalInhalt.ts
//     type Kontext = 'route' | 'vergleich'
//     type ListenKanal = 'email' | 'telegram' | 'sms'          // Kanaele mit eigener Liste
//     type Kanal = ListenKanal | 'premium_sms'                 // Segment der Karte
//     type Format = 'roh' | 'einfach'
//     interface KanalZeile { id: string; enabled: boolean; format: Format }
//     type KanalListen = Record<ListenKanal, KanalZeile[]>
//     const KANAELE: readonly Kanal[]              = ['email', 'telegram', 'sms', 'premium_sms']
//     const LISTEN_KANAELE: readonly ListenKanal[] = ['email', 'telegram', 'sms']
//     normalisiereZeilen(zeilen | null | undefined, auswahl: string[], formatFuer: (id) => Format): KanalZeile[]
//         Teilmenge der Wetter-Auswahl (abgewaehlte fallen weg), fehlende Metrik eingeschaltet ans Ende
//         (Format aus formatFuer), Aus-Zeilen behalten ihre Position; ohne Liste = Auswahl, alle an.
//     listenAusAbo(kontext, abo, auswahl, formatFuer): KanalListen
//         liest `display_config.channel_layouts` (Trip UND Vergleich, gleiche Form). Reihenfolge der
//         eingeschalteten Zeilen = die der Renderer (Python `_sorted_by_layout`: bucket, dann order;
//         fehlt order, Listenreihenfolge). Format: use_friendly_format (fehlt ⇒ Einfach wie Python).
//         Vergleich ohne channel_layouts: Rueckfall `channel_active_metrics[kanal]` (gelistete an in
//         dieser Reihenfolge, uebrige Auswahl aus, Format laut Katalog) — #3039.
//     channelLayoutsAusListen(listen, bestand?): Record<ListenKanal, Eintrag[]>
//         Eintrag = { metric_id, enabled, use_friendly_format, ...Bestandsfelder des Eintrags };
//         KEIN format_mode (eine Wahrheit je Zeile), Reihenfolge = Listenreihenfolge, d. h.
//         `order` fehlt oder ist der Listenindex.
//     channelActiveMetricsAusListen(listen): Record<ListenKanal, string[]>  // nur eingeschaltete, geordnet
//     zeilenFuerKanal(listen, kanal): KanalZeile[]   // premium_sms ⇒ die SMS-Liste (ADR-0049, bis S9)
//     istSchreibgeschuetzt(kanal): boolean           // nur premium_sms
//     warnungsPosition(kanal): 'oben' | 'unten'      // E-Mail/Telegram oben, SMS/Premium-SMS unten
//     zeilenName(eintrag: KatalogEintrag): string    // „Temperatur (Temp | T)"; leeres Kuerzel ⇒ „–"
//     hatFormatWahl(eintrag: KatalogEintrag): boolean // Katalog hat mehr als einen format_mode
//     mitReihenfolge(listen, kanal, ids: string[]): KanalListen   // reine Operationen,
//     mitSchalter(listen, kanal, id, an: boolean): KanalListen    // Eingabe unveraendert,
//     mitFormat(listen, kanal, id, format: Format): KanalListen   // andere Kanaele unberuehrt
//
//   frontend/src/lib/components/organisms/wetter-tab/kanalInhaltBeispiele.ts
//     beispiel(id: string, format: Format, lang: 'de' | 'en'): string | null
//
// Befund zur Spec (Test 7): Der echte Katalog fuehrt Boeen/Wind/Niederschlag mit
// `has_friendly_format: false`, aber `format_modes: ['raw', 'simplified']` (Ampelpunkt in der Mail,
// vgl. Test 9). Die Wahl Roh/Einfach haengt deshalb an `format_modes` (mehr als ein Modus), nicht
// allein an `has_friendly_format` — sonst haette Boeen keinen Umschalter und AC-4 waere unerfuellbar.
//
// Reine Funktionsausgabe gegen den ECHTEN Katalog und die ECHTE Python-Kaskade (Orakel), keine Mocks.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/kanal_inhalt_3031_modell.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { fixture } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import {
	formatAusKatalog,
	hatWahlLautKatalog,
	kanalInhalt,
	kanalInhaltBeispiele,
	katalogNachId,
	pythonKanalStand,
	type OrakelZeile
} from '../../shared/wetter-tab/__tests__/kanalInhaltPruefstand.ts';

type Zeile = { id: string; enabled: boolean; format: 'roh' | 'einfach' };
const LK = ['email', 'telegram', 'sms'] as const;
const ids = (z: Zeile[]) => z.map((x) => x.id);
const an = (z: Zeile[]) => z.filter((x) => x.enabled).map((x) => x.id);
const fmt = (id: string) => formatAusKatalog(id);

// ─── Test 1 / AC-1 ───────────────────────────────────────────────────────────

describe('Test 1: Kanal ohne Eintrag ⇒ alle Wetter-Metriken eingeschaltet, Reihenfolge der Wetter-Liste', () => {
	test('normalisiereZeilen(null, auswahl) = Auswahl, alle an', async () => {
		const m = await kanalInhalt();
		const z: Zeile[] = m.normalisiereZeilen(null, ['temperature', 'gust', 'precipitation'], fmt);
		assert.deepEqual(ids(z), ['temperature', 'gust', 'precipitation']);
		assert.ok(z.every((x) => x.enabled), `nicht alle eingeschaltet: ${JSON.stringify(z)}`);
	});

	test('listenAusAbo ohne channel_layouts: jede der drei Listen = Auswahl, alle an (Trip und Vergleich)', async () => {
		const m = await kanalInhalt();
		for (const kontext of ['route', 'vergleich'] as const) {
			const l = m.listenAusAbo(kontext, { display_config: {} }, ['temperature', 'gust', 'precipitation'], fmt);
			for (const k of LK) {
				assert.deepEqual(ids(l[k]), ['temperature', 'gust', 'precipitation'], `${kontext}/${k}`);
				assert.ok(l[k].every((x: Zeile) => x.enabled), `${kontext}/${k}: nicht alle an`);
			}
		}
	});

	test('Kanal-Konstanten: vier Segmente, drei Listen; Premium-SMS ohne eigene Liste (ADR-0049)', async () => {
		const m = await kanalInhalt();
		assert.deepEqual([...m.KANAELE], ['email', 'telegram', 'sms', 'premium_sms']);
		assert.deepEqual([...m.LISTEN_KANAELE], ['email', 'telegram', 'sms']);
	});
});

// ─── Test 2 / AC-8 ───────────────────────────────────────────────────────────

describe('Test 2: neue Metrik eingeschaltet am Ende, abgewaehlte fehlt in allen Kanaelen, Aus behaelt Position', () => {
	const gespeichert = (): Zeile[] => [
		{ id: 'gust', enabled: true, format: 'roh' },
		{ id: 'temperature', enabled: false, format: 'roh' },
		{ id: 'precipitation', enabled: true, format: 'einfach' }
	];

	test('gespeicherte Telegram-Liste ohne „Luftdruck" ⇒ Luftdruck eingeschaltet am Ende', async () => {
		const m = await kanalInhalt();
		const z: Zeile[] = m.normalisiereZeilen(gespeichert(), ['temperature', 'gust', 'precipitation', 'pressure'], fmt);
		assert.deepEqual(ids(z), ['gust', 'temperature', 'precipitation', 'pressure']);
		assert.deepEqual(z.at(-1), { id: 'pressure', enabled: true, format: formatAusKatalog('pressure') });
	});

	test('Aus-Zeile behaelt ihre Position und ihren Zustand; Format der Bestandszeilen bleibt', async () => {
		const m = await kanalInhalt();
		const z: Zeile[] = m.normalisiereZeilen(gespeichert(), ['temperature', 'gust', 'precipitation'], fmt);
		assert.deepEqual(z, gespeichert());
	});

	test('im Reiter Wetter abgewaehlte Metrik fehlt in ALLEN drei Listen', async () => {
		const m = await kanalInhalt();
		const dc = {
			channel_layouts: Object.fromEntries(
				LK.map((k) => [k, gespeichert().map((x) => ({ metric_id: x.id, enabled: x.enabled, use_friendly_format: x.format === 'einfach' }))])
			)
		};
		const l = m.listenAusAbo('route', { display_config: dc }, ['temperature', 'precipitation'], fmt);
		for (const k of LK) assert.ok(!ids(l[k]).includes('gust'), `${k}: abgewaehlte Boeen stehen noch in der Liste`);
	});

	test('normalisiereZeilen veraendert die Eingabe nicht', async () => {
		const m = await kanalInhalt();
		const ein = gespeichert();
		const kopie = structuredClone(ein);
		m.normalisiereZeilen(ein, ['gust', 'pressure'], fmt);
		assert.deepEqual(ein, kopie);
	});
});

// ─── Adapter lesen: echter Bestand (golden_b) gegen die echte Python-Kaskade ──

describe('Adapter lesen: was die Karte zeigt, ist was die Renderer ausliefern (Trip-Bestand golden_b)', () => {
	const golden = () => fixture('einstellung_auslieferung/golden_b.json');
	const auswahlVon = (dc: { metrics: { metric_id: string; enabled?: boolean }[] }) =>
		dc.metrics.filter((x) => x.enabled !== false).map((x) => x.metric_id);

	for (const kontext of ['route', 'vergleich'] as const) {
		test(`${kontext}: eingeschaltete Zeilen je Kanal = Python-Kaskade (Reihenfolge nach bucket/order, nicht Array-Folge)`, async () => {
			const m = await kanalInhalt();
			const dc = golden().display_config;
			const orakel = pythonKanalStand(dc);
			const l = m.listenAusAbo(kontext, { display_config: dc }, auswahlVon(dc), fmt);
			for (const k of LK) {
				assert.deepEqual(an(l[k]), orakel[k].map((o: OrakelZeile) => o[0]), `${kontext}/${k}: Reihenfolge/Auswahl weicht vom Renderer ab`);
			}
		});

		test(`${kontext}: Roh/Einfach je Zeile = use_friendly_format des Kanal-Eintrags (wie die Renderer)`, async () => {
			const m = await kanalInhalt();
			const dc = golden().display_config;
			const orakel = pythonKanalStand(dc);
			const l = m.listenAusAbo(kontext, { display_config: dc }, auswahlVon(dc), fmt);
			for (const k of LK) {
				for (const [id, einfach] of orakel[k]) {
					const z = l[k].find((x: Zeile) => x.id === id);
					assert.equal(z?.format, einfach ? 'einfach' : 'roh', `${kontext}/${k}/${id}`);
				}
			}
		});
	}

	test('Teilmenge: global nicht gewaehlte Metrik (dewpoint in der SMS-Liste) erscheint nicht; Aus-Zeilen der Auswahl bleiben als Aus', async () => {
		const m = await kanalInhalt();
		const dc = golden().display_config;
		const auswahl = auswahlVon(dc);
		const l = m.listenAusAbo('route', { display_config: dc }, auswahl, fmt);
		assert.ok(!ids(l.sms).includes('dewpoint'), 'dewpoint ist im Reiter Wetter nicht gewaehlt');
		for (const k of LK) assert.deepEqual([...ids(l[k])].sort(), [...auswahl].sort(), `${k}: Liste ist nicht genau die Wetter-Auswahl`);
		const uv = l.email.find((x: Zeile) => x.id === 'uv_index');
		assert.equal(uv?.enabled, false, 'uv_index ist in der E-Mail-Liste ausgeschaltet gespeichert');
	});

	test('Vergleich ohne channel_layouts: Rueckfall auf channel_active_metrics (gelistete an in dieser Folge, uebrige aus)', async () => {
		const m = await kanalInhalt();
		const abo = {
			display_config: {
				channel_active_metrics: { telegram: [{ metric_id: 'gust', aggregation: 'max' }, { metric_id: 'temperature', aggregation: 'max' }] }
			}
		};
		const l = m.listenAusAbo('vergleich', abo, ['temperature', 'wind', 'gust'], fmt);
		assert.deepEqual(an(l.telegram), ['gust', 'temperature']);
		assert.equal(l.telegram.find((x: Zeile) => x.id === 'wind')?.enabled, false, 'nicht gelistete Metrik muss aus sein (Renderer zeigt sie nicht)');
		assert.deepEqual(an(l.email), ['temperature', 'wind', 'gust'], 'Kanal ohne Eintrag folgt der Auswahl');
	});
});

// ─── Adapter schreiben ───────────────────────────────────────────────────────

describe('Adapter schreiben: channel_layouts in der Form {metric_id, enabled, use_friendly_format}', () => {
	const listen = () => ({
		email: [
			{ id: 'temperature', enabled: true, format: 'roh' },
			{ id: 'gust', enabled: true, format: 'einfach' }
		],
		telegram: [
			{ id: 'gust', enabled: true, format: 'roh' },
			{ id: 'temperature', enabled: true, format: 'roh' }
		],
		sms: [
			{ id: 'temperature', enabled: true, format: 'roh' },
			{ id: 'gust', enabled: false, format: 'roh' }
		]
	});

	test('jede Liste vollstaendig, in Listenreihenfolge, Aus-Zeilen als enabled:false, Format als use_friendly_format', async () => {
		const m = await kanalInhalt();
		const cl = m.channelLayoutsAusListen(listen());
		assert.deepEqual(Object.keys(cl).sort(), ['email', 'sms', 'telegram'], 'genau die drei Listen-Kanaele (Premium-SMS folgt der SMS-Liste)');
		for (const k of LK) {
			const soll = listen()[k];
			assert.deepEqual(
				cl[k].map((e: Record<string, unknown>) => [e.metric_id, e.enabled, e.use_friendly_format]),
				soll.map((z) => [z.id, z.enabled, z.format === 'einfach']),
				k
			);
			cl[k].forEach((e: Record<string, unknown>, i: number) => {
				assert.ok(!('format_mode' in e), `${k}/${e.metric_id}: format_mode wuerde die Roh/Einfach-Wahl ueberstimmen`);
				assert.ok(e.order === undefined || e.order === i, `${k}/${e.metric_id}: order ${e.order} ≠ Listenposition ${i}`);
			});
		}
	});

	test('Bestandsfelder eines Eintrags (horizons, sms_threshold) bleiben erhalten (Read-Modify-Write)', async () => {
		const m = await kanalInhalt();
		const bestand = {
			sms: [
				{ metric_id: 'gust', enabled: true, use_friendly_format: false, sms_threshold: 50, horizons: { today: true } },
				{ metric_id: 'temperature', enabled: true, use_friendly_format: false }
			]
		};
		const cl = m.channelLayoutsAusListen(listen(), bestand);
		const gust = cl.sms.find((e: Record<string, unknown>) => e.metric_id === 'gust');
		assert.equal(gust.sms_threshold, 50, 'sms_threshold des Bestandseintrags verloren');
		assert.deepEqual(gust.horizons, { today: true }, 'horizons des Bestandseintrags verloren');
		assert.equal(gust.enabled, false, 'der Schalter der Karte muss den Bestand ueberschreiben');
	});

	test('Rundlauf: schreiben → lesen ergibt dieselben Listen', async () => {
		const m = await kanalInhalt();
		const dc = { channel_layouts: m.channelLayoutsAusListen(listen()) };
		const l = m.listenAusAbo('route', { display_config: dc }, ['temperature', 'gust'], fmt);
		assert.deepEqual(l, listen());
	});

	test('channelActiveMetricsAusListen: nur eingeschaltete Kennungen in Listenreihenfolge', async () => {
		const m = await kanalInhalt();
		assert.deepEqual(m.channelActiveMetricsAusListen(listen()), {
			email: ['temperature', 'gust'],
			telegram: ['gust', 'temperature'],
			sms: ['temperature']
		});
	});
});

// ─── Reine Operationen (Umsortieren, Schalter, Format) ───────────────────────

describe('Operationen der Karte wirken nur im gewaehlten Kanal', () => {
	const basis = () => ({
		email: [
			{ id: 'temperature', enabled: true, format: 'roh' },
			{ id: 'gust', enabled: true, format: 'roh' },
			{ id: 'wind', enabled: true, format: 'roh' }
		],
		telegram: [
			{ id: 'temperature', enabled: true, format: 'roh' },
			{ id: 'gust', enabled: true, format: 'roh' },
			{ id: 'wind', enabled: true, format: 'roh' }
		],
		sms: [
			{ id: 'temperature', enabled: true, format: 'roh' },
			{ id: 'gust', enabled: true, format: 'roh' },
			{ id: 'wind', enabled: true, format: 'roh' }
		]
	});

	test('mitReihenfolge(telegram): nur Telegram umsortiert, E-Mail/SMS Zeile fuer Zeile gleich, Eingabe unveraendert', async () => {
		const m = await kanalInhalt();
		const b = basis();
		const n = m.mitReihenfolge(b, 'telegram', ['wind', 'temperature', 'gust']);
		assert.deepEqual(ids(n.telegram), ['wind', 'temperature', 'gust']);
		assert.deepEqual(n.email, basis().email);
		assert.deepEqual(n.sms, basis().sms);
		assert.deepEqual(b, basis(), 'Eingabe mutiert');
	});

	test('mitSchalter(sms, gust, aus): Zeile bleibt an Position 2, nur in der SMS aus', async () => {
		const m = await kanalInhalt();
		const n = m.mitSchalter(basis(), 'sms', 'gust', false);
		assert.deepEqual(n.sms[1], { id: 'gust', enabled: false, format: 'roh' });
		assert.deepEqual(ids(n.sms), ['temperature', 'gust', 'wind']);
		assert.ok(n.email[1].enabled && n.telegram[1].enabled, 'anderer Kanal mitgeschaltet');
	});

	test('mitFormat(email, gust, einfach): nur die E-Mail-Zeile wechselt', async () => {
		const m = await kanalInhalt();
		const n = m.mitFormat(basis(), 'email', 'gust', 'einfach');
		assert.equal(n.email[1].format, 'einfach');
		assert.equal(n.telegram[1].format, 'roh');
		assert.equal(n.sms[1].format, 'roh');
	});
});

// ─── Premium-SMS, Warnungs-Zeile (AC-5, AC-6) ────────────────────────────────

describe('Premium-SMS folgt der SMS-Liste, Amtliche Warnungen oben bzw. unten', () => {
	test('zeilenFuerKanal(premium_sms) = SMS-Liste; schreibgeschuetzt nur Premium-SMS', async () => {
		const m = await kanalInhalt();
		const l = {
			email: [{ id: 'wind', enabled: true, format: 'roh' }],
			telegram: [{ id: 'gust', enabled: true, format: 'roh' }],
			sms: [
				{ id: 'temperature', enabled: true, format: 'roh' },
				{ id: 'gust', enabled: false, format: 'roh' }
			]
		};
		assert.deepEqual(m.zeilenFuerKanal(l, 'premium_sms'), l.sms);
		assert.deepEqual(m.zeilenFuerKanal(l, 'telegram'), l.telegram);
		assert.deepEqual(
			['email', 'telegram', 'sms', 'premium_sms'].map((k) => m.istSchreibgeschuetzt(k)),
			[false, false, false, true]
		);
	});

	test('warnungsPosition: E-Mail/Telegram oben, SMS/Premium-SMS unten', async () => {
		const m = await kanalInhalt();
		assert.deepEqual(
			['email', 'telegram', 'sms', 'premium_sms'].map((k) => m.warnungsPosition(k)),
			['oben', 'oben', 'unten', 'unten']
		);
	});
});

// ─── Test 7 / AC-1, AC-4: Name und Format-Wahl aus dem Katalog ───────────────

describe('Test 7: Name „Spaltenname (Kürzel)" und Roh/Einfach-Wahl aus dem echten Katalog', () => {
	test('Temperatur ⇒ „Temperatur (Temp | T)" (Katalog, nicht das D des Mockups)', async () => {
		const m = await kanalInhalt();
		const k = katalogNachId();
		assert.equal(m.zeilenName({ ...k.temperature, label: 'Temperatur' }), 'Temperatur (Temp | T)');
		assert.equal(m.zeilenName({ ...k.gust, label: 'Böen' }), 'Böen (Gust | G)');
	});

	test('leeres Kuerzel im Katalog ⇒ „–" (Mockup-Schreibweise)', async () => {
		const m = await kanalInhalt();
		const k = katalogNachId();
		assert.equal(k.temperature_night.sms_code, '', 'Messaufbau: temperature_night hat kein Kuerzel');
		assert.equal(m.zeilenName({ ...k.temperature_night, label: 'Nacht' }), 'Nacht (Night | –)');
	});

	test('hatFormatWahl: genau die Metriken mit mehr als einem Format-Modus im Katalog', async () => {
		const m = await kanalInhalt();
		const k = katalogNachId();
		assert.equal(m.hatFormatWahl(k.temperature), false, 'Temperatur hat nur Roh');
		assert.equal(m.hatFormatWahl(k.visibility), false, 'Sichtweite hat nur Roh (#819)');
		assert.equal(m.hatFormatWahl(k.gust), true, 'Boeen: Roh/Einfach (Ampelpunkt in der Mail, Test 9)');
		for (const e of Object.values(k)) {
			assert.equal(m.hatFormatWahl(e), hatWahlLautKatalog(e), `${e.id}: format_modes ${JSON.stringify(e.format_modes)}`);
		}
	});
});

describe('Test 7 / Beispiele: jede Metrik mit Roh/Einfach-Wahl hat ein Beispiel in DE und EN', () => {
	test('beispiel(id, roh|einfach, de|en) fuer alle wahlfaehigen Katalog-Metriken nicht leer', async () => {
		const b = await kanalInhaltBeispiele();
		const fehlt: string[] = [];
		for (const e of Object.values(katalogNachId()).filter(hatWahlLautKatalog)) {
			for (const lang of ['de', 'en'] as const) {
				for (const f of ['roh', 'einfach'] as const) {
					const t = b.beispiel(e.id, f, lang);
					if (typeof t !== 'string' || t.trim() === '') fehlt.push(`${e.id}/${f}/${lang}`);
				}
			}
		}
		assert.deepEqual(fehlt, [], `Beispiel fehlt: ${fehlt.join(', ')}`);
	});

	test('Roh und Einfach unterscheiden sich je Metrik (sonst zeigt die Zeile keinen Unterschied)', async () => {
		const b = await kanalInhaltBeispiele();
		for (const e of Object.values(katalogNachId()).filter(hatWahlLautKatalog)) {
			for (const lang of ['de', 'en'] as const) {
				assert.notEqual(b.beispiel(e.id, 'roh', lang), b.beispiel(e.id, 'einfach', lang), `${e.id}/${lang}`);
			}
		}
	});

	test('EN ist keine Kopie von DE: mindestens ein Beispiel unterscheidet sich (Wort/Dezimalzeichen)', async () => {
		const b = await kanalInhaltBeispiele();
		const verschieden = Object.values(katalogNachId())
			.filter(hatWahlLautKatalog)
			.some((e) => (['roh', 'einfach'] as const).some((f) => b.beispiel(e.id, f, 'de') !== b.beispiel(e.id, f, 'en')));
		assert.ok(verschieden, 'alle EN-Beispiele gleichen den deutschen — nicht in der Nutzersprache (AC-12)');
	});
});
