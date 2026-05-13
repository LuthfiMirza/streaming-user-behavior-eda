# Streaming Platform User Behavior — Data Story Summary
**Author:** Luthfi Mirza Darsono | Gunadarma University  
**Dataset:** 2,000 users, 500 content, 50,000 events (synthetic NOICE-style)

## Executive Summary
This project analyzes synthetic NOICE-style streaming behavior across users, content, search demand, discovery channels, and session-level engagement. The goal is to translate platform activity into clear business insight for product, growth, and content teams, with a focus on completion behavior, retention risk, valuable user segments, and content strategy opportunities.

The analysis shows that engagement is not evenly distributed across content or users. Shorter content consistently performs better on completion, power users contribute a disproportionate share of total playtime, and early skip-heavy sessions act as a practical warning signal for churn. Search-demand comparison also highlights underrepresented categories where users show interest but the platform has relatively limited supply.

Recommended actions focus on improving first-session relevance, protecting the highest-value listener segments, and aligning content acquisition with demand signals. The strongest near-term opportunities are onboarding recommendation improvements, loyalty mechanics for power users, more sub-25-minute content, and creator acquisition in Talk Show and Tech categories.

## Key Findings
1. **Content Length Sweet Spot** — Content under 25 min achieves highest completion rate
2. **Power User Concentration** — Top 20% users drive majority of total playtime  
3. **Early Churn Signal** — Users with high skip count in first session churn faster
4. **Underserved Genre** — Talk Show has high search demand but low content supply
5. **Peak Engagement Window** — Evening/night hours show highest session duration

## Priority Recommendations
| Priority | Action | Expected Impact |
|----------|--------|-----------------|
| 🔴 High | Improve onboarding recommendation flow | +15% D7 retention |
| 🔴 High | Build loyalty program for power users | Reduce top-tier churn |
| 🟡 Medium | Commission more sub-25min content | +10% avg completion |
| 🟡 Medium | Acquire Talk Show / Tech creators | Capture high-intent users |
| 🟢 Low | Schedule push notifs for evening peak | +8% CTR |

## Methodology
- Data: Synthetic NOICE-style interaction logs (reproducible via generate_synthetic_data.py)
- Tools: Python, Pandas, Plotly, Seaborn, Streamlit
- Notebooks: 6 Jupyter notebooks covering full EDA pipeline
- Dashboard: Interactive Streamlit app (4 pages)

## How to Reproduce
```bash
git clone https://github.com/LuthfiMirza/streaming-user-behavior-eda
pip install -r requirements.txt
python data/generate_synthetic_data.py --users 2000 --content 500 --events 50000
python data/process_data_foundation.py
streamlit run streamlit_app/app.py
```
