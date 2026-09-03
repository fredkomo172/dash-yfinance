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