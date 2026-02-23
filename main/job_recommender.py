"""
Job Recommendation Engine
Matches job seekers with opportunities using semantic and keyword-based matching
with domain-specific filtering.
"""

import re
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
import os
import django
from sklearn.preprocessing import MinMaxScaler


# ============================================================================
# CONFIGURATION
# ============================================================================

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "job_recommendation",
    "user": "postgres",
    "password": "2003"
}

IT_KEYWORDS = {
    'python', 'java', 'javascript', 'typescript', 'golang', 'rust', 'c#', 'cpp',
    'csharp', 'php', 'ruby', 'scala', 'kotlin', 'swift', 'objective-c', 'dart',
    'elixir', 'clojure', 'r programming', 'matlab', 'perl', 'bash',
    'react', 'vue', 'angular', 'nodejs', 'express', 'django', 'flask', 'fastapi',
    'spring', 'hibernate', 'html', 'css', 'sass', 'webpack', 'babel', 'graphql',
    'rest api', 'websocket', 'html5', 'jquery',
    'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'cassandra',
    'dynamodb', 'firestore', 'oracle', 'mssql', 'sqlite', 'mariadb',
    'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'ansible',
    'jenkins', 'gitlab', 'github', 'circleci', 'travisci', 'cloudformation',
    'ec2', 'lambda', 's3', 'rds', 'gke', 'aks', 'appengine',
    'git', 'linux', 'unix', 'windows', 'macos', 'api', 'microservices',
    'machine learning', 'deep learning', 'ai', 'nltk', 'pytorch', 'tensorflow',
    'scikit-learn', 'pandas', 'numpy', 'data science', 'big data', 'spark',
    'hadoop', 'hive', 'presto', 'agile', 'scrum', 'jira', 'ci/cd',
    'devops', 'infrastructure', 'cloud', 'backend', 'frontend', 'fullstack',
    'database', 'server', 'deployment', 'debugging',
    'graphql api', 'typescript react', 'nextjs', 'nuxtjs', 'svelte', 'nestjs', 'spring boot',
    'quarkus', 'micronaut', 'flutter', 'unity', 'unreal engine', 'godot', 'tensorflow lite',
    'keras', 'opencv', 'fastai', 'huggingface', 'transformers', 'reinforcement learning',
    'computer vision', 'nlp', 'docker compose', 'helm', 'terraform cloud', 'ansible tower',
    'prometheus', 'grafana', 'elk stack', 'logstash', 'kibana', 'splunk', 'new relic',
    'datadog', 'aws lambda edge', 'cloudfront', 'sns', 'sqs', 'ecs', 'eks', 'eksctl', 
    'gke autopilot', 'cloud run', 'azure functions', 'logic apps', 'event hub', 'service bus', 
    'rabbitmq', 'kafka', 'spark streaming', 'databricks', 'airflow dag', 'prefect', 'luigi',
    'pyspark', 'scala spark', 'hbase', 'zeppelin', 'mlflow', 'dvc', 'fastapi jwt', 'oauth2',
    'openid connect', 'jwt', 'saml', 'keycloak', 'hashicorp vault', 'consul', 'nomad', 'packer',
    'vagrant', 'ci/cd pipeline', 'circleci config', 'github actions workflow', 'travis yaml',
    'bitbucket pipeline', 'jenkinsfile', 'sonarqube', 'codecov', 'pytest', 'unittest', 'jest',
    'mocha', 'chai', 'cypress', 'selenium', 'playwright', 'puppeteer', 'postman', 'swagger',
    'openapi', 'raml', 'graphql playground', 'apollo', 'relay', 'react native', 'electron',
    'capacitor', 'cordova', 'pwa', 'service worker', 'webassembly', 'wasm', 'edge computing', 
    'serverless', 'event-driven', 'microfrontend', 'cqrs', 'event sourcing', 'design patterns',
    'clean architecture', 'hexagonal architecture', 'tdd', 'bdd', 'mocking', 'stubbing', 
    'feature flag', 'canary deployment', 'blue green deployment'
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def detect_resume_sections(text):
    """Extract sections from resume text."""
    sections = {
        "profile": "", "experience": "", "skills": "", "projects": "",
        "education": "", "certificates": "", "other": ""
    }
    
    current = "other"
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    headings = {
        "profile": ["PROFILE", "SUMMARY", "ABOUT"],
        "experience": ["PROFESSIONAL EXPERIENCE", "WORK EXPERIENCE", "EXPERIENCE"],
        "skills": ["TECHNICAL SKILLS", "SKILLS"],
        "projects": ["PROJECTS"],
        "education": ["EDUCATION"],
        "certificates": ["CERTIFICATES", "CERTIFICATIONS"]
    }
    
    for line in lines:
        l_clean = line.upper().strip()
        found_heading = False
        
        for section, keys in headings.items():
            if l_clean in keys:
                current = section
                found_heading = True
                break
        
        if not found_heading:
            sections[current] += " " + line
    
    for key in sections:
        sections[key] = sections[key].strip()
    
    return sections


def clean_text(text):
    """Clean and normalize text while preserving tech terms."""
    if not isinstance(text, str):
        return ""
    
    text = text.lower()
    text = re.sub(r'\S+@\S+', ' ', text)
    text = re.sub(r'\+?\d[\d\s\-()]{7,}', ' ', text)
    text = re.sub(r'http\S+', ' ', text)
    text = text.replace("•", " ").replace("\t", " ")
    text = re.sub(r'[^\w\s\-./+#]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def detect_domain(skills_text, experience_text):
    """Detect if resume is IT-related or not.

    Returns tuple ("IT" or "NOT_IT", confidence_float).
    """
    text = (skills_text + " " + experience_text).lower()
    it_matches = len([kw for kw in IT_KEYWORDS if kw in text])

    if it_matches == 0:
        return "NOT_IT", 0.0

    # confidence scaled by number of matches (cap to 1.0)
    confidence = float(it_matches) / (it_matches + 1)
    return "IT", min(1.0, confidence)


def extract_keywords(text, n_terms=25):
    """Extract top TF-IDF terms from a text as a set of keywords."""
    try:
        if not isinstance(text, str) or not text.strip():
            return set()
        vec = TfidfVectorizer(max_features=n_terms, stop_words='english')
        vec.fit([text])
        return set(vec.get_feature_names_out())
    except Exception:
        return set()


def keyword_overlap_score(resume_kw, job_kw):
    if not resume_kw or not job_kw:
        return 0.0
    overlap = len(resume_kw & job_kw)
    union = len(resume_kw | job_kw)
    return overlap / union if union > 0 else 0.0


def detect_job_domain(description, qualifications):
    """Detect if a job posting is IT-related or general.

    Returns 'IT' when IT keywords are present, otherwise 'GENERAL'.
    """
    text = (str(description or "") + " " + str(qualifications or "")).lower()
    it_matches = len([kw for kw in IT_KEYWORDS if kw in text])
    return "IT" if it_matches > 0 else "GENERAL"


def compute_embedding_similarities(emb_a, emb_b_series):
    """Compute cosine similarity between one embedding and a series."""
    return emb_b_series.apply(lambda x: float(cosine_similarity([emb_a], [x])[0][0]))


# ============================================================================
# MAIN RECOMMENDER CLASS
# ============================================================================

class JobRecommender:
    """Job recommendation engine using semantic + keyword matching.

    This version uses Django ORM when available (recommended for integration
    with the web app). If run as a standalone script, ensure Django settings
    are configured in the environment (DJANGO_SETTINGS_MODULE) before use.
    """

    def __init__(self, db_config=None):
        """Initialize. `db_config` is kept for backward compatibility but not used.
        """
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vectorizer_v2 = None
        self.jobs_df = None
    
    def load_resume(self, user_id):
        """Load and process resume from database."""
        # Prefer Django ORM when available
        resume_text = None
        # ensure Django settings are configured for ORM access
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
        try:
            django.setup()
            from main.models import JobResume

            # JobResume is linked to a User; look up by user_id (not resume PK)
            resume_obj = JobResume.objects.filter(user_id=user_id).first()
            if not resume_obj:
                raise ValueError(f"No resume found for user_id {user_id}")

            resume_text = getattr(resume_obj, 'resume_text', None)
            if not resume_text:
                raise ValueError(f"Resume for user_id {user_id} has no extracted text")

        except Exception as e:
            # Propagate a clear error to the caller
            raise ValueError(str(e))
        self.resume_sections = detect_resume_sections(resume_text)
        
        # Clean sections
        self.resume_sections_clean = {
            section: clean_text(text)
            for section, text in self.resume_sections.items()
        }
        
        # Extract key sections
        self.profile_clean = self.resume_sections_clean["profile"]
        self.experience_clean = self.resume_sections_clean["experience"]
        self.skills_clean = self.resume_sections_clean["skills"]
        self.projects_clean = self.resume_sections_clean["projects"]
        
        # Detect resume domain
        self.resume_domain, self.domain_confidence = detect_domain(
            self.skills_clean, self.experience_clean
        )
        
        # Encode resume sections
        self.profile_emb = self.model.encode(self.profile_clean)
        self.experience_emb = self.model.encode(self.experience_clean)
        self.skills_emb = self.model.encode(self.skills_clean)
        self.projects_emb = self.model.encode(self.projects_clean)
    
    def load_jobs(self):
        """Load jobs from database."""
        # Use Django ORM to build a jobs DataFrame
        try:
            if not os.environ.get('DJANGO_SETTINGS_MODULE'):
                os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
            django.setup()
            from main.models import Job

            rows = []
            for job in Job.objects.all():
                desc = job.description or ""
                quali = getattr(job, 'qualifications', None) or ""
                # If qualifications empty, try to split from description
                if not quali and desc:
                    try:
                        from main.views import split_job_text
                        _desc, _quali = split_job_text(desc)
                        if _quali and not quali:
                            quali = _quali
                            desc = _desc or desc
                    except Exception:
                        pass

                rows.append({
                    'id': job.id,
                    'title': job.title,
                    'company': getattr(job, 'company', '') or '',
                    'description': desc,
                    'qualifications': quali,
                    'url': getattr(job, 'url', '') or ''
                })

            self.jobs_df = pd.DataFrame(rows)
        except Exception as e:
            raise RuntimeError("Unable to load jobs via Django ORM: %s" % str(e))

        # Filter out jobs with missing data
        if self.jobs_df is None or self.jobs_df.empty:
            self.jobs_df = pd.DataFrame(columns=['id', 'title', 'company', 'description', 'qualifications', 'url'])

        self.jobs_df = self.jobs_df[
            self.jobs_df['description'].notna() & self.jobs_df['qualifications'].notna()
        ]
        self.jobs_df = self.jobs_df[
            (self.jobs_df['description'].str.strip() != "") & (self.jobs_df['qualifications'].str.strip() != "")
        ]

        # Clean job texts
        self.jobs_df["clean_desc"] = self.jobs_df["description"].fillna("").apply(clean_text)
        self.jobs_df["clean_quali"] = self.jobs_df["qualifications"].fillna("").apply(clean_text)

        # Detect job domains
        self.jobs_df["job_domain"] = self.jobs_df.apply(
            lambda row: detect_job_domain(row['description'], row['qualifications']),
            axis=1
        )

        # Encode job texts
        self.jobs_df["desc_emb"] = self.jobs_df["clean_desc"].apply(lambda x: self.model.encode(x) if x.strip() else self.model.encode(""))
        self.jobs_df["quali_emb"] = self.jobs_df["clean_quali"].apply(lambda x: self.model.encode(x) if x.strip() else self.model.encode(""))

        # Precompute job keywords from qualifications
        self.jobs_df["job_keywords"] = self.jobs_df["clean_quali"].fillna("").apply(lambda x: extract_keywords(x, n_terms=25))
    
    def compute_similarities(self):
        """Compute semantic and keyword-based similarities."""
        
        # ---- Semantic Similarities ----
        self.jobs_df["skills_vs_quali_emb"] = compute_embedding_similarities(
            self.skills_emb, self.jobs_df["quali_emb"]
        )
        self.jobs_df["exp_vs_desc_emb"] = compute_embedding_similarities(
            self.experience_emb, self.jobs_df["desc_emb"]
        )
        self.jobs_df["profile_vs_quali_emb"] = compute_embedding_similarities(
            self.profile_emb, self.jobs_df["quali_emb"]
        )
        self.jobs_df["profile_vs_desc_emb"] = compute_embedding_similarities(
            self.profile_emb, self.jobs_df["desc_emb"]
        )
        self.jobs_df["projects_vs_desc_emb"] = compute_embedding_similarities(
            self.projects_emb, self.jobs_df["desc_emb"]
        )
        
        # ---- TF-IDF Similarities ----
        all_texts = [
            self.skills_clean, self.experience_clean, self.projects_clean
        ] + self.jobs_df["clean_quali"].tolist() + self.jobs_df["clean_desc"].tolist()
        
        self.vectorizer_v2 = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            max_features=500,
            sublinear_tf=True,
            min_df=1,
            max_df=0.9
        )
        self.vectorizer_v2.fit(all_texts)
        
        # Skills vs Qualifications
        skills_quali_matrix = self.vectorizer_v2.transform(
            [self.skills_clean] + self.jobs_df["clean_quali"].tolist()
        )
        self.jobs_df["skills_vs_quali_tfidf"] = cosine_similarity(
            skills_quali_matrix[0:1], skills_quali_matrix[1:]
        ).flatten()
        
        # Experience vs Description
        exp_desc_matrix = self.vectorizer_v2.transform(
            [self.experience_clean] + self.jobs_df["clean_desc"].tolist()
        )
        self.jobs_df["exp_vs_desc_tfidf"] = cosine_similarity(
            exp_desc_matrix[0:1], exp_desc_matrix[1:]
        ).flatten()
        
        # Projects vs Description
        projects_desc_matrix = self.vectorizer_v2.transform(
            [self.projects_clean] + self.jobs_df["clean_desc"].tolist()
        )
        self.jobs_df["projects_vs_desc_tfidf"] = cosine_similarity(
            projects_desc_matrix[0:1], projects_desc_matrix[1:]
        ).flatten()

        # --- Keyword extraction and overlap ---
        resume_kw_text = (self.skills_clean + " " + self.experience_clean).strip()
        self.resume_keywords = extract_keywords(resume_kw_text, n_terms=40)
        # Ensure job keywords exist (may have been set in load_jobs)
        if 'job_keywords' not in self.jobs_df.columns:
            self.jobs_df['job_keywords'] = self.jobs_df['clean_quali'].fillna("").apply(lambda x: extract_keywords(x, n_terms=25))

        self.jobs_df['keyword_overlap'] = self.jobs_df['job_keywords'].apply(
            lambda jk: keyword_overlap_score(self.resume_keywords, jk)
        )
    
    def calculate_scores(self):
        """Calculate final hybrid scores."""
        
        # Hybrid scoring: 60% semantic, 40% keywords
        self.jobs_df["skills_match"] = (
            0.6 * self.jobs_df["skills_vs_quali_emb"] +
            0.4 * self.jobs_df["skills_vs_quali_tfidf"]
        )
        # Boost skills match with keyword overlap (moderate)
        if 'keyword_overlap' in self.jobs_df.columns:
            self.jobs_df["skills_match"] = self.jobs_df["skills_match"] * (1 + 0.5 * self.jobs_df["keyword_overlap"])
        
        self.jobs_df["experience_match"] = (
            0.6 * self.jobs_df["exp_vs_desc_emb"] +
            0.4 * self.jobs_df["exp_vs_desc_tfidf"]
        )
        
        self.jobs_df["profile_match"] = (
            0.5 * self.jobs_df["profile_vs_quali_emb"] +
            0.5 * self.jobs_df["profile_vs_desc_emb"]
        )
        
        self.jobs_df["projects_match"] = self.jobs_df["projects_vs_desc_tfidf"]
        
        # Normalize component scores to 0-1 to balance their influence
        scaler = MinMaxScaler()
        comps = ["skills_match", "experience_match", "profile_match", "projects_match"]
        for c in comps:
            if c not in self.jobs_df.columns:
                self.jobs_df[c] = 0.0

        try:
            normed = scaler.fit_transform(self.jobs_df[comps].fillna(0.0))
            for i, c in enumerate(comps):
                self.jobs_df[c + "_norm"] = normed[:, i]
        except Exception:
            # Fallback: copy raw values
            for c in comps:
                self.jobs_df[c + "_norm"] = self.jobs_df[c].fillna(0.0)

        # Final composite score uses normalized components
        self.jobs_df["final_score"] = (
            0.25 * self.jobs_df["skills_match_norm"] +
            0.35 * self.jobs_df["experience_match_norm"] +
            0.25 * self.jobs_df["profile_match_norm"] +
            0.15 * self.jobs_df["projects_match_norm"]
        )
    
    def get_recommendations(self, top_n=10, min_score=0.15):
        """Get top job recommendations, filtered by domain."""
        # Apply domain handling: only accept IT resumes for IT-only DB.
        if getattr(self, 'resume_domain', 'NOT_IT') == "IT":
            filtered = self.jobs_df[self.jobs_df["job_domain"] == "IT"].copy()
        else:
            # Resume not IT -> give zero score to all jobs (database contains only IT jobs)
            filtered = self.jobs_df.copy()
            filtered["final_score"] = 0.0

        # Filter by minimum score
        filtered = filtered[filtered["final_score"] >= min_score]
        
        # Sort and return top N
        recommendations = filtered.nlargest(top_n, "final_score")
        cols = [
            "title", "company", "final_score", "skills_match",
            "experience_match", "profile_match", "projects_match", "url"
        ]
        if 'id' in recommendations.columns:
            cols.insert(0, 'id')

        return recommendations[cols]
    
    def recommend(self, user_id, top_n=10, min_score=0.15):
        """Full pipeline: load, process, score, and recommend."""
        self.load_resume(user_id)
        self.load_jobs()
        self.compute_similarities()
        self.calculate_scores()
        return self.get_recommendations(top_n, min_score)

    def recommend_from_resume_text(self, resume_text, jobs_df, top_n=8, min_score=0.15):
        """Run recommendation pipeline using provided resume text and jobs DataFrame.

        jobs_df must be a pandas DataFrame with at least the columns:
        - id (optional but recommended), title, company, description, qualifications, url
        """
        # Process resume text
        self.resume_sections = detect_resume_sections(resume_text)
        self.resume_sections_clean = {
            section: clean_text(text)
            for section, text in self.resume_sections.items()
        }

        self.profile_clean = self.resume_sections_clean.get("profile", "")
        self.experience_clean = self.resume_sections_clean.get("experience", "")
        self.skills_clean = self.resume_sections_clean.get("skills", "")
        self.projects_clean = self.resume_sections_clean.get("projects", "")

        self.resume_domain, self.domain_confidence = detect_domain(
            self.skills_clean, self.experience_clean
        )

        # Encode resume sections
        self.profile_emb = self.model.encode(self.profile_clean)
        self.experience_emb = self.model.encode(self.experience_clean)
        self.skills_emb = self.model.encode(self.skills_clean)
        self.projects_emb = self.model.encode(self.projects_clean)

        # Prepare jobs DataFrame
        self.jobs_df = jobs_df.copy()

        # Ensure clean text columns exist
        if "clean_desc" not in self.jobs_df.columns:
            self.jobs_df["clean_desc"] = self.jobs_df["description"].fillna("").apply(clean_text)
        if "clean_quali" not in self.jobs_df.columns:
            self.jobs_df["clean_quali"] = self.jobs_df["qualifications"].fillna("").apply(clean_text)

        # Detect job domains
        self.jobs_df["job_domain"] = self.jobs_df.apply(
            lambda row: detect_job_domain(row.get("description", ""), row.get("qualifications", "")),
            axis=1
        )

        # Encode job texts
        self.jobs_df["desc_emb"] = self.jobs_df["clean_desc"].apply(lambda x: self.model.encode(x) if str(x).strip() else self.model.encode(""))
        self.jobs_df["quali_emb"] = self.jobs_df["clean_quali"].apply(lambda x: self.model.encode(x) if str(x).strip() else self.model.encode(""))

        # Run rest of pipeline
        self.compute_similarities()
        self.calculate_scores()

        return self.get_recommendations(top_n=top_n, min_score=min_score)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import sys
    # Get user_id from command line or use default
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    # Try to configure Django for ORM usage
    try:
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
        django.setup()
    except Exception:
        pass

    recommender = JobRecommender()

    try:
        recommendations = recommender.recommend(user_id, top_n=10, min_score=0.15)

        # Display results
        print(f"\n{'='*80}")
        print(f"JOB RECOMMENDATIONS FOR USER {user_id}")
        print(f"{'='*80}")
        print(f"\nResume Domain: {getattr(recommender, 'resume_domain', 'UNKNOWN')} ({getattr(recommender, 'domain_confidence', 0.0):.1%} confidence)")
        print(f"Total Recommendations: {len(recommendations)}\n")

        for rank, (idx, job) in enumerate(recommendations.iterrows(), 1):
            print(f"{rank:2d}. {job['title']} @ {job['company']}")
            print(f"    Score: {job['final_score']:.4f}")
            print(f"    └─ Skills: {job['skills_match']:.3f} | Experience: {job['experience_match']:.3f} | "
                  f"Profile: {job['profile_match']:.3f}")
            print(f"    {job['url']}\n")

    except Exception as e:
        print("Error running recommender:", str(e))
        sys.exit(1)
