<script lang="ts">
	// Issue #301 Lieferung A — Dialog zum Anlegen einer neuen Gruppe.
	//
	// Spec: docs/specs/modules/issue_301_sidebar_groups.md §6
	// Pattern: Dialog.Root wie shared/weather-metrics-tab/SavePresetDialog.svelte
	// (Issue #1311: von trip-detail/ verschoben).
	//
	// Sendet POST /api/groups; bei doppeltem Namen (gleiche kebab-ID -> 409)
	// zeigt der Dialog die Backend-Fehlermeldung in data-testid="create-group-error".

	import { api } from '$lib/api.js';
	import type { Group, ActivityProfile } from '$lib/types.js';
	import { ACTIVITY_PROFILE_OPTIONS } from '$lib/types.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Btn } from '$lib/components/atoms';
	import { Select } from '$lib/components/ui/select';
	// Issue #2659 (i18n F10): Texte aus dem Katalog; ohne Server-Text haelt `error` nur
	// das Flag '' und die Meldung entsteht beim Rendern in der aktuellen Sprache.
	import { t, type MessageKey } from '$lib/i18n';

	interface Props {
		open: boolean;
		onCreate: (group: Group) => void;
	}

	let { open = $bindable(false), onCreate }: Props = $props();

	let name = $state('');
	let profile = $state<ActivityProfile | ''>('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	let canSubmit = $derived(name.trim().length > 0 && !saving);

	function reset() {
		name = '';
		profile = '';
		saving = false;
		error = null;
	}

	function close() {
		open = false;
		reset();
	}

	async function submit() {
		if (!canSubmit) return;
		saving = true;
		error = null;
		try {
			const group = await api.post<Group>('/api/groups', {
				name: name.trim(),
				default_profile: profile || undefined,
			});
			onCreate(group);
			open = false;
			reset();
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			error = body?.detail ?? body?.error ?? '';
		} finally {
			saving = false;
		}
	}
</script>

<Dialog.Root bind:open onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content data-testid="create-group-dialog" class="max-w-sm">
		<Dialog.Header>
			<Dialog.Title>{$t('vergleich.gruppe.neu')}</Dialog.Title>
		</Dialog.Header>

		<div class="dialog-body">
			<label class="field">
				<span class="field-label">{$t('listen.spalte.name')} <span class="required">*</span></span>
				<input
					data-testid="create-group-name"
					type="text"
					bind:value={name}
					maxlength="80"
					placeholder={$t('vergleich.gruppe.beispiel')}
					required
				/>
			</label>

			<label class="field">
				<span class="field-label">{$t('vergleich.gruppe.standard_profil')}</span>
				<Select data-testid="create-group-profile" bind:value={profile} class="w-full">
					<option value="">{$t('vergleich.gruppe.kein_profil')}</option>
					{#each ACTIVITY_PROFILE_OPTIONS as opt}
						<option value={opt.value}>{$t(`bausteine.profil.${opt.value}` as MessageKey)}</option>
					{/each}
				</Select>
			</label>

			{#if error !== null}
				<p class="error-msg" data-testid="create-group-error">{error || $t('vergleich.gruppe.fehler')}</p>
			{/if}
		</div>

		<Dialog.Footer>
			<Btn variant="outline" onclick={close} disabled={saving}>{$t('aktionen.abbrechen')}</Btn>
			<Btn
				variant="primary"
				data-testid="create-group-submit"
				disabled={!canSubmit}
				onclick={submit}
			>
				{saving ? $t('vergleich.gruppe.legt_an') : $t('konto.passkey.anlegen')}
			</Btn>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<style>
	.dialog-body {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
		padding: var(--g-s-2) 0;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1);
	}
	.field-label {
		font-size: var(--g-text-xs);
		font-weight: 500;
	}
	.required {
		color: var(--g-accent-deep);
	}
	.field input[type='text'] {
		padding: var(--g-s-2) var(--g-s-2);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-xs);
		font: inherit;
		font-size: var(--g-text-sm);
		background: var(--g-paper);
		color: var(--g-ink);
	}
	.error-msg {
		font-size: var(--g-text-xs);
		color: var(--g-danger);
	}
	@media (max-width: 767px) {
		.field input[type='text'] {
			/* iOS zoom guard (#272): exakt 16px */
			font-size: 16px;
		}
	}
</style>
