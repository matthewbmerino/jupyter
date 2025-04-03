import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify
import requests # Added for Alpha Vantage API calls
from stbr_model import fetch_price_data, calculate_stbr, define_risk_levels
import plotly.graph_objects as go
import plotly.io as pio

app = Flask(__name__)

# --- Alpha Vantage API Key (Consider Environment Variable!) ---
ALPHA_VANTAGE_API_KEY = 'BPTOGR49F6YEZ5G2' 
# --- ------------------------------------------------------ ---

# --- Predefined Ticker List --- 
# In a real app, load this from a file, database, or dynamic source
AVAILABLE_TICKERS = {
    'stock': [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'JPM', 'JNJ',
        'V', 'PG', 'UNH', 'HD', 'MA', 'BAC', 'DIS', 'PYPL', 'NFLX', 'CRM'
    ],
    'crypto': [
        'BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'SHIB', 'AVAX', 'DOT', 'MATIC',
        'LTC', 'TRX', 'LINK', 'BCH', 'XLM', 'ATOM', 'NEAR', 'ALGO', 'VET', 'ICP'
    ],
    'cash': ['CASH'] # Added CASH ticker
}
# --- ----------------------- ---

# --- Signal Colors ---
SIGNAL_COLORS = {
    "Rotate In": '#00FF00',  # Green
    "Hold": '#FFFF00',       # Yellow
    "Rotate Out": '#FF4500', # OrangeRed / Red
    "Cash": '#AAAAAA'        # Grey for Cash
}
# --- -------------- ---

@app.route('/')
def index():
    return render_template('index.html')

# Helper function to get color for a single STBR value
def get_color_for_stbr(value, levels, colors):
    for i, (key, (lower, upper)) in enumerate(levels.items()):
        if lower <= value < upper:
            return colors[i]
    return 'grey' # Default color if somehow not found

# Helper function to get STBR category name
def get_stbr_category(value, levels):
    for key, (lower, upper) in levels.items():
        if lower <= value < upper:
            return key
    return "N/A"

# Helper function to determine rotation signal based on STBR category
def get_rotation_signal(stbr_category):
    if "Risky" in stbr_category or "Bubble" in stbr_category:
        return "Rotate Out"
    elif "Bearish" in stbr_category:
        return "Rotate In"
    # Explicitly check for Cash category if we add it later, otherwise default to Hold
    elif stbr_category == "Cash":
        return "Cash" # Keep cash signal distinct if needed
    else: # Neutral, Normal, Heating Up
        return "Hold"

@app.route('/get_available_tickers')
def get_available_tickers():
    asset_type = request.args.get('asset_type', 'crypto') # Default to crypto or get from request
    tickers = AVAILABLE_TICKERS.get(asset_type, [])
    return jsonify(tickers)

# --- New Endpoint for Alpha Vantage Symbol Search ---
@app.route('/search_symbol')
def search_symbol():
    keywords = request.args.get('keywords', '')
    asset_type = request.args.get('asset_type', 'stock') # Primarily for stocks
    print(f"Searching AV for: {keywords} (Type: {asset_type})")

    if not keywords:
        return jsonify({"bestMatches": []}) # Return empty list if no keywords
        
    # Only search stocks for now, crypto search isn't directly supported this way
    # and cash is handled locally.
    if asset_type != 'stock':
         # Return empty or maybe filter AVAILABLE_TICKERS[asset_type] if needed
         tickers = AVAILABLE_TICKERS.get(asset_type, [])
         filtered = [t for t in tickers if t.startswith(keywords.upper())]
         # Format like AV results for consistency
         matches = [{ "1. symbol": t, "2. name": "" } for t in filtered]
         return jsonify({"bestMatches": matches})

    try:
        url = f'https://www.alphavantage.co/query'
        params = {
            'function': 'SYMBOL_SEARCH',
            'keywords': keywords,
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        response = requests.get(url, params=params)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        
        # Check for API limit error message
        if "Note" in data and "API call frequency" in data["Note"]:
             print("Alpha Vantage API limit reached during search.")
             # Return an empty list or a specific error structure
             return jsonify({"bestMatches": [], "error": "API limit reached"}), 503 # Service Unavailable
             
        # Check if 'bestMatches' exists and is a list
        if "bestMatches" in data and isinstance(data["bestMatches"], list):
            print(f"AV Search successful, found {len(data['bestMatches'])} matches.")
            # Filter out non-US markets if desired (optional)
            # data["bestMatches"] = [m for m in data["bestMatches"] if m.get("4. region") == "United States"]
            return jsonify(data) 
        else:
            print(f"Unexpected AV search response format: {data}")
            return jsonify({"bestMatches": []})

    except requests.exceptions.RequestException as e:
        print(f"Error calling Alpha Vantage Search API: {e}")
        return jsonify({"error": f"Failed to contact symbol search service: {e}"}), 500
    except Exception as e:
        print(f"Unexpected error during symbol search: {e}")
        return jsonify({"error": "An unexpected error occurred during symbol search."}), 500
# --- ------------------------------------------- ---

@app.route('/get_chart_data', methods=['POST'])
def get_chart_data():
    symbol = request.form.get('symbol', 'BTC').upper()
    asset_type = request.form.get('asset_type', 'crypto')

    # Prevent analyzing CASH directly in the single ticker view
    if symbol == 'CASH' and asset_type == 'cash':
         return jsonify({'error': 'Cannot analyze CASH directly. Add it to your portfolio instead.'}), 400

    print(f"Received request: symbol={symbol}, type={asset_type}")

    # Fetch and calculate data
    price_data = fetch_price_data(symbol=symbol, asset_type=asset_type)

    if price_data.empty:
        print("Failed to fetch price data.")
        return jsonify({'error': f'Failed to fetch data for {symbol}. Check symbol, API key, or network connection.'}), 400

    if 'Close' not in price_data.columns:
        print("'Close' column missing after fetch.")
        return jsonify({'error': 'Data processing error: Missing Close price information after fetch.'}), 500

    stbr_data = calculate_stbr(price_data.copy())

    if stbr_data.empty:
        print("STBR calculation resulted in empty data.")
        return jsonify({'error': 'Not enough historical data (need > 140 days) to calculate STBR.'}), 400

    print(f"Successfully processed STBR data for {symbol}. Shape: {stbr_data.shape}")

    # Prepare data for Plotly (Reverted)
    levels, colors = define_risk_levels()
    level_keys = list(levels.keys())

    fig = go.Figure()

    # Add Price trace (Left Y-axis, Log scale)
    fig.add_trace(go.Scatter(x=stbr_data.index,
                             y=stbr_data['Close'],
                             mode='lines',
                             name=f'{symbol} Price',
                             line=dict(color='#3498db', width=1.5),
                             yaxis='y1',
                             showlegend=False)) # Hide price from legend like target

    # --- Create STBR Bars relative to 1.0 --- 
    # Calculate bar properties
    stbr_values = stbr_data['STBR']
    bar_colors = [get_color_for_stbr(val, levels, colors) for val in stbr_values]
    bar_base = 1.0
    bar_y_values = stbr_values # The actual value determines the color and where the bar ends

    # Add the STBR bars
    fig.add_trace(go.Bar(
        x=stbr_data.index,
        y=bar_y_values - bar_base, # Height relative to base
        base=bar_base,            # Set base of bars to 1.0 on y2
        marker_color=bar_colors,  # Assign color to each bar
        name='STBR Levels',       # Name for hover (won't show in legend by default)
        yaxis='y2',
        showlegend=False,
        hoverinfo='skip' # Optional: Hide hover info for bars if cluttered
    ))

    # --- Create Dummy Traces for Legend --- 
    for i, key in enumerate(level_keys):
        fig.add_trace(go.Scatter(
            x=[None], # No data points needed
            y=[None],
            mode='markers',
            marker=dict(color=colors[i], size=10, symbol='square'),
            name=key, # This name will appear in the legend
            yaxis='y1' # Assign to a y-axis, doesn't matter which for legend
        ))

    # Update layout
    latest_stbr = stbr_data['STBR'].iloc[-1]
    latest_date = stbr_data.index[-1].strftime('%Y-%m-%d')
    latest_stbr_category_short = "N/A"
    for key, (lower, upper) in levels.items():
        if lower <= latest_stbr < upper:
            latest_stbr_category_short = key.split(" ")[0] # Get short category name like "Neutral"
            break
            
    title_text = (f"{symbol} Price vs Short Term Bubble Risk (STBR)<br>" +
                  f"Latest STBR: {latest_stbr:.3f} ({latest_stbr_category_short})") # Use short category

    fig.update_layout(
        title=dict(text=title_text, x=0.5, y=0.95, xanchor='center'), # Center title, adjust vertical position
        xaxis_title=None, # No x-axis title in target image
        yaxis=dict(
            title=f'{symbol} Price ($) (Log Scale)', # Keep title, add log scale text back
            type='log',
            side='left',
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            gridwidth=0.5,
            zeroline=False
        ),
        yaxis2=dict(
            title='STBR (Price / 140D SMA)',
            overlaying='y',
            side='right',
            range=[0, 2.5], # Fixed range like target image
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            gridwidth=0.5,
            zeroline=False,
            tickfont=dict(size=10)
        ),
        legend=dict(
            orientation="h",  # Horizontal orientation
            yanchor="top",    # Anchor legend from its top
            y=-0.1,          # Position below the x-axis (adjust as needed)
            xanchor="center", # Anchor legend from its center
            x=0.5,           # Position horizontally centered
            bgcolor='rgba(0,0,0,0)', # Transparent background for cleaner look below axis
            bordercolor='rgba(0,0,0,0)',
            borderwidth=0
        ),
        template="plotly_dark",
        hovermode="x unified",
        bargap=0, # Remove gap between bars
        autosize=True,
        height=600, # <<< INCREASED CHART HEIGHT
        margin=dict(l=70, r=80, t=80, b=50) # Adjust margins
    )

    # Convert figure to JSON
    graph_json = pio.to_json(fig)
    print("Successfully generated Plotly JSON matching target style.")
    return jsonify(graph_json)

@app.route('/analyze_portfolio', methods=['POST'])
def analyze_portfolio():
    portfolio_data = request.get_json()
    if not portfolio_data or 'holdings' not in portfolio_data:
        return jsonify({'error': 'Invalid input: Missing holdings data.'}), 400

    holdings = portfolio_data['holdings']
    analysis_results = []
    total_portfolio_value = 0
    rotate_out_value = 0 # Initialize value for potential cash rotation
    levels, _ = define_risk_levels() # Get levels once

    for holding in holdings:
        ticker = holding.get('ticker', '').upper()
        shares_str = holding.get('shares', '0')
        asset_type = holding.get('asset_type', 'crypto') # Default to crypto if not provided

        if not ticker:
            analysis_results.append({'ticker': 'N/A', 'error': 'Missing ticker symbol.'})
            continue

        try:
            shares = float(shares_str) # For cash, this is the dollar amount
            if shares < 0: # Allow zero shares (might be simplifying input)
                 raise ValueError("Shares/Amount cannot be negative.")
        except (ValueError, TypeError):
            analysis_results.append({'ticker': ticker, 'shares': shares_str, 'asset_type': asset_type, 'error': 'Invalid shares/amount value.'})
            continue

        # --- Handle CASH specially ---
        if ticker == 'CASH' and asset_type == 'cash':
            print(f"Processing CASH holding: Amount: {shares}")
            holding_value = shares
            result_item = {
                'ticker': 'CASH',
                'asset_type': 'Cash',
                'shares': shares, # The dollar amount
                'latest_close': 1.00,
                'holding_value': holding_value,
                'latest_stbr': None, # No STBR for cash
                'stbr_category': 'Cash', # Special category
                'signal': 'Cash' # Special signal
            }
            analysis_results.append(result_item)
            total_portfolio_value += holding_value
            continue # Skip the rest of the loop for CASH
        # --- End CASH handling ---

        print(f"Analyzing portfolio holding: {ticker} ({asset_type}), Shares: {shares}")

        # Skip fetching if shares are zero (no value contribution)
        if shares == 0:
             analysis_results.append({
                'ticker': ticker,
                'asset_type': asset_type,
                'shares': 0,
                'latest_close': 0,
                'holding_value': 0,
                'latest_stbr': None,
                'stbr_category': 'N/A',
                'signal': 'Hold' # Or maybe 'N/A'?
            })
             continue

        price_data = fetch_price_data(symbol=ticker, asset_type=asset_type)
        if price_data.empty or 'Close' not in price_data.columns:
            analysis_results.append({'ticker': ticker, 'shares': shares, 'asset_type': asset_type, 'error': f'Failed to fetch price data for {ticker}.'})
            continue

        stbr_data = calculate_stbr(price_data.copy())
        if stbr_data.empty or 'STBR' not in stbr_data.columns or 'Close' not in stbr_data.columns:
            analysis_results.append({'ticker': ticker, 'shares': shares, 'asset_type': asset_type, 'error': f'Not enough data for STBR ({ticker}).'})
            continue

        try:
            latest_close = stbr_data['Close'].iloc[-1]
            latest_stbr = stbr_data['STBR'].iloc[-1]
            holding_value = latest_close * shares
            stbr_category = get_stbr_category(latest_stbr, levels)
            signal = get_rotation_signal(stbr_category)

            result_item = {
                'ticker': ticker,
                'asset_type': asset_type,
                'shares': shares,
                'latest_close': latest_close, # Keep unrounded for calculations
                'holding_value': holding_value, # Keep unrounded for calculations
                'latest_stbr': latest_stbr,
                'stbr_category': stbr_category,
                'signal': signal
            }
            analysis_results.append(result_item)
            total_portfolio_value += holding_value

            # Accumulate value if signal is Rotate Out
            if signal == "Rotate Out":
                rotate_out_value += holding_value

        except IndexError:
            analysis_results.append({'ticker': ticker, 'shares': shares, 'asset_type': asset_type, 'error': 'Error processing STBR data.'})
        except Exception as e:
            print(f"Unexpected error processing {ticker}: {e}")
            analysis_results.append({'ticker': ticker, 'shares': shares, 'asset_type': asset_type, 'error': f'Processing error: {e}'})

    # --- Create Portfolio Bar Chart --- 
    chart_data = [item for item in analysis_results if 'error' not in item and item['holding_value'] > 0]
    portfolio_chart_json = None
    if chart_data:
        # Sort by holding value descending for better visualization
        chart_data.sort(key=lambda x: x['holding_value'], reverse=True)

        tickers = [item['ticker'] for item in chart_data]
        values = [item['holding_value'] for item in chart_data]
        # Use the signal (which is now 'Cash' for cash holdings) to get color
        colors = [SIGNAL_COLORS.get(item['signal'], 'grey') for item in chart_data]
        hover_text = []
        for item in chart_data:
            if item['ticker'] == 'CASH':
                hover_text.append(
                    f"<b>CASH</b><br>" +
                    f"Value: ${item['holding_value']:.2f}"
                )
            else:
                 hover_text.append(
                    f"<b>{item['ticker']} ({item['asset_type']})</b><br>" +
                    f"Value: ${item['holding_value']:.2f}<br>" +
                    f"STBR: {item['latest_stbr']:.3f} ({item['stbr_category']})<br>" +
                    f"Signal: {item['signal']}" 
                 )

        fig_port = go.Figure()

        fig_port.add_trace(go.Bar(
            y=tickers, # Use tickers as categories on y-axis
            x=values,  # Values on x-axis
            marker_color=colors,
            orientation='h', # Horizontal bars
            name='Holdings',
            hovertext=hover_text,
            hoverinfo='text' # Show only the custom hover text
        ))
        
        # Add dummy traces for legend based on SIGNAL_COLORS used in the chart
        # Include 'Cash' signal if present
        signals_in_chart = set(item['signal'] for item in chart_data)
        for signal, color in SIGNAL_COLORS.items():
             if signal in signals_in_chart:
                 fig_port.add_trace(go.Bar(
                    x=[0], y=[None], name=signal, marker_color=color, orientation='h', showlegend=True
                 ))

        fig_port.update_layout(
            title='Portfolio Holdings by Rotation Signal',
            xaxis_title='Holding Value ($)',
            yaxis_title='Ticker',
            yaxis=dict(autorange="reversed"), # Show largest value bar at the top
            height=max(400, len(tickers) * 35 + 60), # Dynamic height, more space per bar + buffer
            margin=dict(l=80, r=50, t=80, b=50),
            bargap=0.15, # Slightly larger gap
            legend_title_text='Rotation Signal',
            template="plotly_dark"
        )
        
        portfolio_chart_json = pio.to_json(fig_port)
        print("Successfully generated portfolio chart JSON.")

    # --- Format analysis_results for table output (rounding/formatting) --- 
    formatted_analysis = []
    for item in analysis_results:
        # Format non-error items
        if 'error' not in item:
            item['latest_close'] = f"{item['latest_close']:.2f}" if item['latest_close'] is not None else 'N/A'
            item['holding_value'] = f"{item['holding_value']:.2f}" if item['holding_value'] is not None else 'N/A'
            item['latest_stbr'] = f"{item['latest_stbr']:.3f}" if item['latest_stbr'] is not None else 'N/A'
            # Format shares (amount for cash)
            item['shares'] = f"{item['shares']:.2f}" if item['ticker'] == 'CASH' else f"{item['shares']:,}"
        formatted_analysis.append(item)
    # -----------------------------------------------------------

    print(f"Portfolio analysis complete. Total value: {total_portfolio_value:.2f}, Rotate Out value: {rotate_out_value:.2f}")
    return jsonify({
        'portfolio_analysis': formatted_analysis,
        'total_value': round(total_portfolio_value, 2),
        'rotate_out_value': round(rotate_out_value, 2),
        'portfolio_chart_json': portfolio_chart_json # Can be None if no valid data
    })

if __name__ == '__main__':
    # Listen on all available network interfaces on a specific port
    app.run(host='0.0.0.0', port=5001, debug=True)
