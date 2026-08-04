// TDD RED — Bugfix "Sende-Dialog nennt das tatsaechliche Versandziel".
// Spec: docs/specs/modules/fix_1471_sende_dialog_ziel.md — AC-1, AC-2, AC-3, AC-4, AC-6.
//
// Verhaltenstests der neuen geteilten Ableitung `sendTargetLabel(profile, preset)`.
// Reine Funktion, kein Netz, kein DOM, keine Attrappe — der Prueflig wird echt
// aufgerufen und sein Rueckgabewert bewertet.
//
// RED heute: `../sendTargetLabel.ts` existiert nicht (ERR_MODULE_NOT_FOUND),
// der Dialog rechnet stattdessen `sendTarget?.empfaenger?.length ?? 0`.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/sendTargetLabel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { sendTargetLabel } from '../sendTargetLabel.ts';
import { channelConnectionStatus } from '../channelConnectionStatus.ts';

const MAIL = 'anna@example.org';

describe('AC-1: der Dialog nennt die bestaetigte Konto-Adresse statt einer Zaehlung', () => {
	test('bestaetigte Adresse, keine Zusatzkanaele → Adresse im Text, zustellbar', () => {
		const ziel = sendTargetLabel({ mail_to: MAIL, email_verified: true }, {});

		assert.equal(
			ziel.deliverable,
			true,
			'Eine hinterlegte UND bestaetigte Adresse ist zustellbar — der Versand muss ' +
				'ausloesbar bleiben (AC-1).'
		);
		assert.ok(
			ziel.text.includes(MAIL),
			`Der Ziel-Text nennt die Konto-Adresse nicht. Ist: "${ziel.text}" (AC-1).`
		);
	});

	test('Der Ziel-Text enthaelt in keiner Konstellation eine Empfaenger-Zaehlung', () => {
		const faelle = [
			[{ mail_to: MAIL, email_verified: true }, {}],
			[{ mail_to: MAIL, email_verified: false }, {}],
			[{}, {}],
			[{ mail_to: MAIL, email_verified: true, telegram_chat_id: '4711' }, { send_telegram: true }]
		] as const;

		for (const [profil, preset] of faelle) {
			const { text } = sendTargetLabel(profil, preset);
			assert.doesNotMatch(
				text,
				/\d+\s*Empf(ä|ae)nger/i,
				`Der Ziel-Text zaehlt weiterhin Empfaenger: "${text}". Das Legacy-Feld ist seit ` +
					'#1452 dauerhaft leer — die Zahl ist immer falsch (AC-1).'
			);
		}
	});
});

describe('AC-2: Zusatzkanaele nur, wenn im Vergleich aktiviert UND im Konto hinterlegt', () => {
	test('(a) Telegram aktiviert und Chat-ID hinterlegt → Telegram steht im Ziel-Text', () => {
		const { text, deliverable } = sendTargetLabel(
			{ mail_to: MAIL, email_verified: true, telegram_chat_id: '4711' },
			{ send_telegram: true }
		);
		assert.equal(deliverable, true);
		assert.match(
			text,
			/telegram/i,
			`Telegram ist aktiviert und hinterlegt, fehlt aber im Ziel-Text: "${text}" (AC-2a).`
		);
	});

	test('(b) Telegram aktiviert, aber KEINE Chat-ID → Telegram fehlt, E-Mail bleibt', () => {
		const { text } = sendTargetLabel(
			{ mail_to: MAIL, email_verified: true },
			{ send_telegram: true }
		);
		assert.doesNotMatch(
			text,
			/telegram/i,
			`Der Ziel-Text nennt Telegram, obwohl im Konto keine Chat-ID hinterlegt ist: "${text}". ` +
				'Das waere die Falschaussage aus #1471 in neuer Form (AC-2b).'
		);
		assert.ok(text.includes(MAIL), `E-Mail fehlt im Ziel-Text: "${text}" (AC-2b).`);
	});

	test('(c) SMS aktiviert und Nummer erlaubt hinterlegt → SMS steht im Ziel-Text', () => {
		const { text } = sendTargetLabel(
			{ mail_to: MAIL, email_verified: true, sms_to: '+49150000000', sms_allowed: true },
			{ send_sms: true }
		);
		assert.match(text, /sms/i, `SMS ist aktiviert und hinterlegt, fehlt aber: "${text}" (AC-2c).`);
	});

	test('(d) SMS aktiviert, aber Tier verbietet den Versand → SMS fehlt im Ziel-Text', () => {
		const { text } = sendTargetLabel(
			{ mail_to: MAIL, email_verified: true, sms_to: '+49150000000', sms_allowed: false },
			{ send_sms: true }
		);
		assert.doesNotMatch(
			text,
			/sms/i,
			`Der Ziel-Text nennt SMS, obwohl das Konto sie nicht senden darf: "${text}" (AC-2d).`
		);
	});

	test('(e) Kanaele NICHT im Vergleich aktiviert → nicht genannt, obwohl hinterlegt', () => {
		const { text } = sendTargetLabel(
			{
				mail_to: MAIL,
				email_verified: true,
				telegram_chat_id: '4711',
				sms_to: '+49150000000',
				sms_allowed: true
			},
			{}
		);
		assert.doesNotMatch(text, /telegram/i, `Telegram genannt, obwohl im Vergleich aus: "${text}".`);
		assert.doesNotMatch(text, /sms/i, `SMS genannt, obwohl im Vergleich aus: "${text}".`);
	});

	// (e) laesst die Flags WEG (undefined). Der Normalfall nach dem Abwaehlen im Editor
	// ist aber ein explizites `false`: `SendTelegram *bool json:"send_telegram,omitempty"`
	// (internal/model/compare_preset.go:91) — der Pointer ist non-nil, `false` ueberlebt
	// omitempty. Ohne die beiden Faelle bliebe `=== true` gegen `!== undefined`
	// austauschbar, und ein abgewaehlter Kanal erschiene wieder im Ziel-Text.
	test('(f) Telegram im Vergleich ABGEWAEHLT (false) trotz Chat-ID → nicht genannt', () => {
		const { text } = sendTargetLabel(
			{ mail_to: MAIL, email_verified: true, telegram_chat_id: '4711' },
			{ send_telegram: false }
		);
		assert.doesNotMatch(
			text,
			/telegram/i,
			`Der Ziel-Text nennt Telegram, obwohl der Kanal im Vergleich abgewaehlt ist ` +
				`(send_telegram: false): "${text}" (AC-2f).`
		);
		assert.ok(text.includes(MAIL), `E-Mail fehlt im Ziel-Text: "${text}" (AC-2f).`);
	});

	test('(g) SMS im Vergleich ABGEWAEHLT (false) trotz hinterlegter Nummer → nicht genannt', () => {
		const { text } = sendTargetLabel(
			{ mail_to: MAIL, email_verified: true, sms_to: '+49150000000', sms_allowed: true },
			{ send_sms: false }
		);
		assert.doesNotMatch(
			text,
			/sms/i,
			`Der Ziel-Text nennt SMS, obwohl der Kanal im Vergleich abgewaehlt ist ` +
				`(send_sms: false): "${text}" (AC-2g).`
		);
	});
});

describe('AC-3 / AC-4: nicht zustellbare Zustaende sperren und erklaeren sich unterschiedlich', () => {
	test('AC-3: keine Adresse hinterlegt → nicht zustellbar, Text erklaert das Fehlen', () => {
		const { text, deliverable } = sendTargetLabel({}, {});

		assert.equal(
			deliverable,
			false,
			'Ohne Konto-Adresse wirft der Server "kein Empfaenger — mail_to fehlt" ' +
				'(scheduler_dispatch_service.py:336-340) — der Versand darf nicht ausloesbar sein (AC-3).'
		);
		assert.match(
			text,
			/fehlt|keine|nicht hinterlegt/i,
			`Der Text erklaert das Fehlen der Adresse nicht: "${text}" (AC-3).`
		);
		assert.doesNotMatch(
			text,
			/best(ä|ae)tigt/i,
			`Der Text spricht von Bestaetigung, obwohl gar keine Adresse hinterlegt ist: "${text}" ` +
				'— AC-3 und AC-4 muessen sich sichtbar unterscheiden.'
		);
	});

	test('AC-4: Adresse hinterlegt, aber nicht bestaetigt → gesperrt, Text nennt "nicht bestaetigt"', () => {
		const { text, deliverable } = sendTargetLabel({ mail_to: MAIL, email_verified: false }, {});

		assert.equal(
			deliverable,
			false,
			'Bei unbestaetigter Adresse blockt der Empfaengerschutz die Zustellung ' +
				'(email.py:239-285, Guard :440-447) — ein Knopf, der nichts bewirkt, waere #1471 ' +
				'mit umgekehrtem Vorzeichen (AC-4).'
		);
		assert.match(
			text,
			/nicht best(ä|ae)tigt/i,
			`Der Text nennt den Zwischenzustand "nicht bestaetigt" nicht: "${text}" (AC-4).`
		);
	});

	test('AC-3 und AC-4 liefern sichtbar verschiedene Texte', () => {
		const ohne = sendTargetLabel({}, {}).text;
		const unbestaetigt = sendTargetLabel({ mail_to: MAIL, email_verified: false }, {}).text;
		assert.notEqual(
			ohne,
			unbestaetigt,
			'Fehlende und unbestaetigte Adresse erzeugen denselben Text — der Nutzer kann die ' +
				'beiden Ursachen nicht auseinanderhalten (AC-3/AC-4).'
		);
	});
});

// Das Feld, das im Dialog DIREKT an `disabled` gebunden wird. Seine Bedeutung wird
// hier geprueft — im Template ist nur noch ein nackter Feldzugriff erlaubt, dort ist
// also nichts mehr zu bewerten. Ohne diese Faelle waere `gesperrt: !deliverable` gegen
// `gesperrt: deliverable` austauschbar und der Knopf spraeche das Gegenteil des Textes.
describe('AC-3 / AC-4: `gesperrt` steuert den Knopf und ist die Umkehrung von `deliverable`', () => {
	const FAELLE = [
		{ name: 'keine Adresse hinterlegt (AC-3)', profil: {}, preset: {}, gesperrt: true },
		{
			name: 'Adresse hinterlegt, nicht bestaetigt (AC-4)',
			profil: { mail_to: MAIL, email_verified: false },
			preset: {},
			gesperrt: true
		},
		{
			name: 'Adresse bestaetigt (AC-1)',
			profil: { mail_to: MAIL, email_verified: true },
			preset: {},
			gesperrt: false
		},
		{
			name: 'bestaetigt mit Zusatzkanal (AC-2a)',
			profil: { mail_to: MAIL, email_verified: true, telegram_chat_id: '4711' },
			preset: { send_telegram: true },
			gesperrt: false
		}
	];

	for (const fall of FAELLE) {
		test(`${fall.name} → gesperrt === ${fall.gesperrt}`, () => {
			const ziel = sendTargetLabel(fall.profil, fall.preset);
			assert.equal(
				ziel.gesperrt,
				fall.gesperrt,
				`\`gesperrt\` ist ${ziel.gesperrt}, erwartet ${fall.gesperrt}. Der Bestaetigen-Knopf ` +
					`spraeche damit das Gegenteil des Ziel-Textes ("${ziel.text}") (AC-3/AC-4).`
			);
			assert.equal(
				ziel.gesperrt,
				!ziel.deliverable,
				`\`gesperrt\` (${ziel.gesperrt}) ist nicht die Umkehrung von \`deliverable\` ` +
					`(${ziel.deliverable}) — Text und Sperre laufen auseinander (AC-3/AC-4).`
			);
		});
	}
});

describe('AC-6: der Ziel-Text widerspricht dem Verbindungsstatus des Versand-Reiters nicht', () => {
	const TABELLE = [
		{
			name: 'alle Kanaele hinterlegt',
			profil: {
				mail_to: MAIL,
				email_verified: true,
				telegram_chat_id: '4711',
				sms_to: '+49150000000',
				sms_allowed: true
			},
			preset: { send_telegram: true, send_sms: true }
		},
		{
			name: 'Telegram aktiviert ohne Chat-ID',
			profil: { mail_to: MAIL, email_verified: true },
			preset: { send_telegram: true }
		},
		{
			name: 'SMS aktiviert, sms_allowed false',
			profil: { mail_to: MAIL, email_verified: true, sms_to: '+49150000000', sms_allowed: false },
			preset: { send_sms: true }
		},
		{
			name: 'nur E-Mail, nichts sonst hinterlegt',
			profil: { mail_to: MAIL, email_verified: true },
			preset: { send_telegram: true, send_sms: true }
		},
		{
			name: 'gar nichts hinterlegt',
			profil: {},
			preset: { send_telegram: true, send_sms: true }
		}
	];

	// Erkennungsmarken je Kanal im Ziel-Text. Fuer E-Mail wird die Adresse
	// gesucht (das Wort "E-Mail" darf auch in der Fehl-Erklaerung stehen).
	const MARKE: Record<string, RegExp> = {
		telegram: /telegram/i,
		sms: /sms/i,
		email: /@/
	};

	test('kein Kanal mit Status "nicht verbunden" kommt im Ziel-Text vor', () => {
		let geprueft = 0;
		const verstoesse: string[] = [];

		for (const zeile of TABELLE) {
			const { text } = sendTargetLabel(zeile.profil, zeile.preset);
			const status = channelConnectionStatus(zeile.profil);

			for (const kanal of ['email', 'telegram', 'sms'] as const) {
				if (status[kanal].label !== 'nicht verbunden') continue;
				geprueft += 1;
				if (MARKE[kanal].test(text)) {
					verstoesse.push(`[${zeile.name}] Kanal ${kanal} → Ziel-Text: "${text}"`);
				}
			}
		}

		assert.ok(
			geprueft >= 5,
			`Die Tabelle erzeugt nur ${geprueft} "nicht verbunden"-Faelle — bei zu wenigen ` +
				'Faellen waere die Behauptung fast leer und damit wertlos (AC-6).'
		);
		assert.deepEqual(
			verstoesse,
			[],
			'Der Ziel-Text nennt Kanaele, die der Versand-Reiter als "nicht verbunden" fuehrt — ' +
				`die beiden Ansichten widersprechen sich (AC-6):\n${verstoesse.join('\n')}`
		);
	});
});
