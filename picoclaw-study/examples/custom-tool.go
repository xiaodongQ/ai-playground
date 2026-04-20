// PicoClaw 自定义工具示例
// 文件：examples/custom-tool.go
// 说明：演示如何实现和注册自定义工具

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// ============================================
// 工具接口定义（来自 PicoClaw 核心）
// ============================================

// Context 执行上下文
type Context interface {
	Get(key string) any
	Set(key string, value any)
}

// ParameterSchema 参数定义
type ParameterSchema struct {
	Type        string   `json:"type"`
	Description string   `json:"description"`
	Required    bool     `json:"required"`
	Enum        []string `json:"enum,omitempty"`
	Default     any      `json:"default,omitempty"`
}

// Result 工具执行结果
type Result struct {
	ToolCallID string         `json:"tool_call_id"`
	Content    string         `json:"content"`
	Error      error          `json:"error,omitempty"`
	Metadata   map[string]any `json:"metadata,omitempty"`
}

// Tool 工具接口
type Tool interface {
	Name() string
	Description() string
	Parameters() map[string]ParameterSchema
	Execute(ctx Context, params map[string]any) Result
}

// ============================================
// 示例 1: 天气查询工具
// ============================================

// WeatherTool 天气查询工具
type WeatherTool struct {
	apiKey string
	baseURL string
}

// NewWeatherTool 创建天气工具
func NewWeatherTool(apiKey string) *WeatherTool {
	return &WeatherTool{
		apiKey:  apiKey,
		baseURL: "https://api.openweathermap.org/data/2.5",
	}
}

// Name 工具名称（必须唯一）
func (w *WeatherTool) Name() string {
	return "weather"
}

// Description 工具描述（LLM 会看到这个描述来决定是否使用工具）
func (w *WeatherTool) Description() string {
	return "Get current weather information for a specific location. Returns temperature, humidity, and conditions."
}

// Parameters 参数定义（LLM 会看到这个来生成正确的调用参数）
func (w *WeatherTool) Parameters() map[string]ParameterSchema {
	return map[string]ParameterSchema{
		"city": {
			Type:        "string",
			Description: "The city name (e.g., 'Tokyo', 'New York')",
			Required:    true,
		},
		"country": {
			Type:        "string",
			Description: "Optional country code (e.g., 'JP', 'US')",
			Required:    false,
		},
		"units": {
			Type:        "string",
			Description: "Temperature units",
			Required:    false,
			Enum:        []string{"celsius", "fahrenheit", "kelvin"},
			Default:     "celsius",
		},
	}
}

// Execute 执行工具调用
func (w *WeatherTool) Execute(ctx Context, params map[string]any) Result {
	startTime := time.Now()
	
	// 1. 参数验证
	city, ok := params["city"].(string)
	if !ok || city == "" {
		return Result{
			Error: fmt.Errorf("missing or invalid 'city' parameter"),
		}
	}
	
	country, _ := params["country"].(string)
	units, ok := params["units"].(string)
	if !ok {
		units = "celsius"
	}
	
	// 2. 构建 API 请求
	unitParam := "metric"
	if units == "fahrenheit" {
		unitParam = "imperial"
	}
	
	location := city
	if country != "" {
		location = fmt.Sprintf("%s,%s", city, country)
	}
	
	url := fmt.Sprintf("%s/weather?q=%s&units=%s&appid=%s",
		w.baseURL, location, unitParam, w.apiKey)
	
	// 3. 发送 HTTP 请求
	resp, err := http.Get(url)
	if err != nil {
		return Result{
			Error: fmt.Errorf("HTTP request failed: %w", err),
			Metadata: map[string]any{
				"execution_time_ms": time.Since(startTime).Milliseconds(),
			},
		}
	}
	defer resp.Body.Close()
	
	// 4. 解析响应
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return Result{
			Error: fmt.Errorf("failed to read response: %w", err),
		}
	}
	
	if resp.StatusCode != http.StatusOK {
		return Result{
			Error: fmt.Errorf("API error: %s", string(body)),
		}
	}
	
	// 5. 提取关键信息
	var weatherData map[string]any
	if err := json.Unmarshal(body, &weatherData); err != nil {
		return Result{
			Error: fmt.Errorf("failed to parse JSON: %w", err),
		}
	}
	
	// 6. 格式化输出
	main, _ := weatherData["main"].(map[string]any)
	weather, _ := weatherData["weather"].([]any)
	weather0, _ := weather[0].(map[string]any)
	
	temp, _ := main["temp"].(float64)
	humidity, _ := main["humidity"].(float64)
	description, _ := weather0["description"].(string)
	
	content := fmt.Sprintf(
		"Weather in %s:\n- Temperature: %.1f°%s\n- Humidity: %.0f%%\n- Conditions: %s",
		city,
		temp,
		map[string]string{"metric": "C", "imperial": "F"}[unitParam],
		humidity,
		description,
	)
	
	return Result{
		Content: content,
		Metadata: map[string]any{
			"city":           city,
			"temperature":    temp,
			"humidity":       humidity,
			"execution_time_ms": time.Since(startTime).Milliseconds(),
		},
	}
}

// ============================================
// 示例 2: 数据库查询工具
// ============================================

// DatabaseTool 数据库查询工具
type DatabaseTool struct {
	// 实际项目中这里会有数据库连接
	// db *sql.DB
}

func NewDatabaseTool() *DatabaseTool {
	return &DatabaseTool{}
}

func (d *DatabaseTool) Name() string {
	return "database_query"
}

func (d *DatabaseTool) Description() string {
	return "Execute a read-only SQL query against the database. Use this to retrieve data."
}

func (d *DatabaseTool) Parameters() map[string]ParameterSchema {
	return map[string]ParameterSchema{
		"query": {
			Type:        "string",
			Description: "SQL SELECT query (read-only, no modifications allowed)",
			Required:    true,
		},
		"limit": {
			Type:        "number",
			Description: "Maximum number of rows to return",
			Required:    false,
			Default:     100,
		},
	}
}

func (d *DatabaseTool) Execute(ctx Context, params map[string]any) Result {
	startTime := time.Now()
	
	// 1. 参数验证
	query, ok := params["query"].(string)
	if !ok || query == "" {
		return Result{
			Error: fmt.Errorf("missing or invalid 'query' parameter"),
		}
	}
	
	// 2. 安全检查：只允许 SELECT 查询
	// 这是重要的安全措施，防止 SQL 注入或数据修改
	queryUpper := strings.TrimSpace(strings.ToUpper(query))
	if !strings.HasPrefix(queryUpper, "SELECT") {
		return Result{
			Error: fmt.Errorf("only SELECT queries are allowed"),
		}
	}
	
	// 禁止危险操作
	dangerous := []string{"DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"}
	for _, dangerousKeyword := range dangerous {
		if strings.Contains(queryUpper, dangerousKeyword) {
			return Result{
				Error: fmt.Errorf("query contains forbidden keyword: %s", dangerousKeyword),
			}
		}
	}
	
	// 3. 执行查询（示例代码，实际需要数据库连接）
	/*
	rows, err := d.db.QueryContext(ctx.Context(), query)
	if err != nil {
		return Result{
			Error: fmt.Errorf("query failed: %w", err),
		}
	}
	defer rows.Close()
	
	// 4. 转换为 JSON
	columns, _ := rows.Columns()
	results := make([]map[string]any, 0)
	
	for rows.Next() {
		values := make([]any, len(columns))
		valuePtrs := make([]any, len(columns))
		for i := range values {
			valuePtrs[i] = &values[i]
		}
		
		rows.Scan(valuePtrs...)
		
		rowMap := make(map[string]any)
		for i, col := range columns {
			rowMap[col] = values[i]
		}
		results = append(results, rowMap)
	}
	
	// 5. 格式化输出
	jsonBytes, _ := json.MarshalIndent(results, "", "  ")
	*/
	
	// 示例返回
	return Result{
		Content: "Query executed successfully (mock result)",
		Metadata: map[string]any{
			"query":           query,
			"execution_time_ms": time.Since(startTime).Milliseconds(),
			"rows_returned":    0, // 实际项目中填充
		},
	}
}

// ============================================
// 示例 3: HTTP 请求工具
// ============================================

// HTTPRequestTool HTTP 请求工具
type HTTPRequestTool struct {
	client *http.Client
}

func NewHTTPRequestTool() *HTTPRequestTool {
	return &HTTPRequestTool{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (h *HTTPRequestTool) Name() string {
	return "http_request"
}

func (h *HTTPRequestTool) Description() string {
	return "Make an HTTP request to a web API. Supports GET, POST, PUT, DELETE methods."
}

func (h *HTTPRequestTool) Parameters() map[string]ParameterSchema {
	return map[string]ParameterSchema{
		"url": {
			Type:        "string",
			Description: "The URL to request",
			Required:    true,
		},
		"method": {
			Type:        "string",
			Description: "HTTP method",
			Required:    false,
			Enum:        []string{"GET", "POST", "PUT", "DELETE", "PATCH"},
			Default:     "GET",
		},
		"headers": {
			Type:        "object",
			Description: "HTTP headers as key-value pairs",
			Required:    false,
		},
		"body": {
			Type:        "string",
			Description: "Request body (for POST/PUT/PATCH)",
			Required:    false,
		},
	}
}

func (h *HTTPRequestTool) Execute(ctx Context, params map[string]any) Result {
	startTime := time.Now()
	
	// 1. 参数验证
	url, ok := params["url"].(string)
	if !ok || url == "" {
		return Result{
			Error: fmt.Errorf("missing or invalid 'url' parameter"),
		}
	}
	
	method, ok := params["method"].(string)
	if !ok {
		method = "GET"
	}
	
	// 2. 创建请求
	var bodyReader io.Reader
	if bodyStr, ok := params["body"].(string); ok && bodyStr != "" {
		bodyReader = strings.NewReader(bodyStr)
	}
	
	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		return Result{
			Error: fmt.Errorf("failed to create request: %w", err),
		}
	}
	
	// 3. 设置 headers
	if headers, ok := params["headers"].(map[string]any); ok {
		for key, value := range headers {
			if strValue, ok := value.(string); ok {
				req.Header.Set(key, strValue)
			}
		}
	}
	
	// 4. 发送请求
	resp, err := h.client.Do(req)
	if err != nil {
		return Result{
			Error: fmt.Errorf("request failed: %w", err),
			Metadata: map[string]any{
				"execution_time_ms": time.Since(startTime).Milliseconds(),
			},
		}
	}
	defer resp.Body.Close()
	
	// 5. 读取响应
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return Result{
			Error: fmt.Errorf("failed to read response: %w", err),
		}
	}
	
	// 6. 格式化输出
	content := fmt.Sprintf(
		"Status: %d %s\n\nHeaders:\n%s\n\nBody:\n%s",
		resp.StatusCode,
		resp.Status,
		formatHeaders(resp.Header),
		string(body),
	)
	
	return Result{
		Content: content,
		Metadata: map[string]any{
			"status_code":     resp.StatusCode,
			"content_length":  len(body),
			"execution_time_ms": time.Since(startTime).Milliseconds(),
		},
	}
}

func formatHeaders(headers http.Header) string {
	var builder strings.Builder
	for key, values := range headers {
		builder.WriteString(fmt.Sprintf("  %s: %s\n", key, strings.Join(values, ", ")))
	}
	return builder.String()
}

// ============================================
// 工具注册示例
// ============================================

// ToolRegistry 简化工具注册表
type ToolRegistry struct {
	tools map[string]Tool
}

func NewToolRegistry() *ToolRegistry {
	return &ToolRegistry{
		tools: make(map[string]Tool),
	}
}

func (r *ToolRegistry) Register(tool Tool) {
	r.tools[tool.Name()] = tool
	fmt.Printf("✓ Tool registered: %s\n", tool.Name())
}

func (r *ToolRegistry) Get(name string) Tool {
	return r.tools[name]
}

func (r *ToolRegistry) List() []string {
	names := make([]string, 0, len(r.tools))
	for name := range r.tools {
		names = append(names, name)
	}
	return names
}

// ============================================
// 主函数 - 演示使用
// ============================================

func main() {
	// 创建工具注册表
	registry := NewToolRegistry()
	
	// 注册自定义工具
	registry.Register(NewWeatherTool("your-api-key"))
	registry.Register(NewDatabaseTool())
	registry.Register(NewHTTPRequestTool())
	
	// 列出所有已注册工具
	fmt.Println("\n📦 Registered Tools:")
	for _, name := range registry.List() {
		tool := registry.Get(name)
		fmt.Printf("  - %s: %s\n", name, tool.Description())
	}
	
	// 示例：执行工具调用
	fmt.Println("\n🔧 Executing tool call...")
	
	// 模拟上下文
	ctx := &SimpleContext{data: make(map[string]any)}
	
	// 调用天气工具
	weatherTool := registry.Get("weather").(*WeatherTool)
	result := weatherTool.Execute(ctx, map[string]any{
		"city":    "Tokyo",
		"country": "JP",
		"units":   "celsius",
	})
	
	if result.Error != nil {
		fmt.Printf("Error: %v\n", result.Error)
	} else {
		fmt.Printf("Result:\n%s\n", result.Content)
		fmt.Printf("Metadata: %+v\n", result.Metadata)
	}
}

// SimpleContext 简单的上下文实现
type SimpleContext struct {
	data map[string]any
}

func (c *SimpleContext) Get(key string) any {
	return c.data[key]
}

func (c *SimpleContext) Set(key string, value any) {
	c.data[key] = value
}

// 需要的 import
import "strings"
