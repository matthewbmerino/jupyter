// Basic JS, will add Plotly later 

// --- Debounce Function ---
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};
// --- ------------------- ---

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('stbr-form');
    const chartDiv = document.getElementById('plotly-chart');
    const statusDiv = document.getElementById('status-message');
    const symbolInput = document.getElementById('symbol');
    const assetTypeInput = document.getElementById('asset_type');
    const searchResultsDiv = document.getElementById('search-results');

    // Portfolio Elements
    const holdingsListDiv = document.getElementById('holdings-list');
    const addHoldingBtn = document.getElementById('add-holding');
    const analyzePortfolioBtn = document.getElementById('analyze-portfolio-btn');
    const portfolioStatusDiv = document.getElementById('portfolio-status-message');
    const portfolioResultsDiv = document.getElementById('portfolio-results-section');
    const portfolioTableBody = document.getElementById('portfolio-table-body');
    const totalPortfolioValueSpan = document.getElementById('total-portfolio-value');
    const rotateOutValueSpan = document.getElementById('rotate-out-value');
    const portfolioChartDiv = document.getElementById('portfolio-plotly-chart');

    let predefinedTickers = {}; // Cache for fetched tickers
    let searchAbortController = null; // To cancel ongoing fetch requests

    // --- Function to fetch predefined tickers --- 
    async function fetchPredefinedTickers(assetType) {
        // Handle CASH type locally for suggestions if needed, or rely on backend
        if (assetType === 'cash') {
             predefinedTickers['cash'] = ['CASH']; // Simple local definition
             return predefinedTickers['cash'];
        }
        
        if (predefinedTickers[assetType]) {
            return predefinedTickers[assetType]; // Return cached tickers
        }
        try {
            const response = await fetch(`/get_available_tickers?asset_type=${assetType}`);
            if (!response.ok) {
                 throw new Error(`HTTP error ${response.status}`);
            }
            const tickers = await response.json();
            predefinedTickers[assetType] = tickers.sort(); // Cache sorted tickers
            return predefinedTickers[assetType];
        } catch (error) {
            console.error(`Error fetching predefined tickers for ${assetType}:`, error);
            return []; // Return empty array on error
        }
    }
    // --- --------------------------------------- ---

    // --- Function to fetch data from Alpha Vantage search endpoint ---
    async function fetchAVSearchResults(keywords, assetType) {
        if (searchAbortController) {
            searchAbortController.abort(); // Cancel the previous request
        }
        searchAbortController = new AbortController();
        const signal = searchAbortController.signal;

        try {
            const response = await fetch(`/search_symbol?keywords=${encodeURIComponent(keywords)}&asset_type=${assetType}`, { signal });
            if (!response.ok) {
                 // Handle API limit specifically if possible
                 if (response.status === 503) {
                    console.warn("Search API limit likely reached.");
                    // Optionally show a brief message to the user in statusDiv?
                    return []; // Return empty array on API limit
                 }
                 throw new Error(`HTTP error ${response.status}`);
            }
            const data = await response.json();
             // Check for explicit error from backend
             if (data.error) {
                 console.error("Search API Error:", data.error);
                 // Optionally show a brief message
                 return [];
             }
            return data.bestMatches || []; // Return the list of matches or empty array
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('Search fetch aborted'); // Expected when user types quickly
            } else {
                console.error('Error fetching search results:', error);
            }
            return []; // Return empty array on error or abort
        }
    }
    // --- --------------------------------------------------------- ---

    // --- Debounced Search Function ---
    const debouncedSearch = debounce(async (keywords, assetType) => {
        if (keywords.length < 1) { // Don't search on very short input
            displayResults([]);
            return;
        }

        let results = [];
        if (assetType === 'stock') {
            results = await fetchAVSearchResults(keywords, assetType);
        } else {
            // Filter local tickers for crypto/cash
            const localTickers = await fetchPredefinedTickers(assetType); // Ensure list is fetched
            const upperKeywords = keywords.toUpperCase();
            results = localTickers
                .filter(ticker => ticker.toUpperCase().includes(upperKeywords))
                 // Format like AV results for consistency in displayResults
                .map(ticker => ({ "1. symbol": ticker, "2. name": "" })); 
        }
        displayResults(results);
    }, 300); // 300ms delay
    // --- --------------------------- ---

    // --- Function to display search results --- 
    function displayResults(matches) {
        searchResultsDiv.innerHTML = ''; // Clear previous results
        if (!Array.isArray(matches) || matches.length === 0) {
            searchResultsDiv.style.display = 'none';
            return;
        }

        const ul = document.createElement('ul');
        matches.slice(0, 10).forEach(match => { // Limit to max 10 results
            const symbol = match["1. symbol"];
            const name = match["2. name"];
            const li = document.createElement('li');
            // Display both symbol and name if name exists
            li.innerHTML = `<strong>${symbol}</strong>${name ? `<span style="color: var(--text-color-muted); font-size: 0.85em;">${name}</span>` : ''}`;
            li.dataset.symbol = symbol; // Store symbol in data attribute

            li.addEventListener('click', () => {
                symbolInput.value = li.dataset.symbol; // Use stored symbol
                searchResultsDiv.innerHTML = ''; // Clear results
                searchResultsDiv.style.display = 'none';
                // Trigger analysis if needed, or let user press button
                // updateChart(symbolInput.value, assetTypeInput.value);
            });
            ul.appendChild(li);
        });
        searchResultsDiv.appendChild(ul);
        searchResultsDiv.style.display = 'block'; // Show results
    }
    // --- ---------------------------------- ---

    function updateChart(symbol, assetType) {
        // Prevent analyzing CASH directly
        if (symbol === 'CASH' && assetType === 'cash') {
            statusDiv.textContent = 'Cannot analyze CASH directly. Add it to your portfolio instead.';
            statusDiv.style.color = 'orange';
            chartDiv.innerHTML = ''; // Clear any existing chart/message
             setTimeout(() => { statusDiv.textContent = ''; }, 3000);
            return;
        }

        statusDiv.textContent = `Fetching data for ${symbol}...`;
        statusDiv.style.color = '#e0e0e0'; // Neutral color

        const formData = new FormData();
        formData.append('symbol', symbol);
        formData.append('asset_type', assetType);

        fetch('/get_chart_data', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            // Always try to parse JSON, even for errors
            return response.json().then(data => {
                if (!response.ok) {
                    // Throw an error with the message from the backend JSON
                    throw new Error(data.error || `HTTP error ${response.status}`);
                }
                return data; // This is the graph JSON if successful
            });
        })
        .then(graphJsonString => {
            // The backend sends a JSON string, which needs parsing *again*
            const figure = JSON.parse(graphJsonString); 
            Plotly.newPlot(chartDiv, figure.data, figure.layout, {responsive: true});
            statusDiv.textContent = 'Chart loaded successfully.';
            statusDiv.style.color = 'var(--success-color)';
        })
        .catch(error => {
            console.error('Error fetching or plotting chart:', error);
            // Display the error message from the caught error
            statusDiv.textContent = `Error: ${error.message}`;
            statusDiv.style.color = 'var(--error-color)'; 
            chartDiv.innerHTML = '<div style="text-align: center; padding: 50px; color: var(--error-color);">Could not load chart.</div>';
        });
    }

    // --- Portfolio Functions --- 
    function addHoldingRow() {
        const newRow = document.createElement('div');
        newRow.classList.add('holding-row');
        // Update innerHTML to include the new wrapper divs and labels
        newRow.innerHTML = `
            <div class="holding-asset-type-group">
                <label>Type</label>
                <select class="holding-asset-type">
                    <option value="crypto">Crypto</option>
                    <option value="stock">Stock</option>
                    <option value="cash">Cash</option>
                </select>
            </div>
            <div class="holding-ticker-group">
                <label>Ticker</label>
                <input type="text" class="holding-ticker" placeholder="Ticker (e.g., BTC, AAPL, CASH)" required>
            </div>
            <div class="holding-shares-group">
                <label>Shares/Amount</label>
                <input type="number" class="holding-shares" placeholder="Shares / Amount ($)" step="any" min="0" required>
            </div>
            <button type="button" class="remove-holding">Remove</button>
        `;
        holdingsListDiv.appendChild(newRow);
        // Add event listener to the new remove button
        newRow.querySelector('.remove-holding').addEventListener('click', function() {
            this.closest('.holding-row').remove();
        });
        // Add event listener to the new asset type select for CASH handling
        const assetTypeSelect = newRow.querySelector('.holding-asset-type');
        const tickerInput = newRow.querySelector('.holding-ticker');
        assetTypeSelect.addEventListener('change', function() {
            handleCashTicker(assetTypeSelect, tickerInput);
        });
        // Initial check in case default is CASH (though unlikely)
        handleCashTicker(assetTypeSelect, tickerInput);
    }

    // Helper function to manage CASH ticker input based on type selection
    function handleCashTicker(assetTypeSelect, tickerInput) {
        if (assetTypeSelect.value === 'cash') {
            tickerInput.value = 'CASH';
            tickerInput.readOnly = true; // Make it read-only
            tickerInput.style.backgroundColor = '#444'; // Indicate read-only
        } else {
            if (tickerInput.value === 'CASH' && tickerInput.readOnly) {
                tickerInput.value = ''; // Clear CASH if type changes
            }
            tickerInput.readOnly = false;
            tickerInput.style.backgroundColor = ''; // Reset background
        }
    }

    async function analyzePortfolio() {
        portfolioStatusDiv.textContent = 'Analyzing portfolio...';
        portfolioStatusDiv.style.color = '#e0e0e0';
        portfolioResultsDiv.style.display = 'none'; // Hide previous results
        portfolioTableBody.innerHTML = ''; // Clear table body
        portfolioChartDiv.innerHTML = ''; // Clear previous chart
        totalPortfolioValueSpan.textContent = '0.00';
        rotateOutValueSpan.textContent = '0.00'; // Clear cash value

        const holdingRows = holdingsListDiv.querySelectorAll('.holding-row');
        const holdings = [];
        let hasInputError = false;

        holdingRows.forEach(row => {
            const assetType = row.querySelector('.holding-asset-type').value;
            const tickerInput = row.querySelector('.holding-ticker');
            const sharesInput = row.querySelector('.holding-shares');
            const ticker = tickerInput.value.trim().toUpperCase();
            const shares = sharesInput.value.trim();

            // Basic validation
            let currentInputError = false;
            if (!ticker) {
                tickerInput.style.borderColor = 'red';
                currentInputError = true;
            } else {
                tickerInput.style.borderColor = '';
            }
             // Allow 0 shares/amount, but not negative or non-numeric
            const sharesNum = parseFloat(shares);
            if (shares === '' || isNaN(sharesNum) || sharesNum < 0) {
                sharesInput.style.borderColor = 'red';
                currentInputError = true;
            } else {
                sharesInput.style.borderColor = '';
            }
            
            // Specific check for CASH type
            if (assetType === 'cash' && ticker !== 'CASH') {
                 tickerInput.style.borderColor = 'orange'; // Use orange for warning
                 // Optionally add a tooltip or message here indicating ticker should be CASH
                 currentInputError = true; // Treat as error for now
                 // TODO: Show tooltip/message instead?
            } else if (assetType !== 'cash' && ticker === 'CASH') {
                 tickerInput.style.borderColor = 'orange';
                 currentInputError = true;
            }

            if (currentInputError) {
                 hasInputError = true;
            } else if (ticker && shares !== '') {
                 holdings.push({ 
                    ticker: ticker, 
                    shares: shares, // Send as string, backend will parse
                    asset_type: assetType
                 });
            }
        });

        if (hasInputError) {
            portfolioStatusDiv.textContent = 'Please fix errors/warnings in input fields (marked red/orange). Use ticker CASH for Cash type.';
            portfolioStatusDiv.style.color = 'var(--warning-color)';
            return; // Stop if there are input errors
        }

        if (holdings.length === 0) {
            portfolioStatusDiv.textContent = 'Please add at least one holding to analyze.';
            portfolioStatusDiv.style.color = 'var(--warning-color)';
            return;
        }

        try {
            const response = await fetch('/analyze_portfolio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ holdings: holdings })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `HTTP error ${response.status}`);
            }

            // Process and display results
            displayPortfolioResults(result);
            portfolioStatusDiv.textContent = 'Portfolio analysis complete.';
            portfolioStatusDiv.style.color = 'var(--success-color)';
            portfolioResultsDiv.style.display = 'block'; // Show results section

        } catch (error) {
            console.error('Error analyzing portfolio:', error);
            portfolioStatusDiv.textContent = `Error: ${error.message}`;
            portfolioStatusDiv.style.color = 'var(--error-color)';
            portfolioChartDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--error-color);">Could not load portfolio chart.</div>';
        }
    }

    function displayPortfolioResults(data) {
        // Clear previous results
        portfolioTableBody.innerHTML = ''; 
        portfolioChartDiv.innerHTML = ''; 
        totalPortfolioValueSpan.textContent = '0.00';
        rotateOutValueSpan.textContent = '0.00';

        if (!data) {
            portfolioTableBody.innerHTML = '<tr><td colspan="9">No analysis data received.</td></tr>';
            return;
        }

        // Display Table Data
        if (data.portfolio_analysis && data.portfolio_analysis.length > 0) {
             data.portfolio_analysis.forEach(item => {
                const row = portfolioTableBody.insertRow();
                const isCash = item.ticker === 'CASH' && item.asset_type === 'Cash';
                const signalColor = item.error ? 'var(--error-color)' : 
                                    isCash ? 'var(--text-color-muted)' : // Muted color for cash signal cell
                                    item.signal === 'Rotate Out' ? '#FF4500' : 
                                    item.signal === 'Rotate In' ? '#00FF00' : 
                                    'inherit'; // Default color for Hold

                row.innerHTML = `
                    <td>${item.ticker || 'N/A'}</td>
                    <td>${item.asset_type || 'N/A'}</td>
                    <td>${item.shares !== undefined ? item.shares : 'N/A'}</td> <!-- Use formatted value -->
                    <td>${isCash ? 'N/A' : (item.latest_close !== undefined ? item.latest_close : 'N/A')}</td>
                    <td>${item.holding_value !== undefined ? item.holding_value : 'N/A'}</td>
                    <td>${isCash ? 'N/A' : (item.latest_stbr !== undefined ? item.latest_stbr : 'N/A')}</td>
                    <td>${item.stbr_category || 'N/A'}</td>
                    <td style="color: ${signalColor}; font-weight: ${isCash ? 'normal' : 'bold'};">${item.signal || 'N/A'}</td>
                    <td>${item.error || ''}</td> <!-- Display error message -->
                `;
                // Apply styling based on error
                if (item.error) {
                    row.style.color = 'var(--error-color)'; // Error color for the whole row
                }
            });
        } else {
             portfolioTableBody.innerHTML = '<tr><td colspan="9">No valid holdings data to display.</td></tr>';
        }
       
        // Display Summary Values
        totalPortfolioValueSpan.textContent = data.total_value !== undefined ? data.total_value.toFixed(2) : '0.00';
        rotateOutValueSpan.textContent = data.rotate_out_value !== undefined ? data.rotate_out_value.toFixed(2) : '0.00';

        // Display Portfolio Chart
        if (data.portfolio_chart_json) {
            try {
                const figure = JSON.parse(data.portfolio_chart_json);
                Plotly.newPlot(portfolioChartDiv, figure.data, figure.layout, {responsive: true});
            } catch (e) {
                console.error('Error parsing or plotting portfolio chart JSON:', e);
                 portfolioChartDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--error-color);">Error loading portfolio chart.</div>';
            }
        } else if (!data.portfolio_analysis || data.portfolio_analysis.filter(item => !item.error && parseFloat(item.holding_value) > 0).length === 0) { // Check for valid, non-zero value holdings
             // No chart if no valid data points (all had errors or zero value)
             portfolioChartDiv.innerHTML = '<div style="text-align: center; padding: 20px;">No data available to generate portfolio chart.</div>';
        }
    }
    // --- ----------------------- ---

    // --- Event Listeners --- 
    form.addEventListener('submit', function(event) {
        event.preventDefault(); // Prevent default form submission
        searchResultsDiv.style.display = 'none'; // Hide search results on submit
        updateChart(symbolInput.value, assetTypeInput.value);
    });

    // --- Autocomplete Listener --- 
    symbolInput.addEventListener('input', function() {
        const keywords = symbolInput.value.trim();
        const assetType = assetTypeInput.value;

        if (keywords.length > 0) {
            // Use debounced search for stocks or local filtering for others
            debouncedSearch(keywords, assetType);
        } else {
            searchResultsDiv.innerHTML = ''; // Clear if input is empty
            searchResultsDiv.style.display = 'none';
        }
    });

    // Clear results when input loses focus (if not clicking on a result)
    symbolInput.addEventListener('blur', function(event) {
         // Delay hiding to allow click event on results to register
         setTimeout(() => {
             // Check if the related target (where focus went) is inside the results div
            if (!searchResultsDiv.contains(event.relatedTarget)) {
                searchResultsDiv.style.display = 'none';
            }
        }, 150);
    });

    // Clear/Refetch results when asset type changes
    assetTypeInput.addEventListener('change', function() {
        symbolInput.value = ''; // Clear symbol input when type changes
        searchResultsDiv.innerHTML = '';
        searchResultsDiv.style.display = 'none';
        // Pre-fetch tickers for the selected type if not already cached
        fetchPredefinedTickers(assetTypeInput.value);
    });

    // --- Portfolio Listeners ---
    addHoldingBtn.addEventListener('click', addHoldingRow);
    analyzePortfolioBtn.addEventListener('click', analyzePortfolio);

    // Add event listener for removing the initial row
    const initialRemoveBtn = holdingsListDiv.querySelector('.remove-holding');
    if(initialRemoveBtn) { // Ensure it exists
        initialRemoveBtn.addEventListener('click', function() {
            this.closest('.holding-row').remove();
        });
    }

    // --- Initial Setup --- 
    updateChart(symbolInput.value, assetTypeInput.value); // Initial chart load
    fetchPredefinedTickers('crypto'); // Pre-fetch crypto tickers
    fetchPredefinedTickers('stock'); // Pre-fetch stock tickers

    // Add event listeners to existing remove buttons on page load
    document.querySelectorAll('.remove-holding').forEach(button => {
        button.addEventListener('click', function() {
            this.closest('.holding-row').remove();
        });
    });

     // Add event listeners to existing asset type selects on page load
    document.querySelectorAll('.holding-row').forEach(row => {
        const assetTypeSelect = row.querySelector('.holding-asset-type');
        const tickerInput = row.querySelector('.holding-ticker');
        if(assetTypeSelect && tickerInput) {
             assetTypeSelect.addEventListener('change', function() {
                handleCashTicker(assetTypeSelect, tickerInput);
            });
            // Initial check for rows loaded from backend (if applicable later)
             handleCashTicker(assetTypeSelect, tickerInput); 
        }
    });

}); // End DOMContentLoaded 