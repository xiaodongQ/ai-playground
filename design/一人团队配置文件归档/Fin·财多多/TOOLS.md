# TOOLS.md - Fin·财多多工具配置

**最后更新**: 2026-03-09  
**维护者**: Fin·财多多 💰

---

## 内置工具（已配置）

| 工具 | 状态 | 说明 |
|------|------|------|
| `web_search` | ⏳ 需 Brave API | 搜索财经新闻 |
| `web_fetch` | ✅ 可用 | 抓取网页数据（新浪财经、东方财富等） |
| `tavily` | ✅ 已配置 | AI 优化搜索（优先使用） |

---

## 外部 API（免费方案）

### Alpha Vantage（股票行情）

| 属性 | 值 |
|------|-----|
| **状态** | ⏳ 待配置 |
| **API Key** | 存储在 Gateway 环境变量 `ALPHA_VANTAGE_API_KEY` |
| **免费额度** | 25 次/天，5 次/分钟 |
| **文档** | https://www.alphavantage.co/documentation/ |
| **用途** | 股价、K 线、技术指标、财报数据 |

**配置步骤**:
1. 注册：https://www.alphavantage.co/support/#api-key
2. 添加到 Gateway: `openclaw config.patch --note "添加 Alpha Vantage API"`
3. 重启 Gateway: `openclaw gateway restart`

**使用示例**:
```javascript
// 获取实时股价
const url = `https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey=${API_KEY}`;
const data = await web_fetch(url);
```

---

### CoinGecko（加密货币）

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 可用（免费） |
| **API Key** | 无需 |
| **文档** | https://www.coingecko.com/en/api/documentation |
| **用途** | 比特币、以太坊等加密货币价格 |

**使用示例**:
```javascript
// 获取加密货币价格（无需 Key）
const url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd,cny";
const data = await web_fetch(url);
// 返回：{"bitcoin": {"usd": 95234.5, "cny": 692345.2}, ...}
```

---

### 新浪财经（A 股行情）

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 可用（免费） |
| **API Key** | 无需 |
| **文档** | 无官方文档（公开接口） |
| **用途** | A 股、港股实时行情 |

**使用示例**:
```javascript
// 获取贵州茅台（600519）行情
const url = "http://hq.sinajs.cn/list=sh600519";
const data = await web_fetch(url);
// 返回：var hq_str_sh600519="贵州茅台，1680.00，1675.50，...";
```

---

### Exchangerate.host（外汇汇率）

| 属性 | 值 |
|------|-----|
| **状态** | ✅ 可用（免费） |
| **API Key** | 无需（基础功能） |
| **文档** | https://exchangerate.host/ |
| **用途** | 全球法币汇率 |

**使用示例**:
```javascript
// 获取 USD 对 CNY 汇率
const url = "https://api.exchangerate.host/latest?base=USD&target=CNY";
const data = await web_fetch(url);
```

---

## 数据源优先级

### 股票行情
```
Alpha Vantage（主） → 新浪财经（备用） → Tavily 搜索（兜底）
```

### 加密货币
```
CoinGecko（唯一，无需备用）
```

### 外汇汇率
```
Exchangerate.host（主） → 中国人民银行官网（备用）
```

### 财经新闻
```
Tavily（主） → 新浪财经/东方财富（备用）
```

---

## 配额管理

| API | 免费额度 | 建议调用频率 | 优化策略 |
|-----|---------|-------------|---------|
| Alpha Vantage | 25 次/天 | ≤ 2 次/小时 | 缓存热点股票（5 分钟） |
| CoinGecko | 10-50 次/分 | 按需使用 | 无需优化 |
| Tavily | 已配置额度 | 按需使用 | 复用搜索结果（30 分钟） |

---

## 缓存策略

| 数据类型 | 缓存时间 | 说明 |
|---------|---------|------|
| 热门股票价格 | 5 分钟 | 减少 API 调用 |
| 加密货币价格 | 1 分钟 | 波动较大 |
| 外汇汇率 | 1 小时 | 日内波动小 |
| 财经新闻 | 30 分钟 | 避免重复搜索 |

---

## 错误处理

### 降级策略

```javascript
async function getStockPrice(symbol) {
  try {
    // 主：Alpha Vantage
    return await alphaVantage(symbol);
  } catch (e) {
    try {
      // 备用：新浪财经
      return await sinaFinance(symbol);
    } catch (e2) {
      // 兜底：Tavily 搜索
      const news = await tavily(`${symbol} 最新股价`);
      return parsePriceFromNews(news);
    }
  }
}
```

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| API 返回空数据 | 股票代码错误 | 验证代码格式（sh600519 / sz000001） |
| 请求被限流 | 超过配额 | 等待后重试，增加缓存 |
| 网页抓取失败 | 反爬机制 | 更换数据源 |

---

## 安全建议

### API Key 管理

- ✅ 存储在 Gateway 环境变量
- ✅ 不提交到 Git 仓库
- ✅ 不在群聊中明文发送

### 隐私保护

- ✅ 不记录用户具体持仓
- ✅ 财务数据仅本地存储
- ✅ 不提供投资承诺，只做分析

---

## 更新日志

| 日期 | 变更内容 | 变更人 |
|------|---------|--------|
| 2026-03-09 | 初始版本，配置免费数据源方案 | 小黑 - 管家 |

---

## 相关文档

- [Alpha Vantage 文档](https://www.alphavantage.co/documentation/)
- [CoinGecko API](https://www.coingecko.com/en/api/documentation)
- [一人团队 Multi-Agent 系统设计](../../design/一人团队-Multi-Agent-系统设计.md)
- [Fin·财多多免费数据源配置方案](../../drafts/2026-03/2026-03-09-Fin·财多多免费数据源配置方案.md)
