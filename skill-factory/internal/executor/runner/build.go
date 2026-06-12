// Package runner 提供 AI CLI 命令构造（claude / cbc / shell）。
package runner

import (
	"errors"
	"fmt"
	"log/slog"
	"os/exec"
	"strings"
)

// BuildCommand 根据类型构造命令列表，避免 shell 注入。
//
// claude:   claude -p --output-format json [--model <m>] [--session-id <sid>] "<prompt>"
//
//	输出为单次 JSON（含 num_turns / result / is_error 等元数据，便于 evaluator 判定真伪）
//
// cbc:      cbc -p [--model <m>] "<prompt>"   （PATH 中无 cbc 时回落到 codebuddy）
// shell:    sh -c "<prompt>"
func BuildCommand(typ, model, sessionID, prompt string, opts ...func(*buildOpts)) ([]string, error) {
	slog.Debug("runner: BuildCommand",
		slog.String("type", typ),
		slog.String("model", model),
		slog.Int("prompt_chars", len(prompt)),
	)
	o := &buildOpts{}
	for _, opt := range opts {
		opt(o)
	}
	switch typ {
	case "claude":
		cmd := []string{"claude", "-p", "--output-format", "json"}
		if model != "" {
			cmd = append(cmd, "--model", model)
		}
		if sessionID != "" {
			cmd = append(cmd, "--session-id", sessionID)
		}
		finalPrompt := prompt
		if o.actionReport {
			finalPrompt = prompt + ActionReportSuffix
		}
		cmd = append(cmd, finalPrompt)
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
		finalPrompt := prompt
		if o.actionReport {
			finalPrompt = prompt + ActionReportSuffix
		}
		cmd = append(cmd, finalPrompt)
		return cmd, nil
	case "shell":
		// sh -c "<prompt>" 形式：单元素由调用方用 sh 包装
		return []string{"sh", "-c", prompt}, nil
	default:
		return nil, fmt.Errorf("unknown command_type: %q", typ)
	}
}

func CmdString(cmd []string) string { return strings.Join(cmd, " ") }

// ActionReportSuffix 追加到 AI 任务执行 prompt 末尾，要求 AI 自报动作清单，
// 便于后续 evaluator 交叉验证"嘴上说做了 vs 实际执行了"。
// shell 类型不适用。
const ActionReportSuffix = `

## 任务完成后必须输出"动作清单"（便于自动评估）
请严格按以下 Markdown 格式输出，**必须用真实可执行命令，不允许用 ` + "`...`" + ` 占位符**：

## 动作清单
- 命令: <实际执行的命令，完整可复制>
- 退出码: <命令退出码，无命令填 N/A>
- 工具调用: <Bash / Read / Write / Edit / 其他 / 无>
- 验证步骤: <如何确认结果正确，无验证填 N/A>
`

// WithActionReport 返回一个选项，启用动作清单自报后缀（仅对 claude/cbc 生效）。
func WithActionReport() func(*buildOpts) { return func(o *buildOpts) { o.actionReport = true } }

type buildOpts struct {
	actionReport bool
}
