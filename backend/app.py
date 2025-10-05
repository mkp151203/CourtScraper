from flask import Flask, request, jsonify, send_file, render_template, Response
from flask_cors import CORS
import os
import json
from datetime import datetime
import sqlite3
from high_court_scraper import HCServicesCompleteScraper
from district_court_scraper import DistrictCourtsScraper
from causelist_scraper import HCCauseListScraper
from district_causelist_scraper import DistrictCauseListScraper
import uuid
import glob
import time
from io import BytesIO

app = Flask(__name__, static_folder='../frontend', template_folder='../frontend')
CORS(app)

# Store active scraper sessions (session_id -> scraper instance)
# This is critical: captcha must be verified in the same session it was fetched
active_sessions = {}

# In-memory PDF storage for Render deployment
# Structure: {pdf_id: {'content': bytes, 'filename': str, 'timestamp': float}}
pdf_cache = {}

# Track current active search session and its PDFs
current_search_session = {
    'session_id': None,
    'pdf_ids': [],
    'timestamp': None
}

# Progress tracking for long-running operations
# Structure: {session_id: {'current': int, 'total': int, 'message': str, 'status': str}}
progress_tracker = {}

def cleanup_downloads(exclude_files=None):
    """Delete PDF files in the downloads/orders directory (for local development)"""
    try:
        downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads', 'orders')
        if os.path.exists(downloads_dir):
            pdf_files = glob.glob(os.path.join(downloads_dir, '*.pdf'))
            exclude_set = set(exclude_files) if exclude_files else set()
            
            for pdf_file in pdf_files:
                if pdf_file not in exclude_set:
                    try:
                        os.remove(pdf_file)
                        print(f"Deleted: {os.path.basename(pdf_file)}")
                    except Exception as e:
                        print(f"Failed to delete {pdf_file}: {e}")
    except Exception as e:
        print(f"Error during cleanup: {e}")

def cleanup_old_session():
    """Clean up PDFs from the previous search session"""
    global current_search_session, pdf_cache
    
    if current_search_session['pdf_ids']:
        print(f"Cleaning up old session PDFs: {len(current_search_session['pdf_ids'])} PDFs")
        
        for pdf_id in current_search_session['pdf_ids']:
            if pdf_id in pdf_cache:
                del pdf_cache[pdf_id]
                print(f"Deleted PDF from cache: {pdf_id}")
        
        # Also clean disk files if they exist (for local development)
        downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads', 'orders')
        if os.path.exists(downloads_dir):
            for pdf_id in current_search_session['pdf_ids']:
                # Try to find and delete file with this ID in name
                for pdf_file in glob.glob(os.path.join(downloads_dir, f"*{pdf_id}*.pdf")):
                    try:
                        os.remove(pdf_file)
                        print(f"Deleted disk file: {os.path.basename(pdf_file)}")
                    except Exception:
                        pass
    
    # Reset session
    current_search_session = {
        'session_id': None,
        'pdf_ids': [],
        'timestamp': None
    }

def register_search_session(case_data):
    """Register a new search session and track its PDFs"""
    global current_search_session
    
    # Clean up old session first
    cleanup_old_session()
    
    # Create new session
    session_id = str(uuid.uuid4())
    pdf_ids = []
    
    # Extract PDF IDs from case_data
    if 'orders' in case_data:
        for order in case_data.get('orders', []):
            if 'pdf_id' in order:
                pdf_ids.append(order['pdf_id'])
    
    current_search_session = {
        'session_id': session_id,
        'pdf_ids': pdf_ids,
        'timestamp': time.time()
    }
    
    print(f"New search session registered: {session_id} with {len(pdf_ids)} PDFs")
    return session_id

# Clean up downloads on server startup
cleanup_downloads()

# Database setup
DATABASE = os.path.join(os.path.dirname(__file__), '..', 'database', 'court_cases.db')

def init_db():
    """Initialize the database"""
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            court_type TEXT NOT NULL,
            query_params TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS case_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER,
            case_data TEXT NOT NULL,
            raw_response TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (query_id) REFERENCES queries(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_query(court_type, query_params):
    """Save a query to database"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO queries (court_type, query_params) VALUES (?, ?)',
        (court_type, json.dumps(query_params))
    )
    query_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return query_id

def save_case_result(query_id, case_data, raw_response):
    """Save case result to database"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO case_results (query_id, case_data, raw_response) VALUES (?, ?, ?)',
        (query_id, json.dumps(case_data), json.dumps(raw_response))
    )
    conn.commit()
    conn.close()

# Initialize database
init_db()

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/high-court/courts', methods=['GET'])
def get_high_courts():
    """Get list of all High Courts"""
    try:
        scraper = HCServicesCompleteScraper()
        scraper.initialize_session()
        courts = scraper.fetch_available_courts()
        return jsonify({
            'success': True,
            'courts': courts
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/high-court/case-types', methods=['POST'])
def get_high_court_case_types():
    """Get case types for selected High Court"""
    try:
        data = request.json
        court_code = data.get('court_code')
        state_code = data.get('state_code')
        
        scraper = HCServicesCompleteScraper()
        scraper.court_code = court_code
        scraper.state_code = state_code
        scraper.initialize_session()
        scraper.fetch_court_complexes()
        
        case_types = scraper.get_case_types()
        
        return jsonify({
            'success': True,
            'case_types': case_types
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/high-court/search', methods=['POST'])
def search_high_court():
    """Search for a High Court case"""
    try:
        data = request.json
        
        # Save query to database
        query_params = {
            'court_code': data.get('court_code'),
            'state_code': data.get('state_code'),
            'court_name': data.get('court_name'),
            'case_type': data.get('case_type'),
            'case_number': data.get('case_number'),
            'year': data.get('year')
        }
        query_id = save_query('high_court', query_params)
        
        # Initialize scraper and store session
        scraper = HCServicesCompleteScraper()
        scraper.court_code = data.get('court_code')
        scraper.state_code = data.get('state_code')
        scraper.current_court_name = data.get('court_name')
        
        if not scraper.initialize_session():
            return jsonify({
                'success': False,
                'error': 'Failed to initialize session'
            }), 500
        
        scraper.fetch_court_complexes()
        
        # Get captcha (this sets up the session)
        captcha_result = scraper.get_captcha()
        if not captcha_result:
            return jsonify({
                'success': False,
                'error': 'Failed to get captcha'
            }), 500
        
        # Generate session ID and store scraper
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = scraper
        
        captcha_url = captcha_result.get('captcha_url')
        
        return jsonify({
            'success': True,
            'query_id': query_id,
            'session_id': session_id,
            'captcha_url': captcha_url,
            'message': 'Please solve the captcha'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/high-court/verify-captcha', methods=['POST'])
def verify_high_court_captcha():
    """Verify captcha and get case details"""
    try:
        data = request.json
        captcha = data.get('captcha')
        session_id = data.get('session_id')
        
        # Retrieve the stored scraper session
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session. Please try searching again.'
            }), 400
        
        scraper = active_sessions[session_id]
        
        # Search case using the SAME session that fetched the captcha
        search_result = scraper.search_case(
            case_type=data.get('case_type'),
            case_no=data.get('case_number'),
            year=data.get('year'),
            captcha=captcha
        )
        
        # Clean up session after use
        del active_sessions[session_id]
        
        if not search_result:
            return jsonify({
                'success': False,
                'error': 'Case not found or invalid captcha'
            }), 400
        
        # Get detailed case history
        case_history_html = scraper.get_case_history(search_result)
        if case_history_html:
            case_data = scraper.parse_case_history(case_history_html)
            
            # Download all order PDFs (pass global pdf_cache for in-memory storage)
            if case_data.get('orders'):
                print(f"Downloading {len(case_data['orders'])} order PDFs...")
                case_data = scraper.download_all_orders(case_data, pdf_cache)
                
            # Register this search session and cleanup old files
            search_session_id = register_search_session(case_data)
        else:
            case_data = {'raw_search_result': search_result}
            search_session_id = None
        
        # Save to database
        query_id = data.get('query_id')
        if query_id:
            save_case_result(query_id, case_data, search_result)
        
        return jsonify({
            'success': True,
            'case_data': case_data,
            'search_session_id': search_session_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-court/states', methods=['GET'])
def get_states():
    """Get list of all states"""
    try:
        scraper = DistrictCourtsScraper()
        return jsonify({
            'success': True,
            'states': scraper.states
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-court/districts', methods=['POST'])
def get_districts():
    """Get districts for selected state"""
    try:
        data = request.json
        state_code = data.get('state_code')
        state_name = data.get('state_name')
        
        print(f"DEBUG: Fetching districts for state_code={state_code}, state_name={state_name}")
        
        scraper = DistrictCourtsScraper()
        scraper.current_state = state_name
        scraper.current_state_code = state_code
        
        if not scraper.initialize_session():
            print("DEBUG: Failed to initialize session")
            return jsonify({
                'success': False,
                'error': 'Failed to initialize session'
            }), 500
        
        print("DEBUG: Session initialized, fetching districts...")
        districts = scraper.fetch_districts(state_code)
        print(f"DEBUG: Got {len(districts)} districts")
        
        if districts:
            return jsonify({
                'success': True,
                'districts': districts
            })
        else:
            print("DEBUG: No districts returned")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch districts'
            }), 500
            
    except Exception as e:
        print(f"DEBUG: Exception in get_districts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-court/court-complexes', methods=['POST'])
def get_court_complexes():
    """Get court complexes for selected district"""
    try:
        data = request.json
        
        scraper = DistrictCourtsScraper()
        scraper.current_state = data.get('state_name')
        scraper.current_state_code = data.get('state_code')
        scraper.current_district = data.get('district_name')
        scraper.current_district_code = data.get('district_code')
        
        if not scraper.initialize_session():
            return jsonify({
                'success': False,
                'error': 'Failed to initialize session'
            }), 500
        
        court_complexes = scraper.fetch_court_complexes(
            data.get('state_code'),
            data.get('district_code')
        )
        if court_complexes:
            return jsonify({
                'success': True,
                'court_complexes': court_complexes
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch court complexes. Please try again.'
            }), 500
            
    except Exception as e:
        print(f"Error in get_court_complexes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-court/case-types', methods=['POST'])
def get_district_case_types():
    """Get case types for selected court complex"""
    try:
        data = request.json
        
        scraper = DistrictCourtsScraper()
        scraper.current_state = data.get('state_name')
        scraper.current_state_code = data.get('state_code')
        scraper.current_district = data.get('district_name')
        scraper.current_district_code = data.get('district_code')
        scraper.current_court_complex = data.get('court_complex_name')
        scraper.current_court_complex_code = data.get('court_complex_code')
        
        if not scraper.initialize_session():
            return jsonify({
                'success': False,
                'error': 'Failed to initialize session'
            }), 500
        
        case_types = scraper.fetch_case_types(
            data.get('state_code'),
            data.get('district_code'),
            data.get('court_complex_code')
        )
        if case_types:
            return jsonify({
                'success': True,
                'case_types': case_types
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch case types'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-court/search', methods=['POST'])
def search_district_court():
    """Search for a District Court case"""
    try:
        data = request.json
        
        # Save query to database
        query_params = {
            'state_name': data.get('state_name'),
            'state_code': data.get('state_code'),
            'district_name': data.get('district_name'),
            'district_code': data.get('district_code'),
            'court_complex_name': data.get('court_complex_name'),
            'court_complex_code': data.get('court_complex_code'),
            'case_type': data.get('case_type'),
            'case_number': data.get('case_number'),
            'year': data.get('year')
        }
        query_id = save_query('district_court', query_params)
        
        # Initialize scraper and store session
        scraper = DistrictCourtsScraper()
        scraper.current_state = data.get('state_name')
        scraper.current_state_code = data.get('state_code')
        scraper.current_district = data.get('district_name')
        scraper.current_district_code = data.get('district_code')
        scraper.current_court_complex = data.get('court_complex_name')
        scraper.current_court_complex_code = data.get('court_complex_code')
        
        if not scraper.initialize_session():
            return jsonify({
                'success': False,
                'error': 'Failed to initialize session'
            }), 500
        
        # Get captcha (this sets up the session)
        captcha_result = scraper.get_captcha()
        if not captcha_result:
            return jsonify({
                'success': False,
                'error': 'Failed to get captcha'
            }), 500
        
        # Generate session ID and store scraper
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = scraper
        
        captcha_url = captcha_result.get('captcha_url')
        
        return jsonify({
            'success': True,
            'query_id': query_id,
            'session_id': session_id,
            'captcha_url': captcha_url,
            'message': 'Please solve the captcha'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-court/verify-captcha', methods=['POST'])
def verify_district_captcha():
    """Verify captcha and get case details"""
    try:
        data = request.json
        captcha = data.get('captcha')
        session_id = data.get('session_id')
        
        # Retrieve the stored scraper session
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session. Please try searching again.'
            }), 400
        
        scraper = active_sessions[session_id]
        
        # Search case using the SAME session that fetched the captcha
        case_data = scraper.search_case(
            case_type_code=data.get('case_type'),
            case_no=data.get('case_number'),
            case_year=data.get('year'),
            captcha=captcha
        )
        
        # Clean up session after use
        del active_sessions[session_id]
        
        if not case_data:
            return jsonify({
                'success': False,
                'error': 'Case not found or invalid captcha'
            }), 400
        
        # Download all order PDFs (pass global pdf_cache for in-memory storage)
        case_data = scraper.download_all_orders(case_data, pdf_cache)
        
        # Register this search session and cleanup old files
        search_session_id = register_search_session(case_data)
        
        # Save to database
        query_id = data.get('query_id')
        if query_id:
            save_case_result(query_id, case_data, case_data.get('raw_response', {}))
        
        return jsonify({
            'success': True,
            'case_data': case_data,
            'search_session_id': search_session_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/download-pdf/<pdf_id>', methods=['GET'])
def download_pdf(pdf_id):
    """Serve PDF files from memory cache (works on Render) or disk (local development)"""
    try:
        # First, try to serve from memory cache (for Render deployment)
        if pdf_id in pdf_cache:
            pdf_data = pdf_cache[pdf_id]
            print(f"✓ Serving PDF from MEMORY CACHE: {pdf_id} ({len(pdf_data['content'])} bytes)")
            return Response(
                pdf_data['content'],
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'inline; filename="{pdf_data["filename"]}"',
                    'X-PDF-Source': 'memory-cache'  # Custom header to identify source
                }
            )
        
        # Fallback to disk for local development
        backend_downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads', 'orders')
        
        # Try to find file with this pdf_id in the name
        pdf_files = glob.glob(os.path.join(backend_downloads_dir, f"*{pdf_id}*.pdf"))
        if pdf_files:
            print(f"✓ Serving PDF from DISK: {pdf_files[0]}")
            return send_file(pdf_files[0], mimetype='application/pdf', 
                           extra_headers={'X-PDF-Source': 'disk'})
        
        # If not found anywhere
        print(f"✗ PDF not found: {pdf_id}")
        print(f"   - Memory cache keys: {list(pdf_cache.keys())[:5]}...")
        print(f"   - Disk files: {os.listdir(backend_downloads_dir) if os.path.exists(backend_downloads_dir) else 'directory not found'}")
        return jsonify({
            'success': False,
            'error': 'PDF file not found. It may have been cleaned up.'
        }), 404

    except Exception as e:
        print(f"✗ Error serving PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/proxy-pdf', methods=['POST'])
def proxy_pdf():
    """Proxy endpoint to fetch PDF from eCourts and serve it
    This allows viewing PDFs without storing them in memory
    
    IMPORTANT: eCourts PDF links may be session-dependent.
    We try to reuse the original search session if available, 
    otherwise create a new session.
    """
    try:
        data = request.json
        pdf_url = data.get('pdf_url')
        session_id = data.get('session_id')  # Optional: session from original search
        
        if not pdf_url:
            return jsonify({
                'success': False,
                'error': 'PDF URL is required'
            }), 400
        
        print(f"[INFO] Proxying PDF from: {pdf_url}")
        print(f"[DEBUG] Received session_id: {session_id}")
        print(f"[DEBUG] Active sessions: {list(active_sessions.keys())}")
        
        # Try to reuse existing session if provided
        scraper = None
        if session_id and session_id in active_sessions:
            scraper = active_sessions[session_id]
            print(f"[INFO] ✓ Reusing existing session: {session_id}")
        else:
            # No valid session - create new scraper WITHOUT initializing
            # The scraper should already have a session from when it was created
            scraper = HCCauseListScraper()
            print(f"[WARNING] ✗ No valid session found, created new scraper (may not work for session-dependent PDFs)")
            print(f"[WARNING] This PDF likely requires the original session and may return 'Order not uploaded'")
        
        # Download the PDF
        pdf_bytes = scraper.download_pdf_to_memory(pdf_url)
        
        if not pdf_bytes or len(pdf_bytes) < 1000:
            # Less than 1KB is likely an error page, not a PDF
            error_msg = pdf_bytes.decode('utf-8', errors='ignore') if pdf_bytes else 'No data'
            print(f"[ERROR] Downloaded data too small ({len(pdf_bytes) if pdf_bytes else 0} bytes) - likely not a PDF")
            if pdf_bytes:
                print(f"[DEBUG] Content preview: {pdf_bytes[:200]}")
            
            # Check for specific error messages
            if 'not uploaded' in error_msg.lower():
                return jsonify({
                    'success': False,
                    'error': 'This PDF has not been uploaded to eCourts yet. Please try again later or contact the court.'
                }), 404
            elif not session_id or session_id not in active_sessions:
                return jsonify({
                    'success': False,
                    'error': 'Session expired. Please search again to view PDFs.'
                }), 401
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to download PDF from eCourts. The file may not be available.'
                }), 500
        
        print(f"[SUCCESS] Downloaded valid PDF ({len(pdf_bytes)} bytes)")
        
        # Remove BOM if present (some eCourts servers add UTF-8 BOM to PDF files)
        if pdf_bytes.startswith(b'\xef\xbb\xbf'):
            print(f"[INFO] Removing UTF-8 BOM from PDF")
            pdf_bytes = pdf_bytes[3:]  # Skip the 3-byte BOM
        
        # Verify it's actually a PDF
        if not pdf_bytes.startswith(b'%PDF'):
            print(f"[ERROR] Downloaded content is not a PDF. First 100 bytes: {pdf_bytes[:100]}")
            return jsonify({
                'success': False,
                'error': 'Downloaded content is not a valid PDF file. The link may have expired or requires authentication.'
            }), 500
        
        # Return the PDF
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'inline; filename="causelist.pdf"',
                'X-PDF-Source': 'proxy',
                'Content-Length': str(len(pdf_bytes))
            }
        )
        
    except Exception as e:
        print(f"[ERROR] Proxy PDF failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get search history"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT q.id, q.court_type, q.query_params, q.timestamp,
                   cr.case_data
            FROM queries q
            LEFT JOIN case_results cr ON q.id = cr.query_id
            ORDER BY q.timestamp DESC
            LIMIT 50
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                'id': row[0],
                'court_type': row[1],
                'query_params': json.loads(row[2]),
                'timestamp': row[3],
                'case_data': json.loads(row[4]) if row[4] else None
            })
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/debug/cache-status', methods=['GET'])
def cache_status():
    """Debug endpoint to check PDF cache status"""
    try:
        backend_downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads', 'orders')
        disk_files = []
        if os.path.exists(backend_downloads_dir):
            disk_files = os.listdir(backend_downloads_dir)
        
        return jsonify({
            'success': True,
            'cache_info': {
                'memory_cache': {
                    'count': len(pdf_cache),
                    'pdf_ids': list(pdf_cache.keys()),
                    'total_size_bytes': sum(len(pdf['content']) for pdf in pdf_cache.values())
                },
                'disk_storage': {
                    'count': len(disk_files),
                    'files': disk_files
                },
                'current_session': current_search_session
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== CAUSELIST ENDPOINTS ====================

@app.route('/api/causelist/courts', methods=['GET'])
def get_causelist_courts():
    """Get list of all High Courts for cause list"""
    try:
        scraper = HCCauseListScraper()
        courts = scraper.get_all_high_courts()
        return jsonify({
            'success': True,
            'courts': courts
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/causelist/benches', methods=['POST'])
def get_causelist_benches():
    """Get benches for selected High Court"""
    try:
        data = request.json
        state_code = data.get('state_code')
        
        scraper = HCCauseListScraper()
        benches = scraper.fetch_benches(state_code)
        
        return jsonify({
            'success': True,
            'benches': benches
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/causelist/search', methods=['POST'])
def search_causelist():
    """Initialize cause list search and get captcha"""
    try:
        data = request.json
        
        # Save query to database
        query_params = {
            'state_code': data.get('state_code'),
            'court_code': data.get('court_code'),
            'court_name': data.get('court_name'),
            'bench_name': data.get('bench_name'),
            'date': data.get('date'),
            'search_term': data.get('search_term'),
            'is_party_name': data.get('is_party_name', False)
        }
        query_id = save_query('causelist', query_params)
        
        # Initialize scraper and store session
        scraper = HCCauseListScraper()
        scraper.current_state_code = data.get('state_code')
        scraper.current_court_code = data.get('court_code')
        
        # Get captcha (this sets up the session)
        captcha_result = scraper.get_captcha()
        if not captcha_result:
            return jsonify({
                'success': False,
                'error': 'Failed to get captcha'
            }), 500
        
        # Generate session ID and store scraper
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = scraper
        
        captcha_url = captcha_result.get('captcha_url')
        
        return jsonify({
            'success': True,
            'query_id': query_id,
            'session_id': session_id,
            'captcha_url': captcha_url,
            'message': 'Please solve the captcha'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/causelist/verify-captcha', methods=['POST'])
def verify_causelist_captcha():
    """Verify captcha and process cause list PDFs"""
    try:
        data = request.json
        captcha = data.get('captcha')
        session_id = data.get('session_id')
        
        # Retrieve the stored scraper session
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session. Please try searching again.'
            }), 400
        
        scraper = active_sessions[session_id]
        
        # Fetch cause list
        cause_list_items = scraper.fetch_cause_list(
            state_code=data.get('state_code'),
            court_code=data.get('court_code'),
            date=data.get('date'),
            captcha=captcha
        )
        
        # DON'T delete session yet - we need it for downloading PDFs later
        # Store the session_id in results so frontend can use it for PDF downloads
        # Session will be cleaned up after timeout or manual cleanup
        
        if cause_list_items is None:
            return jsonify({
                'success': False,
                'error': 'Invalid captcha or failed to fetch cause list'
            }), 400
        
        if not cause_list_items:
            return jsonify({
                'success': True,
                'results': {
                    'search_term': data.get('search_term'),
                    'search_type': 'party_name' if data.get('is_party_name') else 'case_number',
                    'total_pdfs_scanned': 0,
                    'pdfs_with_matches': 0,
                    'total_matches': 0,
                    'matching_pdfs': [],
                    'message': 'No cause lists found for the selected date'
                }
            })
        
        # Process PDFs and search for term
        search_term = data.get('search_term')
        is_party_name = data.get('is_party_name', False)
        
        print(f"Processing {len(cause_list_items)} PDFs, searching for: {search_term}")
        
        results = scraper.process_cause_list_pdfs(
            cause_list_items=cause_list_items,
            search_term=search_term,
            is_party_name=is_party_name,
            pdf_cache=pdf_cache
        )
        
        # Register this search session and cleanup old files
        if results['matching_pdfs']:
            # Create a case_data-like structure for session registration
            case_data_for_session = {
                'orders': [{'pdf_id': pdf['pdf_id']} for pdf in results['matching_pdfs']]
            }
            search_session_id = register_search_session(case_data_for_session)
            results['search_session_id'] = search_session_id
        
        # Save to database
        query_id = data.get('query_id')
        if query_id:
            save_case_result(query_id, results, {'cause_list_items': len(cause_list_items)})
        
        # Include session_id in results for PDF downloads
        results['session_id'] = session_id
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        print(f"Error in verify_causelist_captcha: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== END CAUSELIST ENDPOINTS ====================

# ==================== DISTRICT CAUSELIST ENDPOINTS ====================

# Store active district causelist sessions
district_causelist_sessions = {}

@app.route('/api/district-causelist/states', methods=['GET'])
def get_district_causelist_states():
    """Get list of all states for district cause list"""
    try:
        scraper = DistrictCauseListScraper()
        states = scraper.get_states()
        return jsonify({
            'success': True,
            'states': states
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-causelist/init-session', methods=['POST'])
def init_district_causelist_session():
    """Initialize a new session for district causelist dropdowns"""
    try:
        import uuid
        session_id = str(uuid.uuid4())
        
        scraper = DistrictCauseListScraper()
        if not scraper.initialize_session():
            return jsonify({
                'success': False,
                'error': 'Failed to initialize session'
            }), 500
        
        # Store scraper instance
        district_causelist_sessions[session_id] = scraper
        
        return jsonify({
            'success': True,
            'session_id': session_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-causelist/districts', methods=['POST'])
def get_district_causelist_districts():
    """Get districts for selected state"""
    try:
        data = request.json
        state_code = data.get('state_code')
        session_id = data.get('session_id')
        
        # Get or create scraper
        if session_id and session_id in district_causelist_sessions:
            scraper = district_causelist_sessions[session_id]
        else:
            scraper = DistrictCauseListScraper()
            if not scraper.initialize_session():
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize session'
                }), 500
        
        districts = scraper.fetch_districts(state_code)
        
        return jsonify({
            'success': True,
            'districts': districts
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-causelist/court-complexes', methods=['POST'])
def get_district_causelist_complexes():
    """Get court complexes for selected district"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        # Get or create scraper
        if session_id and session_id in district_causelist_sessions:
            scraper = district_causelist_sessions[session_id]
        else:
            scraper = DistrictCauseListScraper()
            scraper.initialize_session()
        
        complexes = scraper.fetch_court_complexes(
            state_code=data.get('state_code'),
            district_code=data.get('district_code')
        )
        
        return jsonify({
            'success': True,
            'court_complexes': complexes
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-causelist/establishments', methods=['POST'])
def get_district_causelist_establishments():
    """Get establishments for selected court complex"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        # Get or create scraper
        if session_id and session_id in district_causelist_sessions:
            scraper = district_causelist_sessions[session_id]
        else:
            scraper = DistrictCauseListScraper()
            scraper.initialize_session()
        
        establishments = scraper.fetch_establishments(
            state_code=data.get('state_code'),
            district_code=data.get('district_code'),
            court_complex_code=data.get('court_complex_code')
        )
        
        return jsonify({
            'success': True,
            'establishments': establishments
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-causelist/judges', methods=['POST'])
def get_district_causelist_judges():
    """Get judges/courts for selected establishment"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        print(f"[DEBUG] Judges request - session_id: {session_id}")
        print(f"[DEBUG] Available sessions: {list(district_causelist_sessions.keys())}")
        
        # Get or create scraper
        if session_id and session_id in district_causelist_sessions:
            scraper = district_causelist_sessions[session_id]
            print(f"[DEBUG] Reusing existing session: {session_id}")
        else:
            scraper = DistrictCauseListScraper()
            scraper.initialize_session()
            print(f"[DEBUG] Created new scraper (session not found)")
        
        judges = scraper.fetch_judges(
            state_code=data.get('state_code'),
            district_code=data.get('district_code'),
            court_complex_code=data.get('court_complex_code'),
            est_code=data.get('est_code')
        )
        
        return jsonify({
            'success': True,
            'judges': judges
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-causelist/search', methods=['POST'])
def search_district_causelist():
    """Initialize district cause list search and get captcha"""
    try:
        data = request.json
        dropdown_session_id = data.get('dropdown_session_id')  # Session from dropdown selections
        
        # Save query to database
        query_params = {
            'state_code': data.get('state_code'),
            'state_name': data.get('state_name'),
            'district_code': data.get('district_code'),
            'district_name': data.get('district_name'),
            'court_complex_code': data.get('court_complex_code'),
            'court_complex_name': data.get('court_complex_name'),
            'est_code': data.get('est_code'),
            'est_name': data.get('est_name'),
            'court_no': data.get('court_no'),
            'court_name': data.get('court_name'),
            'date': data.get('date'),
            'search_term': data.get('search_term'),
            'is_party_name': data.get('is_party_name', False),
            'case_type': data.get('case_type', 'civ')
        }
        query_id = save_query('district_causelist', query_params)
        
        # Try to reuse the dropdown session scraper if available
        if dropdown_session_id and dropdown_session_id in district_causelist_sessions:
            scraper = district_causelist_sessions[dropdown_session_id]
            print(f"[INFO] Reusing dropdown session: {dropdown_session_id}")
        else:
            # Create new scraper if no dropdown session
            scraper = DistrictCauseListScraper()
            scraper.initialize_session()
            print("[INFO] Created new scraper session for search")
        
        # Get captcha
        captcha_result = scraper.get_captcha()
        if not captcha_result:
            return jsonify({
                'success': False,
                'error': 'Failed to get captcha'
            }), 500
        
        # Generate new session ID for captcha verification and store scraper
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = scraper
        
        captcha_url = captcha_result.get('captcha_url')
        
        return jsonify({
            'success': True,
            'query_id': query_id,
            'session_id': session_id,
            'captcha_url': captcha_url,
            'message': 'Please solve the captcha'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/district-causelist/verify-captcha', methods=['POST'])
def verify_district_causelist_captcha():
    """Verify captcha and process district cause list"""
    try:
        data = request.json
        captcha = data.get('captcha')
        session_id = data.get('session_id')
        
        print(f"[DEBUG] Verify captcha - session_id: {session_id}")
        print(f"[DEBUG] Verify captcha - captcha: {captcha}")
        print(f"[DEBUG] Active sessions: {list(active_sessions.keys())}")
        
        # Retrieve the stored scraper session
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session. Please try searching again.'
            }), 400
        
        scraper = active_sessions[session_id]
        print(f"[DEBUG] Found scraper, app_token: {scraper.app_token[:20] if scraper.app_token else 'None'}...")
        
        print(f"[DEBUG] Request data from frontend:")
        print(f"[DEBUG]   court_no: {data.get('court_no')}")
        print(f"[DEBUG]   court_name: {data.get('court_name')}")
        print(f"[DEBUG]   est_code: {data.get('est_code')}")
        print(f"[DEBUG]   case_type: {data.get('case_type')}")
        
        # Process cause list search
        results = scraper.process_cause_list_search(
            state_code=data.get('state_code'),
            district_code=data.get('district_code'),
            court_complex_code=data.get('court_complex_code'),
            est_code=data.get('est_code'),
            court_no=data.get('court_no'),
            court_name=data.get('court_name'),
            date=data.get('date'),
            captcha=captcha,
            search_term=data.get('search_term'),
            is_party_name=data.get('is_party_name', False),
            case_type=data.get('case_type', 'civ')
        )
        
        # Clean up session after use
        del active_sessions[session_id]
        
        if results.get('status') == 'error':
            return jsonify({
                'success': False,
                'error': results.get('message', 'Failed to fetch cause list')
            }), 400
        
        # Save to database
        query_id = data.get('query_id')
        if query_id:
            save_case_result(query_id, results, {'raw_results': results})
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        print(f"Error in verify_district_causelist_captcha: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== END DISTRICT CAUSELIST ENDPOINTS ====================


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
