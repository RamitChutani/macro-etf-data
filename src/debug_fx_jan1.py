import pandas as pd
import sys
import os

# Mock the logic from src/build_combined_etf_weo.py
def debug_compute_returns(eur_series, min_year, max_year):
    # Get first trading day for each year
    first_days = eur_series.to_frame(name="fx").assign(year=eur_series.index.year).groupby("year").head(1)
    
    # Shift back to get previous Jan 1st for calculating current year return
    first_days["prev_jan1_fx"] = first_days["fx"].shift(1)
    first_days["jan1_fx_pct"] = ((first_days["fx"] / first_days["prev_jan1_fx"]) - 1.0) * 100.0
    
    # Shift forward to assign the return to the year it happens in
    first_days["fx_over_year_pct"] = first_days["jan1_fx_pct"].shift(-1)
    
    return first_days

def main():
    df = pd.read_csv('data/outputs/fx_prices.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    eur = df[df['currency'] == 'EUR'].sort_values('Date').set_index('Date')['price_usd']

    # Manual check
    jan1_2024 = eur[eur.index >= '2024-01-01'].iloc[0]
    jan1_2025 = eur[eur.index >= '2025-01-01'].iloc[0]
    manual_ret = (jan1_2025 / jan1_2024 - 1.0) * 100.0
    
    print(f"Manual 2024 (Jan 1 '24 to Jan 1 '25): {manual_ret:.4f}%")
    
    debug_df = debug_compute_returns(eur, 2020, 2025)
    print("\nDebug DataFrame:")
    print(debug_df.tail(5))
    
    val_2024 = debug_df.loc[debug_df.index.year == 2024, "fx_over_year_pct"].values[0]
    print(f"\nScript Value for 2024: {val_2024:.4f}%")
    
    if abs(manual_ret - val_2024) < 1e-6:
        print("\nSUCCESS: Manual matches Script.")
    else:
        print("\nFAILURE: Discrepancy detected.")

if __name__ == "__main__":
    main()
