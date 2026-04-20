#!/bin/bash

# Test script for JSON logging feature

echo "=== Starting proxy server on port 8082 ==="
./go-simple-proxy > /tmp/proxy_test.log 2>&1 &
PROXY_PID=$!
sleep 2

# Check if server started
if ! kill -0 $PROXY_PID 2>/dev/null; then
    echo "ERROR: Server failed to start"
    cat /tmp/proxy_test.log
    exit 1
fi

echo "Server started with PID $PROXY_PID"
echo ""

# Test 1: Request with missing header (should log 400)
echo "=== Test 1: Request without X-Target-URL (expect 400) ==="
curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:8082/test
sleep 1

# Test 2: Valid request to httpbin
echo ""
echo "=== Test 2: Valid GET request ==="
curl -s -H "X-Target-URL: http://httpbin.org/get" http://localhost:8082/api/test -o /dev/null -w "Status: %{http_code}\n"
sleep 1

# Test 3: POST request
echo ""
echo "=== Test 3: POST request ==="
curl -s -X POST -H "X-Target-URL: http://httpbin.org/post" -d "test=data" http://localhost:8082/submit -o /dev/null -w "Status: %{http_code}\n"
sleep 1

# Stop server
echo ""
echo "=== Stopping server ==="
kill $PROXY_PID 2>/dev/null
wait $PROXY_PID 2>/dev/null

echo ""
echo "=== JSON Logs Output ==="
grep -E '^\{.*\}$' /tmp/proxy_test.log || echo "No JSON logs found in stdout"

echo ""
echo "=== All Logs (for debugging) ==="
cat /tmp/proxy_test.log

# Cleanup
rm -f /tmp/proxy_test.log
