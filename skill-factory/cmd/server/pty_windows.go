//go:build windows

package main

import (
	"log"
	"net/http"
)

// handlePty 在 Windows 上不可用（creack/pty 不支持 Windows ConPTY）。
// 返回 503 + 友好提示，UI 探测 navigator.userAgentData 隐藏 "AI Chat" Tab。
func handlePty(w http.ResponseWriter, r *http.Request) {
	log.Printf("PTY requested on Windows, returning 503")
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusServiceUnavailable)
	w.Write([]byte(`{"error":"PTY not supported on Windows. Use the web UI for task execution instead."}`))
}
