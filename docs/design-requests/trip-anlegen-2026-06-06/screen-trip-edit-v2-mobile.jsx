/* ════════════════════════════════════════════════════════════════════════
 *  Trip bearbeiten v2 — Mobile Screen
 *  Prefix TM2_ — Babel-Scope-Disziplin.
 *  Export: ScreenTripEditV2Mobile
 *  Nutzt: PhoneFrame, TopAppBar, MTab, ScreenScroll, Sheet, MSwitch,
 *         MBtn aus mobile-shell.jsx + WM2_* aus screen-trip-edit-v2-weather.jsx
 * ════════════════════════════════════════════════════════════════════════ */

/* ─── Hilfsfunktionen ─── */
function TM2_Arrow({ dir, disabled, onClick }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      width: 36, height: 36, border: "1px solid var(--g-rule)", borderRadius: 4,
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.3 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0, flexShrink: 0,
    }}>
      <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
        {dir === "up" ? <path d="M6 2.5L10 8H2Z"/> : <path d="M6 9.5L2 4H10Z"/>}
      </svg>
    </button>
  );
}

/* ─── Wetter-Metriken Tab (Mobile) ─── */
function TM2_WetterTab({ onChannelsChange }) {
  const [state, setState] = React.useState(() => WM2_buildState("alpine"));
  const [highlight, setHl] = React.useState(null);
  const [mailOpen, setMailOpen] = React.useState(false);
  const [mailCh, setMailCh] = React.useState("email");

  const flash = (id, kind) => { setHl({ id, kind }); setTimeout(() => setHl(null), 2500); };

  const toggle = (id, wasOn) => {
    setState(s => {
      const n = { ...s, primary: [...s.primary], off: [...s.off], dirty: true };
      if (wasOn) { n.primary = n.primary.filter(x => x !== id); n.off = [...n.off, id]; }
      else { n.off = n.off.filter(x => x !== id); n.primary = [...n.primary, id]; }
      return n;
    });
    flash(id, wasOn ? "removed" : "added");
  };



  const reorder = (bucket, id, dir) => {
    setState(s => {
      const list = [...s[bucket]]; const i = list.indexOf(id); const ni = i + dir;
      if (ni < 0 || ni >= list.length) return s;
      [list[i], list[ni]] = [list[ni], list[i]];
      return { ...s, [bucket]: list, dirty: true };
    });
    flash(id, "moved");
  };

  const setMode = (id, m) => { setState(s => ({ ...s, mode: { ...s.mode, [id]: m }, dirty: true })); flash(id, "mode"); };
  const loadPreset = (pid) => { setState(WM2_buildState(pid)); flash(null, null); };

  const [channels, setChannels] = React.useState({ email: true, telegram: true, sms: false });
  const handleChannels = (c) => { setChannels(c); if (onChannelsChange) onChannelsChange(c); };

  const active = new Set(state.primary);
  const chGlyph = { email: "✉", telegram: "✈", sms: "✱" };

  return (
    <React.Fragment>
      <ScreenScroll padding={14} style={{ paddingBottom: 88 }}>

        {/* 01 Profil */}
        <div style={{ marginBottom: 16 }}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>01 — Profil</div>
          <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }}>
            {PRESETS.map(p => {
              const on = p.id === state.presetId && !state.dirty;
              return (
                <button key={p.id} onClick={() => loadPreset(p.id)} style={{
                  flexShrink: 0, padding: "8px 14px", borderRadius: "var(--g-r-pill)", cursor: "pointer",
                  border: `1px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`,
                  background: on ? "var(--g-accent-tint)" : "var(--g-card)",
                  color: on ? "var(--g-accent-deep)" : "var(--g-ink-2)", fontSize: 13, fontWeight: on ? 600 : 500,
                }}>{p.name}</button>
              );
            })}
          </div>
        </div>

        {/* 02 Grundauswahl */}
        <div style={{ marginBottom: 16 }}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
            02 — Grundauswahl <span style={{ color: "var(--g-ink-2)", textTransform: "none", fontFamily: "var(--g-font-sans)", letterSpacing: 0 }}>{active.size} aktiv</span>
          </div>
          <Card padding={14}>
            {CATEGORY_ORDER.map(cat => (
              <div key={cat} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: "var(--g-ink-3)", fontWeight: 600, marginBottom: 7 }}>{CATEGORY_LABELS[cat]}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {(METRICS_BY_CATEGORY[cat] || []).map(m => {
                    const on = active.has(m.id);
                    const hl = highlight && highlight.id === m.id;
                    return (
                      <button key={m.id} onClick={() => toggle(m.id, on)} style={{
                        padding: "7px 12px", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 500,
                        border: `1px solid ${on ? "var(--g-ink)" : "var(--g-rule)"}`,
                        background: hl ? "var(--g-accent-tint)" : on ? "var(--g-ink)" : "var(--g-card)",
                        color: on ? "var(--g-paper)" : "var(--g-ink-3)",
                        outline: hl ? "2px solid var(--g-accent)" : "none", outlineOffset: 2,
                        minHeight: 44,
                      }}>
                        {on && <span style={{ fontSize: 10, marginRight: 4, opacity: 0.7 }}>✓</span>}
                        {m.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </Card>
        </div>

        {/* 03 Reihenfolge */}
        <div style={{ marginBottom: 16 }}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>03 — Reihenfolge & Darstellung</div>
          <Card padding={0}>
            <div style={{ padding: "12px 14px 8px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>Spalten <span style={{ color: "var(--g-ink-4)", fontWeight: 400, fontSize: 12 }}>· {state.primary.length}</span></span>
              <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>links → rechts</span>
            </div>
            {state.primary.map((id, i) => {
              const m = METRIC_BY_ID[id]; if (!m) return null;
              const hl = highlight && highlight.id === id;
              const isTgCut = i === WM2_TG_LIMIT;
              return (
                <React.Fragment key={id}>
                  {isTgCut && (
                    <div style={{ padding: "5px 14px", fontSize: 10.5, color: "#8a6210", background: "rgba(192,138,26,0.07)", borderTop: "1.5px dashed var(--g-warn)", borderBottom: "1.5px dashed var(--g-warn)", fontFamily: "var(--g-font-mono)" }}>
                      ✂ ab hier Telegram-Limit
                    </div>
                  )}
                  <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px", borderBottom: "1px solid var(--g-rule-soft)", background: hl ? "var(--g-accent-tint)" : "transparent", transition: "background 0.3s", minHeight: 56 }}>
                    <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", width: 22, textAlign: "right", flexShrink: 0 }}>{i + 1}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 500 }}>{m.label}</div>
                      {m.unit && <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{m.unit}</div>}
                    </div>
                    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>

                      <TM2_Arrow dir="up"   disabled={i === 0} onClick={() => reorder("primary", id, -1)}/>
                      <TM2_Arrow dir="down" disabled={i === state.primary.length - 1} onClick={() => reorder("primary", id, +1)}/>
                    </div>
                  </div>
                </React.Fragment>
              );
            })}


          </Card>
        </div>

        {/* 04 Kanäle */}
        <div style={{ marginBottom: 16 }}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>04 — Kanäle</div>
          <Card padding={0}>
            {WM2_CHANNELS.map(ch => {
              const on = channels[ch.id];
              return (
                <div key={ch.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", borderBottom: "1px solid var(--g-rule-soft)", minHeight: 60 }}>
                  <span className="mono" style={{ fontSize: 16, width: 24, textAlign: "center", color: on ? "var(--g-ink)" : "var(--g-ink-4)" }}>{ch.glyph}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{ch.label}</div>
                    <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 1 }}>{ch.note}</div>
                  </div>
                  <MSwitch checked={on} onChange={(v) => handleChannels({ ...channels, [ch.id]: v })}/>
                </div>
              );
            })}
          </Card>
          <div style={{ marginTop: 8, fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.5, paddingLeft: 2 }}>
            Aktivierte Kanäle erscheinen auch im <strong>Briefing-Zeitplan</strong> und in den <strong>Alerts</strong>.
          </div>
        </div>

      </ScreenScroll>

      {/* Floating "Mail anzeigen"-Button */}
      <div style={{ position: "absolute", bottom: 16, left: 14, right: 14, zIndex: 20 }}>
        <button onClick={() => setMailOpen(true)} style={{
          width: "100%", padding: "14px", borderRadius: "var(--g-r-pill)",
          background: "var(--g-ink)", color: "var(--g-paper)", border: "none",
          fontSize: 14, fontWeight: 600, cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          boxShadow: "0 4px 20px rgba(26,26,24,0.25)",
        }}>
          <span>So kommt es an</span>
          <span className="mono" style={{ fontSize: 11, opacity: 0.7, background: "rgba(255,255,255,0.15)", padding: "2px 8px", borderRadius: 999 }}>{state.primary.length} Metriken</span>
        </button>
      </div>

      {/* Mail-Vorschau als Bottom-Sheet */}
      <Sheet open={mailOpen} onClose={() => setMailOpen(false)} title="So kommt es an">
        <div style={{ padding: "4px 16px 24px" }}>
          <WM2_ChannelTabs value={mailCh} onChange={setMailCh} primary={state.primary}/>
          <div style={{ marginTop: 12 }}>
            <WM2_DiffBanner highlight={highlight}/>
            {mailCh === "email"    && <WM2_EmailTable    primary={state.primary} mode={state.mode} highlight={highlight} compact/>}
            {mailCh === "telegram" && <WM2_TelegramBubble primary={state.primary} mode={state.mode} highlight={highlight}/>}
            {mailCh === "sms"      && <WM2_SMSLine        primary={state.primary}/>}
          </div>
        </div>
      </Sheet>
    </React.Fragment>
  );
}

/* ─── Zeitplan Tab (Mobile) ─── */
function TM2_ZeitplanTab({ channels }) {
  const active = Object.entries(channels).filter(([,v]) => v).map(([k]) => k);
  const chLabel = { email: "Email", telegram: "Telegram", sms: "SMS" };
  const [cards, setCards] = React.useState([
    { id: "morning", title: "Morgen-Briefing", time: "06:00",       on: true,  ch: { email: true, telegram: true, sms: false } },
    { id: "evening", title: "Abend-Briefing",  time: "18:00",       on: true,  ch: { email: true, telegram: false, sms: false } },
    { id: "alert",   title: "Alert-Trigger",   time: "bei Schwellwert", on: true, accent: true, ch: { email: false, telegram: true, sms: false } },
    { id: "trend",   title: "Mehrtages-Trend", time: "So 18:00",    on: false, ch: { email: true, telegram: false, sms: false } },
  ]);
  if (active.length === 0) {
    return (
      <ScreenScroll padding={16}>
        <div style={{ padding: "18px 16px", background: "rgba(192,138,26,0.07)", border: "1px solid var(--g-warn)", borderRadius: "var(--g-r-2)", fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
          <strong style={{ color: "#8a6210" }}>Kein Kanal aktiv.</strong> Aktiviere zuerst einen Kanal in <strong>Abschnitt 04 — Kanäle</strong>.
        </div>
      </ScreenScroll>
    );
  }
  return (
    <ScreenScroll padding={14}>
      <div style={{ padding: "10px 12px", background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", fontSize: 12.5, color: "var(--g-ink-2)", marginBottom: 14 }}>
        Aktive Kanäle aus Wetter-Metriken:{active.map(k => <strong key={k} style={{ marginLeft: 6, color: "var(--g-ink)" }}>{chLabel[k]}</strong>)}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {cards.map(c => (
          <Card key={c.id} padding={14} style={{ borderLeft: c.accent && c.on ? "3px solid var(--g-accent)" : undefined }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{c.title}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 1 }}>{c.time}</div>
              </div>
              <MSwitch checked={c.on} onChange={() => setCards(cs => cs.map(x => x.id === c.id ? { ...x, on: !x.on } : x))}/>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {active.map(k => (
                <button key={k} onClick={() => setCards(cs => cs.map(x => x.id === c.id ? { ...x, ch: { ...x.ch, [k]: !x.ch[k] } } : x))} style={{
                  padding: "6px 12px", fontSize: 13, fontWeight: 500, borderRadius: 4, cursor: "pointer", minHeight: 36,
                  background: c.ch[k] ? "var(--g-ink)" : "var(--g-paper-deep)",
                  color: c.ch[k] ? "var(--g-paper)" : "var(--g-ink-4)",
                  border: `1px solid ${c.ch[k] ? "var(--g-ink)" : "var(--g-rule)"}`,
                }}>{chLabel[k]}</button>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </ScreenScroll>
  );
}

/* ─── Alerts Tab (Mobile) ─── */
function TM2_AlertsTab({ defaultChannels }) {
  const active = Object.entries(defaultChannels).filter(([,v]) => v).map(([k]) => k);
  const chLabel = { email: "Email", telegram: "Telegram", sms: "SMS" };
  const [alerts, setAlerts] = React.useState([
    { id: 1, label: "Sturm-Böen", cond: ">= 60 km/h", on: true, ch: { ...defaultChannels } },
    { id: 2, label: "Starkregen-Wahrscheinlichkeit", cond: ">= 80 %", on: true, ch: { ...defaultChannels } },
  ]);
  return (
    <ScreenScroll padding={14}>
      <div style={{ padding: "10px 12px", background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", fontSize: 12.5, color: "var(--g-ink-2)", marginBottom: 14 }}>
        Kanäle sind aus <strong>Wetter-Metriken</strong> vorbelegt — pro Alert änderbar.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {alerts.map(a => (
          <Card key={a.id} padding={14} style={{ borderLeft: a.on ? "3px solid var(--g-accent)" : undefined }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{a.label}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 1 }}>{a.cond}</div>
              </div>
              <MSwitch checked={a.on} onChange={() => setAlerts(as => as.map(x => x.id === a.id ? { ...x, on: !x.on } : x))}/>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {active.map(k => (
                <button key={k} onClick={() => setAlerts(as => as.map(x => x.id === a.id ? { ...x, ch: { ...x.ch, [k]: !x.ch[k] } } : x))} style={{
                  padding: "6px 12px", fontSize: 13, fontWeight: 500, borderRadius: 4, cursor: "pointer", minHeight: 36,
                  background: a.ch[k] ? "var(--g-ink)" : "var(--g-paper-deep)",
                  color: a.ch[k] ? "var(--g-paper)" : "var(--g-ink-4)",
                  border: `1px solid ${a.ch[k] ? "var(--g-ink)" : "var(--g-rule)"}`,
                }}>{chLabel[k]}</button>
              ))}
            </div>
          </Card>
        ))}
        <button style={{ padding: "12px", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-2)", background: "transparent", color: "var(--g-ink-3)", fontSize: 13, cursor: "pointer", minHeight: 44 }}>
          + Neuen Alert hinzufügen
        </button>
      </div>
    </ScreenScroll>
  );
}

/* ════════════════════ MAIN: ScreenTripEditV2Mobile ════════════════════ */
function ScreenTripEditV2Mobile({ initialTab = "metriken" } = {}) {
  const [tab, setTab] = React.useState(initialTab);
  const [channels, setChannels] = React.useState({ email: true, telegram: true, sms: false });

  const TABS = [
    { id: "uebersicht", label: "Übersicht" },
    { id: "etappen",    label: "Etappen", badge: "5" },
    { id: "metriken",   label: "Wetter" },
    { id: "zeitplan",   label: "Zeitplan" },
    { id: "alerts",     label: "Alerts", badge: "2", accent: true },
  ];

  return (
    <PhoneFrame height={812} time="08:14">
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Wetter-Metriken"
          eyebrow="KHW 403 · bearbeiten"
          leftIcon="back"
          right={<button style={{ height: 44, padding: "0 14px", border: "none", background: "transparent", color: "var(--g-accent)", fontWeight: 600, fontSize: 14, cursor: "pointer" }}>Speichern</button>}
        />
        <MTab items={TABS} active={tab} onChange={setTab}/>
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          {tab === "uebersicht" && (
            <ScreenScroll padding={16}>
              <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>KHW 403</div>
              <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginBottom: 16 }}>Karnischer Höhenweg · 5 Etappen · 182 km</div>
              {[["Wetter-Metriken", () => setTab("metriken")], ["Briefing-Zeitplan", () => setTab("zeitplan")], ["Alerts", () => setTab("alerts")]].map(([lbl, fn]) => (
                <div key={lbl} onClick={fn} style={{ display: "flex", justifyContent: "space-between", padding: "14px 0", borderBottom: "1px solid var(--g-rule-soft)", cursor: "pointer", minHeight: 44, alignItems: "center" }}>
                  <span style={{ fontSize: 15, fontWeight: 500 }}>{lbl}</span>
                  <span style={{ color: "var(--g-ink-4)" }}>›</span>
                </div>
              ))}
            </ScreenScroll>
          )}
          {tab === "etappen" && (
            <ScreenScroll padding={16}>
              <div style={{ padding: "20px", background: "var(--g-card-alt)", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-2)", color: "var(--g-ink-3)", fontSize: 13, textAlign: "center" }}>
                Wegpunkt-Editor: bereits als eigene Komponente gebaut (Issue #503)
              </div>
            </ScreenScroll>
          )}
          {tab === "metriken" && <TM2_WetterTab onChannelsChange={setChannels}/>}
          {tab === "zeitplan" && <TM2_ZeitplanTab channels={channels}/>}
          {tab === "alerts"   && <TM2_AlertsTab defaultChannels={channels}/>}
        </div>
      </div>
    </PhoneFrame>
  );
}

window.ScreenTripEditV2Mobile = ScreenTripEditV2Mobile;
