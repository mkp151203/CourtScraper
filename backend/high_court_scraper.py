import requests
from bs4 import BeautifulSoup
import json
import re
import base64
import io
from typing import Dict, Optional, List
from PIL import Image

class HCServicesCompleteScraper:
    """Simplified High Court scraper for web app"""
    
    def __init__(self):
        self.base_url = "https://hcservices.ecourts.gov.in/hcservices/"
        self.session = requests.Session()
        
        self.headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://hcservices.ecourts.gov.in',
            'Referer': 'https://hcservices.ecourts.gov.in/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
        self.session.headers.update(self.headers)
        
        self.court_code = "1"
        self.state_code = "26"
        self.court_complex_code = "1"
        self.current_court_name = "Delhi High Court"
        self.available_case_types = {}
    
    def initialize_session(self) -> bool:
        """Initialize session"""
        try:
            response = self.session.get(f"{self.base_url}main.php", timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def fetch_available_courts(self) -> List[Dict]:
        """Fetch all available High Courts"""
        fallback_courts = [
            {'court_code': '1', 'state_code': '26', 'court_name': 'Delhi High Court'},
            {'court_code': '2', 'state_code': '1', 'court_name': 'Allahabad High Court'},
            {'court_code': '3', 'state_code': '2', 'court_name': 'Andhra Pradesh High Court'},
            {'court_code': '4', 'state_code': '3', 'court_name': 'Bombay High Court'},
            {'court_code': '5', 'state_code': '4', 'court_name': 'Calcutta High Court'},
            {'court_code': '6', 'state_code': '5', 'court_name': 'Chhattisgarh High Court'},
            {'court_code': '7', 'state_code': '7', 'court_name': 'Gujarat High Court'},
            {'court_code': '8', 'state_code': '8', 'court_name': 'Guwahati High Court'},
            {'court_code': '9', 'state_code': '9', 'court_name': 'Himachal Pradesh High Court'},
            {'court_code': '10', 'state_code': '10', 'court_name': 'Jammu & Kashmir High Court'},
            {'court_code': '11', 'state_code': '11', 'court_name': 'Jharkhand High Court'},
            {'court_code': '12', 'state_code': '12', 'court_name': 'Karnataka High Court'},
            {'court_code': '13', 'state_code': '13', 'court_name': 'Kerala High Court'},
            {'court_code': '14', 'state_code': '14', 'court_name': 'Madhya Pradesh High Court'},
            {'court_code': '15', 'state_code': '15', 'court_name': 'Madras High Court'},
            {'court_code': '16', 'state_code': '17', 'court_name': 'Orissa High Court'},
            {'court_code': '17', 'state_code': '18', 'court_name': 'Patna High Court'},
            {'court_code': '18', 'state_code': '19', 'court_name': 'Punjab & Haryana High Court'},
            {'court_code': '19', 'state_code': '20', 'court_name': 'Rajasthan High Court'},
            {'court_code': '20', 'state_code': '21', 'court_name': 'Sikkim High Court'},
            {'court_code': '21', 'state_code': '22', 'court_name': 'Telangana High Court'},
            {'court_code': '22', 'state_code': '24', 'court_name': 'Tripura High Court'},
            {'court_code': '23', 'state_code': '25', 'court_name': 'Uttarakhand High Court'},
            {'court_code': '24', 'state_code': '27', 'court_name': 'Manipur High Court'},
            {'court_code': '25', 'state_code': '28', 'court_name': 'Meghalaya High Court'},
        ]
        return fallback_courts
    
    def fetch_court_complexes(self):
        """Fetch court complexes - uses default"""
        self.court_complex_code = "1"
    
    def get_case_types(self) -> Dict:
        """Fetch case types from API or use comprehensive defaults"""
        try:
            url = f"{self.base_url}cases_qry/index_qry.php?action_code=fillCaseType"
            data_str = f"court_code={self.court_code}&state_code={self.state_code}"
            
            headers = self.headers.copy()
            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
            
            response = self.session.post(url, data=data_str, headers=headers, timeout=15)
            
            if response.status_code == 200:
                response.encoding = 'utf-8-sig'
                response_text = response.text.strip()
                
                # Try parsing delimited format: "code~name#code~name#..."
                if '#' in response_text and '~' in response_text:
                    parsed_types = {}
                    items = response_text.split('#')
                    
                    for item in items:
                        item = item.strip()
                        if not item or '~' not in item:
                            continue
                        
                        parts = item.split('~', 1)
                        if len(parts) != 2:
                            continue
                        
                        code = parts[0].strip()
                        name_part = parts[1].strip()
                        
                        # Skip "Select" option
                        if code == '0' or 'select' in name_part.lower():
                            continue
                        
                        # Remove trailing -CODE if present
                        if '-' in name_part:
                            last_dash_idx = name_part.rfind('-')
                            potential_code = name_part[last_dash_idx+1:].strip()
                            if potential_code == code:
                                name_part = name_part[:last_dash_idx].strip()
                        
                        if code and name_part:
                            parsed_types[code] = name_part
                    
                    if parsed_types:
                        self.available_case_types = parsed_types
                        return parsed_types
        except:
            pass
        
        # Use comprehensive default case types
        default_case_types = {
            '1': 'Civil Appeal',
            '2': 'Civil Revision',
            '3': 'Civil Writ Petition',
            '4': 'Criminal Appeal',
            '5': 'Criminal Revision',
            '6': 'Criminal Writ Petition',
            '7': 'Company Petition',
            '8': 'Arbitration Petition',
            '9': 'Contempt Petition',
            '10': 'Matrimonial Appeal',
            '50': 'Special Leave Petition (Civil)',
            '51': 'Special Leave Petition (Criminal)',
            '83': 'ARB.A. (Arbitration Appeal)',
            '100': 'PIL (Public Interest Litigation)',
            '102': 'ARB. A. (COMM.)',
            '134': 'W.P.(C) - Writ Petition (Civil)',
            '135': 'W.P.(CRL) - Writ Petition (Criminal)',
            '136': 'Crl.A. - Criminal Appeal',
            '137': 'C.R.P. - Civil Revision Petition',
            '138': 'FAO - First Appeal from Order',
            '139': 'RFA - Regular First Appeal',
            '140': 'CS - Civil Suit',
            '141': 'Execution Petition',
            '142': 'Bail Application',
        }
        self.available_case_types = default_case_types
        return default_case_types
    
    def get_captcha(self) -> Optional[Dict]:
        """Get captcha image - using the same method as original scraper.py"""
        try:
            # Generate captcha URL with random parameter (same as scraper.py)
            import random
            random_param = random.randint(10, 99)
            captcha_url = f"{self.base_url}securimage/securimage_show.php?{random_param}"
            
            response = self.session.get(captcha_url, timeout=10)
            
            if response.status_code == 200:
                # Convert image to base64 for web display
                img_base64 = base64.b64encode(response.content).decode('utf-8')
                captcha_data_url = f"data:image/png;base64,{img_base64}"
                
                return {
                    'captcha_url': captcha_data_url,
                    'captcha_image': response.content
                }
            return None
        except Exception as e:
            print(f"Error getting captcha: {e}")
            return None
    
    def search_case(self, case_type: str, case_no: str, year: str, captcha: str) -> Optional[Dict]:
        """Search for case details"""
        try:
            url = f"{self.base_url}cases_qry/index_qry.php?action_code=showRecords"
            
            data = {
                'court_code': self.court_code,
                'state_code': self.state_code,
                'court_complex_code': self.court_complex_code,
                'caseStatusSearchType': 'CScaseNumber',
                'captcha': captcha,
                'case_type': case_type,
                'case_no': case_no,
                'rgyear': year,
                'caseNoType': 'new',
                'displayOldCaseNo': 'NO'
            }
            
            response = self.session.post(url, data=data, timeout=15)
            
            if response.status_code == 200:
                response.encoding = 'utf-8-sig'
                result = response.json()
                
                if result.get('Error') == '':
                    return result
                return None
            return None
        except:
            return None
    
    def get_case_history(self, case_details: Dict) -> Optional[str]:
        """Fetch detailed case history HTML"""
        try:
            con_data = json.loads(case_details['con'][0])
            case_info = con_data[0]
            
            url = f"{self.base_url}cases_qry/o_civil_case_history.php"
            
            data = {
                'court_code': self.court_code,
                'state_code': self.state_code,
                'court_complex_code': self.court_complex_code,
                'case_no': case_info['case_no'],
                'cino': case_info['cino'],
                'appFlag': ''
            }
            
            response = self.session.post(url, data=data, timeout=15)
            
            if response.status_code == 200:
                return response.text
            return None
        except:
            return None
    
    def parse_case_history(self, html: str) -> Dict:
        """Parse case history HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            case_data = {
                'court_info': {
                    'court_name': self.current_court_name,
                    'court_code': self.court_code,
                    'state_code': self.state_code
                },
                'case_details': {},
                'case_status': {},
                'parties': {},
                'orders': []
            }
            
            # Extract case details
            details_table = soup.find('table', class_='case_details_table')
            if details_table:
                rows = details_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        for i in range(0, len(cells), 2):
                            if i+1 < len(cells):
                                key = cells[i].get_text(strip=True)
                                value = cells[i+1].get_text(strip=True)
                                case_data['case_details'][key] = value
            
            # Extract case status
            status_table = soup.find('table', class_='table_r')
            if status_table:
                rows = status_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        case_data['case_status'][key] = value
            
            # Extract parties
            pet_span = soup.find('span', class_='Petitioner_Advocate_table')
            if pet_span:
                case_data['parties']['petitioner'] = pet_span.get_text(strip=True)
            
            res_span = soup.find('span', class_='Respondent_Advocate_table')
            if res_span:
                case_data['parties']['respondent'] = res_span.get_text(strip=True)
            
            # Extract orders
            order_table = soup.find('table', class_='order_table')
            if order_table:
                rows = order_table.find_all('tr')[1:]
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 5:
                        order = {
                            'order_number': cells[0].get_text(strip=True),
                            'order_on': cells[1].get_text(strip=True),
                            'judge': cells[2].get_text(strip=True),
                            'order_date': cells[3].get_text(strip=True),
                            'view_link': cells[4].find('a')['href'] if cells[4].find('a') else None
                        }
                        case_data['orders'].append(order)
            
            return case_data
        except Exception as e:
            return {}
    
    def download_order_pdf(self, view_link: str, save_dir: Optional[str] = None) -> Optional[str]:
        """Download order/judgment PDF and return local file path.

        By default saves into the webapp backend downloads folder so the Flask app
        can serve the file without relying on remote viewer sessions.
        Returns a backend-relative path like 'downloads/orders/<filename>.pdf' on success.
        """
        try:
            import os
            from datetime import datetime
            import hashlib

            # Default backend downloads location: prefer the local backend downloads
            # folder next to this scraper (i.e. CourtScraper/backend/downloads/orders).
            # Fall back to the older webapp/backend/downloads/orders path if needed.
            scraper_dir = os.path.dirname(os.path.abspath(__file__))

            if save_dir is None:
                primary_dir = os.path.join(scraper_dir, 'downloads', 'orders')
                # fallback to project_root/webapp/backend/downloads/orders
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                fallback_dir = os.path.join(project_root, 'webapp', 'backend', 'downloads', 'orders')

                # Prefer primary_dir (next to this file). If it doesn't exist, we'll still
                # create it. Use fallback only if primary cannot be created for some reason.
                abs_save_dir = primary_dir
                rel_save_dir = os.path.join('downloads', 'orders')
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                abs_save_dir = os.path.join(project_root, save_dir)
                rel_save_dir = save_dir

            # Create directory if it doesn't exist
            os.makedirs(abs_save_dir, exist_ok=True)

            # Construct full URL
            url = f"{self.base_url}{view_link}"

            # Download PDF
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                # Create a unique filename
                hash_obj = hashlib.md5(view_link.encode())
                filename = f"order_{hash_obj.hexdigest()[:12]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                filepath = os.path.join(abs_save_dir, filename)

                # Save PDF
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                # Return backend-relative path for use by the webapp (e.g. '/api/download-pdf/<path>')
                return os.path.join(rel_save_dir, filename)

            return None
        except Exception as e:
            print(f"Error downloading PDF: {e}")
            return None
    
    def download_all_orders(self, case_data: Dict, save_dir: Optional[str] = None) -> Dict:
        """Download all order PDFs and update case_data with local paths.

        Uses the backend downloads folder by default (same behavior as download_order_pdf).
        """
        if 'orders' not in case_data:
            return case_data

        for order in case_data['orders']:
            if order.get('view_link'):
                try:
                    print(f"Downloading order #{order.get('order_number', '?')}...")
                    local_path = self.download_order_pdf(order['view_link'], save_dir)
                    if local_path:
                        order['local_pdf_path'] = local_path
                        print(f"✓ Saved to {local_path}")
                    else:
                        print(f"✗ Failed to download order #{order.get('order_number', '?')}")
                except Exception:
                    print(f"✗ Exception while downloading order #{order.get('order_number', '?')}")

        return case_data
