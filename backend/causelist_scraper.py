"""
High Court Cause List Scraper - Web App Version
- Fetches cause list PDFs
- Processes PDFs in memory (no disk storage)
- Searches for case numbers or party names
- Returns matching PDFs with details
"""

import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import json
from datetime import datetime
import time
import PyPDF2
import re
import base64
import hashlib
from urllib.parse import urljoin
from typing import Dict, Optional, List
from captcha_ocr import detect_captcha_text


class HCCauseListScraper:
    """High Court Cause List Scraper for web application"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://hcservices.ecourts.gov.in/hcservices"
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': 'https://hcservices.ecourts.gov.in/hcservices/'
        })
        
        self.current_state_code = None
        self.current_court_code = None
    
    def get_all_high_courts(self) -> List[Dict]:
        """
        Returns list of all High Courts with their state codes
        Based on actual hcservices.ecourts.gov.in court list
        """
        return [
            {"state_code": "0", "court_code": "0", "name": "Select Highcourt"},
            {"state_code": "13", "court_code": "13", "name": "Allahabad High Court"},
            {"state_code": "1", "court_code": "1", "name": "Bombay High Court"},
            {"state_code": "16", "court_code": "16", "name": "Calcutta High Court"},
            {"state_code": "6", "court_code": "6", "name": "Gauhati High Court"},
            {"state_code": "19", "court_code": "19", "name": "High Court for State of Telangana"},
            {"state_code": "2", "court_code": "2", "name": "High Court of Andhra Pradesh"},
            {"state_code": "18", "court_code": "18", "name": "High Court of Chhattisgarh"},
            {"state_code": "26", "court_code": "26", "name": "High Court of Delhi"},
            {"state_code": "17", "court_code": "17", "name": "High Court of Gujarat"},
            {"state_code": "5", "court_code": "5", "name": "High Court of Himachal Pradesh"},
            {"state_code": "7", "court_code": "7", "name": "High Court of Jharkhand"},
            {"state_code": "12", "court_code": "12", "name": "High Court of Jammu and Kashmir"},
            {"state_code": "4", "court_code": "4", "name": "High Court of Kerala"},
            {"state_code": "23", "court_code": "23", "name": "High Court of Madhya Pradesh"},
            {"state_code": "25", "court_code": "25", "name": "High Court of Manipur"},
            {"state_code": "21", "court_code": "21", "name": "High Court of Meghalaya"},
            {"state_code": "11", "court_code": "11", "name": "High Court of Orissa"},
            {"state_code": "22", "court_code": "22", "name": "High Court of Punjab and Haryana"},
            {"state_code": "9", "court_code": "9", "name": "High Court of Rajasthan"},
            {"state_code": "24", "court_code": "24", "name": "High Court of Sikkim"},
            {"state_code": "20", "court_code": "20", "name": "High Court of Tripura"},
            {"state_code": "15", "court_code": "15", "name": "High Court of Uttarakhand"},
            {"state_code": "3", "court_code": "3", "name": "High Court of Karnataka"},
            {"state_code": "10", "court_code": "10", "name": "Madras High Court"},
            {"state_code": "8", "court_code": "8", "name": "Patna High Court"},
        ]
    
    def fetch_benches(self, state_code: str) -> List[Dict]:
        """
        Fetch available benches (court codes) for a selected High Court
        Returns: List of benches with code and name
        """
        try:
            data = {
                'action_code': 'fillHCBench',
                'state_code': state_code,
                'appFlag': 'web'
            }
            
            response = self.session.post(
                f"{self.base_url}/cases_qry/index_qry.php",
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                benches = []
                items = response.text.split('#')
                
                for item in items:
                    if '~' in item:
                        parts = item.split('~', 1)
                        court_code = parts[0].strip()
                        name = parts[1].strip() if len(parts) > 1 else ''
                        
                        if court_code != '0' and name:
                            benches.append({
                                'court_code': court_code,
                                'name': name
                            })
                
                print(f"[SUCCESS] Fetched {len(benches)} benches/court locations")
                return benches
            else:
                print(f"[ERROR] Failed to fetch benches: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[ERROR] Exception while fetching benches: {e}")
            return []
    
    def get_captcha(self) -> Optional[Dict]:
        """
        Get CAPTCHA image as base64 for web app
        Returns: Dict with captcha_url (data URL)
        """
        try:
            url = f"{self.base_url}/securimage/securimage_show.php"
            timestamp = int(time.time() * 1000)
            response = self.session.get(f"{url}?{timestamp}", timeout=10)
            
            if response.status_code == 200:
                # Convert to base64 for web display
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
            else:
                print(f"[ERROR] Failed to fetch CAPTCHA: {response.status_code}")
                return None
        except Exception as e:
            print(f"[ERROR] Exception while fetching CAPTCHA: {e}")
            return None
    
    def fetch_cause_list(self, state_code: str, court_code: str, date: str, captcha: str) -> Optional[List[Dict]]:
        """
        Fetch cause list with CAPTCHA validation
        Date format: DD-MM-YYYY
        Returns: List of cause list items with PDF links
        """
        try:
            data = {
                'action_code': 'showCauseList',
                'flag': '',
                'selprevdays': '0',
                'captcha': captcha,
                'state_code': state_code,
                'court_code': court_code,
                'caseStatusSearchType': 'CLcauselist',
                'appFlag': '',
                'causelist_date': date
            }
            
            print(f"[DEBUG] Request data: state_code={state_code}, court_code={court_code}, date={date}")
            
            response = self.session.post(
                f"{self.base_url}/cases_qry/index_qry.php",
                data=data,
                timeout=15
            )
            
            if response.status_code == 200:
                if 'Invalid Captcha' in response.text or 'captcha' in response.text.lower():
                    print("[ERROR] Invalid CAPTCHA entered!")
                    return None
                
                soup = BeautifulSoup(response.text, 'html.parser')
                table = soup.find('table', class_='causelistTbl')
                
                if not table:
                    print("[WARNING] No cause list table found in response")
                    return []
                
                results = []
                tbody = table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 4:
                            link_tag = cells[3].find('a')
                            pdf_link = ''
                            
                            if link_tag and link_tag.get('href'):
                                pdf_link = urljoin(self.base_url + '/', link_tag['href'])
                            
                            results.append({
                                'sr_no': cells[0].text.strip(),
                                'bench': cells[1].text.strip(),
                                'type': cells[2].text.strip(),
                                'pdf_link': pdf_link
                            })
                    
                    print(f"[SUCCESS] Found {len(results)} cause lists")
                    return results
                else:
                    print("[WARNING] No tbody found in table")
                    return []
            else:
                print(f"[ERROR] Failed to fetch cause list: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Exception while fetching cause list: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def download_pdf_to_memory(self, pdf_url: str) -> Optional[bytes]:
        """
        Download PDF to memory (not to disk)
        Returns: PDF content as bytes or None
        """
        try:
            print(f"[INFO] Fetching PDF: {pdf_url}")
            response = self.session.get(pdf_url, timeout=30)
            
            if response.status_code == 200:
                print(f"[SUCCESS] PDF fetched ({len(response.content)} bytes)")
                return response.content
            else:
                print(f"[ERROR] Failed to fetch PDF: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Exception while fetching PDF: {e}")
            return None
    
    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes (in memory)
        Returns: Extracted text as string
        """
        try:
            print(f"[INFO] Extracting text from PDF...")
            text = ""
            
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
            
            print(f"[SUCCESS] Extracted {len(text)} characters from PDF")
            return text
            
        except Exception as e:
            print(f"[ERROR] Exception while extracting text from PDF: {e}")
            return ""
    
    def search_case_in_text(self, search_term: str, text: str, is_party_name: bool = False) -> List[Dict]:
        """
        Search for case number or party name in text
        Returns: List of matches with context
        """
        print(f"[INFO] Searching for: {search_term}")
        
        matches = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            search_found = False
            if is_party_name:
                # Case-insensitive search for party name
                if search_term.lower() in line.lower():
                    search_found = True
            else:
                # Search for case number (remove special chars for matching)
                case_clean = re.sub(r'[^\w\d]', '', search_term).upper()
                line_clean = re.sub(r'[^\w\d]', '', line).upper()
                if case_clean in line_clean or search_term.upper() in line.upper():
                    search_found = True
            
            if search_found:
                # Find start of case entry (backtrack to find serial number or section header)
                case_start = i
                while case_start > 0:
                    prev_line = lines[case_start - 1].strip()
                    if (re.search(r'^\d+[\.\)]\s*$', prev_line) or 
                        re.search(r'^Sr\.|^S\.No|^Serial', prev_line, re.IGNORECASE) or 
                        (prev_line == '' and case_start > 1 and lines[case_start - 2].strip() == '')):
                        break
                    if re.match(r'^\d+[\.\)]\s+[A-Z]+', prev_line):
                        break
                    case_start -= 1
                
                # Find end of case entry
                case_end = i + 1
                empty_line_count = 0
                while case_end < len(lines):
                    next_line = lines[case_end].strip()
                    
                    # Stop if we hit next case number (starting with digit followed by case type)
                    if re.match(r'^\d+[\.\)]\s*[A-Z]', next_line):
                        break
                    
                    # Stop if we hit just a number (likely next serial number)
                    if re.match(r'^\d+[\.\)]?\s*$', next_line):
                        break
                    
                    # Stop after 2 consecutive empty lines
                    if next_line == '':
                        empty_line_count += 1
                        if empty_line_count >= 2:
                            break
                    else:
                        empty_line_count = 0
                    
                    # Stop if we hit a section header (ORDERS, ADMISSION, etc.)
                    if re.search(r'^(ORDERS|ADMISSION|MOTION|FINAL|REGULAR|PRELIMINARY|MISCELLANEOUS|Sr\.|S\.No|Serial|Item)', next_line, re.IGNORECASE):
                        break
                    
                    # Stop if line looks like page number or footer
                    if re.match(r'^\d+/\d+\s*$', next_line):
                        break
                    
                    case_end += 1
                
                case_entry = '\n'.join(lines[case_start:case_end])
                
                matches.append({
                    'line_number': i + 1,
                    'matched_line': line.strip(),
                    'full_case_entry': case_entry.strip(),
                    'start_line': case_start + 1,
                    'end_line': case_end
                })
                
                i = case_end
            else:
                i += 1
        
        print(f"[SUCCESS] Found {len(matches)} matches")
        return matches
    
    def process_cause_list_pdfs(self, cause_list_items: List[Dict], search_term: str, 
                                 is_party_name: bool, pdf_cache: Dict, progress_callback=None) -> Dict:
        """
        Process all cause list PDFs in memory, search for matches, store in pdf_cache
        
        MEMORY MANAGEMENT STRATEGY:
        - Only PDFs with matches are stored in pdf_cache (for download with highlights)
        - Non-matching PDFs are NOT stored (saved via 'all_pdfs' with original URLs)
        - Frontend uses proxy endpoint to fetch non-matching PDFs on-demand
        - This prevents storing 100+ PDFs (could be 500+ MB) in memory
        
        Args:
            cause_list_items: List of cause list items with PDF links
            search_term: Case number or party name to search
            is_party_name: Whether searching for party name (True) or case number (False)
            pdf_cache: Global PDF cache to store ONLY matching PDFs
            progress_callback: Optional callback function(current, total, message)
        
        Returns:
            Dict with results per PDF
        """
        results = {
            'search_term': search_term,
            'search_type': 'party_name' if is_party_name else 'case_number',
            'total_pdfs_scanned': 0,
            'pdfs_with_matches': 0,
            'total_matches': 0,
            'matching_pdfs': [],
            'all_pdfs': cause_list_items  # Include all PDFs from cause list
        }
        
        print(f"\n{'='*80}")
        print(f"STREAMING SEARCH FOR {'PARTY NAME' if is_party_name else 'CASE NUMBER'}: {search_term}")
        print(f"{'='*80}\n")
        print(f"Total PDFs to search: {len(cause_list_items)}")
        
        for idx, item in enumerate(cause_list_items, 1):
            if not item['pdf_link']:
                print(f"[SKIP] Item {idx}: No PDF link available")
                if progress_callback:
                    progress_callback(idx, len(cause_list_items), f"Skipped: No PDF link")
                continue
            
            print(f"\n{'─'*80}")
            print(f"Processing PDF {idx}/{len(cause_list_items)}")
            print(f"Bench: {item['bench'][:60]}...")
            print(f"Type: {item['type']}")
            print(f"{'─'*80}")
            
            if progress_callback:
                progress_callback(idx, len(cause_list_items), f"Processing: {item['bench'][:40]}...")
            
            results['total_pdfs_scanned'] += 1
            
            # Download PDF to memory
            pdf_bytes = self.download_pdf_to_memory(item['pdf_link'])
            if not pdf_bytes:
                print(f"[SKIP] Failed to download PDF")
                if progress_callback:
                    progress_callback(idx, len(cause_list_items), f"Failed to download PDF")
                continue
            
            # Extract text from PDF
            text = self.extract_text_from_pdf_bytes(pdf_bytes)
            if not text:
                print(f"[SKIP] Failed to extract text from PDF")
                if progress_callback:
                    progress_callback(idx, len(cause_list_items), f"Failed to extract text")
                continue
            
            # Search for term in text
            matches = self.search_case_in_text(search_term, text, is_party_name)
            
            if matches:
                results['pdfs_with_matches'] += 1
                results['total_matches'] += len(matches)
                
                # Generate unique PDF ID
                hash_obj = hashlib.md5(item['pdf_link'].encode())
                pdf_id = f"{hash_obj.hexdigest()[:12]}_{int(datetime.now().timestamp())}"
                filename = f"causelist_{item['sr_no']}_{pdf_id}.pdf"
                
                # Store PDF in memory cache
                pdf_cache[pdf_id] = {
                    'content': pdf_bytes,
                    'filename': filename,
                    'timestamp': datetime.now().timestamp()
                }
                
                print(f"[FOUND] Match found! Stored in cache with ID: {pdf_id}")
                if progress_callback:
                    progress_callback(idx, len(cause_list_items), f"✓ Match found in: {item['bench'][:30]}...")
                
                # Add to results
                results['matching_pdfs'].append({
                    'sr_no': item['sr_no'],
                    'bench': item['bench'],
                    'type': item['type'],
                    'pdf_id': pdf_id,
                    'pdf_url': f"/api/download-pdf/{pdf_id}",
                    'match_count': len(matches),
                    'matches': matches
                })
            else:
                print(f"[SKIP] No match in this PDF")
            
            time.sleep(0.3)  # Small delay to avoid overwhelming server
        
        print(f"\n{'='*80}")
        print(f"SEARCH SUMMARY")
        print(f"{'='*80}")
        print(f"Total PDFs scanned: {results['total_pdfs_scanned']}")
        print(f"PDFs with matches: {results['pdfs_with_matches']}")
        print(f"Total matches found: {results['total_matches']}")
        
        return results
