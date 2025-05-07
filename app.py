from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
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
    'testing': ['junit', 'pytest', 'selenium', 'cypress', 'jest', 'mocha']
}

# Common skill patterns to look for in text
SKILL_PATTERNS = [
    r'\b(?:proficient|experienced|skilled|expert|knowledge|familiar|working|using|developed|implemented|created|built|designed|maintained|managed|administered|configured|deployed|tested|debugged|optimized|analyzed|monitored|secured|automated|integrated|migrated|upgraded|troubleshoot|resolved|documented|collaborated|led|mentored|trained|coordinated|planned|executed|delivered|improved|enhanced|optimized|scaled|maintained|supported|developed|implemented|created|built|designed|maintained|managed|administered|configured|deployed|tested|debugged|optimized|analyzed|monitored|secured|automated|integrated|migrated|upgraded|troubleshoot|resolved|documented|collaborated|led|mentored|trained|coordinated|planned|executed|delivered|improved|enhanced|optimized|scaled|maintained|supported)\s+(?:in|with|on|using|through|via|by|for|as|at|to|from|of|about|regarding|concerning|relating|pertaining|involving|including|containing|comprising|consisting|constituting|forming|making|composing|constituting|forming|making|composing)\s+([a-zA-Z0-9\s\+\#\.]+?)(?:,|\.|;|:|$|\s)',
    r'\b(?:experience|knowledge|skills|expertise|proficiency|familiarity|understanding|mastery|command|grasp|comprehension|awareness|insight|wisdom|savvy|know-how|expertise|proficiency|familiarity|understanding|mastery|command|grasp|comprehension|awareness|insight|wisdom|savvy|know-how)\s+(?:in|with|on|using|through|via|by|for|as|at|to|from|of|about|regarding|concerning|relating|pertaining|involving|including|containing|comprising|consisting|constituting|forming|making|composing|constituting|forming|making|composing)\s+([a-zA-Z0-9\s\+\#\.]+?)(?:,|\.|;|:|$|\s)',
    r'\b(?:worked|developed|implemented|created|built|designed|maintained|managed|administered|configured|deployed|tested|debugged|optimized|analyzed|monitored|secured|automated|integrated|migrated|upgraded|troubleshoot|resolved|documented|collaborated|led|mentored|trained|coordinated|planned|executed|delivered|improved|enhanced|optimized|scaled|maintained|supported)\s+(?:with|on|using|through|via|by|for|as|at|to|from|of|about|regarding|concerning|relating|pertaining|involving|including|containing|comprising|consisting|constituting|forming|making|composing|constituting|forming|making|composing)\s+([a-zA-Z0-9\s\+\#\.]+?)(?:,|\.|;|:|$|\s)'
]

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }

def scrape_indeed(query, location):
    """Scrape jobs from Indeed with improved error handling and reliability."""
    jobs = []
    try:
        print(f"Scraping Indeed for query: {query}, location: {location}")
        
        # More complete headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }
        
        # Try multiple page numbers to get more results
        for page in range(3):  # Try first 3 pages
            try:
                # Use query parameters properly
                params = {
                    'q': query,
                    'l': location,
                    'sort': 'date',
                    'start': page * 10,  # Indeed uses multiples of 10 for pagination
                    'fromage': '7',  # Last 7 days
                    'filter': '0'    # No filtering
                }
                
                base_url = "https://www.indeed.com/jobs"
                
                print(f"Requesting Indeed URL: {base_url} with params: {params}")
                response = requests.get(base_url, headers=headers, params=params, timeout=20)
                print(f"Indeed Response Status: {response.status_code}")
                print(f"Indeed Response URL: {response.url}")
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'lxml')
                    
                    # Try different possible selectors for job cards
                    job_cards = []
                    selectors = [
                        'div.job_seen_beacon',
                        'td.resultContent',
                        'div.jobsearch-SerpJobCard',
                        'div[class*="job_seen_beacon"]',
                        'div[class*="jobsearch-SerpJobCard"]',
                        'div[class*="job-card"]'
                    ]
                    
                    for selector in selectors:
                        job_cards = soup.select(selector)
                        if job_cards:
                            print(f"Found {len(job_cards)} job cards using selector: {selector}")
                            break
                    
                    if not job_cards:
                        print("No job cards found with any selector on page", page + 1)
                        continue
                    
                    for card in job_cards:
                        try:
                            # Multiple selectors for different Indeed HTML structures
                            title = None
                            title_selectors = [
                                'h2.jobTitle', 
                                'a.jcs-JobTitle',
                                'h2.title',
                                'span.jobTitle'
                            ]
                            for selector in title_selectors:
                                title_elem = card.select_one(selector)
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    break
                            
                            company = None
                            company_selectors = [
                                'span.companyName',
                                'div.company_location',
                                'span.company'
                            ]
                            for selector in company_selectors:
                                company_elem = card.select_one(selector)
                                if company_elem:
                                    company = company_elem.get_text(strip=True)
                                    break
                            
                            job_location = None
                            location_selectors = [
                                'div.companyLocation',
                                'div.companyInfo span.location',
                                'span.location'
                            ]
                            for selector in location_selectors:
                                location_elem = card.select_one(selector)
                                if location_elem:
                                    job_location = location_elem.get_text(strip=True)
                                    break
                            
                            # Find URL - look for any anchor tag with href
                            url = None
                            url_elem = card.find('a', href=True)
                            if url_elem and 'href' in url_elem.attrs:
                                url = url_elem['href']
                                if not url.startswith('http'):
                                    url = 'https://www.indeed.com' + url
                            
                            if title and company:  # Only require title and company to be present
                                job_data = {
                                    "title": title,
                                    "company": company,
                                    "location": job_location or location,
                                    "url": url or "#",
                                    "source": "Indeed"
                                }
                                
                                # Check for duplicates before adding
                                is_duplicate = False
                                for existing_job in jobs:
                                    if (existing_job['title'] == job_data['title'] and 
                                        existing_job['company'] == job_data['company']):
                                        is_duplicate = True
                                        break
                                
                                if not is_duplicate:
                                    print(f"Found Indeed job: {job_data['title']} at {job_data['company']}")
                                    jobs.append(job_data)
                            
                        except Exception as e:
                            print(f"Error parsing Indeed job card: {str(e)}")
                            continue
                    
                    # If we have enough jobs, break the pagination loop
                    if len(jobs) >= 15:  # Aim for 15 unique jobs
                        break
                        
                else:
                    print(f"Indeed returned non-200 status code: {response.status_code}")
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"Request error for Indeed page {page + 1}: {str(e)}")
                continue
                
    except Exception as e:
        print(f"Error in Indeed scraping: {str(e)}")
    
    print(f"Returning {len(jobs)} jobs from Indeed")
    return jobs

def scrape_linkedin(query, location):
    """Scrape jobs from LinkedIn with improved error handling and reliability."""
    jobs = []
    try:
        print(f"Scraping LinkedIn for query: {query}, location: {location}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Try multiple pages
        for page in range(3):  # Try first 3 pages
            try:
                # LinkedIn uses 'start' parameter for pagination, 25 results per page
                start = page * 25
                url = f"https://www.linkedin.com/jobs/search?keywords={urllib.parse.quote(query)}&location={urllib.parse.quote(location)}&start={start}"
                print(f"LinkedIn URL: {url}")
                
                response = requests.get(url, headers=headers, timeout=15)
                print(f"LinkedIn Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    job_cards = soup.find_all('div', {'class': 'base-card'})
                    print(f"Found {len(job_cards)} job cards on LinkedIn page {page + 1}")
                    
                    if not job_cards:
                        print(f"No job cards found on LinkedIn page {page + 1}")
                        continue
                    
                    for card in job_cards:
                        try:
                            title_elem = card.find('h3', {'class': 'base-search-card__title'})
                            company_elem = card.find('h4', {'class': 'base-search-card__subtitle'})
                            location_elem = card.find('span', {'class': 'job-search-card__location'})
                            url_elem = card.find('a', {'class': 'base-card__full-link'})
                            
                            if title_elem and company_elem:
                                job_data = {
                                    "title": title_elem.get_text(strip=True),
                                    "company": company_elem.get_text(strip=True),
                                    "location": location_elem.get_text(strip=True) if location_elem else location,
                                    "url": url_elem['href'] if url_elem and 'href' in url_elem.attrs else "",
                                    "source": "LinkedIn"
                                }
                                
                                # Check for duplicates before adding
                                is_duplicate = False
                                for existing_job in jobs:
                                    if (existing_job['title'] == job_data['title'] and 
                                        existing_job['company'] == job_data['company']):
                                        is_duplicate = True
                                        break
                                
                                if not is_duplicate:
                                    print(f"Found LinkedIn job: {job_data['title']} at {job_data['company']}")
                                    jobs.append(job_data)
                                    
                        except Exception as e:
                            print(f"Error parsing LinkedIn job card: {str(e)}")
                            continue
                    
                    # If we have enough jobs, break the pagination loop
                    if len(jobs) >= 15:  # Aim for 15 unique jobs
                        break
                        
                else:
                    print(f"LinkedIn returned non-200 status code: {response.status_code}")
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"Request error for LinkedIn page {page + 1}: {str(e)}")
                continue
                
    except Exception as e:
        print(f"Error in LinkedIn scraping: {str(e)}")
    
    print(f"Returning {len(jobs)} jobs from LinkedIn")
    return jobs

def scrape_naukri(query, location):
    """Scrape jobs from Naukri with improved error handling and reliability."""
    jobs = []
    try:
        print(f"Scraping Naukri for query: {query}, location: {location}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        url = f"https://www.naukri.com/{urllib.parse.quote(query)}-jobs-in-{urllib.parse.quote(location)}"
        print(f"Naukri URL: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            print(f"Naukri Response Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                job_cards = soup.find_all('article', {'class': 'jobTuple'})
                print(f"Found {len(job_cards)} job cards on Naukri")
                
                for card in job_cards[:5]:  # Limit to first 5 jobs
                    try:
                        title_elem = card.find('a', {'class': 'title'})
                        company_elem = card.find('a', {'class': 'subTitle'})
                        location_elem = card.find('li', {'class': 'location'})
                        
                        if title_elem and company_elem:
                            job_data = {
                                "title": title_elem.get_text(strip=True),
                                "company": company_elem.get_text(strip=True),
                                "location": location_elem.get_text(strip=True) if location_elem else location,
                                "url": "https://www.naukri.com" + title_elem['href'] if title_elem and 'href' in title_elem.attrs else "",
                                "source": "Naukri"
                            }
                            print(f"Found Naukri job: {job_data['title']} at {job_data['company']}")
                            jobs.append(job_data)
                    except Exception as e:
                        print(f"Error parsing Naukri job card: {str(e)}")
                        continue
            else:
                print(f"Naukri returned non-200 status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request error for Naukri: {str(e)}")
            raise
    except Exception as e:
        print(f"Error in Naukri scraping: {str(e)}")
        raise
    
    print(f"Returning {len(jobs)} jobs from Naukri")
    return jobs

def scrape_timesjobs(query, location):
    """Scrape jobs from TimesJobs with improved error handling and reliability."""
    jobs = []
    try:
        print(f"Scraping TimesJobs for query: {query}, location: {location}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        url = f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords={urllib.parse.quote(query)}&txtLocation={urllib.parse.quote(location)}"
        print(f"TimesJobs URL: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            print(f"TimesJobs Response Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                job_cards = soup.find_all('li', {'class': 'clearfix job-bx wht-shd-bx'})
                print(f"Found {len(job_cards)} job cards on TimesJobs")
                
                for card in job_cards[:5]:  # Limit to first 5 jobs
                    try:
                        title_elem = card.find('h2')
                        company_elem = card.find('h3', {'class': 'joblist-comp-name'})
                        location_elem = card.find('ul', {'class': 'top-jd-dtl clearfix'}).find('span')
                        
                        if title_elem and company_elem:
                            job_data = {
                                "title": title_elem.get_text(strip=True),
                                "company": company_elem.get_text(strip=True),
                                "location": location_elem.get_text(strip=True) if location_elem else location,
                                "url": title_elem.find('a')['href'] if title_elem.find('a') and 'href' in title_elem.find('a').attrs else "",
                                "source": "TimesJobs"
                            }
                            print(f"Found TimesJobs job: {job_data['title']} at {job_data['company']}")
                            jobs.append(job_data)
                    except Exception as e:
                        print(f"Error parsing TimesJobs job card: {str(e)}")
                        continue
            else:
                print(f"TimesJobs returned non-200 status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request error for TimesJobs: {str(e)}")
            raise
    except Exception as e:
        print(f"Error in TimesJobs scraping: {str(e)}")
        raise
    
    print(f"Returning {len(jobs)} jobs from TimesJobs")
    return jobs

def scrape_shine(query, location):
    jobs = []
    encoded_query = urllib.parse.quote(query)
    encoded_location = urllib.parse.quote(location)
    url = f"https://www.shine.com/job-search/{encoded_query}-jobs-in-{encoded_location}"
    
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        job_cards = soup.find_all('div', {'class': 'jobCard_jobCard__body__'})
        
        for card in job_cards:
            try:
                title_elem = card.find('h2')
                company_elem = card.find('div', {'class': 'jobCard_jobCard__companyName__'})
                location_elem = card.find('div', {'class': 'jobCard_jobCard__location__'})
                url_elem = card.find('a', {'class': 'jobCard_jobCard__link__'})
                
                if title_elem:
                    jobs.append({
                        "title": title_elem.get_text(strip=True),
                        "company": company_elem.get_text(strip=True) if company_elem else "Company not listed",
                        "location": location_elem.get_text(strip=True) if location_elem else location,
                        "url": "https://www.shine.com" + url_elem['href'] if url_elem and 'href' in url_elem.attrs else "",
                        "source": "Shine"
                    })
            except Exception as e:
                print(f"Error parsing Shine job: {e}")
                continue
    except Exception as e:
        print(f"Error fetching from Shine: {e}")
    
    return jobs

def get_default_companies(query):
    """Return relevant default companies based on the job query."""
    query_lower = query.lower()
    
    # Define company categories with keywords and related companies
    company_categories = {
        'technology': {
            'keywords': ['software', 'developer', 'engineer', 'programmer', 'tech', 'it', 'data', 'cloud', 'devops'],
            'companies': [
                {"company": "Google", "url": "https://careers.google.com", "locations": ["Mountain View, CA", "Remote", "Multiple Locations"]},
                {"company": "Microsoft", "url": "https://careers.microsoft.com", "locations": ["Redmond, WA", "Remote", "Multiple Locations"]},
                {"company": "Amazon", "url": "https://www.amazon.jobs", "locations": ["Seattle, WA", "Remote", "Multiple Locations"]},
                {"company": "Apple", "url": "https://www.apple.com/careers", "locations": ["Cupertino, CA", "Remote", "Multiple Locations"]},
                {"company": "Meta", "url": "https://www.metacareers.com", "locations": ["Menlo Park, CA", "Remote", "Multiple Locations"]},
                {"company": "Netflix", "url": "https://jobs.netflix.com", "locations": ["Los Gatos, CA", "Remote", "Multiple Locations"]},
                {"company": "LinkedIn", "url": "https://careers.linkedin.com", "locations": ["Sunnyvale, CA", "Remote", "Multiple Locations"]},
                {"company": "Twitter", "url": "https://careers.twitter.com", "locations": ["San Francisco, CA", "Remote", "Multiple Locations"]},
                {"company": "Adobe", "url": "https://www.adobe.com/careers", "locations": ["San Jose, CA", "Remote", "Multiple Locations"]},
                {"company": "Salesforce", "url": "https://www.salesforce.com/company/careers", "locations": ["San Francisco, CA", "Remote", "Multiple Locations"]}
            ]
        },
        'finance': {
            'keywords': ['finance', 'bank', 'accounting', 'financial', 'investment', 'trading', 'analyst'],
            'companies': [
                {"company": "JPMorgan Chase", "url": "https://careers.jpmorgan.com", "locations": ["New York, NY", "Multiple Locations"]},
                {"company": "Goldman Sachs", "url": "https://www.goldmansachs.com/careers", "locations": ["New York, NY", "Multiple Locations"]},
                {"company": "Morgan Stanley", "url": "https://www.morganstanley.com/people-opportunities", "locations": ["New York, NY", "Multiple Locations"]},
                {"company": "Bank of America", "url": "https://careers.bankofamerica.com", "locations": ["Charlotte, NC", "Multiple Locations"]},
                {"company": "Wells Fargo", "url": "https://www.wellsfargo.com/about/careers", "locations": ["San Francisco, CA", "Multiple Locations"]},
                {"company": "Citigroup", "url": "https://jobs.citi.com", "locations": ["New York, NY", "Multiple Locations"]},
                {"company": "BlackRock", "url": "https://careers.blackrock.com", "locations": ["New York, NY", "Multiple Locations"]},
                {"company": "Visa", "url": "https://www.visa.com/careers", "locations": ["San Francisco, CA", "Multiple Locations"]}
            ]
        },
        'healthcare': {
            'keywords': ['health', 'medical', 'doctor', 'nurse', 'hospital', 'clinical', 'healthcare'],
            'companies': [
                {"company": "Mayo Clinic", "url": "https://jobs.mayoclinic.org", "locations": ["Rochester, MN", "Multiple Locations"]},
                {"company": "Cleveland Clinic", "url": "https://my.clevelandclinic.org/careers", "locations": ["Cleveland, OH", "Multiple Locations"]},
                {"company": "Kaiser Permanente", "url": "https://www.kaiserpermanentejobs.org", "locations": ["Oakland, CA", "Multiple Locations"]},
                {"company": "UnitedHealth Group", "url": "https://careers.unitedhealthgroup.com", "locations": ["Minnetonka, MN", "Multiple Locations"]},
                {"company": "HCA Healthcare", "url": "https://careers.hcahealthcare.com", "locations": ["Nashville, TN", "Multiple Locations"]},
                {"company": "Johnson & Johnson", "url": "https://www.careers.jnj.com", "locations": ["New Brunswick, NJ", "Multiple Locations"]},
                {"company": "Pfizer", "url": "https://careers.pfizer.com", "locations": ["New York, NY", "Multiple Locations"]},
                {"company": "Moderna", "url": "https://www.modernatx.com/careers", "locations": ["Cambridge, MA", "Multiple Locations"]}
            ]
        }
    }
    
    # Find matching category
    matched_category = None
    for category, data in company_categories.items():
        if any(keyword in query_lower for keyword in data['keywords']):
            matched_category = category
            break
    
    # If no specific match, use technology companies as default
    if not matched_category:
        matched_category = 'technology'
    
    companies = company_categories[matched_category]['companies']
    
    # Convert to job listings format with varied locations
    default_jobs = []
    import random
    
    for company in companies:
        location = random.choice(company["locations"])
        default_jobs.append({
            "title": f"{query.title()} Position",
            "company": company["company"],
            "location": location,
            "url": company["url"],
            "source": "Direct"
        })
    
    # Randomize the order of default jobs
    random.shuffle(default_jobs)
    
    # Return only the first 10 jobs
    return default_jobs[:10]

def scrape_jobs(query, location):
    """Scrape jobs from multiple sources and combine results."""
    all_jobs = []
    
    # Scrape from Indeed first
    indeed_jobs = scrape_indeed(query, location)
    if indeed_jobs:
        all_jobs.extend(indeed_jobs)
        print(f"Added {len(indeed_jobs)} jobs from Indeed")
    
    # Try LinkedIn
    linkedin_jobs = scrape_linkedin(query, location)
    if linkedin_jobs:
        all_jobs.extend(linkedin_jobs)
        print(f"Added {len(linkedin_jobs)} jobs from LinkedIn")
    
    # Try Naukri for Indian locations
    if any(indian_city in location.lower() for indian_city in ['delhi', 'bangalore', 'mumbai', 'chennai', 'hyderabad', 'pune', 'kolkata']):
        try:
            naukri_jobs = scrape_naukri(query, location)
            if naukri_jobs:
                all_jobs.extend(naukri_jobs)
                print(f"Added {len(naukri_jobs)} jobs from Naukri")
        except Exception as e:
            print(f"Error scraping Naukri: {str(e)}")
    
    # Try TimesJobs for Indian locations
    if any(indian_city in location.lower() for indian_city in ['delhi', 'bangalore', 'mumbai', 'chennai', 'hyderabad', 'pune', 'kolkata']):
        try:
            timesjobs_jobs = scrape_timesjobs(query, location)
            if timesjobs_jobs:
                all_jobs.extend(timesjobs_jobs)
                print(f"Added {len(timesjobs_jobs)} jobs from TimesJobs")
        except Exception as e:
            print(f"Error scraping TimesJobs: {str(e)}")
    
    # Try Shine for Indian locations
    if any(indian_city in location.lower() for indian_city in ['delhi', 'bangalore', 'mumbai', 'chennai', 'hyderabad', 'pune', 'kolkata']):
        try:
            shine_jobs = scrape_shine(query, location)
            if shine_jobs:
                all_jobs.extend(shine_jobs)
                print(f"Added {len(shine_jobs)} jobs from Shine")
        except Exception as e:
            print(f"Error scraping Shine: {str(e)}")
    
    # If we still don't have enough jobs, add default companies
    if len(all_jobs) < 10:
        default_jobs = get_default_companies(query)
        all_jobs.extend(default_jobs)
        print(f"Added {len(default_jobs)} default company jobs")
    
    # Remove any duplicates that might have slipped through
    unique_jobs = []
    seen = set()
    for job in all_jobs:
        job_key = (job['title'], job['company'])
        if job_key not in seen:
            seen.add(job_key)
            unique_jobs.append(job)
    
    print(f"Final number of unique jobs: {len(unique_jobs)}")
    return unique_jobs

def analyze_jobs(jobs):
    if not jobs:
        return {
            "top_companies": [],
            "total_jobs": 0,
            "message": "No jobs found. Try different search terms."
        }
    
    companies = [job['company'] for job in jobs if job.get('company')]
    top_companies = Counter(companies).most_common(5)
    
    message = "Found the following companies"
    if any(job['source'] == 'Direct' for job in jobs):
        message += " (including suggested companies for direct application)"
    
    return {
        "top_companies": top_companies,
        "total_jobs": len(jobs),
        "message": message
    }

# Update VALID_JOB_CATEGORIES with more comprehensive lists
VALID_JOB_CATEGORIES = {
    'education': [
        'teacher', 'professor', 'instructor', 'tutor', 'lecturer', 'educator',
        'principal', 'dean', 'counselor', 'coordinator', 'administrator', 
        'superintendent', 'assistant teacher', 'head teacher', 'faculty',
        'academic', 'school', 'college', 'university', 'teaching'
    ],
    'healthcare': [
        'doctor', 'nurse', 'physician', 'surgeon', 'therapist', 'pharmacist',
        'dentist', 'pediatrician', 'psychiatrist', 'psychologist', 'medical',
        'healthcare', 'clinical', 'dental', 'veterinary', 'physiotherapist',
        'optometrist', 'radiologist', 'dietitian', 'paramedic'
    ],
    'technology': [
        'software', 'developer', 'engineer', 'programmer', 'analyst',
        'data scientist', 'devops', 'system administrator', 'network',
        'security', 'cloud', 'web', 'frontend', 'backend', 'full stack',
        'mobile', 'qa', 'tester', 'architect', 'database', 'ui/ux'
    ],
    'business': [
        'manager', 'analyst', 'consultant', 'coordinator', 'administrator',
        'supervisor', 'director', 'executive', 'sales', 'marketing',
        'finance', 'accountant', 'hr', 'human resources', 'operations',
        'project manager', 'product manager', 'business analyst', 'ceo',
        'cfo', 'cto', 'team lead', 'head'
    ],
    'skilled_trades': [
        'technician', 'mechanic', 'electrician', 'plumber', 'carpenter',
        'construction', 'welder', 'operator', 'driver', 'chef', 'cook',
        'maintenance', 'repair', 'installer', 'machinist', 'painter',
        'builder', 'contractor', 'fabricator', 'assembler'
    ],
    'service': [
        'customer service', 'support', 'representative', 'cashier', 'retail',
        'server', 'receptionist', 'assistant', 'clerk', 'secretary',
        'hospitality', 'attendant', 'concierge', 'agent', 'specialist'
    ]
}

# Add a list of valid locations
VALID_LOCATIONS = {
    'india': [
        'mumbai', 'delhi', 'bangalore', 'hyderabad', 'chennai', 'kolkata',
        'pune', 'ahmedabad', 'jaipur', 'surat', 'lucknow', 'kanpur',
        'nagpur', 'indore', 'thane', 'bhopal', 'noida', 'gurgaon',
        'gwalior', 'jabalpur', 'bhopal', 'indore', 'raipur', 'bhubaneswar',
        'patna', 'guwahati', 'chandigarh', 'amritsar', 'vadodara', 'coimbatore',
        'kochi', 'visakhapatnam', 'madurai', 'vijayawada', 'varanasi', 'allahabad',
        'ranchi', 'jamshedpur', 'dhanbad', 'bhubaneshwar', 'cuttack', 'siliguri',
        'remote', 'work from home', 'pan india', 'india'
    ],
    'states': [
        'maharashtra', 'delhi', 'karnataka', 'tamil nadu', 'telangana',
        'west bengal', 'gujarat', 'rajasthan', 'uttar pradesh', 'madhya pradesh',
        'bihar', 'andhra pradesh', 'punjab', 'haryana', 'kerala', 'odisha',
        'jharkhand', 'chhattisgarh', 'assam', 'himachal pradesh', 'uttarakhand',
        'goa', 'manipur', 'meghalaya', 'tripura', 'nagaland', 'arunachal pradesh',
        'sikkim', 'mizoram'
    ]
}

def validate_job_title(query):
    """Validate job title and return appropriate error message."""
    if not query:
        return False, "Please enter a job title"
    
    query = query.strip().lower()
    
    # Check for minimum length
    if len(query) < 2:
        return False, "Job title must be at least 2 characters long"
    
    # Check for numbers only
    if query.isdigit():
        return False, "Job title cannot be numbers only"
    
    # Check for special characters only
    if not any(c.isalpha() for c in query):
        return False, "Job title must contain at least one letter"
    
    # Check for common invalid inputs
    invalid_inputs = ['test', 'xyz', 'abc', 'job', 'none', 'nil', 'na', 'n/a']
    if query in invalid_inputs:
        return False, "Please enter a valid job title"
    
    # Check for excessive length
    if len(query) > 50:
        return False, "Job title is too long. Please be more specific"

    # Check for nonsensical input (strings with too many consonants in a row)
    consonants = 'bcdfghjklmnpqrstvwxz'
    vowels = 'aeiou'
    max_consonants_in_row = 3
    consonant_count = 0
    has_vowel = False
    
    for char in query.lower():
        if char in consonants:
            consonant_count += 1
            if consonant_count > max_consonants_in_row:
                return False, f"'{query}' doesn't appear to be a valid job title. Please enter a real job title."
        elif char in vowels:
            has_vowel = True
            consonant_count = 0
        else:
            consonant_count = 0
    
    # Check if the string has at least one vowel
    if not has_vowel:
        return False, f"'{query}' doesn't appear to be a valid job title. Please enter a real job title."
    
    # Check if the input matches any known job categories or common job words
    found_valid_word = False
    for category, words in VALID_JOB_CATEGORIES.items():
        # Check if any word from our valid categories is part of the query
        if any(word in query for word in words):
            found_valid_word = True
            break
    
    if not found_valid_word:
        suggestions = get_job_suggestions(query)[:3]
        suggestion_text = ", ".join(suggestions)
        return False, f"'{query}' doesn't seem to be a valid job title. Try searching for: {suggestion_text}"
    
    return True, query

def validate_location(location):
    """Validate location and return appropriate error message."""
    if not location:
        return False, "Please enter a location"
    
    location = location.strip().lower()
    
    # Check for minimum length
    if len(location) < 2:
        return False, "Location must be at least 2 characters long"
    
    # Check for numbers only
    if location.isdigit():
        return False, "Location cannot be numbers only"
    
    # Check for special characters only
    if not any(c.isalpha() for c in location):
        return False, "Location must contain at least one letter"
    
    # Check for common invalid inputs
    invalid_locations = ['test', 'xyz', 'abc', 'location', 'none', 'nil', 'na', 'n/a']
    if location in invalid_locations:
        return False, "Please enter a valid location"
    
    # Check for excessive length
    if len(location) > 50:
        return False, "Location name is too long. Please be more specific"

    # Check for special characters (except spaces, dots, and hyphens)
    valid_chars = set("abcdefghijklmnopqrstuvwxyz -.")
    if not all(c in valid_chars for c in location):
        return False, "Location contains invalid characters"

    # Check for common remote work terms
    remote_terms = ['remote', 'work from home', 'wfh', 'virtual', 'anywhere']
    if any(term in location for term in remote_terms):
        return True, location

    # Check if location is "india" or "pan india"
    if location in ['india', 'pan india']:
        return True, location

    # Check against valid locations in India
    for region_locations in VALID_LOCATIONS.values():
        if any(valid_loc in location for valid_loc in region_locations):
            return True, location

    # If location doesn't match any known location, suggest alternatives
    suggestions = get_location_suggestions(location)
    suggestion_text = ", ".join(suggestions[:3])
    return False, f"'{location}' doesn't seem to be a valid location. Try: {suggestion_text}"

def get_location_suggestions(location):
    """Get relevant location suggestions based on the input."""
    suggestions = []
    location_lower = location.lower()
    
    # Add major cities and work types
    major_cities = [
        'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai',
        'Kolkata', 'Pune', 'Ahmedabad', 'Jaipur', 'Noida',
        'Gwalior', 'Bhopal', 'Indore', 'Jabalpur', 'Raipur'
    ]
    
    work_types = [
        'Remote', 'Work from Home', 'Pan India', 'Multiple Locations'
    ]
    
    # If location is very short, return popular locations
    if len(location) < 3:
        suggestions.extend(major_cities[:5])
        suggestions.append('Remote')
        return suggestions
    
    # Try to find matching cities using fuzzy matching
    matching_cities = []
    for city in major_cities:
        city_lower = city.lower()
        # Check if query is part of city name or vice versa
        if location_lower in city_lower or city_lower in location_lower:
            matching_cities.append(city)
        # Check for partial matches at word boundaries
        elif any(word in city_lower for word in location_lower.split()):
            matching_cities.append(city)
    
    suggestions.extend(matching_cities[:3])
    
    # Add remote work options if the query seems related
    remote_keywords = ['remote', 'work', 'home', 'anywhere', 'virtual', 'wfh']
    if any(keyword in location_lower for keyword in remote_keywords):
        suggestions.extend(work_types)
    
    # If no matches found, return popular locations
    if not suggestions:
        suggestions.extend(major_cities[:3])
        suggestions.append('Remote')
    
    # Return unique suggestions, limited to 5
    return list(dict.fromkeys(suggestions))[:5]

def filter_jobs(jobs, filters):
    if not filters:
        return jobs

    filtered_jobs = jobs.copy()
    
    # Filter by job type
    if filters.get('jobType'):
        job_type = filters['jobType'].lower()
        filtered_jobs = [
            job for job in filtered_jobs 
            if job_type in job['title'].lower() or job_type in job.get('description', '').lower()
        ]
    
    # Filter by experience level
    if filters.get('experienceLevel'):
        level = filters['experienceLevel'].lower()
        level_keywords = {
            'entry': ['entry', 'junior', 'fresher', 'trainee', 'graduate'],
            'mid': ['mid', 'intermediate', 'experienced', '2-5 years', '3-5 years'],
            'senior': ['senior', 'lead', 'principal', 'architect', '5+ years', '7+ years']
        }
        keywords = level_keywords.get(level, [])
        filtered_jobs = [
            job for job in filtered_jobs 
            if any(keyword in job['title'].lower() or keyword in job.get('description', '').lower() 
                  for keyword in keywords)
        ]
    
    # Filter by date posted (if available in job data)
    if filters.get('datePosted'):
        try:
            days = int(filters['datePosted'])
            current_time = time.time()
            filtered_jobs = [
                job for job in filtered_jobs 
                if job.get('posted_date') and 
                (current_time - job['posted_date']) <= (days * 24 * 60 * 60)
            ]
        except (ValueError, TypeError):
            pass
    
    return filtered_jobs

def filter_jobs_by_location(jobs, requested_location):
    """Filter jobs to ensure they match the requested location."""
    requested_location = requested_location.lower().strip()
    filtered_jobs = []
    
    # Handle remote work cases
    is_remote_search = any(term in requested_location for term in ['remote', 'work from home', 'wfh', 'anywhere'])
    
    for job in jobs:
        job_location = job['location'].lower().strip()
        
        # Check for remote jobs
        if is_remote_search:
            if any(term in job_location for term in ['remote', 'work from home', 'wfh', 'anywhere']):
                filtered_jobs.append(job)
                continue
        
        # Check for exact location match
        if requested_location == job_location:
            filtered_jobs.append(job)
            continue
            
        # Check for partial location matches
        if requested_location in job_location or job_location in requested_location:
            filtered_jobs.append(job)
            continue
            
        # Check for city/state/region matches
        location_parts = requested_location.split(',')
        job_location_parts = job_location.split(',')
        
        # Compare each part of the location
        for req_part in location_parts:
            req_part = req_part.strip()
            for job_part in job_location_parts:
                job_part = job_part.strip()
                if req_part == job_part or req_part in job_part or job_part in req_part:
                    filtered_jobs.append(job)
                    break
            if job in filtered_jobs:
                break
    
    return filtered_jobs

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# Cache for 1 hour
@lru_cache(maxsize=100)
def get_cached_jobs(query, location):
    return None

def save_jobs_to_csv(jobs, query, location):
    """Save job search results to CSV file."""
    csv_file = 'job_search_history.csv'
    file_exists = os.path.exists(csv_file)
    
    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header if file is new
            if not file_exists:
                writer.writerow(['timestamp', 'query', 'location', 'title', 'company', 'job_location', 'url', 'source'])
            
            # Write each job
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for job in jobs:
                writer.writerow([
                    timestamp,
                    query,
                    location,
                    job['title'],
                    job['company'],
                    job['location'],
                    job['url'],
                    job['source']
                ])
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")

def get_jobs_from_csv(query, location):
    """Retrieve job search results from CSV file."""
    csv_file = 'job_search_history.csv'
    if not os.path.exists(csv_file):
        return []
    
    try:
        jobs = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check if this row matches our search criteria
                if (query.lower() in row['query'].lower() and 
                    location.lower() in row['location'].lower()):
                    jobs.append({
                        'title': row['title'],
                        'company': row['company'],
                        'location': row['job_location'],
                        'url': row['url'],
                        'source': row['source']
                    })
        return jobs
    except Exception as e:
        print(f"Error reading from CSV: {str(e)}")
        return []

@app.route('/api/search', methods=['POST'])
def search_jobs():
    """Handle job search requests with improved error handling and validation."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'No search data provided',
                'jobs': []
            }), 400
            
        query = data.get('query', '').strip()
        location = data.get('location', '').strip()
        
        print(f"Received search request - Query: {query}, Location: {location}")
        
        # First, try to get results from CSV
        cached_jobs = get_jobs_from_csv(query, location)
        if cached_jobs:
            print(f"Found {len(cached_jobs)} cached jobs in CSV")
            return jsonify({
                'jobs': cached_jobs,
                'source_breakdown': {'CSV': len(cached_jobs)},
                'total_jobs': len(cached_jobs),
                'message': 'Showing cached results'
            })
        
        # If no cached results, proceed with normal search
        all_jobs = []
        source_breakdown = {
            'Indeed': 0,
            'LinkedIn': 0,
            'Naukri': 0,
            'TimesJobs': 0,
            'Shine': 0,
            'Direct': 0
        }
        errors = []
        
        # Get jobs from all sources
        try:
            all_jobs = scrape_jobs(query, location)
            print(f"Total jobs found: {len(all_jobs)}")
        except Exception as e:
            error_msg = f"Error in job search: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
        
        # If no jobs found, try with broader search terms
        if not all_jobs:
            print("No jobs found, trying with broader search terms")
            broader_query = ' '.join(query.split()[:2])  # Use first two words of query
            try:
                all_jobs = scrape_jobs(broader_query, location)
                print(f"Found {len(all_jobs)} jobs with broader search")
            except Exception as e:
                print(f"Error in broader search: {str(e)}")
        
        # Remove duplicates
        unique_jobs = []
        seen = set()
        for job in all_jobs:
            job_key = (job['title'], job['company'], job['location'])
            if job_key not in seen:
                seen.add(job_key)
                unique_jobs.append(job)
        
        print(f"Final unique jobs count: {len(unique_jobs)}")
        
        # Save results to CSV
        if unique_jobs:
            save_jobs_to_csv(unique_jobs, query, location)
        
        response = {
            'jobs': unique_jobs,
            'source_breakdown': source_breakdown,
            'total_jobs': len(unique_jobs)
        }
        
        if errors:
            response['warnings'] = errors
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in search_jobs: {str(e)}")
        return jsonify({
            'error': 'An error occurred while searching for jobs',
            'jobs': []
        }), 500

def get_job_suggestions(query):
    """Get relevant job suggestions based on the query."""
    query_lower = query.lower()
    
    # Define job categories with keywords and related titles
    job_categories = {
        'education': {
            'keywords': ['teach', 'professor', 'lecturer', 'faculty', 'school', 'college', 'principal'],
            'titles': ['Professor', 'Assistant Professor', 'Lecturer', 'Teacher', 'Principal', 'Academic Coordinator']
        },
        'technology': {
            'keywords': ['develop', 'engineer', 'code', 'program', 'tech', 'software'],
            'titles': ['Software Engineer', 'Developer', 'System Administrator', 'Data Scientist', 'DevOps Engineer']
        },
        'business': {
            'keywords': ['manage', 'business', 'market', 'sales', 'finance', 'account'],
            'titles': ['Business Analyst', 'Project Manager', 'Marketing Manager', 'Financial Analyst', 'Account Manager']
        },
        'healthcare': {
            'keywords': ['doctor', 'nurse', 'health', 'medical', 'clinic', 'hospital'],
            'titles': ['Doctor', 'Nurse', 'Healthcare Specialist', 'Medical Officer', 'Clinical Coordinator']
        }
    }
    
    # Find matching category
    for category, data in job_categories.items():
        if any(keyword in query_lower for keyword in data['keywords']):
            return data['titles']
    
    # If no specific match, return general suggestions
    return ['Software Engineer', 'Project Manager', 'Business Analyst', 'Teacher', 'Sales Manager']

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file using PyPDF2."""
    try:
        # Create a temporary file to store the uploaded PDF
        temp_path = os.path.join(os.path.dirname(__file__), 'temp.pdf')
        pdf_file.save(temp_path)
        
        # Read the PDF
        reader = PdfReader(temp_path)
        text = ""
        
        # Extract text from each page
        for page in reader.pages:
            text += page.extract_text() or ""
        
        # Clean up the temporary file
        os.remove(temp_path)
        
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def extract_skills(text):
    """Extract skills from text using regex patterns and predefined skill sets."""
    if not text:
        return []
        
    # Convert text to lowercase for better matching
    text = text.lower()
    
    # Initialize skills set
    found_skills = set()
    
    # Check for technical skills from predefined list
    for category, skills in TECHNICAL_SKILLS.items():
        for skill in skills:
            if skill in text:
                found_skills.add(skill)
    
    # Use regex patterns to find additional skills
    for pattern in SKILL_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            skill = match.group(1).strip().lower()
            # Only add if it's a reasonable length and not just a single word
            if 2 <= len(skill.split()) <= 4:
                found_skills.add(skill)
    
    # Clean up the skills
    cleaned_skills = set()
    for skill in found_skills:
        # Remove common words that might have been caught
        if skill not in ['and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by']:
            cleaned_skills.add(skill)
    
    return list(cleaned_skills)

def calculate_job_match(skills, job_description):
    """Calculate match score between skills and job description."""
    if not job_description:
        return 0
        
    job_skills = extract_skills(job_description)
    if not job_skills:
        return 0
    
    # Calculate match score
    matching_skills = set(skills) & set(job_skills)
    match_score = (len(matching_skills) / len(job_skills)) * 100
    
    return round(match_score, 1)

@app.route('/api/analyze-cv', methods=['POST'])
def analyze_cv():
    """Endpoint to analyze uploaded CV and recommend jobs."""
    if 'cv' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['cv']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(file)
        if not text:
            return jsonify({'error': 'Could not extract text from PDF'}), 400
        
        # Extract skills
        skills = extract_skills(text)
        
        # Get location from request if provided, otherwise use default
        location = request.form.get('location', 'Remote')
        
        # Search for jobs using the extracted skills
        all_jobs = []
        for skill in skills[:5]:  # Use top 5 skills for job search
            try:
                # Search Indeed
                indeed_jobs = scrape_indeed(skill, location)
                if indeed_jobs:
                    all_jobs.extend(indeed_jobs)
                
                # Search LinkedIn
                linkedin_jobs = scrape_linkedin(skill, location)
                if linkedin_jobs:
                    all_jobs.extend(linkedin_jobs)
            except Exception as e:
                print(f"Error searching jobs for skill {skill}: {str(e)}")
                continue
        
        # If no jobs found from scrapers, use default companies
        if not all_jobs:
            default_jobs = get_default_companies(skills[0] if skills else 'software engineer')
            all_jobs.extend(default_jobs)
        
        # Remove duplicates
        unique_jobs = []
        seen = set()
        for job in all_jobs:
            job_key = (job['title'], job['company'])
            if job_key not in seen:
                seen.add(job_key)
                unique_jobs.append(job)
        
        # Calculate match scores for each job
        recommended_jobs = []
        for job in unique_jobs:
            # Create a job description from title and company
            job_description = f"{job['title']} {job['company']}"
            match_score = calculate_job_match(skills, job_description)
            if match_score > 0:
                job['match_score'] = match_score
                recommended_jobs.append(job)
        
        # Sort jobs by match score
        recommended_jobs.sort(key=lambda x: x['match_score'], reverse=True)
        
        # Prepare response
        response = {
            'skills': skills,
            'recommended_jobs': recommended_jobs[:10],  # Return top 10 matches
            'total_jobs': len(recommended_jobs),
            'message': f'Found {len(recommended_jobs)} matching jobs based on your skills'
        }
        
        if not recommended_jobs:
            response['message'] = 'No matching jobs found. Try searching with different skills or location.'
            response['location_suggestions'] = get_location_suggestions(location)
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error analyzing CV: {str(e)}")
        return jsonify({'error': 'Error analyzing CV'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)