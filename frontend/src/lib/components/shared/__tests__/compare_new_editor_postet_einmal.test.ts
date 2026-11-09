// TDD RED — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-5, AC-7 (+ Seite /compare/new)
//
// AC-5: `/compare/new` — Name, Region, Aktivitätsprofil und Orte eingetragen, „Briefing
// aktivieren" ⇒ GENAU EIN `POST /api/compare/presets` mit allen eingegebenen Werten, danach
// navigiert der Editor per `goto` zum neuen Vergleich. Der Editor hält seinen Zustand selbst
// (kein `getContext`), das Speichern ist eine lokale Funktion (kein `saveNewPreset` an einer Klasse).
// AC-7: `vorlage`-Prop belegt EINMALIG beim Start vor (ohne `$effect`); eine spätere Änderung wird
// nicht von der Vorlage überschrieben; `weekday` wird weder gesetzt noch gesendet.
//
// Messweise (kein Mock-Theater): das ECHTE Instanz-Skript von CompareNewEditor.svelte
// (compareNeuEditorPruefstand.ts). Gesät werden nur Props, die die Seite setzt; der Speicherweg ist
// der echte (`handleActivate` → Payload-Bau → `$lib/api` → fetch). Aufgezeichnet wird nur die
// Netzgrenze (fetch) und die Navigation (`goto` aus der Saat — setzt einen statischen
// `import { goto } from '$app/navigation'` voraus, Muster TripNewEditor.svelte:11).
// Die Vorlage muss in einer Deklaration (Initialisierer) angewendet werden — der Prüfstand führt
// nackte Ausdrucks-Anweisungen außer onMount/beforeNavigate nicht aus (und `$effect` ist verboten).
//
// Warum heute rot: CompareNewEditor holt seinen Zustand per `getContext('compare-…')`; ohne
// Context ist er leer, `stateOverride` kennt name/pickedIds nicht, eine Prop `vorlage` gibt es
// nicht, die Seite reicht keine Vorlage durch.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/shared/__tests__/compare_new_editor_postet_einmal.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { effekteVon, findeKomponenten, attributAusdruck, type Knoten } from './svelteInstanzPruefstand.ts';
import { importQuelle, mountenUndWarten } from './standardwerteEditorPruefstand.ts';
import {
	VERTRAG_FEHLT_EDITOR,
	buendelAus,
	fetchMitschnitt,
	vergleichEditor
} from './compareNeuEditorPruefstand.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const SEITE = resolve(HIER, '..', '..', '..', '..', 'routes', 'compare', 'new', '+page.svelte');

// #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): letzter Schritt „Zustellung".
const ALLE_BESUCHT = { activeTab: 'zustellung', isMobileViewport: false, metrikenVisited: true, zustellungVisited: true };
const ORTE = ['loc-a', 'loc-b', 'loc-c'].map((id) => ({ id, name: id, lat: 0, lon: 0 }));

let netz: ReturnType<typeof fetchMitschnitt>;
beforeEach(() => {
	netz = fetchMitschnitt('cmp-neu');
});
afterEach(() => {
	netz.abbauen();
});

const EINGABEN = {
	name: 'Sardinien-Woche',
	region: 'Gallura',
	activityProfile: 'wintersport',
	pickedIds: ['loc-a', 'loc-b', 'loc-c']
};

describe('AC-5: Anlegen postet genau einmal, mit allen Eingaben, und navigiert', () => {
	test('Vorbedingung: name/region/activityProfile/pickedIds kommen über stateOverride an (ohne Context)', async () => {
		const e = await vergleichEditor({ stateOverride: { ...ALLE_BESUCHT, ...EINGABEN }, locations: ORTE });
		assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
		assert.equal(e.u.orteOk, true, VERTRAG_FEHLT_EDITOR);
		assert.equal(e.u.canActivateNow, true, 'VERTRAG FEHLT (#2727): „Briefing aktivieren" ist trotz Name, 3 Orten und allen Besuchen gesperrt');
	});

	test('„Briefing aktivieren" ⇒ genau ein POST /api/compare/presets; Körper trägt Name, Orte, Profil, Region', async () => {
		const e = await vergleichEditor({ stateOverride: { ...ALLE_BESUCHT, ...EINGABEN }, locations: ORTE });
		assert.equal(typeof e.u.handleActivate, 'function', 'Messaufbau: handleActivate nicht gebunden');
		assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
		await e.u.handleActivate();
		const posts = netz.presetPosts();
		assert.equal(posts.length, 1, `erwartet genau EINEN POST, gesehen ${posts.length}`);
		const b = posts[0].koerper as Knoten;
		assert.equal(b.name, 'Sardinien-Woche');
		assert.deepEqual(b.location_ids, ['loc-a', 'loc-b', 'loc-c']);
		assert.equal(b.profil, 'wintersport', 'Aktivitätsprofil fehlt im Payload (Rückfall „wandern"?)');
		assert.equal((b.display_config as Knoten)?.region, 'Gallura', 'Region fehlt in display_config');
		assert.equal(b.schedule, 'daily', 'Standard-Zeitplan des Anlegens');
	});

	test('nach Erfolg navigiert der Editor per goto zum neuen Vergleich', async () => {
		const e = await vergleichEditor({ stateOverride: { ...ALLE_BESUCHT, ...EINGABEN }, locations: ORTE });
		assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
		await e.u.handleActivate();
		assert.deepEqual(e.gotos, ['/compare/cmp-neu'], `Navigation nach dem POST: ${JSON.stringify(e.gotos)}`);
	});

	test('Doppelklick: zwei gleichzeitige Aktivierungen legen nur EIN Preset an', async () => {
		const e = await vergleichEditor({ stateOverride: { ...ALLE_BESUCHT, ...EINGABEN }, locations: ORTE });
		assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
		await Promise.all([e.u.handleActivate(), e.u.handleActivate()]);
		assert.equal(netz.presetPosts().length, 1, 'Re-Entrancy-Guard fehlt: Doppelklick legt zwei Presets an');
	});

	test('Gegenprobe: Zustellung nicht besucht ⇒ kein POST (Freischaltung leitet der Editor selbst her)', async () => {
		const e = await vergleichEditor({
			stateOverride: { ...ALLE_BESUCHT, zustellungVisited: false, ...EINGABEN },
			locations: ORTE
		});
		assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
		await e.u.handleActivate();
		assert.equal(netz.presetPosts().length, 0);
	});

	test('eine Nutzergeste im Versand-Reiter (Premium-SMS an) landet im selben POST', async () => {
		const e = await vergleichEditor({ stateOverride: { ...ALLE_BESUCHT, ...EINGABEN }, locations: ORTE });
		assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
		(buendelAus(e, 'WetterMetrikenVersandPanel', 'versand').onSendPremiumSmsChange as (an: boolean) => void)(true);
		await e.u.handleActivate();
		assert.equal(netz.presetPosts()[0]?.koerper?.send_premium_sms, true);
	});
});

// ── AC-7: Vorlage (/compare/new?from=<id>) ───────────────────────────────────────

function vorlage(): Knoten {
	return {
		id: 'cmp-original',
		etag: 'W/"orig-etag"',
		name: 'Korsika Nord',
		location_ids: ['loc-a', 'loc-b', 'loc-c'],
		schedule: 'weekly',
		weekday: 3,
		profil: 'wandern',
		letzter_versand: '2026-09-01T07:00:00Z',
		created_at: '2026-08-01T00:00:00Z',
		display_config: { region: 'Korsika', telegram_style: 'kurzform' },
		alert_channels: { email: false, telegram: true, sms: false, premium_sms: true },
		send_telegram: true,
		send_sms: true,
		send_premium_sms: true,
		morning_enabled: false,
		morning_time: '05:30:00',
		evening_enabled: true,
		evening_time: '19:45:00',
		official_alert_triggers_enabled: false
	};
}

describe('AC-7: Prop `vorlage` belegt einmalig vor', () => {
	test('POST trägt die Vorlagenwerte, aber keine Identität, kein If-Match und kein weekday', async () => {
		const e = await vergleichEditor({ stateOverride: ALLE_BESUCHT, vorlage: vorlage(), locations: ORTE });
		assert.equal(e.u.nameOk, true, 'VERTRAG FEHLT (#2727): Prop `vorlage` belegt den Namen nicht vor');
		await e.u.handleActivate();
		const posts = netz.presetPosts();
		assert.equal(posts.length, 1);
		const { koerper, kopf, roh } = posts[0];
		const b = koerper as Knoten;
		assert.equal(b.name, 'Korsika Nord (Kopie)');
		assert.deepEqual(b.location_ids, ['loc-a', 'loc-b', 'loc-c']);
		assert.equal((b.display_config as Knoten).region, 'Korsika');
		assert.equal(b.schedule, 'weekly');
		assert.equal(b.send_telegram, true);
		assert.equal(b.morning_time, '05:30:00');
		assert.equal(b.official_alert_triggers_enabled, false);
		assert.deepEqual(b.alert_channels, { email: false, telegram: true, sms: false, premium_sms: true });
		assert.ok(!('weekday' in b), `weekday darf nicht gesendet werden: ${JSON.stringify(b.weekday)}`);
		for (const verboten of ['id', 'etag', 'letzter_versand', 'created_at', 'paused_at']) {
			assert.ok(!(verboten in b), `Create-Request darf "${verboten}" nicht tragen`);
		}
		assert.ok(!roh.includes('cmp-original') && !roh.includes('orig-etag'), 'Vorlagen-Identität im Request');
		assert.ok(!('If-Match' in kopf), 'Create-Request darf kein If-Match tragen');
	});

	test('gelöschter Ort der Vorlage fehlt in den Orten (Filter gegen `locations`)', async () => {
		const e = await vergleichEditor({
			stateOverride: ALLE_BESUCHT,
			vorlage: vorlage(),
			locations: ORTE.filter((o) => o.id !== 'loc-b')
		});
		assert.equal(e.u.nameOk, true, 'VERTRAG FEHLT (#2727): Prop `vorlage` belegt den Namen nicht vor');
		await e.u.handleActivate();
		assert.deepEqual(netz.presetPosts()[0]?.koerper?.location_ids, ['loc-a', 'loc-c']);
	});

	test('einmalig: eine spätere Änderung überlebt Mount und alle Effekte (die Vorlage überschreibt nicht)', async () => {
		const e = await vergleichEditor({ stateOverride: ALLE_BESUCHT, vorlage: vorlage(), locations: ORTE });
		assert.equal(e.u.nameOk, true, 'VERTRAG FEHLT (#2727): Prop `vorlage` belegt den Namen nicht vor');
		(buendelAus(e, 'WetterMetrikenVersandPanel', 'versand').onSendTelegramChange as (an: boolean) => void)(false);
		await mountenUndWarten(e);
		await e.u.handleActivate();
		assert.equal(netz.presetPosts()[0]?.koerper?.send_telegram, false, 'die Vorlage wurde nach der Nutzeränderung erneut angewendet');
	});

	test('kein $effect wendet die Vorlage an; der Editor nutzt die reine Funktion feldsatzAusVorlage', async () => {
		const e = await vergleichEditor({ stateOverride: ALLE_BESUCHT, vorlage: vorlage(), locations: ORTE });
		assert.ok(
			importQuelle(e.ast, 'feldsatzAusVorlage') !== null,
			'VERTRAG FEHLT (#2727): CompareNewEditor importiert feldsatzAusVorlage nicht'
		);
		assert.deepEqual(effekteVon(e.ast, e.quelle, e.u, 'feldsatzAusVorlage').length, 0, 'Vorlage in einem $effect');
		assert.deepEqual(effekteVon(e.ast, e.quelle, e.u, 'vorlage').length, 0, 'ein $effect liest die Vorlage');
	});
});

// ── Seite /compare/new: reicht die Vorlage durch, setzt keinen Context ─────────

describe('Seite /compare/new (Vertrag 5)', () => {
	const quelle = readFileSync(SEITE, 'utf-8');
	const ast: Knoten = parse(quelle, { modern: true });

	test('Positivkontrolle: die Seite mountet CompareNewEditor mit den Orten', () => {
		const mounts = findeKomponenten(ast, 'CompareNewEditor');
		assert.equal(mounts.length, 1);
		assert.equal(attributAusdruck(mounts[0], quelle, 'locations'), 'data.locations');
	});

	test('die Vorlage reist als Prop `vorlage={data.vorlage}` (kein Zustandsobjekt, kein Context)', () => {
		const m = findeKomponenten(ast, 'CompareNewEditor')[0];
		assert.equal(attributAusdruck(m, quelle, 'vorlage'), 'data.vorlage', 'VERTRAG FEHLT (#2727): Seite reicht data.vorlage nicht als Prop durch');
		const aufrufe: string[] = [];
		(function lauf(n: unknown): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach(lauf);
			const k = n as Knoten;
			if (k.type === 'CallExpression' && k.callee?.type === 'Identifier') aufrufe.push(k.callee.name);
			for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		})(ast.instance?.content);
		assert.ok(!aufrufe.includes('setContext'), 'Seite /compare/new ruft noch setContext auf');
	});
});
