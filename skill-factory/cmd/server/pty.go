//go:build !windows

package main

import (
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"github.com/creack/pty"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for local development
	},
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
}

type PTYSession struct {
	ptmx *os.File
	winsize *pty.Winsize
}

var sessions = make(map[*websocket.Conn]*PTYSession)
var sessionMu sync.Mutex

func handlePty(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("websocket upgrade error: %v", err)
		return
	}
	defer conn.Close()

	// Get context directory path
	ctxDir := getContextDir()

	// Determine shell and initial command
	shell := os.Getenv("SHELL")
	if shell == "" {
		shell = "/bin/bash"
	}

	// Build Claude Code command with context files
	args := []string{"-c"}
	cmdStr := os.Getenv("CLAUDE_CMD")
	if cmdStr == "" {
		cmdStr = determineClaudeCmd(ctxDir)
	}
	args = append(args, cmdStr)

	cmd := exec.Command(shell, args...)
	cmd.Env = os.Environ()
	cmd.Env = append(cmd.Env, "TERM=xterm-256color")
	cmd.Env = append(cmd.Env, "CLAUDE_CODE_PROMPT_PATH="+ctxDir)

	ptmx, err := pty.Start(cmd)
	if err != nil {
		log.Printf("pty start error: %v", err)
		conn.WriteMessage(websocket.TextMessage, []byte("Failed to start terminal\r\n"))
		return
	}
	defer ptmx.Close()
	defer cmd.Process.Kill()

	sessionMu.Lock()
	sessions[conn] = &PTYSession{ptmx: ptmx}
	sessionMu.Unlock()

	// Handle resize
	go func() {
		for {
			_, msg, err := conn.ReadMessage()
			if err != nil {
				break
			}
			// Parse resize messages: "resize,w,h"
			if strings.HasPrefix(string(msg), "resize,") {
				parts := strings.Split(string(msg), ",")
				if len(parts) == 3 {
					var ws pty.Winsize
					ws.Cols = uint16(parseInt(parts[1], 80))
					ws.Rows = uint16(parseInt(parts[2], 24))
					pty.Setsize(ptmx, &ws)
				}
			}
		}
	}()

	// Copy PTY output to WebSocket
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		buf := make([]byte, 1024)
		for {
			n, err := ptmx.Read(buf)
			if err != nil {
				break
			}
			if err := conn.WriteMessage(websocket.BinaryMessage, buf[:n]); err != nil {
				break
			}
		}
	}()

	// Copy WebSocket input to PTY
	io.Copy(ptmx, &wsReader{conn: conn})

	sessionMu.Lock()
	delete(sessions, conn)
	sessionMu.Unlock()
	wg.Wait()
}

type wsReader struct {
	conn *websocket.Conn
}

func (r *wsReader) Read(p []byte) (int, error) {
	msgType, data, err := r.conn.ReadMessage()
	if err != nil {
		return 0, err
	}
	if msgType == websocket.TextMessage || msgType == websocket.BinaryMessage {
		n := copy(p, data)
		return n, nil
	}
	return 0, nil
}

func getContextDir() string {
	// Look for .skill-factory/context in the executable's directory
	exe, err := os.Executable()
	if err != nil {
		return ""
	}
	ctxDir := filepath.Join(filepath.Dir(exe), ".skill-factory", "context")
	if _, err := os.Stat(ctxDir); err == nil {
		return ctxDir
	}
	// Fallback: relative to current working directory
	cwd, err := os.Getwd()
	if err != nil {
		return ""
	}
	ctxDir = filepath.Join(cwd, ".skill-factory", "context")
	if _, err := os.Stat(ctxDir); err == nil {
		return ctxDir
	}
	return ""
}

func determineClaudeCmd(ctxDir string) string {
	if ctxDir == "" {
		return "claude"
	}

	// Build a prompt that includes the context files
	promptFiles := ""
	systemFiles := []string{"system-prompt.md", "task-schema.md", "experience-schema.md"}
	for _, f := range systemFiles {
		path := filepath.Join(ctxDir, f)
		if data, err := os.ReadFile(path); err == nil {
			promptFiles += string(data) + "\n\n"
		}
	}

	if promptFiles != "" {
		// Write combined prompt to a temp file for CLAUDE_CODE to read
		tmpFile := "/tmp/claude-code-skill-factory-prompt.txt"
		os.WriteFile(tmpFile, []byte(promptFiles), 0644)
		return "claude --prompt-file " + tmpFile
	}

	return "claude"
}

// parseInt is in main.go