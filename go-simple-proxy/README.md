# Go Simple Proxy

轻量级 HTTP/HTTPS 反向代理服务器，使用 Go 标准库实现，无第三方依赖。

## 功能特性

- ✅ **HTTP 反向代理** - 支持 GET、POST、PUT、DELETE、PATCH 等所有 HTTP 方法
- ✅ **HTTPS 隧道支持** - 处理 CONNECT 方法，代理 HTTPS 流量
- ✅ **JSON 格式日志** - 结构化日志输出，便于接入 ELK 等日志系统
- ✅ **完善的错误处理** - 超时返回 504，连接失败返回 502
- ✅ **零第三方依赖** - 仅使用 Go 标准库
- ✅ **可配置端口** - 通过环境变量 `PROXY_PORT` 自定义监听端口

## 快速开始

### 环境要求

- Go 1.21 或更高版本

### 安装

```bash
# 克隆或下载项目
cd go-simple-proxy

# 下载依赖（仅标准库，通常无需额外操作）
go mod download

# 编译
go build -o go-simple-proxy

# 或者直接运行
go run main.go
```

### 基本使用

```bash
# 启动代理服务器（默认端口 8080）
./go-simple-proxy

# 自定义端口
PROXY_PORT=:3000 ./go-simple-proxy
```

### 使用示例

#### 1. 代理 HTTP 请求

```bash
# 启动代理
./go-simple-proxy

# 通过代理访问目标服务器
curl -H "X-Target-URL: http://example.com" http://localhost:8080/api/users
```

#### 2. 代理 HTTPS 请求（CONNECT 隧道）

```bash
# 使用 curl 通过 HTTPS 代理
curl -x http://localhost:8080 https://example.com
```

#### 3. 转发 POST 请求

```bash
curl -X POST \
  -H "X-Target-URL: http://api.example.com" \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}' \
  http://localhost:8080/users
```

## 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `PROXY_PORT` | `:8080` | 代理服务器监听端口 |

### 请求头配置

| 请求头 | 说明 | 示例 |
|--------|------|------|
| `X-Target-URL` | 目标服务器 URL（HTTP 代理必需） | `http://api.example.com` |

## API 说明

### HTTP 反向代理模式

当请求包含 `X-Target-URL` 请求头时，代理会将请求转发到指定的目标服务器。

**请求流程：**
1. 客户端发送请求到代理服务器
2. 代理读取 `X-Target-URL` 请求头
3. 代理将请求转发到目标服务器
4. 目标服务器响应返回给客户端

**示例：**
```bash
curl -H "X-Target-URL: http://backend:8000" http://localhost:8080/api/data
```

### HTTPS 隧道模式（CONNECT 方法）

当客户端使用 `curl -x` 或浏览器代理设置时，会自动使用 CONNECT 方法建立隧道。

**示例：**
```bash
# 通过代理访问 HTTPS 网站
curl -x http://localhost:8080 https://example.com
```

## 日志格式

代理服务器以 JSON 格式输出请求日志到 stdout，每条日志包含以下字段：

```json
{
  "timestamp": "2026-03-19T19:00:00+08:00",
  "method": "GET",
  "path": "/api/users",
  "target_url": "http://backend:8000",
  "status": 200,
  "duration_ms": 150
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | string | 请求时间（RFC3339 格式） |
| `method` | string | HTTP 方法（GET、POST 等） |
| `path` | string | 请求路径 |
| `target_url` | string | 目标服务器 URL |
| `status` | integer | 响应状态码 |
| `duration_ms` | integer | 请求耗时（毫秒） |
| `error` | string | 错误信息（可选，仅在出错时出现） |

### 日志示例

**成功请求：**
```json
{"timestamp":"2026-03-19T19:00:00+08:00","method":"GET","path":"/api/users","target_url":"http://backend:8000","status":200,"duration_ms":45}
```

**连接失败：**
```json
{"timestamp":"2026-03-19T19:00:01+08:00","method":"CONNECT","path":"example.com:443","target_url":"example.com:443","status":502,"duration_ms":10,"error":"connection refused"}
```

**请求超时：**
```json
{"timestamp":"2026-03-19T19:00:02+08:00","method":"GET","path":"/slow","target_url":"http://slow-server.com","status":504,"duration_ms":30000,"error":"Gateway Timeout"}
```

## 错误处理

代理服务器会根据错误类型返回相应的 HTTP 状态码：

| 状态码 | 说明 | 触发条件 |
|--------|------|----------|
| `400` | Bad Request | 缺少 `X-Target-URL` 请求头或 URL 格式无效 |
| `502` | Bad Gateway | 目标服务器拒绝连接、主机不存在 |
| `504` | Gateway Timeout | 目标服务器响应超时 |

### 超时配置

代理内置以下超时设置：

- **连接超时**: 10 秒
- **TLS 握手超时**: 10 秒
- **响应头超时**: 30 秒
- **继续期望超时**: 1 秒

## 项目结构

```
go-simple-proxy/
├── main.go              # 程序入口，TCP 连接处理
├── proxy.go             # 代理核心逻辑，日志中间件
├── proxy_test.go        # 单元测试
├── go.mod               # Go 模块定义
├── README.md            # 使用说明
└── docs/
    └── plans/
        └── 2026-03-19-go-simple-proxy.md
```

## 测试

运行所有测试：

```bash
go test ./... -v
```

测试覆盖：

- ✅ 缺失请求头处理
- ✅ 无效 URL 处理
- ✅ 请求转发功能
- ✅ 多种 HTTP 方法支持
- ✅ 请求头转发
- ✅ CONNECT 方法逻辑
- ✅ 日志 JSON 序列化
- ✅ 日志中间件功能

## 后续迭代计划

- [ ] YAML 配置文件支持
- [ ] SOCKS5 协议支持
- [ ] IP 白名单/黑名单
- [ ] 上游代理（链式代理）
- [ ] 请求/响应内容过滤
- [ ] Prometheus 指标导出

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
