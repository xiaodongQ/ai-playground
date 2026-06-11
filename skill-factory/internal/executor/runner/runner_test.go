package runner

import "testing"

func TestBuildCommandClaude(t *testing.T) {
	got, err := BuildCommand("claude", "sonnet", "sess-1", "解析 slowlog")
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"claude", "--print", "--verbose", "--model", "sonnet", "--session-id", "sess-1", "解析 slowlog"}
	if len(got) != len(want) {
		t.Fatalf("len = %d, want %d: %v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

func TestBuildCommandCbc(t *testing.T) {
	got, err := BuildCommand("cbc", "opus", "", "写一个 hello world")
	if err != nil {
		// PATH 中可能没有 cbc/codebuddy，跳过
		t.Skip("cbc/codebuddy not in PATH:", err)
	}
	// 至少验证第一项是 cbc 或 codebuddy
	if got[0] != "cbc" && got[0] != "codebuddy" {
		t.Errorf("got[0] = %q, want cbc or codebuddy", got[0])
	}
	if got[1] != "-p" {
		t.Errorf("got[1] = %q, want -p", got[1])
	}
}

func TestBuildCommandShell(t *testing.T) {
	got, err := BuildCommand("shell", "", "", "echo hi")
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"sh", "-c", "echo hi"}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

func TestBuildCommandUnknown(t *testing.T) {
	if _, err := BuildCommand("nonsense", "", "", "x"); err == nil {
		t.Error("expected error for unknown type")
	}
}
