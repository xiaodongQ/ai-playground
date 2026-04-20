package main

import (
	"encoding/json"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"
)

// RequestLog represents a structured log entry for each request
type RequestLog struct {
	Timestamp  string `json:"timestamp"`
	Method     string `json:"method"`
	Path       string `json:"path"`
	TargetURL  string `json:"target_url"`
	Status     int    `json:"status"`
	DurationMs int64  `json:"duration_ms"`
	Error      string `json:"error,omitempty"`
}

// logResponseWriter wraps http.ResponseWriter to capture status code
type logResponseWriter struct {
	http.ResponseWriter
	status int
}

func (lrw *logResponseWriter) WriteHeader(status int) {
	lrw.status = status
	lrw.ResponseWriter.WriteHeader(status)
}

// LoggingMiddleware wraps an http.Handler and logs each request in JSON format
func LoggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		startTime := time.Now()

		// Wrap the response writer to capture status code
		lrw := &logResponseWriter{
			ResponseWriter: w,
			status:         http.StatusOK, // default status
		}

		// Get target URL for logging
		targetURLStr := r.Header.Get("X-Target-URL")

		// Call the next handler
		next.ServeHTTP(lrw, r)

		// Calculate duration
		duration := time.Since(startTime)

		// Create log entry
		logEntry := RequestLog{
			Timestamp:  startTime.Format(time.RFC3339),
			Method:     r.Method,
			Path:       r.URL.Path,
			TargetURL:  targetURLStr,
			Status:     lrw.status,
			DurationMs: duration.Milliseconds(),
		}

		// Output JSON log to stdout
		logJSON, err := json.Marshal(logEntry)
		if err != nil {
			log.Printf("Failed to marshal log entry: %v", err)
			return
		}
		println(string(logJSON))
	})
}

// ProxyHandler creates a reverse proxy handler that forwards requests
// to the target URL specified in the X-Target-URL header
func ProxyHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		startTime := time.Now()

		// Parse target URL from X-Target-URL header
		targetURLStr := r.Header.Get("X-Target-URL")
		if targetURLStr == "" {
			http.Error(w, "Missing X-Target-URL header", http.StatusBadRequest)
			return
		}

		targetURL, err := url.Parse(targetURLStr)
		if err != nil {
			log.Printf("[%s] Failed to parse target URL %q: %v", startTime.Format(time.RFC3339), targetURLStr, err)
			http.Error(w, "Invalid target URL", http.StatusBadRequest)
			return
		}

		// Create reverse proxy
		proxy := httputil.NewSingleHostReverseProxy(targetURL)

		// Customize error handling for better error responses
		proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
			log.Printf("[%s] Proxy error for %q: %v", startTime.Format(time.RFC3339), r.URL.String(), err)

			// Determine appropriate status code based on error type
			statusCode := http.StatusBadGateway
			errorMsg := "Bad Gateway: unable to reach target server"

			// Check for timeout errors
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				statusCode = http.StatusGatewayTimeout
				errorMsg = "Gateway Timeout: target server did not respond in time"
			} else if strings.Contains(err.Error(), "connection refused") {
				statusCode = http.StatusBadGateway
				errorMsg = "Bad Gateway: connection refused by target server"
			} else if strings.Contains(err.Error(), "no such host") {
				statusCode = http.StatusBadGateway
				errorMsg = "Bad Gateway: target host not found"
			}

			http.Error(w, errorMsg, statusCode)
		}

		// Set timeouts for the proxy transport
		transport := &http.Transport{
			DialContext: (&net.Dialer{
				Timeout:   10 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			TLSHandshakeTimeout:   10 * time.Second,
			ResponseHeaderTimeout: 30 * time.Second,
			ExpectContinueTimeout: 1 * time.Second,
		}
		proxy.Transport = transport

		// Log request (internal logging, separate from JSON logs)
		log.Printf("[%s] %s %s -> %s",
			startTime.Format(time.RFC3339),
			r.Method,
			r.URL.Path,
			targetURL.String())

		// Forward request
		proxy.ServeHTTP(w, r)

		// Log completion (internal logging)
		duration := time.Since(startTime)
		log.Printf("[%s] Completed in %v", startTime.Format(time.RFC3339), duration)
	})
}

// handleConnect handles HTTPS CONNECT method for tunneling HTTPS traffic through the proxy
// It establishes a TCP connection to the target server and bidirectionally forwards data
func handleConnect(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()

	// Get the target host from the Request-URI (e.g., "example.com:443")
	targetHost := r.URL.Host
	if targetHost == "" {
		// Fallback to Host header if URL.Host is empty
		targetHost = r.Host
	}

	if targetHost == "" {
		log.Printf("[%s] CONNECT: Missing target host", startTime.Format(time.RFC3339))
		http.Error(w, "Missing target host", http.StatusBadRequest)
		return
	}

	// Ensure port is specified, default to 443 if not
	if !strings.Contains(targetHost, ":") {
		targetHost = targetHost + ":443"
	}

	// Establish TCP connection to target server
	targetConn, err := net.Dial("tcp", targetHost)
	if err != nil {
		log.Printf("[%s] CONNECT: Failed to connect to %q: %v", startTime.Format(time.RFC3339), targetHost, err)
		http.Error(w, "Failed to connect to target", http.StatusBadGateway)
		return
	}
	defer targetConn.Close()

	// Get the client connection from our custom ResponseWriter
	clientConn, ok := w.(*hijackedConnection)
	if !ok {
		// Try connResponseWriter as fallback
		if cw, ok2 := w.(*connResponseWriter); ok2 {
			clientConn = &hijackedConnection{Conn: cw.Conn}
		} else {
			log.Printf("[%s] CONNECT: Unexpected ResponseWriter type: %T", startTime.Format(time.RFC3339), w)
			http.Error(w, "Connection not available", http.StatusInternalServerError)
			return
		}
	}

	// Send 200 OK response to client to establish tunnel
	_, err = clientConn.Write([]byte("HTTP/1.1 200 Connection Established\r\n\r\n"))
	if err != nil {
		log.Printf("[%s] CONNECT: Failed to send response to client: %v", startTime.Format(time.RFC3339), err)
		return
	}

	log.Printf("[%s] CONNECT: Tunnel established to %q", startTime.Format(time.RFC3339), targetHost)

	// Bidirectionally forward data between client and target
	// Use channels to wait for both copies to complete
	done := make(chan error, 2)

	go func() {
		_, err := io.Copy(targetConn, clientConn)
		done <- err
	}()

	go func() {
		_, err := io.Copy(clientConn, targetConn)
		done <- err
	}()

	// Wait for either direction to complete (usually means connection closed)
	err = <-done
	if err != nil {
		log.Printf("[%s] CONNECT: Connection closed with error: %v", startTime.Format(time.RFC3339), err)
	} else {
		log.Printf("[%s] CONNECT: Tunnel closed normally", startTime.Format(time.RFC3339))
	}
}

// handleConnectWithLogging wraps handleConnect and adds JSON logging
func handleConnectWithLogging(w http.ResponseWriter, r *http.Request, startTime time.Time) {
	// Get the target host for logging
	targetHost := r.URL.Host
	if targetHost == "" {
		targetHost = r.Host
	}

	// Ensure port is specified for logging
	if !strings.Contains(targetHost, ":") {
		targetHost = targetHost + ":443"
	}

	// Log the start of CONNECT request
	logEntry := RequestLog{
		Timestamp:  startTime.Format(time.RFC3339),
		Method:     "CONNECT",
		Path:       targetHost,
		TargetURL:  targetHost,
		Status:     0, // Will be updated
		DurationMs: 0,
	}

	// We need to track if the connection was successful
	// For CONNECT, we'll log after the tunnel is established/closed

	// Create a wrapper to track status
	status := 200 // Default to success
	var errorMsg string

	// Get the client connection to verify it's available
	_, ok := w.(*hijackedConnection)
	if !ok {
		if _, ok2 := w.(*connResponseWriter); !ok2 {
			// Log error
			logEntry.Status = 500
			logEntry.Error = "Connection not available"
			logEntry.DurationMs = time.Since(startTime).Milliseconds()
			outputLog(logEntry)
			handleConnect(w, r)
			return
		}
	}

	// Check if target host is available
	if targetHost == "" {
		logEntry.Status = 400
		logEntry.Error = "Missing target host"
		logEntry.DurationMs = time.Since(startTime).Milliseconds()
		outputLog(logEntry)
		handleConnect(w, r)
		return
	}

	// Try to establish connection first to check if it will succeed
	testConn, err := net.Dial("tcp", targetHost)
	if err != nil {
		logEntry.Status = 502
		logEntry.Error = err.Error()
		logEntry.DurationMs = time.Since(startTime).Milliseconds()
		outputLog(logEntry)
		handleConnect(w, r)
		return
	}
	testConn.Close()

	// Connection successful, now handle the actual CONNECT
	// We'll log after the connection completes
	done := make(chan bool, 1)
	go func() {
		handleConnect(w, r)
		done <- true
	}()

	// Wait for completion (with timeout)
	select {
	case <-done:
		// Normal completion
		logEntry.Status = status
		logEntry.Error = errorMsg
		logEntry.DurationMs = time.Since(startTime).Milliseconds()
		outputLog(logEntry)
	case <-time.After(30 * time.Second):
		// Timeout
		logEntry.Status = 504
		logEntry.Error = "Connection timeout"
		logEntry.DurationMs = time.Since(startTime).Milliseconds()
		outputLog(logEntry)
	}
}

// outputLog outputs a log entry as JSON to stdout
func outputLog(entry RequestLog) {
	logJSON, err := json.Marshal(entry)
	if err != nil {
		log.Printf("Failed to marshal log entry: %v", err)
		return
	}
	println(string(logJSON))
}
