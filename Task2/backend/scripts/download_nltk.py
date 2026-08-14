import os
import zipfile
import urllib.request

nltk_dir = os.path.expanduser("~/nltk_data")
corpora_dir = os.path.join(nltk_dir, "corpora")
tokenizers_dir = os.path.join(nltk_dir, "tokenizers")

os.makedirs(corpora_dir, exist_ok=True)
os.makedirs(tokenizers_dir, exist_ok=True)

resources = [
    ("corpora", "wordnet.zip", "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/wordnet.zip"),
    ("corpora", "omw-1.4.zip", "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/omw-1.4.zip"),
    ("tokenizers", "punkt.zip", "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/tokenizers/punkt.zip"),
    ("tokenizers", "punkt_tab.zip", "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/tokenizers/punkt_tab.zip"),
]

for category, filename, url in resources:
    dest_dir = os.path.join(nltk_dir, category)
    zip_path = os.path.join(dest_dir, filename)
    print(f"Downloading {filename}...")
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        print(f"[OK] Extracted {filename}")
    except Exception as e:
        print(f"[ERROR] Failed {filename}: {e}")


print("NLTK data download complete.")
