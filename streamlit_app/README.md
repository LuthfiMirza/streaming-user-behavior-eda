# Streamlit Dashboard

Interactive dashboard for the Streaming Platform User Behavior EDA project.

## Run Locally

```bash
streamlit run streamlit_app/app.py
```

## Required Data

The dashboard expects `data/processed/master_dataset.csv` to exist. If it is missing, run the pipeline first:

```bash
python data/generate_synthetic_data.py
python data/process_data_foundation.py
python visuals/generate_visuals.py
```

## Deploy to Streamlit Cloud

1. Push this repository to GitHub.
2. Open [streamlit.io/cloud](https://streamlit.io/cloud).
3. Create a new app and connect this repo.
4. Set the main file path to `streamlit_app/app.py`.
5. Deploy.
