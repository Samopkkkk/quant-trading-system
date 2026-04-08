# Webull OpenAPI MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

MCP Server for Webull OpenAPI — enables AI assistants (Cursor, Claude Desktop, Kiro, etc.) to securely access Webull trading and market data.

---

## ⚠️ Disclaimer

The information provided by this tool is for reference only and does not constitute investment advice. Trading involves risk; please make decisions carefully.

See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer.

---

## Features

- **Multi-Region Support** — US and HK regions with region-specific order types, trading sessions, and validation
- **Market Data** — Real-time snapshots, tick data, quotes (depth), footprint, and OHLCV bars for stocks, futures, crypto, and event contracts
- **Trading** — Place, modify, cancel orders for stocks, options, futures, crypto, and event contracts
- **Combo Orders** — OTO, OCO, OTOCO combo orders (US only)
- **Option Strategies** — Multi-leg option strategies: vertical, straddle, strangle, butterfly, condor, etc. (US only)
- **Algo Orders** — TWAP, VWAP, POV algorithmic orders (US only)
- **Risk Controls** — Market-specific notional limits (USD/HKD/CNH), quantity limits, symbol whitelist
- **Auto Account Resolution** — Automatically selects the correct account based on asset type (stock, futures, crypto, event)
- **Audit Logging** — All order operations are logged for compliance
- **2FA Support** — Interactive authentication flow for accounts with Two-Factor Authentication

---

## Example Prompts

Here are some prompts you can use with your AI assistant:

**Market Data**
- Show me AAPL's daily bars for the last 5 days
- Get a real-time snapshot for AAPL, MSFT, and GOOGL
- What's the current bid/ask for TSLA?
- Show me 1-minute tick data for NVDA

**Account & Portfolio**
- What's my account balance and buying power?
- Show me all my current positions
- List all my linked accounts

**Stock Trading**
- Place a limit order to buy 100 shares of AAPL at $250
- Place a market order to sell 50 shares of TSLA
- Preview a limit buy order for 200 shares of MSFT at $450 before placing it

**Options Trading**
- Buy 1 AAPL call option, strike $250, expiring 2026-04-17, limit price $5.00
- Buy 1 TSLA put option, strike $200, expiring 2026-05-15

**Order Management**
- Show me my order history for the last 7 days
- What are my current open orders?
- Cancel order with ID abc123

**HK Market**
- Place an enhanced limit order to buy 100 shares of Tencent (00700) at HKD 500
- Place an at-auction limit order for 200 shares of 00700 at HKD 510

---

## Prerequisites

1. **Webull Developer Account** — Register at:
   - US: [developer.webull.com](https://developer.webull.com/apis/home)
   - HK: [developer.webull.hk](https://developer.webull.hk/apis/home)
2. **API Credentials** — Obtain your `App Key` and `App Secret`
3. **Market Data Subscription** — Subscribe to quotes for market data access:
   - US: [webullapp.com/quote](https://www.webullapp.com/quote) | [Guide](https://developer.webull.com/apis/docs/market-data-api/subscribe-quotes)
   - HK: [webullapp.hk/quote](https://www.webullapp.hk/quote) | [Guide](https://developer.webull.hk/apis/docs/market-data-api/subscribe-quotes)
4. **Python 3.10+**
5. **uv** (recommended) — [Install guide](https://docs.astral.sh/uv/getting-started/installation/)

---

## Installation

### Option 1: uvx (Recommended)

```bash
uvx webull-openapi-mcp serve
```

### Option 2: pip

```bash
pip install webull-openapi-mcp
webull-openapi-mcp serve
```

### Option 3: Local Development

```bash
git clone https://github.com/webull-inc/webull-mcp-server.git
cd webull-mcp-server
uv sync
uv run python -m webull_openapi_mcp serve
```

---

## Quick Start

### 1. Initialize Configuration

```bash
webull-openapi-mcp init
```

Creates a `.env` file. Fill in your `WEBULL_APP_KEY` and `WEBULL_APP_SECRET`.

### 2. Authenticate

```bash
webull-openapi-mcp auth
```

For 2FA accounts: approve the request in your Webull mobile app. Token is valid for 15 days and auto-refreshes.

### 3. Start the Server

```bash
webull-openapi-mcp serve
```

---

## Client Configuration

### Kiro / Cursor / Claude Desktop

Add to your MCP configuration:

**Using environment variables:**

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
        "WEBULL_ENVIRONMENT": "prod"
      }
    }
  }
}
```

**Using .env file (local development):**

```json
{
  "mcpServers": {
    "webull": {
      "command": "uv",
      "args": [
        "run", "--directory", "/path/to/webull-mcp-server",
        "python", "-m", "webull_openapi_mcp", "serve",
        "--env-file", "/path/to/.env"
      ]
    }
  }
}
```

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `WEBULL_APP_KEY` | App Key (required) | — |
| `WEBULL_APP_SECRET` | App Secret (required) | — |
| `WEBULL_ENVIRONMENT` | `uat` (sandbox) or `prod` | `uat` |
| `WEBULL_REGION_ID` | `us` or `hk` | `us` |
| `WEBULL_TOOLSETS` | Enabled tool categories (comma-separated) | (all enabled) |
| `WEBULL_MAX_ORDER_NOTIONAL_USD` | Max order value for US market (USD) | `10000` |
| `WEBULL_MAX_ORDER_NOTIONAL_HKD` | Max order value for HK market (HKD) | `80000` |
| `WEBULL_MAX_ORDER_NOTIONAL_CNH` | Max order value for CN market (CNH) | `70000` |
| `WEBULL_MAX_ORDER_QUANTITY` | Max order quantity | `1000` |
| `WEBULL_SYMBOL_WHITELIST` | Allowed symbols (comma-separated) | (no restriction) |
| `WEBULL_TOKEN_DIR` | Token storage directory | `./conf/` |
| `WEBULL_AUDIT_LOG_FILE` | Audit log file path | stderr only |
| `WEBULL_LOG_LEVEL` | SDK log level | `WARNING` |

> **Note:** `WEBULL_REGION_ID=us` represents **Webull US** ([developer.webull.com](https://developer.webull.com/apis/home)), and `WEBULL_REGION_ID=hk` represents **Webull Hong Kong** ([developer.webull.hk](https://developer.webull.hk/apis/home)).

See [.env.example](.env.example) for full configuration template.

---

## Available Tools

### Market Data

| Category | Tools | Region |
|----------|-------|--------|
| **Stock** | `get_stock_tick`, `get_stock_snapshot`, `get_stock_quotes`, `get_stock_footprint`, `get_stock_bars`, `get_stock_bars_single` | US, HK |
| **Futures** | `get_futures_tick`, `get_futures_snapshot`, `get_futures_depth`, `get_futures_bars`, `get_futures_footprint` | US |
| **Crypto** | `get_crypto_snapshot`, `get_crypto_bars` | US |
| **Event** | `get_event_tick`, `get_event_snapshot`, `get_event_depth`, `get_event_bars` | US |

### Trading

| Category | Tools | Region |
|----------|-------|--------|
| **Account** | `get_account_list` | US, HK |
| **Assets** | `get_account_balance`, `get_account_positions` | US, HK |
| **Instrument** | `get_instruments`, `get_futures_instruments`, `get_futures_products`, `get_crypto_instruments`, `get_event_series`, `get_event_instruments`, `get_event_categories`, `get_event_events` | varies |
| **Stock Order** | `place_stock_order`, `preview_stock_order`, `replace_stock_order` | US, HK |
| **Combo Order** | `place_stock_combo_order` (OTO/OCO/OTOCO) | US |
| **Option Order** | `place_option_single_order`, `preview_option_order`, `replace_option_order` | US, HK |
| **Option Strategy** | `place_option_strategy_order` | US |
| **Algo Order** | `place_algo_order` (TWAP/VWAP/POV) | US |
| **Futures Order** | `place_futures_order`, `replace_futures_order` | US |
| **Crypto Order** | `place_crypto_order` | US |
| **Event Order** | `place_event_order`, `replace_event_order` | US |
| **Order** | `cancel_order`, `get_order_history`, `get_open_orders`, `get_order_detail` | US, HK |

### Region Differences

| Feature | US | HK |
|---------|----|----|
| Stock/Option Trading | ✅ | ✅ |
| Futures Trading | ✅ | ❌ |
| Crypto Trading | ✅ | ❌ |
| Event Contracts | ✅ | ❌ |
| Combo Orders | ✅ | ❌ |
| Option Strategies | ✅ | ❌ |
| Algo Orders | ✅ | ❌ |
| Markets | US | US, HK, CN |
| Order Types | LIMIT, MARKET, STOP_LOSS, STOP_LOSS_LIMIT, TRAILING_STOP_LOSS, etc. | LIMIT, MARKET, ENHANCED_LIMIT, AT_AUCTION, AT_AUCTION_LIMIT, etc. |

---

## CLI Commands

```bash
webull-openapi-mcp --version    # Show version
webull-openapi-mcp init         # Initialize .env configuration
webull-openapi-mcp auth         # Authenticate (2FA accounts)
webull-openapi-mcp serve        # Start MCP server
webull-openapi-mcp status       # Show configuration status
webull-openapi-mcp tools        # List available tools
```

---

## Security

- **Never share your AK/SK with AI models** — Do not paste your App Key or App Secret into chat prompts, AI assistants, or any LLM conversation. These credentials should only be configured via environment variables or `.env` files, never exposed in plain text to the model.
- **Prefer `env` over `.env` files** — Pass credentials via the MCP client's `env` field (in `mcp.json`) rather than a `.env` file in your workspace. The `env` field injects credentials as process environment variables, which the AI model cannot access. A `.env` file in your workspace could be read by the AI assistant through IDE file access.
- **Credential isolation** — AK/SK are used only inside the MCP server process for SDK initialization and request signing. They never appear in tool outputs, logs, or error messages.
- **Review before trading** — Always review order details proposed by the AI before confirming. Use `preview_stock_order` / `preview_option_order` before placing orders.
- **Use toolset filtering** — Set `WEBULL_TOOLSETS=account,market-data` to disable trading tools entirely if you only need read-only access.
- **Default sandbox** — The server defaults to UAT (sandbox) environment. You must explicitly set `WEBULL_ENVIRONMENT=prod` for live trading.
- **Dependency security** — `fastmcp` is pinned to version `2.0.0`. Users are responsible for monitoring and updating third-party dependencies for security patches. Review release notes before upgrading.

---

## Troubleshooting

### 2FA Authentication Required

```bash
webull-openapi-mcp auth    # Approve in Webull app
webull-openapi-mcp serve   # Then start server
```

### Device Not Registered

1. Open Webull mobile app → log in with your API account → complete device registration
2. Run `webull-openapi-mcp auth`

### Market Data 401/403

Subscribe to quotes:
- HK: [webullapp.hk/quote](https://www.webullapp.hk/quote) | [Guide](https://developer.webull.hk/apis/docs/market-data-api/subscribe-quotes)
- US: [webullapp.com/quote](https://www.webullapp.com/quote) | [Guide](https://developer.webull.com/apis/docs/market-data-api/subscribe-quotes)

### Token Expired

```bash
rm -rf ./conf/token.txt
webull-openapi-mcp auth
```

---

## Project Structure

```
webull-mcp-server/
├── webull_openapi_mcp/
│   ├── cli.py              # CLI commands
│   ├── server.py           # MCP server
│   ├── sdk_client.py       # Webull SDK adapter
│   ├── config.py           # Configuration management
│   ├── region_config.py    # Region-specific settings
│   ├── guards.py           # Order validation
│   ├── audit.py            # Audit logging
│   ├── errors.py           # Error handling
│   ├── formatters.py       # Response formatting
│   ├── constants.py        # Enum constants
│   └── tools/
│       ├── market_data/    # Stock, futures, crypto, event market data
│       └── trading/        # Account, order, instrument tools
├── tests/                  # Unit & property-based tests
├── conf/                   # Token storage
├── .env.example            # Configuration template
├── DISCLAIMER.md           # Full disclaimer
└── pyproject.toml          # Package configuration
```

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
