from .base import PriceProvider


def get_provider(name: str = "yfinance") -> PriceProvider:
    """按名字返回数据源。以后加 Tiingo/Polygon 就在这里注册。"""
    if name == "yfinance":
        from .yfinance_provider import YFinanceProvider

        return YFinanceProvider()
    raise ValueError(f"未知数据源: {name}")
