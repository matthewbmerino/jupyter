import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
# Import both classes needed
from alpha_vantage.cryptocurrencies import CryptoCurrencies 
from alpha_vantage.timeseries import TimeSeries

def fetch_price_data(symbol, asset_type, start_date="2010-01-01"):
    """Fetches historical price data for a given symbol and asset type using Alpha Vantage."""
    # --- IMPORTANT: Consider using environment variables or a config file for your API key --- 
    api_key = 'BPTOGR49F6YEZ5G2' 
    # --- -------------------------------------------------------------------------------- ---
    
    if api_key == 'YOUR_API_KEY':
        print("WARNING: Please replace 'YOUR_API_KEY' with your actual Alpha Vantage API key in the fetch_price_data function.")
        return pd.DataFrame() 

    data = pd.DataFrame()
    meta_data = {}
    
    try:
        if asset_type == 'crypto':
            print(f"Fetching crypto data for {symbol}...")
            cc = CryptoCurrencies(key=api_key, output_format='pandas')
            # Assume USD market for crypto, user might want to customize this later
            data, meta_data = cc.get_digital_currency_daily(symbol=symbol, market='USD')

            # Find crypto close column - updated logic
            if '4b. close (USD)' in data.columns:
                close_col_name = '4b. close (USD)'
            elif '4. close' in data.columns: # Added check for the observed column name
                close_col_name = '4. close'
            else:
                # Fallback search if primary names aren't found
                close_cols = [col for col in data.columns if 'close' in col.lower() and '(usd)' in col.lower()]
                if not close_cols:
                     # Updated error message to show all possibilities checked
                     raise KeyError(f"No suitable 'close' column ('4b. close (USD)' or '4. close') found for crypto {symbol}. Available: {data.columns.tolist()}")
                close_col_name = close_cols[0]
                
        elif asset_type == 'stock':
            print(f"Fetching stock data for {symbol}...")
            ts = TimeSeries(key=api_key, output_format='pandas')
            # Use get_daily_adjusted for stocks to account for dividends/splits
            data, meta_data = ts.get_daily_adjusted(symbol=symbol, outputsize='full')
            # Find stock close column (prefer adjusted close)
            if '5. adjusted close' in data.columns:
                close_col_name = '5. adjusted close'
            elif '4. close' in data.columns:
                close_col_name = '4. close' # Fallback to non-adjusted close
            else:
                raise KeyError(f"No suitable 'close' or 'adjusted close' column found for stock {symbol}. Available: {data.columns.tolist()}")
        else:
            raise ValueError("Invalid asset_type specified. Use 'crypto' or 'stock'.")

        # --- Common Processing Logic --- 
        print(f"Raw data columns: {data.columns.tolist()}")
        print(f"Using column '{close_col_name}' as closing price.")
        
        # Rename the identified column to 'Close'
        data.rename(columns={close_col_name: 'Close'}, inplace=True)
        
        # Convert index to datetime and sort oldest first
        data.index = pd.to_datetime(data.index)
        data.sort_index(inplace=True)

        # Ensure 'Close' column is numeric
        data['Close'] = pd.to_numeric(data['Close'])
        
        # Filter by start_date 
        data = data[data.index >= pd.to_datetime(start_date)]
        
        if data.empty:
             print(f"Warning: No data found for {symbol} after processing and date filtering.")
             return pd.DataFrame()
             
        print(f"Successfully processed data for {symbol}. Shape: {data.shape}")
        return data[['Close']].copy()
        
    except ValueError as ve:
         # Handle specific known errors like API limits more gracefully if needed
         if "call frequency" in str(ve):
              print(f"Alpha Vantage API Error for {symbol}: {ve}. You might have hit the rate limit.")
         else:
              print(f"Data fetching/processing error for {symbol}: {ve}")
         import traceback
         traceback.print_exc()
         return pd.DataFrame()
    except Exception as e:
        print(f"Unexpected error fetching/processing data for {symbol}: {e}")
        import traceback
        traceback.print_exc()  # Print detailed traceback
        return pd.DataFrame() 

def calculate_stbr(data):
    """Calculates the 20-week SMA and STBR."""
    data['SMA_140D'] = data['Close'].rolling(window=140).mean()
    data['STBR'] = data['Close'] / data['SMA_140D']
    data.dropna(inplace=True)
    return data

def define_risk_levels():
    """Defines risk levels and corresponding colors based on the image legend."""
    levels = {
        "Bearish < 0.5": (-np.inf, 0.5),
        "Bearish 0.5-0.75": (0.5, 0.75),
        "Neutral 0.75-1": (0.75, 1.0),
        "Normal 1-1.25": (1.0, 1.25),
        "Heating Up 1.25-1.50": (1.25, 1.50),
        "Risky 1.50-1.75": (1.50, 1.75),
        "Super Risky 1.75-2": (1.75, 2.0),
        "Bubble Pop > 2": (2.0, np.inf)
    }
    # Colors based approximately on the legend (dark blue to red)
    colors = [
        '#0000FF',  # Dark Blue (< 0.5)
        '#0055FF',  # Medium Blue (0.5-0.75)
        '#00FFFF',  # Cyan (0.75-1)
        '#00FF00',  # Green (1-1.25)
        '#FFFF00',  # Yellow (1.25-1.50)
        '#FFA500',  # Orange (1.50-1.75)
        '#FF4500',  # OrangeRed (1.75-2)
        '#FF0000'   # Red (> 2)
    ]
    return levels, colors

def plot_stbr(data, symbol):
    """Plots the Price and STBR for the given symbol."""
    levels, colors = define_risk_levels()

    fig, ax1 = plt.subplots(figsize=(16, 8))
    fig.patch.set_facecolor('#121417') # Dark background
    ax1.set_facecolor('#121417')

    # Plot BTC Price (Left Axis, Log Scale)
    ax1.set_yscale('log')
    ax1.plot(data.index, data['Close'], label='BTC Price', color='#3498db', linewidth=1.5) # Blue color for price
    ax1.set_ylabel('BTC Price ($) (Log Scale)', color='white')
    ax1.tick_params(axis='y', labelcolor='white')
    ax1.tick_params(axis='x', labelcolor='white')
    ax1.grid(axis='y', linestyle='--', alpha=0.3, color='gray')
    ax1.spines['top'].set_visible(False)
    ax1.spines['left'].set_color('white')
    ax1.spines['bottom'].set_color('white')
    ax1.spines['right'].set_color('white')

    # Create Right Axis for STBR
    ax2 = ax1.twinx()
    ax2.set_ylabel('STBR (Price / 140D SMA)', color='white')
    ax2.tick_params(axis='y', labelcolor='white')
    ax2.spines['top'].set_visible(False)
    ax2.spines['left'].set_color('white')
    ax2.spines['bottom'].set_color('white')
    ax2.spines['right'].set_color('white')

    # Plot STBR colored areas
    level_keys = list(levels.keys())
    norm = mcolors.BoundaryNorm(boundaries=[levels[k][0] for k in level_keys] + [levels[level_keys[-1]][1]], ncolors=len(colors))
    cmap = mcolors.ListedColormap(colors)

    one_line = np.ones_like(data['STBR'].values)

    for i, key in enumerate(level_keys):
        lower_bound, upper_bound = levels[key]
        mask = (data['STBR'] >= lower_bound) & (data['STBR'] < upper_bound)
        
        # Where condition ensures we only fill where the mask is true
        ax2.fill_between(data.index, data['STBR'], one_line, where=mask, 
                         color=colors[i], interpolate=True, alpha=0.8, step=None)

    # Set reasonable limits for STBR axis based on data, maybe 0 to 4?
    min_stbr = data['STBR'].min()
    max_stbr = data['STBR'].max()
    ax2.set_ylim(min(0, min_stbr*1.1), max(max_stbr * 1.1, 2.5)) # Ensure range covers typical values

    # Create custom legend for STBR colors
    legend_handles = [plt.Rectangle((0,0),1,1, color=colors[i]) for i in range(len(colors))]
    ax1.legend(legend_handles, level_keys, loc='lower left', facecolor='#2E2E2E', edgecolor='gray', labelcolor='white', fontsize='small')

    # Add latest value text
    latest_stbr = data['STBR'].iloc[-1]
    latest_stbr_category = ""
    for key, (lower, upper) in levels.items():
        if lower <= latest_stbr < upper:
            latest_stbr_category = key.split(" ")[0] # Get category name like "Bearish", "Risky"
            break
    
    # Updated title to include the symbol
    title_text = f"{symbol} Price vs Short Term Bubble Risk (STBR)\nLatest STBR: {latest_stbr:.3f} ({latest_stbr_category})" 
    ax1.set_title(title_text, color='white', pad=20)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":

    # Get user input
    while True:
        asset_type_input = input("Enter asset type (crypto/stock): ").lower().strip()
        if asset_type_input in ['crypto', 'stock']:
            break
        else:
            print("Invalid asset type. Please enter 'crypto' or 'stock'.")

    symbol_input = input(f"Enter ticker symbol for {asset_type_input} (e.g., {'BTC' if asset_type_input == 'crypto' else 'AAPL'}): ").upper().strip()

    # Fetch data based on user input
    price_data = fetch_price_data(symbol=symbol_input, asset_type=asset_type_input)

    # Check if data fetching was successful and the necessary column exists
    if not price_data.empty and 'Close' in price_data.columns:
        print("Data fetched successfully, proceeding to calculate STBR...")
        stbr_data = calculate_stbr(price_data.copy()) # Pass a copy to avoid SettingWithCopyWarning

        # Also check if calculation resulted in data (dropna might empty it)
        if not stbr_data.empty:
             print("STBR calculated successfully, generating plot...")
             plot_stbr(stbr_data, symbol_input) # Pass symbol to plot function
        else:
            # Explicit message about calculation failure
            print("-" * 30)
            print(f"ERROR: Could not calculate STBR for {symbol_input}.")
            print("Reason: Insufficient historical data (less than 140 days) after fetching and filtering.")
            print("The chart cannot be generated.")
            print("-" * 30)
    elif price_data.empty:
        # Explicit message about fetch failure
        print("-" * 30)
        print(f"ERROR: Failed to fetch data for {symbol_input} from Alpha Vantage.")
        print("Reason: Check API key validity/limits, network connection, or if the symbol exists.")
        print("         See previous messages from the fetch function for more details.")
        print("The chart cannot be generated.")
        print("-" * 30)
    else: # Data fetched, but 'Close' column was missing somehow
         print("-" * 30)
         print(f"ERROR: Fetched data for {symbol_input}, but could not identify the 'Close' price column.")
         print("Reason: The structure of the data from Alpha Vantage might have changed unexpectedly.")
         print("         Check the 'Raw data columns' printed earlier by the fetch function.")
         print("The chart cannot be generated.")
         print("-" * 30) 