// TDD RED — Issue #2955 (gebündelt mit #3012): Reiter Wetter, Metrik-Inhalte an Mockup Fassung 3.
// Spec: docs/specs/modules/wetter_metrik_inhalte.md — AC-1, AC-2, AC-3, AC-3b, AC-4, AC-5, AC-6.
//
// EIN Code für Trip und Orts-Vergleich (shared/wetter-tab + organisms/wetter-tab). Metrik-Eigenschaften
// kommen aus der echten Python-Antwort von /api/metrics (wetterTabDaten.live), nie aus einer Frontend-Kopie.
// Sichtbare Texte per Server-Render der echten MetrikZeile (svelte/server), DE und EN über den Sprach-Store.
//
// RED heute:
//   - /api/metrics liefert kein `rang`; zeilenGruppen folgt der Auswahl (Regenwahrscheinlichkeit vor Gewitter).
//   - Gewitter-Satz sagt „auf mittel“ statt „auf mittel oder hoch“.
//   - Erklärsatz setzt das kleine Farbwort („orange“) statt des Stufenworts („Orange“).
//   - Kopfzähler: zweite Zahl = alarmfähige statt aller ausgewählten Metriken.
//   - Gefühlte Temperatur, Bewölkung, Taupunkt, Luftdruck sind keine Vorboten.
//   - DE-Namenskopien „Nacht-Tiefsttemperatur“, „Luftfeuchtigkeit“.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/fix2955_metrik_inhalte.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { ampelModell, FRONTEND, live, wetterKatalog, type Json } from './wetterTabDaten.ts';

register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const MetrikZeile = (await import(pathToFileURL(join(FRONTEND, 'src/lib/components/organisms/wetter-tab/MetrikZeile.svelte')).href)).default;

afterEach(() => locale.set('de'));

// Mockup Fassung 3, in Fassung 4 unverändert (docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html, TRIP_METRICS / ORTE_METRICS).
const MOCKUP_TRIP = [
	'temperature', 'temperature_night', 'wind_chill', 'wind', 'gust', 'wind_direction',
	'precipitation', 'thunder', 'rain_probability', 'visibility', 'cloud_low', 'uv_index',
	'freezing_level', 'snowfall_limit'
];
const MOCKUP_ORTE = ['temperature', 'wind', 'gust', 'wind_direction', 'precipitation', 'thunder', 'rain_probability', 'cloud_total', 'sunshine'];

async function umgebung(): Promise<{ m: Json; eig: Json }> {
	const m = await ampelModell();
	return { m, eig: m.eigenschaftenAusKatalog(live().metrics) };
}

const noop = () => {};
const text = (h: string) =>
	h.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
function zeile(id: string, eig: Json, eintrag: Json, thunder?: Json): string {
	return render(MetrikZeile, {
		props: {
			id, name: id, eig, eintrag, thunder, offen: false, abweichend: false, vorlageLabel: 'Standard', fehler: [],
			onEntfernen: noop, onAlarmAb: noop, onGrenzen: noop, onWert: noop, onGewitter: noop
		}
	}).body;
}
function erklaer(h: string, id: string): string {
	const m = h.match(new RegExp(`data-testid="wetter-erklaersatz-${id}"[^>]*>([\\s\\S]*?)</span>`));
	assert.ok(m, `Erklärsatz ${id} fehlt`);
	return text(m![1]);
}
function inSprache<T>(lang: 'de' | 'en', f: () => T): T {
	locale.set(lang);
	try {
		return f();
	} finally {
		locale.set('de');
	}
}
const fuelle = (vorlage: string, werte: Record<string, unknown>) =>
	vorlage.replace(/\{([a-z0-9_]+)\}/g, (_, k) => String(werte[k] ?? `{${k}}`));

// ── AC-3 / AC-3b: Reihenfolge aus `rang` von /api/metrics ─────────────────────

describe('AC-3/AC-3b: Zeilenfolge folgt dem Rang aus /api/metrics', () => {
	test('eigenschaftenAusKatalog reicht `rang` unverändert durch', async () => {
		const { eig } = await umgebung();
		for (const liste of Object.values(live().metrics) as Json[][]) {
			for (const k of liste) {
				assert.equal(typeof k.rang, 'number', `/api/metrics: ${k.id} ohne rang`);
				assert.equal(eig[k.id].rang, k.rang, `${k.id}: rang nicht durchgereicht`);
			}
		}
	});

	test('Auswahl [Regenwahrscheinlichkeit, Gewitter] → Gewitter steht vorn', async () => {
		const { m, eig } = await umgebung();
		const g = m.zeilenGruppen(['rain_probability', 'thunder'], eig);
		assert.deepEqual(g.flatMap((x: Json) => x.metriken), ['thunder', 'rain_probability']);
	});

	for (const [name, mockup] of [['Trip Alpen-Trekking', MOCKUP_TRIP], ['Orte Allgemein', MOCKUP_ORTE]] as const) {
		test(`${name}: Zeilen in Mockup-Reihenfolge, unabhängig von der Eingangsreihenfolge`, async () => {
			const { m, eig } = await umgebung();
			const soll = m.zeilenGruppen([...mockup], eig).map((x: Json) => x.gruppe)
				.flatMap((gr: string) => mockup.filter((id) => eig[id].group === gr));
			for (const eingang of [[...mockup].reverse(), [...mockup].sort(), [...mockup]]) {
				const ist = m.zeilenGruppen(eingang, eig).flatMap((x: Json) => x.metriken);
				assert.deepEqual(ist, soll, `Eingang ${eingang.join(',')}`);
			}
		});
	}

	test('gleicher oder fehlender Rang behält die Auswahl-Reihenfolge (stabil)', async () => {
		const { m, eig } = await umgebung();
		const gleich = structuredClone(eig);
		gleich.gust.rang = gleich.wind.rang;
		assert.deepEqual(m.zeilenGruppen(['gust', 'wind'], gleich)[0].metriken, ['gust', 'wind']);
		assert.deepEqual(m.zeilenGruppen(['wind', 'gust'], gleich)[0].metriken, ['wind', 'gust']);
		const ohne = structuredClone(eig);
		delete ohne.gust.rang;
		delete ohne.wind.rang;
		assert.deepEqual(m.zeilenGruppen(['gust', 'wind'], ohne)[0].metriken, ['gust', 'wind']);
	});

	test('„Nicht im Briefing“ bietet in derselben Rangfolge an (Gewitter vor Regenwahrscheinlichkeit)', async () => {
		const { m, eig } = await umgebung();
		const angebot: string[] = m.briefingAngebot('route', eig, [], new Set(Object.keys(eig)));
		assert.ok(angebot.indexOf('thunder') < angebot.indexOf('rain_probability'), angebot.join(','));
	});
});

// ── AC-1: Vorbote-Zeilen ──────────────────────────────────────────────────────

describe('AC-1: Vorboten zeigen „Vorbote, kein Alarm“, Gipfel in Wolken nicht', () => {
	const SOLL = {
		de: ['Vorbote, kein Alarm', 'Nur im Briefing gefärbt. Vorboten lösen keinen Alarm aus.', 'kein Alarm (Vorbote)'],
		en: ['precursor, no alert', 'Only coloured in the briefing. Precursors do not trigger alerts.', 'no alert (precursor)']
	};
	for (const id of ['wind_chill', 'cloud_total', 'dewpoint', 'pressure']) {
		for (const lang of ['de', 'en'] as const) {
			test(`${id} (${lang})`, async () => {
				const { eig } = await umgebung();
				const t = inSprache(lang, () => text(zeile(id, eig[id], { enabled: true, alarm_ab: 'never', lower: {}, upper: {} })));
				for (const s of SOLL[lang]) assert.ok(t.includes(s), `${id}/${lang}: „${s}“ fehlt in „${t}“`);
			});
		}
	}
	test('cloud_low ist kein Vorbote und zeigt „kein Alarm“', async () => {
		const { eig } = await umgebung();
		const t = text(zeile('cloud_low', eig.cloud_low, { enabled: true, alarm_ab: 'never', lower: {}, upper: { yellow: 50, orange: 80 } }));
		assert.ok(!t.includes('Vorbote'), t);
		assert.ok(t.includes('kein Alarm'), t);
	});
});

// ── AC-2: Gewitter-Satz ───────────────────────────────────────────────────────

describe('AC-2: Gewitter-Erklärsatz „mittel oder hoch“', () => {
	const fall = [
		{ thunder: { mittel: 'orange', hoch: 'red' }, de: 'auf mittel oder hoch steigt (Orange)', en: 'rises to medium or high since the last briefing (Orange)' },
		{ thunder: { mittel: 'yellow', hoch: 'orange' }, de: 'auf hoch steigt (Orange)', en: 'rises to high since the last briefing (Orange)' }
	];
	for (const f of fall) {
		for (const lang of ['de', 'en'] as const) {
			test(`mittel=${f.thunder.mittel}, hoch=${f.thunder.hoch}, Alarm ab Orange (${lang})`, async () => {
				const { eig } = await umgebung();
				const s = inSprache(lang, () => erklaer(zeile('thunder', eig.thunder, { enabled: true, alarm_ab: 'orange' }, f.thunder), 'thunder'));
				assert.ok(s.includes(f[lang]), `${lang}: „${f[lang]}“ fehlt in „${s}“`);
				if (f.thunder.mittel === 'yellow') assert.ok(!s.includes(lang === 'de' ? 'mittel oder' : 'medium or'), s);
			});
		}
	}
	test('Skala bleibt „keins · mittel · hoch“ (Regressionsschutz)', () => {
		const de = wetterKatalog('de');
		assert.deepEqual([de['wetter.gewitter.keins'], de['wetter.gewitter.mittel'], de['wetter.gewitter.hoch']], ['keins', 'mittel', 'hoch']);
	});
});

// ── AC-6: Stufenwort groß (#3012) ─────────────────────────────────────────────

describe('AC-6: Erklärsatz nennt das Stufenwort groß', () => {
	const WORT = { de: { yellow: 'Gelb', orange: 'Orange', red: 'Rot' }, en: { yellow: 'Yellow', orange: 'Orange', red: 'Red' } };
	for (const stufe of ['yellow', 'orange', 'red'] as const) {
		for (const lang of ['de', 'en'] as const) {
			test(`Böen, Alarm ab ${stufe} (${lang})`, async () => {
				const { eig } = await umgebung();
				const eintrag = { enabled: true, alarm_ab: stufe, lower: {}, upper: { yellow: 35, orange: 50, red: 70 } };
				const s = inSprache(lang, () => erklaer(zeile('gust', eig.gust, eintrag), 'gust'));
				assert.ok(s.includes(`(${WORT[lang][stufe]})`), `${lang}: „(${WORT[lang][stufe]})“ fehlt in „${s}“`);
			});
		}
	}
});

// ── AC-5: Kopfzähler ──────────────────────────────────────────────────────────

describe('AC-5: „9 von 13 Metriken … 3 können keinen auslösen“', () => {
	const FAEHIG = ['temperature', 'temperature_night', 'wind', 'gust', 'precipitation', 'thunder', 'visibility', 'uv_index', 'freezing_level', 'snowfall_limit'];
	const OHNE = ['wind_chill', 'rain_probability', 'wind_direction'];
	function ampel(nie: string[]): Json {
		const metrics: Json = {};
		for (const id of FAEHIG) metrics[id] = { enabled: true, alarm_ab: nie.includes(id) ? 'never' : 'orange', lower: {}, upper: {} };
		for (const id of OHNE) metrics[id] = { enabled: true, alarm_ab: 'never', lower: {}, upper: {} };
		return { template: 'alpen-trekking', metrics, thunder: { mittel: 'orange', hoch: 'red' } };
	}
	const auswahl = [...FAEHIG, ...OHNE];

	test('Messaufbau: 10 alarmfähige, 3 nicht alarmfähige Metriken', async () => {
		const { eig } = await umgebung();
		assert.deepEqual(FAEHIG.filter((id) => !eig[id].alertable), []);
		assert.deepEqual(OHNE.filter((id) => eig[id].alertable), []);
	});
	for (const [lang, soll] of [
		['de', '9 von 13 Metriken lösen einen Alarm aus. 3 können keinen auslösen (Vorboten und reine Anzeige).'],
		['en', '9 of 13 metrics trigger an alert. 3 cannot trigger one (precursors and display only).']
	] as const) {
		test(`Zähler (${lang})`, async () => {
			const { m, eig } = await umgebung();
			const z = m.alarmZaehler(ampel(['uv_index']), auswahl, eig);
			assert.equal(fuelle(wetterKatalog(lang)[z.schluessel], z.werte), soll);
		});
	}
	test('Stufe „nie“ senkt nur die erste Zahl', async () => {
		const { m, eig } = await umgebung();
		const z = m.alarmZaehler(ampel(['uv_index', 'wind']), auswahl, eig);
		assert.equal(fuelle(wetterKatalog('de')[z.schluessel], z.werte), '8 von 13 Metriken lösen einen Alarm aus. 3 können keinen auslösen (Vorboten und reine Anzeige).');
	});
});

// ── AC-4: ein Name überall ────────────────────────────────────────────────────

describe('AC-4: Wertebereiche und Alarme-Seite nutzen den Katalognamen', () => {
	const de = (bereich: string) => JSON.parse(readFileSync(join(FRONTEND, 'src/lib/i18n/messages/de', `${bereich}.json`), 'utf8'));
	const NAMEN: Record<string, string> = {
		temperature_night: 'Tiefsttemperatur Nacht',
		wind_chill_night: 'Gefühlte Tiefsttemperatur Nacht',
		humidity: 'Luftfeuchte'
	};
	test('Katalog /api/metrics liefert die neuen deutschen Namen', async () => {
		const { eig } = await umgebung();
		for (const [id, name] of Object.entries(NAMEN)) assert.equal(eig[id].label_de, name, id);
	});
	// #3383 S1: die Symbolzeilen-Schluessel (wertebereiche.symbolzeile.*) entfielen mit der Waise
	// wertebereicheAnzeige.ts; der Name kommt live aus dem Katalog /api/metrics (Test oben).
	test('Alarme-Seite zeigt denselben Namen', () => {
		assert.equal(de('alarme')['alarme.metrik.humidity'], NAMEN.humidity);
	});
});
