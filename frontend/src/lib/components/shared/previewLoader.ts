// Issue #2283 (Epic #2345 P3) — EIN Lader fuer den geteilten Vorschau-Reiter
// beider Hubs (shared/PreviewTab.svelte).
// Spec: docs/specs/modules/shared_preview_tab.md (AC-9, AC-10, AC-15).
//
// Reines TypeScript ohne Runen (laeuft unter node:test). Der Lader haelt den
// EINEN Zustand des Reiters: Daten, Kanal, E-Mail-Ansicht, Optionen.
//   * Anlegen ruft nichts ab; `load()` = genau EIN Abruf, jeder weitere keiner.
//   * Kanal-/Ansichtswechsel ist reine Anzeige — nie ein Abruf.
//   * Morgen/Abend + Demo gibt es nur im Trip (`route`); im Vergleich ignoriert.

import { briefingVorschau, type BriefingKind } from '../../api.ts';
import {
	defaultReportType,
	friendlyPreviewError,
	PREVIEW_ERROR_GENERIC,
	type ReportType
} from '../preview/previewHelpers.ts';

export type PreviewKind = BriefingKind;
export type PreviewChannel = 'email' | 'sms' | 'telegram';
export type EmailView = 'desktop' | 'mobile';

export interface PreviewBundle {
	subject: string;
	email_html: string;
	sms: { text: string; char_count: number };
	telegram: { body: string; bubbles?: string[] };
}

export interface PreviewOptions {
	type?: ReportType;
	date?: string;
	demo?: boolean;
}

export interface PreviewState {
	status: 'idle' | 'loading' | 'ready' | 'error';
	data: PreviewBundle | null;
	error: string | null;
	channel: PreviewChannel;
	emailView: EmailView;
	options: PreviewOptions;
}

export interface PreviewLoader {
	kind: PreviewKind;
	id: string;
	getState(): PreviewState;
	load(): Promise<void>;
	setChannel(c: PreviewChannel): void;
	setEmailView(v: EmailView): void;
	setOptions(o: PreviewOptions): Promise<void>;
	subscribe(fn: (s: PreviewState) => void): () => void;
}

export interface PreviewLoaderInit {
	kind: PreviewKind;
	id: string;
	options?: PreviewOptions;
	channel?: PreviewChannel;
	emailView?: EmailView;
}

/** Nur der Trip kennt Berichtstyp (Morgen/Abend) und Demo-Daten (AC-10). */
export function hatTripOptionen(kind: PreviewKind): boolean {
	return kind === 'route';
}

/** Fehler aus `api.ts` (Objekt `{error, detail, status}` oder TimeoutError) → deutsche Meldung. */
function fehlerMeldung(e: unknown): string {
	if (e instanceof Error && e.name === 'TimeoutError' && e.message) return e.message;
	if (e && typeof e === 'object' && typeof (e as { status?: unknown }).status === 'number') {
		return friendlyPreviewError((e as { status: number }).status, JSON.stringify(e));
	}
	return PREVIEW_ERROR_GENERIC;
}

export function createPreviewLoader(init: PreviewLoaderInit): PreviewLoader {
	const { kind, id } = init;
	let state: PreviewState = {
		status: 'idle',
		data: null,
		error: null,
		channel: init.channel ?? 'email',
		emailView: init.emailView ?? 'desktop',
		options: hatTripOptionen(kind) ? { type: defaultReportType(), demo: true, ...init.options } : {}
	};
	const abonnenten = new Set<(s: PreviewState) => void>();
	let laufend: Promise<void> | null = null;
	let abrufNr = 0;

	function setze(teil: Partial<PreviewState>): void {
		state = { ...state, ...teil };
		for (const fn of abonnenten) fn(state);
	}

	function abrufen(): Promise<void> {
		const nr = ++abrufNr;
		setze({ status: 'loading', error: null });
		laufend = briefingVorschau<PreviewBundle>(kind, id, state.options).then(
			(data) => {
				if (nr === abrufNr) setze({ status: 'ready', data, error: null });
			},
			(e: unknown) => {
				if (nr === abrufNr) setze({ status: 'error', data: null, error: fehlerMeldung(e) });
			}
		);
		return laufend;
	}

	return {
		kind,
		id,
		getState: () => state,
		load: () => laufend ?? abrufen(),
		setChannel: (channel) => {
			if (channel !== state.channel) setze({ channel });
		},
		setEmailView: (emailView) => {
			if (emailView !== state.emailView) setze({ emailView });
		},
		setOptions: async (o) => {
			if (!hatTripOptionen(kind)) return;
			const options = { ...state.options, ...o };
			const geaendert = (Object.keys(options) as (keyof PreviewOptions)[]).some(
				(k) => options[k] !== state.options[k]
			);
			if (!geaendert) return;
			setze({ options });
			if (laufend) await abrufen();
		},
		subscribe: (fn) => {
			abonnenten.add(fn);
			return () => abonnenten.delete(fn);
		}
	};
}
