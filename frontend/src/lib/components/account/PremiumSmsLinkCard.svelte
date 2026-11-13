<script lang="ts">
	// Issue #2154 Scheibe B — Premium-SMS-Verknuepfungscode auf /account.
	// Spec: docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md
	//
	// Rein props-getriebene Darstellungskomponente: kein eigener API-Aufruf,
	// kein eigener $state ausser dem, was zur reinen Darstellung gehoert.
	// `+page.svelte` haelt den Zustand und verzweigt ueber
	// resolveGenerateClick/resolveDialogAction — diese Karte reicht nur die
	// Callback-Ergebnisse durch. Vorbild: VTBriefingChannels.svelte.
	//
	// Issue #2961 Welle 2 (ADR-0116): "Verbindung trennen". Rueckfrage,
	// Laufzustand und Fehler haelt die Karte selbst (keine weitere Logik in
	// +page.svelte); den Aufruf selbst reicht die Seite als `onDisconnect`
	// herein, damit die Karte ohne eigenen API-Import auskommt.
	import * as Card from '$lib/components/ui/card/index.js';
	import { Btn } from '$lib/components/atoms';
	import type { UserTier } from '$lib/types';
	import { t } from '$lib/i18n';
	import {
		errorMessageFrom,
		resolveDisconnectClick,
		shouldShowDisconnect
	} from '$lib/utils/premiumSmsLinkCodeHelpers';

	interface Props {
		tier: UserTier | undefined;
		exists: boolean;
		codeValue: string | null;
		busy: boolean;
		errorMsg: string | null;
		showRenewConfirm: boolean;
		onGenerateOrRenewClick: () => void;
		onDialogConfirm: () => void;
		onDialogCancel: () => void;
		/** Server-Feld `premium_sms_reply_state` (none/stale/fresh). */
		replyState?: string;
		/** Trennt die Verbindung (DELETE) und laedt die Seitendaten neu. */
		onDisconnect?: () => Promise<void>;
		/** Rueckfrage offen — nur fuer den Darstellungstest von aussen setzbar. */
		disconnectConfirm?: boolean;
	}
	let {
		exists,
		codeValue,
		busy,
		errorMsg,
		showRenewConfirm,
		onGenerateOrRenewClick,
		onDialogConfirm,
		onDialogCancel,
		replyState = undefined,
		onDisconnect = async () => {},
		disconnectConfirm = $bindable(false)
	}: Props = $props();

	let disconnectBusy = $state(false);
	let disconnectError = $state<string | null>(null);

	function onDisconnectClick() {
		if (resolveDisconnectClick(disconnectBusy) === 'confirm-dialog') disconnectConfirm = true;
	}

	async function runDisconnect() {
		disconnectConfirm = false;
		disconnectBusy = true;
		disconnectError = null;
		try {
			await onDisconnect();
		} catch (e: unknown) {
			disconnectError = errorMessageFrom(e, $t('konto.kopplung.trennen_fehlgeschlagen'));
		} finally {
			disconnectBusy = false;
		}
	}
</script>

<Card.Root data-testid="premium-sms-link-card">
	<Card.Header>
		<Card.Title>{$t('konto.kopplung.titel')}</Card.Title>
		<Card.Description>
			{$t('konto.kopplung.beschreibung')}
		</Card.Description>
	</Card.Header>
	<Card.Content class="space-y-3">
		{#if !exists}
			<Btn
				data-testid="premium-sms-link-generate"
				variant="outline"
				size="sm"
				disabled={busy}
				onclick={onGenerateOrRenewClick}
			>
				{$t('konto.kopplung.erzeugen')}
			</Btn>
		{:else}
			<Btn
				data-testid="premium-sms-link-renew"
				variant="outline"
				size="sm"
				disabled={busy}
				onclick={onGenerateOrRenewClick}
			>
				{$t('konto.kopplung.erneuern')}
			</Btn>
		{/if}

		{#if codeValue !== null}
			<div data-testid="premium-sms-link-code-value" class="text-sm">
				<code class="font-mono">{codeValue}</code>
				<p class="mt-1 text-xs text-muted-foreground">
					{$t('konto.kopplung.einmalig')}
				</p>
			</div>
		{/if}

		{#if showRenewConfirm}
			<div class="space-y-2 text-sm">
				<p>
					{$t('konto.kopplung.erneuern_frage')}
				</p>
				<div class="flex gap-2">
					<Btn
						data-testid="premium-sms-link-renew-confirm"
						variant="destructive"
						size="sm"
						onclick={onDialogConfirm}
					>
						{$t('konto.kopplung.bestaetigen')}
					</Btn>
					<Btn
						data-testid="premium-sms-link-renew-cancel"
						variant="outline"
						size="sm"
						onclick={onDialogCancel}
					>
						{$t('aktionen.abbrechen')}
					</Btn>
				</div>
			</div>
		{/if}

		{#if errorMsg !== null}
			<p data-testid="premium-sms-link-error" class="text-sm text-[var(--g-danger-fg)]">{errorMsg}</p>
		{/if}

		{#if shouldShowDisconnect(replyState)}
			<div class="space-y-2 border-t pt-3 text-sm">
				<p>{$t('konto.kopplung.verbunden')}</p>
				<Btn
					data-testid="premium-sms-disconnect"
					variant="outline"
					size="sm"
					disabled={disconnectBusy}
					onclick={onDisconnectClick}
				>
					{$t('konto.kopplung.trennen')}
				</Btn>
				{#if disconnectConfirm}
					<p>{$t('konto.kopplung.trennen_frage')}</p>
					<div class="flex gap-2">
						<Btn
							data-testid="premium-sms-disconnect-confirm"
							variant="destructive"
							size="sm"
							onclick={runDisconnect}
						>
							{$t('konto.kopplung.trennen')}
						</Btn>
						<Btn
							data-testid="premium-sms-disconnect-cancel"
							variant="outline"
							size="sm"
							onclick={() => (disconnectConfirm = false)}
						>
							{$t('aktionen.abbrechen')}
						</Btn>
					</div>
				{/if}
				{#if disconnectError !== null}
					<p data-testid="premium-sms-disconnect-error" class="text-[var(--g-danger-fg)]">{disconnectError}</p>
				{/if}
			</div>
		{/if}
	</Card.Content>
</Card.Root>
