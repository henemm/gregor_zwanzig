// TDD RED — Issue #2283 (Epic #2345 P3): EIN geteilter Vorschau-Reiter fuer
// Trip-Hub und Ortsvergleich-Hub.
// Spec: docs/specs/modules/shared_preview_tab.md — AC-8 (Anordnung Trip),
// AC-10 (Morgen/Abend + Demo nur route), AC-12 (gleiche Anordnung im
// Vergleich, CompareTabs ohne eigenes Vorschau-Markup), AC-13 (kein
// Test-Senden-Knopf im Reiter), AC-14 (CompareTabs laedt die entfernten
// Bausteine nicht mehr — am echten Modulgraphen).
//
// ZIELSCHNITTSTELLE `shared/PreviewTab.svelte` (von diesen Tests festgelegt):
//   Props:
//     context: 'route' | 'vergleich'
//     id: string                       // Trip- bzw. Vergleichs-ID
//     loader?: PreviewLoader           // aus shared/previewLoader.ts
//                                      // (createPreviewLoader); fehlt er, legt
//                                      // PreviewTab ihn selbst mit kind=context an
//     premiumSms?: boolean             // Premium-SMS eingeschaltet → Hinweis beim
//                                      // SMS-Kanal (Text = premiumSmsPreviewNote)
//     configuredChannels?: string[]    // optional, fuer die Kanal-Markierung
//   PreviewTab zeigt AUSSCHLIESSLICH den Zustand des Laders an (Kanal,
//   E-Mail-Ansicht, Optionen, Daten) — EIN Zustand, EINE Naht fuer Produktion
//   und Test. Deshalb wird hier ein echter Lader mit echtem `api.ts` geladen
//   (Netzgrenze `globalThis.fetch` liefert eine Buendel-Antwort) und der Kanal
//   ueber `loader.setChannel(...)` gewaehlt, bevor serverseitig gerendert wird.
//   SSR fuehrt weder onMount noch $effect aus — es wird also nichts abgerufen.
//
//   Markup-Vertrag (data-testid; vorhandene Kennungen bewusst weiterverwendet,
//   damit die Live-Specs klein migrieren):
//     preview-tab  (Wurzel, data-context="route|vergleich")
//     Kanalumschalter: drei <button> „E-Mail/Email" · „SMS" · „Telegram"
//     compare-preview-premium-sms-note  (nur Kanal SMS + premiumSms)
//     SMS:      sms-phone-wrapper > sms-token-bubble  (Text = sms.text)
//     E-Mail:   email-iframe-wrapper[data-email-view="desktop|mobile"] > iframe
//               data-testid="email-iframe" srcdoc=email_html;
//               Umschalter preview-email-view-desktop / preview-email-view-mobile
//     Telegram: preview-telegram  (Chat-Blase mit telegram.body)
//     route:    preview-demo-banner (bei options.demo), preview-controls mit
//               Radios value="morning"/"evening" (checked = options.type)
//     Laden:    preview-loading · Fehler: preview-error
//     Kanal nicht in configuredChannels: preview-channel-not-configured
//   Kein Sende-Knopf (AC-13): Senden gibt es nur im Hub-Kopf (#2278).
//
// Grenze: Klickverhalten im Browser bewacht frontend/e2e/preview-tab-gleiche-anordnung.spec.ts.
//
// RED HEUTE: shared/PreviewTab.svelte und shared/previewLoader.ts fehlen;
// CompareTabs rendert noch das eigene Vorschau-Markup (iframe srcdoc,
// „Test-Briefing senden") und initialisiert den Reiter erst im $effect
// (SSR sieht deshalb den Vorschau-Reiter nicht — s. Vorbedingung unten).
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/previewTab.test.ts

import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { MessageChannel } from 'node:worker_threads';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

// Pfadregel #1409: alles relativ zu DIESER Datei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const basis = pathToFileURL(FRONTEND + '/').href;

// Modul-Mitschnitt (AC-14) zuerst anlegen, damit er jede Ladung sieht.
const geladen = new Set<string>();
const kanal = new MessageChannel();
kanal.port1.on('message', (u: string) => geladen.add(u));
kanal.port1.unref();

register(pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, basis);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(path.join(HERE, 'svelteTsModulHook.mjs')).href, basis);
register(pathToFileURL(path.join(HERE, 'modulMitschnittHook.mjs')).href, {
	parentURL: basis,
	data: { port: kanal.port2 },
	transferList: [kanal.port2]
});

const { render } = await import('svelte/server');
const { premiumSmsPreviewNote } = await import('../../compare/subscriptionHelpers.ts');
const { vollerVergleich } = await import('./goMergeServerPruefstand.ts');

type Loader = {
	load(): Promise<void>;
	setChannel(c: string): void;
	setEmailView(v: string): void;
	getState(): { status: string; options: { type?: string; demo?: boolean } };
};

async function previewTab(): Promise<unknown> {
	try {
		return (await import(pathToFileURL(path.join(HERE, '../PreviewTab.svelte')).href)).default;
	} catch (e) {
		assert.fail(`shared/PreviewTab.svelte fehlt oder laedt nicht (AC-8/AC-12): ${(e as Error).message}`);
	}
}

async function loaderModul(): Promise<{ createPreviewLoader: (i: Record<string, unknown>) => Loader }> {
	try {
		const m = await import(pathToFileURL(path.join(HERE, '../previewLoader.ts')).href);
		assert.equal(typeof m.createPreviewLoader, 'function', 'previewLoader.ts muss createPreviewLoader exportieren');
		return m;
	} catch (e) {
		assert.fail(`shared/previewLoader.ts fehlt oder laedt nicht (AC-9): ${(e as Error).message}`);
	}
}

const BUENDEL = {
	subject: '[Huetten Korsika] Vergleich Morgen',
	email_html: '<html><body><h1>Vergleich Refuge Ortu</h1><p>Wind 35 km/h</p></body></html>',
	sms: { text: 'VGL: 1 Ortu W35 G52 | 2 Petra W20 G31', char_count: 37 },
	telegram: { body: 'Vergleich: Ortu vor Petra — Wind 35 km/h', bubbles: ['Vergleich: Ortu vor Petra — Wind 35 km/h'] }
};

let echtesFetch: typeof globalThis.fetch;
before(() => {
	echtesFetch = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = () =>
		Promise.resolve(new Response(JSON.stringify(BUENDEL), { status: 200, headers: { 'Content-Type': 'application/json' } }));
});
after(() => {
	(globalThis as { fetch: unknown }).fetch = echtesFetch;
});

type Ctx = 'route' | 'vergleich';

/** Echter Lader, echt geladen (Netzgrenze liefert BUENDEL), Kanal/Ansicht gewaehlt. */
async function geladenerLader(
	ctx: Ctx,
	channel: string,
	emailView = 'desktop',
	options?: Record<string, unknown>
): Promise<Loader> {
	const { createPreviewLoader } = await loaderModul();
	const l = createPreviewLoader({ kind: ctx, id: ctx === 'route' ? 't-1' : 'cp-1', ...(options ? { options } : {}) });
	await l.load();
	assert.equal(l.getState().status, 'ready', 'Messaufbau: der Lader muss die Buendel-Antwort geladen haben');
	l.setChannel(channel);
	l.setEmailView(emailView);
	return l;
}

async function renderTab(ctx: Ctx, loader: Loader, extra: Record<string, unknown> = {}): Promise<string> {
	const PreviewTab = await previewTab();
	return render(PreviewTab as never, {
		props: { context: ctx, id: ctx === 'route' ? 't-1' : 'cp-1', loader, ...extra }
	}).body;
}

const tid = (t: string) => `data-testid="${t}"`;
const zaehle = (html: string, nadel: string) => html.split(nadel).length - 1;

/** Sichtbare Beschriftungen aller <button>-Elemente. */
function knopfTexte(html: string): string[] {
	return [...html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)].map((m) =>
		m[1].replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
	);
}

/** Inhalt ab dem Element mit testid bis zum Ende seines direkten Bereichs (grob: naechste 4000 Zeichen). */
function bereich(html: string, testid: string): string {
	const i = html.indexOf(tid(testid));
	assert.notEqual(i, -1, `Element ${testid} fehlt im gerenderten HTML`);
	return html.slice(i, i + 4000);
}

function assertKeinSendeKnopf(html: string, wo: string): void {
	const sende = knopfTexte(html).filter((t) => /senden|send/i.test(t));
	assert.deepEqual(sende, [], `${wo}: Sende-Knopf im Vorschau-Reiter (AC-13 — Senden nur im Hub-Kopf, #2278): ${JSON.stringify(sende)}`);
	assert.equal(/data-testid="[^"]*(testsend|send-)[^"]*"/.test(html), false, `${wo}: Sende-Element (testid) im Vorschau-Reiter`);
}

for (const ctx of ['route', 'vergleich'] as Ctx[]) {
	const AC = ctx === 'route' ? 'AC-8' : 'AC-12';
	describe(`${AC}: PreviewTab context="${ctx}" — gleiche Anordnung in beiden Hubs`, () => {
		test('Wurzel traegt den Kontext; Kanalumschalter E-Mail · SMS · Telegram', async () => {
			const html = await renderTab(ctx, await geladenerLader(ctx, 'email'));
			assert.match(html, new RegExp(`${tid('preview-tab')}[^>]*data-context="${ctx}"|data-context="${ctx}"[^>]*${tid('preview-tab')}`));
			const knoepfe = knopfTexte(html);
			for (const label of [/^e-?mail\b/i, /^sms\b/i, /^telegram\b/i]) {
				assert.ok(knoepfe.some((k) => label.test(k)), `Kanalumschalter ohne ${label} — Knoepfe: ${JSON.stringify(knoepfe)}`);
			}
		});

		test('Kanal SMS: Text im Telefonrahmen', async () => {
			const html = await renderTab(ctx, await geladenerLader(ctx, 'sms'));
			const rahmen = bereich(html, 'sms-phone-wrapper');
			assert.ok(rahmen.includes(tid('sms-token-bubble')), 'SMS-Text steht nicht im Telefonrahmen (sms-token-bubble fehlt)');
			assert.ok(rahmen.includes(BUENDEL.sms.text), `SMS-Text aus der Vorschau fehlt im Telefonrahmen. HTML: ${rahmen.slice(0, 600)}`);
			assert.equal(zaehle(html, tid('email-iframe')), 0, 'beim Kanal SMS darf keine E-Mail angezeigt werden');
		});

		test('Kanal SMS + Premium-SMS an: Hinweis „Premium-SMS versendet denselben Text"', async () => {
			const erwartet = premiumSmsPreviewNote({ send_premium_sms: true } as never, 'sms');
			assert.ok(erwartet.length > 0, 'Messaufbau: premiumSmsPreviewNote liefert Text');
			const html = await renderTab(ctx, await geladenerLader(ctx, 'sms'), { premiumSms: true });
			const m = html.match(new RegExp(`${tid('compare-preview-premium-sms-note')}[^>]*>([^<]*)<`));
			assert.ok(m, `Premium-SMS-Hinweis fehlt (AC-8/AC-12, alle vier Kanaele gleichrangig). HTML: ${html.slice(0, 800)}`);
			assert.equal(m![1].trim(), erwartet);
		});

		test('Premium-SMS aus oder Kanal E-Mail: kein Hinweis', async () => {
			const aus = await renderTab(ctx, await geladenerLader(ctx, 'sms'), { premiumSms: false });
			assert.equal(zaehle(aus, tid('compare-preview-premium-sms-note')), 0);
			const email = await renderTab(ctx, await geladenerLader(ctx, 'email'), { premiumSms: true });
			assert.equal(zaehle(email, tid('compare-preview-premium-sms-note')), 0);
		});

		for (const view of ['desktop', 'mobile']) {
			test(`Kanal E-Mail, Ansicht ${view}: iframe mit dem Vorschau-HTML, Umschalter Desktop/Mobil`, async () => {
				const html = await renderTab(ctx, await geladenerLader(ctx, 'email', view));
				assert.ok(html.includes(tid('preview-email-view-desktop')), 'Ansicht-Umschalter Desktop fehlt');
				assert.ok(html.includes(tid('preview-email-view-mobile')), 'Ansicht-Umschalter Mobil fehlt');
				const wrapper = html.match(/<[^>]*data-testid="email-iframe-wrapper"[^>]*>/);
				assert.ok(wrapper, 'email-iframe-wrapper fehlt');
				assert.match(wrapper![0], new RegExp(`data-email-view="${view}"`), `die gewaehlte Ansicht (${view}) kommt nicht aus dem Lader`);
				// Attributbewusst: Svelte laesst `>` im srcdoc roh (escaping.js ATTR_REGEX = /[&"<]/).
				const iframes = [...html.matchAll(/<iframe\b(?:[^>"]|"[^"]*")*>/g)].map((m) => m[0]);
				assert.equal(iframes.length, 1, `genau ein iframe erwartet, gefunden: ${iframes.length}`);
				assert.match(iframes[0], /data-testid="email-iframe"/);
				assert.match(iframes[0], /srcdoc="[^"]*Vergleich Refuge Ortu/, 'srcdoc traegt nicht das email_html der Vorschau');
			});
		}

		test('Kanal Telegram: Chat-Blase mit dem Telegram-Text', async () => {
			const html = await renderTab(ctx, await geladenerLader(ctx, 'telegram'));
			const blase = bereich(html, 'preview-telegram');
			assert.ok(blase.includes(BUENDEL.telegram.body), `Telegram-Text fehlt in der Blase. HTML: ${blase.slice(0, 600)}`);
			assert.equal(zaehle(html, tid('email-iframe')), 0);
		});

		test('AC-13: kein Test-Senden-Knopf im Reiter (alle drei Kanaele)', async () => {
			for (const ch of ['email', 'sms', 'telegram']) {
				assertKeinSendeKnopf(await renderTab(ctx, await geladenerLader(ctx, ch), { premiumSms: true }), `${ctx}/${ch}`);
			}
		});

		test('nicht konfigurierter Kanal: Hinweis neben dem Umschalter (#1256 S8b AC-3 bleibt)', async () => {
			const html = await renderTab(ctx, await geladenerLader(ctx, 'sms'), { configuredChannels: ['email'] });
			assert.ok(html.includes(tid('preview-channel-not-configured')), 'Hinweis „Kanal nicht konfiguriert" fehlt');
			const email = await renderTab(ctx, await geladenerLader(ctx, 'email'), { configuredChannels: ['email'] });
			assert.equal(zaehle(email, tid('preview-channel-not-configured')), 0);
		});

		test('Ladezustand des Laders wird angezeigt', async () => {
			const { createPreviewLoader } = await loaderModul();
			const vorher = globalThis.fetch;
			let antworte: (r: Response) => void = () => {};
			(globalThis as { fetch: unknown }).fetch = () => new Promise<Response>((r) => (antworte = r));
			let laeuft: Promise<void> | undefined;
			try {
				const l = createPreviewLoader({ kind: ctx, id: 'e-lade' });
				laeuft = l.load();
				await new Promise((r) => setImmediate(r));
				assert.equal(l.getState().status, 'loading', 'Messaufbau: der Lader laeuft');
				const html = await renderTab(ctx, l);
				assert.ok(html.includes(tid('preview-loading')), 'Ladezustand wird nicht angezeigt (preview-loading fehlt)');
			} finally {
				// Abruf beenden, damit kein Zeitlimit-Timer den Testprozess offen haelt.
				antworte(new Response(JSON.stringify(BUENDEL), { status: 200, headers: { 'Content-Type': 'application/json' } }));
				await laeuft?.catch(() => undefined);
				(globalThis as { fetch: unknown }).fetch = vorher;
			}
		});

		test('Fehlerzustand des Laders wird angezeigt', async () => {
			const { createPreviewLoader } = await loaderModul();
			const vorher = globalThis.fetch;
			(globalThis as { fetch: unknown }).fetch = () =>
				Promise.resolve(new Response(JSON.stringify({ error: 'x' }), { status: 500, headers: { 'Content-Type': 'application/json' } }));
			try {
				const l = createPreviewLoader({ kind: ctx, id: 'e-err' });
				await l.load();
				const html = await renderTab(ctx, l);
				assert.ok(html.includes(tid('preview-error')), 'Fehlerzustand des Laders wird nicht angezeigt (preview-error fehlt)');
			} finally {
				(globalThis as { fetch: unknown }).fetch = vorher;
			}
		});
	});
}

describe('AC-10: Morgen/Abend und Demo-Hinweis nur im Trip', () => {
	test('route: Demo-Hinweis und Morgen/Abend vorhanden, Auswahl aus dem Lader', async () => {
		const html = await renderTab('route', await geladenerLader('route', 'email', 'desktop', { type: 'evening', demo: true }));
		assert.ok(html.includes(tid('preview-demo-banner')), 'route: Demo-Hinweis fehlt (Standard demoMode=true)');
		const ctrl = bereich(html, 'preview-controls');
		const radios = [...ctrl.matchAll(/<input\b[^>]*type="radio"[^>]*>/g)].map((m) => m[0]);
		assert.ok(radios.some((r) => /value="morning"/.test(r)), 'route: Radio Morgen fehlt');
		const abend = radios.find((r) => /value="evening"/.test(r));
		assert.ok(abend, 'route: Radio Abend fehlt');
		assert.match(abend!, /\bchecked\b/, 'route: der gewaehlte Berichtstyp (Abend) ist nicht markiert');
	});

	test('route mit echten Daten (demo=false): kein Demo-Hinweis, Morgen/Abend bleibt', async () => {
		const html = await renderTab('route', await geladenerLader('route', 'email', 'desktop', { type: 'morning', demo: false }));
		assert.equal(zaehle(html, tid('preview-demo-banner')), 0);
		assert.ok(html.includes(tid('preview-controls')));
	});

	test('vergleich: weder Demo-Hinweis noch Morgen/Abend', async () => {
		const html = await renderTab('vergleich', await geladenerLader('vergleich', 'email'));
		assert.equal(zaehle(html, tid('preview-demo-banner')), 0, 'vergleich: Demo-Hinweis darf es nicht geben');
		assert.equal(zaehle(html, tid('preview-controls')), 0, 'vergleich: Morgen/Abend darf es nicht geben');
		assert.equal(/type="radio"[^>]*value="(morning|evening)"|value="(morning|evening)"[^>]*type="radio"/.test(html), false);
	});
});

describe('AC-12/AC-13/AC-14: CompareTabs-Reiter „vorschau" nutzt den geteilten PreviewTab', () => {
	async function renderCompareVorschau(): Promise<string> {
		const CompareTabs = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/compare/CompareTabs.svelte')).href))
			.default;
		const html = render(CompareTabs, {
			props: { preset: vollerVergleich('cp-2283'), locations: [], initialTab: 'vorschau' }
		}).body;
		// Vorbedingung: ohne sie waere jede Abwesenheits-Pruefung unten umsonst gruen.
		assert.ok(
			html.includes(tid('compare-detail-panel-vorschau')),
			'Vorbedingung: CompareTabs rendert mit initialTab="vorschau" den Vorschau-Reiter nicht. Heute setzt erst ein ' +
				'$effect den Reiter (SSR fuehrt ihn nie aus) — der Reiter muss SYNCHRON aus initialTab ' +
				'(resolveTab) initialisiert werden, und die Huelle data-testid="compare-detail-panel-vorschau" bleibt.'
		);
		return html.slice(html.indexOf(tid('compare-detail-panel-vorschau')));
	}

	test('AC-12: der Vorschau-Reiter enthaelt PreviewTab mit context="vergleich"', async () => {
		const panel = await renderCompareVorschau();
		assert.ok(panel.includes(tid('preview-tab')), 'CompareTabs rendert im Reiter vorschau keinen geteilten PreviewTab');
		assert.match(panel, /data-context="vergleich"/, 'CompareTabs uebergibt nicht context="vergleich"');
	});

	test('AC-12/AC-14: kein eigenes Vorschau-Markup mehr (eigenes iframe srcdoc, CompareSmsPreview)', async () => {
		const panel = await renderCompareVorschau();
		for (const alt of ['compare-preview-iframe', 'compare-preview-sms', 'compare-preview-sms-text', 'compare-preview-loading', 'compare-preview-empty']) {
			assert.equal(zaehle(panel, tid(alt)), 0, `CompareTabs rendert noch eigenes Vorschau-Markup (${alt})`);
		}
		const iframes = [...panel.matchAll(/<iframe\b[^>]*>/g)].map((m) => m[0]);
		assert.ok(
			iframes.every((f) => /data-testid="email-iframe"/.test(f)),
			`CompareTabs hat ein eigenes iframe neben dem geteilten: ${JSON.stringify(iframes)}`
		);
	});

	test('AC-13: kein Test-Senden-Knopf im Vorschau-Reiter des Ortsvergleichs', async () => {
		const panel = await renderCompareVorschau();
		assertKeinSendeKnopf(panel, 'CompareTabs/vorschau');
		assert.equal(zaehle(panel, tid('compare-send-success')), 0);
		assert.equal(zaehle(panel, tid('compare-send-error')), 0);
	});

	test('AC-13: auch der Versand-Reiter hat keinen Test-Senden-Knopf mehr (nur Hub-Kopf, #2278)', async () => {
		const CompareTabs = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/compare/CompareTabs.svelte')).href))
			.default;
		const html = render(CompareTabs, {
			props: { preset: vollerVergleich('cp-2283'), locations: [], initialTab: 'versand' }
		}).body;
		assert.ok(
			html.includes(tid('compare-detail-panel-versand')),
			'Vorbedingung: CompareTabs rendert mit initialTab="versand" den Versand-Reiter nicht (Reiter synchron aus initialTab initialisieren)'
		);
		const panel = html.slice(html.indexOf(tid('compare-detail-panel-versand')));
		assert.equal(zaehle(panel, tid('compare-hub-activation-testsend')), 0, 'Versand-Aktivierungskarte hat noch „Test-Briefing jetzt senden"');
		assert.deepEqual(knopfTexte(panel).filter((t) => /Test-Briefing/i.test(t)), []);
	});

	test('AC-14: CompareTabs laedt keinen entfernten Vorschau-Baustein (Modulgraph)', async () => {
		await renderCompareVorschau().catch(() => undefined);
		await new Promise((r) => setTimeout(r, 50));
		assert.ok(
			[...geladen].some((u) => u.endsWith('/compare/CompareTabs.svelte')),
			'Messaufbau: der Modul-Mitschnitt hat CompareTabs nicht gesehen'
		);
		const verboten = [...geladen].filter((u) =>
			/\/molecules\/(CompareSmsPreview|CompareBriefingPreview|ComparePreviewMissing)\.svelte$/.test(u)
		);
		assert.deepEqual(verboten, [], `CompareTabs laedt noch entfernte Bausteine: ${verboten.join(', ')}`);
	});
});
