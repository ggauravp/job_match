import re
import os
import numpy as np
import pandas as pd
import django
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import MinMaxScaler
_zero_shot_classifier = None
from transformers import pipeline


def detect_resume_sections(text):
    sections = {"profile": "", "experience": "", "skills": "", "projects": "",
                "education": "", "certificates": "", "other": ""}
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
    return {k: v.strip() for k, v in sections.items()}


def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'\S+@\S+', ' ', text)
    text = re.sub(r'\+?\d[\d\s\-()]{7,}', ' ', text)
    text = re.sub(r'http\S+', ' ', text)
    text = text.replace("•", " ").replace("\t", " ")
    text = re.sub(r'[^\w\s\-./+#]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def extract_keywords(text, n_terms=25):
    try:
        if not text.strip():
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
    return overlap / union if union else 0.0


def classify_resume_domain(resume_text, candidate_labels=None):
    global _zero_shot_classifier
    if candidate_labels is None:
        candidate_labels = ["IT and Technology", "Education", "Healthcare", "Finance", "Other"]
    try:
        if _zero_shot_classifier is None:
            _zero_shot_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
        text_to_classify = resume_text[:1024]
        result = _zero_shot_classifier(text_to_classify, candidate_labels, multi_class=False)
        return result['labels'][0], float(result['scores'][0])
    except Exception as e:
        print(f"Warning: Zero-shot classification failed: {str(e)}")
        return "Other", 0.0



class JobRecommender:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.jobs_df = None
        self.vectorizer_v2 = None

    #  RESUME LOADING 
    def load_resume_from_text(self, resume_text):
        domain, confidence = classify_resume_domain(resume_text)
        self.resume_domain, self.domain_confidence = domain, confidence
        if "IT" not in domain or confidence < 0.3:
            raise ValueError(f"Resume classified as NON-IT, only IT JOBS ARE AVAILABLE")

        self.resume_sections = detect_resume_sections(resume_text)
        self.resume_sections_clean = {k: clean_text(v) for k, v in self.resume_sections.items()}

        self.profile_clean = self.resume_sections_clean.get("profile", "")
        self.experience_clean = self.resume_sections_clean.get("experience", "")
        self.skills_clean = self.resume_sections_clean.get("skills", "")
        self.projects_clean = self.resume_sections_clean.get("projects", "")

        # Batch encode resume sections
        self.profile_emb, self.experience_emb, self.skills_emb, self.projects_emb = self.model.encode(
            [self.profile_clean, self.experience_clean, self.skills_clean, self.projects_clean]
        )

    #  JOB LOADING 
    def load_jobs(self, jobs_df):
        self.jobs_df = jobs_df.copy()
        self.jobs_df["clean_desc"] = self.jobs_df["description"].fillna("").apply(clean_text)
        self.jobs_df["clean_quali"] = self.jobs_df["qualifications"].fillna("").apply(clean_text)

        # Batch encode job texts
        self.jobs_df["desc_emb"] = list(self.model.encode(self.jobs_df["clean_desc"].tolist()))
        self.jobs_df["quali_emb"] = list(self.model.encode(self.jobs_df["clean_quali"].tolist()))

        # Precompute job keywords
        self.jobs_df["job_keywords"] = self.jobs_df["clean_quali"].apply(lambda x: extract_keywords(x, 25))

    #  SIMILARITY COMPUTATION 
    def compute_similarities(self):
        # Semantic embeddings
        self.jobs_df["skills_vs_quali_emb"] = [float(cosine_similarity([self.skills_emb], [e])[0][0]) for e in self.jobs_df["quali_emb"]]
        self.jobs_df["exp_vs_desc_emb"] = [float(cosine_similarity([self.experience_emb], [e])[0][0]) for e in self.jobs_df["desc_emb"]]
        self.jobs_df["profile_vs_quali_emb"] = [float(cosine_similarity([self.profile_emb], [e])[0][0]) for e in self.jobs_df["quali_emb"]]
        self.jobs_df["profile_vs_desc_emb"] = [float(cosine_similarity([self.profile_emb], [e])[0][0]) for e in self.jobs_df["desc_emb"]]
        self.jobs_df["projects_vs_desc_emb"] = [float(cosine_similarity([self.projects_emb], [e])[0][0]) for e in self.jobs_df["desc_emb"]]

        # TF-IDF
        all_texts = [self.skills_clean, self.experience_clean, self.projects_clean] + \
                    self.jobs_df["clean_quali"].tolist() + self.jobs_df["clean_desc"].tolist()
        self.vectorizer_v2 = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=500, sublinear_tf=True)
        self.vectorizer_v2.fit(all_texts)

        # Skills vs qualifications
        skills_quali_matrix = self.vectorizer_v2.transform([self.skills_clean] + self.jobs_df["clean_quali"].tolist())
        self.jobs_df["skills_vs_quali_tfidf"] = cosine_similarity(skills_quali_matrix[0:1], skills_quali_matrix[1:]).flatten()

        # Experience vs description
        exp_desc_matrix = self.vectorizer_v2.transform([self.experience_clean] + self.jobs_df["clean_desc"].tolist())
        self.jobs_df["exp_vs_desc_tfidf"] = cosine_similarity(exp_desc_matrix[0:1], exp_desc_matrix[1:]).flatten()

        # Projects vs description
        projects_desc_matrix = self.vectorizer_v2.transform([self.projects_clean] + self.jobs_df["clean_desc"].tolist())
        self.jobs_df["projects_vs_desc_tfidf"] = cosine_similarity(projects_desc_matrix[0:1], projects_desc_matrix[1:]).flatten()

        # Keyword overlap
        resume_kw_text = (self.skills_clean + " " + self.experience_clean).strip()
        self.resume_keywords = extract_keywords(resume_kw_text, 40)
        self.jobs_df['keyword_overlap'] = self.jobs_df['job_keywords'].apply(
            lambda jk: keyword_overlap_score(self.resume_keywords, jk)
        )

    #  SCORING 
    def calculate_scores(self):
        self.jobs_df["skills_match"] = 0.6*self.jobs_df["skills_vs_quali_emb"] + 0.4*self.jobs_df["skills_vs_quali_tfidf"]
        self.jobs_df["skills_match"] *= (1 + 0.5*self.jobs_df["keyword_overlap"])
        self.jobs_df["experience_match"] = 0.6*self.jobs_df["exp_vs_desc_emb"] + 0.4*self.jobs_df["exp_vs_desc_tfidf"]
        self.jobs_df["profile_match"] = 0.5*self.jobs_df["profile_vs_quali_emb"] + 0.5*self.jobs_df["profile_vs_desc_emb"]
        self.jobs_df["projects_match"] = self.jobs_df["projects_vs_desc_tfidf"]

        # Normalize
        scaler = MinMaxScaler()
        comps = ["skills_match", "experience_match", "profile_match", "projects_match"]
        normed = scaler.fit_transform(self.jobs_df[comps].fillna(0.0))
        for i, c in enumerate(comps):
            self.jobs_df[c + "_norm"] = normed[:, i]

        # Final score
        self.jobs_df["final_score"] = 0.25*self.jobs_df["skills_match_norm"] + \
                                      0.35*self.jobs_df["experience_match_norm"] + \
                                      0.25*self.jobs_df["profile_match_norm"] + \
                                      0.15*self.jobs_df["projects_match_norm"]

    #  GET TOP JOBS 
    def get_recommendations(self, top_n=10, min_score=0.15):
        filtered = self.jobs_df[self.jobs_df["final_score"] >= min_score]
        recommendations = filtered.nlargest(top_n, "final_score")
        cols = ["id", "title", "company", "final_score", "skills_match", "experience_match", "profile_match", "projects_match", "url"]
        return recommendations[cols]

    def recommend_from_resume_text(self, resume_text, jobs_df, top_n=10, min_score=0.15):
        self.load_resume_from_text(resume_text)
        self.load_jobs(jobs_df)
        self.compute_similarities()
        self.calculate_scores()
        return self.get_recommendations(top_n, min_score)

    # RECOMMEND BY USER ID (Django ORM) 
    def recommend(self, user_id, top_n=10, min_score=0.15):
        """
        Fetch resume using Django ORM for the given user_id and recommend jobs.
        Requires DJANGO_SETTINGS_MODULE set.
        """
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
        django.setup()
        from main.models import JobResume, Job

        resume_obj = JobResume.objects.filter(user_id=user_id).first()
        if not resume_obj or not getattr(resume_obj, 'resume_text', None):
            raise ValueError(f"No resume found for user_id {user_id}")

        resume_text = resume_obj.resume_text

        # Load jobs from DB
        rows = []
        for job in Job.objects.all():
            rows.append({
                "id": job.id,
                "title": job.title,
                "company": getattr(job, "company", "") or "",
                "description": getattr(job, "description", "") or "",
                "qualifications": getattr(job, "qualifications", "") or "",
                "url": getattr(job, "url", "") or ""
            })
        jobs_df = pd.DataFrame(rows)

        # Run pipeline
        return self.recommend_from_resume_text(resume_text, jobs_df, top_n=top_n, min_score=min_score)

if __name__ == "__main__":
    import sys
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    recommender = JobRecommender()
    try:
        recommendations = recommender.recommend(user_id=user_id, top_n=10, min_score=0.15)
        print(f"\n{'='*80}")
        print(f"JOB RECOMMENDATIONS FOR USER {user_id}")
        print(f"{'='*80}\n")
        for rank, (idx, job) in enumerate(recommendations.iterrows(), 1):
            print(f"{rank:2d}. {job['title']} @ {job['company']}")
            print(f"    Score: {job['final_score']:.4f}")
            print(f"    └─ Skills: {job['skills_match']:.3f} | Experience: {job['experience_match']:.3f} | "
                  f"Profile: {job['profile_match']:.3f}")
            print(f"    URL: {job['url']}\n")
    except Exception as e:
        print("Error generating recommendations:", str(e))