// Package executor 提供子进程流式执行 + 4 种人工确认信号检测。
package executor

import (
	"context"
	"errors"
	"os/exec"
	"strings"
	"sync"
)

// Result 一次执行的完整结果。
type Result struct {
	Output   string
	ErrorOut string
	CmdStr   string
	ExitCode int
	Err      error // 启动/等待过程中的错误（如 ctx 超时）
}

// Run 启动子进程并流式回调 stdout/stderr。ctx 取消会 kill 子进程。
// onChunk 收到的每段以 "\n" 结尾的文本片段（来自 stdout 或 stderr，前者无前缀，后者带 "[err] "）。
func Run(ctx context.Context, cmd []string, onChunk func(string)) (*Result, error) {
	if len(cmd) == 0 {
		return nil, errors.New("empty command")
	}
	c := exec.CommandContext(ctx, cmd[0], cmd[1:]...)
	stdout, err := c.StdoutPipe()
	if err != nil {
		return nil, err
	}
	stderr, err := c.StderrPipe()
	if err != nil {
		return nil, err
	}
	if err := c.Start(); err != nil {
		return nil, err
	}

	var out, errBuf strings.Builder
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		buf := make([]byte, 4096)
		for {
			n, e := stdout.Read(buf)
			if n > 0 {
				s := string(buf[:n])
				out.WriteString(s)
				if onChunk != nil {
					onChunk(s)
				}
			}
			if e != nil {
				return
			}
		}
	}()
	go func() {
		defer wg.Done()
		buf := make([]byte, 4096)
		for {
			n, e := stderr.Read(buf)
			if n > 0 {
				s := string(buf[:n])
				errBuf.WriteString(s)
				if onChunk != nil {
					onChunk("[err] " + s)
				}
			}
			if e != nil {
				return
			}
		}
	}()

	waitErr := c.Wait()
	wg.Wait()

	exit := -1
	if c.ProcessState != nil {
		exit = c.ProcessState.ExitCode()
	}
	res := &Result{
		Output:   out.String(),
		ErrorOut: errBuf.String(),
		CmdStr:   strings.Join(cmd, " "),
		ExitCode: exit,
	}
	if waitErr != nil {
		// ctx 超时返回的 error 带 "signal: killed"
		res.Err = waitErr
	}
	return res, nil
}
