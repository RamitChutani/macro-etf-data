#!/usr/bin/env python3
"""Build a professional, drill-down HTML dashboard for Macro ETF Analysis."""

from __future__ import annotations

import argparse
import json
import os
import pandas as pd

from build_excel_dashboard_mvp import (
    COUNTRY_TO_REGION,
    PricePoint,
    last_on_or_before,
    max_start_point,
    pct_return,
    cagr_from_total_return,
    choose_price_columns,
    load_gdp_growth_maps,
)
from build_combined_etf_weo import build_ticker_country_map
from etf_mapping import COUNTRY_TO_ISO3

# Main view timeframes (Macro valid)
MAIN_TIMEFRAMES = ["1Y", "3Y", "5Y", "10Y"]
# Detail view timeframes (Short term)
SHORT_TIMEFRAMES = ["1D", "1W", "1M", "YTD"]

def get_gdp_cagr(cc, years, maps, end_year=2025):
    _, _, _, _, current_usd_map = maps
    try:
        v_start = current_usd_map.get((cc, end_year - years))
        v_end = current_usd_map.get((cc, end_year))
        if v_start and v_end and v_start > 0:
            total_ret = (v_end / v_start) - 1.0
            return cagr_from_total_return(total_ret * 100.0, years)
    except:
        return None
    return None

def build_dashboard_data(etf_csv: str, weo_csv: str, metadata_csv: str) -> dict:
    prices_raw = pd.read_csv(etf_csv)
    prices_raw["Date"] = pd.to_datetime(prices_raw["Date"], errors="coerce")
    prices_raw = prices_raw.dropna(subset=["Date"]).sort_values("Date")
    
    ticker_to_country = build_ticker_country_map()
    price_columns = choose_price_columns(prices_raw.columns.tolist())
    metadata = pd.read_csv(metadata_csv)
    ticker_info = metadata.set_index("ticker").to_dict(orient="index")
    gdp_maps = load_gdp_growth_maps(weo_csv)
    (gdp_real_map, gdp_lcu_map, gdp_usd_map, fx_map, _) = gdp_maps
    
    latest_date = prices_raw["Date"].max()
    as_of_str = latest_date.strftime("%b %d, %Y").upper()
    
    countries_data = []
    
    for ticker, price_col in price_columns.items():
        country = ticker_to_country.get(ticker)
        if not country: continue
        
        region = COUNTRY_TO_REGION.get(country, "Other")
        cc = COUNTRY_TO_ISO3.get(country)
        series = prices_raw.set_index("Date")[price_col].dropna()
        if series.empty: continue
        
        start_pt_max = max_start_point(series)
        if start_pt_max is None: continue
        end_pt = PricePoint(series.index[-1], float(series.iloc[-1]))
        
        # Calculate Returns and Disconnects
        perf = {}
        for label in MAIN_TIMEFRAMES + SHORT_TIMEFRAMES:
            if label == "YTD":
                target = pd.Timestamp(year=end_pt.date.year, month=1, day=1)
            else:
                unit = label[-1]
                val = int(label[:-1])
                offset = pd.DateOffset(years=val) if unit == 'Y' else \
                         pd.DateOffset(months=val) if unit == 'M' else \
                         pd.DateOffset(weeks=val) if unit == 'W' else \
                         pd.DateOffset(days=val)
                target = end_pt.date - offset
            
            start_pt = last_on_or_before(series, target)
            if start_pt and start_pt.date >= start_pt_max.date:
                ret = pct_return(start_pt.value, end_pt.value)
                if label in ["3Y", "5Y", "10Y"]:
                    ret = cagr_from_total_return(ret, int(label[:-1]))
                
                perf[label.lower()] = round(ret / 100.0, 4)
                
                if label in MAIN_TIMEFRAMES:
                    gdp_val = gdp_usd_map.get((cc, 2025)) if label == "1Y" else get_gdp_cagr(cc, int(label[:-1]), gdp_maps)
                    if gdp_val is not None:
                        perf[f"disc_{label.lower()}"] = round((gdp_val - ret) / 100.0, 4)
                        perf[f"gdp_{label.lower()}"] = round(gdp_val / 100.0, 4)
            else:
                perf[label.lower()] = None

        # Annual History (Last 10 Years)
        history = []
        for y in range(2015, 2026):
            history.append({
                "year": y,
                "gdp_usd": gdp_usd_map.get((cc, y)),
                "gdp_real": gdp_real_map.get((cc, y)),
                "gdp_lcu": gdp_lcu_map.get((cc, y)),
                "weo_fx": fx_map.get((cc, y))
            })

        countries_data.append({
            "ticker": ticker, "country": country, "region": region, "cc": cc,
            "etf": ticker_info.get(ticker, {}).get("long_name", ticker),
            "currency": ticker_info.get(ticker, {}).get("currency", "USD"),
            **perf, "history": history
        })
            
    return {
        "as_of": as_of_str,
        "countries": countries_data,
        "regions": sorted(list(set(COUNTRY_TO_REGION.values())))
    }

def generate_html(data: dict, output_path: str):
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Macro Analysis Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#0f172a;--bg-card:#1e293b;--border:#334155;--text:#f8fafc;--text-dim:#94a3b8;--green:#4ade80;--red:#fb7185;--blue:#3b82f6;--cyan:#22d3ee;--font-body:'Inter', sans-serif;--font-mono:'JetBrains Mono', monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:var(--font-body);line-height:1.5}
.header{position:sticky;top:0;z-index:100;background:rgba(15,23,42,0.9);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);padding:16px 40px;display:flex;align-items:center;justify-content:space-between}
.logo{font-family:var(--font-mono);font-size:20px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.main{padding:32px 40px;max-width:1400px;margin:0 auto}
.controls{display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;background:var(--bg-card);padding:20px;border-radius:12px;border:1px solid var(--border)}
.btn-group{display:flex;background:var(--bg);padding:4px;border-radius:8px;border:1px solid var(--border)}
.btn{background:transparent;border:none;color:var(--text-dim);padding:8px 16px;font-family:var(--font-mono);font-size:12px;font-weight:700;cursor:pointer;border-radius:6px;transition:0.2s}
.btn.active{background:var(--blue);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.card{background:var(--bg-card);padding:20px;border-radius:12px;border:1px solid var(--border);cursor:pointer;transition:0.3s;display:flex;flex-direction:column;justify-content:space-between;min-height:140px}
.card:hover{transform:translateY(-4px);border-color:var(--text-dim)}
.c-name{font-size:18px;font-weight:800;color:#fff;margin-bottom:2px}
.c-region{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;font-weight:700}
.c-val{font-family:var(--font-mono);font-size:28px;font-weight:800;margin-top:12px}
.c-sub{font-size:11px;color:rgba(255,255,255,0.7);font-weight:600}
.detail-view{display:none}
.back-btn{display:inline-flex;align-items:center;gap:8px;color:var(--cyan);cursor:pointer;margin-bottom:24px;font-weight:700;font-size:14px}
.detail-header{margin-bottom:32px}
.table-wrap{background:var(--bg-card);border-radius:12px;border:1px solid var(--border);overflow:hidden;margin-bottom:32px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-family:var(--font-mono);font-size:11px;color:var(--text-dim);padding:16px;background:rgba(0,0,0,0.2);text-transform:uppercase}
td{padding:16px;border-bottom:1px solid var(--border);font-size:14px}
.val-pos{color:var(--red);font-weight:700}
.val-neg{color:var(--green);font-weight:700}
</style>
</head>
<body>
<div class="header"><div class="logo">MACRO DISCONNECT</div><div style="font-family:var(--font-mono);font-size:12px;color:var(--cyan)" id="asOf"></div></div>
<div class="main">
  <div id="mainView">
    <div class="controls">
      <div style="display:flex;gap:24px">
        <div style="display:flex;flex-direction:column;gap:8px">
          <div style="font-size:10px;font-weight:800;color:var(--text-dim);text-transform:uppercase">Annual</div>
          <div class="btn-group">
            <button class="btn period-btn" onclick="setPeriod('1y', this)">1Y</button>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px">
          <div style="font-size:10px;font-weight:800;color:var(--text-dim);text-transform:uppercase">CAGR Horizons</div>
          <div class="btn-group">
            <button class="btn period-btn active" onclick="setPeriod('3y', this)">3Y</button>
            <button class="btn period-btn" onclick="setPeriod('5y', this)">5Y</button>
            <button class="btn period-btn" onclick="setPeriod('10y', this)">10Y</button>
          </div>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div style="font-size:10px;font-weight:800;color:var(--text-dim);text-transform:uppercase">Region Filter</div>
        <div id="regionFilters" style="display:flex;gap:8px"></div>
      </div>
    </div>
    <div id="grid" class="grid"></div>
  </div>

  <div id="detailView" class="detail-view">
    <div class="back-btn" onclick="showMain()">&larr; Back to Overview</div>
    <div id="detailContent"></div>
  </div>
</div>

<script>
(function() {
  const data = REPLACE_DATA_JSON;
  let currentPeriod = '3y';
  let currentRegion = 'All';

  function fp(v){if(v==null)return'—';return(v>=0?'+':'')+(v*100).toFixed(1)+'%'}
  
  window.hc = function(v) {
    if(v == null) return 'var(--bg-card)';
    // Invert: Positive Disconnect (Lag) = Green (Value), Negative (Outperformance) = Red (Expensive)
    let n = Math.min(Math.abs(v) / 0.15, 1);
    let i = 0.2 + n * 0.6;
    return v >= 0 ? `rgba(74, 222, 128, ${i})` : `rgba(251, 113, 133, ${i})`;
  };

  window.render = function() {
    document.getElementById('asOf').innerText = 'AS OF: ' + data.as_of;
    const discKey = 'disc_' + currentPeriod;
    const label = currentPeriod.toUpperCase();
    const filtered = data.countries.filter(d => currentRegion === 'All' || d.region === currentRegion);
    
    document.getElementById('grid').innerHTML = filtered.sort((a,b) => (b[discKey]||-99) - (a[discKey]||-99)).map(d => `
      <div class="card" style="background:${hc(d[discKey])}" onclick="showDetail('${d.ticker}')">
        <div>
          <div class="c-name">${d.country}</div>
          <div class="c-region">${d.region}</div>
        </div>
        <div>
          <div class="c-val">${fp(d[discKey])}</div>
          <div class="c-sub">${label} Disconnect (vs GDP USD)</div>
        </div>
      </div>
    `).join('');
  };

  window.showDetail = function(ticker) {
    const d = data.countries.find(x => x.ticker === ticker);
    document.getElementById('mainView').style.display = 'none';
    document.getElementById('detailView').style.display = 'block';
    
    let html = `
      <div class="detail-header">
        <h1 style="font-size:32px;margin-bottom:4px">${d.country}</h1>
        <p style="color:var(--text-dim);font-family:var(--font-mono)">${d.etf} (${d.ticker}) · ${d.currency}</p>
      </div>
      
      <h3 style="font-size:14px;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px">Short Term Performance</h3>
      <div class="table-wrap"><table><thead><tr><th>Timeframe</th><th>Return</th></tr></thead><tbody>
        ${['1d','1w','1m','ytd'].map(tf => `<tr><td>${tf.toUpperCase()}</td><td style="font-family:var(--font-mono);font-weight:700;color:${d[tf]>=0?'var(--green)':'var(--red)'}">${fp(d[tf])}</td></tr>`).join('')}
      </tbody></table></div>

      <h3 style="font-size:14px;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px">Annual Macro Decomposition</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>Year</th><th>Nominal GDP (USD) %</th><th>Real GDP %</th><th>LCU Return vs USD %</th></tr></thead>
        <tbody>
          ${d.history.filter(h => h.gdp_usd !== null).reverse().map(h => `
            <tr>
              <td>${h.year}</td>
              <td style="font-family:var(--font-mono)">${fp(h.gdp_usd/100)}</td>
              <td style="font-family:var(--font-mono)">${fp(h.gdp_real/100)}</td>
              <td style="font-family:var(--font-mono)">${fp(h.weo_fx/100)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table></div>
    `;
    document.getElementById('detailContent').innerHTML = html;
    window.scrollTo(0,0);
  };

  window.showMain = function() {
    document.getElementById('mainView').style.display = 'block';
    document.getElementById('detailView').style.display = 'none';
  };

  window.setPeriod = function(p, btn) {
    currentPeriod = p;
    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    render();
  };

  window.setRegion = function(r, btn) {
    currentRegion = r;
    document.querySelectorAll('.region-pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    render();
  };

  const regs = ['All', ...data.regions];
  document.getElementById('regionFilters').innerHTML = regs.map(r => `<button class="btn region-pill ${r==='All'?'active':''}" onclick="setRegion('${r}', this)">${r}</button>`).join('');

  render();
})();
</script>
</body>
</html>"""
    with open(output_path, "w") as f: f.write(html_template.replace("REPLACE_DATA_JSON", json.dumps(data)))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--etf-csv", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-csv", default="data/outputs/weo_gdp.csv")
    parser.add_argument("--metadata-csv", default="data/outputs/etf_ticker_metadata.csv")
    parser.add_argument("--output", default="data/outputs/etf_macro_dashboard.html")
    args = parser.parse_args()
    generate_html(build_dashboard_data(args.etf_csv, args.weo_csv, args.metadata_csv), args.output)
    print(f"Drill-down dashboard generated: {args.output}")

if __name__ == "__main__": main()
