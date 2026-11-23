package config

// MCP-Konnektor „Gregor Wetter“ (Issue #3281, Scheibe 2): Allowlist
// GZ_MCP_USER_IDS nach dem Muster GZ_ADMIN_USER_IDS, fail-closed.

import (
	"os"
	"testing"
)

func TestLoad_LiestMCPUserIDs(t *testing.T) {
	os.Clearenv()
	t.Setenv("GZ_MCP_USER_IDS", " anna , bernd,, ")
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	ids := ParseMCPUserIDs(cfg.MCPUserIDs)
	if len(ids) != 2 {
		t.Fatalf("zwei Kennungen erwartet: %v", ids)
	}
	for _, id := range []string{"anna", "bernd"} {
		if _, ok := ids[id]; !ok {
			t.Errorf("%s fehlt: %v", id, ids)
		}
	}
	if _, ok := ids["Anna"]; ok {
		t.Errorf("Vergleich muss exakt bleiben")
	}
}

func TestLoad_MCPUserIDsOhneEnvIstNiemand(t *testing.T) {
	os.Clearenv()
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.MCPUserIDs != "" || len(ParseMCPUserIDs(cfg.MCPUserIDs)) != 0 {
		t.Errorf("ohne Env darf niemand freigegeben sein: %q", cfg.MCPUserIDs)
	}
	if cfg.AdminUserIDs != "" {
		t.Errorf("MCP-Freigabe darf keine Admin-Rechte setzen")
	}
}
