"""whale-watch-tg — Telegram whale tracker with AI summaries.

Subscribe to any wallet address and get instant Telegram alerts with an LLM
summary of the flow ("3,000 ETH to Binance — likely sell pressure").
"""

__version__ = "0.1.0"

DEMO_CHAT_ID = 0  # synthetic chat used by the keyless demo

DEFAULT_RPC_URL = "https://ethereum-rpc.publicnode.com"
DEFAULT_MAX_ALERTS_PER_HOUR = 10
DEFAULT_MIN_ALERT_GAP_SECONDS = 5