package main

import (
	"bufio"
	"encoding/json"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

func main() {
	// Allow port override via environment variable for testing
	port := getEnv("PROXY_PORT", ":8080")
	startTime := time.Now().Format(time.RFC3339)
	log.Printf("[%s] Starting proxy server on port %s", startTime, port)

	// Create custom server that intercepts CONNECT method
	listener, err := net.Listen("tcp", port)
	if err != nil {
		log.Fatalf("[%s] Failed to start listener: %v", startTime, err)
	}
	defer listener.Close()

	for {
		clientConn, err := listener.Accept()
		if err != nil {
			log.Printf("[%s] Failed to accept connection: %v", startTime, err)
			continue
		}

		go handleConnection(clientConn, startTime)
	}
}

// logConnectRequest logs a CONNECT request in JSON format
func logConnectRequest(startTime time.Time, method, host string, status int, duration time.Duration, errMsg string) {
	logEntry := RequestLog{
		Timestamp:  startTime.Format(time.RFC3339),
		Method:     method,
		Path:       host,
		TargetURL:  host,
		Status:     status,
		DurationMs: duration.Milliseconds(),
		Error:      errMsg,
	}

	logJSON, err := json.Marshal(logEntry)
	if err != nil {
		log.Printf("Failed to marshal CONNECT log entry: %v", err)
		return
	}
	println(string(logJSON))
}

// handleConnection processes incoming TCP connections and routes CONNECT requests
func handleConnection(clientConn net.Conn, startTimeStr string) {
	startTime := time.Now()
	defer clientConn.Close()

	// Read the first line to check if it's a CONNECT request
	reader := bufio.NewReader(clientConn)
	firstLine, err := reader.ReadString('\n')
	if err != nil {
		log.Printf("[%s] Failed to read request: %v", startTimeStr, err)
		return
	}

	// Check if this is a CONNECT request
	if strings.HasPrefix(firstLine, "CONNECT ") {
		// Parse the CONNECT request
		parts := strings.Fields(firstLine)
		if len(parts) < 2 {
			log.Printf("[%s] Invalid CONNECT request: %q", startTimeStr, firstLine)
			// Log the error
			logConnectRequest(startTime, "CONNECT", "", 400, time.Since(startTime), "Invalid CONNECT request")
			return
		}

		targetHost := parts[1]

		// Read remaining headers
		headers := make(http.Header)
		for {
			line, err := reader.ReadString('\n')
			if err != nil || line == "\r\n" || line == "\n" {
				break
			}
			line = strings.TrimSpace(line)
			if colonIdx := strings.Index(line, ":"); colonIdx > 0 {
				key := strings.TrimSpace(line[:colonIdx])
				value := strings.TrimSpace(line[colonIdx+1:])
				headers.Add(key, value)
			}
		}

		// Create a fake http.ResponseWriter to pass to handleConnect
		hijackedConn := &hijackedConnection{
			Conn:   clientConn,
			reader: reader,
		}

		// Create minimal http.Request for CONNECT
		req := &http.Request{
			Method: "CONNECT",
			URL:    &url.URL{Host: targetHost},
			Host:   targetHost,
			Header: headers,
		}

		// Handle the CONNECT request with logging
		handleConnectWithLogging(hijackedConn, req, startTime)
	} else {
		// Not a CONNECT request, parse it as a regular HTTP request
		// We need to create a full http.Request from the buffered reader
		req, err := http.ReadRequest(reader)
		if err != nil {
			log.Printf("[%s] Failed to parse HTTP request: %v", startTimeStr, err)
			return
		}

		// Create a response writer that writes to the connection
		writer := &connResponseWriter{
			Conn: clientConn,
		}

		// Handle with our proxy handler wrapped in logging middleware
		LoggingMiddleware(ProxyHandler()).ServeHTTP(writer, req)
	}
}

// hijackedConnection wraps a connection for use as http.ResponseWriter
type hijackedConnection struct {
	net.Conn
	reader *bufio.Reader
}

func (h *hijackedConnection) Header() http.Header {
	return make(http.Header)
}

func (h *hijackedConnection) Write(data []byte) (int, error) {
	return h.Conn.Write(data)
}

func (h *hijackedConnection) WriteHeader(statusCode int) {
	// Already handled in handleConnect
}

// connResponseWriter writes HTTP responses to a connection
type connResponseWriter struct {
	net.Conn
	wroteHeader bool
}

func (c *connResponseWriter) Header() http.Header {
	return make(http.Header)
}

func (c *connResponseWriter) Write(data []byte) (int, error) {
	if !c.wroteHeader {
		c.WriteHeader(http.StatusOK)
	}
	return c.Conn.Write(data)
}

func (c *connResponseWriter) WriteHeader(statusCode int) {
	if c.wroteHeader {
		return
	}
	c.wroteHeader = true

	// Write status line
	statusText := http.StatusText(statusCode)
	if statusText == "" {
		statusText = "Unknown Status"
	}
	c.Conn.Write([]byte("HTTP/1.1 " + strconv.Itoa(statusCode) + " " + statusText + "\r\n"))
	c.Conn.Write([]byte("\r\n"))
}

// Implement Hijacker interface for handleConnect
type hijacker interface {
	Hijack() (net.Conn, *bufio.ReadWriter, error)
}

// We need to make our connection work with the hijacking approach
// Actually, let's simplify: handleConnect should work directly with the connection

// getEnv returns the environment variable value or a default
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
