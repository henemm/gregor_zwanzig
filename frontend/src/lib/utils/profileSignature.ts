// Issue #238 — Profil-Signaturen im Design-System.
//
// Liefert pro ActivityProfile eine visuelle Signatur (Akzentfarbe als
// CSS-Variablen-Referenz, Unicode-Icon, Eyebrow-Label). Zentrale Quelle fuer
// Frontend-Cards und Mail-Renderer.
//
// Bei unbekannter oder leerer Eingabe wird die Signatur von `allgemein`
// zurueckgegeben (Fallback, kein Throw).
//
// Spec: docs/specs/modules/issue_238_profile_signatures.md

import type { ActivityProfile } from '$lib/types';
import { tr, type MessageKey } from '../i18n/index.ts';

export type ProfileSignature = {
	accent: string;          // CSS-Variablen-Referenz: var(--g-profile-...)
	icon: string;            // Unicode-Glyph
	eyebrow: string;         // Sichtbares Label
};

// #2660: die Tabelle haelt Katalog-Schluessel; `profileSignature()` loest sie bei
// jedem Aufruf in der aktuellen Sprache auf (nie beim Import eingefroren).
type Eintrag = Omit<ProfileSignature, 'eyebrow'> & { eyebrowKey: MessageKey };

const SIGNATURES: Record<ActivityProfile, Eintrag> = {
	wintersport: {
		accent: 'var(--g-profile-wintersport)',
		icon: '❄',          // Schneeflocke
		eyebrowKey: 'bausteine.profil.wintersport',
	},
	wandern: {
		accent: 'var(--g-profile-wandern)',
		icon: '\u{1F97E}',       // Wanderschuh
		eyebrowKey: 'bausteine.profil.wandern',
	},
	summer_trekking: {
		accent: 'var(--g-profile-summer-trekking)',
		icon: '\u{1F3D4}',       // Berg-Symbol
		eyebrowKey: 'bausteine.profil.summer_trekking',
	},
	allgemein: {
		accent: 'var(--g-profile-allgemein)',
		icon: '◯',          // Kreis
		eyebrowKey: 'bausteine.profil.allgemein',
	},
};

export function profileSignature(profile: ActivityProfile | string | null | undefined): ProfileSignature {
	const eintrag = (profile == null ? undefined : SIGNATURES[profile as ActivityProfile]) ?? SIGNATURES.allgemein;
	const { eyebrowKey, ...rest } = eintrag;
	return { ...rest, eyebrow: tr(eyebrowKey) };
}
