"""
StockSense AI - Demand Forecasting Engine Unit Tests
"""

from datetime import date, timedelta
import pandas as pd
from app.forecasting.engine import (
    aggregate_daily_sales,
    moving_average_forecast,
    holt_winters_forecast,
    forecast_product,
)


def test_aggregate_daily_sales():
    today = date.today()
    sales_data = [
        {"date": today - timedelta(days=2), "quantity": 5},
        {"date": today - timedelta(days=2), "quantity": 3},
        {"date": today - timedelta(days=1), "quantity": 4},
    ]

    series = aggregate_daily_sales(sales_data, start_date=today - timedelta(days=2), end_date=today)
    assert len(series) == 3
    assert series.iloc[0] == 8.0  # 5 + 3
    assert series.iloc[1] == 4.0
    assert series.iloc[2] == 0.0  # zero-filled


def test_moving_average_forecast():
    # 14 days of constant 10 units/day
    demand = pd.Series([10.0] * 14)
    preds, mae, std = moving_average_forecast(demand, horizon=5, window=7)

    assert len(preds) == 5
    assert all(p == 10.0 for p in preds)
    assert mae == 0.0
    assert std == 0.0


def test_forecast_product_fallback_zero():
    forecast = forecast_product(product_id=1, sales_data=[], horizon=7)
    assert forecast.product_id == 1
    assert forecast.model_used == "fallback_zero"
    assert forecast.confidence == "LOW"
    assert len(forecast.forecasts) == 7
    assert all(f["predicted_demand"] == 0.0 for f in forecast.forecasts)


def test_forecast_product_with_history():
    today = date.today()
    # 40 days of linear and noisy demand
    sales = []
    for i in range(40, 0, -1):
        d = today - timedelta(days=i)
        sales.append({"date": d, "quantity": 10 + (i % 3)})

    forecast = forecast_product(product_id=99, sales_data=sales, horizon=7, today=today)
    assert forecast.product_id == 99
    assert forecast.model_used in ("holt_winters", "moving_average")
    assert forecast.confidence in ("HIGH", "MEDIUM")
    assert len(forecast.forecasts) == 7
    assert all(f["predicted_demand"] > 0 for f in forecast.forecasts)
