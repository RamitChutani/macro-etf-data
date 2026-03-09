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

# Timeframe specs
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

def get_gdp_hurdle(cc, label, maps, latest_year=2025):
    """Get the appropriate GDP growth hurdle for a timeframe."""
    real_map, nominal_lcu_map, nominal_usd_map, country_fx_map, current_usd_map = maps
    
    if label in ["3Y", "5Y", "10Y"]:
        years = int(label[:-1])
        # Simple CAGR calculation for GDP (nominal USD)
        try:
            start_year = latest_year - years
            v_start = current_usd_map.get((cc, start_year))
            v_end = current_usd_map.get((cc, latest_year))
            if v_start and v_end and v_start > 0:
                total_ret = (v_end / v_start) - 1.0
                return cagr_from_total_return(total_ret * 100.0, years)
        except:
            pass
        return nominal_usd_map.get((cc, latest_year)) # Fallback
    
    # For YTD and shorter, use 2025 Nominal GDP Growth as the annual hurdle
    return nominal_usd_map.get((cc, latest_year))

def build_dashboard_data(
    etf_csv: str,
    weo_csv: str,
    metadata_csv: str,
) -> dict:
    prices_raw = pd.read_csv(etf_csv)
    prices_raw["Date"] = pd.to_datetime(prices_raw["Date"], errors="coerce")
    prices_raw = prices_raw.dropna(subset=["Date"]).sort_values("Date")
    
    ticker_to_country = build_ticker_country_map()
    price_columns = choose_price_columns(prices_raw.columns.tolist())
    
    metadata = pd.read_csv(metadata_csv)
    ticker_info = metadata.set_index("ticker").to_dict(orient="index")
    
    gdp_maps = load_gdp_growth_maps(weo_csv)
    (gdp_real_map, _, gdp_nominal_usd_map, country_fx_map, _) = gdp_maps
    
    latest_date = prices_raw["Date"].max()
    as_of_str = latest_date.strftime("%b %d, %Y").upper()
    
    benchmark_list = ["CSPX.L", "VUAA.L", "VUSA.L", "SAUS.L", "XDAX.L"]
    
    benchmarks_data = []
    countries_data = []
    
    for ticker, price_col in price_columns.items():
        country = ticker_to_country.get(ticker, "Unknown")
        region = COUNTRY_TO_REGION.get(country, "Other")
        cc = COUNTRY_TO_ISO3.get(country)
        
        series = prices_raw.set_index("Date")[price_col].dropna()
        if series.empty: continue
            
        start_pt_max = max_start_point(series)
        if start_pt_max is None: continue
            
        end_pt = PricePoint(series.index[-1], float(series.iloc[-1]))
        
        returns = {}
        disconnects = {}
        
        for label, spec in HTML_TIMEFRAME_SPECS:
            if spec == "ytd":
                jan1 = pd.Timestamp(year=end_pt.date.year, month=1, day=1)
                start_pt = last_on_or_before(series, jan1)
            else:
                target = end_pt.date - spec
                start_pt = last_on_or_before(series, target)
                
            if start_pt and start_pt.date >= start_pt_max.date:
                ret = pct_return(start_pt.value, end_pt.value)
                if label in ["3Y", "5Y", "10Y"]:
                    ret = cagr_from_total_return(ret, int(label[:-1]))
                
                returns[label.lower()] = round(ret / 100.0, 4)
                
                # Macro Disconnect = GDP Hurdle - ETF Return
                hurdle = get_gdp_hurdle(cc, label, gdp_maps)
                if hurdle is not None:
                    disconnects[f"disc_{label.lower()}"] = round((hurdle - ret) / 100.0, 4)
                else:
                    disconnects[f"disc_{label.lower()}"] = None
            else:
                returns[label.lower()] = None
                disconnects[f"disc_{label.lower()}"] = None
        
        latest_year = 2025
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
            **disconnects,
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
        "regions": sorted(list(set(COUNTRY_TO_REGION.values())))
    }

def generate_html(data: dict, output_path: str):
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Macro Disconnect Lab</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg-primary:#0a0e17;--bg-secondary:#111827;--bg-card:#151d2e;--bg-card-hover:#1a2540;--border:#1e293b;--border-light:#2a3a52;--text-primary:#e2e8f0;--text-secondary:#94a3b8;--text-muted:#64748b;--accent-green:#22c55e;--accent-red:#ef4444;--accent-blue:#3b82f6;--accent-cyan:#06b6d4;--font-body:'DM Sans',sans-serif;--font-mono:'JetBrains Mono',monospace;--radius:10px}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg-primary);color:var(--text-primary);font-family:var(--font-body);line-height:1.5;overflow-x:hidden}
.header{position:sticky;top:0;z-index:100;background:rgba(10,14,23,0.85);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:16px 32px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.logo{font-family:var(--font-mono);font-size:20px;font-weight:700;background:linear-gradient(135deg,#3b82f6,#8b5cf6,#06b6d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.5px}
.date-badge{font-family:var(--font-mono);font-size:11px;color:var(--accent-cyan);background:rgba(6,182,212,0.1);border:1px solid rgba(6,182,212,0.2);padding:5px 12px;border-radius:20px}
.main{padding:24px 32px 60px;max-width:1600px;margin:0 auto}
.controls{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:20px;margin-bottom:24px}
.control-group{display:flex;align-items:center;gap:12px}
.group-label{font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:700;letter-spacing:0.5px}
.period-toggle, .view-toggle{display:flex;background:var(--bg-card);border-radius:8px;border:1px solid var(--border);overflow:hidden}
.btn{font-family:var(--font-mono);font-size:12px;font-weight:500;padding:7px 14px;border:none;cursor:pointer;background:transparent;color:var(--text-muted);transition:all 0.2s}
.btn.active{background:var(--accent-blue);color:#fff}
.filter-pill{font-size:12px;font-weight:500;padding:6px 14px;border-radius:20px;border:1px solid var(--border);background:var(--bg-card);color:var(--text-muted);cursor:pointer;transition:all 0.2s}
.filter-pill.active{border-color:var(--accent-blue);color:var(--accent-blue);background:rgba(59,130,246,0.1)}
.heatmap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:24px}
.heat-cell{position:relative;border-radius:var(--radius);padding:16px;cursor:pointer;border:1px solid transparent;transition:all 0.25s ease;background:var(--bg-card)}
.heat-cell:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(0,0,0,0.4);border-color:rgba(255,255,255,0.1)}
.cell-name{font-size:14px;font-weight:600;margin-bottom:2px}
.cell-ticker{font-family:var(--font-mono);font-size:10px;color:var(--text-muted);margin-bottom:8px}
.cell-return{font-family:var(--font-mono);font-size:22px;font-weight:700}
.cell-sub{font-size:10px;color:var(--text-muted);margin-top:4px}
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
  <div class="logo">MACRO DISCONNECT LAB</div>
  <div class="date-badge">DATA AS OF: <span id="asOfDate"></span></div>
</div>
<div class="main">
  <div class="controls">
    <div class="control-group">
      <div class="group-label">Hurdle Window</div>
      <div class="period-toggle">
        <button class="btn period-btn" onclick="setPeriod('1d', this)">1D</button>
        <button class="btn period-btn" onclick="setPeriod('1w', this)">1W</button>
        <button class="btn period-btn active" onclick="setPeriod('ytd', this)">YTD</button>
        <button class="btn period-btn" onclick="setPeriod('1y', this)">1Y</button>
        <button class="btn period-btn" onclick="setPeriod('3y', this)">3Y</button>
        <button class="btn period-btn" onclick="setPeriod('5y', this)">5Y</button>
      </div>
    </div>
    
    <div class="control-group">
      <div class="group-label">View</div>
      <div class="view-toggle">
        <button class="btn view-btn active" onclick="setView('grid', this)">Grid</button>
        <button class="btn view-btn" onclick="setView('table', this)">Table</button>
      </div>
    </div>
  </div>

  <div class="control-group" style="margin-bottom:30px">
    <div class="group-label">Region Filter</div>
    <div id="regionFilters" style="display:flex;gap:8px;flex-wrap:wrap"></div>
  </div>
  
  <div id="dashboardContent">
    <h3 style="font-size:14px;color:var(--text-muted);margin-bottom:12px;text-transform:uppercase;">Core Benchmarks</h3>
    <div id="benchmarksGrid" class="heatmap-grid"></div>
    
    <h3 style="font-size:14px;color:var(--text-muted);margin-bottom:12px;text-transform:uppercase;">Country Disconnect (Macro Hurdle - Asset Return)</h3>
    <div id="countriesGrid" class="heatmap-grid"></div>
    <div id="rankingTableContainer" style="display:none"></div>
  </div>
</div>

<div class="tooltip" id="tooltip"></div>
<div class="footer">Positive % = Macro Hurdle > ETF Return (Asset Lags) | Negative % = ETF Return > Macro Hurdle (Outperformance)</div>

<script>
(function() {
  const data = REPLACE_DATA_JSON;
  let currentPeriod = 'ytd';
  let currentRegion = 'All';
  let currentView = 'grid';

  window.fp = function(v) {
    if(v == null) return '—';
    return (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%';
  };

  window.hc = function(v) {
    if(v == null) return 'var(--bg-card)';
    // In Disconnect: Positive (Red) = Bad (Asset lags), Negative (Green) = Good (Asset leads)
    let n = Math.min(Math.abs(v) / 0.15, 1);
    let i = 0.15 + n * 0.55;
    return v >= 0 ? `rgba(239,68,68,${i})` : `rgba(34,197,94,${i})`;
  };

  window.render = function() {
    document.getElementById('asOfDate').innerText = data.as_of;
    const discKey = 'disc_' + currentPeriod;
    
    const filteredCountries = data.countries.filter(d => currentRegion === 'All' || d.region === currentRegion);
    
    const benchmarksGrid = document.getElementById('benchmarksGrid');
    const countriesGrid = document.getElementById('countriesGrid');
    const tableContainer = document.getElementById('rankingTableContainer');
    const content = document.getElementById('dashboardContent');

    if (currentView === 'grid') {
      benchmarksGrid.style.display = 'grid';
      countriesGrid.style.display = 'grid';
      tableContainer.style.display = 'none';
      
      const renderGrid = (el, items) => {
        el.innerHTML = [...items].sort((a,b) => (b[discKey]||-99) - (a[discKey]||-99)).map(d => `
          <div class="heat-cell" style="background:${hc(d[discKey])}" onmouseenter="showTip(event, ${JSON.stringify(d).replace(/"/g, '&quot;')})" onmouseleave="hideTip()">
            <div class="cell-name">${d.country}</div>
            <div class="cell-ticker">${d.ticker}</div>
            <div class="cell-return">${fp(d[discKey])}</div>
            <div class="cell-sub">${d.region}</div>
          </div>
        `).join('');
      };
      renderGrid(benchmarksGrid, data.benchmarks);
      renderGrid(countriesGrid, filteredCountries);
    } else {
      benchmarksGrid.style.display = 'none';
      countriesGrid.style.display = 'none';
      tableContainer.style.display = 'block';
      
      let tableHtml = `<table class="ranking-table"><thead><tr><th>Rank</th><th>Country</th><th>Region</th><th>Disconnect</th><th>ETF Return</th><th>GDP Hurdle</th></tr></thead><tbody>`;
      const allItems = [...data.benchmarks, ...filteredCountries].sort((a,b) => (b[discKey]||-99) - (a[discKey]||-99));
      allItems.forEach((d, i) => {
        const hurdle = (d[discKey] || 0) + (d[currentPeriod] || 0);
        tableHtml += `<tr>
          <td>${i+1}</td>
          <td><b>${d.country}</b> <small style="color:var(--text-muted)">${d.ticker}</small></td>
          <td>${d.region}</td>
          <td style="color:${d[discKey] >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'};font-weight:700">${fp(d[discKey])}</td>
          <td>${fp(d[currentPeriod])}</td>
          <td>${fp(hurdle)}</td>
        </tr>`;
      });
      tableHtml += '</tbody></table>';
      tableContainer.innerHTML = tableHtml;
    }
  };

  window.setPeriod = function(p, btn) {
    currentPeriod = p;
    document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    render();
  };

  window.setView = function(v, btn) {
    currentView = v;
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    render();
  };

  window.setRegion = function(r) {
    currentRegion = r;
    document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    render();
  };

  const tip = document.getElementById('tooltip');
  window.showTip = function(e, d) {
    const hurdle = (d['disc_' + currentPeriod] || 0) + (d[currentPeriod] || 0);
    tip.innerHTML = `
      <div style="font-size:16px;font-weight:700">${d.country}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px">${d.etf}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;border-top:1px solid var(--border);padding-top:10px">
        <div><div style="font-size:10px;color:var(--text-muted)">Disconnect</div><div style="font-weight:700;color:${d['disc_'+currentPeriod] >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'}">${fp(d['disc_'+currentPeriod])}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">ETF Return</div><div style="font-weight:700">${fp(d[currentPeriod])}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">GDP Hurdle</div><div style="font-weight:700">${fp(hurdle)}</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">Region</div><div style="font-weight:700">${d.region}</div></div>
      </div>
    `;
    tip.classList.add('show');
    tip.style.left = (e.clientX + 15) + 'px';
    tip.style.top = (e.clientY + 15) + 'px';
  };
  window.hideTip = function() { tip.classList.remove('show'); };

  const filterEl = document.getElementById('regionFilters');
  const regions = ['All', ...data.regions];
  filterEl.innerHTML = regions.map(r => `<button class="filter-pill ${r==='All'?'active':''}" onclick="setRegion('${r}')">${r}</button>`).join('');

  if (document.readyState === 'complete' || document.readyState === 'interactive') render();
  else window.onload = render;
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
