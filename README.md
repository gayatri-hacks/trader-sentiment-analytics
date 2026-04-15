# Trader Sentiment Analytics

An exploratory data analysis examining how cryptocurrency traders perform across different market sentiment regimes, using the Bitcoin Fear & Greed Index as a sentiment indicator.

## Overview

This project analyzes **211,224+ trades** from the Hyperliquid exchange (2023-2025) and correlates trader profitability with market sentiment. The analysis reveals actionable insights about trading behavior during Fear, Neutral, and Greed periods—identifying which strategies work best when markets are euphoric vs panicked.

## Dataset

- **Historical Trades:** Hyperliquid exchange trade data (May 2023 - May 2025)
  - 211,224 total trades
  - 104,408 closed PnL trades
  - 32 unique traders
  - 246 crypto assets
  
- **Sentiment Index:** Bitcoin Fear & Greed Index (Crypto Fear Index)
  - 5 classifications: Extreme Fear, Fear, Neutral, Greed, Extreme Greed
  - 100% coverage across trade dates

## Key Findings

### 📊 PnL Performance by Sentiment
- **Fear periods:** Highest mean PnL per trade ($113)
- **Extreme Greed:** Highest win rate (89%) but lower per-trade profitability
- **Regime Shift Days:** ~8% higher mean PnL ($103 vs $96) — detecting sentiment transitions is profitable

### 📈 Buy vs Sell Strategy
- **During Fear:** BUY trades outperform ($210 avg) — panic buying captures dips
- **During Greed:** SELL trades dominate ($176 avg) — shorting euphoria extracts value
- **Contrarian edge:** Confirmed as traders profit most when fading sentiment extremes

### 🎯 Trader Archetypes
- **Contrarian Traders:** Profit more in Fear periods (buying low)
- **Momentum Traders:** Profit more in Greed periods (riding rallies)
- **Finding:** Contrarian traders show higher total PnL on average

### 💎 Asset-Specific Insights
- **SOL:** Momentum favorite ($891 avg in Greed)
- **ETH:** Safe haven ($473 in Fear, $350 in Extreme Fear)
- **TRUMP:** News-driven volatility (not sentiment-correlated)
- **FARTCOIN:** Loses consistently during Fear (avoid in downturns)

## Project Structure

```
analysis.ipynb
├── Section 1: Data Loading & Preparation
│   └── Load Fear/Greed and trade data, merge on dates
├── Section 2: Core Analysis - PnL & Win Rate by Sentiment
│   └── Sentiment regime performance metrics
├── Section 3: Directional Analysis - Buy vs Sell
│   └── Long vs short performance across sentiment
├── Section 4: Trader Archetypes
│   └── Contrarian vs Momentum classification
├── Section 5: Asset Sensitivity
│   └── Individual coin performance heatmap
└── Section 6: Regime Shift Analysis
    └── Early sentiment transition detection
```

## Dependencies

```
pandas>=2.0
numpy>=1.26
matplotlib>=3.8
seaborn>=0.12
python>=3.9
```

## Usage

### Running the Analysis

```bash
# Install dependencies
pip install -r requirements.txt

# Run notebook in Jupyter
jupyter notebook analysis.ipynb
```

### Loading Data

Place these CSV files in the project directory:
- `fear_greed_index.csv` — Crypto Fear & Greed Index (date, classification, value)
- `historical_data (1).csv` — Hyperliquid trade data (Timestamp IST, Account, Coin, Side, Closed PnL, etc.)

## Visualization Overview

1. **PnL by Sentiment** — Stacked bar charts showing mean PnL and win rates
2. **Buy vs Sell Performance** — Directional strategy comparison across regimes
3. **Trader Type Scatterplot** — Fear PnL vs Greed PnL highlighting trader archetypes
4. **Asset Heatmap** — Coin-specific profitability across sentiment regimes
5. **Regime Shift Impact** — Mean PnL on classification transition days

## Key Actionable Signals

✅ **Buy during Fear** — Highest absolute returns  
✅ **Sell into Greed** — High win rates on shorts  
✅ **Watch Sentiment Transitions** — Regime shifts = 8% PnL uplift  
✅ **Size positions by sentiment** — Fear allows larger risk, Greed caps exposure  
✅ **Match strategy to asset** — SOL for momentum, ETH as hedge  

## Author Notes

This analysis was created as a data science assignment examining the Hyperliquid exchange. The correlations identified suggest that **market sentiment drives measurable differences in trader profitability**, making sentiment analysis a valuable component of trading systems.

## License

MIT License — See LICENSE file for details

## Contact & Questions

For insights, methodology questions, or dataset inquiries, please open an issue or discussion.

---

**Last Updated:** April 2026  
**Data Range:** May 2023 - May 2025  
**Analysis Focus:** Sentiment-driven trading behavior in crypto markets
