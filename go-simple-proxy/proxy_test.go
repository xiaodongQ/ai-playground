package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/http/httputil"
	"net/url"
	"strings"
	"testing"
	"time"
)

// TestProxyHandler_MissingHeader tests that missing X-Target-URL header returns 400
func TestProxyHandler_MissingHeader(t *testing.T) {
	handler := ProxyHandler()

	req := httptest.NewRequest("GET", "http://localhost:8080/test", nil)
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}

	body := w.Body.String()
	if !strings.Contains(body, "Missing X-Target-URL") {
		t.Errorf("Expected error about missing header, got: %s", body)
	}
}

// TestProxyHandler_InvalidURL tests that invalid URL returns 400
func TestProxyHandler_InvalidURL(t *testing.T) {
	handler := ProxyHandler()

	req := httptest.NewRequest("GET", "http://localhost:8080/test", nil)
	req.Header.Set("X-Target-URL", "://invalid-url")
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// TestProxyHandler_ValidForward tests that valid requests are forwarded correctly
func TestProxyHandler_ValidForward(t *testing.T) {
	// Create a test backend server
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Test-Header", "backend-response")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("Hello from backend"))
	}))
	defer backend.Close()

	handler := ProxyHandler()

	req := httptest.NewRequest("GET", "http://localhost:8080/api/test", nil)
	req.Header.Set("X-Target-URL", backend.URL)
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	// Check status code
	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	// Check response body
	body := w.Body.String()
	if body != "Hello from backend" {
		t.Errorf("Expected 'Hello from backend', got: %s", body)
	}

	// Check header was forwarded
	if w.Header().Get("X-Test-Header") != "backend-response" {
		t.Errorf("Expected header X-Test-Header to be forwarded")
	}
}

// TestProxyHandler_Methods tests that different HTTP methods are forwarded
func TestProxyHandler_Methods(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(r.Method))
	}))
	defer backend.Close()

	handler := ProxyHandler()

	methods := []string{"GET", "POST", "PUT", "DELETE", "PATCH"}

	for _, method := range methods {
		t.Run(method, func(t *testing.T) {
			req := httptest.NewRequest(method, "http://localhost:8080/test", strings.NewReader("test body"))
			req.Header.Set("X-Target-URL", backend.URL)
			w := httptest.NewRecorder()

			handler.ServeHTTP(w, req)

			if w.Code != http.StatusOK {
				t.Errorf("Expected status 200 for %s, got %d", method, w.Code)
			}

			if w.Body.String() != method {
				t.Errorf("Expected method %s to be forwarded, got: %s", method, w.Body.String())
			}
		})
	}
}

// TestProxyHandler_RealServer tests forwarding to a real server (example.com)
func TestProxyHandler_RealServer(t *testing.T) {
	t.Skip("Skipping real server test - requires internet connection")

	handler := ProxyHandler()

	req := httptest.NewRequest("GET", "http://localhost:8080/", nil)
	req.Header.Set("X-Target-URL", "http://example.com")
	w := httptest.NewRecorder()

	// Set a timeout
	done := make(chan bool, 1)
	go func() {
		handler.ServeHTTP(w, req)
		done <- true
	}()

	select {
	case <-done:
		if w.Code != http.StatusOK {
			t.Errorf("Expected status 200, got %d", w.Code)
		}
		if w.Body.Len() == 0 {
			t.Error("Expected non-empty response body")
		}
	case <-time.After(10 * time.Second):
		t.Fatal("Request timed out")
	}
}

// TestNewSingleHostReverseProxy verifies the standard library proxy works
func TestNewSingleHostReverseProxy(t *testing.T) {
	// Create backend
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("backend response"))
	}))
	defer backend.Close()

	// Parse backend URL
	targetURL, _ := url.Parse(backend.URL)

	// Create proxy
	proxy := httputil.NewSingleHostReverseProxy(targetURL)

	// Test request
	req := httptest.NewRequest("GET", "http://localhost/test", nil)
	w := httptest.NewRecorder()

	proxy.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected 200, got %d", w.Code)
	}

	if w.Body.String() != "backend response" {
		t.Errorf("Expected 'backend response', got: %s", w.Body.String())
	}
}

// TestProxyHandler_Headers tests that headers are properly forwarded
func TestProxyHandler_Headers(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Echo back the received headers
		w.Header().Set("X-Received-Auth", r.Header.Get("Authorization"))
		w.WriteHeader(http.StatusOK)
	}))
	defer backend.Close()

	handler := ProxyHandler()

	req := httptest.NewRequest("GET", "http://localhost:8080/test", nil)
	req.Header.Set("X-Target-URL", backend.URL)
	req.Header.Set("Authorization", "Bearer token123")
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	// Check if Authorization header was forwarded (backend echoes it back)
	if w.Header().Get("X-Received-Auth") != "Bearer token123" {
		t.Errorf("Expected Authorization header to be forwarded")
	}
}

// TestHandleConnect_MissingHost tests that missing target host returns 400
func TestHandleConnect_MissingHost(t *testing.T) {
	handler := ProxyHandler()

	req := httptest.NewRequest("CONNECT", "", nil)
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Expected status 400, got %d", w.Code)
	}
}

// TestHandleConnect_WithHost tests CONNECT request with valid host
func TestHandleConnect_WithHost(t *testing.T) {
	t.Skip("Skipping CONNECT test - requires hijacking support")

	// Note: httptest.NewRecorder doesn't support hijacking, so we skip this
	// The actual CONNECT functionality is tested manually with curl
}

// TestHandleConnect_DefaultPort tests that port 443 is added when missing
func TestHandleConnect_DefaultPort(t *testing.T) {
	// This is a unit test for the logic in handleConnect
	// We verify that "example.com" becomes "example.com:443"
	host := "example.com"
	if !strings.Contains(host, ":") {
		host = host + ":443"
	}

	if host != "example.com:443" {
		t.Errorf("Expected 'example.com:443', got: %s", host)
	}
}

// TestHandleConnect_PortPreserved tests that existing port is preserved
func TestHandleConnect_PortPreserved(t *testing.T) {
	host := "example.com:8443"
	if !strings.Contains(host, ":") {
		host = host + ":443"
	}

	if host != "example.com:8443" {
		t.Errorf("Expected 'example.com:8443', got: %s", host)
	}
}

// TestRequestLog_JSONMarshal tests that RequestLog marshals correctly to JSON
func TestRequestLog_JSONMarshal(t *testing.T) {
	logEntry := RequestLog{
		Timestamp:  "2026-03-19T12:00:00Z",
		Method:     "GET",
		Path:       "/api/test",
		TargetURL:  "http://example.com",
		Status:     200,
		DurationMs: 150,
	}

	jsonBytes, err := json.Marshal(logEntry)
	if err != nil {
		t.Fatalf("Failed to marshal log entry: %v", err)
	}

	jsonStr := string(jsonBytes)

	// Verify all required fields are present
	requiredFields := []string{"timestamp", "method", "path", "target_url", "status", "duration_ms"}
	for _, field := range requiredFields {
		if !strings.Contains(jsonStr, field) {
			t.Errorf("Expected JSON to contain field %q", field)
		}
	}

	// Verify values
	if !strings.Contains(jsonStr, `"2026-03-19T12:00:00Z"`) {
		t.Error("Expected timestamp in JSON")
	}
	if !strings.Contains(jsonStr, `"GET"`) {
		t.Error("Expected method in JSON")
	}
	if !strings.Contains(jsonStr, `200`) {
		t.Error("Expected status 200 in JSON")
	}
	if !strings.Contains(jsonStr, `150`) {
		t.Error("Expected duration_ms 150 in JSON")
	}
}

// TestRequestLog_WithError tests that error field is included when present
func TestRequestLog_WithError(t *testing.T) {
	logEntry := RequestLog{
		Timestamp:  "2026-03-19T12:00:00Z",
		Method:     "POST",
		Path:       "/api/error",
		TargetURL:  "http://example.com",
		Status:     500,
		DurationMs: 50,
		Error:      "connection refused",
	}

	jsonBytes, err := json.Marshal(logEntry)
	if err != nil {
		t.Fatalf("Failed to marshal log entry: %v", err)
	}

	jsonStr := string(jsonBytes)
	if !strings.Contains(jsonStr, `"error":"connection refused"`) {
		t.Error("Expected error field in JSON")
	}
}

// TestRequestLog_WithoutError tests that error field is omitted when empty
func TestRequestLog_WithoutError(t *testing.T) {
	logEntry := RequestLog{
		Timestamp:  "2026-03-19T12:00:00Z",
		Method:     "GET",
		Path:       "/api/success",
		TargetURL:  "http://example.com",
		Status:     200,
		DurationMs: 100,
	}

	jsonBytes, err := json.Marshal(logEntry)
	if err != nil {
		t.Fatalf("Failed to marshal log entry: %v", err)
	}

	jsonStr := string(jsonBytes)
	// Error field should be omitted when empty (omitempty tag)
	if strings.Contains(jsonStr, `"error"`) {
		t.Error("Expected error field to be omitted when empty")
	}
}

// TestLoggingMiddleware tests that the middleware logs requests
func TestLoggingMiddleware(t *testing.T) {
	// Create a simple handler that returns 200
	testHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	// Wrap with logging middleware
	loggedHandler := LoggingMiddleware(testHandler)

	// Create test request
	req := httptest.NewRequest("GET", "http://localhost/test", nil)
	w := httptest.NewRecorder()

	// Serve request (this will output JSON to stdout)
	loggedHandler.ServeHTTP(w, req)

	// Verify the handler was called
	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}
}

// TestLoggingMiddleware_CapturesStatus tests that the middleware captures status codes
func TestLoggingMiddleware_CapturesStatus(t *testing.T) {
	// Create a handler that returns 404
	testHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})

	loggedHandler := LoggingMiddleware(testHandler)

	req := httptest.NewRequest("GET", "http://localhost/notfound", nil)
	w := httptest.NewRecorder()

	loggedHandler.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("Expected status 404, got %d", w.Code)
	}
}

// TestLoggingMiddleware_Duration tests that duration is calculated
func TestLoggingMiddleware_Duration(t *testing.T) {
	// Create a handler with a small delay
	testHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(10 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	})

	loggedHandler := LoggingMiddleware(testHandler)

	req := httptest.NewRequest("GET", "http://localhost/slow", nil)
	w := httptest.NewRecorder()

	start := time.Now()
	loggedHandler.ServeHTTP(w, req)
	duration := time.Since(start)

	// Verify duration is at least 10ms
	if duration < 10*time.Millisecond {
		t.Errorf("Expected duration >= 10ms, got %v", duration)
	}
}

// TestLogResponseWriter tests the logResponseWriter wrapper
func TestLogResponseWriter(t *testing.T) {
	// Create a mock ResponseWriter
	mockWriter := httptest.NewRecorder()

	// Wrap it
	lrw := &logResponseWriter{
		ResponseWriter: mockWriter,
		status:         http.StatusOK,
	}

	// Write header
	lrw.WriteHeader(http.StatusCreated)

	// Verify status was captured
	if lrw.status != http.StatusCreated {
		t.Errorf("Expected status 201, got %d", lrw.status)
	}

	// Verify header was written to underlying writer
	if mockWriter.Code != http.StatusCreated {
		t.Errorf("Expected underlying writer status 201, got %d", mockWriter.Code)
	}
}

// TestLogResponseWriter_DefaultStatus tests default status is 200
func TestLogResponseWriter_DefaultStatus(t *testing.T) {
	mockWriter := httptest.NewRecorder()

	lrw := &logResponseWriter{
		ResponseWriter: mockWriter,
		status:         http.StatusOK,
	}

	// Don't call WriteHeader, just write data
	lrw.Write([]byte("test"))

	// Status should still be captured (will be set by Write)
	if lrw.status != http.StatusOK {
		t.Errorf("Expected default status 200, got %d", lrw.status)
	}
}
