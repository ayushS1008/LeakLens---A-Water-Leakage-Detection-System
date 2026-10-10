# Credits and licences

## Dataset and derived demo data

Wilhelm, Sebastian; Kasbauer, Jakob; Jakob, Dietmar; Elser, Benedikt; Ahrens, Diane. **Smart Meter Water Consumption Measurements**, version 1.0 (2023), Deggendorf Institute of Technology. DOI: https://doi.org/10.5281/zenodo.7506076

Licence: **Creative Commons Attribution 4.0 International (CC BY 4.0)**, confirmed from the Zenodo record metadata. Licence text: https://creativecommons.org/licenses/by/4.0/

Changes made: cumulative cubic metres were converted into 15-minute litres-used intervals; unreliable intervals were marked unknown; calendar and recent-consumption features were derived. The files in `data/demo` add a constant 1 L/min flow for 24 hours and remove it to illustrate a repair. These changes are not endorsed by the dataset authors. Raw readings are not committed to this repository. The trained model was constructed using the attributed household hh-01 dataset.

The actual downloaded hh-01 file spans December 2020 to June 2021. The application and evaluation use those actual timestamps.

## Libraries and tools

| Dependency | Purpose | Licence / source |
|---|---|---|
| React / React DOM | Dashboard | MIT — https://github.com/facebook/react |
| Vite / React plugin | Frontend build and development server | MIT — https://github.com/vitejs/vite |
| ESLint | Frontend checks | MIT — https://github.com/eslint/eslint |
| FastAPI | API | MIT — https://github.com/fastapi/fastapi |
| Uvicorn | API server | BSD-3-Clause — https://github.com/encode/uvicorn |
| python-multipart | CSV uploads | Apache-2.0 — https://github.com/Kludex/python-multipart |
| pandas | Time-series processing | BSD-3-Clause — https://github.com/pandas-dev/pandas |
| NumPy | Numerical features | BSD-3-Clause — https://github.com/numpy/numpy |
| scikit-learn | Isolation Forest | BSD-3-Clause — https://github.com/scikit-learn/scikit-learn |
| joblib | Model persistence | BSD-3-Clause — https://github.com/joblib/joblib |
| Matplotlib | Evaluation figures | See installed licence — https://github.com/matplotlib/matplotlib |
| Boto3 / Botocore | AWS storage SDK | Apache-2.0 — https://github.com/boto/boto3 |
| Nginx | AWS reverse proxy | BSD-2-Clause — https://nginx.org/en/LICENSE |
| Python / SQLite | Runtime and local ticket storage | PSF / SQLite public domain — https://www.python.org/psf/license/ and https://www.sqlite.org/copyright.html |

Installed third-party licence texts, including transitive Python packages and bundled React packages, are collected in THIRD_PARTY_NOTICES.txt. Dependency versions are recorded in requirements.txt and frontend/package-lock.json. Library authors retain their copyrights and licences.

## AI tools

OpenAI ChatGPT / Codex assisted with project planning, Python and React code, debugging, tests, and documentation. The team must review and understand the submitted implementation and add any other AI tools actually used.
