# Creep Experiment Scraper
A scraper that collects data from the live creep experiment. The scraper is configured to run for 7 days and record data at 30s intervals. The data is saved to a CSV file in the working directory, which is created by the script on first execution.
## Requirements
- Python 3.8+
- Chrome 138+
- Must be logged into OU website
## Setup
Spin up a virtual environment in the directory:
```bash
python -m venv .
```

Activate the `venv`:
```bash
. bin/activate
```

Install requirements with `pip`:
```bash
pip install -r requirements.txt
```

Finally, run the scraper:
```
python scraper.py
```

## Additional Info
Here's a screenshot of the login form request. It requires a POST request with email and password, and then returns a json with session cookies that can be used for authentication.

<img width="1012" height="744" alt="image" src="https://github.com/user-attachments/assets/1ac4ccf7-d379-4235-905b-f96c0ed56e44" />
