"""
District Court Cause List Scraper - Web App Version
- Fetches district court cause list data
- Processes cause lists in memory
- Supports State → District → Court Complex → Establishment → Judge selection
- Searches for case numbers or party names
"""

import requests
from bs4 import BeautifulSoup
import base64
import re
import time
from typing import Dict, Optional, List
from datetime import datetime
from captcha_ocr import detect_captcha_text


class DistrictCauseListScraper:
    """District Court Cause List Scraper for web application"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://services.ecourts.gov.in"
        self.session.headers.update({
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://services.ecourts.gov.in',
            'Referer': 'https://services.ecourts.gov.in/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0',
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        
        self.app_token = None
        
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
    
    def initialize_session(self) -> bool:
        """Initialize session and get app_token"""
        try:
            print("[INFO] Initializing session...")
            response = self.session.get(f"{self.base_url}/ecourtindia_v6/", timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'app_token'})
                
                if token_input:
                    self.app_token = token_input.get('value')
                    print(f"[SUCCESS] Session initialized with token: {self.app_token[:20]}...")
                    return True
                else:
                    print("[WARNING] App token not found, will extract from responses")
                    return True
            
            return False
        except Exception as e:
            print(f"[ERROR] Session initialization failed: {e}")
            return False
    
    def get_states(self) -> Dict[str, str]:
        """Return hardcoded states"""
        return self.states
    
    def fetch_districts(self, state_code: str) -> Dict[str, str]:
        """Fetch districts for a state"""
        try:
            if not self.app_token:
                self.initialize_session()
            
            print(f"[INFO] Fetching districts for state code: {state_code}")
            
            url = f"{self.base_url}/ecourtindia_v6/?p=casestatus/fillDistrict"
            
            data_str = f"state_code={state_code}&ajax_req=true&app_token={self.app_token if self.app_token else ''}"
            
            response = self.session.post(url, data=data_str, timeout=10)
            
            if response.status_code == 200:
                response.encoding = 'utf-8-sig'
                result = response.json()
                
                # Update token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                districts = {}
                if 'dist_list' in result:
                    soup = BeautifulSoup(result['dist_list'], 'html.parser')
                    options = soup.find_all('option')
                    
                    for option in options:
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        
                        if value and text and value != '0':
                            districts[text] = value
                    
                    print(f"[SUCCESS] Found {len(districts)} districts")
                    return districts
            
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to fetch districts: {e}")
            return {}
    
    def fetch_court_complexes(self, state_code: str, district_code: str) -> Dict[str, str]:
        """Fetch court complexes for a district"""
        try:
            print(f"[INFO] Fetching court complexes for district: {district_code}")
            
            url = f"{self.base_url}/ecourtindia_v6/?p=casestatus/fillcomplex"
            
            data = {
                'state_code': state_code,
                'dist_code': district_code,
                'ajax_req': 'true',
                'app_token': self.app_token if self.app_token else ''
            }
            
            response = self.session.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                complexes = {}
                if 'complex_list' in result:
                    soup = BeautifulSoup(result['complex_list'], 'html.parser')
                    options = soup.find_all('option')
                    
                    for option in options:
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        
                        if value and value != '' and value != '0':
                            complexes[text] = value
                    
                    print(f"[SUCCESS] Found {len(complexes)} court complexes")
                    return complexes
            
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to fetch court complexes: {e}")
            return {}
    
    def fetch_establishments(self, state_code: str, district_code: str, court_complex_code: str) -> Dict[str, str]:
        """Fetch establishments (court types) for a court complex
        
        Returns empty dict if establishment dropdown is not available (flag=N or flag=0)
        Returns dict with special key '__no_establishment__' if no dropdown needed
        """
        try:
            print(f"[INFO] Fetching establishments for court complex: {court_complex_code}")
            
            # Parse court_complex_code (format: court_code@est_code@flag)
            court_arr = court_complex_code.split('@')
            court_complex = court_arr[0] if len(court_arr) > 0 else court_complex_code
            flag = court_arr[2] if len(court_arr) > 2 else 'Y'
            
            # If flag='N' or flag='0', establishment dropdown is not available
            if flag == 'N' or flag == '0':
                print(f"[INFO] Establishment dropdown not available for this court complex (flag={flag})")
                # Return special marker indicating to skip to judges
                return {'__no_establishment__': court_arr[1] if len(court_arr) > 1 else '0'}
            
            url = f"{self.base_url}/ecourtindia_v6/?p=casestatus/fillCourtEstablishment"
            
            data_str = (f"state_code={state_code}&"
                       f"dist_code={district_code}&"
                       f"court_complex_code={court_complex}&"
                       f"ajax_req=true&"
                       f"app_token={self.app_token if self.app_token else ''}")
            
            response = self.session.post(url, data=data_str, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                establishments = {}
                # The response key is 'establishment_list' not 'est_list'
                if 'establishment_list' in result:
                    soup = BeautifulSoup(result['establishment_list'], 'html.parser')
                    options = soup.find_all('option')
                    
                    for option in options:
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        
                        if value and value != '' and value != '0':
                            establishments[text] = value
                    
                    print(f"[SUCCESS] Found {len(establishments)} establishments")
                    return establishments
            
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to fetch establishments: {e}")
            return {}
    
    def set_data(self, state_code: str, district_code: str, court_complex_code: str, est_code: str = '') -> bool:
        """Call set_data endpoint after selecting court complex/establishment
        This is required before fetching judges
        """
        try:
            print(f"[INFO] Calling set_data for court complex: {court_complex_code}")
            
            url = f"{self.base_url}/ecourtindia_v6/?p=casestatus/set_data"
            
            data_str = (f"complex_code={court_complex_code}&"
                       f"selected_state_code={state_code}&"
                       f"selected_dist_code={district_code}&"
                       f"selected_est_code={est_code}&"
                       f"ajax_req=true&"
                       f"app_token={self.app_token if self.app_token else ''}")
            
            response = self.session.post(url, data=data_str, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                    print(f"[SUCCESS] set_data called, token updated")
                    return True
            
            return False
        except Exception as e:
            print(f"[ERROR] Failed to call set_data: {e}")
            return False
    
    def fetch_judges(self, state_code: str, district_code: str, court_complex_code: str, est_code: str = None) -> Dict[str, str]:
        """Fetch judges/court numbers for an establishment
        
        Args:
            est_code: Can be None if establishment dropdown is not available
        """
        try:
            print(f"[INFO] Fetching judges for establishment: {est_code}")
            
            # Parse court_complex_code
            court_arr = court_complex_code.split('@')
            court_complex = court_arr[0] if len(court_arr) > 0 else court_complex_code
            flag = court_arr[2] if len(court_arr) > 2 else 'Y'
            
            # Determine the est_code to use
            if est_code is None or est_code == '__no_establishment__':
                # If flag is N or 0, use the comma-separated establishment codes from court_complex_code
                if flag == 'N' or flag == '0':
                    est_code_to_use = court_arr[1] if len(court_arr) > 1 else ''
                    print(f"[INFO] Using establishment codes for flag={flag}: {est_code_to_use}")
                else:
                    # Otherwise use the est_code from court_complex_code
                    est_code_to_use = court_arr[1] if len(court_arr) > 1 else ''
                    print(f"[INFO] Using establishment code from court complex: {est_code_to_use}")
            else:
                est_code_to_use = est_code
            
            # For set_data, use empty string when flag='N', but for fillCauseList use the comma-separated codes
            set_data_est_code = '' if (flag == 'N' or flag == '0') else est_code_to_use
            
            # Call set_data first
            self.set_data(state_code, district_code, court_complex_code, set_data_est_code)
            
            url = f"{self.base_url}/ecourtindia_v6/?p=cause_list/fillCauseList"
            
            data_str = (f"state_code={state_code}&"
                       f"dist_code={district_code}&"
                       f"court_complex_code={court_complex}&"
                       f"est_code={est_code_to_use}&"
                       f"search_act=undefined&"
                       f"ajax_req=true&"
                       f"app_token={self.app_token if self.app_token else ''}")
            
            print(f"[DEBUG] fillCauseList request: est_code={est_code_to_use}")
            
            response = self.session.post(url, data=data_str, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Update token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                judges = {}
                # The response key is 'cause_list' not 'court_name_list'
                if 'cause_list' in result:
                    soup = BeautifulSoup(result['cause_list'], 'html.parser')
                    options = soup.find_all('option')
                    
                    print(f"[DEBUG] Total options found: {len(options)}")
                    
                    current_court_type = ""  # Track the current court type (Criminal/Civil)
                    
                    for option in options:
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        
                        print(f"[DEBUG] Option: value='{value}', text='{text}'")
                        
                        # Check if this is a header (disabled option with court type)
                        if value.upper() == 'D':
                            # Extract court type from header text
                            if 'Criminal' in text or 'criminal' in text:
                                current_court_type = " (Criminal)"
                            elif 'Civil' in text or 'civil' in text:
                                current_court_type = " (Civil)"
                            else:
                                current_court_type = ""
                            print(f"[DEBUG] Found court type header: {current_court_type}")
                            continue
                        
                        # Skip empty values
                        if value and value != '' and value != '0':
                            # Append court type to judge name if available
                            display_text = text + current_court_type
                            judges[value] = display_text
                            print(f"[DEBUG] Added judge: {value} -> {display_text}")
                    
                    print(f"[SUCCESS] Found {len(judges)} judges/courts")
                    return judges
            
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to fetch judges: {e}")
            return {}
    
    def get_captcha(self) -> Optional[Dict]:
        """Get CAPTCHA image as base64"""
        try:
            if not self.app_token:
                self.initialize_session()
            
            url = f"{self.base_url}/ecourtindia_v6/vendor/securimage/securimage_show.php"
            timestamp = int(time.time() * 1000)
            
            response = self.session.get(f"{url}?{timestamp}", timeout=10)
            
            if response.status_code == 200:
                img_base64 = base64.b64encode(response.content).decode('utf-8')
                captcha_url = f"data:image/png;base64,{img_base64}"
                
                # Attempt to auto-detect captcha text using OCR
                detected_text = detect_captcha_text(response.content)
                print(f"[OCR] Auto-detected CAPTCHA text: '{detected_text}'")
                
                print(f"[SUCCESS] CAPTCHA fetched successfully")
                return {
                    'captcha_url': captcha_url,
                    'detected_text': detected_text
                }
            
            return None
        except Exception as e:
            print(f"[ERROR] Failed to fetch CAPTCHA: {e}")
            return None
    
    def fetch_cause_list(self, state_code: str, district_code: str, court_complex_code: str, 
                        est_code: str, court_no: str, court_name: str, date: str, captcha: str, 
                        case_type: str = 'civ') -> Optional[Dict]:
        """
        Fetch cause list data
        
        Args:
            state_code: State code
            district_code: District code
            court_complex_code: Court complex code
            est_code: Establishment code (can be empty string)
            court_no: Court number (format: est_code^court_no)
            court_name: Full court name text
            date: Date in DD-MM-YYYY format
            captcha: CAPTCHA text
            case_type: 'civ' for civil, 'cri' for criminal
        """
        try:
            print(f"[INFO] Fetching cause list for court: {court_no}, date: {date}, type: {case_type}")
            print(f"[DEBUG] court_name parameter: '{court_name}'")
            print(f"[DEBUG] captcha parameter: '{captcha}'")
            
            url = f"{self.base_url}/ecourtindia_v6/?p=cause_list/submitCauseList"
            
            # Parse court_complex_code to get just the court code
            court_arr = court_complex_code.split('@')
            court_complex = court_arr[0] if len(court_arr) > 0 else court_complex_code
            
            data_str = (f"CL_court_no={court_no}&"
                       f"causelist_date={date}&"
                       f"cause_list_captcha_code={captcha}&"
                       f"court_name_txt={court_name}&"
                       f"state_code={state_code}&"
                       f"dist_code={district_code}&"
                       f"court_complex_code={court_complex}&"
                       f"est_code={est_code if est_code and est_code != '__no_establishment__' else ''}&"
                       f"cicri={case_type}&"
                       f"selprevdays=0&"
                       f"ajax_req=true&"
                       f"app_token={self.app_token if self.app_token else ''}")
            
            print(f"[DEBUG] Request parameters: state={state_code}, dist={district_code}, complex={court_complex}, est={est_code if est_code and est_code != '__no_establishment__' else ''}, court={court_no}, date={date}, type={case_type}, court_name_txt={court_name}")
            
            response = self.session.post(url, data=data_str, timeout=15)
            
            print(f"[DEBUG] Response status code: {response.status_code}")
            print(f"[DEBUG] Response content-type: {response.headers.get('content-type')}")
            print(f"[DEBUG] Response text preview: {response.text[:500]}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except Exception as e:
                    print(f"[ERROR] JSON decode failed: {e}")
                    print(f"[DEBUG] Full response text: {response.text}")
                    return None
                
                # Update token
                if 'app_token' in result:
                    self.app_token = result['app_token']
                
                # Log the full response for debugging
                print(f"[DEBUG] Response keys: {result.keys()}")
                print(f"[DEBUG] Response status: {result.get('status')}")
                if 'error' in result:
                    print(f"[DEBUG] Response error: {result.get('error')}")
                print(f"[DEBUG] Case data length: {len(result.get('case_data', ''))}")
                
                # Check for invalid captcha
                if 'error' in result:
                    if 'captcha' in result['error'].lower() or 'invalid' in result['error'].lower():
                        print(f"[ERROR] Invalid CAPTCHA or error: {result['error']}")
                        return None
                
                # Check for case data
                if 'case_data' in result:
                    case_data_html = result['case_data']
                    
                    # Log first 500 chars of case_data for debugging
                    print(f"[DEBUG] Case data preview: {case_data_html[:500]}")
                    
                    # Check if no records found
                    if 'Record not found' in case_data_html or 'No record found' in case_data_html:
                        print("[INFO] No cause list records found for this date")
                        return {
                            'status': 'no_records',
                            'message': 'No cause list records found for the selected date and court'
                        }
                    
                    print(f"[SUCCESS] Cause list data fetched")
                    return {
                        'status': 'success',
                        'case_data_html': case_data_html,
                        'raw_response': result
                    }
                else:
                    print("[WARNING] No case_data in response")
                    print(f"[DEBUG] Response keys: {result.keys()}")
                    return None
            
            return None
        except Exception as e:
            print(f"[ERROR] Failed to fetch cause list: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def parse_cause_list_html(self, html: str) -> List[Dict]:
        """Parse cause list HTML and extract case details"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            cases = []
            
            # Find all case entries
            # The structure varies, but typically uses tables or divs
            tables = soup.find_all('table')
            
            print(f"[DEBUG] Found {len(tables)} tables in HTML")
            
            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                print(f"[DEBUG] Table {table_idx + 1} has {len(rows)} rows")
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) >= 2:
                        # Extract text from cells
                        case_info = {
                            'serial_no': cells[0].get_text(strip=True) if len(cells) > 0 else '',
                            'case_details': ' | '.join([cell.get_text(strip=True) for cell in cells[1:]]),
                            'full_text': row.get_text(strip=True)
                        }
                        
                        # Only add if it has content and not a header row
                        if (case_info['full_text'] and 
                            len(case_info['full_text']) > 10 and
                            not re.match(r'^(Sr\.?|S\.No|Serial|Case|Court)', case_info['full_text'], re.IGNORECASE)):
                            cases.append(case_info)
            
            # If no table structure found, try div-based structure
            if not cases:
                print("[DEBUG] No cases found in tables, trying divs...")
                divs = soup.find_all('div', class_=re.compile('case|item|entry'))
                for div in divs:
                    text = div.get_text(strip=True)
                    if text and len(text) > 10:
                        cases.append({
                            'serial_no': '',
                            'case_details': text,
                            'full_text': text
                        })
            
            # If still no cases, try plain text parsing
            if not cases:
                print("[DEBUG] No cases found in structured HTML, trying plain text parsing...")
                text = soup.get_text()
                lines = text.split('\n')
                
                current_case = []
                for line in lines:
                    line = line.strip()
                    if line:
                        # Check if this looks like a new case entry (starts with number or case type)
                        if re.match(r'^\d+[\.\)]\s+', line) or re.match(r'^[A-Z]+[/\d\-]+', line):
                            if current_case:
                                full_text = ' '.join(current_case)
                                if len(full_text) > 10:
                                    cases.append({
                                        'serial_no': '',
                                        'case_details': full_text,
                                        'full_text': full_text
                                    })
                            current_case = [line]
                        else:
                            current_case.append(line)
                
                # Add last case
                if current_case:
                    full_text = ' '.join(current_case)
                    if len(full_text) > 10:
                        cases.append({
                            'serial_no': '',
                            'case_details': full_text,
                            'full_text': full_text
                        })
            
            print(f"[SUCCESS] Parsed {len(cases)} case entries")
            return cases
        except Exception as e:
            print(f"[ERROR] Failed to parse cause list HTML: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def search_in_cause_list(self, cases: List[Dict], search_term: str, is_party_name: bool = False) -> List[Dict]:
        """Search for case number or party name in cause list"""
        print(f"[INFO] Searching for: {search_term} (party_name: {is_party_name})")
        
        matches = []
        
        for idx, case in enumerate(cases):
            found = False
            
            if is_party_name:
                # Case-insensitive search for party name
                if search_term.lower() in case['full_text'].lower():
                    found = True
            else:
                # Search for case number (remove special chars for matching)
                case_clean = re.sub(r'[^\w\d]', '', search_term).upper()
                text_clean = re.sub(r'[^\w\d]', '', case['full_text']).upper()
                if case_clean in text_clean or search_term.upper() in case['full_text'].upper():
                    found = True
            
            if found:
                matches.append({
                    'index': idx,
                    'serial_no': case['serial_no'],
                    'case_details': case['case_details'],
                    'full_text': case['full_text'],
                    'matched_term': search_term
                })
        
        print(f"[SUCCESS] Found {len(matches)} matches")
        return matches
    
    def process_cause_list_search(self, state_code: str, district_code: str, court_complex_code: str,
                                  est_code: str, court_no: str, court_name: str, date: str, captcha: str,
                                  search_term: str, is_party_name: bool = False,
                                  case_type: str = 'civ') -> Dict:
        """
        Complete workflow to fetch and search cause list
        
        Returns:
            Dict with search results
        """
        results = {
            'search_term': search_term,
            'search_type': 'party_name' if is_party_name else 'case_number',
            'date': date,
            'court_no': court_no,
            'court_name': court_name,
            'case_type': case_type,
            'status': 'pending',
            'matches': []
        }
        
        # Fetch cause list
        cause_list_data = self.fetch_cause_list(
            state_code, district_code, court_complex_code,
            est_code, court_no, court_name, date, captcha, case_type
        )
        
        if not cause_list_data:
            results['status'] = 'error'
            results['message'] = 'Failed to fetch cause list or invalid CAPTCHA'
            return results
        
        if cause_list_data.get('status') == 'no_records':
            results['status'] = 'no_records'
            results['message'] = cause_list_data.get('message')
            return results
        
        # Parse HTML
        cases = self.parse_cause_list_html(cause_list_data['case_data_html'])
        
        if not cases:
            results['status'] = 'no_cases'
            results['message'] = 'No cases found in cause list'
            return results
        
        # Search for term
        matches = self.search_in_cause_list(cases, search_term, is_party_name)
        
        results['status'] = 'success'
        results['total_cases'] = len(cases)
        results['all_cases'] = cases  # Include all cases from the cause list
        results['matches'] = matches
        results['match_count'] = len(matches)
        
        return results
