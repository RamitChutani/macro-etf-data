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
:root{
  --bg-primary:#0f172a;
  --bg-secondary:#1e293b;
  --bg-card:#1e293b;
  --bg-card-hover:#334155;
  --border:#334155;
  --border-light:#475569;
  --text-primary:#f8fafc;
  --text-secondary:#cbd5e1;
  --text-muted:#94a3b8;
  --accent-green:#4ade80;
  --accent-red:#fb7185;
  --accent-blue:#3b82f6;
  --accent-cyan:#22d3ee;
  --font-body:'Inter', 'DM Sans', -apple-system, sans-serif;
  --font-mono:'JetBrains Mono', 'Roboto Mono', monospace;
  --radius:12px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg-primary);color:var(--text-primary);font-family:var(--font-body);line-height:1.6;overflow-x:hidden}
.header{position:sticky;top:0;z-index:100;background:rgba(15, 23, 42, 0.9);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:20px 40px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.logo{font-family:var(--font-mono);font-size:22px;font-weight:800;background:linear-gradient(135deg,#60a5fa,#a78bfa,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-1px}
.date-badge{font-family:var(--font-mono);font-size:12px;color:var(--accent-cyan);background:rgba(34, 211, 238, 0.1);border:1px solid rgba(34, 211, 238, 0.2);padding:6px 14px;border-radius:20px;font-weight:600}
.main{padding:32px 40px 80px;max-width:1600px;margin:0 auto}
.controls{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:24px;margin-bottom:32px;background:rgba(30, 41, 59, 0.5);padding:24px;border-radius:var(--radius);border:1px solid var(--border)}
.control-group{display:flex;flex-direction:column;gap:8px}
.group-label{font-size:12px;color:var(--text-muted);text-transform:uppercase;font-weight:800;letter-spacing:1px}
.period-toggle, .view-toggle{display:flex;background:var(--bg-primary);border-radius:10px;border:1px solid var(--border);overflow:hidden;padding:4px}
.btn{font-family:var(--font-mono);font-size:13px;font-weight:600;padding:8px 18px;border:none;cursor:pointer;background:transparent;color:var(--text-muted);transition:all 0.2s;border-radius:8px}
.btn:hover{color:var(--text-primary)}
.btn.active{background:var(--accent-blue);color:#fff;box-shadow:0 4px 12px rgba(59, 130, 246, 0.3)}
.filter-pill{font-size:13px;font-weight:600;padding:8px 18px;border-radius:30px;border:1px solid var(--border);background:var(--bg-primary);color:var(--text-muted);cursor:pointer;transition:all 0.2s}
.filter-pill:hover{border-color:var(--text-secondary);color:var(--text-primary)}
.filter-pill.active{border-color:var(--accent-blue);color:#fff;background:var(--accent-blue);box-shadow:0 4px 12px rgba(59, 130, 246, 0.2)}
.heatmap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:40px}
.heat-cell{position:relative;border-radius:var(--radius);padding:20px;cursor:pointer;border:1px solid var(--border);transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1);background:var(--bg-card);display:flex;flex-direction:column;justify-content:space-between;min-height:120px}
.heat-cell:hover{transform:translateY(-4px);box-shadow:0 12px 30px rgba(0,0,0,0.5);border-color:var(--border-light)}
.cell-name{font-size:16px;font-weight:700;color:#fff;margin-bottom:4px}
.cell-ticker{font-family:var(--font-mono);font-size:11px;color:rgba(255,255,255,0.6);margin-bottom:12px;letter-spacing:0.5px}
.cell-return{font-family:var(--font-mono);font-size:26px;font-weight:800;color:#fff}
.cell-sub{font-size:11px;color:rgba(255,255,255,0.5);font-weight:600;text-transform:uppercase;letter-spacing:0.5px}
.ranking-table{width:100%;border-collapse:separate;border-spacing:0;background:var(--bg-card);border-radius:var(--radius);overflow:hidden;border:1px solid var(--border);box-shadow:0 10px 25px rgba(0,0,0,0.2)}
.ranking-table th{font-family:var(--font-mono);font-size:12px;text-transform:uppercase;color:var(--text-muted);padding:16px 20px;text-align:left;background:var(--bg-secondary);font-weight:700;letter-spacing:0.5px;border-bottom:1px solid var(--border)}
.ranking-table td{padding:16px 20px;font-size:14px;border-bottom:1px solid var(--border);color:var(--text-secondary)}
.ranking-table tr:last-child td{border-bottom:none}
.ranking-table tr:hover td{background:var(--bg-card-hover);color:var(--text-primary)}
.section-title{font-size:16px;color:var(--text-primary);margin-bottom:16px;text-transform:uppercase;letter-spacing:1.5px;font-weight:800;display:flex;align-items:center;gap:12px}
.section-title::after{content:'';height:1px;background:var(--border);flex:1}
.tooltip{display:none;position:fixed;z-index:200;background:var(--bg-secondary);border:1px solid var(--border-light);border-radius:var(--radius);padding:20px;box-shadow:0 20px 50px rgba(0,0,0,0.6);min-width:320px;pointer-events:none;backdrop-filter:blur(8px)}
.footer{text-align:center;padding:40px;font-size:12px;color:var(--text-muted);border-top:1px solid var(--border);font-family:var(--font-mono);letter-spacing:0.5px}
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
      <div class="group-label">View Mode</div>
      <div class="view-toggle">
        <button class="btn view-btn active" onclick="setView('grid', this)">Grid</button>
        <button class="btn view-btn" onclick="setView('table', this)">Table</button>
      </div>
    </div>

    <div class="control-group">
      <div class="group-label">Region filter</div>
      <div id="regionFilters" style="display:flex;gap:10px;flex-wrap:wrap"></div>
    </div>
  </div>
  
  <div id="dashboardContent">
    <div class="section-title">Core Benchmarks</div>
    <div id="benchmarksGrid" class="heatmap-grid"></div>
    
    <div class="section-title">Country Disconnect (Macro Hurdle - Asset Return)</div>
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
    // Professional color scale: subtle for small moves, saturated for large disconnects
    let n = Math.min(Math.abs(v) / 0.12, 1);
    let i = 0.2 + n * 0.6;
    return v >= 0 ? `rgba(251, 113, 133, ${i})` : `rgba(74, 222, 128, ${i})`;
  };

  window.render = function() {
    document.getElementById('asOfDate').innerText = data.as_of;
    const discKey = 'disc_' + currentPeriod;
    
    const filteredCountries = data.countries.filter(d => currentRegion === 'All' || d.region === currentRegion);
    
    const benchmarksGrid = document.getElementById('benchmarksGrid');
    const countriesGrid = document.getElementById('countriesGrid');
    const tableContainer = document.getElementById('rankingTableContainer');

    if (currentView === 'grid') {
      benchmarksGrid.style.display = 'grid';
      countriesGrid.style.display = 'grid';
      tableContainer.style.display = 'none';
      
      const renderGrid = (el, items) => {
        el.innerHTML = [...items].sort((a,b) => (b[discKey]||-99) - (a[discKey]||-99)).map(d => `
          <div class="heat-cell" style="background:${hc(d[discKey])}" onmouseenter="showTip(event, ${JSON.stringify(d).replace(/"/g, '&quot;')})" onmouseleave="hideTip()">
            <div>
              <div class="cell-name">${d.country}</div>
              <div class="cell-ticker">${d.ticker}</div>
            </div>
            <div>
              <div class="cell-return">${fp(d[discKey])}</div>
              <div class="cell-sub">${d.region}</div>
            </div>
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
          <td style="color:var(--text-primary);font-weight:700">${d.country} <small style="color:var(--text-muted);font-family:var(--font-mono);margin-left:8px">${d.ticker}</small></td>
          <td>${d.region}</td>
          <td style="color:${d[discKey] >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'};font-weight:800;font-family:var(--font-mono)">${fp(d[discKey])}</td>
          <td style="font-family:var(--font-mono)">${fp(d[currentPeriod])}</td>
          <td style="font-family:var(--font-mono)">${fp(hurdle)}</td>
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
    const disc = d['disc_' + currentPeriod];
    tip.innerHTML = `
      <div style="font-size:18px;font-weight:800;color:#fff;margin-bottom:4px">${d.country}</div>
      <div style="font-size:13px;color:var(--text-muted);margin-bottom:16px;font-family:var(--font-mono)">${d.etf}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;border-top:1px solid var(--border);padding-top:16px">
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:700">Disconnect</div>
          <div style="font-size:20px;font-weight:800;color:${disc >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'};font-family:var(--font-mono)">${fp(disc)}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:700">ETF Return</div>
          <div style="font-size:20px;font-weight:800;color:#fff;font-family:var(--font-mono)">${fp(d[currentPeriod])}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:700">GDP Hurdle</div>
          <div style="font-size:16px;font-weight:700;color:var(--text-secondary);font-family:var(--font-mono)">${fp(hurdle)}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;font-weight:700">Region</div>
          <div style="font-size:16px;font-weight:700;color:var(--text-secondary)">${d.region}</div>
        </div>
      </div>
    `;
    tip.classList.add('show');
    tip.style.left = (e.clientX + 20) + 'px';
    tip.style.top = (e.clientY + 20) + 'px';
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
