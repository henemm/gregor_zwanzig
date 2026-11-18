// Issue #3122 B3a — Beispieldaten der Vorschauseite /_design-system/einstelltabelle.
// Werte und Wortlaut aus dem Soll-Bild Fassung 4 (docs/context/einstellungen_neu/seiten/
// mockup-hub-fassung4.html, echte Renderer-Ausgabe vom 17.11.2026). Roh/Einfach je Stelle nach der Spec
// (Teil A Nr. 4): Gewitter nur in der E-Mail, Regenwahrscheinlichkeit mit zwei Formen.
// Nur Vorschau: die echte Karte bekommt alles vom Endpoint (Scheibe B3).
import type { EinstellFesteZeile, EinstellMetrik, EinstellStelle, EinstellZelle } from '$lib/components/molecules';

export type Flaeche = 'trip' | 'orte';
type Form = 'raw' | 'simplified';

export const FESTE_ZEILE: EinstellFesteZeile = {
	name: 'Amtliche Warnungen',
	hinweis: 'immer dabei: in E-Mail und Telegram zuerst, in der SMS am Ende',
	grund: 'immer dabei',
	stellen: ['email', 'telegram', 'sms']
};

export function stellen(flaeche: Flaeche, kurzstil: boolean): EinstellStelle[] {
	const orte = flaeche === 'orte';
	const liste: EinstellStelle[] = [
		{ id: 'email', titel: 'E-Mail', unterzeile: orte ? 'Übersicht' : 'Stundentabelle', zellenName: (m) => `${m} in E-Mail` },
		{ id: 'telegram', titel: 'Telegram', titelKurz: orte ? 'Telegr.' : 'Telegram', unterzeile: kurzstil ? 'Kurzstil: wie SMS' : 'Nachricht', bedienbar: !kurzstil, zellenName: (m) => `${m} in Telegram` },
		{ id: 'sms', titel: 'SMS', unterzeile: 'und Premium-SMS', zellenName: (m) => `${m} in SMS` }
	];
	if (orte) liste.push({ id: 'hourly', titel: 'Stundenverlauf', titelKurz: 'Std.', unterzeile: 'nur E-Mail', abgesetzt: true, schmal: true, zellenName: (m) => `${m} im Stundenverlauf` });
	liste.push({ id: 'outlook', titel: '3-Tages-Ausblick', titelKurz: 'Ausbl.', unterzeile: 'E-Mail und Telegram', abgesetzt: true, schmal: true, zellenName: (m) => `${m} im 3-Tages-Ausblick` });
	return liste;
}

const an = (beispiel?: string, format?: Form): EinstellZelle => ({ zustand: 'on', beispiel, format: format ?? null });
const PASST_NICHT = { text: 'passt nicht mehr', ton: 'warn' } as const;
const NUR_TAGESWERT = { text: 'nur Tageswert', ton: 'leise' } as const;

/** Orte „Münsterland“, Ort Münster am 18.11.2026. `gemischt` zeigt abgewählte und abgeleitete Zustände. */
export function orteMetriken(gemischt = false): EinstellMetrik[] {
	const zeile = (id: string, name: string, mail: string, tg: string, sms: string, form?: Form, passt = false, nurMail = false): EinstellMetrik => ({
		id,
		name,
		zellen: {
			email: an(mail, form),
			telegram: an(tg, nurMail ? undefined : form),
			sms: { ...an(sms), marke: passt ? PASST_NICHT : undefined },
			hourly: an(undefined, nurMail ? undefined : form),
			outlook: an(undefined, nurMail ? undefined : form)
		}
	});
	const liste = [
		zeile('temperature', 'Temperatur', '13°C / 4°C', 'Temp max 13°C · Temp min 4°C', 'D 13C L 4C'),
		zeile('wind', 'Wind', '30 km/h', 'Wind 30 km/h', 'W 30 km/h', 'raw'),
		zeile('gust', 'Böen', '51 km/h', 'Böen 51 km/h', 'G 51 km/h', 'raw'),
		zeile('precipitation', 'Niederschlag', '1.8 mm', 'Regen 1.8 mm', 'R 1.8 mm', 'raw', true),
		zeile('thunder', 'Gewitter', '–', 'Gewitter –', 'TH -', 'simplified', true, true),
		zeile('rain_probability', 'Regenwahrscheinlichkeit', '60%', 'Regenwahrscheinlichkeit 60%', 'PR 60%', 'raw', true),
		zeile('cloud_total', 'Bewölkung', '70%', 'Wolken 70%', 'CT 70%', 'simplified', true),
		zeile('sunshine', 'Sonnenstunden', '3.0 h', 'Sonne 3.0h', 'SU 3.0h', 'simplified', true)
	];
	liste[7].zellen.hourly = { zustand: 'locked', grund: 'kein Stundenwert' };
	if (gemischt) {
		liste[1].zellen.telegram.zustand = 'off';
		liste[2].zellen.email.zustand = 'off';
		liste[2].zellen.hourly = { zustand: 'not_in_email', grund: 'nicht in der E-Mail' };
		liste[2].zellen.outlook = { zustand: 'not_in_email', grund: 'nicht in der E-Mail' };
		liste[6].zellen.outlook.zustand = 'off';
	}
	return liste;
}

/** Trip „GR221 Mallorca“, Etappe 2 am 24.02.2026, Abend-Briefing. */
export function tripMetriken(): EinstellMetrik[] {
	const zeile = (id: string, name: string, mail: string, tg: string, sms: string, form?: Form, tageswert = false, nurMail = false): EinstellMetrik => ({
		id,
		name,
		zellen: {
			email: an(mail, form),
			telegram: { ...an(tg, nurMail ? undefined : form), marke: tageswert ? NUR_TAGESWERT : undefined },
			sms: an(sms),
			outlook: an(undefined, nurMail ? undefined : form)
		}
	});
	const liste = [
		zeile('temperature', 'Temperatur', 'Temp 14.4', 'T 9.6-15.2', 'D10/15'),
		zeile('temperature_night', 'Tiefsttemperatur Nacht', '', '', 'N10'),
		zeile('wind_chill', 'Gefühlte Temperatur', 'Feels 11.0', 'TF 6.8-11.7', 'TF- FN7 FD7/12'),
		zeile('wind', 'Wind', 'Wind 36', 'W 20-38@15', 'W30@10(38@15)', 'raw'),
		zeile('gust', 'Böen', 'Gust 50', 'G 30-52@15', 'G36@7(52@15)', 'raw'),
		zeile('precipitation', 'Niederschlag', 'Rain 0.4', 'R 0.0-0.4', 'R-', 'raw'),
		zeile('thunder', 'Gewitter', 'Thdr ● gelb', 'TH leicht', 'TH:L@13 TH+:-', 'simplified', false, true),
		zeile('rain_probability', 'Regenwahrscheinlichkeit', 'Rain% 60', 'PR 10-60@14', 'PR60%@14', 'raw'),
		zeile('visibility', 'Sichtweite', 'Visib 4.0', 'VS 4.0-15', 'VS-', undefined, true),
		zeile('cloud_low', 'Tiefe Wolken', 'CldLow 🌥️', 'CL 🌤️-🌥️@15', 'CL:BKN@15', 'simplified', true),
		zeile('uv_index', 'UV-Index', 'UV 3.5', 'UV 0.0-4.0', 'UV-', undefined, true),
		zeile('freezing_level', 'Nullgradgrenze', '0°Line 2120', 'FZ 2100-2320@04', 'FZ2100@15', undefined, true),
		zeile('snowfall_limit', 'Schneefallgrenze', 'SnowL 1820', 'SL 1800-2020@04', 'SL1780', undefined, true)
	];
	liste[1].zellen.email = { zustand: 'locked', grund: 'keine eigene Spalte' };
	return liste;
}
