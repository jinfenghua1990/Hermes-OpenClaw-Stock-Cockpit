"""
TuShare MCP Client - 统一封装 TuShare 可用接口
Phase-2.3C: 2000积分可用接口全部封装，默认不全部启用
"""
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "e85b62c1005ad7254faf4cfa7b2e0fac194af09889ddb784d1882f74"
BASE_URL = "https://api.tushare.pro"
HEADERS = {"Content-Type": "application/json"}
TIMEOUT = 30
RETRY_TIMES = 3
RETRY_DELAY = 5

PROJECT_DIR = Path(__file__).parent.parent.resolve()


class TuShareClient:
    def __init__(self, token: str = TOKEN):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _call(self, api_name: str, params: Optional[Dict] = None,
              fields: Optional[str] = None, retry: int = RETRY_TIMES) -> Dict:
        payload = {
            "api_name": api_name,
            "token": self.token,
            "params": params or {},
        }
        # 注意：fields放在哪里取决于API
        # stock_basic/ trade_cal 等：fields在params里
        # daily/daily_basic/index_daily 等：fields在顶层
        if fields:
            if api_name in ("stock_basic", "trade_cal", "index_basic"):
                payload["params"]["fields"] = fields
            else:
                payload["fields"] = fields

        for attempt in range(retry):
            try:
                resp = self.session.post(BASE_URL, json=payload, timeout=TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
                # 有积分限制/接口不可用
                logger.warning(f"TuShare {api_name} code={data.get('code')} msg={data.get('msg')}")
                return {"items": [], "fields": [], "has_more": False}
            except Exception as e:
                if attempt < retry - 1:
                    logger.warning(f"TuShare {api_name} 失败(重试{attempt+1}): {e}")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"TuShare {api_name} 最终失败: {e}")
                    return {"items": [], "fields": [], "has_more": False}
        return {"items": [], "fields": [], "has_more": False}

    def _items_to_df(self, data: Dict, fields: Optional[str] = None) -> pd.DataFrame:
        """把items转成DataFrame，自动用fields做列名"""
        field_list = fields.split(",") if fields else []
        items = data.get("items", [])
        if not items:
            return pd.DataFrame()
        df = pd.DataFrame(items, columns=field_list) if field_list else pd.DataFrame(items)
        return df

    # ─────────────────────────────────────────────
    # 默认启用接口（进入 baseline_v1）
    # ─────────────────────────────────────────────

    def stock_basic(self, list_status: str = "L") -> pd.DataFrame:
        """股票列表基础信息"""
        data = self._call("stock_basic", {
            "list_status": list_status,
        })
        return self._items_to_df(data)

    def trade_cal(self, exchange: str = "SSE", start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """交易日历"""
        today = datetime.now().strftime("%Y%m%d")
        params = {
            "exchange": exchange,
            "start_date": start_date or (datetime.now() - timedelta(days=365)).strftime("%Y%m%d"),
            "end_date": end_date or today,
        }
        data = self._call("trade_cal", params)
        return self._items_to_df(data)

    def daily(self, ts_code: str = "", trade_date: str = "", start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """日K线 - 核心数据源"""
        params = {}
        if ts_code: params["ts_code"] = ts_code
        if trade_date: params["trade_date"] = trade_date
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        fields = "ts_code,trade_date,open,high,low,close,vol,amount"
        data = self._call("daily", params, fields)
        df = self._items_to_df(data, fields)
        # 统一列名：TuShare的trade_date→date, vol→volume
        if "trade_date" in df.columns:
            df = df.rename(columns={"trade_date": "date"})
        if "vol" in df.columns:
            df = df.rename(columns={"vol": "volume"})
        return df

    def daily_basic(self, ts_code: str = "", trade_date: str = "", start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """每日行情指标 - 量比/换手率/振幅/PE/流通市值"""
        params = {}
        if ts_code: params["ts_code"] = ts_code
        if trade_date: params["trade_date"] = trade_date
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        fields = "ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,total_market_cap,float_market_cap"
        data = self._call("daily_basic", params, fields)
        df = self._items_to_df(data, fields)
        if "trade_date" in df.columns:
            df = df.rename(columns={"trade_date": "date"})
        return df

    def adj_factor(self, ts_code: str = "", start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """复权因子 - 用于计算真实前复权/后复权价格"""
        params = {}
        if ts_code: params["ts_code"] = ts_code
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        fields = "ts_code,trade_date,adj_factor"
        data = self._call("adj_factor", params, fields)
        df = self._items_to_df(data, fields)
        if "trade_date" in df.columns:
            df = df.rename(columns={"trade_date": "date"})
        return df

    def stk_limit(self, trade_date: str = "") -> pd.DataFrame:
        """涨跌停价格"""
        params = {}
        if trade_date: params["trade_date"] = trade_date
        fields = "trade_date,ts_code,open_limit_h,open_limit_l,close_limit_h,close_limit_l"
        data = self._call("stk_limit", params, fields)
        return self._items_to_df(data, fields)

    # ─────────────────────────────────────────────
    # 备用接口（不进入 baseline，只在 experimental 层使用）
    # ─────────────────────────────────────────────

    def index_basic(self, market: str = "A") -> pd.DataFrame:
        """指数基础信息"""
        params = {"market": market}
        fields = "ts_code,name,fullname,market,publish_date,category"
        data = self._call("index_basic", params, fields)
        return self._items_to_df(data, fields)

    def index_daily(self, ts_code: str = "", start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """指数日K线"""
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        fields = "ts_code,trade_date,open,high,low,close,vol,amount"
        data = self._call("index_daily", params, fields)
        return self._items_to_df(data, fields)

    def moneyflow(self, ts_code: str = "", trade_date: str = "") -> pd.DataFrame:
        """个股资金流向"""
        params = {}
        if ts_code: params["ts_code"] = ts_code
        if trade_date: params["trade_date"] = trade_date
        fields = "ts_code,trade_date,buy_sm_amount,sell_sm_amount,buy_md_amount,sell_md_amount,buy_lg_amount,sell_lg_amount,buy_elg_amount,sell_elg_amount,net_mf_amount"
        data = self._call("moneyflow", params, fields)
        return self._items_to_df(data, fields)

    def fina_indicator(self, ts_code: str = "", start_date: str = "", end_date: str = "", period: str = "") -> pd.DataFrame:
        """财务指标"""
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        if period: params["period"] = period
        fields = "ts_code,trade_date,eps,roe,roa,gross_margin,net_margin,debt_to_assets,current_ratio,quick_ratio"
        data = self._call("fina_indicator", params, fields)
        return self._items_to_df(data, fields)

    def balancesheet(self, ts_code: str = "", start_date: str = "", end_date: str = "", period: str = "") -> pd.DataFrame:
        """资产负债表"""
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        if period: params["period"] = period
        fields = "ts_code,ann_date,total_assets,total_liab,equity,fixed_assets"
        data = self._call("balancesheet", params, fields)
        return self._items_to_df(data, fields)

    def income(self, ts_code: str = "", start_date: str = "", end_date: str = "", period: str = "") -> pd.DataFrame:
        """利润表"""
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        if period: params["period"] = period
        fields = "ts_code,ann_date,revenue,cost,gross_profit,net_profit,total_profit"
        data = self._call("income", params, fields)
        return self._items_to_df(data, fields)

    def cashflow(self, ts_code: str = "", start_date: str = "", end_date: str = "", period: str = "") -> pd.DataFrame:
        """现金流量表"""
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date
        if end_date: params["end_date"] = end_date
        if period: params["period"] = period
        fields = "ts_code,ann_date,net_operate_cashflow,net_invest_cashflow,net_finance_cashflow"
        data = self._call("cashflow", params, fields)
        return self._items_to_df(data, fields)

    # ─────────────────────────────────────────────
    # 批量下载工具
    # ─────────────────────────────────────────────

    def download_all_daily(self, start_date: str, end_date: str, output_dir: str = "data/kline_daily",
                          adj_factor_dir: str = "data/adj_factor", sleep: float = 0.15) -> Dict:
        """
        批量下载所有股票的日K线 + 复权因子
        每天自动sleep避免触发频率限制
        """
        output_path = PROJECT_DIR / output_dir
        adj_path = PROJECT_DIR / adj_factor_dir
        output_path.mkdir(parents=True, exist_ok=True)
        adj_path.mkdir(parents=True, exist_ok=True)

        # 1. 获取全部股票列表
        logger.info("[1/4] 获取股票列表...")
        stocks = self.stock_basic(list_status="L")
        logger.info(f"  上市股票: {len(stocks)} 只")

        # 2. 批量下载日K
        results = {"ok": 0, "fail": 0, "skipped": 0}
        logger.info(f"[2/4] 下载日K线 {start_date}~{end_date}...")
        for i, row in stocks.iterrows():
            ts_code = row["ts_code"]
            try:
                df = self.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df.empty:
                    results["skipped"] += 1
                    continue
                # 修复 high < low
                df = df.copy()
                if "high" in df.columns and "low" in df.columns:
                    mask = df["high"] < df["low"]
                    if mask.any():
                        logger.warning(f"  {ts_code} high<low {mask.sum()}条，已修复")
                        df.loc[mask, "high"] = df.loc[mask, ["high", "low"]].max(axis=1)
                        df.loc[mask, "low"] = df.loc[mask, ["high", "low"]].min(axis=1)
                code = ts_code.replace(".SH", ".SH").replace(".SZ", ".SZ")
                fname = output_path / f"{code}.csv"
                df.to_csv(fname, index=False, encoding="utf-8")
                results["ok"] += 1
            except Exception as e:
                results["fail"] += 1
                logger.warning(f"  {ts_code} 下载失败: {e}")
            if (i + 1) % 50 == 0:
                logger.info(f"  进度: {i+1}/{len(stocks)}")
            time.sleep(sleep)

        # 3. 批量下载复权因子
        logger.info(f"[3/4] 下载复权因子...")
        adj_results = {"ok": 0, "fail": 0}
        for i, row in stocks.iterrows():
            ts_code = row["ts_code"]
            try:
                df = self.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
                if df.empty:
                    continue
                code = ts_code
                fname = adj_path / f"{code}.csv"
                df.to_csv(fname, index=False, encoding="utf-8")
                adj_results["ok"] += 1
            except Exception as e:
                adj_results["fail"] += 1
            time.sleep(sleep)

        logger.info(f"[4/4] 完成: 日K ok={results['ok']} fail={results['fail']} 跳过={results['skipped']}")
        logger.info(f"      复权因子 ok={adj_results['ok']} fail={adj_results['fail']}")
        return results


if __name__ == "__main__":
    client = TuShareClient()
    # 快速测试
    print("=== TuShare 连通性测试 ===")
    cal = client.trade_cal()
    print(f"交易日历: {len(cal)} 条")
    stocks = client.stock_basic()
    print(f"上市股票: {len(stocks)} 只")
