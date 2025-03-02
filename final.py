import requests
from fake_useragent import UserAgent
import plotly.express as px
from collections import Counter
import re
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc
import time
import random
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urlencode
import plotly.express as px
import logging
#import fitz  # PyMuPDF
import google.generativeai as genai
from docxtpl import DocxTemplate
import re
import json

# Configure Gemini API
genai.configure(api_key="AIzaSyAYIht3IahoIqQIBSJitwAbeDu0d0Uugag")
model = genai.GenerativeModel("gemini-1.5-flash")


# Initialize UserAgent
ua = UserAgent()

# Configuration
MAX_JOBS = 50  # Safety limit for scraping
SKILLS_LIST = ['python', 'sql', 'aws', 'spark', 'machine learning', 'tensorflow',
               'pytorch', 'docker', 'kubernetes', 'azure', 'big data', 'nlp', 'tableau']
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'job_search'

if 'selected_job_description' not in st.session_state:
    st.session_state.selected_job_description = ''

# Custom CSS
st.markdown("""
<style>
    .job-card {
        padding: 20px;
        margin: 15px 0;
        border-radius: 15px;
        border: 1px solid #e0e0e0;
        transition: all 0.3s ease;
        background: white;
    }
    .job-card:hover {
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transform: translateY(-3px);
    }
    .salary-badge {
        background: #4CAF50;
        color: white;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8em;
    }
    .skill-chip {
        background: #2196F3;
        color: white;
        padding: 2px 8px;
        border-radius: 15px;
        font-size: 0.8em;
        margin: 2px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


# Function to extract text from a PDF file
def read_resume(file_path):
    with fitz.open(file_path) as doc:
        text = "\n".join([page.get_text() for page in doc])
    return text


# Function to extract resume keywords
def extract_resume_keywords(resume_text):
    prompt = f"""
    Analyze the following resume and extract key skills, technologies, and experience.

    Resume:
    {resume_text}
    """
    response = model.generate_content(prompt)
    return response.text


# Function to match resume to job description
def match_resume_to_job(resume_text, job_description):
    prompt = f"""
    Compare the following resume with the job description.
    Return a match percentage and areas of improvement.

    Resume:
    {resume_text}

    Job Description:
    {job_description}

    Output in JSON format:
    - Match Percentage
    - Key Strengths
    - Areas to Improve
    """
    response = model.generate_content(prompt)
    return response.text


# Function to update resume
def update_resume(resume_text, job_description):
    prompt = f""" 
    Improve the following resume to better match the job description by emphasizing relevant skills and experience, ensuring the updated section is concise, relevant, and ATS-friendly.
    Keep it professional and well-structured. Do not provide any additional advice, explanations, or changes to other parts of the resume.

    Resume:
    {resume_text}

    Job Description:
    {job_description}

    Updated Resume:
    """
    response = model.generate_content(prompt)
    return response.text


# Function to clean resume text
def clean_resume_text(text):
    text = re.sub(r'\n\s*\n+', '\n\n', text.strip())
    text = re.sub(r'(?<=\w)\n(?=\w)', ' ', text)
    return text


# Function to parse resume with Gemini
def parse_resume_with_gemini(resume_text):
    prompt = f"""
    Extract the following details from the resume text below and return them in JSON format:
    - name
    - post
    - contact_info (email, phone, location, linkedin)
    - summary
    - skills (comma-separated list)
    - projects (list of project titles and descriptions)
    - experience (list of dictionaries with keys: place, role, brief, duration)
    - education (duration, university, degree, gpa)

    Return only the JSON object. Do not include any additional text or explanations.

    Resume Text:
    {resume_text}
    """
    response = model.generate_content(prompt)
    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if not json_match:
        st.error("Error: No JSON found in the response.")
        return None
    json_str = json_match.group(0)
    try:
        user_data = json.loads(json_str)
        return user_data
    except json.JSONDecodeError as e:
        st.error(f"Error: Invalid JSON returned by Gemini. Details: {e}")
        return None


# Function to update resume document
def update_resume_doc(template_path, output_path, user_data):
    doc = DocxTemplate(template_path)
    for paragraph in doc.render():
        if "[NAME]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[NAME]", user_data.get("name", ""))
        if "[POST]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[POST]", user_data.get("post", ""))
        if "[PHONE NUMBER]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[PHONE NUMBER]",
                                                    user_data.get("contact_info", {}).get("phone", ""))
        if "[EMAIL ADDRESS]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[EMAIL ADDRESS]",
                                                    user_data.get("contact_info", {}).get("email", ""))
        if "[LOCATION]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[LOCATION]", user_data.get("contact_info", {}).get("location", ""))
        if "[LINKED IN]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[LINKED IN]",
                                                    str(user_data.get("contact_info", {}).get("linkedin", "")))
        if "[summary]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[summary]", user_data.get("summary", ""))
        if "[skills]" in paragraph.text:
            paragraph.text = paragraph.text.replace("[skills]", user_data.get("skills", ""))
    education = user_data.get("education", {})
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if "[duration]" in cell.text:
                    cell.text = cell.text.replace("[duration]", education.get("duration", ""))
                if "[UNIVERSITY]" in cell.text:
                    cell.text = cell.text.replace("[UNIVERSITY]", education.get("university", ""))
                if "[Degree]" in cell.text:
                    cell.text = cell.text.replace("[Degree]", education.get("degree", ""))
                if "[GPA]" in cell.text:
                    gpa = education.get("gpa", "")
                    if gpa:
                        cell.text = cell.text.replace("[GPA]", f"GPA: {gpa}")
                    else:
                        cell.text = cell.text.replace("GPA: [GPA]", "")
    projects = user_data.get("projects", [])
    for i, project in enumerate(projects, start=1):
        for paragraph in doc.add_paragraphs:
            if f"[PROJECT_TITLE_{i}]" in paragraph.text:
                paragraph.text = paragraph.text.replace(f"[PROJECT_TITLE_{i}]",
                                                        project.get("title", "Untitled Project"))
            if f"[PROJECT_DESCRIPTION_{i}]" in paragraph.text:
                paragraph.text = paragraph.text.replace(f"[PROJECT_DESCRIPTION_{i}]",
                                                        project.get("description", "No description available."))
    experiences = user_data.get("experience", [])
    for table in doc.tables:
        for i, row in enumerate(table.rows):
            if i >= len(experiences):
                break
            exp = experiences[i]
            for cell in row.cells:
                if f"[Place {i + 1}]" in cell.text:
                    cell.text = cell.text.replace(f"[Place {i + 1}]", exp.get("place", "No place available."))
                if f"[ROLE_{i + 1}]" in cell.text:
                    cell.text = cell.text.replace(f"[ROLE_{i + 1}]", exp.get("role", "No role available."))
                if f"[duration {i + 1}]" in cell.text:
                    cell.text = cell.text.replace(f"[duration {i + 1}]", exp.get("duration", "No duration available."))
                if f"[EXPERIENCE BRIEF {i + 1}]" in cell.text:
                    cell.text = cell.text.replace(f"[EXPERIENCE BRIEF {i + 1}]",
                                                  exp.get("brief", "No description available."))
    doc.save(output_path)

def get_job_criteria(job_soup):
    criteria = {}
    items = job_soup.find_all('li', class_='description__job-criteria-item')
    for item in items:
        try:
            key = item.find('h3').get_text(strip=True).replace(' ', '_').lower()
            value = item.find('span').get_text(strip=True)
            criteria[key] = value
        except AttributeError:
            continue
    return criteria


def scrape_linkedin_job_page(job_id):
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        response = requests.get(
            url,
            headers={'User-Agent': ua.random},
            timeout=10
        )
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        job_data = {
            'job_id': job_id,
            'title': soup.find('h2', class_='top-card-layout__title').get_text(strip=True) if soup.find('h2',
                                                                                                        class_='top-card-layout__title') else None,
            'company': soup.find('a', class_='topcard__org-name-link').get_text(strip=True) if soup.find('a',
                                                                                                         class_='topcard__org-name-link') else None,
            'location': soup.find('span', class_='topcard__flavor--bullet').get_text(strip=True) if soup.find('span',
                                                                                                              class_='topcard__flavor--bullet') else None,
            'posted': soup.find('span', class_='posted-time-ago__text').get_text(strip=True) if soup.find('span',
                                                                                                          class_='posted-time-ago__text') else None,
            'applicants': soup.find('span', class_='num-applicants__caption').get_text(strip=True) if soup.find('span',
                                                                                                                class_='num-applicants__caption') else None,
            'url': f"https://www.linkedin.com/jobs/view/{job_id}",
        }

        description_div = soup.find('div', class_='show-more-less-html__markup')
        if description_div:
            job_data['description'] = '\n'.join([p.get_text(strip=True) for p in description_div.find_all('p')])

            job_data.update(get_job_criteria(soup))

        return job_data

    except Exception as e:
        return None


def extract_salary(description):
    patterns = [
        r'\$[\d,]+(?:\.\d+)?\s*[-–to]+\s*\$[\d,]+(?:\.\d+)?',
        r'\$\d+[kK]-\$\d+[kK]',
        r'[A-Z][a-z]+ \$\d+,\d+',
        r'\d+-\d+ (?:years|yrs) experience'
    ]

    salaries = []
    for pattern in patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        salaries.extend(matches)

    return salaries[:2] if salaries else None


def analyze_skills(description):
    if not description:
        return []
    description = description.lower()
    return [skill for skill in SKILLS_LIST if skill in description]


def create_company_analysis(df):
    company_counts = df['company'].value_counts().reset_index()
    company_counts.columns = ['Company', 'Job Count']
    fig = px.bar(company_counts.head(10),
                 x='Company', y='Job Count',
                 title='Top Hiring Companies')
    return fig


def create_geo_distribution(df):
    loc_counts = df['location'].value_counts().reset_index()
    loc_counts.columns = ['Location', 'Count']
    fig = px.treemap(loc_counts, path=['Location'], values='Count',
                     title='Job Distribution by Location')
    return fig


def create_skill_wordcloud(df):
    all_skills = ' '.join([' '.join(skills) for skills in df['skills'].dropna()])
    wordcloud = WordCloud(width=800, height=400).generate(all_skills)
    fig, ax = plt.subplots()
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    return fig


def linkedin_interface():
    st.header("LinkedIn Jobs Search")

    if 'saved_jobs' not in st.session_state:
        st.session_state.saved_jobs = {}

    with st.sidebar.expander("🔍 LinkedIn Filters", expanded=True):
        with st.form(key='linkedin_search_form'):
            col1, col2 = st.columns(2)
            with col1:
                keywords = st.text_input("Job Title/Keywords")
                location = st.text_input("Location")
                remote = st.selectbox("Remote", ["All", "Remote", "On-site"])

            with col2:
                experience_level = st.selectbox("Experience", [
                    'All', 'Entry', 'Mid', 'Senior', 'Executive'
                ])
                job_type = st.selectbox("Type", [
                    'All', 'Full-time', 'Part-time', 'Contract', 'Temporary'
                ])

            time_posted = st.select_slider("Posted Within",
                                           options=['24h', '1w', '1m', 'Any'])
            pages = st.slider("Pages to Scan", 1, 5, 2)

            submitted = st.form_submit_button("Start LinkedIn Search")

    if submitted:
        with st.spinner("🕵️ Scanning LinkedIn for opportunities..."):
            jobs_data = []
            job_ids = []

            time_map = {
                '24h': 'r86400',
                '1w': 'r604800',
                '1m': 'r2592000',
                'Any': ''
            }

            experience_map = {
                'Entry': '2',
                'Mid': '3',
                'Senior': '4',
                'Executive': '5',
                'All': ''
            }

            job_type_map = {
                'Full-time': 'F',
                'Part-time': 'P',
                'Contract': 'C',
                'Temporary': 'T',
                'All': ''
            }

            for page in range(pages):
                try:
                    params = {
                        "keywords": keywords,
                        "location": location,
                        "start": page * 25,
                        "f_WT": "1" if remote == "Remote" else "2",
                        "f_E": experience_map.get(experience_level, ''),
                        "f_JT": job_type_map.get(job_type, ''),
                        "f_TPR": time_map.get(time_posted, '')
                    }

                    response = requests.get(
                        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                        params=params,
                        headers={'User-Agent': ua.random},
                        timeout=10
                    )

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        jobs = soup.find_all('li')
                        for job in jobs:
                            if job_id := job.find('div', {'class': 'base-card'}).get('data-entity-urn', '').split(':')[
                                -1]:
                                job_ids.append(job_id)
                        time.sleep(random.uniform(1, 3))

                except Exception as e:
                    st.error(f"Error fetching page {page + 1}: {str(e)}")
                    continue

            progress_bar = st.progress(0)
            total_jobs = len(job_ids[:MAX_JOBS])

            for i, job_id in enumerate(job_ids[:MAX_JOBS]):
                try:
                    job_info = scrape_linkedin_job_page(job_id)
                    if job_info:
                        jobs_data.append(job_info)
                    progress_bar.progress((i + 1) / total_jobs)
                    time.sleep(random.uniform(1, 2))
                except Exception as e:
                    st.error(f"Error scraping job {job_id}: {str(e)}")
                    continue

        if jobs_data:
            df = pd.DataFrame(jobs_data)
            df['salary'] = df['description'].apply(extract_salary)
            df['skills'] = df['description'].apply(analyze_skills)
            st.session_state.linkedin_jobs_data = df.to_dict('records')
            tab1, tab2 = st.tabs(["Job Listings", "Market Insights"])

            with tab1:
                for _, job in df.iterrows():
                    job = job.to_dict()
                    job_id = job['job_id']
                    with st.container():
                        st.markdown(f"""
                        <div class="job-card">
                        <div class="job-title">{job['title']}</div>
                        <div class="company-name">{job['company']}</div>
                        <div style="margin: 5px 0; color: #666;">
                            📍 {job['location']}
                            <span class="separator">•</span>
                            🕒 {job.get('posted', 'N/A')}
                            <span class="separator">•</span>
                            👥 {job.get('applicants', 'N/A')}
                        </div>
                        <div style="margin: 10px 0;">
                            #{" ".join([f"<span class='skill-chip'>{skill}</span>" for skill in job.get('skills', [])[:5]])}
                            {f"<span class='tag'>{job.get('seniority_level', '')}</span>" if job.get('seniority_level') else ""}
                            {f"<span class='tag'>{job.get('employment_type', '')}</span>" if job.get('employment_type') else ""}
                        </div>
                        <a href="{job['url']}" target="_blank" style="text-decoration: none;">
                            <button style="margin-top: 10px; background-color: #0a66c2; color: white; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer;">
                                View Job ➔
                            </button>
                        </a>
                        <button class="update-resume-btn" 
                                onclick="window.streamlit.setComponentValue('update_resume_{job_id}')">
                                Update Resume ✍️
                            </button>
                    </div>
                        """, unsafe_allow_html=True)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name='linkedin_jobs.csv',
                    mime='text/csv'
                )

            with tab2:
                st.header("Market Intelligence Dashboard")
                col1, col2 = st.columns(2)

                with col1:
                    st.plotly_chart(create_company_analysis(df), use_container_width=True)
                    st.plotly_chart(create_geo_distribution(df), use_container_width=True)

                with col2:
                    st.pyplot(create_skill_wordcloud(df))
                    exp_levels = df['seniority_level'].value_counts()
                    fig = px.pie(exp_levels, values=exp_levels.values,
                                 names=exp_levels.index, title='Experience Level Distribution')
                    st.plotly_chart(fig, use_container_width=True)

        else:
            st.warning("No jobs found with these filters. Try different parameters.")

logging.basicConfig(filename="app_errors.log", level=logging.ERROR)

def get_driver():
    """Configure undetectable Chrome driver"""
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(100, 120)}.0.0.0 Safari/537.36")
    options.add_argument("--window-size=1920,1080")

    driver = uc.Chrome(use_subprocess=True,options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def human_interaction(driver):
    """Safer human-like behavior simulation"""
    try:
        # Get window size first
        window_size = driver.execute_script("return [window.innerWidth, window.innerHeight];")
        max_x = window_size[0] - 50
        max_y = window_size[1] - 50

        actions = ActionChains(driver)

        # Start from center position
        start_x = max_x // 2
        start_y = max_y // 2
        actions.move_by_offset(start_x, start_y).perform()
        time.sleep(0.5)

        # Safer mouse movements
        for _ in range(random.randint(2, 3)):
            try:
                # Generate safe offsets
                x_offset = random.randint(-50, 50)
                y_offset = random.randint(-50, 50)

                # Check boundaries
                new_x = start_x + x_offset
                new_y = start_y + y_offset

                if 0 <= new_x <= max_x and 0 <= new_y <= max_y:
                    actions.move_by_offset(x_offset, y_offset).perform()
                    time.sleep(random.uniform(0.1, 0.3))

            except Exception as e:
                print(f"Ignored mouse movement error: {str(e)}")
                continue

        # Safer scrolling
        for _ in range(random.randint(1, 2)):
            try:
                scroll_amount = random.randint(200, 500)
                driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
                time.sleep(random.uniform(0.5, 1))
            except Exception as e:
                print(f"Ignored scrolling error: {str(e)}")
                continue

    except Exception as e:
        print(f"Ignored interaction error: {str(e)}")


def get_job_details(driver, job_card):
    """Scrape detailed job information"""
    details = {
        'job_id': '',
        'title': '',
        'company': '',
        'location': '',
        'salary': '',
        'posted': '',
        'job_url': '',
        'company_rating': '',
        'job_type': '',
        'shift': '',
        'benefits': '',
        'is_remote': False,
        'is_urgent': False,
        'job_snippet': '',
        'experience_level': '',
        'work_model': 'On-site',
        'image_link': '',
        'apply_link': '',
    }
    try:
        job_link = job_card.find('a', class_='jcs-JobTitle')
        if job_link:
            details['job_id'] = job_link.get('data-jk', '')
            details['job_url'] = f"https://in.indeed.com/viewjob?jk={details['job_id']}"
            details['title'] = job_link.get_text(strip=True)

        driver.get(details['job_url'])
        time.sleep(random.uniform(3, 6))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        details['company'] = soup.find("meta", {"property": "og:description"})["content"] if soup.find("meta", {
            "property": "og:description"}) else None
        details['location'] = soup.find("title").text.split(" - ")[1] if soup.find("title") else None
        details['image_link'] = soup.find("meta", {"property": "og:image"})["content"] if soup.find("meta", {
            "property": "og:image"}) else None

        # Extract remote status
        details['is_remote'] = bool(soup.find('div', class_='remote-badge'))

        job_description = soup.find("div", class_="jobsearch-JobComponent-description")
        details['job_snippet'] = job_description.get_text(strip=True) if job_description else "Not Provided"

        pay_tag = soup.find(string=lambda text: "₹" in text if text else False)
        details['salary'] = pay_tag.strip() if pay_tag else "Not mentioned"

        job_type_options = ["Full-time", "Part-time", "Internship", "Permanent", "Contract"]
        job_types = [jt for jt in job_type_options if soup.find(string=jt)]
        details['job_type'] = ", ".join(job_types) if job_types else "Not mentioned"

        shift_options = ["Day shift", "Night shift", "Rotational shift", "Fixed shift"]
        shifts = [s for s in shift_options if soup.find(string=s)]
        details['shift'] = ", ".join(shifts) if shifts else "Not mentioned"

        benefits_header = soup.find(string=lambda text: "Benefits" in text if text else False)
        details['benefits'] = benefits_header.find_next("ul").text if benefits_header else "Not mentioned"

        apply_link_meta = soup.find("meta", {"property": "og:url"})
        details['apply_link'] = apply_link_meta["content"] if apply_link_meta else "Not found"

    except Exception as e:
        logging.error(f"Error occurred: {str(e)}", exc_info=True)
    return details



def indeed_interface():
    st.header("Indeed Jobs Search")
    if 'jobs_data' not in st.session_state:
        st.session_state.jobs_data = []

    with st.sidebar.expander("🔍 Indeed Filters", expanded=True):
        with st.form(key='indeed_search_form'):
            col1, col2 = st.columns(2)
            job_title = st.text_input("Job Title", "Data Scientist")
            location = st.text_input("Location", "India")
            experience = st.selectbox("Experience Level", ["Any", "Entry", "Mid", "Senior"])
            job_type = st.selectbox("Job Type", ["Any", "Full-time", "Part-time", "Contract", "Internship"])
            remote_only = st.checkbox("Remote Only")
            days_old = st.slider("Posted within (days)", 1, 30, 7)
            pages = st.slider("Pages to scrape", 1, 10, 3)

            if st.form_submit_button("Start Search"):
                st.session_state.run_scraping = True
    if st.session_state.get('run_scraping'):
        driver = get_driver()
        progress_bar = st.progress(0)
        status_text = st.empty()
        job_listings = []
        try:
            params = {
                "q": job_title,
                "l": location,
                "fromage": days_old,
                "jt": job_type.lower() if job_type != "Any" else "",
                "explvl": experience.lower() if experience != "Any" else "",
                "sc": "0kf:attr(DSQF7)" if remote_only else ""
            }

            total_jobs = 0
            for page in range(pages):
                status_text.text(f"📃 Scraping page {page + 1}/{pages}...")
                current_params = params.copy()
                current_params["start"] = page * 10

                search_url = f"https://in.indeed.com/jobs?{urlencode(current_params)}"
                driver.get(search_url)
                time.sleep(random.uniform(3, 5))
                human_interaction(driver)
                time.sleep(random.uniform(2, 4))
                # Extract job links
                soup = BeautifulSoup(driver.page_source, "html.parser")
                job_cards = soup.find_all('div', class_='job_seen_beacon')

                # Scrape individual jobs
                for i, card in enumerate(job_cards):
                    job = get_job_details(driver, card)
                    if job:
                        st.session_state.jobs_data.append(job)
                        progress = ((page * len(job_cards)) + i + 1) / (pages * len(job_cards))
                        progress_bar.progress(progress)

                    time.sleep(random.uniform(1, 3))

                time.sleep(random.uniform(5, 8))

            st.success(f"✅ Found {len(st.session_state.jobs_data)} jobs!")

        except Exception as e:
            st.error(f"Scraping failed: {str(e)}")
        finally:
            driver.quit()
            st.session_state.run_scraping = False

    # Display results
    if st.session_state.jobs_data:
        st.header("Job Listings")

        # Job cards
        for job in st.session_state.jobs_data:
            st.markdown(f"""
            <div class="job-card">
                <h3>{job['title']}</h3>
                <div style="margin-bottom: 12px;">
                    <strong>{job['company']}</strong> • {job['location']}
                    <span class="tag">{job['is_remote']}</span>
                    <span class="tag">{job['job_type']}</span>
                </div>
                <div style="margin-bottom: 12px;" class="salary">
                    {job['salary']}
                </div>
                <p>{job['job_snippet']}</p>
                <div style="margin-top: 12px;">
                    {''.join([f'<span class="tag">{benefit}</span>'
                              for benefit in job['benefits'].split(', ')][:5])}
                </div>
                <a href="{job['job_url']}" target="_blank" style="text-decoration: none;">
                    <button style="margin-top: 10px; background: #1565c0; color: white; 
                              border: none; padding: 8px 20px; border-radius: 20px;">
                        View Job ➔
                    </button>
                </a>
                <button class="update-resume-btn" 
                onclick="window.streamlit.setComponentValue('update_resume_{job['job_id']}')">
            Update Resume ✍️
        </button>
            </div>
            """, unsafe_allow_html=True)

        # Analysis section
        st.header("Market Insights")
        df = pd.DataFrame(st.session_state.jobs_data)

        col1, col2 = st.columns(2)
        with col1:
            # Company distribution
            company_counts = df['company'].value_counts().reset_index()
            fig = px.bar(company_counts.head(10),
                         x='company', y='count',
                         title='Top Hiring Companies')
            st.plotly_chart(fig)

        with col2:
            # Salary distribution
            salary_df = df[df['salary'] != 'Not disclosed']
            if not salary_df.empty:
                fig = px.pie(salary_df, names='salary', title='Salary Distribution')
                st.plotly_chart(fig)

        # Download button
        csv = df.to_csv(index=False).encode()
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="indeed_jobs.csv",
            mime="text/csv"
        )

# Function to handle resume analysis and updating
def resume_updater_interface():
    st.title("AI Resume Updater")

    if st.button("← Back to Job Search"):
        st.session_state.current_page = 'job_search'

    st.subheader("Job Description Being Targeted")
    st.write(st.session_state.selected_job_description)

    uploaded_file = st.file_uploader("Upload Your Resume (PDF)", type="pdf")

    if uploaded_file is not None:
        resume_text = read_resume(uploaded_file)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Analyze Resume Match"):
                analysis = match_resume_to_job(
                    resume_text,
                    st.session_state.selected_job_description
                )
                st.subheader("Match Analysis")
                st.write(analysis)

        with col2:
            if st.button("Generate Enhanced Resume"):
                enhanced_resume = update_resume(
                    resume_text,
                    st.session_state.selected_job_description
                )
                st.subheader("Enhanced Resume")
                st.write(clean_resume_text(enhanced_resume))

                # Generate downloadable Word doc
                user_data = parse_resume_with_gemini(enhanced_resume)
                if user_data:
                    update_resume_doc("template.docx", "enhanced_resume.docx", user_data)
                    with open("enhanced_resume.docx", "rb") as f:
                        st.download_button(
                            label="📥 Download Enhanced Resume",
                            data=f,
                            file_name="enhanced_resume.docx",
                            mime="application/octet-stream"
                        )
def main():
    #st.set_page_config(page_title="Smart Job Finder", layout="wide")

    # Handle resume update triggers from job cards
    for key in st.session_state:
        if key.startswith('update_resume_'):
            job_id = key.split('_')[-1]
            # Check Indeed jobs
            job = next((j for j in st.session_state.get('jobs_data', []) if j.get('job_id') == job_id), None)
            if not job:
                # Check LinkedIn jobs
                job = next((j for j in st.session_state.get('linkedin_jobs_data', []) if j.get('job_id') == job_id),
                           None)
            if job:
                st.session_state.selected_job_description = job.get('description', '')
                st.session_state.current_page = 'resume_updater'
                break

    if st.session_state.current_page == 'job_search':
        st.title("🚀 Smart Job Finder")
        st.sidebar.title("Platform Selection")
        platform = st.sidebar.radio("Choose platform:", ("LinkedIn", "Indeed"))

        if platform == "LinkedIn":
            linkedin_interface()
        else:
            indeed_interface()

   # elif st.session_state.current_page == 'resume_updater':
      #  resume_updater_interface()

if __name__ == "__main__":
    main()
