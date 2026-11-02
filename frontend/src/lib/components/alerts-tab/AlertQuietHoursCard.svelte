<script lang="ts">
    // Issue #586 — Eyebrow statt h4, JSX-konformer Hint-Text, Mono-Inputs.
    import { Checkbox } from '$lib/components/ui/checkbox';
    import { Eyebrow } from '$lib/components/atoms';
    import { t } from '$lib/i18n';

    // Issue #1726: `zonen_bezug` benennt, WOVON die Ortszeit abhängt — beim
    // Trip „der Trip", beim Ortsvergleich „des ersten Orts". Reiner Text: welche
    // IANA-Zone gilt, entscheidet das Backend (`anchor_tz`/`first_resolvable_tz`).
    // Issue #2656 (F7): ohne Uebergabe der Trip-Bezug aus dem Katalog (kein
    // Sprach-Standardwert in $props()).
    let {
        quiet_from = $bindable<string | undefined>(undefined),
        quiet_to   = $bindable<string | undefined>(undefined),
        zonen_bezug,
    }: { quiet_from?: string; quiet_to?: string; zonen_bezug?: string } = $props();

    let enabled = $state(quiet_from !== undefined && quiet_to !== undefined);

    function toggleEnabled() {
        enabled = !enabled;
        if (!enabled) {
            quiet_from = undefined;
            quiet_to = undefined;
        }
    }

    let midnightWrap = $derived(
        enabled && !!quiet_from && !!quiet_to && quiet_from > quiet_to
    );
</script>

<div class="quiet-card" data-testid="alert-quiet-hours-card">
    <div class="header-row">
        <Eyebrow>{$t('alarme.stille_stunden.titel')}</Eyebrow>
        <Checkbox
            checked={enabled}
            onchange={toggleEnabled}
            data-testid="alert-quiet-hours-toggle"
        >{$t('alarme.stille_stunden.aktiv')}</Checkbox>
    </div>
    <p class="hint">{$t('alarme.stille_stunden.hinweis', { zonen_bezug: zonen_bezug ?? $t('alarme.stille_stunden.bezug_route') })}</p>
    {#if enabled}
        <div class="time-row">
            <label>
                {$t('alarme.stille_stunden.von')}
                <input
                    type="time"
                    bind:value={quiet_from}
                    data-testid="alert-quiet-from"
                    class="time-input"
                />
            </label>
            <label>
                {$t('alarme.stille_stunden.bis')}
                <input
                    type="time"
                    bind:value={quiet_to}
                    data-testid="alert-quiet-to"
                    class="time-input"
                />
            </label>
        </div>
        {#if midnightWrap}
            <p class="midnight-hint" data-testid="alert-quiet-midnight-hint">
                {$t('alarme.stille_stunden.mitternacht', { von: quiet_from ?? '', bis: quiet_to ?? '' })}
            </p>
        {/if}
    {/if}
</div>

<style>
    .quiet-card {
        padding: var(--g-s-4);
        border: 1px solid var(--g-ink-faint);
        border-radius: var(--g-radius-md);
        background: var(--g-surface-1, #fff);
    }
    .header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: var(--g-s-2);
    }
    .hint { margin: 0 0 var(--g-s-2); font-size: var(--g-text-xs); color: var(--g-ink-muted); }
    .time-row { display: flex; gap: var(--g-s-4); flex-wrap: wrap; }
    .time-row label { display: flex; align-items: center; gap: var(--g-s-2); font-size: var(--g-text-sm); }
    .time-input {
        width: 80px;
        padding: var(--g-s-2) var(--g-s-3);
        border: 1px solid var(--g-rule);
        border-radius: var(--g-radius-sm);
        font-size: var(--g-text-md);
        font-family: var(--g-font-mono);
    }
    .midnight-hint { margin: var(--g-s-2) 0 0; font-size: var(--g-text-xs); color: var(--g-ink-muted); font-style: italic; }

    @media (max-width: 899px) {
        .time-input {
            min-height: 44px;
            font-size: 16px; /* iOS-Zoom-Schutz: <16px löst Auto-Zoom aus */
            width: 100%;
        }
    }
</style>
