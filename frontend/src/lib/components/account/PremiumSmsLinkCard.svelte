<script lang="ts">
	// Issue #2154 Scheibe B — Premium-SMS-Verknuepfungscode auf /account.
	// Spec: docs/specs/modules/fix_2154_s2_premium_sms_link_code_ui.md
	//
	// Rein props-getriebene Darstellungskomponente: kein eigener API-Aufruf,
	// kein eigener $state ausser dem, was zur reinen Darstellung gehoert.
	// `+page.svelte` haelt den Zustand und verzweigt ueber
	// resolveGenerateClick/resolveDialogAction — diese Karte reicht nur die
	// Callback-Ergebnisse durch. Vorbild: VTBriefingChannels.svelte.
	import * as Card from '$lib/components/ui/card/index.js';
	import { Btn } from '$lib/components/atoms';
	import type { UserTier } from '$lib/types';

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
	}
	let {
		exists,
		codeValue,
		busy,
		errorMsg,
		showRenewConfirm,
		onGenerateOrRenewClick,
		onDialogConfirm,
		onDialogCancel
	}: Props = $props();
</script>

<Card.Root data-testid="premium-sms-link-card">
	<Card.Header>
		<Card.Title>Premium-SMS-Verknüpfungscode</Card.Title>
		<Card.Description>
			Verbindet dein Garmin-inReach-Gerät sicher mit deinem Konto.
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
				Code erzeugen
			</Btn>
		{:else}
			<Btn
				data-testid="premium-sms-link-renew"
				variant="outline"
				size="sm"
				disabled={busy}
				onclick={onGenerateOrRenewClick}
			>
				Code erneuern
			</Btn>
		{/if}

		{#if codeValue !== null}
			<div data-testid="premium-sms-link-code-value" class="text-sm">
				<code class="font-mono">{codeValue}</code>
				<p class="mt-1 text-xs text-muted-foreground">
					Dieser Code wird nicht erneut angezeigt — notiere ihn jetzt.
				</p>
			</div>
		{/if}

		{#if showRenewConfirm}
			<div class="space-y-2 text-sm">
				<p>
					Ein bestehender Verknüpfungscode wird beim Erneuern ungültig. Fortfahren?
				</p>
				<div class="flex gap-2">
					<Btn
						data-testid="premium-sms-link-renew-confirm"
						variant="destructive"
						size="sm"
						onclick={onDialogConfirm}
					>
						Bestätigen
					</Btn>
					<Btn
						data-testid="premium-sms-link-renew-cancel"
						variant="outline"
						size="sm"
						onclick={onDialogCancel}
					>
						Abbrechen
					</Btn>
				</div>
			</div>
		{/if}

		{#if errorMsg !== null}
			<p data-testid="premium-sms-link-error" class="text-sm text-red-600">{errorMsg}</p>
		{/if}
	</Card.Content>
</Card.Root>
