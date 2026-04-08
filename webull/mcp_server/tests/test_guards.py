"""Unit tests for guards.py — OrderValidator class."""

from __future__ import annotations

import pytest

from webull_openapi_mcp.config import ServerConfig
from webull_openapi_mcp.errors import (
    FeatureNotSupportedError,
    RegionValidationError,
    ValidationError,
)
from webull_openapi_mcp.guards import OrderValidator
from webull_openapi_mcp.region_config import US_REGION_CONFIG, HK_REGION_CONFIG


def _config(**overrides) -> ServerConfig:
    """Helper to build a ServerConfig with sensible defaults."""
    defaults = dict(
        app_key="test_key",
        app_secret="test_secret",
        region_id="us",
        max_order_notional_usd=10_000.0,
        max_order_notional_hkd=80_000.0,
        max_order_notional_cnh=70_000.0,
        max_order_quantity=1_000.0,
    )
    defaults.update(overrides)
    return ServerConfig(**defaults)


def _us_validator(**config_overrides) -> OrderValidator:
    """Create a US region validator."""
    return OrderValidator(US_REGION_CONFIG, _config(**config_overrides))


def _hk_validator(**config_overrides) -> OrderValidator:
    """Create a HK region validator."""
    return OrderValidator(HK_REGION_CONFIG, _config(region_id="hk", **config_overrides))


def _valid_stock_params(**overrides) -> dict:
    """Return a minimal valid stock order params dict."""
    base = dict(
        symbol="AAPL",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        time_in_force="DAY",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Side Validation
# ---------------------------------------------------------------------------

class TestSideValidation:
    def test_valid_buy(self):
        _us_validator().validate_stock_order(_valid_stock_params(side="BUY"))

    def test_valid_sell(self):
        _us_validator().validate_stock_order(_valid_stock_params(side="SELL"))

    def test_invalid_side(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_stock_order(_valid_stock_params(side="INVALID"))
        assert exc_info.value.field == "side"


# ---------------------------------------------------------------------------
# Order Type Validation (Region-Specific)
# ---------------------------------------------------------------------------

class TestOrderTypeValidation:
    @pytest.mark.parametrize("ot", ["MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_LIMIT", "TRAILING_STOP_LOSS"])
    def test_us_valid_order_types(self, ot):
        params = _valid_stock_params(order_type=ot)
        if ot == "LIMIT":
            params["limit_price"] = 100.0
        elif ot == "STOP_LOSS":
            params["stop_price"] = 100.0
        elif ot == "STOP_LOSS_LIMIT":
            params["limit_price"] = 100.0
            params["stop_price"] = 95.0
        _us_validator().validate_stock_order(params)

    @pytest.mark.parametrize("ot", ["MARKET", "LIMIT", "ENHANCED_LIMIT", "AT_AUCTION"])
    def test_hk_valid_order_types(self, ot):
        params = _valid_stock_params(order_type=ot, time_in_force="DAY")
        if ot == "LIMIT" or ot == "ENHANCED_LIMIT":
            params["limit_price"] = 100.0
        _hk_validator().validate_stock_order(params)

    def test_us_invalid_order_type(self):
        with pytest.raises(RegionValidationError) as exc_info:
            _us_validator().validate_stock_order(_valid_stock_params(order_type="ENHANCED_LIMIT"))
        assert "order_type" in str(exc_info.value)

    def test_hk_invalid_order_type(self):
        with pytest.raises(RegionValidationError) as exc_info:
            _hk_validator().validate_stock_order(_valid_stock_params(order_type="TRAILING_STOP_LOSS"))
        assert "order_type" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Time-in-Force Validation (Region-Specific)
# ---------------------------------------------------------------------------

class TestTimeInForceValidation:
    @pytest.mark.parametrize("tif", ["DAY", "GTC", "IOC"])
    def test_us_valid_tif(self, tif):
        _us_validator().validate_stock_order(_valid_stock_params(time_in_force=tif))

    @pytest.mark.parametrize("tif", ["DAY", "GTC", "GTD"])
    def test_hk_valid_tif(self, tif):
        _hk_validator().validate_stock_order(_valid_stock_params(time_in_force=tif))

    def test_us_invalid_tif(self):
        with pytest.raises(RegionValidationError):
            _us_validator().validate_stock_order(_valid_stock_params(time_in_force="GTD"))

    def test_hk_invalid_tif(self):
        with pytest.raises(RegionValidationError):
            _hk_validator().validate_stock_order(_valid_stock_params(time_in_force="IOC"))


# ---------------------------------------------------------------------------
# Trading Session Validation (Region-Specific)
# ---------------------------------------------------------------------------

class TestTradingSessionValidation:
    @pytest.mark.parametrize("sess", ["ALL", "CORE", "NIGHT"])
    def test_us_valid_sessions(self, sess):
        _us_validator().validate_stock_order(_valid_stock_params(trading_session=sess))

    @pytest.mark.parametrize("sess", ["ALL", "CORE", "NIGHT", "ALL_DAY"])
    def test_hk_valid_sessions(self, sess):
        _hk_validator().validate_stock_order(_valid_stock_params(trading_session=sess))

    def test_none_session_is_ok(self):
        _us_validator().validate_stock_order(_valid_stock_params())

    def test_us_invalid_session(self):
        with pytest.raises(RegionValidationError):
            _us_validator().validate_stock_order(_valid_stock_params(trading_session="ALL_DAY"))


# ---------------------------------------------------------------------------
# Quantity Validation
# ---------------------------------------------------------------------------

class TestQuantityValidation:
    def test_zero_quantity(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_stock_order(_valid_stock_params(quantity=0))
        assert exc_info.value.field == "quantity"

    def test_negative_quantity(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_stock_order(_valid_stock_params(quantity=-5))
        assert exc_info.value.field == "quantity"

    def test_exceeds_max_quantity(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator(max_order_quantity=1000).validate_stock_order(
                _valid_stock_params(quantity=1001)
            )
        assert exc_info.value.field == "quantity"

    def test_at_max_quantity(self):
        _us_validator(max_order_quantity=1000).validate_stock_order(
            _valid_stock_params(quantity=1000)
        )


# ---------------------------------------------------------------------------
# Notional Value Validation
# ---------------------------------------------------------------------------

class TestNotionalValueValidation:
    def test_notional_exceeded_us_market(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator(max_order_notional_usd=10_000.0).validate_stock_order(
                _valid_stock_params(quantity=200, limit_price=60.0, order_type="LIMIT", market="US")
            )
        assert exc_info.value.field == "notional"

    def test_notional_ok_us_market(self):
        _us_validator(max_order_notional_usd=10_000.0).validate_stock_order(
            _valid_stock_params(quantity=100, limit_price=99.0, order_type="LIMIT", market="US")
        )

    def test_notional_exceeded_hk_market(self):
        with pytest.raises(ValidationError) as exc_info:
            _hk_validator(max_order_notional_hkd=80_000.0).validate_stock_order(
                _valid_stock_params(quantity=200, limit_price=500.0, order_type="LIMIT", market="HK")
            )
        assert exc_info.value.field == "notional"

    def test_notional_ok_hk_market(self):
        _hk_validator(max_order_notional_hkd=80_000.0).validate_stock_order(
            _valid_stock_params(quantity=100, limit_price=500.0, order_type="LIMIT", market="HK")
        )

    def test_notional_exceeded_cn_market(self):
        with pytest.raises(ValidationError) as exc_info:
            _hk_validator(max_order_notional_cnh=70_000.0).validate_stock_order(
                _valid_stock_params(quantity=200, limit_price=400.0, order_type="LIMIT", market="CN")
            )
        assert exc_info.value.field == "notional"

    def test_notional_ok_cn_market(self):
        _hk_validator(max_order_notional_cnh=70_000.0).validate_stock_order(
            _valid_stock_params(quantity=100, limit_price=500.0, order_type="LIMIT", market="CN")
        )


# ---------------------------------------------------------------------------
# Price Field Validation
# ---------------------------------------------------------------------------

class TestPriceFieldValidation:
    def test_limit_missing_price(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_stock_order(_valid_stock_params(order_type="LIMIT"))
        assert exc_info.value.field == "limit_price"

    def test_stop_loss_missing_stop_price(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_stock_order(_valid_stock_params(order_type="STOP_LOSS"))
        assert exc_info.value.field == "stop_price"

    def test_stop_loss_limit_missing_price(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_stock_order(
                _valid_stock_params(order_type="STOP_LOSS_LIMIT", stop_price=90.0)
            )
        assert exc_info.value.field == "limit_price"

    def test_stop_loss_limit_missing_stop_price(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_stock_order(
                _valid_stock_params(order_type="STOP_LOSS_LIMIT", limit_price=100.0)
            )
        assert exc_info.value.field == "stop_price"


# ---------------------------------------------------------------------------
# Symbol Whitelist
# ---------------------------------------------------------------------------

class TestSymbolWhitelist:
    def test_whitelist_allows_symbol(self):
        _us_validator(symbol_whitelist=["AAPL", "GOOG"]).validate_stock_order(
            _valid_stock_params(symbol="AAPL")
        )

    def test_whitelist_rejects_symbol(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator(symbol_whitelist=["AAPL", "GOOG"]).validate_stock_order(
                _valid_stock_params(symbol="TSLA")
            )
        assert exc_info.value.field == "symbol"

    def test_no_whitelist_allows_any(self):
        _us_validator(symbol_whitelist=None).validate_stock_order(
            _valid_stock_params(symbol="ANYTHING")
        )


# ---------------------------------------------------------------------------
# Combo Order Validation (US Only)
# ---------------------------------------------------------------------------

class TestComboOrderValidation:
    def test_us_combo_order_allowed(self):
        _us_validator().validate_combo_order({
            "combo_type": "OTO",
            "orders": [
                {"symbol": "AAPL", "side": "BUY", "order_type": "LIMIT", "quantity": 10},
                {"symbol": "AAPL", "side": "SELL", "order_type": "LIMIT", "quantity": 10},
            ]
        })

    def test_hk_combo_order_rejected(self):
        with pytest.raises(FeatureNotSupportedError):
            _hk_validator().validate_combo_order({
                "combo_type": "OTO",
                "orders": []
            })

    def test_invalid_combo_type(self):
        with pytest.raises(RegionValidationError):
            _us_validator().validate_combo_order({
                "combo_type": "INVALID",
                "orders": []
            })


# ---------------------------------------------------------------------------
# Option Order Validation
# ---------------------------------------------------------------------------

def _valid_option_params(**overrides) -> dict:
    """Return a minimal valid option order params dict."""
    base = dict(
        side="BUY",
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=5.00,
    )
    base.update(overrides)
    return base


class TestOptionOrderValidation:
    @pytest.mark.parametrize("ot", ["LIMIT", "STOP_LOSS", "STOP_LOSS_LIMIT"])
    def test_valid_option_order_types(self, ot):
        params = _valid_option_params(order_type=ot)
        if ot in ("STOP_LOSS", "STOP_LOSS_LIMIT"):
            params["stop_price"] = 4.50
        _us_validator().validate_option_order(params)

    def test_market_accepted(self):
        # MARKET is valid for US options
        _us_validator().validate_option_order(_valid_option_params(order_type="MARKET"))

    def test_invalid_order_type(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_order(_valid_option_params(order_type="FOO"))
        assert exc_info.value.field == "order_type"


class TestOptionTifValidation:
    @pytest.mark.parametrize("tif", ["DAY", "GTC"])
    def test_valid_option_tif(self, tif):
        _us_validator().validate_option_order(_valid_option_params(time_in_force=tif))

    def test_ioc_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_order(_valid_option_params(time_in_force="IOC"))
        assert exc_info.value.field == "time_in_force"


class TestOptionPriceFieldValidation:
    def test_limit_missing_limit_price(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_order(_valid_option_params(limit_price=None))
        assert exc_info.value.field == "limit_price"

    def test_stop_loss_missing_stop_price(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_order(
                _valid_option_params(order_type="STOP_LOSS", stop_price=None)
            )
        assert exc_info.value.field == "stop_price"


# ---------------------------------------------------------------------------
# Option Strategy Order Validation (US Only)
# ---------------------------------------------------------------------------

def _make_leg(**overrides) -> dict:
    """Return a single valid option leg dict."""
    base = {
        "symbol": "AAPL230120C00150000",
        "side": "BUY",
        "quantity": 1,
        "option_type": "CALL",
        "strike_price": 150.0,
        "option_expire_date": "2023-01-20",
    }
    base.update(overrides)
    return base


def _valid_strategy_params(**overrides) -> dict:
    """Return a minimal valid option strategy order params dict."""
    base = dict(
        strategy="SINGLE",
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=5.00,
        legs=[_make_leg()],
    )
    base.update(overrides)
    return base


class TestOptionStrategyValidation:
    def test_us_strategy_allowed(self):
        _us_validator().validate_option_strategy_order(
            _valid_strategy_params(strategy="VERTICAL", legs=[_make_leg(), _make_leg()])
        )

    def test_hk_strategy_rejected(self):
        with pytest.raises(FeatureNotSupportedError):
            _hk_validator().validate_option_strategy_order(
                _valid_strategy_params(strategy="VERTICAL", legs=[_make_leg(), _make_leg()])
            )

    def test_single_always_allowed(self):
        # SINGLE strategy should work in both regions
        _us_validator().validate_option_strategy_order(_valid_strategy_params(strategy="SINGLE"))
        _hk_validator().validate_option_strategy_order(_valid_strategy_params(strategy="SINGLE"))


class TestOptionLegCountValidation:
    def test_single_one_leg_ok(self):
        _us_validator().validate_option_strategy_order(_valid_strategy_params(strategy="SINGLE"))

    def test_single_two_legs_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_strategy_order(
                _valid_strategy_params(strategy="SINGLE", legs=[_make_leg(), _make_leg()])
            )
        assert exc_info.value.field == "legs"

    def test_vertical_two_legs_ok(self):
        _us_validator().validate_option_strategy_order(
            _valid_strategy_params(strategy="VERTICAL", legs=[_make_leg(), _make_leg()])
        )

    def test_vertical_one_leg_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_strategy_order(
                _valid_strategy_params(strategy="VERTICAL", legs=[_make_leg()])
            )
        assert exc_info.value.field == "legs"

    def test_butterfly_three_legs_ok(self):
        _us_validator().validate_option_strategy_order(
            _valid_strategy_params(strategy="BUTTERFLY", legs=[_make_leg()] * 3)
        )

    def test_butterfly_four_legs_ok(self):
        _us_validator().validate_option_strategy_order(
            _valid_strategy_params(strategy="BUTTERFLY", legs=[_make_leg()] * 4)
        )

    def test_condor_four_legs_ok(self):
        _us_validator().validate_option_strategy_order(
            _valid_strategy_params(strategy="CONDOR", legs=[_make_leg()] * 4)
        )

    def test_zero_legs_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_strategy_order(
                _valid_strategy_params(strategy="SINGLE", legs=[])
            )
        assert exc_info.value.field == "legs"


class TestOptionLegFieldCompleteness:
    def test_complete_leg_ok(self):
        _us_validator().validate_option_strategy_order(_valid_strategy_params())

    def test_leg_missing_symbol(self):
        leg = _make_leg()
        del leg["symbol"]
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_strategy_order(_valid_strategy_params(legs=[leg]))
        assert exc_info.value.field == "legs"
        assert "symbol" in exc_info.value.message

    def test_leg_missing_multiple_fields(self):
        leg = {"symbol": "X", "side": "BUY"}
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_option_strategy_order(_valid_strategy_params(legs=[leg]))
        assert exc_info.value.field == "legs"


# ---------------------------------------------------------------------------
# Algo Order Validation (US Only)
# ---------------------------------------------------------------------------

class TestAlgoOrderValidation:
    def test_us_algo_order_allowed(self):
        _us_validator().validate_algo_order({
            "side": "BUY",
            "quantity": 100,
            "algo_type": "TWAP",
        })

    def test_hk_algo_order_rejected(self):
        with pytest.raises(FeatureNotSupportedError):
            _hk_validator().validate_algo_order({
                "side": "BUY",
                "quantity": 100,
                "algo_type": "TWAP",
            })

    def test_pov_requires_target_vol_percent(self):
        with pytest.raises(ValidationError) as exc_info:
            _us_validator().validate_algo_order({
                "side": "BUY",
                "quantity": 100,
                "algo_type": "POV",
            })
        assert exc_info.value.field == "target_vol_percent"

    def test_pov_with_target_vol_percent_ok(self):
        _us_validator().validate_algo_order({
            "side": "BUY",
            "quantity": 100,
            "algo_type": "POV",
            "target_vol_percent": 0.1,
        })


# ---------------------------------------------------------------------------
# BCAN Validation (HK Only)
# ---------------------------------------------------------------------------

class TestBCANValidation:
    def test_hk_bcan_optional(self):
        _hk_validator().validate_stock_order(_valid_stock_params())

    def test_hk_bcan_valid(self):
        _hk_validator().validate_stock_order(_valid_stock_params(
            no_party_ids=[{"party_id": "123", "party_id_source": "BCAN"}]
        ))

    def test_hk_bcan_invalid_format(self):
        with pytest.raises(ValidationError) as exc_info:
            _hk_validator().validate_stock_order(_valid_stock_params(
                no_party_ids="invalid"
            ))
        assert exc_info.value.field == "no_party_ids"

    def test_hk_bcan_missing_party_id(self):
        with pytest.raises(ValidationError) as exc_info:
            _hk_validator().validate_stock_order(_valid_stock_params(
                no_party_ids=[{"party_id_source": "BCAN"}]
            ))
        assert exc_info.value.field == "no_party_ids"

    def test_us_ignores_bcan(self):
        # US region should not validate BCAN
        _us_validator().validate_stock_order(_valid_stock_params(
            no_party_ids=[{"party_id": "123", "party_id_source": "BCAN"}]
        ))
