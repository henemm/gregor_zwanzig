// Issue #3031 (Inhalt je Kanal A1): Beispielwerte Roh/Einfach je Metrik, DE und EN.
// Spec: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md, Implementation Details 9.
// Quelle: Mockup Fassung 3 (`const EX`, mockup-hub-fassung3.html), ergaenzt um alle Metriken,
// die laut Katalog eine Roh/Einfach-Wahl haben (Test gegen den echten Katalog). Wolken-Symbole
// nach `cloud_emoji` (src/output/metric_format.py). Einheiten und Symbole sind Protokoll, die
// Woerter (Ampelfarbe, Gewitterstufe) und das Dezimalzeichen folgen der Nutzersprache.

import type { Format } from './kanalInhalt.ts';

type Sprache = 'de' | 'en';
type Paar = { roh: string; einfach: string };

const BEISPIELE: Record<string, Record<Sprache, Paar>> = {
	wind: { de: { roh: '30 km/h', einfach: '● gelb' }, en: { roh: '30 km/h', einfach: '● yellow' } },
	gust: { de: { roh: '45 km/h', einfach: '● orange' }, en: { roh: '45 km/h', einfach: '● orange' } },
	wind_direction: { de: { roh: '270°', einfach: 'W' }, en: { roh: '270°', einfach: 'W' } },
	precipitation: { de: { roh: '2,1 mm', einfach: '● gelb' }, en: { roh: '2.1 mm', einfach: '● yellow' } },
	thunder: { de: { roh: 'mittel', einfach: '● orange' }, en: { roh: 'medium', einfach: '● orange' } },
	cloud_total: { de: { roh: '70 %', einfach: '⛅' }, en: { roh: '70%', einfach: '⛅' } },
	cloud_low: { de: { roh: '40 %', einfach: '⛅' }, en: { roh: '40%', einfach: '⛅' } },
	cloud_mid: { de: { roh: '95 %', einfach: '☁️' }, en: { roh: '95%', einfach: '☁️' } },
	cloud_high: { de: { roh: '20 %', einfach: '🌤️' }, en: { roh: '20%', einfach: '🌤️' } },
	sunshine: { de: { roh: '6,5 h', einfach: '☀️' }, en: { roh: '6.5 h', einfach: '☀️' } }
};

/** Beispiel der Darstellung `format` in der Sprache `lang`; unbekannte Metrik ⇒ null. */
export function beispiel(id: string, format: Format, lang: Sprache): string | null {
	const p = BEISPIELE[id]?.[lang] ?? BEISPIELE[id]?.de;
	return p ? p[format] : null;
}
