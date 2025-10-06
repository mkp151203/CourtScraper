import requests
from bs4 import BeautifulSoup
import json
import re
import base64
import os
import hashlib
from datetime import datetime
from typing import Dict, Optional
from captcha_ocr import detect_captcha_text

class DistrictCourtsScraper:
    """Simplified District Court scraper for web app"""
    
    def __init__(self):
        self.base_url = "https://services.ecourts.gov.in/"
        self.session = requests.Session()
        
        self.headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://services.ecourts.gov.in',
            'Referer': 'https://services.ecourts.gov.in/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        self.session.headers.update(self.headers)
        
        # Hardcoded states
        self.states = {
            'Andhra Pradesh': '2',
            'Arunachal Pradesh': '36',
            'Andaman and Nicobar': '28',
            'Assam': '6',
            'Bihar': '8',
            'Chandigarh': '27',
            'Chhattisgarh': '18',
            'Delhi': '26',
            'Goa': '30',
            'Gujarat': '17',
            'Haryana': '14',
            'Himachal Pradesh': '5',
            'Jammu and Kashmir': '12',
            'Jharkhand': '7',
            'Karnataka': '9',
            'Kerala': '4',
            'Ladakh': '33',
            'Lakshadweep': '37',
            'Madhya Pradesh': '23',
            'Maharashtra': '1',
            'Manipur': '25',
            'Meghalaya': '21',
            'Mizoram': '19',
            'Nagaland': '34',
            'Uttarakhand': '15',
            'Odisha': '11',
            'Puducherry': '35',
            'Punjab': '22',
            'Rajasthan': '3',
            'Sikkim': '24',
            'Tamil Nadu': '10',
            'Telangana': '29',
            'The Dadra And Nagar Haveli And Daman And Diu': '38',
            'Tripura': '20',
            'Uttar Pradesh': '13',
            'West Bengal': '16'
        }
        
        self.districts = {}
        self.court_complexes = {}
        self.case_types = {}
        
        self.current_state = None
        self.current_state_code = None
        self.current_district = None
        self.current_district_code = None
        self.current_court_complex = None
        self.current_court_complex_code = None
        
        self.app_token = None
    
    def initialize_session(self) -> bool:
        """Initialize session"""
        try:
            response = self.session.get(f"{self.base_url}ecourtindia_v6/", timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'app_token'})
                
                if token_input:
                    self.app_token = token_input.get('value')
                    return True
            return False
        except Exception as e:
            print(f"Error initializing session: {e}")
            return False
    
    def fetch_states(self) -> Dict[str, str]:
        """Return hardcoded states"""
        return self.states
    
    def fetch_districts(self, state_code: str) -> Dict[str, str]:
        """Fetch districts for a state"""
        try:
            if not self.app_token:
                self.initialize_session()
            
            # Prepare headers with Referer
            headers = self.headers.copy()
            headers['Referer'] = f"{self.base_url}ecourtindia_v6/?p=casestatus/index"
            
            # Prepare data as a string (matching the working scraper)
            data_str = f"state_code={state_code}&ajax_req=true&app_token={self.app_token if self.app_token else ''}"
            
            print(f"DEBUG: Sending request to fillDistrict with state_code={state_code}")
            
            response = self.session.post(
                f"{self.base_url}ecourtindia_v6/?p=casestatus/fillDistrict",
                data=data_str,
                headers=headers,
                timeout=10
            )
            
            print(f"DEBUG: Response status: {response.status_code}")
            
            if response.status_code == 200:
                # Handle potential BOM
                response.encoding = 'utf-8-sig'
                result = response.json()
                
                print(f"DEBUG: Response JSON keys: {result.keys()}")
                
                # Update app_token if provided
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                # Parse district list HTML
                if 'dist_list' in result:
                    self.districts = {}
                    soup = BeautifulSoup(result['dist_list'], 'html.parser')
                    options = soup.find_all('option')
                    
                    for option in options:
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        
                        if value and text and value != '0':
                            self.districts[text] = value
                    
                    print(f"DEBUG: Found {len(self.districts)} districts")
                    return self.districts
                else:
                    print(f"DEBUG: No 'dist_list' in response")
            else:
                print(f"DEBUG: Response text: {response.text[:200]}")
                
            return {}
        except Exception as e:
            print(f"Error fetching districts: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def fetch_court_complexes(self, state_code: str, district_code: str) -> Dict[str, str]:
        """Fetch court complexes"""
        try:
            if not self.app_token:
                self.initialize_session()
            
            url = f"{self.base_url}ecourtindia_v6/?p=casestatus/fillcomplex"
            
            data = {
                'state_code': state_code,
                'dist_code': district_code,
                'ajax_req': 'true',
                'app_token': self.app_token if self.app_token else ''
            }
            
            response = self.session.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update app_token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                # Parse complex list HTML
                if 'complex_list' in result:
                    self.court_complexes = {}
                    soup = BeautifulSoup(result['complex_list'], 'html.parser')
                    options = soup.find_all('option')
                    
                    for option in options:
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        
                        if value and value != '' and value != '0':
                            self.court_complexes[text] = value
                    
                    return self.court_complexes
            return {}
        except Exception as e:
            print(f"Error fetching court complexes: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def fetch_case_types(self, state_code: str, district_code: str, court_complex_code: str) -> Dict[str, str]:
        """Fetch case types"""
        try:
            if not self.app_token:
                self.initialize_session()
            
            url = f"{self.base_url}ecourtindia_v6/?p=casestatus/fillCaseType"
            
            # Add Referer header
            headers = self.headers.copy()
            headers['Referer'] = f"{self.base_url}ecourtindia_v6/?p=casestatus/index"
            
            # Extract court_complex and est_code from court_complex_code
            # Format: court_code@est_code@flag
            court_arr = court_complex_code.split('@')
            court_complex = court_arr[0] if len(court_arr) > 0 else court_complex_code
            est_code = court_arr[1] if len(court_arr) > 1 else ''
            
            # Prepare data as string
            data_str = (f"state_code={state_code}&"
                       f"dist_code={district_code}&"
                       f"court_complex_code={court_complex}&"
                       f"est_code={est_code}&"
                       f"search_type=c_no&"
                       f"ajax_req=true&"
                       f"app_token={self.app_token if self.app_token else ''}")
            
            response = self.session.post(url, data=data_str, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update app_token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                # Parse case type list HTML - check for both possible keys
                case_type_html = result.get('case_type') or result.get('casetype_list')
                
                if case_type_html:
                    self.case_types = {}
                    soup = BeautifulSoup(case_type_html, 'html.parser')
                    options = soup.find_all('option')
                    
                    for option in options:
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        
                        if value and value != '' and value not in ['0', 'Select case type', 'Select Case Type']:
                            self.case_types[text] = value
                    
                    return self.case_types
            return {}
        except Exception as e:
            print(f"Error fetching case types: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def get_captcha(self) -> Optional[Dict]:
        """Get captcha image as base64 - returns dict for web app"""
        try:
            if not self.app_token:
                self.initialize_session()
            
            # Correct URL pattern
            url = f"{self.base_url}ecourtindia_v6/?p=casestatus/getCaptcha"
            
            # Add Referer header
            headers = self.headers.copy()
            headers['Referer'] = f"{self.base_url}ecourtindia_v6/?p=casestatus/index"
            
            # Prepare data as string
            data_str = f"ajax_req=true&app_token={self.app_token if self.app_token else ''}"
            
            response = self.session.post(url, data=data_str, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update app_token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                # Parse captcha image from HTML
                if 'div_captcha' in result:
                    soup = BeautifulSoup(result['div_captcha'], 'html.parser')
                    img_tag = soup.find('img', {'id': 'captcha_image'})
                    
                    if img_tag:
                        captcha_src = img_tag.get('src')
                        
                        # Handle relative URLs
                        from urllib.parse import urljoin
                        captcha_url = urljoin(self.base_url, captcha_src)
                        
                        # Download captcha image
                        captcha_response = self.session.get(captcha_url, timeout=10)
                        
                        if captcha_response.status_code == 200:
                            # Convert to base64
                            img_base64 = base64.b64encode(captcha_response.content).decode('utf-8')
                            captcha_data_url = f"data:image/png;base64,{img_base64}"
                            
                            # Attempt to auto-detect captcha text using OCR
                            detected_text = detect_captcha_text(captcha_response.content)
                            print(f"[OCR] Auto-detected CAPTCHA text: '{detected_text}'")
                            
                            # Return dict format expected by web app
                            return {
                                'captcha_url': captcha_data_url,
                                'app_token': self.app_token,
                                'detected_text': detected_text  # Auto-detected text for auto-fill
                            }
            
            print("Failed to fetch captcha")
            return None
        except Exception as e:
            print(f"Error getting captcha: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def search_case(self, state_code: str = None, district_code: str = None,
                   court_complex_code: str = None, case_type_code: str = None,
                   case_no: str = None, case_year: str = None, captcha: str = None) -> Optional[Dict]:
        """Search for a case"""
        try:
            if not self.app_token:
                self.initialize_session()
            
            # Store codes for later use
            if state_code:
                self.current_state_code = state_code
            if district_code:
                self.current_district_code = district_code
            if court_complex_code:
                self.current_court_complex_code = court_complex_code
            
            # Correct URL pattern
            url = f"{self.base_url}ecourtindia_v6/?p=casestatus/submitCaseNo"
            
            # Add Referer header
            headers = self.headers.copy()
            headers['Referer'] = f"{self.base_url}ecourtindia_v6/?p=casestatus/index"
            
            # Extract court_complex and est_code from court_complex_code
            # Format: court_code@est_code@flag
            court_arr = (court_complex_code or self.current_court_complex_code).split('@')
            court_complex = court_arr[0] if len(court_arr) > 0 else (court_complex_code or self.current_court_complex_code)
            est_code = court_arr[1] if len(court_arr) > 1 else ''
            
            # Prepare data as string (matching the JavaScript form submission)
            data_str = (f"state_code={state_code or self.current_state_code}&"
                       f"dist_code={district_code or self.current_district_code}&"
                       f"court_complex_code={court_complex}&"
                       f"est_code={est_code}&"
                       f"case_type={case_type_code}&"
                       f"case_no={case_no}&"
                       f"rgyear={case_year}&"
                       f"case_captcha_code={captcha}&"
                       f"ajax_req=true&"
                       f"app_token={self.app_token if self.app_token else ''}")
            
            print(f"DEBUG: Searching case with case_no={case_no}, case_year={case_year}")
            
            response = self.session.post(url, data=data_str, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"DEBUG: Search response status: {result.get('status')}")
                
                # Update app_token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                if result.get('status') == '1' or result.get('status') == 1:
                    print("DEBUG: Case found! Calling get_case_history for detailed data...")
                    
                    # CRITICAL: Call get_case_history to get full case details
                    # This is the TWO-STEP process the original scraper uses
                    return self.get_case_history(result)
                else:
                    error_msg = result.get('error', result.get('errormsg', 'Unknown error'))
                    print(f"DEBUG: Search failed: {error_msg}")
                    return None
            else:
                print(f"DEBUG: Search failed with status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error searching case: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_case_history(self, search_result: Dict) -> Optional[Dict]:
        """Get detailed case history - SECOND API CALL (critical step!)"""
        try:
            print("DEBUG: Fetching detailed case history...")
            
            # Extract viewHistory parameters from the HTML onClick
            if 'case_data' not in search_result:
                print("DEBUG: No case_data in search result")
                return None
            
            html = search_result['case_data']
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the View link with onClick="viewHistory(...)"
            view_link = soup.find('a', {'onclick': lambda x: x and 'viewHistory' in x})
            
            if not view_link:
                print("DEBUG: No viewHistory link found - parsing basic case data as fallback")
                # Return basic parsed data as fallback
                return self.parse_basic_case_data(html, search_result)
            
            # Extract parameters from onClick="viewHistory(param1,param2,...)"
            onclick = view_link.get('onclick', '')
            match = re.search(r"viewHistory\((.*?)\)", onclick)
            
            if not match:
                print("DEBUG: Could not parse viewHistory parameters")
                return self.parse_basic_case_data(html, search_result)
            
            # Parse the parameters (comma-separated, with strings in quotes)
            params_str = match.group(1)
            # Split by comma, handling quoted strings
            params = re.findall(r"'([^']*)'|(\d+)", params_str)
            params = [p[0] if p[0] else p[1] for p in params]
            
            if len(params) < 9:
                print(f"DEBUG: Not enough parameters: {params}")
                return self.parse_basic_case_data(html, search_result)
            
            case_no, cino, sel_court_code, hideparty, case_status_search_type = params[0:5]
            state_code, dist_code, complex_code, search_by = params[5:9]
            
            print(f"DEBUG: Case No: {case_no}, CINO: {cino}")
            
            # Call viewHistory endpoint (SECOND API CALL)
            url = f"{self.base_url}ecourtindia_v6/?p=home/viewHistory"
            
            headers = self.headers.copy()
            headers['Referer'] = f"{self.base_url}ecourtindia_v6/?p=casestatus/index"
            
            data_str = (f"court_code={sel_court_code}&"
                       f"state_code={state_code}&"
                       f"dist_code={dist_code}&"
                       f"court_complex_code={complex_code}&"
                       f"case_no={case_no}&"
                       f"cino={cino}&"
                       f"hideparty={hideparty}&"
                       f"search_flag={case_status_search_type}&"
                       f"search_by={search_by}&"
                       f"ajax_req=true&"
                       f"app_token={self.app_token if self.app_token else ''}")
            
            response = self.session.post(url, data=data_str, headers=headers, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update app_token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                if result.get('status') == '1' or result.get('status') == 1:
                    print("DEBUG: Detailed case history fetched!")
                    
                    # Parse the detailed HTML response from data_list
                    if 'data_list' in result:
                        case_data = self.parse_case_history(result['data_list'])
                        case_data['raw_response'] = result
                        case_data['search_result'] = search_result
                        return case_data
                    else:
                        print("DEBUG: No data_list in response")
                        return {'raw_response': result, 'search_result': search_result}
                else:
                    error_msg = result.get('error', result.get('errormsg', 'Search failed'))
                    print(f"DEBUG: viewHistory failed: {error_msg}")
                    return self.parse_basic_case_data(html, search_result)
            else:
                print(f"DEBUG: viewHistory failed with status {response.status_code}")
                return self.parse_basic_case_data(html, search_result)
                
        except Exception as e:
            print(f"Error getting case history: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def parse_basic_case_data(self, html: str, search_result: Dict) -> Dict:
        """Parse basic case data from search result HTML as fallback"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            case_data = {
                'case_details': {},
                'case_status': {},
                'petitioner': [],
                'respondent': [],
                'raw_response': search_result,
                'search_result': search_result
            }
            
            # Try to extract case number from the HTML
            case_link = soup.find('td')
            if case_link:
                case_data['case_details']['Case Number'] = case_link.get_text(strip=True)
            
            print("DEBUG: Returning basic case data")
            return case_data
            
        except Exception as e:
            print(f"Error parsing basic case data: {e}")
            return {'raw_response': search_result, 'search_result': search_result}
    
    def parse_case_history(self, html: str) -> Dict:
        """Parse case history HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            case_data = {
                'case_details': {},
                'case_status': {},
                'parties': {'petitioners': [], 'respondents': []},
                'acts': [],
                'subordinate_court': {},
                'hearings': [],
                'orders': []
            }
            
            # 1. Extract Case Details
            details_table = soup.find('table', class_='case_details_table')
            if details_table:
                rows = details_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value:
                            case_data['case_details'][key] = value
                    elif len(cells) == 4:
                        key1 = cells[0].get_text(strip=True)
                        value1 = cells[1].get_text(strip=True)
                        key2 = cells[2].get_text(strip=True)
                        value2 = cells[3].get_text(strip=True)
                        if key1 and value1:
                            case_data['case_details'][key1] = value1
                        if key2 and value2:
                            case_data['case_details'][key2] = value2
            
            # 2. Extract Case Status
            status_table = soup.find('table', class_='case_status_table')
            if status_table:
                rows = status_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value:
                            case_data['case_status'][key] = value
                    elif len(cells) == 4:
                        key1 = cells[0].get_text(strip=True)
                        value1 = cells[1].get_text(strip=True)
                        key2 = cells[2].get_text(strip=True)
                        value2 = cells[3].get_text(strip=True)
                        if key1 and value1:
                            case_data['case_status'][key1] = value1
                        if key2 and value2:
                            case_data['case_status'][key2] = value2
            
            # 3. Extract Petitioners
            petitioner_table = soup.find('table', class_='Petitioner_Advocate_table')
            if petitioner_table:
                for cell in petitioner_table.find_all('td'):
                    html_content = str(cell)
                    parts = re.split(r'<br\s*/?>', html_content, flags=re.IGNORECASE)
                    for part in parts:
                        text = BeautifulSoup(part, 'html.parser').get_text(strip=True)
                        text = re.sub(r'\s+', ' ', text).strip()
                        
                        # Extract advocate name if present
                        advocate = ''
                        if 'Advocate' in text or 'advocate' in text:
                            # Extract advocate name
                            adv_match = re.search(r'Advocate[:\s-]*(.+)', text, re.IGNORECASE)
                            if adv_match:
                                advocate = adv_match.group(1).strip()
                                text = re.sub(r'Advocate[:\s-]*.+', '', text, flags=re.IGNORECASE).strip()
                        
                        # Remove numbering
                        name = re.sub(r'^\d+\)\s*', '', text).strip()
                        
                        if name and name not in ['', 'Advocate', 'advocate']:
                            petitioner_entry = {'name': name}
                            if advocate:
                                petitioner_entry['advocate'] = advocate
                            case_data['parties']['petitioners'].append(petitioner_entry)
            
            # 4. Extract Respondents  
            respondent_table = soup.find('table', class_='Respondent_Advocate_table')
            if respondent_table:
                for cell in respondent_table.find_all('td'):
                    html_content = str(cell)
                    parts = re.split(r'<br\s*/?>', html_content, flags=re.IGNORECASE)
                    for part in parts:
                        text = BeautifulSoup(part, 'html.parser').get_text(strip=True)
                        text = re.sub(r'\s+', ' ', text).strip()
                        
                        # Skip advocate lines
                        if text.startswith('Advocate') or text.startswith('advocate'):
                            continue
                        
                        # Remove numbering
                        name = re.sub(r'^\d+\)\s*', '', text).strip()
                        
                        if name and name not in ['', 'Vs', 'vs', 'V/s']:
                            case_data['parties']['respondents'].append({'name': name})
            
            # 4. Extract Acts
            acts_table = soup.find('table', class_='acts_table')
            if acts_table:
                rows = acts_table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        act_name = cells[0].get_text(strip=True)
                        sections = cells[1].get_text(strip=True)
                        if act_name or sections:
                            case_data['acts'].append({
                                'act': act_name,
                                'sections': sections
                            })
            
            # 5. Extract Subordinate Court Info
            lower_court_table = soup.find('table', class_='Lower_court_table')
            if lower_court_table:
                rows = lower_court_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if len(cells) == 4:
                            value = cells[1].get_text(strip=True) + ' ' + cells[3].get_text(strip=True)
                        if key and value:
                            case_data['subordinate_court'][key] = value
            
            # 6. Extract Hearings
            history_table = soup.find('table', class_='history_table')
            if history_table:
                rows = history_table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 4:
                        # Extract business_on_date link
                        business_link = cells[1].find('a')
                        business_on_date = cells[1].get_text(strip=True)
                        business_on_date_link = ''
                        
                        if business_link and business_link.get('onclick'):
                            business_on_date_link = business_link.get('onclick')
                        
                        hearing = {
                            'judge': cells[0].get_text(strip=True),
                            'business_on_date': business_on_date,
                            'hearing_date': cells[2].get_text(strip=True),
                            'purpose': cells[3].get_text(strip=True)
                        }
                        
                        if business_on_date_link:
                            hearing['business_on_date_link'] = business_on_date_link
                        
                        if hearing['business_on_date'] or hearing['hearing_date']:
                            case_data['hearings'].append(hearing)
            
            # 7. Extract Orders
            order_table = soup.find('table', class_='order_table')
            if order_table:
                rows = order_table.find_all('tr')[1:]  # Skip header
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        order_dict = {
                            'order_number': cells[0].get_text(strip=True),
                            'order_date': cells[1].get_text(strip=True),
                            'details': cells[2].get_text(strip=True)
                        }
                        
                        # Extract PDF link if present
                        link = cells[2].find('a')
                        if link and link.get('onclick'):
                            order_dict['pdf_link'] = link.get('onclick')
                        
                        case_data['orders'].append(order_dict)
            
            return case_data
            
        except Exception as e:
            print(f"Error parsing case history: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def download_order_pdf(self, pdf_link: str, pdf_cache=None) -> Optional[Dict]:
        """Download order/judgment PDF and cache in memory or save to disk.
        
        Args:
            pdf_link: The PDF link from the order
            pdf_cache: Optional dict to store PDFs in memory (for Render deployment)
            
        Returns:
            Dict with pdf_id and pdf_url if successful, None otherwise
        """
        try:
            print(f"DEBUG: Downloading PDF from link: {pdf_link}")
            
            # Extract the path from onclick="displayPdf('...')"
            match = re.search(r"displayPdf\('([^']+)'\)", pdf_link)
            if not match:
                print(f"DEBUG: Could not extract path from pdf_link")
                return None
            
            pdf_path = match.group(1)
            print(f"DEBUG: Extracted path: {pdf_path}")
            
            # Parse the path to extract parameters
            # Format: home/display_pdf&filename=/orders/2016/201701005912016_1.pdf&caseno=CRI~APPEAL/100591/2016&court_code=2&appFlag=&normal_v=1
            
            # Split by '&' to get all parts
            parts = pdf_path.split('&')
            endpoint = parts[0]  # home/display_pdf
            
            # Parse parameters
            params = {}
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    params[key] = value
            
            print(f"DEBUG: Endpoint: {endpoint}")
            print(f"DEBUG: Parameters: {params}")
            
            # The PDF is served via POST request to display_pdf endpoint
            url = f"{self.base_url}ecourtindia_v6/?p={endpoint}"
            
            # Prepare POST data
            data_str = '&'.join([f"{k}={v}" for k, v in params.items()])
            data_str += f"&ajax_req=true&app_token={self.app_token if self.app_token else ''}"
            
            print(f"DEBUG: Full PDF URL: {url}")
            print(f"DEBUG: POST data: {data_str}")
            
            # Add proper headers for PDF request
            headers = self.headers.copy()
            headers['Referer'] = f"{self.base_url}ecourtindia_v6/?p=casestatus/index"
            
            # Download PDF using POST
            response = self.session.post(url, data=data_str, headers=headers, timeout=30)
            print(f"DEBUG: PDF response status: {response.status_code}")
            
            if response.status_code == 200 and response.content:
                # Check if it's actually a PDF
                content_type = response.headers.get('content-type', '')
                print(f"DEBUG: Content-Type: {content_type}")
                print(f"DEBUG: Content length: {len(response.content)} bytes")
                
                # Check if content starts with PDF magic bytes
                is_pdf = response.content.startswith(b'%PDF')
                print(f"DEBUG: Is PDF: {is_pdf}")
                
                if not is_pdf:
                    # Response might be JSON with PDF path
                    try:
                        result = response.json()
                        print(f"DEBUG: JSON response: {result}")
                        
                        # Update app_token
                        if 'app_token' in result:
                            self.app_token = result['app_token']
                        
                        # Check if we got a PDF path
                        if 'order' in result:
                            pdf_file_path = result['order']
                            print(f"DEBUG: PDF generated at: {pdf_file_path}")
                            
                            # Download the actual PDF file
                            pdf_download_url = f"{self.base_url}ecourtindia_v6/{pdf_file_path}"
                            print(f"DEBUG: Downloading PDF from: {pdf_download_url}")
                            
                            pdf_response = self.session.get(pdf_download_url, timeout=30)
                            print(f"DEBUG: PDF download status: {pdf_response.status_code}")
                            
                            if pdf_response.status_code == 200 and pdf_response.content.startswith(b'%PDF'):
                                print(f"DEBUG: Successfully downloaded PDF ({len(pdf_response.content)} bytes)")
                                
                                # Use the PDF content for saving
                                response = pdf_response
                                is_pdf = True
                            else:
                                print(f"DEBUG: Failed to download generated PDF")
                                return None
                        else:
                            print(f"DEBUG: No 'order' key in response")
                            return None
                    except ValueError:
                        # Log first 500 chars of response to debug
                        preview = response.content[:500].decode('utf-8', errors='ignore')
                        print(f"DEBUG: Response preview: {preview}")
                        print("DEBUG: Not a valid PDF file - received HTML or error page")
                        return None
                
                if not is_pdf:
                    return None
                
                # Extract filename from path or create one
                if 'filename' in params:
                    original_filename = params['filename'].split('/')[-1]
                    # Clean filename
                    filename = re.sub(r'[^\w\-\.]', '_', original_filename)
                else:
                    # Create a unique filename based on link hash and timestamp
                    hash_obj = hashlib.md5(pdf_link.encode())
                    filename = f"order_{hash_obj.hexdigest()[:12]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                print(f"DEBUG: Saving as: {filename}")
                
                # Generate unique PDF ID
                pdf_id = f"{hashlib.md5((pdf_link + str(datetime.now().timestamp())).encode()).hexdigest()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Cache PDF in memory if cache is provided (for Render deployment)
                if pdf_cache is not None:
                    pdf_cache[pdf_id] = {
                        'content': response.content,
                        'filename': filename,
                        'timestamp': datetime.now().timestamp()
                    }
                    print(f"DEBUG: Cached PDF in memory with ID: {pdf_id}")
                
                # Also try to save to disk for local development (optional fallback)
                try:
                    abs_save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads', 'orders')
                    os.makedirs(abs_save_dir, exist_ok=True)
                    filepath = os.path.join(abs_save_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    print(f"DEBUG: Also saved to disk: {filepath} ({len(response.content)} bytes)")
                except Exception as disk_err:
                    print(f"DEBUG: Could not save to disk (OK for Render): {disk_err}")
                
                # Return PDF info dict
                return {
                    'pdf_id': pdf_id,
                    'pdf_url': f"/api/download-pdf/{pdf_id}"
                }
            
            print(f"DEBUG: Failed to download PDF - status {response.status_code}")
            return None
        except Exception as e:
            print(f"Error downloading PDF: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def download_all_orders(self, case_data: Dict, pdf_cache=None) -> Dict:
        """Download all order PDFs and cache in memory or save to disk.
        
        Args:
            case_data: The case data dictionary
            pdf_cache: Optional dict to store PDFs in memory (for Render deployment)
        """
        if 'orders' not in case_data:
            print("DEBUG: No orders found in case_data")
            return case_data
        
        print(f"DEBUG: Found {len(case_data['orders'])} orders to download")
        
        for order in case_data['orders']:
            if order.get('pdf_link'):
                print(f"DEBUG: Downloading order #{order['order_number']}...")
                pdf_info = self.download_order_pdf(order['pdf_link'], pdf_cache)
                if pdf_info:
                    order['pdf_id'] = pdf_info['pdf_id']
                    order['pdf_url'] = pdf_info['pdf_url']
                    print(f"DEBUG: ✓ Cached PDF: {pdf_info['pdf_id']}")
                else:
                    print(f"DEBUG: ✗ Failed to download order #{order['order_number']}")
            else:
                print(f"DEBUG: Order #{order['order_number']} has no pdf_link")
        
        return case_data
