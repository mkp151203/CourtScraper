from flask import Flask, request, jsonify, send_file, render_template, Response
from flask_cors import CORS
import os
import json
from datetime import datetime
import sqlite3
from high_court_scraper import HCServicesCompleteScraper
from district_court_scraper import DistrictCourtsScraper
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
            return Response(
                pdf_data['content'],
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'inline; filename="{pdf_data["filename"]}"'
                }
            )
        
        # Fallback to disk for local development
        backend_downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads', 'orders')
        
        # Try to find file with this pdf_id in the name
        pdf_files = glob.glob(os.path.join(backend_downloads_dir, f"*{pdf_id}*.pdf"))
        if pdf_files:
            return send_file(pdf_files[0], mimetype='application/pdf')
        
        # If not found anywhere
        return jsonify({
            'success': False,
            'error': 'PDF file not found. It may have been cleaned up.'
        }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    except Exception as e:
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

@app.route('/api/cleanup-downloads', methods=['POST'])
def cleanup_downloads_endpoint():
    """Clean up all downloaded PDF files"""
    try:
        cleanup_downloads()
        return jsonify({
            'success': True,
            'message': 'Downloads cleaned up successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
