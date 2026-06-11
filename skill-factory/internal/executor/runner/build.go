// Package runner 提供 AI CLI 命令构造（claude / cbc / shell）。
package runner

import (
	"errors"
	"fmt"
	"os/exec"
	"strings"
)

// BuildCommand 根据类型构造命令列表，避免 shell 注入。
//
// claude:   claude --print --verbose [--allowedTools ...] [--model <m>] [--session-id <sid>] "<prompt>"
// cbc:      cbc -p [--model <m>] "<prompt>"   （PATH 中无 cbc 时回落到 codebuddy）
// shell:    sh -c "<prompt>"
func BuildCommand(typ, model, sessionID, prompt string) ([]string, error) {
	switch typ {
	case "claude":
		cmd := []string{"claude", "--print", "--verbose"}
		if model != "" {
			cmd = append(cmd, "--model", model)
		}
		if sessionID != "" {
			cmd = append(cmd, "--session-id", sessionID)
		}
		cmd = append(cmd, prompt)
		return cmd, nil
	case "cbc", "codebuddy":
		bin := "cbc"
		if _, err := exec.LookPath("cbc"); err != nil {
			if _, err2 := exec.LookPath("codebuddy"); err2 == nil {
				bin = "codebuddy"
			} else {
				return nil, errors.New("neither cbc nor codebuddy found in PATH")
			}
		}
		cmd := []string{bin, "-p"}
		if model != "" {
			cmd = append(cmd, "--model", model)
		}
		cmd = append(cmd, prompt)
		return cmd, nil
	case "shell":
		// sh -c "<prompt>" 形式：单元素由调用方用 sh 包装
		return []string{"sh", "-c", prompt}, nil
	default:
		return nil, fmt.Errorf("unknown command_type: %q", typ)
	}
}

func CmdString(cmd []string) string { return strings.Join(cmd, " ") }
