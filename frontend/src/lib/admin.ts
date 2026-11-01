// Issue #2155 S4 — reine Helfer der Admin-Seite (ohne Svelte-Umgebung testbar).
import type { AdminInvite, AdminUser, UserTier } from '$lib/types';
import { locale, tr } from './i18n/index.ts';
import { get } from 'svelte/store';

/** Zentrale Tier-Bezeichnungen (Konto-Seite und Admin-Seite). */
export const TIER_LABELS: Record<UserTier, string> = {
	free: 'Free',
	standard: 'Standard',
	premium: 'Premium'
};

/** Klartext je Fehlerfall der Admin-API; nie der rohe Fehlercode. */
export function adminErrorText(status: number, code?: string): string {
	if (status === 403) return tr('admin.fehler.keine_berechtigung');
	if (status === 404) return tr('admin.fehler.nutzer_nicht_gefunden');
	if (status === 409 && code === 'cannot_disable_self') {
		return tr('admin.fehler.selbst_sperren');
	}
	if (status === 400) return tr('admin.fehler.ungueltig');
	return tr('admin.fehler.fehlgeschlagen');
}

/** Ersetzt nur die Zeile mit gleicher ID; Eingabe bleibt unveraendert. */
export function replaceUserRow(users: AdminUser[], updated: AdminUser): AdminUser[] {
	return users.map((u) => (u.id === updated.id ? updated : u));
}

/** Zustand des Sperr-Dialogs: nur die ID des Nutzers, der gesperrt werden soll. */
export function askDisable(id: string): string {
	return id;
}

/** Abbrechen verwirft die Auswahl und sendet nichts. */
export function cancelDisable(): null {
	return null;
}

/** Erst die Bestaetigung erzeugt eine Sende-Aktion; ohne offene Auswahl keine. */
export function confirmDisableAction(
	confirmId: string | null
): { id: string; path: 'disabled'; body: { disabled: true } } | null {
	return confirmId ? { id: confirmId, path: 'disabled', body: { disabled: true } } : null;
}

/** Entsperren braucht keinen Dialog und sendet direkt. */
export function enableAction(id: string): { id: string; path: 'disabled'; body: { disabled: false } } {
	return { id, path: 'disabled', body: { disabled: false } };
}

/** Das eigene Konto ist nie sperrbar; waehrend einer Aktion ebenfalls nicht. */
export function disableBlocked(userId: string, selfId: string, busy: boolean): boolean {
	return busy || userId === selfId;
}

/** Nach Fehler zeigt das Tier-Select wieder den bisherigen Wert. */
export function tierSelectValueAfter(ok: boolean, selected: string, previous: string): string {
	return ok ? selected : previous;
}

export type AdminSendResult = { ok: true; user: AdminUser } | { ok: false; text: string };

/**
 * Uebernimmt ein Sende-Ergebnis: bei Erfolg wird nur die Zeile ersetzt und der
 * Fehlertext der Zeile geloescht; bei Fehler bleibt die Liste UNVERAENDERT und
 * die Zeile bekommt den Klartext.
 */
export function applySendResult(
	users: AdminUser[],
	errors: Record<string, string>,
	id: string,
	result: AdminSendResult
): { users: AdminUser[]; errors: Record<string, string> } {
	const rest = { ...errors };
	delete rest[id];
	if (!result.ok) return { users, errors: { ...rest, [id]: result.text } };
	return { users: replaceUserRow(users, result.user), errors: rest };
}

/** Sendet eine Admin-Aenderung; Fehler werden zu Klartext, nie zu Rohcode. */
export async function sendAdminUpdate(
	fetchFn: typeof fetch,
	id: string,
	path: 'tier' | 'disabled',
	body: unknown
): Promise<AdminSendResult> {
	try {
		const res = await fetchFn(`/api/admin/users/${encodeURIComponent(id)}/${path}`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body)
		});
		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			return { ok: false, text: adminErrorText(res.status, err?.error) };
		}
		return { ok: true, user: (await res.json()) as AdminUser };
	} catch {
		return { ok: false, text: adminErrorText(0) };
	}
}

// ─── Issue #2519: Einladungslinks ────────────────────────────────────────────

/** Datumsformat der Admin-Seite: Deutsch wie bisher `de-DE`, Englisch `en-GB` (Spec F4, A2). */
export function adminLocale(): string {
	return get(locale) === 'en' ? 'en-GB' : 'de-DE';
}

function formatDate(iso: string | null): string {
	if (!iso) return '';
	const d = new Date(iso);
	return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(adminLocale());
}

/** Statustext je Einladung: Offen / Benutzt von <Name> am <Datum> / Widerrufen am <Datum>. */
export function inviteStatusText(inv: AdminInvite): string {
	if (inv.status === 'used') return tr('admin.einladung.status_benutzt', { name: inv.used_by, datum: formatDate(inv.used_at) });
	if (inv.status === 'revoked') return tr('admin.einladung.status_widerrufen', { datum: formatDate(inv.revoked_at) });
	return tr('admin.einladung.status_offen');
}

function inviteErrorText(status: number, code?: string): string {
	if (status === 403) return tr('admin.fehler.keine_berechtigung');
	if (status === 404) return tr('admin.fehler.einladung_nicht_gefunden');
	if (status === 409 && code === 'invite_used') return tr('admin.fehler.einladung_benutzt');
	if (status === 400) return tr('admin.fehler.einladung_ungueltig');
	return tr('admin.fehler.fehlgeschlagen');
}

export type InviteCreateResult =
	| { ok: true; invite: AdminInvite; link: string }
	| { ok: false; text: string };
export type InviteRevokeResult = { ok: true; invite: AdminInvite } | { ok: false; text: string };

async function postInvite(fetchFn: typeof fetch, url: string, body?: unknown) {
	try {
		const res = await fetchFn(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body ?? {})
		});
		if (!res.ok) {
			const err = await res.json().catch(() => ({}));
			return { ok: false as const, text: inviteErrorText(res.status, err?.error) };
		}
		return { ok: true as const, data: await res.json() };
	} catch {
		return { ok: false as const, text: inviteErrorText(0) };
	}
}

/** Erstellt eine Einladung; der Link wird nur in dieser Antwort geliefert. */
export async function createInvite(
	fetchFn: typeof fetch,
	tier: string,
	note: string
): Promise<InviteCreateResult> {
	const r = await postInvite(fetchFn, '/api/admin/invites', { tier, note });
	if (!r.ok) return r;
	return { ok: true, invite: r.data.invite as AdminInvite, link: String(r.data.link) };
}

export async function revokeInvite(fetchFn: typeof fetch, id: string): Promise<InviteRevokeResult> {
	const r = await postInvite(fetchFn, `/api/admin/invites/${encodeURIComponent(id)}/revoke`);
	return r.ok ? { ok: true, invite: r.data as AdminInvite } : r;
}
