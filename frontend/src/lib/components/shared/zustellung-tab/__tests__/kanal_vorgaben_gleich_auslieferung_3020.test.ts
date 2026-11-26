// Issue #3020 R1, AC-4 (Ersatz für das mit #3357 gelöschte versand_tab_defaults_gleich_auslieferung, #2422 S3 AC-25):
// Die Kanal-Vorgaben, die der Reiter Zustellung zeigt, sind die, die der Versand ausliefert — je Kanal (E-Mail,
// Telegram, SMS, Premium-SMS) und Kontext (route, vergleich).
//
// Kette ohne Nachbau: ECHTER Reiter (Instanz-Skript ZustellungTab.svelte) -> ECHTE KanalTabelle (Server-Render,
// sichtbarer Schalter) gegen die ECHTEN Python-Entscheider desselben gespeicherten Abos:
//   Trip  TripReportSchedulerService._resolve_channel_flags (nach load_trip_from_dict)
//   Orte  compare_alert_channels.effective_compare_briefing_channels
// Zwei Nutzer mit echten Profilen (user.json in eigener Datenwurzel): `gz3020-anna` (Premium) und `gz3020-bruno`
// (free, SMS und Premium-SMS nicht erlaubt); beide haben alle Kanäle verbunden. Orts-Abos im Go-Ladeformat
// (`alert_channels` gesetzt, #2293). Kein Mock. Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { register } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { REPO } from '../../wetter-tab/__tests__/wetterTabDaten.ts';
import * as P from '../../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';
import { KANAELE, kanalStatus, type KanalId, type ZustellungProfil } from '../zustellungModell.ts';

type Abo = Record<string, unknown>;
type Kontext = 'route' | 'vergleich';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../../..');
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const KanalTabelle = (await import(pathToFileURL(join(FRONTEND, 'src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte')).href)).default;

// ── Zwei Nutzer ─────────────────────────────────────────────────────────────
const NUTZER = { 'gz3020-anna': 'premium', 'gz3020-bruno': 'free' } as const;
type Nutzer = keyof typeof NUTZER;
const DATEN = mkdtempSync(join(tmpdir(), 'gz3020-'));
after(() => rmSync(DATEN, { recursive: true, force: true }));
for (const [id, tier] of Object.entries(NUTZER)) {
	mkdirSync(join(DATEN, 'users', id), { recursive: true });
	writeFileSync(join(DATEN, 'users', id, 'user.json'), JSON.stringify({ id, tier }));
}

// ── Gespeicherte Kanal-Felder (fehlend = Vorgabe) ────────────────────────────
const FAELLE: Record<string, Abo> = {
	'nichts gespeichert': {},
	'nur E-Mail gespeichert': { send_email: true },
	'ohne send_email': { send_telegram: false, send_sms: false, send_premium_sms: false },
	'E-Mail aus, sonst nichts': { send_email: false },
	'alle an': { send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true },
	'nur Telegram an': { send_email: false, send_telegram: true },
	'nur SMS an': { send_email: false, send_sms: true },
	'nur Premium-SMS an': { send_email: false, send_premium_sms: true }
};
const ALARM = { email: true, telegram: false, sms: false, premium_sms: false };
const ABO: Record<Kontext, (fall: string) => Abo> = {
	route: (f) => ({ id: 'gz3020-trip', name: 'Trip', stages: [], report_config: { enabled: true, ...FAELLE[f] } }),
	vergleich: (f) => ({ id: 'gz3020-ort', name: 'Orte', location_ids: [], morning_time: '07:00:00', display_config: {}, alert_channels: ALARM, ...FAELLE[f] })
};

const PY = `
import sys, json
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from app.config import Settings
from app.loader import load_trip_from_dict
from services.compare_alert_channels import effective_compare_briefing_channels
from services.trip_report_scheduler import TripReportSchedulerService
from services.user_tier import premium_sms_allowed, sms_allowed
K = json.loads(sys.stdin.read())
S = Settings(telegram_bot_token='t', telegram_chat_id='c', sms_gateway_url='u', seven_api_key='k', sms_to='+491')
KAN = ['email', 'telegram', 'sms', 'premium_sms']
aus = {"erlaubt": {}, "route": {}, "vergleich": {}}
for u in K["nutzer"]:
    aus["erlaubt"][u] = {"sms": sms_allowed(u), "premium_sms": premium_sms_allowed(u)}
    for f, roh in K["route"].items():
        e, s, p, t = TripReportSchedulerService._resolve_channel_flags(None, load_trip_from_dict(roh).report_config, u)
        aus["route"].setdefault(u, {})[f] = dict(zip(KAN, map(bool, (e, t, s, p))))
    for f, roh in K["vergleich"].items():
        c = effective_compare_briefing_channels(roh, S, u)
        aus["vergleich"].setdefault(u, {})[f] = {k: k in c for k in KAN}
print(json.dumps(aus))
`;
type Haken = Record<KanalId, boolean>;
const AUS: { erlaubt: Record<Nutzer, { sms: boolean; premium_sms: boolean }> } & Record<Kontext, Record<Nutzer, Record<string, Haken>>> = JSON.parse(
	execFileSync('uv', ['run', 'python3', '-c', PY], {
		cwd: REPO,
		env: { ...process.env, GZ_DATA_DIR: DATEN },
		input: JSON.stringify({
			nutzer: Object.keys(NUTZER),
			...Object.fromEntries((['route', 'vergleich'] as const).map((k) => [k, Object.fromEntries(Object.keys(FAELLE).map((f) => [f, ABO[k](f)]))]))
		}),
		encoding: 'utf-8',
		stdio: ['pipe', 'pipe', 'ignore']
	})
		.trim()
		.split('\n')
		.pop()!
);

/** Profil-Antwort eines Nutzers mit verbundenen Kanälen; die Tarif-Freigaben kommen aus dem Python-Kern. */
const profil = (u: Nutzer): ZustellungProfil =>
	({
		mail_to: 'a@example.invalid',
		email_verified: true,
		telegram_chat_id: '1',
		sms_to: '+491711234567',
		sms_verified: true,
		sms_allowed: AUS.erlaubt[u].sms,
		premium_sms_allowed: AUS.erlaubt[u].premium_sms,
		premium_sms_reply_state: 'fresh',
		premium_sms_reply_at: '2026-11-20T08:00:00Z'
	}) as ZustellungProfil;

/** Sichtbarer Briefing-Schalter je Kanal, aus dem echten Reiter über die echte KanalTabelle. */
async function gezeigt(kontext: Kontext, fall: string, u: Nutzer): Promise<Haken> {
	const abo = ABO[kontext](fall);
	const inst = await P.bauen(P.DATEI.zustellung, { ...P.LAUFZEIT, context: kontext, panel: kontext === 'route' ? { trip: abo } : { preset: abo } });
	const html = render(KanalTabelle, { props: { stand: inst.u.stand, status: kanalStatus(profil(u)), onaendern: () => {} } }).body;
	return Object.fromEntries(
		KANAELE.map((k) => {
			const tag = html.match(new RegExp(`<[^>]*data-testid="zustellung-kanal-${k}-briefing"[^>]*>`))?.[0];
			assert.ok(tag, `Schalter ${k} nicht gerendert`);
			const an = tag!.match(/aria-checked="(true|false)"/)?.[1];
			assert.ok(an, `Schalter ${k} ohne aria-checked: ${tag}`);
			return [k, an === 'true'];
		})
	) as Haken;
}

for (const kontext of ['route', 'vergleich'] as const)
	for (const u of Object.keys(NUTZER) as Nutzer[])
		describe(`${kontext}, ${u} (${NUTZER[u]}): gezeigte Kanal-Vorgabe gleich Auslieferung`, () => {
			for (const fall of Object.keys(FAELLE))
				for (const kanal of KANAELE)
					test(`kanal_vorgabe_gleich_auslieferung ${kontext} ${u} ${kanal}: ${fall}`, async () => {
						assert.equal((await gezeigt(kontext, fall, u))[kanal], AUS[kontext][u][fall][kanal]);
					});
		});

describe('Messaufbau', () => {
	test('beide Werte je Kanal und Kontext kommen vor, die zwei Nutzer unterscheiden sich', () => {
		for (const kontext of ['route', 'vergleich'] as const) {
			for (const k of KANAELE) assert.equal(new Set(Object.values(AUS[kontext]['gz3020-anna']).map((h) => h[k])).size, 2, `${kontext} ${k}`);
			assert.deepEqual(AUS[kontext]['gz3020-anna']['nichts gespeichert'], { email: true, telegram: false, sms: false, premium_sms: false });
			assert.notDeepEqual(AUS[kontext]['gz3020-anna']['alle an'], AUS[kontext]['gz3020-bruno']['alle an']);
		}
	});
});
