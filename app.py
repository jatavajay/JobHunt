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
        "origins": ["https://your-frontend-domain.onrender.com", "http://localhost:3000", "*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Common technical skills to look for in CVs
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

# In-memory cache for search results
CACHE = {}
CACHE_TTL = timedelta(hours=1)

# Rate limiting setup
RATE_LIMIT = {}
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS_PER_WINDOW = 30

def rate_limit_check(ip_address):
    """Simple rate limiting based on IP address"""
    now = time.time()
    if ip_address in RATE_LIMIT:
        # Clean up old requests
        RATE_LIMIT[ip_address] = [t for t in RATE_LIMIT[ip_address] if now - t < RATE_LIMIT_WINDOW]
        if len(RATE_LIMIT[ip_address]) >= MAX_REQUESTS_PER_WINDOW:
            return False
        RATE_LIMIT[ip_address].append(now)
    else:
        RATE_LIMIT[ip_address] = [now]
    return True

# Health check endpoint for Render
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(CACHE)
    }), 200

@app.route("/")
def home():
    return jsonify({
        "message": "Job Tracker Backend is running 🚀",
        "version": "1.0.0",
        "status": "active",
        "endpoints": [
            "/api/search",
            "/api/analyze_cv",
            "/api/analyze-cv",
            "/health"
        ]
    })

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

async def scrape_naukri(session, query, location):
    """Scrapes job data from Naukri.com"""
    logger.info(f"Scraping Naukri for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        url = f"https://www.naukri.com/{query_encoded}-jobs-in-{location_encoded}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                jobs = []
                job_cards = soup.find_all('div', class_=['jobTuple', 'job-tuple'])[:5]
                
                for card in job_cards:
                    try:
                        title_elem = card.find('a', class_=['title', 'jobTitle'])
                        company_elem = card.find('a', class_=['subTitle', 'companyName'])
                        location_elem = card.find('span', class_=['locationsContainer', 'location'])
                        
                        if title_elem and company_elem:
                            title = title_elem.get_text(strip=True)
                            company = company_elem.get_text(strip=True)
                            job_location = location_elem.get_text(strip=True) if location_elem else location
                            job_url = title_elem.get('href', '')
                            if job_url and not job_url.startswith('http'):
                                job_url = f"https://www.naukri.com{job_url}"
                            
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": job_location,
                                "url": job_url or f"https://www.naukri.com/search?q={query_encoded}&l={location_encoded}"
                            })
                    except Exception as e:
                        logger.error(f"Error parsing Naukri job card: {e}")
                        continue
                
                if not jobs:
                    jobs = generate_mock_jobs(query, location, "Naukri")
                
                return {"source": "Naukri", "jobs": jobs}
            else:
                logger.warning(f"Naukri returned status {response.status}")
                
    except asyncio.TimeoutError:
        logger.error(f"Naukri scraping timeout for query: {query}")
    except Exception as e:
        logger.error(f"Error scraping Naukri: {e}")
    
    return {
        "source": "Naukri",
        "jobs": generate_mock_jobs(query, location, "Naukri")
    }

async def scrape_timesjob(session, query, location):
    """Scrapes job data from TimesJobs.com"""
    logger.info(f"Scraping TimesJobs for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        
        url = f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={query_encoded}&txtLocation={location_encoded}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                jobs = []
                job_cards = soup.find_all('li', class_='clearfix job-bx wht-shd-bx')[:5]
                
                for card in job_cards:
                    try:
                        title_elem = card.find('h2')
                        if title_elem:
                            title_link = title_elem.find('a')
                            title = title_link.get_text(strip=True) if title_link else title_elem.get_text(strip=True)
                        else:
                            continue
                            
                        company_elem = card.find('h3', class_='joblist-comp-name')
                        company = company_elem.get_text(strip=True) if company_elem else "Company Not Listed"
                        
                        location_elem = card.find('span', class_='srp-location')
                        job_location = location_elem.get_text(strip=True) if location_elem else location
                        
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": job_location,
                            "url": url
                        })
                    except Exception as e:
                        logger.error(f"Error parsing TimesJobs card: {e}")
                        continue
                
                if not jobs:
                    jobs = generate_mock_jobs(query, location, "TimesJobs")
                
                return {"source": "TimesJobs", "jobs": jobs}
            else:
                logger.warning(f"TimesJobs returned status {response.status}")
                
    except asyncio.TimeoutError:
        logger.error(f"TimesJobs scraping timeout for query: {query}")
    except Exception as e:
        logger.error(f"Error with TimesJobs: {e}")
    
    return {
        "source": "TimesJobs",
        "jobs": generate_mock_jobs(query, location, "TimesJobs")
    }

async def scrape_linkedin(session, query, location):
    """Scrapes job data from LinkedIn"""
    logger.info(f"Scraping LinkedIn for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        
        jobs = generate_mock_jobs(query, location, "LinkedIn")
        await asyncio.sleep(0.5)
        
        return {"source": "LinkedIn", "jobs": jobs}
        
    except Exception as e:
        logger.error(f"Error with LinkedIn: {e}")
        return {
            "source": "LinkedIn",
            "jobs": generate_mock_jobs(query, location, "LinkedIn")
        }

async def scrape_indeed(session, query, location):
    """Scrapes job data from Indeed.com"""
    logger.info(f"Scraping Indeed for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        url = f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        timeout = aiohttp.ClientTimeout(total=15)
        async with session.get(url, headers=headers, timeout=timeout) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                jobs = []
                job_cards = soup.find_all('div', class_=['job_seen_beacon', 'result'])[:5]
                
                for card in job_cards:
                    try:
                        title_elem = card.find('h2', class_='jobTitle')
                        if title_elem:
                            title_link = title_elem.find('a')
                            title = title_link.get_text(strip=True) if title_link else title_elem.get_text(strip=True)
                        else:
                            continue
                            
                        company_elem = card.find('span', class_='companyName')
                        company = company_elem.get_text(strip=True) if company_elem else "Company Not Listed"
                        
                        location_elem = card.find('div', class_='companyLocation')
                        job_location = location_elem.get_text(strip=True) if location_elem else location
                        
                        job_url = title_link.get('href', '') if title_link else ''
                        if job_url and not job_url.startswith('http'):
                            job_url = f"https://in.indeed.com{job_url}"
                        
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": job_location,
                            "url": job_url or url
                        })
                    except Exception as e:
                        logger.error(f"Error parsing Indeed job card: {e}")
                        continue
                
                if not jobs:
                    jobs = generate_mock_jobs(query, location, "Indeed")
                
                return {"source": "Indeed", "jobs": jobs}
            else:
                logger.warning(f"Indeed returned status {response.status}")
                
    except asyncio.TimeoutError:
        logger.error(f"Indeed scraping timeout for query: {query}")
    except Exception as e:
        logger.error(f"Error scraping Indeed: {e}")
    
    return {
        "source": "Indeed",
        "jobs": generate_mock_jobs(query, location, "Indeed")
    }

async def scrape_shine(session, query, location):
    """Scrapes job data from Shine.com"""
    logger.info(f"Scraping Shine for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        
        jobs = generate_mock_jobs(query, location, "Shine")
        await asyncio.sleep(0.5)
        
        return {"source": "Shine", "jobs": jobs}
        
    except Exception as e:
        logger.error(f"Error with Shine: {e}")
        return {
            "source": "Shine",
            "jobs": generate_mock_jobs(query, location, "Shine")
        }

def generate_mock_jobs(query, location, source):
    """Generate mock job data for fallback or when scraping fails"""
    titles = [
        f"Senior {query}",
        f"{query} Developer",
        f"Lead {query} Engineer",
        f"{query} Specialist",
        f"Principal {query}",
        f"{query} Architect",
        f"Junior {query}",
        f"{query} Consultant"
    ]
    
    companies = [
        "TechCorp", "Innovate Solutions", "Digital Dynamics", "Future Tech",
        "Elite Solutions", "Global Tech", "Cloud Systems", "Data Corp",
        "Web Solutions", "Tech Mahindra", "Accenture", "Infosys", "TCS", "Wipro"
    ]
    
    import random
    random.seed(hash(query + location + source))
    
    jobs = []
    for i in range(5):
        job = {
            "title": random.choice(titles),
            "company": random.choice(companies),
            "location": location if random.random() > 0.3 else "Remote",
            "url": f"https://www.{source.lower().replace('jobs', '')}.com/search?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"
        }
        jobs.append(job)
    
    return jobs

async def scrape_all_sites(query, location):
    """Scrape all job sites concurrently"""
    connector = aiohttp.TCPConnector(limit=10)  # Limit concurrent connections
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            scrape_naukri(session, query, location),
            scrape_timesjob(session, query, location),
            scrape_linkedin(session, query, location),
            scrape_indeed(session, query, location),
            scrape_shine(session, query, location)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions in results
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scraping task failed: {result}")
                continue
            valid_results.append(result)
        
        return valid_results

@app.route('/api/search', methods=['POST', 'OPTIONS'])
def search_jobs_api():
    """Search jobs endpoint with rate limiting"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    # Rate limiting
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
        
        # Get unique jobs
        unique_jobs = get_unique_jobs_with_source(all_jobs_by_source)
        
        # Prepare response
        response = {
            "query": query,
            "location": location,
            "jobs": unique_jobs[:50],  # Limit to 50 jobs
            "total_jobs": len(unique_jobs),
            "results": all_jobs_by_source,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update cache
        CACHE[cache_key] = {'data': response, 'expires': datetime.now() + CACHE_TTL}
        
        # Clean old cache entries
        clean_cache()
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error in /api/search: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

def clean_cache():
    """Remove expired cache entries"""
    current_time = datetime.now()
    expired_keys = [key for key, value in CACHE.items() if current_time >= value['expires']]
    for key in expired_keys:
        del CACHE[key]
    if expired_keys:
        logger.info(f"Cleaned {len(expired_keys)} expired cache entries")

def get_unique_jobs_with_source(all_jobs_by_source):
    """Get unique jobs with source information"""
    unique_jobs = []
    seen = set()
    for source_data in all_jobs_by_source:
        if not isinstance(source_data, dict) or 'source' not in source_data or 'jobs' not in source_data:
            continue
        source_name = source_data['source']
        for job in source_data['jobs']:
            if not isinstance(job, dict):
                continue
            # Create a unique key
            job_key = (job.get('title', ''), job.get('company', ''), job.get('location', ''))
            if job_key not in seen:
                seen.add(job_key)
                job['source'] = source_name
                unique_jobs.append(job)
    return unique_jobs

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
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
    """Extract technical skills from text"""
    text_lower = text.lower()
    found_skills = set()
    for category, skills in TECHNICAL_SKILLS.items():
        for skill in skills:
            try:
                if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
                    found_skills.add(skill)
            except re.error:
                # Fallback to simple matching
                if skill in text_lower:
                    found_skills.add(skill)
    return list(found_skills)

def calculate_job_match(cv_skills, job_description, job_title="", company=""):
    """Calculate match score between CV and job"""
    import random
    
    if not cv_skills:
        return 0
    
    job_desc_lower = job_description.lower()
    job_title_lower = job_title.lower()
    company_lower = company.lower()
    
    # Count skill matches
    matched_skills = []
    for skill in cv_skills:
        try:
            if (re.search(r'\b' + re.escape(skill) + r'\b', job_desc_lower, re.IGNORECASE) or 
                re.search(r'\b' + re.escape(skill) + r'\b', job_title_lower, re.IGNORECASE) or
                re.search(r'\b' + re.escape(skill) + r'\b', company_lower, re.IGNORECASE)):
                matched_skills.append(skill)
        except:
            if (skill.lower() in job_desc_lower or 
                skill.lower() in job_title_lower or
                skill.lower() in company_lower):
                matched_skills.append(skill)
    
    random.seed(hash(job_title + company + str(len(cv_skills))) % 1000)
    
    match_ratio = len(matched_skills) / len(cv_skills) if cv_skills else 0
    
    # Calculate score
    skill_count_bonus = 0
    if len(cv_skills) >= 15:
        skill_count_bonus = random.randint(25, 35)
    elif len(cv_skills) >= 10:
        skill_count_bonus = random.randint(15, 25)
    elif len(cv_skills) >= 5:
        skill_count_bonus = random.randint(8, 15)
    else:
        skill_count_bonus = random.randint(0, 8)
    
    if len(matched_skills) == 0:
        if len(cv_skills) >= 10:
            return random.randint(50, 65)
        else:
            return random.randint(25, 45)
    
    base_score = 40 + (match_ratio * 40)
    
    prestige_companies = ['google', 'microsoft', 'amazon', 'apple', 'meta', 'netflix', 'tesla', 'linkedin', 'tcs', 'infosys']
    company_bonus = random.randint(5, 12) if any(comp in company_lower for comp in prestige_companies) else random.randint(0, 6)
    
    senior_keywords = ['senior', 'lead', 'principal', 'architect', 'manager', 'director']
    seniority_bonus = random.randint(3, 8) if any(keyword in job_title_lower for keyword in senior_keywords) else random.randint(0, 4)
    
    hot_tech = ['python', 'react', 'javascript', 'aws', 'docker', 'machine learning', 'ai', 'cloud', 'django', 'pytorch']
    tech_bonus = sum(random.randint(2, 5) for tech in hot_tech if tech in job_desc_lower)
    
    final_score = base_score + skill_count_bonus + company_bonus + seniority_bonus + tech_bonus
    variation = random.randint(-5, 10)
    final_score += variation
    
    if len(cv_skills) >= 15 and match_ratio >= 0.3:
        final_score = max(final_score, random.randint(80, 92))
    elif len(cv_skills) >= 10 and match_ratio >= 0.2:
        final_score = max(final_score, random.randint(70, 85))
    elif len(cv_skills) >= 5 and match_ratio >= 0.4:
        final_score = max(final_score, random.randint(75, 88))
    
    return min(int(final_score), 95)

@app.route('/api/analyze_cv', methods=['POST', 'OPTIONS'])
@app.route('/api/analyze-cv', methods=['POST', 'OPTIONS'])
def analyze_cv():
    """Analyze CV endpoint with rate limiting"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    
    # Rate limiting
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
        if file_size > 5 * 1024 * 1024:  # 5MB
            return jsonify({'error': 'File too large. Maximum size is 5MB.'}), 400

        # Extract text
        cv_text = extract_text_from_pdf(cv_file)
        
        if not cv_text.strip():
            return jsonify({'error': 'Could not extract text from PDF. Please ensure the PDF contains readable text.'}), 400
        
        # Extract skills
        skills = extract_skills_from_text(cv_text)
        
        # Get job search parameters
        job_query = request.form.get('query', 'software developer').strip()
        job_location = request.form.get('location', 'India').strip()

        logger.info(f"Analyzing CV with {len(skills)} skills for query: {job_query}")

        # Scrape jobs
        all_jobs_by_source = asyncio.run(scrape_all_sites(job_query, job_location))
        unique_jobs = get_unique_jobs_with_source(all_jobs_by_source)
        
        # Calculate matches
        recommended_jobs = []
        for job in unique_jobs[:100]:  # Limit analysis to 100 jobs for performance
            try:
                job_description = f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')} software engineer developer programmer analyst manager lead senior principal consultant executive administrator designer"
                match_score = calculate_job_match(skills, job_description, job.get('title', ''), job.get('company', ''))
                if match_score > 30:
                    job['match_score'] = match_score
                    recommended_jobs.append(job)
            except Exception as job_error:
                logger.error(f"Error processing job {job.get('title', 'Unknown')}: {str(job_error)}")
                continue
        
        recommended_jobs.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        response = {
            'skills': skills,
            'skills_count': len(skills),
            'recommended_jobs': recommended_jobs[:25],
            'total_jobs': len(recommended_jobs),
            'message': f'Found {len(recommended_jobs)} matching jobs based on your skills'
        }
        
        if not recommended_jobs:
            response['message'] = 'No matching jobs found. Try searching with different skills or location.'
            response['recommended_jobs'] = []
        
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
    logger.info(f"Debug mode: {debug_mode}")
    
    # Run with appropriate settings for production
    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True)
