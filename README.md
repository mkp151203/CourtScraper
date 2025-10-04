# 🏛️ Indian Court Case Scraper Web Application

A comprehensive web application for searching and retrieving case details from Indian High Courts and District Courts through official eCourts portals.

## Features

✅ **Multi-Court Support**
- All Indian High Courts (25+ courts)
- All District & Taluka Courts across India

✅ **Complete Case Information**
- Case details (Filing date, registration number, CNR)
- Party information (Petitioners & Respondents)
- Case status and next hearing dates
- Order/Judgment details
- Complete hearing history

✅ **Database Storage**
- Automatic storage of all queries and results in SQLite database
- Query history tracking
- Raw response preservation for future analysis

✅ **User-Friendly Interface**
- Clean, modern, responsive design
- Dynamic dropdowns for easy navigation
- Real-time captcha solving
- Detailed result display

## Project Structure

```
webapp/
├── backend/
│   ├── app.py                      # Flask application with API routes
│   ├── high_court_scraper.py       # High Court scraper module
│   └── district_court_scraper.py   # District Court scraper module
├── frontend/
│   └── index.html                  # Single-page web interface
├── database/
│   └── court_cases.db             # SQLite database (auto-created)
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup Steps

1. **Navigate to the webapp directory**
   ```powershell
   cd d:\PAPERS\application\assign\webapp
   ```

2. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

## Running the Application

1. **Start the Flask server**
   ```powershell
   cd backend
   python app.py
   ```

   The server will start on `http://localhost:5000`

2. **Access the web interface**
   Open your browser and go to:
   ```
   http://localhost:5000
   ```

## Usage Guide

### Searching High Court Cases

1. Select **High Court** tab
2. Choose a High Court from the dropdown
3. Select the Case Type (e.g., W.P.(C), Civil Appeal)
4. Enter Case Number (e.g., 16516)
5. Enter Year (e.g., 2022)
6. Click **Search Case**
7. Solve the captcha when prompted
8. View detailed case information

### Searching District Court Cases

1. Select **District Court** tab
2. Choose State from dropdown
3. Select District
4. Choose Court Complex
5. Select Case Type
6. Enter Case Number (e.g., 100591)
7. Enter Year (e.g., 2016)
8. Click **Search Case**
9. Solve the captcha when prompted
10. View detailed case information

## API Endpoints

### High Court Endpoints

- `GET /api/high-court/courts` - Get all High Courts
- `POST /api/high-court/case-types` - Get case types for selected court
- `POST /api/high-court/search` - Initiate case search (returns captcha)
- `POST /api/high-court/verify-captcha` - Verify captcha and get case details

### District Court Endpoints

- `GET /api/district-court/states` - Get all states
- `POST /api/district-court/districts` - Get districts for state
- `POST /api/district-court/court-complexes` - Get court complexes for district
- `POST /api/district-court/case-types` - Get case types for court complex
- `POST /api/district-court/search` - Initiate case search (returns captcha)
- `POST /api/district-court/verify-captcha` - Verify captcha and get case details

### Utility Endpoints

- `GET /api/history` - Get search history (last 50 queries)

## Database Schema

### queries table
- `id` - Primary key
- `court_type` - 'high_court' or 'district_court'
- `query_params` - JSON of search parameters
- `timestamp` - Query timestamp

### case_results table
- `id` - Primary key
- `query_id` - Foreign key to queries table
- `case_data` - JSON of parsed case data
- `raw_response` - JSON of raw API response
- `timestamp` - Result timestamp

## Technical Details

### Backend (Flask)
- RESTful API architecture
- Session management for court portals
- Captcha handling with base64 encoding
- Database integration with SQLite
- CORS enabled for development

### Frontend (HTML/CSS/JavaScript)
- Vanilla JavaScript (no frameworks)
- Responsive design
- Dynamic form generation
- Real-time API communication
- Clean, modern UI with gradient design

### Scrapers
- **High Court Scraper**: Interfaces with `https://hcservices.ecourts.gov.in`
- **District Court Scraper**: Interfaces with `https://services.ecourts.gov.in`
- Session management and cookie handling
- Captcha image extraction and display
- HTML parsing with BeautifulSoup4
- Comprehensive error handling

## Features Implemented

✅ Court selection dropdowns (dynamic)
✅ Case type dropdowns (auto-populated)
✅ Interactive captcha solving
✅ Real-time case search
✅ Detailed result display
✅ Database storage of queries and results
✅ Error handling and user feedback
✅ Responsive design for mobile/desktop
✅ Loading indicators
✅ Alert notifications

## Differences from CLI Scrapers

This web app differs from the original CLI scrapers in the following ways:

1. **No Batch Mode**: Only interactive single-case search (as requested)
2. **Simplified Interface**: Web-based UI instead of command-line prompts
3. **RESTful API**: Backend provides API endpoints for frontend consumption
4. **Database Integration**: Automatic storage of all searches
5. **Captcha Display**: Visual captcha display instead of file saving
6. **Session Management**: Backend handles all session/cookie management
7. **Streamlined Code**: Removed CLI-specific features and batch processing

## Troubleshooting

### Port Already in Use
If port 5000 is already in use, modify `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)  # Change port
```

### Database Errors
The database is automatically created. If you encounter issues:
```powershell
rm database/court_cases.db  # Delete and restart app
```

### Captcha Issues
If captcha doesn't load:
- Check internet connection
- Verify the court portal is accessible
- Try refreshing the page

### Module Import Errors
Ensure all dependencies are installed:
```powershell
pip install -r requirements.txt
```

## Future Enhancements (Not Implemented)

- PDF download functionality for judgments/orders
- Cause list scraping feature
- Advanced search filters
- Export results to PDF/Excel
- User authentication
- Search history management
- Batch import from CSV
- Automated notifications for case updates

## Credits

Built for Internshala assignment - Indian Court Case Scraper Project

## License

This project is for educational purposes only. Please respect the terms of service of the eCourts portals.

## Support

For issues or questions, refer to the source code comments or create an issue in the repository.
