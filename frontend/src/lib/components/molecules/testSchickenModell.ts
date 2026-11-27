// Issue #3440 (S5a, Scheibe #2797) — Zeilenmodell und Rückmeldungen des Menüs „Test schicken ▾“.
// Spec: docs/specs/modules/feat_3440_test_schicken_menue.md (Implementation Details „Frontend“).
//
// Reine Funktionen für Trip (`context="route"`) und Orte (`context="vergleich"`), EIN Code (ADR-0097).
// Bedienbar/gesperrt, Grund und Konto-Verb kommen ausschließlich aus `kanalStatus(profil)` (#3202);
// einzige Abweichung: eine unbestätigte E-Mail-Adresse ist im Menü gesperrt (ADR-0092), in der
// Zustellung bleibt sie bedienbar mit Warnpunkt. Texte nur über den Katalog in der aktuellen Sprache.
// Kein Netz-/DOM-Zugriff — node:testbar.

import { tr, type MessageKey } from '../../i18n/index.ts';
import {
	KANAELE,
	KANAL_NAME_KEYS,
	kanalStatus,
	standAusPreset,
	standAusTrip,
	type KanalId,
	type KanalStatus,
	type KontoVerb,
	type ZustellungProfil
} from '../shared/zustellung-tab/zustellungModell.ts';
import type { ComparePreset, Trip } from '../../types.ts';

export type Berichtsart = 'morning' | 'evening';
export type TestKanal = KanalId | 'alle';
export type TestKontext = 'route' | 'vergleich';
/** Abo-Kanalstand des Briefings: welche Kanäle im Abo eingeschaltet sind (Zustellung-Tab, #2795). */
export type AboKanaele = Record<KanalId, boolean>;

/** Rückmeldedauer der Seite nach einem Klick im Menü (AC-11), EINE Quelle für Trip und Orte. */
export const RUECKMELDUNG_MS = 5000;
/** Vorauswahl der Berichtsart bei jedem Öffnen des Menüs (AC-2). */
export const BERICHTSART_START: Berichtsart = 'morning';

export interface TestZeile {
	kanal: KanalId;
	name: string;
	bedienbar: boolean;
	ziel: string;
	grund: string | null;
	sperrText: string | null;
	kontoLink: null | { verb: KontoVerb; text: string; href: '/account' };
}

export interface TestMenueModell {
	segment: null | { wert: Berichtsart; optionen: { wert: Berichtsart; text: string }[] };
	zeilen: TestZeile[];
	alle: { text: string };
	/** Slot nach dem Trenner unter „Alle“: der Test-Alarm (#3441); gesperrt, solange er läuft. */
	erweiterungen: TestErweiterung[];
}

export interface TestErweiterung {
	id: 'test-alarm';
	text: string;
	untertitel: string;
	bedienbar: boolean;
}

const BERICHTSART_KEYS: Record<Berichtsart, MessageKey> = {
	morning: 'trip.briefing.morgen',
	evening: 'trip.briefing.abend'
};

/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren): Trip mit Segment und
 *  Segment-Namen, Orte ohne Segment mit neutralem „Briefing“ (Glossar). */
const KONTEXT: Record<
	TestKontext,
	{ segment: boolean; briefingKey: (b: Berichtsart) => MessageKey; abo: (q: Trip | ComparePreset) => AboKanaele }
> = {
	route: { segment: true, briefingKey: (b) => BERICHTSART_KEYS[b], abo: (q) => standAusTrip(q as Trip).briefing },
	vergleich: {
		segment: false,
		briefingKey: () => 'test_schicken.briefing',
		abo: (q) => standAusPreset(q as ComparePreset).briefing
	}
};

/** Abo-Kanalstand aus derselben Quelle wie der Zustellung-Tab (standAusTrip / standAusPreset). */
export function aboKanaele(context: TestKontext, quelle: Trip | ComparePreset): AboKanaele {
	return KONTEXT[context].abo(quelle);
}

/** Zustand des Menüs beim Öffnen/Schließen: geöffnet ⇒ Vorauswahl Morgen, sonst unverändert (AC-2). */
export function berichtsartBeiOffen(offen: boolean, aktuell: Berichtsart): Berichtsart {
	return offen ? BERICHTSART_START : aktuell;
}

/** Ziel einer bedienbaren Zeile: E-Mail/SMS gekürzt aus kanalStatus, Telegram nur „verbunden“ (#3202). */
function zielVon(s: KanalStatus): string {
	if (s.kanal === 'telegram') return tr('zustellung.status.verbunden');
	if (s.kanal === 'premium_sms') return tr('test_schicken.ziel.premium_sms');
	return s.ziel;
}

/** ADR-0092: Testmail nur an eine bestätigte Adresse — Sperre nur im Menü, nicht in der Zustellung. */
function emailUnbestaetigt(profil: ZustellungProfil | null | undefined, s: KanalStatus): boolean {
	return s.kanal === 'email' && !s.briefingGesperrt && profil?.email_verified !== true;
}

function zeileAus(profil: ZustellungProfil | null | undefined, s: KanalStatus): TestZeile {
	const name = tr(KANAL_NAME_KEYS[s.kanal]);
	if (emailUnbestaetigt(profil, s)) {
		const grund = tr('test_schicken.grund.email_unbestaetigt');
		return {
			kanal: s.kanal,
			name,
			bedienbar: false,
			ziel: '',
			grund,
			sperrText: tr('zustellung.gesperrt', { grund }),
			kontoLink: { verb: 'bestaetigen', text: tr('zustellung.konto.bestaetigen'), href: '/account' }
		};
	}
	if (s.briefingGesperrt) {
		const grund = s.grund ?? '';
		return {
			kanal: s.kanal,
			name,
			bedienbar: false,
			ziel: '',
			grund: s.grund,
			sperrText: tr('zustellung.gesperrt', { grund }),
			kontoLink: s.kontoLink ? { ...s.kontoLink, href: '/account' } : null
		};
	}
	return { kanal: s.kanal, name, bedienbar: true, ziel: zielVon(s), grund: null, sperrText: null, kontoLink: null };
}

export function testMenueModell(
	profil: ZustellungProfil | null | undefined,
	context: TestKontext,
	berichtsart: Berichtsart = BERICHTSART_START,
	optionen: { alarmLaeuft?: boolean } = {}
): TestMenueModell {
	const status = kanalStatus(profil);
	return {
		segment: KONTEXT[context].segment
			? {
					wert: berichtsart,
					optionen: (['morning', 'evening'] as const).map((wert) => ({ wert, text: tr(BERICHTSART_KEYS[wert]) }))
				}
			: null,
		zeilen: KANAELE.map((k) => zeileAus(profil, status[k])),
		alle: { text: tr('test_schicken.alle') },
		erweiterungen: [
			{
				id: 'test-alarm',
				text: tr('test_schicken.test_alarm.titel'),
				untertitel: tr('test_schicken.test_alarm.untertitel'),
				bedienbar: optionen.alarmLaeuft !== true
			}
		]
	};
}

/** „Morgen-Briefing“/„Abend-Briefing“ beim Trip, neutrales „Briefing“ bei Orten (Glossar). */
function briefingName(context: TestKontext, berichtsart: Berichtsart): string {
	return tr(KONTEXT[context].briefingKey(berichtsart));
}

const zweistellig = (n: number) => String(n).padStart(2, '0');

/** „{Briefing} an {Kanal} geschickt · {Ziel} · {hh:mm}“ — Uhr = Client-Zeit `jetzt` (lokal). */
export function einzelRueckmeldung(p: {
	context: TestKontext;
	berichtsart: Berichtsart;
	kanal: KanalId;
	ziel: string;
	jetzt: Date;
}): string {
	return tr('test_schicken.rueckmeldung.einzel', {
		briefing: briefingName(p.context, p.berichtsart),
		kanal: tr(KANAL_NAME_KEYS[p.kanal]),
		ziel: p.ziel,
		zeit: `${zweistellig(p.jetzt.getHours())}:${zweistellig(p.jetzt.getMinutes())}`
	});
}

/** Grund „übersprungen ({Grund})“ = letzter Teil des Statustexts aus kanalStatus. */
const letzterTeil = (statusText: string) => statusText.split(' · ').pop() ?? statusText;

/** „{Briefing} geschickt: E-Mail ✓ · Telegram übersprungen ({Grund}) · SMS fehlgeschlagen · …“ (AC-10).
 *  ✓ = in sentChannels; gesperrt ⇒ übersprungen mit Grund aus kanalStatus; bedienbar, aber im Abo aus ⇒
 *  übersprungen (im Briefing aus); „fehlgeschlagen“ nur, wenn im Abo an, bedienbar und nicht gesendet. */
export function alleRueckmeldung(p: {
	context: TestKontext;
	berichtsart: Berichtsart;
	sentChannels: KanalId[];
	profil: ZustellungProfil | null | undefined;
	abo: AboKanaele;
}): string {
	const status = kanalStatus(p.profil);
	const zeilen = testMenueModell(p.profil, p.context, p.berichtsart).zeilen;
	const teile = zeilen.map((z) => {
		if (p.sentChannels.includes(z.kanal)) return tr('test_schicken.rueckmeldung.gesendet', { kanal: z.name });
		if (!z.bedienbar) {
			return tr('test_schicken.rueckmeldung.uebersprungen', { kanal: z.name, grund: letzterTeil(status[z.kanal].statusText) });
		}
		if (p.abo[z.kanal] !== true) {
			return tr('test_schicken.rueckmeldung.uebersprungen', { kanal: z.name, grund: tr('test_schicken.grund.im_briefing_aus') });
		}
		return tr('test_schicken.rueckmeldung.fehlgeschlagen', { kanal: z.name });
	});
	return tr('test_schicken.rueckmeldung.alle', { briefing: briefingName(p.context, p.berichtsart), liste: teile.join(' · ') });
}

/** Rückmeldung der Seite nach einem Klick im Menü — Trip und Orte gleich (AC-10 bis AC-12).
 *  Fehler: der bestehende Text aus `fehler.versand.*` bzw. vom Server; Erfolg: Einzel- oder Alle-Text,
 *  ein Hinweis des Versands (z. B. fehlende Orte, #2216) wird angehängt. */
export function testErgebnis(p: {
	context: TestKontext;
	wahl: { kanal: TestKanal; berichtsart: Berichtsart };
	ergebnis: { kind: string; message: string; sentChannels?: KanalId[] };
	profil: ZustellungProfil | null | undefined;
	abo: AboKanaele;
	jetzt: Date;
}): { ok: boolean; text: string } {
	const { context, wahl, ergebnis, profil, abo } = p;
	if (ergebnis.kind !== 'ok') return { ok: false, text: ergebnis.message };
	const text =
		wahl.kanal === 'alle'
			? alleRueckmeldung({ context, berichtsart: wahl.berichtsart, sentChannels: ergebnis.sentChannels ?? [], profil, abo })
			: einzelRueckmeldung({
					context,
					berichtsart: wahl.berichtsart,
					kanal: wahl.kanal,
					ziel: testMenueModell(profil, context).zeilen.find((z) => z.kanal === wahl.kanal)?.ziel ?? '',
					jetzt: p.jetzt
				});
	return { ok: true, text: ergebnis.message ? `${text} · ${ergebnis.message}` : text };
}

/** Kanal mit Grund aus der Antwort des Test-Alarms (#3441). */
type KanalGrund = { channel: string; reason: string };

/** Rückmeldung des Test-Alarms (#3441, AC-7 bis AC-9) — Trip und Orte gleich, Vokabular von #3440:
 *  „Test-Alarm geschickt: E-Mail ✓ · Telegram übersprungen ({Grund}) · SMS fehlgeschlagen · {hh:mm}“,
 *  Kanäle in der Reihenfolge der Menüzeilen. Leere Kanalmenge ⇒ Leer-Text, sonst der Fehlertext. */
export function testAlarmErgebnis(p: {
	ergebnis: {
		kind: string;
		message: string;
		code?: string;
		sentChannels?: string[];
		skippedChannels?: KanalGrund[];
		failedChannels?: KanalGrund[];
	};
	jetzt: Date;
}): { ok: boolean; text: string } {
	const e = p.ergebnis;
	if (e.kind !== 'ok') {
		return { ok: false, text: e.code === 'keine_alarm_kanaele' ? tr('test_schicken.test_alarm.leer') : e.message };
	}
	const teile = KANAELE.flatMap((k) => {
		const kanal = tr(KANAL_NAME_KEYS[k]);
		if (e.sentChannels?.includes(k)) return [tr('test_schicken.rueckmeldung.gesendet', { kanal })];
		const uebersprungen = e.skippedChannels?.find((s) => s.channel === k);
		if (uebersprungen) return [tr('test_schicken.rueckmeldung.uebersprungen', { kanal, grund: uebersprungen.reason })];
		if (e.failedChannels?.some((f) => f.channel === k)) return [tr('test_schicken.rueckmeldung.fehlgeschlagen', { kanal })];
		return [];
	});
	const zeit = `${zweistellig(p.jetzt.getHours())}:${zweistellig(p.jetzt.getMinutes())}`;
	return { ok: true, text: tr('test_schicken.rueckmeldung.test_alarm', { liste: teile.join(' · '), zeit }) };
}
