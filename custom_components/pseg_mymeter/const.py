"""Constants for the PSE&G MyMeter experimental integration."""

DOMAIN = "pseg_mymeter"
NAME = "PSE&G MyMeter (experimental)"
CONF_SESSION_COOKIE = "session_cookie"
DEFAULT_SCAN_INTERVAL_HOURS = 6
SCAN_INTERVAL_HOURS = DEFAULT_SCAN_INTERVAL_HOURS
CHART_URL = "https://mysmartenergy.nj.pseg.com/Dashboard/ChartData"
MYMETER_ROOT = "https://mysmartenergy.nj.pseg.com/"
STATISTIC_ID = f"{DOMAIN}:electricity_consumption"
