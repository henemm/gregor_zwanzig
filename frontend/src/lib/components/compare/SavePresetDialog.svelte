<script lang="ts">
	// Issue #459 — Dialog zum Speichern eines Compare-Presets.
	//
	// Spec: docs/specs/modules/issue_459_auto_briefings_sidepanel.md (§5)
	// Pattern: CreateGroupDialog.svelte (Dialog.Root + bind:open + api.post).
	//
	// Sendet POST /api/compare/presets; bei Fehler wird die Backend-Meldung in
	// data-testid="save-preset-error" angezeigt. Dialog schließt sich bei Erfolg.

	import { api } from '$lib/api.js';
	import type { ComparePreset } from '$lib/types.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Btn } from '$lib/components/ui/btn/index.js';
	import { Select } from '$lib/components/ui/select';

	interface Props {
		open: boolean;
	}

	let { open = $bindable(false) }: Props = $props();

	let name = $state('');
	let schedule: 'daily' | 'weekly' | 'manual' = $state('daily');
	let hour_from = $state(9);
	let hour_to = $state(16);
	let empfaenger = $state('');
	let saving = $state(false);
	let error: string | null = $state(null);

	let canSubmit = $derived(name.trim().length > 0 && !saving);

	function reset() {
		name = '';
		schedule = 'daily';
		hour_from = 9;
		hour_to = 16;
		empfaenger = '';
		saving = false;
		error = null;
	}

	function close() {
		open = false;
		reset();
	}

	async function handleSave() {
		if (!canSubmit) return;
		saving = true;
		error = null;
		try {
			await api.post<ComparePreset>('/api/compare/presets', {
				name: name.trim(),
				schedule,
				hour_from: schedule === 'daily' ? hour_from : 0,
				hour_to: schedule === 'daily' ? hour_to : 0,
				empfaenger: empfaenger.split(',').map((e) => e.trim()).filter(Boolean)
			});
			open = false;
			reset();
		} catch (e: unknown) {
			const body = e as { detail?: string; error?: string };
			error = body?.detail ?? body?.error ?? 'Speichern fehlgeschlagen';
		} finally {
			saving = false;
		}
	}
</script>

<Dialog.Root bind:open onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content data-testid="save-preset-dialog" class="max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Vergleich als Auto-Briefing speichern</Dialog.Title>
		</Dialog.Header>

		<div class="dialog-body">
			<label class="field">
				<span class="field-label">Name <span class="required">*</span></span>
				<input
					data-testid="save-preset-name"
					type="text"
					bind:value={name}
					maxlength="80"
					placeholder="z.B. Alpen-Vergleich"
					required
				/>
			</label>

			<label class="field">
				<span class="field-label">Zeitplan</span>
				<Select data-testid="save-preset-schedule" bind:value={schedule} class="w-full">
					<option value="daily">Täglich</option>
					<option value="weekly">Wöchentlich</option>
					<option value="manual">Manuell</option>
				</Select>
			</label>

			{#if schedule === 'daily'}
				<div class="field-row">
					<label class="field">
						<span class="field-label">Von (Uhr)</span>
						<input
							data-testid="save-preset-hour-from"
							type="number"
							min="0"
							max="23"
							bind:value={hour_from}
						/>
					</label>
					<label class="field">
						<span class="field-label">Bis (Uhr)</span>
						<input
							data-testid="save-preset-hour-to"
							type="number"
							min="0"
							max="23"
							bind:value={hour_to}
						/>
					</label>
				</div>
			{/if}

			<label class="field">
				<span class="field-label">Empfänger (kommasepariert)</span>
				<textarea
					data-testid="save-preset-empfaenger"
					bind:value={empfaenger}
					placeholder="mail@example.com, andere@example.com"
					rows="2"
				></textarea>
			</label>

			{#if error}
				<p class="error-msg" data-testid="save-preset-error">{error}</p>
			{/if}
		</div>

		<Dialog.Footer>
			<Btn variant="outline" onclick={close} disabled={saving}>Abbrechen</Btn>
			<Btn
				variant="primary"
				data-testid="save-preset-submit"
				disabled={!canSubmit}
				onclick={handleSave}
			>
				{saving ? 'Speichern…' : 'Speichern'}
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
	.field-row {
		display: flex;
		gap: var(--g-s-3);
	}
	.field-row .field {
		flex: 1;
	}
	.field-label {
		font-size: var(--g-text-xs);
		font-weight: 500;
	}
	.required {
		color: var(--g-accent-deep);
	}
	.field input[type='text'],
	.field input[type='number'],
	.field textarea {
		padding: var(--g-s-2) var(--g-s-2);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-xs);
		font: inherit;
		font-size: var(--g-text-sm);
		background: var(--g-paper);
		color: var(--g-ink);
	}
	.field textarea {
		resize: vertical;
		min-height: var(--g-s-10);
	}
	.error-msg {
		font-size: var(--g-text-xs);
		color: var(--g-danger);
	}
	@media (max-width: 767px) {
		.field input[type='text'],
		.field input[type='number'],
		.field textarea {
			/* iOS zoom guard (#272): exakt 16px */
			font-size: 16px;
		}
	}
</style>
