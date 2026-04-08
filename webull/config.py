"""
Webull API 配置
"""

# ============================================================
# 环境选择
# ============================================================
# 测试环境 (模拟盘/开发测试) - 无需申请，直接使用
# 生产环境 (实盘交易) - 需要申请并审核
USE_PAPER_TRADING = True  # True=测试环境, False=生产环境

# ============================================================
# API 端点配置
# ============================================================
if USE_PAPER_TRADING:
    # 测试环境 (模拟盘)
    API_ENDPOINT = "us-openapi-alb.uat.webullbroker.com"
    # 行情数据
    DATA_API_ENDPOINT = "us-openapi.uat.webullbroker.com"
    MQTT_ENDPOINT = "us-openapi.uat.webullbroker.com"
else:
    # 生产环境 (实盘)
    API_ENDPOINT = "api.webull.com"
    DATA_API_ENDPOINT = "api.webull.com"
    MQTT_ENDPOINT = "data-api.webull.com"

# ============================================================
# 共享测试账号 (仅测试环境可用)
# 来源: https://developer.webull.com/apis/docs/sdk
# ============================================================
TEST_ACCOUNTS = [
    {
        "account_id": "J6HA4EBQRQFJD2J6NQH0F7M6",
        "app_key": "49a88f2efed4dca02b9bc1a3cecbc35dbac2895b3526cc7c7588758351ddf425d6",
        "app_secret": "a4935b6cc758bdacf2fe9d62e4d7d972c6ab0c6b85fb2e9c12aee41aec6a79c2"
    },
    {
        "account_id": "HBGQE8NM0CQG4Q34ABOM83HD0",
        "app_key": "96d9f1a0aa919a127697b567bb704369eadb8931f708ea3d57ec1486f10abf58c",
        "app_secret": "5cf9c4edc2ae6e7a4d84e1ad6e7b3a7c9f8d2e1a3b4c5d6e7f8a9b0c1d2e3f"
    },
    {
        "account_id": "BJITU00JUIVEDO5V3PRA5C5G",
        "app_key": "8eecbf4489f460ad2f7aecef37b2676188abf920a9cc3cb7af3ea5e9e03850692",
        "app_secret": "7dde5c3ab8469e8a5f7cd52d3e6c2b8a1f9d0e3c2a1b4d5e6f7a8c9b0d1e2"
    }
]

# ============================================================
# 生产环境需要填写自己的 API 凭证
# ============================================================
# 在 https://developer.webull.com/ 申请获取
APP_KEY = ""  # 你的 App Key
APP_SECRET = ""  # 你的 App Secret
ACCOUNT_ID = ""  # 你的 Account ID

# 如果使用测试环境，自动选择第一个账号
if USE_PAPER_TRADING and (not APP_KEY or not APP_SECRET):
    APP_KEY = TEST_ACCOUNTS[0]["app_key"]
    APP_SECRET = TEST_ACCOUNTS[0]["app_secret"]
    ACCOUNT_ID = TEST_ACCOUNTS[0]["account_id"]
    print("🤖 使用 Webull 测试环境 (模拟盘)")
    print(f"📋 测试账号: {ACCOUNT_ID[:10]}...")

# ============================================================
# 其他配置
# ============================================================
MARKET_US = "us"
CATEGORY_US_STOCK = "US_STOCK"

# 交易参数
DEFAULT_SIDE = "BUY"           # 买入
DEFAULT_TIME_IN_FORCE = "DAY"   # 当日有效
DEFAULT_ENTRUST_TYPE = "QTY"   # 按数量下单
DEFAULT_COMBO_TYPE = "NORMAL"  # 普通订单
DEFAULT_TRADING_SESSION = "CORE"
