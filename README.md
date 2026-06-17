# 🎯 RedRob AI Candidate Ranker

[![CI](https://github.com/Santhu7718/redrob-ai-ranker/actions/workflows/ci.yml/badge.svg)](https://github.com/Santhu7718/redrob-ai-ranker/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-ff4b4b)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Rank candidates the way a great recruiter would — not by keywords, but by understanding who genuinely fits.**

A fully offline, no-API, multi-signal candidate ranking system with a beautiful web UI. Upload candidate data in **any format** (Google Forms CSV, Excel, JSON) and get a ranked shortlist with full reasoning for every candidate.

---

## ✨ Features

| | |
|---|---|
| 📂 **Any format** | CSV (Google Forms), Excel (.xlsx), JSON, JSONL |
| 🧠 **Smart column detection** | Auto-maps 50+ column name variants |
| 🌱 **Fresher-friendly** | Dual-track system guarantees fresher representation |
| 📊 **Full reasoning** | Every rank explained — skills, education, certs, experience |
| 💾 **Export** | Download ranked results as CSV or JSON |
| 🔒 **100% offline** | Zero API calls, zero network requests during ranking |
| 🐳 **Docker ready** | One command to deploy anywhere |

---

## 🚀 Quick Start

### Option 1 — Run locally

```bash
# Clone the repo
git clone https://github.com/Santhu7718/redrob-ai-ranker.git
cd redrob-ai-ranker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Launch the UI
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

### Option 2 — Docker

```bash
# Build and run
docker compose up --build

# Or single container
docker build -t redrob-ranker .
docker run -p 8501:8501 redrob-ranker
```

### Option 3 — Deploy to Streamlit Cloud (free)

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub → select this repo → `app.py`
4. Click **Deploy** — done!

---

## 📖 How It Works

### No ML model was trained. No neural networks. No APIs.

The system is a **deterministic, rule-based multi-signal scoring engine** — pure Python math. Every score is fully auditable.

### Scoring Formula

```
final_score = (
    skill_match    × 0.35   # JD skills found in candidate profile
    experience     × 0.25   # YoE curve — freshers boosted
    education      × 0.15   # Institution tier + field + GPA
    completeness   × 0.10   # How filled-in the profile is
    certifications × 0.10   # ML/AI upskilling evidence
    keyword_density × 0.05  # Implicit JD matches across full text
) × fresher_uplift          # Up to ×1.30 for freshers with strong signals
```

### 6 Scoring Signals Explained

#### 🎯 Signal 1: Skill Match (35%)
Regex scans candidate text (skills, summary, title, education) for skills extracted from the JD. Each match contributes to coverage. High-value ML skills (PyTorch, LoRA, RAG, Transformers) get an extra boost.

#### 📅 Signal 2: Experience Fit (25%)
A hand-crafted YoE curve **designed to favor freshers**:
```
0 YoE  → 0.65 base (freshers are valued)
1 YoE  → 0.70
2 YoE  → 0.72
3-6 YoE → 0.78–0.85 (mid-level sweet spot)
6-9 YoE → 0.82 (senior)
12+ YoE → 0.60 (over-experienced penalty)
```

#### 🎓 Signal 3: Education (15%)
- Institution tier: IIT/IISc/BITS → +0.25, NIT → +0.15
- Field relevance: CS/ML/Math → +0.15
- Degree level: PhD > M.Tech > B.Tech
- GPA parsing: CGPA/10, percentage, raw numbers

#### 📋 Signal 4: Profile Completeness (10%)
Counts how many fields are filled in. GitHub URL, LinkedIn, and portfolio links are especially rewarded — a fresher with an active GitHub is more rankable than a senior with no online presence.

#### 📜 Signal 5: Certifications (10%)
Searches certification text for ML-relevant keywords: PyTorch, Coursera, Hugging Face, DeepLearning.AI, Kaggle, NVIDIA, etc.

#### 🔍 Signal 6: Keyword Density (5%)
Full-text scan across all fields. Catches candidates who mention JD terms in project descriptions or summaries without listing them as skills.

### Fresher Dual-Track

```
All 89K candidates
       ↓
┌──────────────────┐    ┌──────────────────┐
│  Experienced     │    │  Freshers        │
│  (> 2 YoE)       │    │  (≤ 2 YoE)       │
│  82K candidates  │    │  7.4K candidates │
│  → Top 70%       │    │  → Top 30%       │
└──────────────────┘    └──────────────────┘
              ↓ Merge & sort by score ↓
                    Final Top 100
```

Freshers also get a **potential uplift** (up to ×1.30) if they show strong signals: GitHub, certifications, top-tier education, or strong skill match.

---

## 📂 Project Structure

```
redrob-ai-ranker/
├── app.py                  # Streamlit UI (main entry point)
├── universal_parser.py     # Parse ANY file format with smart column detection
├── universal_scorer.py     # Scoring engine for flat/form data
├── scorer.py               # Advanced scorer for the original challenge JSONL
├── jd_parser.py            # Parse job descriptions from Word docs
├── rank.py                 # CLI ranker for the original challenge dataset
├── sample_candidates.csv   # Sample Google Forms CSV for testing
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
├── docker-compose.yml      # Easy deployment
├── .streamlit/
│   └── config.toml         # Dark theme configuration
└── .github/
    └── workflows/
        └── ci.yml          # CI pipeline (syntax + integration test)
```

---

## 📄 Supported Input Formats

### Google Forms CSV (auto-detected columns)

The system recognizes 50+ column name variants:

| What you call it | Maps to |
|---|---|
| `Your Name`, `Full Name`, `Applicant Name` | `name` |
| `Years of Experience`, `Work Experience`, `YoE` | `yoe` |
| `Technical Skills`, `Key Skills`, `Tech Stack` | `skills` |
| `Current Role`, `Designation`, `Job Title` | `title` |
| `College / University`, `Institution` | `college` |
| `CGPA / Percentage`, `GPA`, `Marks` | `gpa` |
| `Certifications`, `Courses`, `Online Courses` | `certifications` |
| `GitHub Profile`, `GitHub URL` | `github` |

### Other Formats

- **Excel** (`.xlsx` / `.xls`) — same column auto-detection
- **JSON** — array of flat objects
- **JSONL** — original challenge format (nested structure auto-detected)

---

## ⚙️ CLI Usage (Original Challenge)

```bash
# Rank the original 89K candidate dataset
python rank.py \
  --candidates dataset/candidates.jsonl \
  --out submission.csv

# Validate output
python dataset/validate_submission.py submission.csv
```

---

## 🏆 Challenge Results

| Metric | Value |
|---|---|
| Candidates ranked | 89,788 |
| Runtime | ~126s (712 candidates/sec on CPU) |
| Freshers in top 100 | **30 / 100** |
| Top scorer | Lead AI Engineer @ Razorpay (0.9068) |
| APIs used | **Zero** |
| GPU required | **No** |

---

## 📦 Requirements

```
python >= 3.11
streamlit >= 1.35.0
pandas >= 2.0.0
numpy >= 1.24.0
openpyxl >= 3.1.0    # Excel support
python-docx >= 1.1.2 # Word doc parsing
scikit-learn >= 1.3.0
```

---

## 🤝 Contributing

Pull requests welcome. For major changes, open an issue first.

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for the RedRob AI Challenge — ranks candidates the way a great recruiter would.*
