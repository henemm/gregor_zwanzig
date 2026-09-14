// TDD RED — Issue #2147 Scheibe B2 (Epic #2138), AC-17 (Teil Kontoseite):
// Hat ein bestaetigtes Konto eine ausstehende Adressaenderung
// (`data.profile.pending_contact_address`), zeigt die Kontoseite den Hinweis
// „Bestaetigung ausstehend fuer <neu> — bis dahin gehen Mails weiter an <alt>"
// und ein Bedienelement „Bestaetigungsmail erneut senden".
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §9, AC-17.
//
// Echtes serverseitiges Rendern der ECHTEN Route (svelte/server `render()`,
// Hooks: test-svelte-ssr-hooks.mjs + lokaler Stub fuer `$app/*` und die
// Runen-Module von bits-ui). Keine Mocks, kein Datei-Inhalt-Grep. Die
// Bedingung (`data.profile` traegt eine ausstehende Adresse) haengt nur an
// den Props, nicht an `onMount` — sie wird im SSR-Render also tatsaechlich
// ausgewertet (kein SSR-Vakuum). Messung vorab: die Seite rendert mit den
// unten gesetzten Daten fehlerfrei, `alt@beispiel.de` taucht dabei SCHON
// HEUTE zweimal auf (Eingabefeld `mail_to` + Uebersichts-Badge). Deshalb wird
// der Hinweis auf SEIN Element eingegrenzt, sonst waere die Zusicherung auf
// die alte Adresse falsch-gruen.
//
// Markup-Vertrag fuer /50 (einzige Vorgabe an die Form):
//   Der Hinweis steht in EINEM Element mit `data-testid="pending-address-notice"`.
//   Darin: Text „Bestaetigung ausstehend", neue Adresse, danach alte Adresse,
//   und ein <button> mit dem Text „Bestaetigungsmail erneut senden".
//   Ob der Knopf den Resend-Endpunkt wirklich ruft, ist im SSR nicht messbar
//   (Event-Handler laufen nicht) — das belegt nur `/e2e-verify` auf Staging.
//
// RED heute: `+page.svelte` kennt `pending_contact_address` nicht; es gibt
// weder das Element noch den Text.
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei aufgeloest.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/pending_address_notice.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

// Lokaler Stub zuerst, danach die geteilte Kette (.svelte-Kompilat + $lib).
register(
	pathToFileURL(path.join(HERE, 'app-navigation-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const AccountPage = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/routes/account/+page.svelte')).href)
).default;

const ALT = 'alt@beispiel.de';
const NEU = 'neu@beispiel.de';
const NOTICE_TESTID = 'pending-address-notice';

function profil(extra: Record<string, unknown>) {
	return {
		id: 'konto-ac17',
		display_name: 'Konto AC-17',
		email: ALT,
		mail_to: ALT,
		email_verified: true,
		tier: 'free',
		created_at: '2026-09-01T10:00:00Z',
		passkeys: [],
		...extra
	};
}

function renderAccount(profile: Record<string, unknown>): string {
	return render(AccountPage, {
		props: {
			data: {
				profile,
				scheduler: null,
				health: null,
				templates: [],
				trips: [],
				comparePresets: [],
				locations: [],
				metricPresets: []
			}
		}
	}).body;
}

/** Sichtbarer Text: Svelte-SSR-Kommentare und Tags entfernt, Leerraum verdichtet. */
function sichtbarerText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

/** Vollstaendiges Element (inkl. verschachtelter gleichnamiger Tags) zum testid. */
function elementByTestId(html: string, testid: string): string | null {
	const marker = html.indexOf(`data-testid="${testid}"`);
	if (marker === -1) return null;
	const start = html.lastIndexOf('<', marker);
	const tag = (html.slice(start).match(/^<([a-zA-Z0-9-]+)/) ?? [])[1];
	assert.ok(tag, `Kein Tag-Name fuer data-testid="${testid}" gefunden.`);
	const re = new RegExp(`<${tag}[\\s>]|</${tag}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) {
			tiefe -= 1;
			if (tiefe === 0) return html.slice(start, m.index + m[0].length);
		} else {
			tiefe += 1;
		}
	}
	assert.fail(`Element zu data-testid="${testid}" nicht geschlossen.`);
}

describe('#2147 Scheibe B2 AC-17 — Kontoseite zeigt ausstehende Adressaenderung', () => {
	test('ausstehende_adresse_zeigt_hinweis_mit_neuer_und_alter_adresse', () => {
		const html = renderAccount(profil({ pending_contact_address: NEU }));
		const hinweis = elementByTestId(html, NOTICE_TESTID);
		assert.ok(
			hinweis,
			`AC-17: bei pending_contact_address muss ein Element data-testid="${NOTICE_TESTID}" gerendert werden.`
		);
		const text = sichtbarerText(hinweis);
		assert.match(text, /Bestätigung ausstehend/, `AC-17: Hinweistext fehlt, bekommen: ${text}`);
		assert.ok(text.includes(NEU), `AC-17: neue Adresse fehlt im Hinweis, bekommen: ${text}`);
		assert.ok(text.includes(ALT), `AC-17: alte Adresse fehlt im Hinweis, bekommen: ${text}`);
		assert.ok(
			text.indexOf(NEU) < text.lastIndexOf(ALT),
			`AC-17: „ausstehend fuer <neu> — bis dahin weiter an <alt>": die neue Adresse muss vor der alten stehen, bekommen: ${text}`
		);
		assert.match(
			text,
			/weiter an\s+alt@beispiel\.de/,
			`AC-17: die alte Adresse muss als weiterhin belieferte Adresse benannt sein, bekommen: ${text}`
		);
	});

	test('ausstehende_adresse_bietet_knopf_bestaetigungsmail_erneut_senden', () => {
		const html = renderAccount(profil({ pending_contact_address: NEU }));
		const hinweis = elementByTestId(html, NOTICE_TESTID);
		assert.ok(hinweis, `AC-17: Element data-testid="${NOTICE_TESTID}" fehlt.`);
		const knoepfe = [...hinweis.matchAll(/<button[\s>][\s\S]*?<\/button>/g)].map((m) =>
			sichtbarerText(m[0])
		);
		assert.ok(
			knoepfe.some((k) => k.includes('Bestätigungsmail erneut senden')),
			`AC-17: im Hinweis fehlt ein <button> „Bestätigungsmail erneut senden", gefundene Knoepfe: ${JSON.stringify(knoepfe)}`
		);
	});

	// Gegenprobe: ohne ausstehende Adresse darf der Hinweis nicht erscheinen —
	// sonst waere ein bedingungslos gerenderter Hinweis gruen.
	test('ohne_ausstehende_adresse_kein_hinweis', () => {
		const html = renderAccount(profil({}));
		assert.equal(
			elementByTestId(html, NOTICE_TESTID),
			null,
			'AC-17 Gegenprobe: ohne pending_contact_address darf kein Hinweis-Element erscheinen.'
		);
		const text = sichtbarerText(html);
		assert.ok(!/Bestätigung ausstehend/.test(text), 'AC-17 Gegenprobe: Hinweistext darf nicht erscheinen.');
		assert.ok(
			!text.includes('Bestätigungsmail erneut senden'),
			'AC-17 Gegenprobe: Resend-Knopf darf ohne ausstehende Adresse nicht erscheinen.'
		);
	});

	test('leere_ausstehende_adresse_gilt_als_keine', () => {
		const html = renderAccount(profil({ pending_contact_address: '' }));
		assert.equal(
			elementByTestId(html, NOTICE_TESTID),
			null,
			'AC-17 Gegenprobe: ein leerer pending_contact_address ist keine ausstehende Aenderung.'
		);
	});
});
