import yfinance as yf
import requests
from datetime import datetime
import logging

# Configure logging to capture errors gracefully without crashing the app
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

def fetch_crypto_price(coin_id="bitcoin", currency="usd"):
    """Fetches real-time crypto price using CoinGecko's free public API."""
    try:
        # Correct url
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={currency}"
        # Wrong url -- Just for testing
        # url = f"https://api.coingecko.com/api/v3/fake_endpoint"
        # Adding a timeout is crucial for robust data pipelines
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Raises an HTTPError for bad responses
        data = response.json()
        return data[coin_id][currency]
    except Exception as e:
        logging.error(f"Failed to fetch {coin_id} price: {e}")
        return None

def fetch_yahoo_finance_price(ticker_symbol):
    """Fetches real-time market data using Yahoo Finance."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        # fast_info is significantly faster and more reliable than downloading historical data
        price = ticker.fast_info['lastPrice']
        return price
    except Exception as e:
        logging.error(f"Failed to fetch {ticker_symbol} price: {e}")
        return None

def main():
    # Fetch timestamp and format it
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nAsset Prices - fetched at {timestamp}\n")
    
    # Header format
    print("-" * 45)
    print(f"| {'Asset':<10} | {'Price':<15} | {'Currency':<10} |")
    print("-" * 45)

    # 1. Fetch Crypto: Bitcoin
    btc_price = fetch_crypto_price("bitcoin", "usd")
    btc_display = f"{btc_price:,.2f}" if btc_price is not None else "ERROR"
    print(f"| {'BTC':<10} | {btc_display:>15} | {'USD':<10} |")

    # 2. Fetch Index: NIFTY 50 (^NSEI is the Yahoo Finance ticker)
    nifty_price = fetch_yahoo_finance_price("^NSEI")
    nifty_display = f"{nifty_price:,.2f}" if nifty_price is not None else "ERROR"
    print(f"| {'NIFTY':<10} | {nifty_display:>15} | {'INR':<10} |")

    # 3. Fetch Commodity: GOLD (GC=F is the Yahoo Finance ticker for Gold Futures)
    gold_price = fetch_yahoo_finance_price("GC=F")
    gold_display = f"{gold_price:,.2f}" if gold_price is not None else "ERROR"
    # Note: Yahoo Gold Futures are typically quoted in USD per Ounce
    print(f"| {'GOLD':<10} | {gold_display:>15} | {'USD/oz':<10} |")

    print("-" * 45)
    print("\n")

if __name__ == "__main__":
    main()