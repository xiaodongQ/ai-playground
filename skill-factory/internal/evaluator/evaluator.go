// Package evaluator 调 claude --print 给一次 execution 的 output 打 0-10 分 + 评语。
// 移植自 ai-task-system v2.4 的 evaluator.py（CLI 模式）。
package evaluator

import (
	"context"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"skill-factory/internal/backend"
	"skill-factory/internal/executor"
	"skill-factory/internal/executor/runner"
)

// 评分 prompt：要求 claude 基于"指令 vs AI 自报动作清单 vs 实际 stdout"三方对照打分。
const evalPromptTpl = `你是一个严格的 AI 任务结果评估员。请基于"原始指令"、"AI 自报的动作清单"和"实际 stdout"三方对照，判断任务是否真正完成。

## 任务原始指令
%s

## AI 自报的动作清单（从任务输出末尾提取）
%s

## 任务实际输出（stdout，截断前 3000 字符）
%s

## 任务错误输出（stderr，截断前 500 字符）
%s

## 任务退出码
%d

## 评估要求
1. **交叉验证**：动作清单里声明的每条命令，在 stdout 中是否找到真实执行痕迹（子串匹配）？找不到 = 嘴炮
2. **占位符检测**：动作清单里含 '...' / '<...>' / 'TODO' 等占位符的，视为未真实执行
3. **指令匹配**：动作清单里的动作是否真的回应了原始指令要求
4. 输出严格按以下 2 行格式（便于程序解析）：
   评分: <0-10 的整数>
   评语: <一句话评语，50 字以内，优先点出嘴炮/缺验证/指令不匹配>

评分参考：
  9-10 完美完成，清单真实执行，无占位符
  7-8  大体完成，小瑕疵（如未验证副作用）
  5-6  部分完成或有 1-2 处占位符/缺验证
  3-4  明显嘴炮：清单声明但 stdout 无执行证据
  0-2  完全失败，清单为空或全是占位符
`

var (
	// 兼容 3 种评分格式： "评分: 10" / "评分: 10/10" / "评分：10 分"
	scoreRe = regexp.MustCompile(`评分\s*[:：]\s*(\d+)`)
	cmtRe   = regexp.MustCompile(`评语\s*[:：]\s*(.+?)(?:\n|$)`)
)

// EvalResult 评估结果。
type EvalResult struct {
	Score    int
	Comments string
}

// Evaluate 调 claude --print 给 execution 打分。
// 注意：execution 必须有 output；model 留空用默认 claude。
// 评估员不传 WithActionReport()，避免自指（评估员不该自报清单）。
func Evaluate(ctx context.Context, exec *backend.Execution, taskPrompt string, model string) (*EvalResult, error) {
	if exec == nil {
		return nil, fmt.Errorf("execution is nil")
	}
	if model == "" {
		model = "haiku" // 默认用 haiku 快+便宜
	}
	stdout := exec.Output
	stderr := exec.Error
	report := ExtractActionReport(stdout)

	// 把动作清单渲染成可读文本注入 prompt
	reportText := "（AI 未输出动作清单）"
	if len(report.Commands) > 0 {
		var b strings.Builder
		b.WriteString("| # | 命令 | 退出码 |\n|---|------|--------|\n")
		for i, cmd := range report.Commands {
			exit := "N/A"
			if i < len(report.ExitCodes) {
				if report.ExitCodes[i] == -1 {
					exit = "N/A"
				} else {
					exit = strconv.Itoa(report.ExitCodes[i])
				}
			}
			fmt.Fprintf(&b, "| %d | `%s` | %s |\n", i+1, cmd, exit)
		}
		reportText = b.String()
	}

	prompt := strings.TrimSpace(fmt.Sprintf(evalPromptTpl,
		taskPrompt,
		reportText,
		truncate(stdout, 3000),
		truncate(stderr, 500),
		exec.ExitCode,
	))

	cmd, err := runner.BuildCommand("claude", model, "", prompt)
	if err != nil {
		return nil, fmt.Errorf("build cmd: %w", err)
	}
	ctx2, cancel := context.WithTimeout(ctx, 3*time.Minute)
	defer cancel()
	res, runErr := executor.Run(ctx2, cmd, nil)
	if runErr != nil && res == nil {
		return nil, fmt.Errorf("run: %w", runErr)
	}
	if res.ExitCode != 0 {
		return nil, fmt.Errorf("claude returned exit %d, stderr: %s", res.ExitCode, truncate(res.ErrorOut, 200))
	}
	return parseEval(res.Output), nil
}

// parseEval 解析 claude 输出,提取"评分: X"和"评语: ..."。
// 解析失败时 Score 保持 -1,Comments 保留原始 output,方便前端识别"解析失败" vs "真低分"。
func parseEval(output string) *EvalResult {
	res := &EvalResult{Score: -1, Comments: strings.TrimSpace(output)}
	if m := scoreRe.FindStringSubmatch(output); len(m) >= 2 {
		if n, err := strconv.Atoi(m[1]); err == nil && n >= 0 && n <= 10 {
			res.Score = n
		}
	}
	if m := cmtRe.FindStringSubmatch(output); len(m) >= 2 {
		res.Comments = strings.TrimSpace(m[1])
	}
	// 解析出评语但 score 失败:把完整 output 附加便于排查
	if res.Score == -1 && res.Comments != strings.TrimSpace(output) {
		res.Comments = res.Comments + "\n[原始输出]\n" + strings.TrimSpace(output)
	}
	// 注意:不再 fallback 到 0,保留 -1 表示"无法解析"
	return res
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "\n... (truncated)"
}

// RunAndSave 评估并把结果存 evaluations 表。返回 evaluation id。
func RunAndSave(ctx context.Context, evalDB *backend.EvaluationRepo, execDB *backend.ExecutionRepo, exec *backend.Execution, taskPrompt, model string) (string, error) {
	res, err := Evaluate(ctx, exec, taskPrompt, model)
	if err != nil {
		return "", err
	}
	ev := &backend.Evaluation{
		ID:             uuid.New().String(),
		TaskID:         exec.TaskID,
		ExecutionID:    exec.ID,
		EvaluatorModel: model,
		Score:          float64(res.Score),
		Comments:       res.Comments,
		CreatedAt:      time.Now(),
	}
	if err := evalDB.Create(ev); err != nil {
		return "", fmt.Errorf("save evaluation: %w", err)
	}
	return ev.ID, nil
}

// GetByExecution 查 execution 的最新 evaluation（按时间倒序取 1）。
func GetByExecution(evalDB *backend.EvaluationRepo, execID string) (*backend.Evaluation, error) {
	// 简化：返回列表的第一个
	list, err := evalDB.ListByExecution(execID)
	if err != nil {
		return nil, err
	}
	if len(list) == 0 {
		return nil, nil
	}
	return list[0], nil
}

// ActionReport 从 AI 任务输出末尾的"动作清单"段提取的结构化数据。
type ActionReport struct {
	Commands  []string // AI 声明执行的命令
	ExitCodes []int    // 对应退出码（N/A 用 -1）
}

var (
	cmdLineRe  = regexp.MustCompile(`(?m)^-?\s*命令\s*[:：]\s*(.+?)\s*$`)
	exitLineRe = regexp.MustCompile(`(?m)^-?\s*退出码\s*[:：]\s*(\d+|N/A)\s*$`)
)

// ExtractActionReport 从 stdout 提取 AI 自报的动作清单（简单 Markdown 解析）。
// 找不到"## 动作清单"段时返回空报告，不报错。
func ExtractActionReport(stdout string) *ActionReport {
	r := &ActionReport{}
	for _, m := range cmdLineRe.FindAllStringSubmatch(stdout, -1) {
		cmd := strings.TrimSpace(m[1])
		// 过滤占位符嘴炮：`...` / `<...>` / `(待填)` / `TODO` / `xxx`
		if isPlaceholder(cmd) {
			continue
		}
		r.Commands = append(r.Commands, cmd)
	}
	for _, m := range exitLineRe.FindAllStringSubmatch(stdout, -1) {
		if m[1] == "N/A" {
			r.ExitCodes = append(r.ExitCodes, -1)
		} else {
			n, _ := strconv.Atoi(m[1])
			r.ExitCodes = append(r.ExitCodes, n)
		}
	}
	return r
}

// ActionVerifyResult 验证结果。
type ActionVerifyResult struct {
	AllExecuted  bool     // 清单中所有命令在 stdout 中都出现过
	MissingCount int      // 缺失（嘴炮）命令数
	MissingCmds  []string // 缺失的命令列表
}

// VerifyActionReport 用 stdout 验证清单中的命令是否真实执行过。
// 判定标准：命令字符串在 stdout 中出现过（子串匹配，容忍换行/缩进差异）。
func VerifyActionReport(report *ActionReport, stdout string) *ActionVerifyResult {
	res := &ActionVerifyResult{AllExecuted: true}
	if report == nil || len(report.Commands) == 0 {
		return res
	}
	// 标准化：去多余空白，方便子串匹配
	norm := strings.Join(strings.Fields(stdout), " ")
	for _, cmd := range report.Commands {
		normCmd := strings.Join(strings.Fields(cmd), " ")
		if !strings.Contains(norm, normCmd) {
			res.AllExecuted = false
			res.MissingCount++
			res.MissingCmds = append(res.MissingCmds, cmd)
		}
	}
	return res
}

func isPlaceholder(s string) bool {
	placeholders := []string{"...", "…", "TODO", "xxx", "XXX", "<...>", "(待填)", "(占位)"}
	for _, p := range placeholders {
		if s == p || strings.Contains(s, p) {
			return true
		}
	}
	return false
}
