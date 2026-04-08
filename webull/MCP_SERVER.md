# Webull MCP Server 集成

官方 Webull MCP Server，支持 AI 助手（Cursor、Claude Desktop、Kiro 等）直接调用 Webull 交易和行情数据。

**仓库**: https://github.com/webull-inc/webull-mcp-server

## 功能特性

| 类别 | 功能 |
|------|------|
| **行情数据** | 实时快照、Tick数据、报价、K线 |
| **交易** | 股票、期权、期货、加密货币、事件合约 |
| **组合订单** | OTO、OCO、OTOCO 组合订单 |
| **期权策略** | 垂直价差、跨式、价差、蝴蝶、秃鹰 |
| **算法订单** | TWAP、VWAP、POV |
| **多区域** | US 美股、HK 港股 |

## 快速开始

### 1. 安装

```bash
# 推荐使用 uvx
uvx webull-openapi-mcp serve

# 或使用 pip
pip install webull-openapi-mcp
webull-openapi-mcp serve
```

### 2. 初始化配置

```bash
webull-openapi-mcp init
# 会在当前目录创建 .env 文件
```

编辑 `.env`:

```env
WEBULL_APP_KEY=your_app_key
WEBULL_APP_SECRET=your_app_secret
WEBULL_REGION_ID=us
WEBULL_ENVIRONMENT=uat  # uat=测试环境, prod=生产环境
```

### 3. 认证

```bash
webull-openapi-mcp auth
# 如果是 2FA 账户，需要在 Webull 手机App批准
```

### 4. 启动服务

```bash
webull-openapi-mcp serve
```

## MCP 客户端配置

### Cursor / Kiro / Claude Desktop

在 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "webull": {
      "command": "uvx",
      "args": ["webull-openapi-mcp", "serve"],
      "env": {
        "WEBULL_APP_KEY": "your_app_key",
        "WEBULL_APP_SECRET": "your_app_secret",
        "WEBULL_REGION_ID": "us",
        "WEBULL_ENVIRONMENT": "uat"
      }
    }
  }
}
```

## 可用工具

### 行情数据

| 工具 | 描述 |
|------|------|
| `get_stock_tick` | 股票Tick数据 |
| `get_stock_snapshot` | 股票实时快照 |
| `get_stock_quotes` | 股票报价(深度) |
| `get_stock_bars` | 股票K线 |
| `get_stock_footprint` | 股票筹码分布 |

### 交易

| 工具 | 描述 |
|------|------|
| `get_account_list` | 获取账户列表 |
| `get_account_balance` | 获取账户余额 |
| `get_account_positions` | 获取持仓 |
| `place_stock_order` | 股票下单 |
| `place_option_single_order` | 期权下单 |
| `cancel_order` | 撤单 |
| `get_order_history` | 订单历史 |

## 示例 prompts

**市场数据**
- "Show me AAPL's daily bars for the last 5 days"
- "Get a real-time snapshot for AAPL, MSFT, and GOOGL"
- "What's the current bid/ask for TSLA?"

**账户**
- "What's my account balance and buying power?"
- "Show me all my current positions"

**交易**
- "Place a limit order to buy 100 shares of AAPL at $250"
- "Place a market order to sell 50 shares of TSLA"
- "Preview a limit buy order for 200 shares of MSFT at $450"

## 环境配置

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `WEBULL_APP_KEY` | App Key | - |
| `WEBULL_APP_SECRET` | App Secret | - |
| `WEBULL_ENVIRONMENT` | `uat` 或 `prod` | `uat` |
| `WEBULL_REGION_ID` | `us` 或 `hk` | `us` |
| `WEBULL_MAX_ORDER_NOTIONAL_USD` | 美股最大订单金额 | 10000 USD |
| `WEBULL_MAX_ORDER_QUANTITY` | 最大订单数量 | 1000 |

## 安全建议

1. **不要在聊天中分享 AK/SK** — 凭证只通过环境变量或 .env 文件配置
2. **使用 `env` 而非 `.env`** — 通过 MCP 客户端的 env 字段注入凭证
3. **默认使用测试环境** — `WEBULL_ENVIRONMENT=uat`
4. **下单前预览** — 使用 `preview_stock_order` 确认订单详情

## CLI 命令

```bash
webull-openapi-mcp --version    # 显示版本
webull-openapi-mcp init         # 初始化配置
webull-openapi-mcp auth         # 认证
webull-openapi-mcp serve        # 启动服务
webull-openapi-mcp status       # 显示状态
webull-openapi-mcp tools        # 列出可用工具
```

## 与本项目的关系

- **本项目** (`webull/`) — Python 量化交易框架，适合策略开发和自动化交易
- **MCP Server** — AI 助手集成，通过自然语言调用 Webull API

两者可以结合使用：
1. 用 MCP Server 进行快速查询和简单交易
2. 用本项目的框架开发复杂的量化策略
