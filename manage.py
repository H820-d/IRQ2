import json, os, re

REMOVED_FILE = "removed_questions.json"
CUSTOM_FILE = "custom_questions.json"


# ---------- REMOVED ----------
def load_removed():
    if os.path.exists(REMOVED_FILE):
        with open(REMOVED_FILE) as f:
            return json.load(f)
    return []

def save_removed(removed_ids):
    with open(REMOVED_FILE, "w") as f:
        json.dump(removed_ids, f, indent=2)


# ---------- CUSTOM (user-added) ----------
def load_custom():
    if os.path.exists(CUSTOM_FILE):
        with open(CUSTOM_FILE) as f:
            return json.load(f)
    return []

def save_custom(custom_questions):
    with open(CUSTOM_FILE, "w") as f:
        json.dump(custom_questions, f, indent=2)

def add_custom_question(q):
    custom = load_custom()
    custom.append(q)
    save_custom(custom)


# ---------- ACTIVE = (master + custom) - removed ----------
def get_active_questions(master_questions):
    removed = load_removed()
    custom = load_custom()
    combined = master_questions + custom
    return [q for q in combined if q["id"] not in removed]


def all_question_ids(master_questions):
    """Every known ID (master + custom) - prevents duplicates."""
    ids = {q["id"] for q in master_questions}
    ids.update(q["id"] for q in load_custom())
    return ids


# ---------- AUTO-GENERATE ID ----------
def generate_id(master_questions, section):
    """
    'B - Geography' -> B; picks the next free number starting at 100.
    Custom IDs start at 100 so they never clash with built-in IDs (B1a...).
    """
    prefix = section.strip().split("-")[0].strip()
    prefix = re.sub(r"[^A-Za-z]", "", prefix).upper()
    if not prefix:
        prefix = "Q"

    existing = all_question_ids(master_questions)
    n = 100
    while f"{prefix}{n}" in existing:
        n += 1
    return f"{prefix}{n}"