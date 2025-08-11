import requests
import time
import csv
import json
from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Dict, Any, Optional
import browser_cookie3

class SensorAPIMonitor:
    def __init__(self, output_file: str = "sensor_data.csv", original_length_mm: float = 100.0):
        self.api_url = "https://learn5.open.ac.uk/mod/htmlactivity/api/service.php"
        self.output_file = output_file
        self.original_length_mm = original_length_mm  # Original specimen length in mm
        
        # Experiment start time: 11th August 2025 at 12pm BST
        # BST is UTC+1, so 12pm BST = 11am UTC
        self.experiment_start = datetime(2025, 8, 11, 11, 0, 0, tzinfo=timezone.utc)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        # Form data for the API request
        self.form_data = {
            'a': 'default',
            'c': '3',
            'i': 't193_creep_capture',
            's': 'yWYFUnYGAQ',  # This might need to be extracted from cookies
            'x': 'service',
            'service': 'creep',
            'names': 'action',
            'values': 'getUpdate'
        }
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('sensor_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Load cookies for authentication
        self.load_chrome_cookies()
        
        # Initialize CSV file
        self.init_csv_file()
        
    def load_chrome_cookies(self):
        """Load authentication cookies from Chrome for the OU domain"""
        try:
            # Get all OU-related cookies
            all_chrome_cookies = browser_cookie3.chrome()
            ou_cookies = [cookie for cookie in all_chrome_cookies 
                         if 'open.ac.uk' in cookie.domain.lower()]
            
            cookie_count = 0
            session_key = None
            
            for cookie in ou_cookies:
                # Add cookie to session
                self.session.cookies.set(
                    cookie.name, 
                    cookie.value, 
                    domain=cookie.domain, 
                    path=cookie.path if cookie.path else '/'
                )
                cookie_count += 1
                
                # Look for session key in cookie names/values
                if 'session' in cookie.name.lower() or cookie.name == 's':
                    session_key = cookie.value
                    self.logger.info(f"Found potential session key: {session_key}")
                
            self.logger.info(f"Loaded {cookie_count} OU cookies")
            
            # Update session key in form data if found
            if session_key:
                self.form_data['s'] = session_key
                self.logger.info("Updated API session key from cookies")
            else:
                self.logger.warning("No session key found in cookies - using default")
                
        except Exception as e:
            self.logger.error(f"Error loading cookies: {e}")
            self.logger.info("Continuing with default session key")
    
    def init_csv_file(self):
        """Initialize CSV file with headers"""
        if not os.path.exists(self.output_file):
            with open(self.output_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'Date', 
                    'Elapsed Time (s)',
                    'Change in Length (mm)', 
                    '% Strain'
                ])
    
    def update_session_key_from_cookies(self):
        """Update session key from Chrome cookies before each API request"""
        try:
            # Get fresh cookies from Chrome
            all_chrome_cookies = browser_cookie3.chrome()
            ou_cookies = [cookie for cookie in all_chrome_cookies 
                         if 'open.ac.uk' in cookie.domain.lower()]
            
            session_key_updated = False
            
            for cookie in ou_cookies:
                # Update all cookies in session
                self.session.cookies.set(
                    cookie.name, 
                    cookie.value, 
                    domain=cookie.domain, 
                    path=cookie.path if cookie.path else '/'
                )
                
                # Look for session key and update form data
                if 'session' in cookie.name.lower() or cookie.name == 's':
                    if cookie.value != self.form_data.get('s'):
                        self.logger.info(f"Session key updated: {self.form_data.get('s')} -> {cookie.value}")
                        self.form_data['s'] = cookie.value
                        session_key_updated = True
            
            if not session_key_updated:
                self.logger.debug("Session key unchanged")
                
        except Exception as e:
            self.logger.warning(f"Error updating cookies: {e}")
    
    def fetch_sensor_data(self) -> Optional[Dict[str, Any]]:
        """Fetch sensor data from the API endpoint"""
        try:
            # Refresh cookies before each request
            self.update_session_key_from_cookies()
            
            response = self.session.post(self.api_url, data=self.form_data, timeout=10)
            response.raise_for_status()
            response.raise_for_status()
            
            # Parse JSON response
            json_data = response.json()
            
            if 'ok' in json_data and 'data' in json_data['ok']:
                sensor_data = json_data['ok']['data']
                current_time = datetime.now(timezone.utc)
                
                # Calculate actual elapsed time since experiment start (12pm BST on 11th Aug 2025)
                elapsed_timedelta = current_time - self.experiment_start
                calculated_elapsed_seconds = int(elapsed_timedelta.total_seconds())
                
                # Get raw elapsed value from API for comparison
                api_elapsed_raw = sensor_data.get('elapsed', 0)
                
                # Calculate change in length (extension) in mm
                extension_mm = sensor_data.get('extension', 0)  # This should already be in mm
                change_in_length = round(extension_mm, 3)  # Round to 3 decimal places
                
                # Calculate strain percentage
                strain_percent = round((change_in_length / self.original_length_mm) * 100, 3)
                
                # Format date as DD/MM
                current_time_bst = current_time.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=1)))  # Convert to BST
                date_formatted = current_time_bst.strftime("%d/%m")
                
                data = {
                    'date': date_formatted,
                    'elapsed_seconds': calculated_elapsed_seconds,
                    'change_in_length_mm': change_in_length,
                    'strain_percent': strain_percent,
                    'running': sensor_data.get('running', False),
                    'temperature': sensor_data.get('temperature', 0),
                    'status_code': response.status_code
                }
                
                self.logger.info(f"API Success - Temp: {data['temperature']:.1f}°C, Length: {change_in_length}mm, Strain: {strain_percent}%, Elapsed: {calculated_elapsed_seconds}s")
                return data
            else:
                self.logger.error(f"Unexpected API response format: {json_data}")
                return self.create_error_record("API_FORMAT_ERROR")
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            return self.create_error_record("REQUEST_ERROR")
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            return self.create_error_record("JSON_ERROR")
        except Exception as e:
            self.logger.error(f"Error fetching sensor data: {e}")
            return self.create_error_record("FETCH_ERROR")
    
    def create_error_record(self, error_type: str) -> Dict[str, Any]:
        """Create error record for failed API calls"""
        current_time = datetime.now(timezone.utc)
        elapsed_timedelta = current_time - self.experiment_start
        calculated_elapsed_seconds = int(elapsed_timedelta.total_seconds())
        
        return {
            'date': current_time.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=1))).strftime("%d/%m"),
            'elapsed_seconds': calculated_elapsed_seconds,
            'change_in_length_mm': 0.000,
            'strain_percent': 0.000,
            'running': False,
            'temperature': 0,
            'status_code': f"ERROR_{error_type}"
        }
    
    def save_data(self, data: Dict[str, Any]):
        """Save sensor data to CSV"""
        try:
            with open(self.output_file, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    data['date'],
                    data['elapsed_seconds'],
                    data['change_in_length_mm'],
                    data['strain_percent']
                ])
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
    
    def run_for_duration(self, days: int = 7, interval_seconds: int = 30):
        """Run the sensor monitor for specified duration"""
        start_time = datetime.now()
        end_time = start_time + timedelta(days=days)
        fetch_count = 0
        
        self.logger.info(f"Starting sensor API monitor for {days} days")
        self.logger.info(f"API URL: {self.api_url}")
        self.logger.info(f"Interval: {interval_seconds} seconds")
        self.logger.info(f"Start time: {start_time}")
        self.logger.info(f"End time: {end_time}")
        
        try:
            while datetime.now() < end_time:
                fetch_start = time.time()
                
                # Fetch sensor data from API
                data = self.fetch_sensor_data()
                if data:
                    self.save_data(data)
                
                fetch_count += 1
                
                # Calculate sleep time
                fetch_duration = time.time() - fetch_start
                sleep_time = max(0, interval_seconds - fetch_duration)
                
                # Log progress every hour (120 fetches at 30-second intervals)
                if fetch_count % 120 == 0:
                    remaining_time = end_time - datetime.now()
                    self.logger.info(f"Progress: {fetch_count} API calls completed. Time remaining: {remaining_time}")
                
                # Sleep until next fetch
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            self.logger.info("Monitoring interrupted by user")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            self.logger.info(f"Monitoring completed. Total API calls: {fetch_count}")
            self.logger.info(f"Data saved to: {self.output_file}")

def main():
    # Create and run the sensor monitor
    # Original specimen length: 50mm
    monitor = SensorAPIMonitor("sensor_data.csv", original_length_mm=50.0)
    monitor.run_for_duration(days=7, interval_seconds=30)

if __name__ == "__main__":
    main()