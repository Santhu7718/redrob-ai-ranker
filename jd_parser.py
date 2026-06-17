"""
jd_parser.py — Job Description Parser
Extracts structured requirements from the JD without external APIs.
Uses rule-based NLP and keyword dictionaries curated from the actual JD.
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict


@dataclass
class JobRequirements:
    """Structured extraction of what the JD actually needs."""

    # Hard skills from JD (MUST HAVE)
    critical_skills: Set[str] = field(default_factory=set)
    # Nice-to-have skills
    preferred_skills: Set[str] = field(default_factory=set)
    # Domain context
    domain_keywords: Set[str] = field(default_factory=set)

    # Experience
    min_years: float = 4.0
    max_years: float = 9.0
    ideal_years: float = 6.5

    # Role context
    role_type: str = "ml_engineer"
    product_company_required: bool = True

    # Red flags — people to penalize
    disqualifying_companies: Set[str] = field(default_factory=set)
    disqualifying_patterns: List[str] = field(default_factory=list)

    # Location preferences
    preferred_locations: Set[str] = field(default_factory=set)

    # Raw JD text for semantic matching
    jd_text: str = ""


def parse_jd() -> JobRequirements:
    """
    Returns structured requirements for the Redrob ML/AI Engineer JD.
    Curated from careful reading of the actual job description.
    """
    req = JobRequirements()

    # === CRITICAL SKILLS (must have, weighted heavily) ===
    req.critical_skills = {
        # Embeddings / retrieval
        "sentence-transformers", "sentence_transformers", "embeddings", "embedding",
        "semantic search", "vector search", "dense retrieval", "hybrid retrieval",
        "bge", "e5", "instructor", "openai embeddings",
        # Vector DBs
        "faiss", "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
        "elasticsearch", "annoy", "scann", "chroma", "pgvector",
        # Ranking / retrieval evaluation
        "ndcg", "mrr", "map", "recall@k", "precision@k", "a/b testing",
        "learning to rank", "ltr", "reranking", "bm25", "tf-idf", "tfidf",
        # ML/AI production
        "mlops", "model serving", "inference", "feature store",
        "transformers", "bert", "llm", "fine-tuning", "rag",
        # Python
        "python", "pytorch", "tensorflow", "huggingface", "sklearn",
        # Search / IR
        "information retrieval", "search ranking", "recommendation system",
        "candidate ranking", "matching", "relevance"
    }

    # === PREFERRED SKILLS (good to have) ===
    req.preferred_skills = {
        # LLM fine-tuning
        "lora", "qlora", "peft", "fine-tuning", "finetuning",
        # Distributed / scale
        "spark", "kafka", "airflow", "kubernetes", "docker",
        # Learning to rank
        "xgboost", "lightgbm", "lambdamart",
        # Open source / community
        "github", "open source", "research", "arxiv", "paper",
        # NLP
        "nlp", "text classification", "named entity", "tokenization",
        "attention", "self-attention",
        # Data
        "sql", "pandas", "numpy", "data engineering",
        # Cloud
        "aws", "gcp", "azure", "cloud"
    }

    # === DOMAIN KEYWORDS (for semantic similarity) ===
    req.domain_keywords = {
        "ranking", "retrieval", "matching", "search", "recommendation",
        "candidate", "recruiter", "job", "hiring", "talent",
        "ml", "machine learning", "ai", "deep learning", "neural network",
        "production", "deployment", "scale", "real-time", "latency",
        "evaluation", "benchmark", "metric", "experiment",
        "product company", "startup", "tech company"
    }

    # === DISQUALIFYING COMPANIES (per JD: pure services firms) ===
    req.disqualifying_companies = {
        "tcs", "tata consultancy", "infosys", "wipro", "accenture",
        "cognizant", "capgemini", "hcl", "tech mahindra",
        "mphasis", "hexaware", "l&t infotech", "ltimindtree",
        "persistent systems", "niit technologies"
    }

    # === DISQUALIFYING PATTERNS ===
    req.disqualifying_patterns = [
        "marketing manager", "sales", "hr manager", "business development",
        "content writer", "graphic designer", "customer support",
        "accountant", "finance", "legal"
    ]

    # === PREFERRED LOCATIONS ===
    req.preferred_locations = {
        "pune", "noida", "hyderabad", "mumbai", "bangalore", "bengaluru",
        "delhi", "chennai", "gurgaon", "gurugram", "india"
    }

    # === JD TEXT (for TF-IDF / semantic scoring) ===
    req.jd_text = """
    Senior Machine Learning Engineer Ranking and Retrieval Systems.
    Production experience with embeddings-based retrieval systems sentence-transformers
    OpenAI embeddings BGE E5 deployed to real users embedding drift index refresh
    retrieval quality regression production.
    Production experience with vector databases hybrid search infrastructure Pinecone
    Weaviate Qdrant Milvus OpenSearch Elasticsearch FAISS.
    Strong Python code quality.
    Hands-on experience designing evaluation frameworks for ranking systems NDCG MRR MAP
    offline-to-online correlation AB test interpretation.
    LLM fine-tuning experience LoRA QLoRA PEFT.
    Learning-to-rank models XGBoost neural.
    HR-tech recruiting tech marketplace products.
    Distributed systems large-scale inference optimization.
    Open-source contributions AI ML space.
    Ranking retrieval matching systems recruiters candidates search.
    Intelligence layer product embeddings hybrid retrieval LLM-based reranking.
    Evaluation infrastructure offline benchmarks online AB testing recruiter feedback loops.
    Applied ML AI roles product companies not pure services.
    Ship end-to-end ranking search recommendation system real users meaningful scale.
    Strong opinions retrieval hybrid dense evaluation offline online LLM integration.
    Python machine learning deep learning NLP information retrieval semantic search.
    Vector search FAISS Pinecone Weaviate Qdrant similarity search nearest neighbor.
    Transformer BERT sentence embeddings cosine similarity dot product.
    Recommendation system collaborative filtering content-based filtering.
    """

    return req
