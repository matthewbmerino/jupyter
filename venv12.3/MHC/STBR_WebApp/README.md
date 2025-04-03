# STBR Web Application

This Flask application provides a web interface to visualize the Short Term Bubble Risk (STBR) indicator for cryptocurrencies and stocks.

## Setup

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Set API Key:**
    Replace `'YOUR_API_KEY'` in `stbr_model.py` with your actual Alpha Vantage API key.
3.  **Run the application:**
    ```bash
    flask run
    ```
4.  Open your web browser and navigate to `http://127.0.0.1:5000` (or the address provided by Flask).

## Usage

- Select the asset type (Crypto or Stock).
- Enter the ticker symbol (e.g., BTC for Bitcoin, AAPL for Apple).
- Click "Analyze".
- The application will fetch data, calculate the STBR, and display an interactive chart showing the price (log scale) and the STBR indicator with risk levels.
