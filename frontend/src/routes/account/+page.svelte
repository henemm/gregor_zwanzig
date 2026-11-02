<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Btn } from '$lib/components/atoms';
	import { api, downloadUserDataExport, langlaeufer } from '$lib/api.js';
	import { invalidateAll } from '$app/navigation';
	import { onMount } from 'svelte';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import CheckIcon from '@lucide/svelte/icons/check';
	import XIcon from '@lucide/svelte/icons/x';
	import type { MetricPreset, UserTier } from '$lib/types';
	import { TIER_LABELS } from '$lib/admin';
	import { metricCountLabel, showDefaultBadge, isValidRename, applyRename, removePreset, isEmpty } from '$lib/utils/presetCardHelpers';
	import { formatNextRun } from '$lib/utils/schedulerTime';
	import { ABMELDE_MERKMAL, merkeAbmeldung, vergissAbmeldung } from '$lib/pwa/geraetespeicher';
	import { isWebAuthnSupported, registerPasskey, deletePasskey, type RegisteredPasskey } from '$lib/passkey';
	import { profileSaveErrorMessage } from './profileSaveError';
	import { passwortAendernErrorMessage } from './passwortAendernError';
	import { lastRunDot } from './schedulerLastRun';
	import PremiumSmsLinkCard from '$lib/components/account/PremiumSmsLinkCard.svelte';
	import SpracheAuswahl from '$lib/components/account/SpracheAuswahl.svelte';
	import {
		shouldShowPremiumSmsLinkCard,
		resolveGenerateClick,
		resolveDialogAction,
		errorMessageFrom
	} from '$lib/utils/premiumSmsLinkCodeHelpers';
	import { shouldShowSmsUsageRow } from '$lib/utils/smsDailyUsageHelpers';
	import { countActive, formatQuotaUsage } from '$lib/utils/mengenQuoteHelpers';
	import type { ProfileQuota } from '$lib/types';
	// Issue #2653 (i18n F4): alle Texte aus dem Katalog (konto.*, nav.*); Sprache = data.lang
	// des angemeldeten Nutzers (Store `locale`, gesetzt von +layout.svelte).
	import { t, tn, locale, type MessageKey } from '$lib/i18n';
	import { fmtRelativeMinutes } from '$lib/i18n/format';
	import { deleteErrorText } from './deleteErrorText';
	import { textTeile } from './textTeile';
	let { data } = $props();

	// Kanalnamen sind Eigennamen (ADR-0104, Spec F4 Nr. 5) und stehen nicht im Katalog.
	const KANAL = { email: 'E-Mail', telegram: 'Telegram', sms: 'SMS', premiumSms: 'Premium-SMS' } as const;
	const SMS_BEISPIEL = '+49XXXXXXXXXX';

	// Issue #2482: Tarif-Grenzen aus dem Profil; fehlt das Feld, bleibt die Anzeige bei "x".
	const quota = $derived(data.profile?.quota as ProfileQuota | undefined);

	let displayName = $state(data.profile?.display_name ?? '');
	let mailTo = $state(data.profile?.mail_to ?? '');
	let smsTo = $state(data.profile?.sms_to ?? '');
	let telegramConnected = $state(!!data.profile?.telegram_chat_id);
	let telegramChatIdSuffix = $state(
		data.profile?.telegram_chat_id
			? '...' + data.profile.telegram_chat_id.slice(-3)
			: ''
	);
	let telegramConnecting = $state(false);
	let telegramPollInterval: ReturnType<typeof setInterval> | null = null;
	let successMsg = $state<string | null>(null);
	let errorMsg = $state<string | null>(null);

	type TestStatus = 'idle' | 'loading' | 'ok' | 'error';
	let testStatus = $state<Record<string, TestStatus>>({email: 'idle', telegram: 'idle'});
	let testError = $state<Record<string, string | null>>({email: null, telegram: null});

	// Issue #344 — Wetter-Profile (User-MetricPresets)
	let presets = $state<MetricPreset[]>(data.metricPresets ?? []);
	let editingId = $state<string | null>(null);
	let editName = $state('');
	let presetError = $state<string | null>(null);
	let deletePresetTarget: MetricPreset | null = $state(null);
	let showDeleteAccountDialog = $state(false);
	let showLogoutAllDialog = $state(false);
	let logoutAllErrorMsg = $state<string | null>(null);

	// Issue #2154 Scheibe B — Premium-SMS-Verknüpfungscode. `linkCodeValue`
	// bleibt bewusst rein lokaler Client-State (AC-7): er fliesst nie in
	// `data`/`PageData` und verschwindet bei Reload, weil das Backend nur den
	// Hash haelt, nie den Klartext erneut liefert.
	let linkCodeExists = $state(data.premiumSmsLinkCodeExists);
	let linkCodeValue = $state<string | null>(null);
	let linkCodeBusy = $state(false);
	let linkCodeErrorMsg = $state<string | null>(null);
	let showRenewConfirm = $state(false);

	function onGenerateOrRenewClick() {
		const decision = resolveGenerateClick(linkCodeExists, linkCodeBusy);
		if (decision === 'confirm-dialog') {
			showRenewConfirm = true;
			return;
		}
		if (decision === 'call-post') runLinkCodeGenerate();
	}

	function onDialogConfirm() {
		const decision = resolveDialogAction('confirm');
		showRenewConfirm = false;
		if (decision === 'call-post') runLinkCodeGenerate();
	}

	function onDialogCancel() {
		resolveDialogAction('cancel');
		showRenewConfirm = false;
	}

	async function runLinkCodeGenerate() {
		linkCodeBusy = true;
		linkCodeErrorMsg = null;
		try {
			const res = await api.post<{ code: string }>('/api/auth/premium-sms-link-code', {});
			linkCodeValue = res.code;
			linkCodeExists = true;
		} catch (e: unknown) {
			linkCodeErrorMsg = errorMessageFrom(e, $t('konto.kopplung.fehlgeschlagen'));
		} finally {
			linkCodeBusy = false;
		}
	}

	// Issue #2270 — Datenexport nach DSGVO Art. 20.
	let exportBusy = $state(false);
	let exportErrorMsg = $state<string | null>(null);

	// Issue #2246 — Passkey-Karte. Die Liste kommt aus dem ohnehin geladenen
	// Profil, ein eigener Lese-Abruf waere ein zweiter Weg zu denselben Daten.
	// `null` heisst "noch nicht gemessen": WebAuthn laesst sich erst im Browser
	// pruefen, und ein serverseitiges `false` liesse den Hinweis kurz aufblitzen.
	let passkeySupported = $state<boolean | null>(null);
	let showPasskeyDialog = $state(false);
	let passkeyLabel = $state('');
	let passkeyBusy = $state(false);
	let passkeySuccessMsg = $state<string | null>(null);
	let passkeyErrorMsg = $state<string | null>(null);
	// Rueckfrage vor dem Loeschen (PO-Entscheid 2026-09-08): das Entfernen ist
	// nicht umkehrbar, und jede andere destruktive Aktion dieser Seite fragt nach.
	let deletePasskeyTarget = $state<RegisteredPasskey | null>(null);
	const passkeys = $derived((data.profile?.passkeys ?? []) as RegisteredPasskey[]);

	// Issue #1068 — Nutzerlevel-Badge (immer sichtbar). Der Wert kommt aus
	// data.profile.tier (Response-Feld ist serverseitig immer gesetzt, Default "free").
	function tierLabel(tier: unknown): string {
		return TIER_LABELS[(tier as UserTier)] ?? 'Free';
	}

	// Issue #1071 — Level-Wechsel beantragen. Der Pending-Hinweis wird
	// ausschließlich aus dem Server-State abgeleitet (requested_tier vorhanden
	// UND ungleich tier), damit er einen Reload übersteht.
	const TIER_OPTIONS: UserTier[] = ['free', 'standard', 'premium'];
	let requestedTierChoice = $state<UserTier>('standard');
	let tierChangeStatus = $state<TestStatus>('idle');
	let tierChangeError = $state<string | null>(null);
	// Issue #2436 — Antwort des Servers: wurde der Betreiber benachrichtigt?
	let tierChangeNotified = $state<boolean | null>(null);
	const pendingTier = $derived(
		data.profile?.requested_tier && data.profile.requested_tier !== data.profile?.tier
			? (data.profile.requested_tier as UserTier)
			: null
	);
	const tierNotNotified = $derived(
		!!pendingTier && !data.profile?.requested_notified_at
	);

	async function requestTierChange() {
		tierChangeStatus = 'loading';
		tierChangeError = null;
		tierChangeNotified = null;
		try {
			const res = (await api.post('/api/auth/tier-change-request', {
				requested_tier: requestedTierChoice
			})) as { po_notified?: boolean } | undefined;
			tierChangeNotified = res?.po_notified === true;
			// Profil neu laden, damit requested_tier sofort im UI erscheint.
			await invalidateAll();
			tierChangeStatus = 'ok';
			setTimeout(() => (tierChangeStatus = 'idle'), 4000);
		} catch (e: unknown) {
			const body = e as { error?: string };
			if (body?.error === 'already_current_tier') {
				tierChangeError = $t('konto.level.bereits_aktiv');
			} else if (body?.error === 'invalid_tier') {
				tierChangeError = $t('konto.level.ungueltig');
			} else {
				tierChangeError = body?.error ?? $t('konto.level.antrag_fehlgeschlagen');
			}
			tierChangeStatus = 'error';
		}
	}

	function startEdit(p: MetricPreset) {
		editingId = p.id;
		editName = p.name;
		presetError = null;
	}

	function cancelEdit() {
		editingId = null;
		editName = '';
	}

	async function saveRename(id: string) {
		if (!isValidRename(editName)) return;
		try {
			const updated = await api.patch<MetricPreset>(`/api/metric-presets/${id}`, { name: editName.trim() });
			presets = applyRename(presets, updated);
			editingId = null;
			editName = '';
		} catch (e: unknown) {
			const body = e as { error?: string };
			presetError = body?.error ?? $t('konto.wetter_profile.umbenennen_fehler');
		}
	}

	function deletePreset(p: MetricPreset) {
		deletePresetTarget = p;
	}

	async function confirmDeletePreset() {
		if (!deletePresetTarget) return;
		const p = deletePresetTarget;
		deletePresetTarget = null;
		try {
			await api.del(`/api/metric-presets/${p.id}`);
			presets = removePreset(presets, p.id);
		} catch (e: unknown) {
			const body = e as { error?: string };
			presetError = body?.error ?? $t('konto.aktion.loeschen_fehlgeschlagen');
		}
	}

	// Issue #2147 Scheibe B2 (AC-17) — ausstehende Adressaenderung: die
	// Bestaetigungsmail an die ausstehende Adresse erneut anfordern. Der
	// Endpunkt antwortet immer 200 (verraet nichts), die Seite quittiert daher
	// bestaetigend.
	let resendStatus = $state<TestStatus>('idle');
	async function resendVerification() {
		resendStatus = 'loading';
		try {
			await api.post('/api/auth/verify-email/resend', { username: data.profile?.id ?? '' });
			resendStatus = 'ok';
		} catch {
			resendStatus = 'error';
		}
	}

	// Issue #2406 (AC-13) — SMS-Nummer bestaetigen. Die Nummer, um die es geht,
	// ist die ausstehende; ohne ausstehende die eingetragene, solange sie
	// unbestaetigt ist. Ist die wirksame Nummer bewiesen und nichts ausstehend,
	// gibt es nichts zu bestaetigen (kein Hinweis, keine Code-Eingabe).
	let smsZuBestaetigen = $derived(
		data.profile?.pending_sms_to || (data.profile?.sms_verified ? '' : (data.profile?.sms_to ?? ''))
	);
	let smsCode = $state('');
	let smsVerifyStatus = $state<TestStatus>('idle');
	let smsVerifyError = $state<string | null>(null);
	let smsResendStatus = $state<TestStatus>('idle');

	async function verifySmsCode() {
		smsVerifyStatus = 'loading';
		smsVerifyError = null;
		try {
			await api.post('/api/auth/sms/verify', { code: smsCode });
			smsCode = '';
			smsVerifyStatus = 'ok';
			// Der Pending-Hinweis haengt an `data.profile` — ohne Neuladen bliebe
			// er stehen, obwohl die Nummer bereits bewiesen ist.
			await invalidateAll();
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string; status?: number };
			smsVerifyError = profileSaveErrorMessage(body?.status ?? 0, body);
			smsVerifyStatus = 'error';
		}
	}

	async function resendSmsCode() {
		smsResendStatus = 'loading';
		smsVerifyError = null;
		try {
			await api.post('/api/auth/sms/resend', {});
			smsResendStatus = 'ok';
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string; status?: number };
			smsVerifyError = profileSaveErrorMessage(body?.status ?? 0, body);
			smsResendStatus = 'error';
		}
	}

	async function sendTest(channel: string) {
		testStatus[channel] = 'loading';
		testError[channel] = null;
		try {
			// #2361: eigenes Budget 130 s (Go-Proxy 120 s), s. `langlaeufer` in api.ts.
			const resp = await langlaeufer.testNachricht<{ error?: string }>(channel);
			if (resp?.error) {
				testError[channel] = resp.error;
				testStatus[channel] = 'error';
			} else {
				testStatus[channel] = 'ok';
				setTimeout(() => (testStatus[channel] = 'idle'), 4000);
			}
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			testError[channel] = body?.detail ?? body?.error ?? $t('konto.aktion.senden_fehlgeschlagen');
			testStatus[channel] = 'error';
		}
	}

	let oldPassword = $state('');
	let newPassword = $state('');
	let confirmNewPassword = $state('');
	let pwSuccessMsg = $state<string | null>(null);
	let pwErrorMsg = $state<string | null>(null);

	async function changePassword() {
		pwSuccessMsg = null;
		pwErrorMsg = null;

		if (newPassword !== confirmNewPassword) {
			pwErrorMsg = $t('konto.passwort.ungleich');
			return;
		}

		try {
			await api.put('/api/auth/password', {
				old_password: oldPassword,
				new_password: newPassword,
			});
			pwSuccessMsg = $t('konto.passwort.geaendert');
			oldPassword = '';
			newPassword = '';
			confirmNewPassword = '';
			setTimeout(() => (pwSuccessMsg = null), 4000);
		} catch (e: unknown) {
			pwErrorMsg = passwortAendernErrorMessage(e);
		}
	}

	function formatDate(iso: string | null | undefined): string {
		if (!iso) return '—';
		try {
			// Deutsch wie bisher `de-AT`, Englisch `en-GB` (Spec F4, A2).
			return new Date(iso).toLocaleDateString($locale === 'en' ? 'en-GB' : 'de-AT', {
				year: 'numeric',
				month: '2-digit',
				day: '2-digit',
			});
		} catch {
			return iso;
		}
	}

	/**
	 * Bezeichnung einer Passkey-Zeile: das freiwillige Label zuerst, sonst der
	 * aus der AAGUID abgeleitete Geraetename (fehlt bei Null-AAGUID), sonst ein
	 * neutraler Platzhalter — namenlos darf keine Zeile bleiben.
	 */
	function passkeyTitel(pk: RegisteredPasskey): string {
		return pk.label?.trim() || pk.authenticator_name?.trim() || $t('konto.passkey.unbenannt');
	}

	/** Rohe Zeremonie-Fehler in einen verstaendlichen Satz der Nutzersprache uebersetzen. */
	function passkeyFehlertext(e: unknown, ersatz: string): string {
		const name = (e as { name?: string })?.name;
		if (name === 'NotAllowedError' || name === 'AbortError' || name === 'TimeoutError') {
			return $t('konto.passkey.abgebrochen');
		}
		return ersatz;
	}

	async function createPasskey() {
		// Der Dialog bleibt waehrend der Zeremonie offen und zeigt den
		// Wartezustand — ein Dialog, der vor der Geraeteabfrage zugeht, wirkt,
		// als sei nichts passiert. Geschlossen wird erst im `finally`.
		passkeyBusy = true;
		passkeySuccessMsg = null;
		passkeyErrorMsg = null;
		try {
			await registerPasskey(passkeyLabel.trim());
			passkeyLabel = '';
			// Liste aus dem Server-Stand nachziehen statt die Seite neu zu laden.
			await invalidateAll();
			passkeySuccessMsg = $t('konto.passkey.angelegt');
			setTimeout(() => (passkeySuccessMsg = null), 4000);
		} catch (e: unknown) {
			passkeyErrorMsg = passkeyFehlertext(e, $t('konto.passkey.anlegen_fehler'));
		} finally {
			passkeyBusy = false;
			showPasskeyDialog = false;
		}
	}

	/** Bestaetigte Rueckfrage: erst hier wird wirklich geloescht. */
	async function confirmDeletePasskey() {
		const ziel = deletePasskeyTarget;
		deletePasskeyTarget = null;
		if (!ziel) return;
		await removePasskey(ziel.id);
	}

	async function removePasskey(id: string) {
		passkeySuccessMsg = null;
		passkeyErrorMsg = null;
		try {
			await deletePasskey(id);
			await invalidateAll();
			passkeySuccessMsg = $t('konto.passkey.entfernt');
			setTimeout(() => (passkeySuccessMsg = null), 4000);
		} catch {
			passkeyErrorMsg = $t('konto.passkey.entfernen_fehler');
		}
	}

	async function save() {
		errorMsg = null;
		successMsg = null;
		try {
			await api.put('/api/auth/profile', {
				display_name: displayName,
				mail_to: mailTo,
				sms_to: smsTo,
			});
			successMsg = $t('konto.profil.gespeichert');
			setTimeout(() => (successMsg = null), 4000);
			// Issue #2147 Scheibe B2: eine Adressaenderung eines bestaetigten
			// Kontos steht danach als ausstehend im Profil — neu laden, damit
			// der Hinweis sofort erscheint.
			await invalidateAll();
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string; status?: number };
			errorMsg = profileSaveErrorMessage(body?.status ?? 0, body);
		}
	}

	async function connectTelegram() {
		telegramConnecting = true;
		try {
			const resp = await api.get<{ link: string }>('/api/auth/telegram-link');
			window.open(resp.link, '_blank');
			let attempts = 0;
			telegramPollInterval = setInterval(async () => {
				attempts++;
				try {
					const status = await api.get<{ connected: boolean; chat_id_suffix?: string }>(
						'/api/auth/telegram-status'
					);
					if (status.connected) {
						telegramConnected = true;
						telegramChatIdSuffix = status.chat_id_suffix ?? '';
						telegramConnecting = false;
						clearInterval(telegramPollInterval!);
					} else if (attempts >= 20) {
						telegramConnecting = false;
						clearInterval(telegramPollInterval!);
					}
				} catch {
					telegramConnecting = false;
					clearInterval(telegramPollInterval!);
				}
			}, 3000);
		} catch {
			telegramConnecting = false;
		}
	}

	async function disconnectTelegram() {
		await api.put('/api/auth/profile', { telegram_chat_id: '' });
		telegramConnected = false;
		telegramChatIdSuffix = '';
	}

	// --- System-Status helpers (migrated from settings) ---

	// Issue #2653: `vor 3 Min` | `3 min ago` (fmtRelativeMinutes, auch „gerade eben"),
	// Stunden und Tage als Plural aus dem Katalog.
	function timeAgo(iso: string): string {
		const diff = Date.now() - new Date(iso).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 60) return fmtRelativeMinutes(mins, $locale);
		const hours = Math.floor(mins / 60);
		if (hours < 24) return $tn('konto.zeit.vor_stunden', hours);
		const days = Math.floor(hours / 24);
		return $tn('konto.zeit.vor_tagen', days);
	}

	// Issue #1727 S5e: Die Seite wird serverseitig vorgerendert und der Node-Prozess
	// laeuft in Etc/UTC. Ohne feste Zone formatierte also zuerst der Server — alle
	// Nutzer saehen UTC statt ihrer eigenen Zone. Die Uhrzeit entsteht deshalb erst
	// nach dem Mounten im Browser; bis dahin steht dort '—'.
	let imBrowser = $state(false);
	onMount(() => {
		imBrowser = true;
		passkeySupported = isWebAuthnSupported();
	});

	function getProvider(lat: number, lon: number): string {
		return (lat >= 45 && lat <= 50 && lon >= 8 && lon <= 18)
			? 'GeoSphere (Alpen)' : 'OpenMeteo';
	}

	const userJobs: Record<string, MessageKey> = {
		trip_reports_hourly: 'konto.job.trip_checks',
	};

	// Issue #2160 (ADR-0081): Löschen nur mit frischem Nachweis — Passwort
	// (falls das Konto eines hat) oder Lösch-Code per E-Mail.
	const deleteHasPassword = $derived(data.profile?.has_password === true);
	const deleteCodeAddress = $derived(data.profile?.mail_to || data.profile?.email || '');
	let deletePassword = $state('');
	let deleteCode = $state('');
	let deleteBusy = $state(false);
	let deleteCodeSent = $state(false);
	let deleteDialogMsg = $state<string | null>(null);

	// Fehlertexte beim Loeschen: deleteErrorText.ts (konto.fehler.*).

	function deleteAccount() {
		deletePassword = '';
		deleteCode = '';
		deleteCodeSent = false;
		deleteDialogMsg = null;
		showDeleteAccountDialog = true;
	}

	async function requestDeleteCode() {
		deleteBusy = true;
		deleteDialogMsg = null;
		try {
			await api.post('/api/auth/account/delete-code', {});
			deleteCodeSent = true;
		} catch (e: unknown) {
			deleteDialogMsg = deleteErrorText(e, $t('konto.loeschen.code_versand_fehlgeschlagen'));
		} finally {
			deleteBusy = false;
		}
	}

	async function confirmDeleteAccount() {
		const body = deletePassword ? { password: deletePassword } : { code: deleteCode.trim() };
		deleteBusy = true;
		deleteDialogMsg = null;
		// Abmelde-Muster wie "auf allen Geräten abmelden" (#2128): Merker VOR dem
		// Aufruf, weil die Löschung die Sitzung sofort beendet.
		merkeAbmeldung();
		try {
			await api.post('/api/auth/account/delete', body);
			showDeleteAccountDialog = false;
			window.location.href = `/login?${ABMELDE_MERKMAL}=1`;
		} catch (e: unknown) {
			const err = e as { status?: number };
			if (err?.status !== 401) vergissAbmeldung();
			deleteDialogMsg = deleteErrorText(e, $t('konto.aktion.loeschen_fehlgeschlagen'));
		} finally {
			deleteBusy = false;
		}
	}

	// Issue #2129 AC-17: auf allen Geräten abmelden — mit Bestätigungsschritt,
	// weil die Wirkung jedes andere Gerät des Nutzers trifft.
	function logoutAllDevices() {
		showLogoutAllDialog = true;
	}

	async function confirmLogoutAllDevices() {
		showLogoutAllDialog = false;
		// Issue #2128 AC-11: dasselbe Abmelde-Merkmal wie beim Abmelden ueber die
		// Seitenleiste -- geraeumt wird auf der Anmeldeseite. Es steht VOR dem
		// Aufruf und zusaetzlich im Sitzungsspeicher, weil die Abmeldung sofort
		// serverseitig wirkt: der zentrale 401-Umleiter kann uns danach jederzeit
		// von dieser Seite nehmen und ersetzt dabei das Weiterleitungsziel durch
		// `/login?expired=1&redirect=…` (gemessen, #2128).
		merkeAbmeldung();
		try {
			await api.post('/api/auth/logout-all', {});
			window.location.href = `/login?${ABMELDE_MERKMAL}=1`;
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string; status?: number };
			// Issue #2128 AC-19: gescheitert heisst NICHT abgemeldet. Der Merker
			// muss weg -- sonst gilt der naechste, voellig regulaere
			// Sitzungsablauf (401 -> /login?expired=1) als Abmeldung und die
			// Anmeldeseite raeumt still den Gerätespeicher (AC-12). Gilt fuer
			// beide Fehlerarten gleich, in denen der Nutzer auf dieser Seite
			// bleibt: geworfener Netzfehler wie 5xx-Antwort.
			//
			// AUSNAHME 401: die Sitzung ist bereits fort, der Nutzer ist also
			// tatsaechlich abgemeldet, und $lib/api leitet in diesem Moment auf
			// die Anmeldeseite -- dort soll geraeumt werden (AC-11). Bleibt diese
			// Umleitung wider Erwarten aus, faengt das Zeitfenster des Merkers den
			// Fall (AC-20).
			if (body?.status !== 401) vergissAbmeldung();
			logoutAllErrorMsg = body?.detail ?? body?.error ?? $t('konto.anmeldungen.fehlgeschlagen');
		}
	}

	// Issue #2270 — Datenexport. Der Download laeuft am JSON-Client vorbei
	// (s. downloadUserDataExport in $lib/api).
	async function exportiereMeineDaten() {
		exportBusy = true;
		exportErrorMsg = null;
		try {
			await downloadUserDataExport();
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string; message?: string };
			exportErrorMsg = body?.detail ?? body?.error ?? body?.message ?? $t('konto.daten.fehlgeschlagen');
		} finally {
			exportBusy = false;
		}
	}
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-bold">{$t('konto.titel')}</h1>

	{#if successMsg}
		<div class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
			{successMsg}
		</div>
	{/if}

	{#if errorMsg}
		<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
			{errorMsg}
		</div>
	{/if}

	<Card.Root>
		<Card.Header>
			<Card.Title>{$t('konto.profil.titel')}</Card.Title>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="grid gap-1">
				<span class="text-sm font-medium text-muted-foreground">{$t('konto.profil.benutzername')}</span>
				<span class="text-sm">{data.profile?.id ?? '—'}</span>
			</div>
			<div class="space-y-2">
				<label for="displayName" class="text-sm font-medium">{$t('konto.profil.anzeigename')}</label>
				<input
					id="displayName"
					name="display_name"
					type="text"
					maxlength="50"
					bind:value={displayName}
					placeholder={data.profile?.id ?? $t('konto.profil.anzeigename')}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>
			<div class="grid gap-1">
				<span class="text-sm font-medium text-muted-foreground">{$t('konto.profil.mitglied_seit')}</span>
				<span class="text-sm">{formatDate(data.profile?.created_at)}</span>
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Issue #2648 — Sprache: eigenes Feld, speichert nur { language }. -->
	<SpracheAuswahl />

	<Card.Root id="kanaele">
		<Card.Header>
			<Card.Title>{$t('konto.kanaele.titel')}</Card.Title>
			<Card.Description>{$t('konto.kanaele.beschreibung')}</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="space-y-2">
				<label for="mailTo" class="text-sm font-medium">{$t('konto.kanaele.mail_label')}</label>
				<div class="flex items-center gap-2">
					<input
						id="mailTo"
						name="mail_to"
						type="email"
						bind:value={mailTo}
						placeholder={$t('konto.kanaele.mail_platzhalter')}
						class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					/>
					{#if mailTo}
						<button
							onclick={() => sendTest('email')}
							disabled={testStatus.email === 'loading'}
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{testStatus.email === 'loading' ? '...' : $t('konto.aktion.test_senden')}
						</button>
					{/if}
				</div>
				{#if testStatus.email === 'ok'}
					<span class="text-sm text-green-600">{$t('konto.aktion.gesendet')}</span>
				{/if}
				{#if testStatus.email === 'error'}
					<span class="text-sm text-red-600">{testError.email}</span>
				{/if}
				{#if data.profile?.pending_contact_address}
					<div
						data-testid="pending-address-notice"
						class="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
					>
						<p>
								{#each textTeile($t('konto.adresse.ausstehend')) as teil}{#if teil.platzhalter === 'neu'}<strong>{data.profile.pending_contact_address}</strong>{:else if teil.platzhalter === 'alt'}<strong>{data.profile.mail_to || data.profile.email}</strong>{:else}{teil.text}{/if}{/each}
							</p>
						<button
							type="button"
							onclick={resendVerification}
							disabled={resendStatus === 'loading'}
							class="inline-flex items-center min-h-[44px] text-sm font-medium text-blue-700 hover:underline disabled:opacity-50"
						>
							{$t('konto.adresse.mail_erneut')}
						</button>
						{#if resendStatus === 'ok'}
							<span class="text-sm text-green-700">{$t('konto.adresse.mail_verschickt')}</span>
						{/if}
						{#if resendStatus === 'error'}
							<span class="text-sm text-red-700">{$t('konto.aktion.senden_fehlgeschlagen')}</span>
						{/if}
					</div>
				{/if}
			</div>

			<div class="space-y-2">
				<label for="smsTo" class="block text-sm font-medium">{$t('konto.sms.label')}</label>
				<input
					id="smsTo"
					name="sms_to"
					type="tel"
					bind:value={smsTo}
					placeholder={SMS_BEISPIEL}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
				<p class="mt-1 text-xs text-gray-500">{$t('konto.sms.format_hinweis')}</p>
				<!-- Issue #2406 (AC-13): solange die Nummer nicht per Code bewiesen ist,
				     geht an sie keine SMS raus (Sperre in config.py). Der Hinweis macht
				     das sichtbar und traegt den einzigen Weg heraus. -->
				{#if smsZuBestaetigen}
					<div
						data-testid="sms-pending-notice"
						class="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
					>
						<p>
								{#each textTeile($t('konto.sms.ausstehend')) as teil}{#if teil.platzhalter === 'nummer'}<strong>{smsZuBestaetigen}</strong>{:else}{teil.text}{/if}{/each}
							</p>
						<input
							data-testid="sms-code-input"
							name="sms_code"
							inputmode="numeric"
							autocomplete="one-time-code"
							bind:value={smsCode}
							placeholder={$t('konto.sms.code_platzhalter')}
							class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
						/>
						<div class="flex flex-wrap items-center gap-4">
							<button
								type="button"
								onclick={verifySmsCode}
								disabled={smsVerifyStatus === 'loading'}
								class="inline-flex items-center min-h-[44px] text-sm font-medium text-blue-700 hover:underline disabled:opacity-50"
							>
								{$t('konto.sms.code_bestaetigen')}
							</button>
							<button
								type="button"
								onclick={resendSmsCode}
								disabled={smsResendStatus === 'loading'}
								class="inline-flex items-center min-h-[44px] text-sm font-medium text-blue-700 hover:underline disabled:opacity-50"
							>
								{$t('konto.sms.code_erneut')}
							</button>
						</div>
						{#if smsResendStatus === 'ok'}
							<span class="text-sm text-green-700">{$t('konto.sms.code_verschickt')}</span>
						{/if}
						{#if smsVerifyError}
							<span class="text-sm text-red-700">{smsVerifyError}</span>
						{/if}
					</div>
				{/if}
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium">{KANAL.telegram}</label>
				{#if telegramConnected}
					<div class="flex items-center gap-3">
						<span class="text-sm text-green-700">{$t('konto.telegram.verbunden', { suffix: telegramChatIdSuffix })}</span>
						<button
							onclick={() => sendTest('telegram')}
							disabled={testStatus.telegram === 'loading'}
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{testStatus.telegram === 'loading' ? '...' : $t('konto.aktion.test_senden')}
						</button>
						<button
							onclick={disconnectTelegram}
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-destructive hover:underline"
						>
							{$t('konto.telegram.trennen')}
						</button>
					</div>
				{:else}
					<div class="flex items-center gap-3">
						<span class="text-sm text-muted-foreground">{$t('konto.telegram.nicht_verbunden')}</span>
						<button
							onclick={connectTelegram}
							disabled={telegramConnecting}
							class="shrink-0 inline-flex items-center min-h-[44px] text-sm text-blue-600 hover:underline disabled:opacity-50"
						>
							{telegramConnecting ? $t('konto.telegram.warte') : $t('konto.telegram.verbinden')}
						</button>
					</div>
				{/if}
				{#if testStatus.telegram === 'ok'}
					<span class="text-sm text-green-600">{$t('konto.aktion.gesendet')}</span>
				{/if}
				{#if testStatus.telegram === 'error'}
					<span class="text-sm text-red-600">{testError.telegram}</span>
				{/if}
			</div>

			<button
				onclick={save}
				class="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				{$t('konto.aktion.speichern')}
			</button>
		</Card.Content>
	</Card.Root>

	<!-- Issue #2154 Scheibe B — Premium-SMS-Verknüpfungscode (nur Tier Premium) -->
	{#if shouldShowPremiumSmsLinkCard(data.profile?.tier)}
		<PremiumSmsLinkCard
			tier={data.profile?.tier}
			exists={linkCodeExists}
			codeValue={linkCodeValue}
			busy={linkCodeBusy}
			errorMsg={linkCodeErrorMsg}
			showRenewConfirm={showRenewConfirm}
			onGenerateOrRenewClick={onGenerateOrRenewClick}
			onDialogConfirm={onDialogConfirm}
			onDialogCancel={onDialogCancel}
		/>
	{/if}

	<!-- Issue #2246 — Passkeys verwalten -->
	<Card.Root data-testid="passkeys-card">
		<Card.Header>
			<Card.Title>{$t('konto.passkey.titel')}</Card.Title>
		</Card.Header>
		<Card.Content class="space-y-4">
			{#if passkeySuccessMsg}
				<div class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
					{passkeySuccessMsg}
				</div>
			{/if}
			{#if passkeyErrorMsg}
				<div
					data-testid="passkey-error"
					class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive"
				>
					{passkeyErrorMsg}
				</div>
			{/if}

			{#if passkeys.length === 0}
				<p data-testid="passkey-empty" class="text-sm text-muted-foreground">
					{$t('konto.passkey.leer')}
				</p>
			{:else}
				<ul class="space-y-2">
					{#each passkeys as pk (pk.id)}
						<li
							data-testid="passkey-row"
							class="flex items-start justify-between gap-3 rounded-md border border-input p-3"
						>
							<div class="space-y-1">
								<span class="block text-sm font-medium">{passkeyTitel(pk)}</span>
								{#if pk.label?.trim() && pk.authenticator_name?.trim()}
									<span class="block text-sm text-muted-foreground">{pk.authenticator_name}</span>
								{/if}
								<span class="block text-sm text-muted-foreground">
									{$t('konto.passkey.angelegt_am', { datum: formatDate(pk.created_at) })}
								</span>
								{#if pk.last_used_at}
									<span data-testid="passkey-last-used" class="block text-sm text-muted-foreground">
										{$t('konto.passkey.zuletzt_verwendet', { datum: formatDate(pk.last_used_at) })}
									</span>
								{/if}
							</div>
							<button
								onclick={() => (deletePasskeyTarget = pk)}
								class="shrink-0 inline-flex items-center gap-1 min-h-[44px] text-sm text-destructive hover:underline"
							>
								<Trash2Icon class="h-4 w-4" aria-hidden="true" />
								{$t('konto.aktion.loeschen')}
							</button>
						</li>
					{/each}
				</ul>
			{/if}

			{#if passkeySupported === true}
				<Btn onclick={() => (showPasskeyDialog = true)} disabled={passkeyBusy}>
					{$t('konto.passkey.hinzufuegen')}
				</Btn>
			{:else if passkeySupported === false}
				<p data-testid="passkey-unsupported" class="text-sm text-muted-foreground">
					{$t('konto.passkey.nicht_unterstuetzt')}
				</p>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title>{$t('konto.passwort.titel')}</Card.Title>
		</Card.Header>
		<Card.Content class="space-y-4">
			<div class="space-y-2">
				<label for="oldPassword" class="text-sm font-medium">{$t('konto.passwort.aktuell')}</label>
				<input
					id="oldPassword"
					type="password"
					bind:value={oldPassword}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<div class="space-y-2">
				<label for="newPassword" class="text-sm font-medium">{$t('konto.passwort.neu')}</label>
				<input
					id="newPassword"
					type="password"
					bind:value={newPassword}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<div class="space-y-2">
				<label for="confirmNewPassword" class="text-sm font-medium">{$t('konto.passwort.neu_bestaetigen')}</label>
				<input
					id="confirmNewPassword"
					type="password"
					bind:value={confirmNewPassword}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			{#if pwSuccessMsg}
				<div class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
					{pwSuccessMsg}
				</div>
			{/if}

			{#if pwErrorMsg}
				<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
					{pwErrorMsg}
				</div>
			{/if}

			<button
				onclick={changePassword}
				class="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				{$t('konto.passwort.titel')}
			</button>
		</Card.Content>
	</Card.Root>

	<!-- Issue #344 — Wetter-Profile (User-MetricPresets) -->
	<Card.Root data-testid="wetter-profile-card">
		<Card.Header>
			<Card.Title>{$t('konto.wetter_profile.titel')}</Card.Title>
			<Card.Description>{$t('konto.wetter_profile.beschreibung')}</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if isEmpty(presets)}
				<p data-testid="wetter-profile-empty" class="text-sm text-muted-foreground">
					{$t('konto.wetter_profile.leer')}
				</p>
			{:else}
				<div class="space-y-2">
					{#each presets as p (p.id)}
						<div data-testid="wetter-profile-row-{p.id}" class="flex items-center justify-between gap-2 text-sm">
							{#if editingId === p.id}
								<input
									data-testid="wetter-profile-rename-input-{p.id}"
									bind:value={editName}
									onkeydown={(e) => { if (e.key === 'Enter') saveRename(p.id); if (e.key === 'Escape') cancelEdit(); }}
									class="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
								/>
								<div class="flex items-center gap-1">
									<button
										onclick={() => saveRename(p.id)}
										aria-label={$t('konto.aktion.speichern')}
										class="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent"
									>
										<CheckIcon class="h-4 w-4" />
									</button>
									<button
										onclick={cancelEdit}
										aria-label={$t('aktionen.abbrechen')}
										class="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent"
									>
										<XIcon class="h-4 w-4" />
									</button>
								</div>
							{:else}
								<span data-testid="wetter-profile-name-{p.id}" class="font-medium">{p.name}</span>
								<div class="flex items-center gap-2">
									<Badge variant="secondary" data-testid="wetter-profile-count-{p.id}">{(void $locale, metricCountLabel(p))}</Badge>
									{#if showDefaultBadge(p)}
										<Badge variant="secondary" data-testid="wetter-profile-default-{p.id}">{$t('konto.wetter_profile.standard')}</Badge>
									{/if}
									<button
										data-testid="wetter-profile-edit-{p.id}"
										onclick={() => startEdit(p)}
										aria-label={$t('konto.wetter_profile.umbenennen')}
										class="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-accent"
									>
										<PencilIcon class="h-4 w-4" />
									</button>
									<button
										data-testid="wetter-profile-delete-{p.id}"
										onclick={() => deletePreset(p)}
										aria-label={$t('konto.aktion.loeschen')}
										class="inline-flex h-9 w-9 items-center justify-center rounded-md text-destructive hover:bg-destructive/10"
									>
										<Trash2Icon class="h-4 w-4" />
									</button>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
			{#if presetError}
				<p class="mt-2 text-sm text-destructive">{presetError}</p>
			{/if}
		</Card.Content>
	</Card.Root>

	<!-- System-Status Section (migrated from settings) -->
	<div id="system-status" class="space-y-6">
		<!-- Card: Deine Reports -->
		<Card.Root>
			<Card.Header>
				<Card.Title>{$t('konto.reports.titel')}</Card.Title>
			</Card.Header>
			<Card.Content>
				{#if data.scheduler === null}
					<p class="text-sm text-muted-foreground">{$t('konto.reports.nicht_verfuegbar')}</p>
				{:else if data.scheduler?.jobs && data.scheduler.jobs.length > 0}
					<div class="space-y-3">
						{#each data.scheduler.jobs.filter((j: any) => j.id in userJobs) as job}
							{@const dot = lastRunDot(job.last_run)}
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-2">
									<span class="inline-block size-2 rounded-full"
										data-last-run-dot={dot}
										class:bg-green-500={dot === 'ok'}
										class:bg-red-500={dot === 'error'}
										class:bg-slate-500={dot === 'neutral'}
										class:bg-gray-300={dot === 'none'}
									></span>
									<span class="font-medium">{$t(userJobs[job.id])}</span>
								</div>
								<div class="flex items-center gap-4 text-sm text-muted-foreground">
									<span>{$t('konto.reports.naechste_pruefung', { zeit: imBrowser ? formatNextRun(job.next_run) : '—' })}</span>
									<span>{$t('konto.reports.zuletzt', { zeit: job.last_run?.time ? timeAgo(job.last_run.time) : '—' })}</span>
								</div>
							</div>
							{#if job.last_run?.status === 'error'}
								<p class="ml-4 text-sm text-destructive">{job.last_run?.error ? $t('konto.reports.lauf_fehlgeschlagen_mit', { fehler: job.last_run.error }) : $t('konto.reports.lauf_fehlgeschlagen')}</p>
							{/if}
						{/each}
					</div>
				{:else}
					<p class="text-sm text-muted-foreground">{$t('konto.reports.keine')}</p>
				{/if}
			</Card.Content>
		</Card.Root>

		<!-- Card: Dein Account -->
		<Card.Root data-testid="account-section">
			<Card.Header>
				<Card.Title>{$t('konto.account.titel')}</Card.Title>
			</Card.Header>
			<Card.Content>
				<!-- Nutzerlevel (Issue #1068) — immer sichtbar -->
				<div data-testid="tier" class="mb-4">
					<p class="text-sm font-medium mb-2">{$t('konto.level.titel')}</p>
					<Badge variant="secondary">{tierLabel(data.profile?.tier)}</Badge>
				</div>

				<!-- Level-Wechsel beantragen (Issue #1071) -->
				<div data-testid="tier-change" class="mb-4">
					<p class="text-sm font-medium mb-2">{$t('konto.level.wechsel_titel')}</p>
					{#if pendingTier}
						<p data-testid="tier-change-pending" class="text-sm text-muted-foreground mb-2">
							{#each textTeile($t('konto.level.ausstehend')) as teil}{#if teil.platzhalter === 'level'}<span class="font-medium">{tierLabel(pendingTier)}</span>{:else}{teil.text}{/if}{/each}
						</p>
						{#if tierNotNotified}
							<p
								data-testid="tier-change-not-notified"
								role="alert"
								class="text-sm font-medium text-destructive border border-destructive rounded-md px-3 py-2 mb-2"
							>
								{$t('konto.level.nicht_benachrichtigt')}
							</p>
						{/if}
					{/if}
					<div class="flex flex-wrap items-center gap-2">
						<select
							data-testid="tier-change-select"
							bind:value={requestedTierChoice}
							class="h-9 rounded-md border border-input bg-background px-3 text-sm"
						>
							{#each TIER_OPTIONS as opt}
								<option value={opt}>{tierLabel(opt)}</option>
							{/each}
						</select>
						<Btn
							data-testid="tier-change-submit"
							variant="outline"
							size="sm"
							disabled={tierChangeStatus === 'loading'}
							onclick={requestTierChange}
						>
							{tierChangeStatus === 'loading' ? $t('konto.level.wird_gesendet') : $t('konto.level.antrag_stellen')}
						</Btn>
					</div>
					{#if tierChangeStatus === 'ok' && tierChangeNotified}
						<p class="text-sm text-green-600 mt-2">{$t('konto.level.antrag_gesendet')}</p>
					{/if}
					{#if tierChangeStatus === 'error' && tierChangeError}
						<p class="text-sm text-destructive mt-2">{tierChangeError}</p>
					{/if}
				</div>

				<!-- Zähler mit Tarif-Grenzen "x von N" (Issue #2482); unbegrenzt: nur "x" -->
				<div class="space-y-2 mb-4" data-testid="mengen-quote">
					<div class="flex items-center justify-between text-sm">
						<span>{$t('konto.menge.aktive_trips')}</span>
						<a href="/trips" class="g-link-tap font-medium hover:underline" data-testid="quota-trips">{(void $locale, formatQuotaUsage(countActive(data.trips), quota?.trips))}</a>
					</div>
					<div class="flex items-center justify-between text-sm">
						<span>{$t('konto.menge.aktive_vergleiche')}</span>
						<a href="/compare" class="g-link-tap font-medium hover:underline" data-testid="quota-compare-presets">{(void $locale, formatQuotaUsage(countActive(data.comparePresets), quota?.compare_presets))}</a>
					</div>
					<div class="flex items-center justify-between text-sm">
						<span>{$t('konto.menge.locations')}</span>
						<a href="/locations" class="g-link-tap font-medium hover:underline" data-testid="quota-locations">{(void $locale, formatQuotaUsage(Array.isArray(data.locations) ? data.locations.length : 0, quota?.locations))}</a>
					</div>
				</div>

				<!-- SMS-/Premium-SMS-Tageskontingent (Issue #2412 S4b) -->
				{#if data.smsDailyUsage && (shouldShowSmsUsageRow(data.smsDailyUsage.sms?.limit) || shouldShowSmsUsageRow(data.smsDailyUsage.premium_sms?.limit))}
					<div data-testid="sms-daily-usage" class="mb-4">
						<p class="text-sm font-medium mb-2">{$t('konto.kontingent.titel')}</p>
						{#if shouldShowSmsUsageRow(data.smsDailyUsage.sms?.limit)}
							<div class="flex items-center justify-between text-sm">
								<span>{KANAL.sms}</span>
								<span class="font-medium">
									{$t('konto.menge.von', { anzahl: data.smsDailyUsage.sms.used, grenze: data.smsDailyUsage.sms.limit })}
								</span>
							</div>
							<p class="text-xs text-muted-foreground mb-2">
								{$t('konto.kontingent.davon', { briefings: data.smsDailyUsage.sms.limit - data.smsDailyUsage.sms.reserve, reserve: data.smsDailyUsage.sms.reserve })}
							</p>
						{/if}
						{#if shouldShowSmsUsageRow(data.smsDailyUsage.premium_sms?.limit)}
							<div class="flex items-center justify-between text-sm">
								<span>{KANAL.premiumSms}</span>
								<span class="font-medium">
									{#if data.smsDailyUsage.premium_sms.used > data.smsDailyUsage.premium_sms.limit}
										{$t('konto.menge.von', { anzahl: data.smsDailyUsage.premium_sms.limit, grenze: data.smsDailyUsage.premium_sms.limit })}
										{$tn('konto.kontingent.antworten', data.smsDailyUsage.premium_sms.used - data.smsDailyUsage.premium_sms.limit)}
									{:else}
										{$t('konto.menge.von', { anzahl: data.smsDailyUsage.premium_sms.used, grenze: data.smsDailyUsage.premium_sms.limit })}
									{/if}
								</span>
							</div>
							<p class="text-xs text-muted-foreground">
								{$t('konto.kontingent.davon', { briefings: data.smsDailyUsage.premium_sms.limit - data.smsDailyUsage.premium_sms.reserve, reserve: data.smsDailyUsage.premium_sms.reserve })}
							</p>
						{/if}
					</div>
				{/if}

				<!-- Benachrichtigungskanäle -->
				<div data-testid="channels" class="mb-4">
					<p class="text-sm font-medium mb-2">{$t('konto.benachrichtigung.titel')}</p>
					{#if data.profile && (data.profile.mail_to || data.profile.telegram_chat_id)}
						<div class="flex flex-wrap gap-2">
							{#if data.profile.mail_to}
								<Badge variant="secondary">{KANAL.email}: {data.profile.mail_to}</Badge>
							{/if}
							{#if data.profile.telegram_chat_id}
								<Badge variant="secondary">{KANAL.telegram}: ...{data.profile.telegram_chat_id.slice(-3)}</Badge>
							{/if}
						</div>
					{:else}
						<p class="text-sm text-muted-foreground">
							{#each textTeile($t('konto.benachrichtigung.keine')) as teil}{#if teil.platzhalter === 'link'}<a href="/account" class="underline hover:text-foreground">{$t('konto.benachrichtigung.einrichten')}</a>{:else}{teil.text}{/if}{/each}
						</p>
					{/if}
				</div>

				<!-- Wetter-Modelle -->
				<div data-testid="weather-models">
					<p class="text-sm font-medium mb-2">{$t('konto.modelle.titel')}</p>
					{#if data.locations.length > 0}
						<div class="space-y-1">
							{#each data.locations as loc}
								<p class="text-sm text-muted-foreground">
									{loc.name} → {getProvider(loc.lat, loc.lon)}
								</p>
							{/each}
						</div>
					{:else}
						<p class="text-sm text-muted-foreground">
							{#each textTeile($t('konto.modelle.keine')) as teil}{#if teil.platzhalter === 'link'}<a href="/locations" class="underline hover:text-foreground">{$t('konto.modelle.anlegen')}</a>{:else}{teil.text}{/if}{/each}
						</p>
					{/if}
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Card: Verfügbarkeit -->
		<Card.Root>
			<Card.Header>
				<Card.Title>{$t('konto.status.titel')}</Card.Title>
			</Card.Header>
			<Card.Content>
				<div class="flex items-center gap-2">
					{#if data.health === null}
						<span class="inline-block size-3 rounded-full bg-red-500"></span>
						<span class="font-medium">{$t('konto.status.nicht_erreichbar')}</span>
					{:else if data.health.status === 'ok'}
						<span class="inline-block size-3 rounded-full bg-green-500"></span>
						<span class="font-medium">{$t('konto.status.laeuft')}</span>
					{:else if data.health.status === 'degraded'}
						<span class="inline-block size-3 rounded-full bg-yellow-500"></span>
						<span class="font-medium">{$t('konto.status.eingeschraenkt')}</span>
					{:else}
						<span class="inline-block size-3 rounded-full bg-red-500"></span>
						<span class="font-medium">{$t('konto.status.nicht_erreichbar')}</span>
					{/if}
				</div>
				{#if data.health?.version}
					<p class="mt-1 text-sm text-muted-foreground">v{data.health.version}</p>
				{/if}
			</Card.Content>
		</Card.Root>
	</div>

	<!-- Wetter-Templates Card -->
	<Card.Root>
		<Card.Header>
			<Card.Title>{$t('konto.templates.titel')}</Card.Title>
			<Card.Description>{$t('konto.templates.beschreibung')}</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if !data.templates || data.templates.length === 0}
				<p class="text-sm text-muted-foreground">{$t('konto.templates.keine')}</p>
			{:else}
				<div class="space-y-2">
					{#each data.templates as tpl}
						<div class="flex items-center justify-between text-sm">
							<span class="font-medium">{tpl.label ?? tpl.name ?? tpl.id}</span>
							{#if tpl.metrics}
								<Badge variant="secondary">{$tn('konto.metriken', tpl.metrics.length)}</Badge>
							{:else if tpl.description ?? tpl.type}
								<span class="text-muted-foreground">{tpl.description ?? tpl.type}</span>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title>{$t('konto.anmeldungen.titel')}</Card.Title>
		</Card.Header>
		<Card.Content>
			<p class="mb-4 text-sm text-muted-foreground">
				{$t('konto.anmeldungen.text')}
			</p>
			<Btn variant="outline" onclick={logoutAllDevices}>{$t('konto.anmeldungen.alle_abmelden')}</Btn>
			{#if logoutAllErrorMsg}
				<p class="mt-2 text-sm text-red-600">{logoutAllErrorMsg}</p>
			{/if}
		</Card.Content>
	</Card.Root>

	<!--
		Issue #2270: eigene Karte, bewusst VOR und nicht IN der Gefahrenzone —
		der Export ist nichts Destruktives.
	-->
	<Card.Root id="datenexport" data-testid="data-export-card">
		<Card.Header>
			<Card.Title>{$t('konto.daten.titel')}</Card.Title>
		</Card.Header>
		<Card.Content>
			<p class="mb-4 text-sm text-muted-foreground">
				{$t('konto.daten.text')}
			</p>
			<Btn
				variant="outline"
				data-testid="data-export-button"
				disabled={exportBusy}
				onclick={exportiereMeineDaten}
			>
				{exportBusy ? $t('konto.daten.wird_erstellt') : $t('konto.daten.herunterladen')}
			</Btn>
			{#if exportErrorMsg}
				<p class="mt-2 text-sm text-red-600" data-testid="data-export-error">{exportErrorMsg}</p>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root class="border-red-200" data-testid="danger-zone-card">
		<Card.Header>
			<Card.Title class="text-red-700">{$t('konto.loeschen.zone_titel')}</Card.Title>
		</Card.Header>
		<Card.Content>
			<p class="mb-4 text-sm text-muted-foreground">
				{$t('konto.loeschen.zone_text')}
			</p>
			<button
				onclick={deleteAccount}
				class="inline-flex h-10 items-center justify-center rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white ring-offset-background hover:bg-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
			>
				{$t('konto.loeschen.titel')}
			</button>
		</Card.Content>
	</Card.Root>

	<!-- Preset löschen Dialog -->
	<Dialog.Root
		open={deletePresetTarget !== null}
		onOpenChange={(open) => { if (!open) deletePresetTarget = null; }}
	>
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>{$t('konto.wetter_profile.loeschen_titel')}</Dialog.Title>
				<Dialog.Description>
					{$t('konto.wetter_profile.loeschen_frage', { name: deletePresetTarget?.name ?? '' })}
				</Dialog.Description>
			</Dialog.Header>
			<Dialog.Footer>
				<Btn variant="outline" onclick={() => (deletePresetTarget = null)}>{$t('aktionen.abbrechen')}</Btn>
				<Btn variant="destructive" onclick={confirmDeletePreset}>{$t('konto.aktion.loeschen')}</Btn>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>

	<!-- Passkey löschen Rückfrage (#2246) -->
	<Dialog.Root
		open={deletePasskeyTarget !== null}
		onOpenChange={(open) => { if (!open) deletePasskeyTarget = null; }}
	>
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>{$t('konto.passkey.loeschen_titel')}</Dialog.Title>
				<Dialog.Description>
					{$t('konto.passkey.loeschen_frage', { name: deletePasskeyTarget ? passkeyTitel(deletePasskeyTarget) : '' })}
				</Dialog.Description>
			</Dialog.Header>
			<Dialog.Footer>
				<Btn
					variant="outline"
					data-testid="passkey-delete-cancel"
					onclick={() => (deletePasskeyTarget = null)}>{$t('aktionen.abbrechen')}</Btn
				>
				<Btn variant="destructive" data-testid="passkey-delete-confirm" onclick={confirmDeletePasskey}
					>{$t('konto.aktion.loeschen')}</Btn
				>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>

	<!-- Passkey anlegen Dialog (#2246) -->
	<Dialog.Root
		open={showPasskeyDialog}
		onOpenChange={(open) => { if (!open && !passkeyBusy) showPasskeyDialog = false; }}
	>
		<!--
			Waehrend der Zeremonie darf sich der Dialog auf KEINEM Weg schliessen
			(AC-9). `onOpenChange` allein reicht dafuer nicht: der Dialog schliesst
			seinen eigenen Zustand bei Escape/Aussenklick/X selbst und meldet das
			nur noch — der Waechter dort ueberspringt dann bloss das Zuruecksetzen
			von `showPasskeyDialog`, die Anzeige ist da schon weg (gemessen
			09.09.2026: Dialog nach 77 ms bis 1,5 s weg, waehrend `passkeyBusy`
			noch stand und keine Rueckmeldung vorlag). Das Schliessen muss deshalb
			an der Quelle abgelehnt werden; `onOpenChange` bleibt als zweite
			Sicherung stehen.
		-->
		<Dialog.Content
			escapeKeydownBehavior={passkeyBusy ? 'ignore' : 'close'}
			interactOutsideBehavior={passkeyBusy ? 'ignore' : 'close'}
			showCloseButton={!passkeyBusy}
		>
			<Dialog.Header>
				<Dialog.Title>{$t('konto.passkey.hinzufuegen')}</Dialog.Title>
				<Dialog.Description>
					{$t('konto.passkey.dialog_text')}
				</Dialog.Description>
			</Dialog.Header>
			<div class="space-y-2">
				<label for="passkeyLabel" class="text-sm font-medium">{$t('konto.passkey.bezeichnung')}</label>
				<input
					id="passkeyLabel"
					data-testid="passkey-label-input"
					type="text"
					maxlength="50"
					disabled={passkeyBusy}
					bind:value={passkeyLabel}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>
			{#if passkeyBusy}
				<p data-testid="passkey-create-pending" class="text-sm text-muted-foreground">
					{$t('konto.passkey.warte')}
				</p>
			{/if}
			<Dialog.Footer>
				<Btn variant="outline" disabled={passkeyBusy} onclick={() => (showPasskeyDialog = false)}>
					{$t('aktionen.abbrechen')}
				</Btn>
				<Btn data-testid="passkey-create-confirm" disabled={passkeyBusy} onclick={createPasskey}>
					{$t('konto.passkey.anlegen')}
				</Btn>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>

	<!-- Auf allen Geräten abmelden Dialog -->
	<Dialog.Root
		open={showLogoutAllDialog}
		onOpenChange={(open) => { if (!open) showLogoutAllDialog = false; }}
	>
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>{$t('konto.anmeldungen.alle_abmelden')}</Dialog.Title>
				<Dialog.Description>
					{$t('konto.anmeldungen.dialog_text')}
				</Dialog.Description>
			</Dialog.Header>
			<Dialog.Footer>
				<Btn variant="outline" onclick={() => (showLogoutAllDialog = false)}>{$t('aktionen.abbrechen')}</Btn>
				<Btn variant="destructive" onclick={confirmLogoutAllDevices}>{$t('nav.abmelden')}</Btn>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>

	<!-- Account löschen Dialog -->
	<Dialog.Root
		open={showDeleteAccountDialog}
		onOpenChange={(open) => { if (!open) showDeleteAccountDialog = false; }}
	>
		<Dialog.Content>
			<Dialog.Header>
				<Dialog.Title>{$t('konto.loeschen.titel')}</Dialog.Title>
				<Dialog.Description>
					{deleteHasPassword ? $t('konto.loeschen.frage_mit_passwort') : $t('konto.loeschen.frage_ohne_passwort')}
				</Dialog.Description>
			</Dialog.Header>
			<div class="space-y-4">
				{#if deleteHasPassword}
					<div class="space-y-2">
						<label for="deletePassword" class="text-sm font-medium">{$t('konto.loeschen.passwort')}</label>
						<input
							id="deletePassword"
							type="password"
							autocomplete="current-password"
							data-testid="delete-account-password"
							bind:value={deletePassword}
							class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
						/>
					</div>
				{/if}
				<div class="space-y-2">
					<Btn
						variant="outline"
						class="h-auto w-full min-w-0 whitespace-normal [overflow-wrap:anywhere]"
						data-testid="delete-account-send-code"
						disabled={deleteBusy}
						onclick={requestDeleteCode}
					>
						{$t('konto.loeschen.code_senden', { adresse: deleteCodeAddress })}
					</Btn>
					{#if deleteCodeSent}
						<p class="text-sm">{$t('konto.loeschen.code_verschickt')}</p>
					{/if}
					<label for="deleteCode" class="block text-sm font-medium">{$t('konto.loeschen.code')}</label>
					<input
						id="deleteCode"
						type="text"
						inputmode="numeric"
						autocomplete="one-time-code"
						maxlength="6"
						data-testid="delete-account-code"
						bind:value={deleteCode}
						class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					/>
				</div>
				{#if deleteDialogMsg}
					<p class="text-sm text-red-700" data-testid="delete-account-error">{deleteDialogMsg}</p>
				{/if}
			</div>
			<Dialog.Footer>
				<Btn variant="outline" onclick={() => (showDeleteAccountDialog = false)}>{$t('aktionen.abbrechen')}</Btn>
				<Btn
					variant="destructive"
					data-testid="delete-account-confirm"
					disabled={deleteBusy || (!deletePassword && deleteCode.trim() === '')}
					onclick={confirmDeleteAccount}
				>
					{$t('konto.loeschen.titel')}
				</Btn>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>
</div>
