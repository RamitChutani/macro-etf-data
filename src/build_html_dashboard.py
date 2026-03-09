#!/usr/bin/env python3
"""Build a modern, interactive HTML dashboard for ETF vs Macro data."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from dataclasses import dataclass

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

# Enhanced timeframe list for HTML dashboard
HTML_TIMEFRAME_SPECS = [
    ("1D", pd.DateOffset(days=1)),
    ("1W", pd.DateOffset(weeks=1)),
    ("1M", pd.DateOffset(months=1)),
    ("3M", pd.DateOffset(months=3)),
    ("6M", pd.DateOffset(months=6)),
    ("YTD", "ytd"),
    ("1Y", pd.DateOffset(years=1)),
    ("3Y", pd.DateOffset(years=3)),
    ("5Y", pd.DateOffset(years=5)),
    ("10Y", pd.DateOffset(years=10)),
]

def build_dashboard_data(
    etf_csv: str,
    weo_csv: str,
    metadata_csv: str,
) -> dict:
    """Calculate all returns and prepare JSON data for HTML template."""
    prices_raw = pd.read_csv(etf_csv)
    prices_raw["Date"] = pd.to_datetime(prices_raw["Date"], errors="coerce")
    prices_raw = prices_raw.dropna(subset=["Date"]).sort_values("Date")
    
    ticker_to_country = build_ticker_country_map()
    price_columns = choose_price_columns(prices_raw.columns.tolist())
    
    metadata = pd.read_csv(metadata_csv)
    ticker_info = metadata.set_index("ticker").to_dict(orient="index")
    
    (
        gdp_real_map,
        gdp_nominal_lcu_map,
        gdp_nominal_usd_map,
        country_fx_map,
        current_usd_map,
    ) = load_gdp_growth_maps(weo_csv)
    
    # Identify the latest complete data date
    latest_date = prices_raw["Date"].max()
    as_of_str = latest_date.strftime("%b %d, %Y").upper()
    
    # Benchmark Tickers (Defaults if they exist in our data)
    benchmark_list = ["CSPX.L", "VUAA.L", "VUSA.L", "SAUS.L", "XDAX.L"]
    
    benchmarks_data = []
    countries_data = []
    
    for ticker, price_col in price_columns.items():
        country = ticker_to_country.get(ticker, "Unknown")
        region = COUNTRY_TO_REGION.get(country, "Other")
        
        series = prices_raw.set_index("Date")[price_col].dropna()
        if series.empty:
            continue
            
        # Filter out bad launch prints
        start_pt_max = max_start_point(series)
        if start_pt_max is None:
            continue
            
        end_pt = PricePoint(series.index[-1], float(series.iloc[-1]))
        
        # Calculate returns for each timeframe
        returns = {}
        for label, spec in HTML_TIMEFRAME_SPECS:
            if spec == "ytd":
                jan1 = pd.Timestamp(year=end_pt.date.year, month=1, day=1)
                start_pt = last_on_or_before(series, jan1)
            else:
                target = end_pt.date - spec
                start_pt = last_on_or_before(series, target)
                
            if start_pt and start_pt.date >= start_pt_max.date:
                ret = pct_return(start_pt.value, end_pt.value)
                # Annualize 3Y+
                if label in ["3Y", "5Y", "10Y"]:
                    years = int(label[:-1])
                    ret = cagr_from_total_return(ret, years)
                returns[label.lower()] = round(ret / 100.0, 4)
            else:
                returns[label.lower()] = None
        
        # Get latest Macro Data for Tooltips
        cc = COUNTRY_TO_ISO3.get(country)
        
        latest_year = 2025 # Baseline
        macro = {
            "gdp_real": gdp_real_map.get((cc, latest_year)),
            "gdp_nominal_usd": gdp_nominal_usd_map.get((cc, latest_year)),
            "lcu_return": country_fx_map.get((cc, latest_year)),
        }
        
        entry = {
            "ticker": ticker,
            "country": country,
            "etf": ticker_info.get(ticker, {}).get("long_name", ticker),
            "region": region,
            "currency": ticker_info.get(ticker, {}).get("currency", "USD"),
            **returns,
            "macro": macro
        }
        
        if ticker in benchmark_list:
            benchmarks_data.append(entry)
        else:
            countries_data.append(entry)
            
    return {
        "as_of": as_of_str,
        "benchmarks": benchmarks_data,
        "countries": countries_data,
    }

def generate_html(data: dict, output_path: str):
    """Inject data into HTML template and save."""
    
    # Simplified modern dark template
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ETF vs Macro Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg-primary:#0a0e17;--bg-secondary:#111827;--bg-card:#151d2e;--bg-card-hover:#1a2540;--border:#1e293b;--border-light:#2a3a52;--text-primary:#e2e8f0;--text-secondary:#94a3b8;--text-muted:#64748b;--accent-green:#22c55e;--accent-red:#ef4444;--accent-blue:#3b82f6;--accent-cyan:#06b6d4;--region-americas:#f59e0b;--region-europe:#3b82f6;--region-asia:#10b981;--region-mea:#f43f5e;--region-oceania:#8b5cf6;--font-body:'DM Sans',sans-serif;--font-mono:'JetBrains Mono',monospace;--radius:10px}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg-primary);color:var(--text-primary);font-family:var(--font-body);line-height:1.5;overflow-x:hidden}
.header{position:sticky;top:0;z-index:100;background:rgba(10,14,23,0.85);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:16px 32px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.logo{font-family:var(--font-mono);font-size:20px;font-weight:700;background:linear-gradient(135deg,#3b82f6,#8b5cf6,#06b6d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.5px}
.date-badge{font-family:var(--font-mono);font-size:11px;color:var(--accent-cyan);background:rgba(6,182,212,0.1);border:1px solid rgba(6,182,212,0.2);padding:5px 12px;border-radius:20px}
.main{padding:24px 32px 60px;max-width:1600px;margin:0 auto}
.controls{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:20px}
.period-toggle{display:flex;background:var(--bg-card);border-radius:8px;border:1px solid var(--border);overflow:hidden}
.period-btn{font-family:var(--font-mono);font-size:12px;font-weight:500;padding:7px 16px;border:none;cursor:pointer;background:transparent;color:var(--text-muted);transition:all 0.2s}
.period-btn.active{background:var(--accent-blue);color:#fff}
.heatmap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:24px}
.heat-cell{position:relative;border-radius:var(--radius);padding:16px;cursor:pointer;border:1px solid transparent;transition:all 0.25s ease;background:var(--bg-card)}
.heat-cell:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(0,0,0,0.4);border-color:rgba(255,255,255,0.1)}
.cell-name{font-size:14px;font-weight:600;margin-bottom:2px}
.cell-ticker{font-family:var(--font-mono);font-size:10px;color:var(--text-muted);margin-bottom:8px}
.cell-return{font-family:var(--font-mono);font-size:22px;font-weight:700}
.cell-sub{font-size:10px;color:var(--text-muted);margin-top:4px}
.stat-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:20px}
.ranking-table{width:100%;border-collapse:collapse;background:var(--bg-card);border-radius:var(--radius);overflow:hidden;border:1px solid var(--border)}
.ranking-table th{font-family:var(--font-mono);font-size:11px;text-transform:uppercase;color:var(--text-muted);padding:12px 16px;text-align:left;background:var(--bg-secondary)}
.ranking-table td{padding:12px 16px;font-size:13px;border-bottom:1px solid var(--border)}
.tooltip{display:none;position:fixed;z-index:200;background:var(--bg-card);border:1px solid var(--border-light);border-radius:var(--radius);padding:16px;box-shadow:0 12px 40px rgba(0,0,0,0.5);min-width:280px;pointer-events:none}
.tooltip.show{display:block}
.footer{text-align:center;padding:24px;font-size:11px;color:var(--text-muted);border-top:1px solid var(--border);font-family:var(--font-mono)}
</style>
</head>
<body>
<div class="header">
  <div class="logo">MACRO ETF LAB</div>
  <div class="date-badge">DATA AS OF: <span id="asOfDate"></span></div>
</div>
<div class="main">
  <div class="controls">
    <div class="period-toggle">
      <button class="period-btn" onclick="setPeriod('1d', this)">1D</button>
      <button class="period-btn" onclick="setPeriod('1w', this)">1W</button>
      <button class="period-btn active" onclick="setPeriod('ytd', this)">YTD</button>
      <button class="period-btn" onclick="setPeriod('1y', this)">1Y</button>
      <button class="period-btn" onclick="setPeriod('3y', this)">3Y</button>
      <button class="period-btn" onclick="setPeriod('5y', this)">5Y</button>
    </div>
  </div>
  
  <h3 style="font-size:14px;color:var(--text-muted);margin-bottom:12px;text-transform:uppercase;">Core Tickers</h3>
  <div id="benchmarksGrid" class="heatmap-grid"></div>
  
  <h3 style="font-size:14px;color:var(--text-muted);margin-bottom:12px;text-transform:uppercase;">Country Performance</h3>
  <div id="countriesGrid" class="heatmap-grid"></div>
  
  <h3 style="font-size:14px;color:var(--text-muted);margin-bottom:12px;text-transform:uppercase;">Full Rankings</h3>
  <div id="rankingTableContainer"></div>
</div>

<div class="tooltip" id="tooltip"></div>
<div class="footer">ETF returns vs WEO Macro Metrics — Created by Macro ETF Pipeline</div>

<script>
(function() {
  const dashboardData = REPLACE_DATA_JSON;
  let currentPeriod = 'ytd';

  window.fp = function(v) {
    if(v == null) return '—';
    return (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%';
  };

  window.hc = function(v) {
    if(v == null) return 'var(--bg-card)';
    let n = Math.min(Math.abs(v) / 0.15, 1);
    let i = 0.15 + n * 0.55;
    return v >= 0 ? `rgba(34,197,94,${i})` : `rgba(239,68,68,${i})`;
  };

  window.render = function() {
    try {
      const asOfEl = document.getElementById('asOfDate');
      if (asOfEl) asOfEl.innerText = dashboardData.as_of;
      
      const renderGrid = (id, items) => {
        const gridEl = document.getElementById(id);
        if (!gridEl) return;
        const sorted = [...items].sort((a, b) => (b[currentPeriod] || -99) - (a[currentPeriod] || -99));
        gridEl.innerHTML = sorted.map(d => `
          <div class="heat-cell" style="background:${hc(d[currentPeriod])}" onmouseenter="showTip(event, ${JSON.stringify(d).replace(/"/g, '&quot;')})" onmouseleave="hideTip()">
            <div class="cell-name">${d.country}</div>
            <div class="cell-ticker">${d.ticker} · ${d.region}</div>
            <div class="cell-return">${fp(d[currentPeriod])}</div>
            <div class="cell-sub">${d.region}</div>
          </div>
        `).join('');
      };
      
      renderGrid('benchmarksGrid', dashboardData.benchmarks);
      renderGrid('countriesGrid', dashboardData.countries);
      
      const tableContainer = document.getElementById('rankingTableContainer');
      if (tableContainer) {
        let tableHtml = `<table class="ranking-table"><thead><tr><th>Rank</th><th>Country</th><th>Ticker</th><th>Region</th><th>YTD</th><th>1Y</th><th>3Y (Ann)</th><th>GDP Real (2025)</th></tr></thead><tbody>`;
        const allItems = [...dashboardData.benchmarks, ...dashboardData.countries];
        allItems.sort((a, b) => (b[currentPeriod] || -99) - (a[currentPeriod] || -99)).forEach((d, i) => {
          tableHtml += `<tr>
            <td>${i + 1}</td>
            <td><b>${d.country}</b></td>
            <td><code>${d.ticker}</code></td>
            <td>${d.region}</td>
            <td style="color:${d['ytd'] >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${fp(d['ytd'])}</td>
            <td style="color:${d['y1'] >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${fp(d['y1'])}</td>
            <td style="color:${d['3y'] >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${fp(d['3y'])}</td>
            <td>${d.macro.gdp_real ? d.macro.gdp_real.toFixed(1) + '%' : '—'}</td>
          </tr>`;
        });
        tableHtml += '</tbody></table>';
        tableContainer.innerHTML = tableHtml;
      }
    } catch (err) {
      console.error("Render error:", err);
    }
  };

  window.setPeriod = function(p, btn) {
    currentPeriod = p;
    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    render();
  };

  const tip = document.getElementById('tooltip');
  window.showTip = function(e, d) {
    if (!tip) return;
    tip.innerHTML = `
      <div style="font-size:16px;font-weight:700">${d.country}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px">${d.etf}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;border-top:1px solid var(--border);padding-top:10px">
        <div><div style="font-size:10px;color:var(--text-muted)">YTD Return</div><div style="font-weight:700">${fp(d['ytd'])}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">1Y Return</div><div style="font-weight:700">${fp(d['y1'])}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">GDP Real (2025)</div><div style="font-weight:700">${d.macro.gdp_real ? d.macro.gdp_real.toFixed(1) + '%' : '—'}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">LCU Return (2025)</div><div style="font-weight:700">${fp(dashboardData.macro ? d.macro.lcu_return / 100 : null)}</div></div>
      </div>
    `;
    tip.classList.add('show');
    tip.style.left = (e.clientX + 15) + 'px';
    tip.style.top = (e.clientY + 15) + 'px';
  };
  
  window.hideTip = function() { if (tip) tip.classList.remove('show'); };

  // Initial render
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
</script>
</body>
</html>"""
    
    html_content = html_template.replace("REPLACE_DATA_JSON", json.dumps(data))
    with open(output_path, "w") as f:
        f.write(html_content)

def main():
    parser = argparse.ArgumentParser(description="Generate interactive HTML dashboard.")
    parser.add_argument("--etf-csv", default="data/outputs/etf_prices.csv")
    parser.add_argument("--weo-csv", default="data/outputs/weo_gdp.csv")
    parser.add_argument("--metadata-csv", default="data/outputs/etf_ticker_metadata.csv")
    parser.add_argument("--output", default="data/outputs/etf_macro_dashboard.html")
    args = parser.parse_args()
    
    data = build_dashboard_data(args.etf_csv, args.weo_csv, args.metadata_csv)
    generate_html(data, args.output)
    print(f"HTML dashboard generated: {args.output}")

if __name__ == "__main__":
    main()
