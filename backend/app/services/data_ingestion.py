import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx
import pandas as pd
import yfinance as yf
from fredapi import Fred
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.daily_bars import DailyBar
from app.models.market_regime import MarketRegime
from app.models.options import OptionsFlow, OptionsSnapshot
from app.models.stocks import Stock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class DataProvider(ABC):
    """Provider-agnostic interface for market data."""

    @abstractmethod
    async def get_daily_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_options_eod(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_options_chain(self, symbol: str) -> list[dict[str, Any]]:
        ...


# ---------------------------------------------------------------------------
# Rate limiter helper
# ---------------------------------------------------------------------------
class RateLimiter:
    """Token-bucket style rate limiter for async calls."""

    def __init__(self, calls_per_minute: int) -> None:
        self._semaphore = asyncio.Semaphore(calls_per_minute)
        self._interval = 60.0 / calls_per_minute

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        asyncio.get_running_loop().call_later(self._interval, self._semaphore.release)


async def _backoff_request(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any] | None = None,
    rate_limiter: RateLimiter | None = None,
    max_retries: int = 5,
) -> dict[str, Any]:
    """GET with exponential backoff and optional rate limiting."""
    if rate_limiter:
        await rate_limiter.acquire()
    for attempt in range(max_retries):
        try:
            resp = await client.get(url, params=params, timeout=30.0)
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                logger.warning("Rate limited on %s, waiting %ds", url, wait)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            wait = 2 ** (attempt + 1)
            logger.warning("Request error (%s), retry %d/%d in %ds", exc, attempt + 1, max_retries, wait)
            await asyncio.sleep(wait)
    raise RuntimeError(f"Failed after {max_retries} retries: {url}")


# ---------------------------------------------------------------------------
# Polygon.io
# ---------------------------------------------------------------------------
class PolygonClient(DataProvider):
    BASE = "https://api.polygon.io"

    def __init__(self) -> None:
        self._api_key = settings.polygon_api_key
        self._limiter = RateLimiter(calls_per_minute=5)
        self._client = httpx.AsyncClient()

    async def close(self) -> None:
        await self._client.aclose()

    # -- stock universe ----------------------------------------------------

    async def get_stock_universe(self) -> list[dict[str, Any]]:
        """Fetch active US stocks from Polygon reference data."""
        tickers: list[dict[str, Any]] = []
        url = f"{self.BASE}/v3/reference/tickers"
        params: dict[str, Any] = {
            "market": "stocks",
            "active": "true",
            "limit": 1000,
            "apiKey": self._api_key,
        }
        while True:
            data = await _backoff_request(self._client, url, params, self._limiter)
            tickers.extend(data.get("results", []))
            next_url = data.get("next_url")
            if not next_url:
                break
            url = next_url
            params = {"apiKey": self._api_key}
        return tickers

    async def get_sp500_symbols(self) -> set[str]:
        """Scrape current S&P 500 list from Wikipedia."""
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        try:
            resp = await self._client.get(url, timeout=30.0)
            tables = pd.read_html(resp.text)
            sp500_table = tables[0]
            return set(sp500_table["Symbol"].str.replace(".", "-", regex=False).tolist())
        except Exception:
            logger.exception("Failed to fetch S&P 500 list from Wikipedia")
            return set()

    async def get_russell2000_symbols(self) -> set[str]:
        """Fetch Russell 2000 constituents from iShares IWM holdings CSV."""
        url = (
            "https://www.ishares.com/us/products/239710/"
            "ishares-russell-2000-etf/1467271812596.ajax"
            "?fileType=csv&fileName=IWM_holdings&dataType=fund"
        )
        try:
            resp = await self._client.get(url, timeout=30.0, follow_redirects=True)
            lines = resp.text.strip().split("\n")
            header_idx = None
            for i, line in enumerate(lines):
                if line.startswith("Ticker") or line.startswith('"Ticker'):
                    header_idx = i
                    break
            if header_idx is None:
                logger.warning("Could not parse IWM holdings CSV")
                return set()
            from io import StringIO
            csv_text = "\n".join(lines[header_idx:])
            df = pd.read_csv(StringIO(csv_text))
            ticker_col = [c for c in df.columns if "ticker" in c.lower()][0]
            return set(df[ticker_col].dropna().astype(str).tolist())
        except Exception:
            logger.exception("Failed to fetch Russell 2000 from iShares")
            return set()

    # -- daily bars --------------------------------------------------------

    async def get_daily_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch daily OHLCV from Polygon aggregates endpoint."""
        bars: list[dict[str, Any]] = []
        url = (
            f"{self.BASE}/v2/aggs/ticker/{symbol}/range/1/day"
            f"/{start_date.isoformat()}/{end_date.isoformat()}"
        )
        params: dict[str, Any] = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self._api_key,
        }
        data = await _backoff_request(self._client, url, params, self._limiter)
        for r in data.get("results", []):
            bars.append(
                {
                    "date": datetime.fromtimestamp(r["t"] / 1000).date(),
                    "open": Decimal(str(r["o"])),
                    "high": Decimal(str(r["h"])),
                    "low": Decimal(str(r["l"])),
                    "close": Decimal(str(r["c"])),
                    "volume": int(r["v"]),
                    "vwap": Decimal(str(r.get("vw", 0))) if r.get("vw") else None,
                    "num_trades": r.get("n"),
                }
            )
        return bars

    async def get_options_eod(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        return []

    async def get_options_chain(self, symbol: str) -> list[dict[str, Any]]:
        return []


# ---------------------------------------------------------------------------
# Theta Data
# ---------------------------------------------------------------------------
class ThetaDataClient(DataProvider):
    """Theta Data REST API client for historical options data."""

    BASE = "http://127.0.0.1:25510"

    def __init__(self) -> None:
        self._limiter = RateLimiter(calls_per_minute=30)
        self._client = httpx.AsyncClient()

    async def close(self) -> None:
        await self._client.aclose()

    async def get_daily_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        return []

    async def get_options_eod(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch historical EOD options data from Theta Data."""
        results: list[dict[str, Any]] = []
        try:
            url = f"{self.BASE}/v2/bulk_hist/option/eod"
            params = {
                "root": symbol,
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
            }
            data = await _backoff_request(self._client, url, params, self._limiter)
            header = data.get("header", {}).get("format", [])
            for row in data.get("response", []):
                record = dict(zip(header, row))
                results.append(record)
        except Exception:
            logger.exception("Theta Data EOD fetch failed for %s", symbol)
        return results

    async def get_options_flow(self, symbol: str, trade_date: date) -> list[dict[str, Any]]:
        """Fetch trade-level options data, detect unusual activity."""
        results: list[dict[str, Any]] = []
        try:
            url = f"{self.BASE}/v2/bulk_hist/option/trade"
            params = {
                "root": symbol,
                "start_date": trade_date.strftime("%Y%m%d"),
                "end_date": trade_date.strftime("%Y%m%d"),
            }
            data = await _backoff_request(self._client, url, params, self._limiter)
            header = data.get("header", {}).get("format", [])
            for row in data.get("response", []):
                record = dict(zip(header, row))
                results.append(record)
        except Exception:
            logger.exception("Theta Data flow fetch failed for %s", symbol)
        return results

    async def get_options_chain(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def aggregate_options_snapshot(
        self, eod_records: list[dict[str, Any]], trade_date: date
    ) -> dict[str, Any] | None:
        """Aggregate raw EOD option records into a single OptionsSnapshot row."""
        if not eod_records:
            return None

        df = pd.DataFrame(eod_records)
        snapshot: dict[str, Any] = {"date": trade_date}

        try:
            right_col = "right" if "right" in df.columns else "contract_type"
            if right_col not in df.columns:
                return snapshot

            calls = df[df[right_col].str.upper() == "C"]
            puts = df[df[right_col].str.upper() == "P"]

            if "volume" in df.columns:
                if not calls.empty:
                    snapshot["total_call_volume"] = int(calls["volume"].sum())
                if not puts.empty:
                    snapshot["total_put_volume"] = int(puts["volume"].sum())

            if "open_interest" in df.columns:
                if not calls.empty:
                    snapshot["total_call_oi"] = int(calls["open_interest"].sum())
                if not puts.empty:
                    snapshot["total_put_oi"] = int(puts["open_interest"].sum())

            call_vol = snapshot.get("total_call_volume", 0) or 0
            put_vol = snapshot.get("total_put_volume", 0) or 0
            if call_vol > 0:
                snapshot["put_call_volume_ratio"] = Decimal(str(round(put_vol / call_vol, 4)))

            call_oi = snapshot.get("total_call_oi", 0) or 0
            put_oi = snapshot.get("total_put_oi", 0) or 0
            if call_oi > 0:
                snapshot["put_call_oi_ratio"] = Decimal(str(round(put_oi / call_oi, 4)))

            if "implied_volatility" in df.columns and "strike" in df.columns:
                mid_strike = df["strike"].median()
                atm_mask = (df["strike"] - mid_strike).abs() == (df["strike"] - mid_strike).abs().min()
                atm = df[atm_mask]
                if not atm.empty:
                    snapshot["iv_30d"] = Decimal(str(round(float(atm["implied_volatility"].mean()), 4)))

        except Exception:
            logger.exception("Error aggregating options snapshot")

        return snapshot

    def detect_unusual_flow(
        self, flow_records: list[dict[str, Any]], trade_date: date
    ) -> list[dict[str, Any]]:
        """Detect unusual options activity: volume > 2x OI, large premium."""
        unusual: list[dict[str, Any]] = []
        for rec in flow_records:
            vol = rec.get("volume", 0) or 0
            oi = rec.get("open_interest", 1) or 1
            if vol > 2 * oi:
                unusual.append({**rec, "date": trade_date, "is_unusual": True})
        return unusual


# ---------------------------------------------------------------------------
# yfinance (current options chains)
# ---------------------------------------------------------------------------
class YFinanceClient:
    """Free current options chain data via yfinance."""

    def get_current_options_chain(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch current options chain (synchronous — run in executor)."""
        results: list[dict[str, Any]] = []
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return results
            for exp in expirations[:3]:
                chain = ticker.option_chain(exp)
                for _, row in chain.calls.iterrows():
                    results.append({
                        "contract_type": "CALL",
                        "strike": Decimal(str(row.get("strike", 0))),
                        "expiration": datetime.strptime(exp, "%Y-%m-%d").date(),
                        "volume": int(row.get("volume", 0) or 0),
                        "open_interest": int(row.get("openInterest", 0) or 0),
                        "premium": Decimal(str(row.get("lastPrice", 0))),
                        "iv": Decimal(str(row.get("impliedVolatility", 0))),
                        "bid": Decimal(str(row.get("bid", 0))),
                        "ask": Decimal(str(row.get("ask", 0))),
                    })
                for _, row in chain.puts.iterrows():
                    results.append({
                        "contract_type": "PUT",
                        "strike": Decimal(str(row.get("strike", 0))),
                        "expiration": datetime.strptime(exp, "%Y-%m-%d").date(),
                        "volume": int(row.get("volume", 0) or 0),
                        "open_interest": int(row.get("openInterest", 0) or 0),
                        "premium": Decimal(str(row.get("lastPrice", 0))),
                        "iv": Decimal(str(row.get("impliedVolatility", 0))),
                        "bid": Decimal(str(row.get("bid", 0))),
                        "ask": Decimal(str(row.get("ask", 0))),
                    })
        except Exception:
            logger.exception("yfinance options chain failed for %s", symbol)
        return results


# ---------------------------------------------------------------------------
# Alpha Vantage (backup stock data)
# ---------------------------------------------------------------------------
class AlphaVantageClient(DataProvider):
    BASE = "https://www.alphavantage.co/query"

    def __init__(self) -> None:
        self._api_key = settings.alpha_vantage_api_key
        self._limiter = RateLimiter(calls_per_minute=5)
        self._client = httpx.AsyncClient()

    async def close(self) -> None:
        await self._client.aclose()

    async def get_daily_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch daily bars from Alpha Vantage TIME_SERIES_DAILY_ADJUSTED."""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": self._api_key,
        }
        data = await _backoff_request(self._client, self.BASE, params, self._limiter)
        ts = data.get("Time Series (Daily)", {})
        bars: list[dict[str, Any]] = []
        for date_str, values in ts.items():
            bar_date = date.fromisoformat(date_str)
            if start_date <= bar_date <= end_date:
                bars.append({
                    "date": bar_date,
                    "open": Decimal(values["1. open"]),
                    "high": Decimal(values["2. high"]),
                    "low": Decimal(values["3. low"]),
                    "close": Decimal(values["5. adjusted close"]),
                    "volume": int(values["6. volume"]),
                    "vwap": None,
                    "num_trades": None,
                })
        return sorted(bars, key=lambda x: x["date"])

    async def get_options_eod(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        return []

    async def get_options_chain(self, symbol: str) -> list[dict[str, Any]]:
        return []


# ---------------------------------------------------------------------------
# FRED (macro data)
# ---------------------------------------------------------------------------
class FREDClient:
    """FRED API client for macro data: VIX, yields, rates."""

    def __init__(self) -> None:
        self._fred = Fred(api_key=settings.fred_api_key)

    def get_macro_data(self, start_date: date) -> list[dict[str, Any]]:
        """Pull VIX, 10Y yield, 2Y yield, fed funds rate from FRED.

        Runs synchronously — call from executor if needed.
        """
        series_map = {
            "VIXCLS": "vix_close",
            "DGS10": "us_10y_yield",
            "DGS2": "us_2y_yield",
            "FEDFUNDS": "fed_funds_rate",
        }
        frames: dict[str, pd.Series] = {}  # type: ignore[type-arg]
        for series_id, col_name in series_map.items():
            try:
                s = self._fred.get_series(series_id, observation_start=start_date)
                frames[col_name] = s
            except Exception:
                logger.exception("FRED fetch failed for %s", series_id)

        if not frames:
            return []

        df = pd.DataFrame(frames)
        df.index.name = "date"
        df = df.dropna(how="all")

        results: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            record: dict[str, Any] = {"date": idx.date() if hasattr(idx, "date") else idx}  # type: ignore[union-attr]
            for col in df.columns:
                val = row[col]
                if pd.notna(val):
                    record[col] = Decimal(str(round(float(val), 4)))
            if "us_10y_yield" in record and "us_2y_yield" in record:
                record["yield_curve_spread"] = record["us_10y_yield"] - record["us_2y_yield"]
            results.append(record)
        return results


# ---------------------------------------------------------------------------
# DB upsert helpers
# ---------------------------------------------------------------------------
async def upsert_stock(session: AsyncSession, data: dict[str, Any]) -> int:
    """Upsert a stock record, return stock_id."""
    stmt = pg_insert(Stock).values(**data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol"],
        set_={k: v for k, v in data.items() if k != "symbol"},
    )
    result = await session.execute(stmt.returning(Stock.id))
    await session.commit()
    row = result.fetchone()
    return row[0]  # type: ignore[index]


async def upsert_daily_bars(
    session: AsyncSession, stock_id: int, bars: list[dict[str, Any]]
) -> int:
    """Bulk upsert daily bars, return count inserted."""
    if not bars:
        return 0
    rows = [{**b, "stock_id": stock_id} for b in bars]
    stmt = pg_insert(DailyBar).values(rows)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_daily_bars_stock_date")
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount  # type: ignore[return-value]


async def upsert_options_snapshot(
    session: AsyncSession, stock_id: int, snapshot: dict[str, Any]
) -> None:
    """Upsert a single options snapshot row."""
    data = {**snapshot, "stock_id": stock_id}
    stmt = pg_insert(OptionsSnapshot).values(**data)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_options_snapshots_stock_date",
        set_={k: v for k, v in data.items() if k not in ("stock_id", "date")},
    )
    await session.execute(stmt)
    await session.commit()


async def upsert_options_flow(
    session: AsyncSession, stock_id: int, flows: list[dict[str, Any]]
) -> None:
    """Bulk insert options flow records."""
    if not flows:
        return
    rows = [{**f, "stock_id": stock_id} for f in flows]
    stmt = pg_insert(OptionsFlow).values(rows)
    stmt = stmt.on_conflict_do_nothing()
    await session.execute(stmt)
    await session.commit()


async def upsert_market_regime(
    session: AsyncSession, data: dict[str, Any]
) -> None:
    """Upsert a market regime record."""
    stmt = pg_insert(MarketRegime).values(**data)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_market_regimes_date",
        set_={k: v for k, v in data.items() if k != "date"},
    )
    await session.execute(stmt)
    await session.commit()


async def update_last_seeded_date(
    session: AsyncSession, stock_id: int, seeded_date: date
) -> None:
    """Update checkpoint for resume support."""
    result = await session.execute(select(Stock).where(Stock.id == stock_id))
    stock = result.scalar_one()
    stock.last_seeded_date = seeded_date
    await session.commit()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class DataIngestionOrchestrator:
    """Coordinates data ingestion across multiple providers."""

    def __init__(self) -> None:
        self.polygon = PolygonClient()
        self.theta = ThetaDataClient()
        self.yfinance = YFinanceClient()
        self.alpha_vantage = AlphaVantageClient()
        self.fred = FREDClient()

    async def close(self) -> None:
        await self.polygon.close()
        await self.theta.close()
        await self.alpha_vantage.close()

    async def fetch_daily_bars(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch daily bars — Polygon primary, Alpha Vantage fallback."""
        try:
            bars = await self.polygon.get_daily_bars(symbol, start_date, end_date)
            if bars:
                return bars
        except Exception:
            logger.warning("Polygon failed for %s, trying Alpha Vantage", symbol)
        try:
            return await self.alpha_vantage.get_daily_bars(symbol, start_date, end_date)
        except Exception:
            logger.exception("Alpha Vantage also failed for %s", symbol)
            return []

    async def fetch_options_eod(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch historical options EOD — Theta Data primary, yfinance fallback."""
        try:
            results = await self.theta.get_options_eod(symbol, start_date, end_date)
            if results:
                return results
        except Exception:
            logger.warning("Theta Data EOD failed for %s, trying yfinance fallback", symbol)

        # Fallback: use yfinance for current options snapshot data
        try:
            chain = await self.fetch_current_options_chain(symbol)
            if chain:
                logger.info("Got %d option records from yfinance for %s", len(chain), symbol)
                return chain
        except Exception:
            logger.exception("yfinance options fallback also failed for %s", symbol)
        return []

    async def fetch_current_options_chain(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch current options chain from yfinance (sync, run in executor)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.yfinance.get_current_options_chain, symbol)

    async def fetch_macro_data(self, start_date: date) -> list[dict[str, Any]]:
        """Fetch macro data from FRED (sync, run in executor)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fred.get_macro_data, start_date)

    async def build_stock_universe(self, session: AsyncSession) -> list[int]:
        """Fetch S&P 500 + Russell 2000 and upsert into stocks table."""
        sp500 = await self.polygon.get_sp500_symbols()
        russell2000 = await self.polygon.get_russell2000_symbols()
        logger.info("Fetched %d S&P 500, %d Russell 2000 symbols", len(sp500), len(russell2000))

        all_symbols = sp500 | russell2000
        logger.info("Total unique symbols: %d", len(all_symbols))

        polygon_tickers = await self.polygon.get_stock_universe()
        ticker_info = {t["ticker"]: t for t in polygon_tickers if t.get("ticker") in all_symbols}

        stock_ids: list[int] = []
        for symbol in sorted(all_symbols):
            membership: list[str] = []
            if symbol in sp500:
                membership.append("sp500")
            if symbol in russell2000:
                membership.append("russell2000")

            info = ticker_info.get(symbol, {})
            stock_data: dict[str, Any] = {
                "symbol": symbol,
                "name": info.get("name", symbol),
                "sector": info.get("sic_description", None),
                "industry": None,
                "market_cap": info.get("market_cap", None),
                "index_membership": membership,
                "is_active": True,
            }
            stock_id = await upsert_stock(session, stock_data)
            stock_ids.append(stock_id)

        logger.info("Upserted %d stocks", len(stock_ids))
        return stock_ids
