<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { ActionData } from './$types.js';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import SprachUmschalter from '$lib/components/ui/SprachUmschalter.svelte';
	import { abmeldungLiegtVor, raeumeGeraetespeicher, vergissAbmeldung } from '$lib/pwa/geraetespeicher';
	import { isWebAuthnSupported, loginWithPasskey, loginWithDiscoverablePasskey } from '$lib/passkey';
	import { t, type MessageKey } from '$lib/i18n';

	let { form, data }: { form: ActionData; data: { googleEnabled: boolean } } = $props();
	const registered = $derived($page.url.searchParams.get('registered') === '1');
	// Issue #1006 — Sitzung abgelaufen (zentraler 401-Redirect aus api.ts).
	const sessionExpired = $derived($page.url.searchParams.get('expired') === '1');
	// Issue #2147 Scheibe C (AC-18) — Ablehnungen des Google-Redirect-Flusses.
	// Neutral formuliert: keine Aussage, ob eine Adresse im System existiert.
	// Unbekannte Codes zeigen nichts.
	// Map statt Objekt-Literal: ein Code wie `constructor` traefe sonst
	// Object.prototype. Issue #2650: Code -> Katalogschluessel, Text entsteht bei der Anzeige.
	const GOOGLE_FEHLER_SCHLUESSEL = new Map<string, MessageKey>([
		['oauth_link_failed', 'auth.login.google_fehler_verknuepfung'],
		['oauth_failed', 'auth.login.google_fehler_allgemein'],
		['email_not_verified', 'auth.login.email_nicht_bestaetigt']
	]);
	const googleFehler = $derived(
		GOOGLE_FEHLER_SCHLUESSEL.get($page.url.searchParams.get('error') ?? '') ?? null
	);
	const googleFehlerText = $derived(googleFehler ? $t(googleFehler) : '');
	// Issue #2650: Fehlercode der Login-Action -> Katalogschluessel. Unbekannte
	// Codes zeigt die Seite unveraendert roh an (wie bisher).
	const FORM_FEHLER_SCHLUESSEL = new Map<string, MessageKey>([
		['Rate limit exceeded', 'auth.fehler.zu_viele_versuche'],
		['Invalid credentials', 'auth.login.ungueltige_daten'],
		['Username and password required', 'auth.login.pflichtfelder']
	]);
	const formFehlerText = $derived.by(() => {
		const code = form?.error ?? '';
		const schluessel = FORM_FEHLER_SCHLUESSEL.get(code);
		return schluessel ? $t(schluessel) : code;
	});

	// Issue #2128 AC-11/AC-12 — Raeumen NUR nach einem echten Abmelde-Vorgang.
	// Auf /login landet auch, wessen Sitzung abgelaufen ist oder wer die Seite
	// schlicht aufruft; bedingungsloses Raeumen wuerde die Offline-Faehigkeit
	// genau dann zerstoeren, wenn sie gebraucht wird.
	//
	// Das Merkmal wird erst nach BESTAETIGTEM Raeumen verbraucht (AC-24):
	// scheitert eine Speicher-Schnittstelle, bliebe der Rest sonst fuer immer
	// stehen -- ein spaeterer Aufruf der Anmeldeseite waere nach AC-12
	// zurecht kein Abmelde-Vorgang mehr und duerfte nichts nachholen.
	onMount(() => {
		if (!abmeldungLiegtVor($page.url)) return;
		void raeumeGeraetespeicher()
			.then((gelungen) => {
				if (gelungen) vergissAbmeldung();
			})
			.catch(() => {});
	});

	let username = $state(form?.username ?? '');

	// Issue #2247 — Passkey als erster Anmeldeweg auf dem Handy.
	//
	// Tri-State UMGEKEHRT gegenueber der Konto-Seite (#2246): `null` (noch nicht
	// gemessen) UND `true` zeigen den Knopf, erst ein gemessenes `false` wechselt
	// auf den Hinweistext. Nur so steht der Knopf bereits in der vom Server
	// ausgelieferten Seite (`window` gibt es dort nie) -- entstuende er erst im
	// Browser, verschoebe sich beim Nachladen alles darunter.
	let webAuthnFaehig = $state<boolean | null>(null);
	let passkeyFehler = $state<MessageKey | null>(null);
	let usernameFeld = $state<HTMLInputElement | null>(null);
	// Laufende Autofill-Anbindung (Conditional UI). Wird NUR abgebrochen, wenn
	// der Nutzer die manuelle Zeremonie startet -- ein zweiter credentials.get()
	// scheiterte sonst an der noch offenen ersten Anfrage.
	let autofillAbbruch: AbortController | null = null;

	onMount(() => {
		webAuthnFaehig = isWebAuthnSupported();
		if (webAuthnFaehig) void starteAutofillAnbindung();
		return () => autofillAbbruch?.abort();
	});

	/**
	 * Bietet den hinterlegten Passkey als Vorschlag im Benutzernamen-Feld an.
	 * Startet nur, wenn der Browser das selbst meldet — die Pruefung laeuft rein
	 * im Browser und verbraucht kein Anfrage-Kontingent.
	 */
	async function starteAutofillAnbindung(): Promise<void> {
		try {
			const pkc = window.PublicKeyCredential as unknown as {
				isConditionalMediationAvailable?: () => Promise<boolean>;
			};
			if (typeof pkc?.isConditionalMediationAvailable !== 'function') return;
			if (!(await pkc.isConditionalMediationAvailable())) return;
			autofillAbbruch = new AbortController();
			await loginWithDiscoverablePasskey(autofillAbbruch.signal);
		} catch {
			// Der Hintergrundweg bleibt stumm: ein Abbruch ist hier der Normalfall
			// (der Nutzer nimmt stattdessen den Knopf), und eine Fehlermeldung fuer
			// etwas, das der Nutzer nie angestossen hat, waere nur Laerm.
		}
	}

	/** Rohe Zeremonie-Fehler auf einen Katalogschluessel abbilden (Muster: account/+page.svelte). */
	function passkeyFehlertext(e: unknown): MessageKey {
		const name = (e as { name?: string })?.name;
		// Abbruch, Zeitueberschreitung und "kein passender Passkey" meldet WebAuthn
		// ABSICHTLICH als denselben NotAllowedError (Privacy-Design) -- getrennte
		// Texte dafuer sind strukturell unmoeglich, siehe Spec "Known Limitations".
		if (name === 'NotAllowedError' || name === 'AbortError') {
			return 'auth.login.passkey_abgebrochen';
		}
		return 'auth.login.passkey_fehlgeschlagen';
	}

	async function mitPasskeyAnmelden(): Promise<void> {
		passkeyFehler = null;
		if (!username.trim()) {
			// Nicht deaktivieren, sondern fuehren: ein deaktivierter Knopf ist per
			// Tastatur nicht erreichbar und waere als erstes Element auf dem Handy
			// ein toter Auftakt. Die Autofill-Anbindung laeuft dabei WEITER -- sie
			// abzubrechen und neu zu starten kostete ein weiteres Token aus dem
			// geteilten Passkey-Kontingent.
			usernameFeld?.focus();
			return;
		}
		autofillAbbruch?.abort();
		autofillAbbruch = null;
		try {
			await loginWithPasskey(username.trim());
		} catch (e: unknown) {
			passkeyFehler = passkeyFehlertext(e);
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-background">
	<!-- Issue #2247: `flex flex-col gap-6` statt `space-y-6` — `space-y-*` haengt
	     den Abstand an alle Geschwister AUSSER dem ersten in DOKUMENT-Reihenfolge;
	     nach der Umsortierung per `desktop:order-*` saesse er am falschen Element. -->
	<div class="flex w-full max-w-sm flex-col gap-6 p-6">
		<div class="flex justify-end"><SprachUmschalter /></div>
		<div class="space-y-2 text-center">
			<Wordmark size="lg" href="/" />
			<p class="text-muted-foreground text-sm">{$t('auth.login.untertitel')}</p>
		</div>

		{#if registered}
			<!-- Issue #2271 AC-14: seit der Scharfschaltung ist die Anmeldung erst
			     nach bestaetigter Adresse moeglich — eine Aufforderung "melde dich
			     an" schickte den Nutzer in einen Weg, der garantiert scheitert. -->
			<div
				data-testid="login-registered-hint"
				class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800"
			>
				{$t('auth.login.registriert_hinweis')}
			</div>
		{/if}

		{#if sessionExpired}
			<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm" style="color: var(--g-bad);">
				{$t('auth.login.sitzung_abgelaufen')}
			</div>
		{/if}

		{#if googleFehler && !form}
			<div
				data-testid="login-google-error"
				class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm"
				style="color: var(--g-bad);"
			>
				{googleFehlerText}
			</div>
		{/if}

		{#if form?.resent}
			<!-- Issue #2271 AC-13: Quittung des erneuten Versands. Steht VOR dem
			     Hinweis, der weiterhin erklaert, warum die Mail gebraucht wird. -->
			<div
				data-testid="login-resend-confirmed"
				class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800"
			>
				{$t('auth.login.erneut_gesendet')}
			</div>
		{/if}

		{#if form?.error === 'email_not_verified'}
			<!-- Issue #2271 AC-12/AC-13: eigener Zweig VOR dem allgemeinen
			     Fehlerkasten. Das Passwort stimmt hier — der Nutzer braucht den
			     Grund und einen Ausweg, nicht die Meldung fuer falsche Daten. -->
			<div
				data-testid="login-error-email-not-verified"
				class="space-y-3 rounded-md border border-destructive bg-destructive/10 p-3 text-sm"
				style="color: var(--g-bad);"
			>
				<p>
					{$t('auth.login.email_nicht_bestaetigt')}
				</p>
				<form method="POST" action="?/resend">
					<!-- Die Kennung reist verdeckt mit: der Nutzer hat sie gerade
					     eingegeben, sie erneut zu tippen waere reine Schikane. -->
					<input type="hidden" name="username" value={username} />
					<button
						type="submit"
						data-testid="login-resend-submit"
						class="inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground ring-offset-background hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					>
						{$t('auth.login.erneut_senden')}
					</button>
				</form>
			</div>
		{:else if form?.error}
			<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm" style="color: var(--g-bad);">
				{formFehlerText}
			</div>
		{/if}

		<!-- Issue #2247 — Passkey-Weg. Steht im HTML VOR dem Passwort-Formular,
		     damit er auf dem Handy der erste sichtbare Anmeldeweg ist; ab 900px
		     schiebt `desktop:order-1` ihn unter das Formular (Google `order-2`,
		     Fusslinks `order-3` bleiben dahinter). Die Fokusreihenfolge folgt auf
		     dem Desktop weiterhin dem HTML — bewusst, siehe Spec. -->
		<div class="desktop:order-1 space-y-2">
			<!-- Feste Hoehe: der Bereich ist in allen drei Zustaenden (ungeprueft /
			     faehig / nicht faehig) gleich hoch, damit der Inhaltstausch nach der
			     Faehigkeitspruefung nichts darunter verschiebt. -->
			<div data-testid="login-passkey-area" class="flex h-14 items-center justify-center">
				{#if webAuthnFaehig === false}
					<p data-testid="login-passkey-hint" class="text-center text-sm text-muted-foreground">
						{$t('auth.login.passkey_nicht_unterstuetzt')}
					</p>
				{:else}
					<button
						type="button"
						data-testid="login-passkey-btn"
						onclick={mitPasskeyAnmelden}
						class="inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground ring-offset-background hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					>
						{$t('auth.login.passkey_anmelden')}
					</button>
				{/if}
			</div>
			{#if passkeyFehler}
				<div
					data-testid="login-passkey-error"
					class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm"
					style="color: var(--g-bad);"
				>
					{$t(passkeyFehler)}
				</div>
			{/if}
		</div>

		<!-- Issue #2271: `action="?/login"` ist Pflicht — die Seite hat seit dem
		     Resend-Formular zwei benannte Actions und keine `default` mehr. -->
		<form method="POST" action="?/login" class="space-y-4">
			<div class="space-y-2">
				<label for="username" class="text-sm font-medium">{$t('auth.feld.benutzername')}</label>
				<input
					id="username"
					name="username"
					type="text"
					required
					autocomplete="username webauthn"
					bind:value={username}
					bind:this={usernameFeld}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<div class="space-y-2">
				<label for="password" class="text-sm font-medium">{$t('auth.feld.passwort')}</label>
				<input
					id="password"
					name="password"
					type="password"
					required
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				/>
			</div>

			<button
				type="submit"
				class="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				{$t('auth.anmelden')}
			</button>
		</form>
		{#if data.googleEnabled}
			<div class="desktop:order-2 relative">
				<div class="absolute inset-0 flex items-center">
					<span class="w-full border-t border-input"></span>
				</div>
				<div class="relative flex justify-center text-xs uppercase">
					<span class="bg-background px-2 text-muted-foreground">{$t('auth.oder')}</span>
				</div>
			</div>
			<a
				href="/api/auth/google/init"
				class="desktop:order-2 inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground ring-offset-background hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				{$t('auth.login.google_knopf')}
			</a>
		{/if}

		<div class="desktop:order-3 space-y-2">
			<a href="/register" class="block py-3 text-center text-sm text-muted-foreground hover:underline">
				{$t('auth.login.zu_registrieren')}
			</a>
			<a href="/forgot-password" class="block py-3 text-center text-sm text-muted-foreground hover:underline">
				{$t('auth.login.zu_passwort_vergessen')}
			</a>
			<a href="/magic-link" class="block py-3 text-center text-sm text-muted-foreground hover:underline">
				{$t('auth.login.zu_magic_link')}
			</a>
		</div>
	</div>
</div>
