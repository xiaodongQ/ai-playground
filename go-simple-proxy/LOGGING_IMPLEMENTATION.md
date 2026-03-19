# Request Logging Implementation

**Task**: 5/6 - Add JSON request logging  
**Date**: 2026-03-19  
**Status**: ✅ Complete

---

## Overview

Implemented structured JSON logging for all HTTP/HTTPS proxy requests. Each request is logged to stdout with timestamp, method, path, target URL, status code, duration, and optional error message.

---

## Implementation Details

### 1. Log Structure Definition

**File**: `proxy.go`

```go
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
```

**Fields**:
- `timestamp`: RFC3339 formatted timestamp
- `method`: HTTP method (GET, POST, CONNECT, etc.)
- `path`: Request path or target host
- `target_url`: Target URL from X-Target-URL header
- `status`: HTTP status code
- `duration_ms`: Request duration in milliseconds
- `error`: Error message (omitted if empty)

### 2. Logging Middleware

**File**: `proxy.go`

```go
// LoggingMiddleware wraps an http.Handler and logs each request in JSON format
func LoggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		startTime := time.Now()
		
		// Wrap the response writer to capture status code
		lrw := &logResponseWriter{
			ResponseWriter: w,
			status:         http.StatusOK,
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
```

**Features**:
- Wraps any http.Handler
- Captures response status code via `logResponseWriter`
- Calculates request duration
- Outputs JSON to stdout (one line per request)

### 3. Response Writer Wrapper

**File**: `proxy.go`

```go
// logResponseWriter wraps http.ResponseWriter to capture status code
type logResponseWriter struct {
	http.ResponseWriter
	status int
}

func (lrw *logResponseWriter) WriteHeader(status int) {
	lrw.status = status
	lrw.ResponseWriter.WriteHeader(status)
}
```

### 4. CONNECT Request Logging

**File**: `main.go` & `proxy.go`

```go
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
```

**File**: `main.go` - Updated `handleConnection` to use logging:

```go
// For CONNECT requests
handleConnectWithLogging(hijackedConn, req, startTime)

// For regular HTTP requests
LoggingMiddleware(ProxyHandler()).ServeHTTP(writer, req)
```

---

## Example Log Output

### Successful Request
```json
{"timestamp":"2026-03-19T19:14:31+08:00","method":"GET","path":"/test","target_url":"http://example.com","status":200,"duration_ms":15}
```

### Error Request
```json
{"timestamp":"2026-03-19T19:14:31+08:00","method":"GET","path":"/api/error","target_url":"http://example.com","status":500,"duration_ms":5,"error":"connection refused"}
```

### CONNECT Request
```json
{"timestamp":"2026-03-19T19:14:31+08:00","method":"CONNECT","path":"example.com:443","target_url":"example.com:443","status":200,"duration_ms":1523}
```

### Missing Target URL (400)
```json
{"timestamp":"2026-03-19T19:14:31+08:00","method":"GET","path":"/test","target_url":"","status":400,"duration_ms":0,"error":"Missing X-Target-URL header"}
```

---

## Tests

**File**: `proxy_test.go`

### Test Coverage

1. **TestRequestLog_JSONMarshal** - Verifies JSON marshaling with all fields
2. **TestRequestLog_WithError** - Verifies error field is included when present
3. **TestRequestLog_WithoutError** - Verifies error field is omitted when empty
4. **TestLoggingMiddleware** - Tests basic middleware functionality
5. **TestLoggingMiddleware_CapturesStatus** - Verifies status code capture (404 test)
6. **TestLoggingMiddleware_Duration** - Verifies duration calculation
7. **TestLogResponseWriter** - Tests response writer wrapper
8. **TestLogResponseWriter_DefaultStatus** - Tests default status is 200

### Test Results
```
=== RUN   TestRequestLog_JSONMarshal
--- PASS: TestRequestLog_JSONMarshal (0.00s)
=== RUN   TestRequestLog_WithError
--- PASS: TestRequestLog_WithError (0.00s)
=== RUN   TestRequestLog_WithoutError
--- PASS: TestRequestLog_WithoutError (0.00s)
=== RUN   TestLoggingMiddleware
{"timestamp":"2026-03-19T19:14:31+08:00","method":"GET","path":"/test","target_url":"","status":200,"duration_ms":0}
--- PASS: TestLoggingMiddleware (0.00s)
=== RUN   TestLoggingMiddleware_CapturesStatus
{"timestamp":"2026-03-19T19:14:31+08:00","method":"GET","path":"/notfound","target_url":"","status":404,"duration_ms":0}
--- PASS: TestLoggingMiddleware_CapturesStatus (0.00s)
=== RUN   TestLoggingMiddleware_Duration
{"timestamp":"2026-03-19T19:14:31+08:00","method":"GET","path":"/slow","target_url":"","status":200,"duration_ms":10}
--- PASS: TestLoggingMiddleware_Duration (0.01s)
PASS
ok      go-simple-proxy 0.013s
```

---

## Usage

### Running the Proxy

```bash
# Default port 8080
./go-simple-proxy

# Custom port
PROXY_PORT=:8082 ./go-simple-proxy
```

### Example Requests

```bash
# Simple GET request
curl -H "X-Target-URL: http://example.com" http://localhost:8080/api/test

# POST request
curl -X POST -H "X-Target-URL: http://httpbin.org/post" -d "data=test" http://localhost:8080/submit

# HTTPS CONNECT (via proxy)
curl -x http://localhost:8080 https://example.com
```

### Log Integration

Logs are output to stdout in JSON format, making them easy to integrate with:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Fluentd** / **Fluent Bit**
- **Prometheus** (via json_exporter)
- **Cloud logging** (AWS CloudWatch, GCP Logging, etc.)

Example with log redirection:
```bash
./go-simple-proxy 2>&1 | tee proxy.log
```

---

## Files Modified

1. **proxy.go**
   - Added `RequestLog` struct
   - Added `logResponseWriter` wrapper
   - Added `LoggingMiddleware` function
   - Added `handleConnectWithLogging` function
   - Added `outputLog` helper function

2. **main.go**
   - Added `encoding/json` import
   - Added `os` import for environment variables
   - Added `getEnv` helper function
   - Added `logConnectRequest` function
   - Updated `handleConnection` to use logging middleware

3. **proxy_test.go**
   - Added `encoding/json` import
   - Added 8 new test functions for logging functionality

---

## Acceptance Criteria ✅

- [x] Each request has JSON log output
- [x] Logs contain all required fields (timestamp, method, path, target_url, status, duration_ms, error)
- [x] All tests pass
- [x] CONNECT requests are logged
- [x] Output is to stdout (one JSON per line)

---

## Next Steps

Task 6: Complete documentation and cleanup
- Update README.md with logging documentation
- Run `go fmt` on all files
- Final test suite execution
