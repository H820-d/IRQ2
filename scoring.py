from excel_io import SECTION_WEIGHTS

RISK_FACTORS = {
    "geo_high_risk_exposure":  {"category": "Geography",
        "aggregation": "max", "thresholds": {0: 1, 10: 2, 25: 3, 50: 4}},
    "geo_sanctioned_dealings": {"category": "Geography",
        "aggregation": "max", "thresholds": {"No": 1, "Yes": 4}},
    "cust_high_risk_ratio":    {"category": "Customer",
        "aggregation": "max", "thresholds": {0: 1, 10: 2, 20: 3, 40: 4}},
    "cust_pep_exposure":       {"category": "Customer",
        "aggregation": "sum", "thresholds": {0: 1, 50: 2, 200: 3, 500: 4}},
    "prod_high_risk_ratio":    {"category": "Product",
        "aggregation": "max", "thresholds": {0: 1, 10: 2, 25: 3, 50: 4}},
    "chan_non_face_to_face":   {"category": "Channel",
        "aggregation": "max", "thresholds": {"No": 1, "Yes": 3}},
}

CATEGORY_WEIGHTS = {"Customer": 0.30, "Geography": 0.30,
                    "Product": 0.25, "Channel": 0.15}


def compute_normalized_weights(questions, section_weights=SECTION_WEIGHTS):
    normalized = {}
    sections = {}
    for q in questions:
        sections.setdefault(q["section"], []).append(q)
    for section, qs in sections.items():
        budget = section_weights.get(section, 0)
        total_rel = sum(q.get("weight", 1) for q in qs)
        if total_rel == 0:
            continue
        for q in qs:
            rel = q.get("weight", 1)
            normalized[q["id"]] = (rel / total_rel) * budget
    return normalized


def _score_from_thresholds(value, thresholds):
    if isinstance(value, str):
        return thresholds.get(value, 1)
    numeric = {float(k): v for k, v in thresholds.items() if not isinstance(k, str)}
    score = 1
    for limit in sorted(numeric.keys()):
        try:
            if float(value) >= limit:
                score = numeric[limit]
        except (ValueError, TypeError):
            pass
    return score


def _aggregate(values, method):
    nums = []
    for v in values:
        if isinstance(v, str):
            nums.append(v)
        else:
            try:
                nums.append(float(v))
            except (ValueError, TypeError):
                pass
    if not nums:
        return None
    if all(isinstance(n, str) for n in nums):
        return "Yes" if "Yes" in nums else nums[0]
    numeric = [n for n in nums if not isinstance(n, str)]
    if not numeric:
        return nums[0]
    if method == "sum":
        return sum(numeric)
    if method == "average":
        return sum(numeric) / len(numeric)
    return max(numeric)


def rating_label(score):
    if score >= 3.5: return "Critical"
    if score >= 2.5: return "High"
    if score >= 1.5: return "Medium"
    return "Low"


def calculate_scores(questions, responses, section_weights=SECTION_WEIGHTS):
    norm_weights = compute_normalized_weights(questions, section_weights)

    scored_questions = []
    trace = {}

    for q in questions:
        factor = q.get("risk_factor")
        if not factor or factor not in RISK_FACTORS:
            continue

        cfg = RISK_FACTORS[factor]
        answer = responses.get(q["id"], {})
        raw_values = [v for v in answer.values() if v not in (None, "")]

        if raw_values:
            agg = _aggregate(raw_values, cfg["aggregation"])
            score = _score_from_thresholds(agg, cfg["thresholds"])
            source = "answered"
        else:
            agg, score, source = None, 1, "default (no answer)"

        eff_weight = norm_weights.get(q["id"], 0)

        scored_questions.append({
            "id": q["id"], "category": cfg["category"],
            "score": score, "weight": eff_weight,
        })
        trace[q["id"]] = {
            "risk_factor": factor, "category": cfg["category"],
            "raw_input": agg, "score": score, "rating": rating_label(score),
            "effective_weight_pct": round(eff_weight, 2), "source": source,
        }

    category_scores = {}
    for cat in CATEGORY_WEIGHTS.keys():
        cat_qs = [s for s in scored_questions if s["category"] == cat]
        total_w = sum(s["weight"] for s in cat_qs)
        if total_w > 0:
            category_scores[cat] = sum(s["score"] * s["weight"] for s in cat_qs) / total_w
        else:
            category_scores[cat] = 1

    overall = sum(category_scores.get(cat, 1) * w
                  for cat, w in CATEGORY_WEIGHTS.items())

    return {
        "category_scores": category_scores,
        "overall_score": overall,
        "overall_rating": rating_label(overall),
        "trace": trace,
        "normalized_weights": norm_weights,
    }