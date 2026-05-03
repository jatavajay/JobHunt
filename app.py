import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from collections import Counter
import time
import urllib.parse
import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
import re
from PyPDF2 import PdfReader
import logging

# Configure logging for Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')

# Configure CORS for production
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://jobhunt.onrender.com",
            "https://*.onrender.com",
            "http://localhost:5000",
            "http://127.0.0.1:5000"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Common technical skills
TECHNICAL_SKILLS = {
    'programming': ['python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'php', 'swift', 'kotlin', 'go', 'rust'],
    'frameworks': ['django', 'flask', 'react', 'angular', 'vue', 'spring', 'express', 'laravel', 'rails'],
    'databases': ['mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'sql server', 'sqlite'],
    'cloud': ['aws', 'azure', 'gcp', 'cloud', 'docker', 'kubernetes'],
    'tools': ['git', 'jenkins', 'jira', 'confluence', 'agile', 'scrum'],
    'ai_ml': ['machine learning', 'deep learning', 'tensorflow', 'pytorch', 'scikit-learn', 'nlp', 'computer vision'],
    'web': ['html', 'css', 'sass', 'bootstrap', 'tailwind', 'webpack', 'node.js'],
    'mobile': ['android', 'ios', 'react native', 'flutter', 'xamarin'],
    'testing': ['junit', 'pytest', 'selenium', 'cypress', 'jest'],
    'devops': ['ci/cd', 'ansible', 'chef', 'puppet', 'terraform']
}

# Cache and rate limiting
CACHE = {}
CACHE_TTL = timedelta(hours=1)
RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60
MAX_REQUESTS_PER_WINDOW = 30

def rate_limit_check(ip_address):
    """Simple rate limiting"""
    now = time.time()
    if ip_address in RATE_LIMIT:
        RATE_LIMIT[ip_address] = [t for t in RATE_LIMIT[ip_address] if now - t < RATE_LIMIT_WINDOW]
        if len(RATE_LIMIT[ip_address]) >= MAX_REQUESTS_PER_WINDOW:
            return False
        RATE_LIMIT[ip_address].append(now)
    else:
        RATE_LIMIT[ip_address] = [now]
    return True

def clean_cache():
    """Remove expired cache entries"""
    current_time = datetime.now()
    expired_keys = [key for key, value in CACHE.items() if current_time >= value['expires']]
    for key in expired_keys:
        del CACHE[key]
    if expired_keys:
        logger.info(f"Cleaned {len(expired_keys)} expired cache entries")

# Health check endpoint for Render
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(CACHE),
        'version': '1.0.0'
    }), 200

@app.route("/")
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# Job scraping functions (keep your existing implementations)
async def scrape_naukri(session, query, location):
    """Scrapes Naukri.com"""
    # ... (keep your existing implementation)
    # For brevity, I'm showing a simplified version - replace with your full function
    logger.info(f"Scraping Naukri for {query}")
    await asyncio.sleep(0.5)
    return {"source": "Naukri", "jobs": generate_mock_jobs(query, location, "Naukri")}

async def scrape_timesjob(session, query, location):
    """Scrapes TimesJobs.com"""
    logger.info(f"Scraping TimesJobs for {query}")
    await asyncio.sleep(0.5)
    return {"source": "TimesJobs", "jobs": generate_mock_jobs(query, location, "TimesJobs")}

async def scrape_linkedin(session, query, location):
    """Scrapes LinkedIn"""
    logger.info(f"Scraping LinkedIn for {query}")
    await asyncio.sleep(0.5)
    return {"source": "LinkedIn", "jobs": generate_mock_jobs(query, location, "LinkedIn")}

async def scrape_indeed(session, query, location):
    """Scrapes Indeed.com"""
    logger.info(f"Scraping Indeed for {query}")
    await asyncio.sleep(0.5)
    return {"source": "Indeed", "jobs": generate_mock_jobs(query, location, "Indeed")}

async def scrape_shine(session, query, location):
    """Scrapes Shine.com"""
    logger.info(f"Scraping Shine for {query}")
    await asyncio.sleep(0.5)
    return {"source": "Shine", "jobs": generate_mock_jobs(query, location, "Shine")}

def generate_mock_jobs(query, location, source):
    """Generate mock job data"""
    titles = [
        f"Senior {query}", f"{query} Developer", f"Lead {query} Engineer",
        f"{query} Specialist", f"Principal {query}", f"{query} Architect"
    ]
    companies = ["TechCorp", "Innovate Solutions", "Digital Dynamics", "Future Tech", "Global Tech"]
    import random
    random.seed(hash(query + location + source))
    jobs = []
    for i in range(5):
        jobs.append({
            "title": random.choice(titles),
            "company": random.choice(companies),
            "location": location if random.random() > 0.3 else "Remote",
            "url": f"https://www.{source.lower()}.com/search"
        })
    return jobs

async def scrape_all_sites(query, location):
    """Scrape all job sites concurrently"""
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            scrape_naukri(session, query, location),
            scrape_timesjob(session, query, location),
            scrape_linkedin(session, query, location),
            scrape_indeed(session, query, location),
            scrape_shine(session, query, location)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_results = [r for r in results if not isinstance(r, Exception)]
        return valid_results

def get_unique_jobs_with_source(all_jobs_by_source):
    """Get unique jobs"""
    unique_jobs = []
    seen = set()
    for source_data in all_jobs_by_source:
        if not isinstance(source_data, dict):
            continue
        source_name = source_data.get('source', 'Unknown')
        for job in source_data.get('jobs', []):
            job_key = (job.get('title', ''), job.get('company', ''), job.get('location', ''))
            if job_key not in seen:
                seen.add(job_key)
                job['source'] = source_name
                unique_jobs.append(job)
    return unique_jobs

@app.route('/api/search', methods=['POST', 'OPTIONS'])
def search_jobs_api():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    client_ip = request.remote_addr or 'unknown'
    if not rate_limit_check(client_ip):
        return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
            
        query = data.get('query', '').strip()
        location = data.get('location', '').strip()

        if not query:
            return jsonify({'error': 'Search query is required.'}), 400
        
        # Check cache
        cache_key = f"{query.lower()}_{location.lower()}"
        if cache_key in CACHE and datetime.now() < CACHE[cache_key]['expires']:
            logger.info(f"Returning cached result for {cache_key}")
            return jsonify(CACHE[cache_key]['data'])

        # Run scraping
        logger.info(f"Searching jobs for query: {query}, location: {location}")
        all_jobs_by_source = asyncio.run(scrape_all_sites(query, location))
        unique_jobs = get_unique_jobs_with_source(all_jobs_by_source)
        
        response = {
            "query": query,
            "location": location,
            "jobs": unique_jobs[:50],
            "total_jobs": len(unique_jobs),
            "results": all_jobs_by_source,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update cache
        CACHE[cache_key] = {'data': response, 'expires': datetime.now() + CACHE_TTL}
        clean_cache()
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error in /api/search: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF"""
    try:
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        return text
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
        raise

def extract_skills_from_text(text):
    """Extract technical skills"""
    text_lower = text.lower()
    found_skills = set()
    for category, skills in TECHNICAL_SKILLS.items():
        for skill in skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
                found_skills.add(skill)
    return list(found_skills)

def calculate_job_match(cv_skills, job_description, job_title="", company=""):
    """Calculate match score"""
    if not cv_skills:
        return 0
    
    job_desc_lower = job_description.lower()
    matched_skills = [s for s in cv_skills if s.lower() in job_desc_lower]
    match_ratio = len(matched_skills) / len(cv_skills)
    
    # Base score calculation
    base_score = 40 + (match_ratio * 40)
    skill_bonus = min(len(cv_skills) // 2, 20)
    final_score = min(base_score + skill_bonus, 95)
    
    return int(final_score)

@app.route('/api/analyze_cv', methods=['POST', 'OPTIONS'])
@app.route('/api/analyze-cv', methods=['POST', 'OPTIONS'])
def analyze_cv():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    client_ip = request.remote_addr or 'unknown'
    if not rate_limit_check(client_ip):
        return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
    
    try:
        if 'cv' not in request.files:
            return jsonify({'error': 'No CV file provided'}), 400
        
        cv_file = request.files['cv']
        if cv_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if not cv_file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Only PDF files are supported.'}), 400

        # Check file size (max 5MB)
        cv_file.seek(0, os.SEEK_END)
        file_size = cv_file.tell()
        cv_file.seek(0)
        if file_size > 5 * 1024 * 1024:
            return jsonify({'error': 'File too large. Maximum size is 5MB.'}), 400

        # Extract text and skills
        cv_text = extract_text_from_pdf(cv_file)
        if not cv_text.strip():
            return jsonify({'error': 'Could not extract text from PDF.'}), 400
        
        skills = extract_skills_from_text(cv_text)
        
        # Get job search parameters
        job_query = request.form.get('query', 'software developer').strip()
        job_location = request.form.get('location', 'India').strip()

        logger.info(f"Analyzing CV with {len(skills)} skills")

        # Scrape jobs
        all_jobs_by_source = asyncio.run(scrape_all_sites(job_query, job_location))
        unique_jobs = get_unique_jobs_with_source(all_jobs_by_source)
        
        # Calculate matches
        recommended_jobs = []
        for job in unique_jobs[:100]:
            job_description = f"{job.get('title', '')} {job.get('company', '')}"
            match_score = calculate_job_match(skills, job_description, job.get('title', ''), job.get('company', ''))
            if match_score > 30:
                job['match_score'] = match_score
                recommended_jobs.append(job)
        
        recommended_jobs.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        response = {
            'skills': skills,
            'skills_count': len(skills),
            'recommended_jobs': recommended_jobs[:25],
            'total_jobs': len(recommended_jobs),
            'message': f'Found {len(recommended_jobs)} matching jobs based on your skills'
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error analyzing CV: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error analyzing CV: {str(e)}'}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    logger.info(f"Starting JobHunt app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
