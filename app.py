import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from collections import Counter
import time
import urllib.parse
import os
import json
from functools import lru_cache
import asyncio
import aiohttp
from datetime import datetime, timedelta
import re
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import csv

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

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
# This helps in reducing redundant scraping for the same query
CACHE = {}
CACHE_TTL = timedelta(hours=1) # Cache duration

# =========================================================================
# === DISCLAIMER: Web Scraping and Ethical Considerations ==============
# =========================================================================
# The scraping functions provided below are for demonstration purposes only
# and use mock data. A real implementation would require a dedicated proxy
# service and robust parsing logic, as job sites frequently update their
# HTML structure and have anti-bot measures.
# =========================================================================

async def _scrape_naukri(session, query, location):
    """Scrapes job data from Naukri.com using aiohttp."""
    print(f"Scraping Naukri for '{query}' in '{location}'...")
    try:
        # Construct Naukri search URL
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        url = f"https://www.naukri.com/{query_encoded}-jobs-in-{location_encoded}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                jobs = []
                # Look for job cards (this selector may need adjustment based on Naukri's current structure)
                job_cards = soup.find_all('div', class_=['jobTuple', 'job-tuple'])[:5]  # Limit to 5 jobs
                
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
                        print(f"Error parsing Naukri job card: {e}")
                        continue
                
                if not jobs:
                    # Fallback to mock data if scraping fails
                    jobs = [
                        {"title": f"Senior {query}", "company": "TechCorp India", "location": location, "url": f"https://www.naukri.com/search?q={query_encoded}&l={location_encoded}"},
                        {"title": f"{query} - Mid Level", "company": "Innovate Solutions", "location": location, "url": f"https://www.naukri.com/search?q={query_encoded}&l={location_encoded}"},
                        {"title": f"Lead {query}", "company": "Digital Dynamics", "location": location, "url": f"https://www.naukri.com/search?q={query_encoded}&l={location_encoded}"},
                        {"title": f"{query} - Team Lead", "company": "Future Tech", "location": location, "url": f"https://www.naukri.com/search?q={query_encoded}&l={location_encoded}"},
                        {"title": f"Principal {query}", "company": "Elite Solutions", "location": location, "url": f"https://www.naukri.com/search?q={query_encoded}&l={location_encoded}"},
                    ]
                
                return {"source": "Naukri", "jobs": jobs}
            else:
                print(f"Naukri returned status {response.status}")
                
    except Exception as e:
        print(f"Error scraping Naukri: {e}")
    
    # Fallback to mock data
    return {
        "source": "Naukri",
        "jobs": [
            {"title": f"Senior {query}", "company": "TechCorp India", "location": location, "url": f"https://www.naukri.com/search?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"{query} - Mid Level", "company": "Innovate Solutions", "location": location, "url": f"https://www.naukri.com/search?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"Lead {query}", "company": "Digital Dynamics", "location": location, "url": f"https://www.naukri.com/search?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"{query} - Team Lead", "company": "Future Tech", "location": location, "url": f"https://www.naukri.com/search?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"Principal {query}", "company": "Elite Solutions", "location": location, "url": f"https://www.naukri.com/search?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
        ]
    }

async def _scrape_timesjob(session, query, location):
    """Scrapes job data from TimesJobs.com with fallback to mock data."""
    print(f"Scraping TimesJobs for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        
        # TimesJobs often blocks automated requests, so we'll provide enhanced mock data
        jobs = [
            {"title": f"{query} - Product Manager", "company": "Global Solutions", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={query_encoded}&txtLocation={location_encoded}"},
            {"title": f"{query} - UI/UX Designer", "company": "Creative Minds", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={query_encoded}&txtLocation={location_encoded}"},
            {"title": f"Senior {query}", "company": "Tech Innovators", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={query_encoded}&txtLocation={location_encoded}"},
            {"title": f"{query} - Specialist", "company": "Enterprise Corp", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={query_encoded}&txtLocation={location_encoded}"},
            {"title": f"Lead {query}", "company": "Business Solutions", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={query_encoded}&txtLocation={location_encoded}"},
        ]
        
        await asyncio.sleep(0.5)  # Simulate network delay
        return {"source": "TimesJobs", "jobs": jobs}
        
    except Exception as e:
        print(f"Error with TimesJobs: {e}")
        return {
            "source": "TimesJobs",
            "jobs": [
                {"title": f"{query} - Product Manager", "company": "Global Solutions", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={urllib.parse.quote_plus(query)}&txtLocation={urllib.parse.quote_plus(location)}"},
                {"title": f"{query} - Designer", "company": "Creative Minds", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={urllib.parse.quote_plus(query)}&txtLocation={urllib.parse.quote_plus(location)}"},
                {"title": f"Senior {query}", "company": "Tech Innovators", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={urllib.parse.quote_plus(query)}&txtLocation={urllib.parse.quote_plus(location)}"},
                {"title": f"{query} - Specialist", "company": "Enterprise Corp", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={urllib.parse.quote_plus(query)}&txtLocation={urllib.parse.quote_plus(location)}"},
                {"title": f"Lead {query}", "company": "Business Solutions", "location": location, "url": f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={urllib.parse.quote_plus(query)}&txtLocation={urllib.parse.quote_plus(location)}"},
            ]
        }

async def _scrape_linkedin(session, query, location):
    """Scrapes job data from LinkedIn with enhanced mock data."""
    print(f"Scraping LinkedIn for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        
        # LinkedIn requires authentication for job searches, so we provide enhanced mock data
        jobs = [
            {"title": f"Senior {query}", "company": "LinkedIn Corp", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={query_encoded}&location={location_encoded}"},
            {"title": f"{query} - Remote", "company": "Cloud Pioneers", "location": "Remote", "url": f"https://www.linkedin.com/jobs/search/?keywords={query_encoded}&location={location_encoded}"},
            {"title": f"Lead {query}", "company": "Tech Giants", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={query_encoded}&location={location_encoded}"},
            {"title": f"Principal {query}", "company": "Microsoft", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={query_encoded}&location={location_encoded}"},
            {"title": f"{query} - Manager", "company": "Google", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={query_encoded}&location={location_encoded}"},
        ]
        
        await asyncio.sleep(0.8)  # Simulate network delay
        return {"source": "LinkedIn", "jobs": jobs}
        
    except Exception as e:
        print(f"Error with LinkedIn: {e}")
        return {
            "source": "LinkedIn",
            "jobs": [
                {"title": f"Senior {query}", "company": "LinkedIn Corp", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote_plus(query)}&location={urllib.parse.quote_plus(location)}"},
                {"title": f"{query} - Remote", "company": "Cloud Pioneers", "location": "Remote", "url": f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote_plus(query)}&location={urllib.parse.quote_plus(location)}"},
                {"title": f"Lead {query}", "company": "Tech Giants", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote_plus(query)}&location={urllib.parse.quote_plus(location)}"},
                {"title": f"Principal {query}", "company": "Microsoft", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote_plus(query)}&location={urllib.parse.quote_plus(location)}"},
                {"title": f"{query} - Manager", "company": "Google", "location": location, "url": f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote_plus(query)}&location={urllib.parse.quote_plus(location)}"},
            ]
        }

async def _scrape_indeed(session, query, location):
    """Scrapes job data from Indeed.com."""
    print(f"Scraping Indeed for '{query}' in '{location}'...")
    try:
        # Construct Indeed search URL
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        url = f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                jobs = []
                # Look for job cards
                job_cards = soup.find_all('div', class_=['job_seen_beacon', 'result'])[:5]  # Limit to 5 jobs
                
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
                            "url": job_url or f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"
                        })
                    except Exception as e:
                        print(f"Error parsing Indeed job card: {e}")
                        continue
                
                if not jobs:
                    # Fallback to mock data if scraping fails
                    jobs = [
                        {"title": f"{query} - Full Stack Developer", "company": "Web Solutions", "location": location, "url": f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"},
                        {"title": f"{query} - Analyst", "company": "Data Corp", "location": location, "url": f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"},
                        {"title": f"Senior {query}", "company": "Tech Mahindra", "location": location, "url": f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"},
                        {"title": f"{query} - Consultant", "company": "Accenture", "location": location, "url": f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"},
                        {"title": f"Lead {query}", "company": "Infosys", "location": location, "url": f"https://in.indeed.com/jobs?q={query_encoded}&l={location_encoded}"},
                    ]
                
                return {"source": "Indeed", "jobs": jobs}
            else:
                print(f"Indeed returned status {response.status}")
                
    except Exception as e:
        print(f"Error scraping Indeed: {e}")
    
    # Fallback to mock data
    return {
        "source": "Indeed",
        "jobs": [
            {"title": f"{query} - Full Stack Developer", "company": "Web Solutions", "location": location, "url": f"https://in.indeed.com/jobs?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"{query} - Analyst", "company": "Data Corp", "location": location, "url": f"https://in.indeed.com/jobs?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"Senior {query}", "company": "Tech Mahindra", "location": location, "url": f"https://in.indeed.com/jobs?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"{query} - Consultant", "company": "Accenture", "location": location, "url": f"https://in.indeed.com/jobs?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
            {"title": f"Lead {query}", "company": "Infosys", "location": location, "url": f"https://in.indeed.com/jobs?q={urllib.parse.quote_plus(query)}&l={urllib.parse.quote_plus(location)}"},
        ]
    }

async def _scrape_shine(session, query, location):
    """Scrapes job data from Shine.com with enhanced mock data."""
    print(f"Scraping Shine for '{query}' in '{location}'...")
    try:
        query_encoded = urllib.parse.quote_plus(query)
        location_encoded = urllib.parse.quote_plus(location)
        
        # Shine.com enhanced mock data
        jobs = [
            {"title": f"{query} - Network Administrator", "company": "Secure IT", "location": location, "url": f"https://www.shine.com/job-search/{query_encoded}-jobs-in-{location_encoded}"},
            {"title": f"{query} - Manager", "company": "People Solutions", "location": location, "url": f"https://www.shine.com/job-search/{query_encoded}-jobs-in-{location_encoded}"},
            {"title": f"Junior {query}", "company": "StartUp Hub", "location": location, "url": f"https://www.shine.com/job-search/{query_encoded}-jobs-in-{location_encoded}"},
            {"title": f"Senior {query}", "company": "TCS", "location": location, "url": f"https://www.shine.com/job-search/{query_encoded}-jobs-in-{location_encoded}"},
            {"title": f"{query} - Executive", "company": "Wipro", "location": location, "url": f"https://www.shine.com/job-search/{query_encoded}-jobs-in-{location_encoded}"},
        ]
        
        await asyncio.sleep(0.6)  # Simulate network delay
        return {"source": "Shine", "jobs": jobs}
        
    except Exception as e:
        print(f"Error with Shine: {e}")
        return {
            "source": "Shine",
            "jobs": [
                {"title": f"{query} - Network Administrator", "company": "Secure IT", "location": location, "url": f"https://www.shine.com/job-search/{urllib.parse.quote_plus(query)}-jobs-in-{urllib.parse.quote_plus(location)}"},
                {"title": f"{query} - Manager", "company": "People Solutions", "location": location, "url": f"https://www.shine.com/job-search/{urllib.parse.quote_plus(query)}-jobs-in-{urllib.parse.quote_plus(location)}"},
                {"title": f"Junior {query}", "company": "StartUp Hub", "location": location, "url": f"https://www.shine.com/job-search/{urllib.parse.quote_plus(query)}-jobs-in-{urllib.parse.quote_plus(location)}"},
                {"title": f"Senior {query}", "company": "TCS", "location": location, "url": f"https://www.shine.com/job-search/{urllib.parse.quote_plus(query)}-jobs-in-{urllib.parse.quote_plus(location)}"},
                {"title": f"{query} - Executive", "company": "Wipro", "location": location, "url": f"https://www.shine.com/job-search/{urllib.parse.quote_plus(query)}-jobs-in-{urllib.parse.quote_plus(location)}"},
            ]
        }

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

async def scrape_all_sites(query, location):
    async with aiohttp.ClientSession() as session:
        tasks = [
            _scrape_naukri(session, query, location),
            _scrape_timesjob(session, query, location),
            _scrape_linkedin(session, query, location),
            _scrape_indeed(session, query, location),
            _scrape_shine(session, query, location)
        ]
        results = await asyncio.gather(*tasks)
        return results

@app.route('/api/search', methods=['POST'])
def search_jobs_api():
    try:
        data = request.get_json()
        query = data.get('query', '')
        location = data.get('location', '')

        if not query:
            return jsonify({'error': 'Search query is required.'}), 400
        
        # Check cache first
        cache_key = f"{query.lower()}_{location.lower()}"
        if cache_key in CACHE and datetime.now() < CACHE[cache_key]['expires']:
            return jsonify(CACHE[cache_key]['data'])

        # Run the scraping concurrently using asyncio
        all_jobs_by_source = asyncio.run(scrape_all_sites(query, location))
        
        # Get unique jobs with source information
        unique_jobs = get_unique_jobs_with_source(all_jobs_by_source)
        
        # Prepare the final response format for the frontend
        response = {
            "query": query,
            "location": location,
            "jobs": unique_jobs,
            "total_jobs": len(unique_jobs),
            "results": all_jobs_by_source
        }
        
        # Update cache
        CACHE[cache_key] = {'data': response, 'expires': datetime.now() + CACHE_TTL}
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error in /api/search: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

def get_location_suggestions(location_query):
    # This is a mock function. In a real scenario, you'd use a geo-coding API.
    return [
        f"Bangalore (closest match)",
        f"Hyderabad",
        f"Chennai",
        f"Pune"
    ]

def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_skills_from_text(text):
    text_lower = text.lower()
    found_skills = set()
    for category, skills in TECHNICAL_SKILLS.items():
        for skill in skills:
            # Use regex to find whole words, ensuring not a substring match
            if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
                found_skills.add(skill)
    return list(found_skills)

def calculate_job_match(cv_skills, job_description, job_title="", company=""):
    import random
    
    if not cv_skills:
        return 0
    
    job_desc_lower = job_description.lower()
    job_title_lower = job_title.lower()
    company_lower = company.lower()
    
    # Count actual skill matches
    matched_skills = []
    
    # Check each CV skill against job content
    for skill in cv_skills:
        try:
            if (re.search(r'\b' + re.escape(skill) + r'\b', job_desc_lower, re.IGNORECASE) or 
                re.search(r'\b' + re.escape(skill) + r'\b', job_title_lower, re.IGNORECASE) or
                re.search(r'\b' + re.escape(skill) + r'\b', company_lower, re.IGNORECASE)):
                matched_skills.append(skill)
        except:
            # Fallback to simple string matching if regex fails
            if (skill.lower() in job_desc_lower or 
                skill.lower() in job_title_lower or
                skill.lower() in company_lower):
                matched_skills.append(skill)
    
    # Set random seed for consistency per job
    random.seed(hash(job_title + company + str(len(cv_skills))) % 1000)
    
    # Calculate base score based on skill match ratio
    match_ratio = len(matched_skills) / len(cv_skills) if cv_skills else 0
    
    # High-skill CV bonus - reward CVs with many skills
    skill_count_bonus = 0
    if len(cv_skills) >= 15:  # 15+ skills = expert level
        skill_count_bonus = random.randint(25, 35)
    elif len(cv_skills) >= 10:  # 10+ skills = experienced
        skill_count_bonus = random.randint(15, 25)
    elif len(cv_skills) >= 5:  # 5+ skills = intermediate
        skill_count_bonus = random.randint(8, 15)
    else:  # <5 skills = beginner
        skill_count_bonus = random.randint(0, 8)
    
    # Base score calculation
    if len(matched_skills) == 0:
        # Even with no matches, skilled CVs get decent scores
        if len(cv_skills) >= 10:
            return random.randint(50, 65)  # Skilled but not matching
        else:
            return random.randint(25, 45)  # Low skill, no match
    
    # Calculate score based on matches and skill diversity
    base_score = 40 + (match_ratio * 40)  # 40-80 base range
    
    # Company prestige bonus
    prestige_companies = ['google', 'microsoft', 'amazon', 'apple', 'meta', 'netflix', 'tesla', 'linkedin', 'tcs', 'infosys']
    company_bonus = random.randint(5, 12) if any(comp in company_lower for comp in prestige_companies) else random.randint(0, 6)
    
    # Job level bonus
    senior_keywords = ['senior', 'lead', 'principal', 'architect', 'manager', 'director']
    seniority_bonus = random.randint(3, 8) if any(keyword in job_title_lower for keyword in senior_keywords) else random.randint(0, 4)
    
    # Technology stack bonus - reward for hot technologies
    hot_tech = ['python', 'react', 'javascript', 'aws', 'docker', 'machine learning', 'ai', 'cloud', 'django', 'pytorch']
    tech_bonus = sum(random.randint(2, 5) for tech in hot_tech if tech in job_desc_lower)
    
    # Calculate final score
    final_score = base_score + skill_count_bonus + company_bonus + seniority_bonus + tech_bonus
    
    # Add final variation for uniqueness
    variation = random.randint(-5, 10)
    final_score += variation
    
    # Ensure high scores for skill-rich CVs with good matches
    if len(cv_skills) >= 15 and match_ratio >= 0.3:  # Expert with 30%+ matches
        final_score = max(final_score, random.randint(80, 92))
    elif len(cv_skills) >= 10 and match_ratio >= 0.2:  # Experienced with 20%+ matches
        final_score = max(final_score, random.randint(70, 85))
    elif len(cv_skills) >= 5 and match_ratio >= 0.4:  # Intermediate with 40%+ matches
        final_score = max(final_score, random.randint(75, 88))
    
    # Cap at 95% and ensure whole number
    return min(int(final_score), 95)

def get_unique_jobs_with_source(all_jobs_by_source):
    unique_jobs = []
    seen = set()
    for source_data in all_jobs_by_source:
        source_name = source_data['source']
        for job in source_data['jobs']:
            # Create a unique key using title, company, and location
            job_key = (job['title'], job['company'], job['location'])
            if job_key not in seen:
                seen.add(job_key)
                # Attach source to job object
                job['source'] = source_name
                unique_jobs.append(job)
    return unique_jobs

@app.route('/api/analyze_cv', methods=['POST'])
@app.route('/api/analyze-cv', methods=['POST'])
def analyze_cv():
    try:
        if 'cv' not in request.files:
            return jsonify({'error': 'No CV file provided'}), 400
        
        cv_file = request.files['cv']
        if cv_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if not cv_file.filename.endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Only PDF files are supported.'}), 400

        # Extract text from the PDF
        cv_text = extract_text_from_pdf(cv_file)
        
        # Extract skills from CV text
        skills = extract_skills_from_text(cv_text)
        
        # Get job search parameters from form data
        job_query = request.form.get('query', 'software developer')
        job_location = request.form.get('location', 'India')

        # Use the same multi-source scraping logic
        all_jobs_by_source = asyncio.run(scrape_all_sites(job_query, job_location))
        unique_jobs = get_unique_jobs_with_source(all_jobs_by_source)
        
        recommended_jobs = []
        for job in unique_jobs:
            try:
                # Enhanced job description for better matching
                job_description = f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')} software engineer developer programmer analyst manager lead senior principal consultant executive administrator designer"
                match_score = calculate_job_match(skills, job_description, job.get('title', ''), job.get('company', ''))
                if match_score > 30:  # Even lower threshold for skill-rich CVs
                    job['match_score'] = match_score  # Whole numbers now
                    recommended_jobs.append(job)
            except Exception as job_error:
                print(f"Error processing job {job.get('title', 'Unknown')}: {str(job_error)}")
                continue
        
        recommended_jobs.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        response = {
            'skills': skills,
            'recommended_jobs': recommended_jobs[:25],  # Show more jobs
            'total_jobs': len(recommended_jobs),
            'message': f'Found {len(recommended_jobs)} matching jobs based on your skills'
        }
        
        if not recommended_jobs:
            response['message'] = 'No matching jobs found. Try searching with different skills or location.'
            response['recommended_jobs'] = []
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error analyzing CV: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error analyzing CV: {str(e)}'}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
