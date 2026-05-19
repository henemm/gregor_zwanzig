// Statische Vorlage-Daten fuer Step 2 des Trip-Wizards (Epic #136 Sub-Spec #165).
// Spec: docs/specs/modules/epic_136_step5_templates.md
//
// Factory-Pattern: `stages` ist eine Funktion () => Stage[] — jeder Aufruf erzeugt
// frische Stage- und Waypoint-IDs via newId(). Damit gibt es keine ID-Kollisionen,
// wenn zwei Wizard-Sessions parallel laufen oder eine Vorlage zweimal geladen wird.

import type { Stage, Waypoint, ActivityType } from '$lib/types';
import { newId } from '../wizardHelpers.ts';

export interface TripTemplate {
	id: string;
	name: string;
	shortcode: string;
	activity: ActivityType;
	stages: () => Stage[];
}

function makeStage(
	name: string,
	startLat: number,
	startLon: number,
	startEle: number,
	endLat: number,
	endLon: number,
	endEle: number
): Stage {
	const start: Waypoint = {
		id: newId(),
		name: '',
		lat: startLat,
		lon: startLon,
		elevation_m: startEle
	};
	const end: Waypoint = {
		id: newId(),
		name: '',
		lat: endLat,
		lon: endLon,
		elevation_m: endEle
	};
	return { id: newId(), name, date: '', waypoints: [start, end] };
}

export const TRIP_TEMPLATES: TripTemplate[] = [
	{
		id: 'gr20',
		name: 'GR20',
		shortcode: 'GR20',
		activity: 'trekking',
		stages: () => [
			makeStage('Calenzana → Ortu di u Piobbu',   42.509, 8.848,  275,  42.478, 8.903, 1520),
			makeStage('Ortu → Carrozzu',                42.478, 8.903, 1520,  42.452, 8.907, 1270),
			makeStage('Carrozzu → Ascu Stagnu',         42.452, 8.907, 1270,  42.448, 8.916, 1422),
			makeStage('Ascu → Tighjettu',               42.448, 8.916, 1422,  42.423, 8.950, 1683),
			makeStage('Tighjettu → Ciottulu di i Mori', 42.423, 8.950, 1683,  42.392, 9.008, 1991),
			makeStage('Ciottulu → Manganu',             42.392, 9.008, 1991,  42.298, 9.009, 1601),
			makeStage('Manganu → Petra Piana',          42.298, 9.009, 1601,  42.268, 9.041, 1842),
			makeStage("Petra Piana → L'Onda",           42.268, 9.041, 1842,  42.245, 9.077, 1430),
			makeStage("L'Onda → Vizzavona",             42.245, 9.077, 1430,  42.128, 9.135, 1163),
			makeStage("Vizzavona → E'Capannelle",       42.128, 9.135, 1163,  41.959, 9.233, 1586),
			makeStage("E'Capannelle → Usciolu",         41.959, 9.233, 1586,  41.935, 9.147, 1750),
			makeStage('Usciolu → Asinau',               41.935, 9.147, 1750,  41.895, 9.125, 1536),
			makeStage('Asinau → Paliri',                41.895, 9.125, 1536,  41.758, 9.197, 1055),
			makeStage('Paliri → Conca',                 41.758, 9.197, 1055,  41.666, 9.330,  252)
		]
	},
	{
		id: 'khw',
		name: 'Karnischer Höhenweg',
		shortcode: 'KHW',
		activity: 'trekking',
		stages: () => [
			makeStage('Troblach Bhf → Helmhotel',            46.72475, 12.22542, 1212, 46.73042, 12.32164, 1144),
			makeStage('Helmhotel → Sillianer Hütte',         46.73042, 12.32164, 1142, 46.70606, 12.40627, 2377),
			makeStage('Sillianer Hütte → Obstansersee',      46.70607, 12.40627, 2441, 46.68427, 12.49369, 2312),
			makeStage('Obstansersee → Porzehütte',           46.68427, 12.49369, 2297, 46.65972, 12.58220, 1930),
			makeStage('Porzehütte → Hochweißsteinhaus',      46.65972, 12.58220, 1950, 46.64301, 12.74033, 1815),
			makeStage('Hochweißsteinhaus → Wolayersee-Hütte',46.64301, 12.74033, 1867, 46.61229, 12.86717, 1953),
			makeStage('Wolayersee → Valentinalm',            46.61241, 12.86704, 1949, 46.62285, 12.93057, 1200),
			makeStage('Valentinalm → Zollnersee Hütte',      46.62285, 12.93057, 1190, 46.60538, 13.07065, 1751),
			makeStage('Zollnersee → Straniger Alm',          46.60539, 13.07064, 1729, 46.59567, 13.13447, 1504),
			makeStage('Straniger Alm → Nassfeld',            46.59571, 13.13440, 1515, 46.55762, 13.27852, 1522),
			makeStage('Nassfeld → Egger Alm',                46.55762, 13.27852, 1532, 46.58570, 13.38018, 1396),
			makeStage('Egger Alm → Dolinza Alm',             46.58570, 13.38018, 1408, 46.56405, 13.47916, 1483),
			makeStage('Dolinza → Nötsch im Gailtal',         46.56405, 13.47916, 1468, 46.59079, 13.62275,  560)
		]
	},
	{
		id: 'stubai',
		name: 'Stubaier Höhenweg',
		shortcode: 'SHW',
		activity: 'trekking',
		stages: () => [
			makeStage('Fulpmes → Franz-Senn-Hütte',        47.157, 11.329,  937, 47.131, 11.206, 2147),
			makeStage('Franz-Senn → Neue Regensburger',    47.131, 11.206, 2147, 47.062, 11.048, 2286),
			makeStage('Neue Regensburger → Sulzenauhütte', 47.062, 11.048, 2286, 46.993, 11.068, 2191),
			makeStage('Sulzenauhütte → Nürnberger Hütte',  46.993, 11.068, 2191, 46.986, 11.119, 2280),
			makeStage('Nürnberger → Dresdner Hütte',       46.986, 11.119, 2280, 47.075, 11.110, 2302),
			makeStage('Dresdner → Starkenburger Hütte',    47.075, 11.110, 2302, 47.152, 11.280, 2237),
			makeStage('Starkenburger → Neustift',          47.152, 11.280, 2237, 47.099, 11.314, 1000)
		]
	}
];
