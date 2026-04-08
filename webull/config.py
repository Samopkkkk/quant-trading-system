"""
Webull API 配置
"""

# 替换为你自己的 App Key 和 App Secret
# 在 https://developer.webull.com/ 注册应用获取
APP_KEY = "your_app_key"
APP_SECRET = "your_app_secret"

# API 端点
# 测试环境
API_ENDPOINT = "us-openapi.uat.webullbroker.com"
# 生产环境
# API_ENDPOINT = "us-openapi.webullbroker.com"

# 行情数据 MQTT 端点
DATA_API_ENDPOINT = "us-openapi.uat.webullbroker.com"
MQTT_ENDPOINT = "us-openapi.uat.webullbroker.com"

# 市场类型
MARKET_US = "us"
CATEGORY_US_STOCK = "US_STOCK"

# 交易参数
DEFAULT_SIDE = "BUY"           # 买入
DEFAULT_TIME_IN_FORCE = "DAY"   # 当日有效
DEFAULT_ENTRUST_TYPE = "QTY"   # 按数量下单
DEFAULT_COMBO_TYPE = "NORMAL"  # 普通订单
DEFAULT_TRADING_SESSION = "CORE"
