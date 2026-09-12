<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { ActionData } from './$types.js';
	import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte';
	import { abmeldungLiegtVor, raeumeGeraetespeicher, vergissAbmeldung } from '$lib/pwa/geraetespeicher';
	import { isWebAuthnSupported, loginWithPasskey, loginWithDiscoverablePasskey } from '$lib/passkey';

	let { form, data }: { form: ActionData; data: { googleEnabled: boolean } } = $props();
	const registered = $derived($page.url.searchParams.get('registered') === '1');
	// Issue #1006 — Sitzung abgelaufen (zentraler 401-Redirect aus api.ts).
	const sessionExpired = $derived($page.url.searchParams.get('expired') === '1');

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
	let passkeyFehler = $state<string | null>(null);
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

	/** Rohe Zeremonie-Fehler in verstaendliches Deutsch uebersetzen (Muster: account/+page.svelte). */
	function passkeyFehlertext(e: unknown): string {
		const name = (e as { name?: string })?.name;
		// Abbruch, Zeitueberschreitung und "kein passender Passkey" meldet WebAuthn
		// ABSICHTLICH als denselben NotAllowedError (Privacy-Design) -- getrennte
		// Texte dafuer sind strukturell unmoeglich, siehe Spec "Known Limitations".
		if (name === 'NotAllowedError' || name === 'AbortError') {
			return 'Die Anmeldung mit Passkey wurde abgebrochen oder es stand kein passender Passkey bereit. Bitte versuche es noch einmal oder melde dich mit Passwort an.';
		}
		return 'Die Anmeldung mit Passkey hat nicht geklappt. Bitte versuche es noch einmal oder melde dich mit Passwort an.';
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
		<div class="space-y-2 text-center">
			<Wordmark size="lg" href="/" />
			<p class="text-muted-foreground text-sm">Anmelden um fortzufahren</p>
		</div>

		{#if registered}
			<div class="rounded-md border border-green-300 bg-green-50 p-3 text-sm text-green-800">
				Konto erfolgreich erstellt. Bitte melde dich an.
			</div>
		{/if}

		{#if sessionExpired}
			<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm" style="color: var(--g-bad);">
				Sitzung abgelaufen — bitte neu anmelden.
			</div>
		{/if}

		{#if form?.error}
			<div class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm" style="color: var(--g-bad);">
				{form.error === 'Rate limit exceeded' ? 'Zu viele Versuche — bitte in einigen Minuten erneut versuchen.' : form.error === 'Invalid credentials' ? 'Benutzername oder Passwort nicht korrekt.' : form.error === 'Username and password required' ? 'Bitte Benutzername und Passwort eingeben.' : form.error}
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
						Dieses Gerät unterstützt keine Passkeys — bitte melde dich mit Passwort an.
					</p>
				{:else}
					<button
						type="button"
						data-testid="login-passkey-btn"
						onclick={mitPasskeyAnmelden}
						class="inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground ring-offset-background hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
					>
						Mit Passkey anmelden
					</button>
				{/if}
			</div>
			{#if passkeyFehler}
				<div
					data-testid="login-passkey-error"
					class="rounded-md border border-destructive bg-destructive/10 p-3 text-sm"
					style="color: var(--g-bad);"
				>
					{passkeyFehler}
				</div>
			{/if}
		</div>

		<form method="POST" class="space-y-4">
			<div class="space-y-2">
				<label for="username" class="text-sm font-medium">Benutzername</label>
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
				<label for="password" class="text-sm font-medium">Passwort</label>
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
				Anmelden
			</button>
		</form>
		{#if data.googleEnabled}
			<div class="desktop:order-2 relative">
				<div class="absolute inset-0 flex items-center">
					<span class="w-full border-t border-input"></span>
				</div>
				<div class="relative flex justify-center text-xs uppercase">
					<span class="bg-background px-2 text-muted-foreground">oder</span>
				</div>
			</div>
			<a
				href="/api/auth/google/init"
				class="desktop:order-2 inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground ring-offset-background hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
			>
				Mit Google anmelden
			</a>
		{/if}

		<div class="desktop:order-3 space-y-2">
			<a href="/register" class="block text-center text-sm text-muted-foreground hover:underline">
				Noch kein Konto? Konto erstellen
			</a>
			<a href="/forgot-password" class="block text-center text-sm text-muted-foreground hover:underline">
				Passwort vergessen?
			</a>
			<a href="/magic-link" class="block text-center text-sm text-muted-foreground hover:underline">
				Mit E-Mail-Code anmelden
			</a>
		</div>
	</div>
</div>
