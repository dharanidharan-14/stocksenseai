"""
StockSense AI - Demand Forecasting Engine

Provides moving average and Holt-Winters forecasting with
automatic model selection, confidence labeling, and backtesting.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except ImportError:
    ExponentialSmoothing = None


@dataclass
class ProductForecast:
    """Result of forecasting for a single product."""
    product_id: int
    forecasts: List[Dict]  # [{date, predicted_demand, lower_bound, upper_bound}]
    model_used: str  # "moving_average", "holt_winters", "fallback_zero"
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    mae: Optional[float] = None
    wape: Optional[float] = None
    explanation: str = ""


# Minimum days of history needed for each model
MIN_HISTORY_MOVING_AVG = 7
MIN_HISTORY_HOLT_WINTERS = 30
MOVING_AVG_WINDOW = 7


def aggregate_daily_sales(
    sales_data: List[Dict],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.Series:
    """
    Aggregate sale items into a daily time series.
    
    sales_data: list of {date: date, quantity: Decimal/float}
    Returns pd.Series indexed by date with daily demand totals.
    """
    if not sales_data:
        return pd.Series(dtype=float)

    df = pd.DataFrame(sales_data)
    df["date"] = pd.to_datetime(df["date"])
    df["quantity"] = df["quantity"].astype(float)
    daily = df.groupby("date")["quantity"].sum()

    # Fill in zero-sales days
    if start_date and end_date:
        full_range = pd.date_range(start=start_date, end=end_date, freq="D")
        daily = daily.reindex(full_range, fill_value=0.0)

    return daily.sort_index()


def moving_average_forecast(
    daily_demand: pd.Series,
    horizon: int = 7,
    window: int = MOVING_AVG_WINDOW,
) -> Tuple[List[float], float, float]:
    """
    Simple moving average forecast.
    Returns (predictions, mae, std_dev).
    """
    if len(daily_demand) < window:
        # Use all available data
        window = len(daily_demand)

    recent = daily_demand.tail(window)
    avg = float(recent.mean())
    std = float(recent.std()) if len(recent) > 1 else 0.0

    predictions = [max(0, avg)] * horizon

    # Backtest: compute MAE on last 'window' days using leave-one-out
    if len(daily_demand) >= window * 2:
        test_start = len(daily_demand) - window
        train = daily_demand.iloc[:test_start]
        test = daily_demand.iloc[test_start:]
        train_avg = float(train.tail(window).mean())
        errors = [abs(float(actual) - train_avg) for actual in test]
        mae = sum(errors) / len(errors) if errors else 0.0
    else:
        mae = std  # rough estimate

    return predictions, mae, std


def holt_winters_forecast(
    daily_demand: pd.Series,
    horizon: int = 7,
) -> Optional[Tuple[List[float], float, float]]:
    """
    Holt-Winters exponential smoothing forecast.
    Returns (predictions, mae, std_dev) or None if not applicable.
    """
    if ExponentialSmoothing is None:
        return None

    if len(daily_demand) < MIN_HISTORY_HOLT_WINTERS:
        return None

    # Check for sufficient variation (HW needs non-constant data)
    if daily_demand.std() < 0.01:
        return None

    try:
        # Chronological train/test split for backtesting
        test_size = min(7, len(daily_demand) // 5)
        train = daily_demand.iloc[:-test_size]
        test = daily_demand.iloc[-test_size:]

        # Fit Holt-Winters (additive trend, no seasonal for daily grocery)
        model = ExponentialSmoothing(
            train.values,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True)

        # Backtest
        test_preds = fitted.forecast(test_size)
        errors = [abs(float(a) - float(p)) for a, p in zip(test.values, test_preds)]
        mae = sum(errors) / len(errors)
        std = float(np.std(errors))

        # Refit on full data for final forecast
        model_full = ExponentialSmoothing(
            daily_demand.values,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        fitted_full = model_full.fit(optimized=True)
        predictions = fitted_full.forecast(horizon)
        predictions = [max(0, float(p)) for p in predictions]

        return predictions, mae, std

    except Exception:
        return None


def forecast_product(
    product_id: int,
    sales_data: List[Dict],
    horizon: int = 7,
    today: Optional[date] = None,
) -> ProductForecast:
    """
    Forecast demand for a single product.
    
    Automatically selects the best model:
    1. If >= 30 days of data: try Holt-Winters, compare with MA
    2. If >= 7 days: use moving average
    3. Otherwise: low-confidence fallback
    """
    if today is None:
        today = date.today()

    forecast_dates = [today + timedelta(days=i + 1) for i in range(horizon)]

    # Aggregate daily sales
    if sales_data:
        earliest = min(d["date"] for d in sales_data)
        daily = aggregate_daily_sales(sales_data, start_date=earliest, end_date=today)
    else:
        daily = pd.Series(dtype=float)

    n_days = len(daily)
    total_demand = float(daily.sum()) if n_days > 0 else 0.0

    # Case 1: No history at all
    if n_days == 0 or total_demand == 0:
        return ProductForecast(
            product_id=product_id,
            forecasts=[
                {
                    "date": d,
                    "predicted_demand": 0.0,
                    "lower_bound": 0.0,
                    "upper_bound": 0.0,
                }
                for d in forecast_dates
            ],
            model_used="fallback_zero",
            confidence="LOW",
            explanation=(
                "No sales history available for this product. "
                "Forecast is set to zero. This is a low-confidence estimate."
            ),
        )

    # Case 2: Limited history (< 7 days)
    if n_days < MIN_HISTORY_MOVING_AVG:
        avg = total_demand / n_days
        return ProductForecast(
            product_id=product_id,
            forecasts=[
                {
                    "date": d,
                    "predicted_demand": round(max(0, avg), 2),
                    "lower_bound": 0.0,
                    "upper_bound": round(avg * 2, 2),
                }
                for d in forecast_dates
            ],
            model_used="moving_average",
            confidence="LOW",
            explanation=(
                f"Only {n_days} days of sales history. Using simple average "
                f"({avg:.1f}/day). Recommendation has low confidence."
            ),
        )

    # Case 3: Try Holt-Winters (>= 30 days)
    hw_result = None
    if n_days >= MIN_HISTORY_HOLT_WINTERS:
        hw_result = holt_winters_forecast(daily, horizon)

    # Always compute moving average
    ma_preds, ma_mae, ma_std = moving_average_forecast(daily, horizon)

    # Select best model
    if hw_result:
        hw_preds, hw_mae, hw_std = hw_result
        if hw_mae < ma_mae:
            # Holt-Winters wins
            forecasts = [
                {
                    "date": d,
                    "predicted_demand": round(p, 2),
                    "lower_bound": round(max(0, p - 1.96 * hw_std), 2),
                    "upper_bound": round(p + 1.96 * hw_std, 2),
                }
                for d, p in zip(forecast_dates, hw_preds)
            ]
            confidence = "HIGH" if hw_mae < float(daily.mean()) * 0.3 else "MEDIUM"
            wape = hw_mae / float(daily.mean()) if daily.mean() > 0 else None

            return ProductForecast(
                product_id=product_id,
                forecasts=forecasts,
                model_used="holt_winters",
                confidence=confidence,
                mae=round(hw_mae, 4),
                wape=round(wape, 4) if wape else None,
                explanation=(
                    f"Holt-Winters exponential smoothing selected (MAE: {hw_mae:.2f}) "
                    f"over moving average (MAE: {ma_mae:.2f}). "
                    f"Based on {n_days} days of sales history. "
                    f"Confidence: {confidence}."
                ),
            )

    # Moving average
    forecasts = [
        {
            "date": d,
            "predicted_demand": round(p, 2),
            "lower_bound": round(max(0, p - 1.96 * ma_std), 2),
            "upper_bound": round(p + 1.96 * ma_std, 2),
        }
        for d, p in zip(forecast_dates, ma_preds)
    ]

    confidence = "MEDIUM" if n_days >= 14 else "LOW"
    wape = ma_mae / float(daily.mean()) if daily.mean() > 0 else None

    return ProductForecast(
        product_id=product_id,
        forecasts=forecasts,
        model_used="moving_average",
        confidence=confidence,
        mae=round(ma_mae, 4),
        wape=round(wape, 4) if wape else None,
        explanation=(
            f"{MOVING_AVG_WINDOW}-day moving average used. "
            f"Average daily demand: {float(daily.tail(MOVING_AVG_WINDOW).mean()):.1f}. "
            f"Based on {n_days} days of history. "
            f"Confidence: {confidence}."
            + (
                " Holt-Winters was tested but moving average performed better."
                if hw_result
                else ""
            )
        ),
    )


def compute_forecast_accuracy(
    actual: List[float], predicted: List[float]
) -> Dict[str, float]:
    """Compute MAE and WAPE for forecast accuracy evaluation."""
    if not actual or not predicted or len(actual) != len(predicted):
        return {"mae": None, "wape": None}

    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    mae = sum(errors) / len(errors)

    total_actual = sum(actual)
    total_error = sum(errors)
    wape = total_error / total_actual if total_actual > 0 else None

    return {"mae": round(mae, 4), "wape": round(wape, 4) if wape else None}
