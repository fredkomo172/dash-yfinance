# dash-yfinance
finance dashboard with yahoo finance

## Installing dependencies 
to install the required libraries run ```pip install -r requirements.txt```

## Running
to run the program : ```streamlit run finance-dashboard.py``` (it is recommended to do it in a venv)

## CAC 40 list

The application uses `cac40.json` as its versioned initial list, then creates
the runtime file `data/cac40.json`. At startup, if that file is more than seven
days old, it tries to refresh the composition from Wikipedia. If the network is
unavailable or the response is invalid, the last valid local version is kept.
The runtime file is ignored by Git so a VPS update with `git pull` cannot conflict
with the list generated locally by the application.
The refresh works on Windows and Linux; no cron job is required.

## Indices Yahoo Finance

The `indices.json` file contains the initial list of indices available through
Yahoo Finance and `yfinance`: CAC 40, S&P 500 and its Total Return variant,
Dow Jones, Nasdaq, Euro Stoxx 50, Euronext 100, BEL 20,
FTSE 100, DAX, AEX, IBEX 35, SMI, Nikkei 225,
Hang Seng, Shanghai Composite, BSE SENSEX, Straits Times, S&P/ASX 200,
S&P/TSX Composite, Bovespa and IPC Mexico.

Each entry also documents whether the Yahoo Finance series is a price index or
a total-return index. The S&P 500 is available in two usable variants:
`^GSPC` (price) and `^SP500TR` (gross total return). Yahoo currently returns
only one recent observation for `^SP500NTR`, so it is not included because it
cannot support the dashboard's historical analysis.
In particular, `^GDAXI` is the DAX performance index:
it is a gross total-return series because it reinvests gross dividends. The
other symbols in the initial list are currently treated as price indices.

Yahoo Finance symbols beginning with `^` identify index instruments. Their
availability and history can vary by market and by date; for example, the PSI
20 symbol is currently not returned by Yahoo Finance and is therefore omitted.