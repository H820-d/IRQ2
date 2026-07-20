import streamlit as st
import json, os
from questions import QUESTIONS
from scoring import (calculate_scores, rating_label,
                     compute_normalized_weights)
from excel_io import export_to_excel, import_from_excel, SECTION_WEIGHTS
from manage import (load_removed, save_removed, get_active_questions,
                    load_custom, save_custom, add_custom_question,
                    all_question_ids, generate_id)

st.set_page_config(page_title="EWRA IRQ", layout="wide")
RESPONSE_FILE = "responses.json"

# ---------- LOAD SAVED RESPONSES ----------
if os.path.exists(RESPONSE_FILE):
    with open(RESPONSE_FILE) as f:
        saved_data = json.load(f)
else:
    saved_data = {"assessment_name": "", "assessment_year": "", "responses": {}}
saved_responses = saved_data.get("responses", {})

# ---------- ACTIVE = (master + custom) - removed ----------
ACTIVE_QUESTIONS = get_active_questions(QUESTIONS)

st.title("EWRA - Inherent Risk Questionnaire")

# ---------- SIDEBAR ----------
view_mode = st.sidebar.radio(
    "View",
    ["Questionnaire", "Risk Results", "Question Weights",
     "Add Question", "Manage Questions", "Excel Import/Export"]
)
sections = sorted(set(q["section"] for q in ACTIVE_QUESTIONS))
st.sidebar.write(f"Active questions: {len(ACTIVE_QUESTIONS)} / "
                 f"{len(QUESTIONS) + len(load_custom())}")

# ---------- ASSESSMENT INFO ----------
st.subheader("Assessment Information")
assessment_name = st.text_input("Assessment Name",
                                value=saved_data.get("assessment_name", ""))
assessment_year = st.text_input("Assessment Year",
                                value=saved_data.get("assessment_year", ""))

responses = dict(saved_responses)

# ==========================================================
# VIEW 1: QUESTIONNAIRE
# ==========================================================
if view_mode == "Questionnaire":
    if not sections:
        st.warning("No active questions. Add or restore some.")
    else:
        selected = st.sidebar.selectbox("Select Section", sections)
        sqs = [q for q in ACTIVE_QUESTIONS if q["section"] == selected]
        st.sidebar.info(f"{len(sqs)} questions in this section")

        for q in sqs:
            st.divider()
            st.header(q["id"])
            st.write(q["question"])
            responses[q["id"]] = saved_responses.get(q["id"], {})
            for field in q["fields"]:
                prev = saved_responses.get(q["id"], {}).get(field)
                k = f"{q['id']}_{field}"
                if q["type"] == "number":
                    v = st.number_input(field, min_value=0,
                                        value=int(prev) if prev else 0, key=k)
                elif q["type"] == "currency":
                    v = st.number_input(field, min_value=0.0, format="%.2f",
                                        value=float(prev) if prev else 0.0, key=k)
                elif q["type"] == "boolean":
                    opts = ["Yes", "No"]
                    idx = opts.index(prev) if prev in opts else 1
                    v = st.radio(field, opts, index=idx, key=k)
                elif q["type"] == "textarea":
                    v = st.text_area(field, value=prev if prev else "", key=k)
                elif q["type"] == "percentage":
                    v = st.number_input(field, min_value=0.0, max_value=100.0,
                                        step=0.1, value=float(prev) if prev else 0.0,
                                        key=k)
                responses[q["id"]][field] = v

        st.divider()
        if st.button("Save Assessment"):
            with open(RESPONSE_FILE, "w") as f:
                json.dump({"assessment_name": assessment_name,
                           "assessment_year": assessment_year,
                           "responses": responses}, f, indent=4, default=str)
            st.success("Saved to responses.json")

# ==========================================================
# VIEW 2: RISK RESULTS
# ==========================================================
elif view_mode == "Risk Results":
    st.header("📊 Inherent Risk Results")
    results = calculate_scores(ACTIVE_QUESTIONS, saved_responses)

    st.metric("Overall Inherent Risk", results["overall_rating"],
              delta=f"Score: {results['overall_score']:.2f} / 4")

    st.subheader("Category Scores")
    for cat, score in results["category_scores"].items():
        st.write(f"**{cat}** — {rating_label(score)} (score {score:.2f})")
        st.progress(min(score / 4, 1.0))

    st.subheader("🔍 Why? (Trace-back)")
    if not results["trace"]:
        st.info("No scored questions active.")
    for qid, info in results["trace"].items():
        with st.expander(f"{qid} → {info['rating']} "
                         f"(weight {info['effective_weight_pct']}%)"):
            st.write(f"**Risk factor:** {info['risk_factor']}")
            st.write(f"**Category:** {info['category']}")
            st.write(f"**Raw input:** {info['raw_input']}")
            st.write(f"**Score:** {info['score']} ({info['rating']})")
            st.write(f"**Effective weight:** {info['effective_weight_pct']}%")
            st.write(f"**Source:** {info['source']}")

# ==========================================================
# VIEW 3: QUESTION WEIGHTS
# ==========================================================
elif view_mode == "Question Weights":
    st.header("⚖️ Normalized Question Weights")
    st.write(
        "Section weights are fixed budgets. Each question's % is its share "
        "of that budget. Add/remove a question and the rest auto-redistribute "
        "— the section total never changes."
    )

    weights = compute_normalized_weights(ACTIVE_QUESTIONS, SECTION_WEIGHTS)

    for section in sections:
        budget = SECTION_WEIGHTS.get(section, 0)
        st.subheader(f"{section} — Budget: {budget}%")
        sec_qs = [q for q in ACTIVE_QUESTIONS if q["section"] == section]
        rows = [{
            "ID": q["id"],
            "Relative weight": q.get("weight", 1),
            "Effective %": round(weights.get(q["id"], 0), 2)
        } for q in sec_qs]
        raw_total = round(sum(weights.get(q["id"], 0) for q in sec_qs), 1)
        st.table(rows)
        st.caption(f"✅ Section total: {raw_total}% (target {budget}%)")

# ==========================================================
# VIEW 4: ADD QUESTION (auto-generated ID)
# ==========================================================
elif view_mode == "Add Question":
    st.header("➕ Add a New Question")
    st.write("Create a custom question in any section. The ID is generated "
             "automatically and the section weightage redistributes.")

    existing_sections = sorted(set(q["section"] for q in QUESTIONS))
    section_choice = st.selectbox(
        "Section", existing_sections + ["➕ New section..."]
    )
    if section_choice == "➕ New section...":
        section = st.text_input("New section name (e.g. 'I - Custom')")
    else:
        section = section_choice

    if section and section.strip():
        preview_id = generate_id(QUESTIONS, section)
        st.info(f"Auto-generated ID will be: **{preview_id}**")

    q_type = st.selectbox(
        "Answer type",
        ["number", "currency", "percentage", "boolean", "textarea"]
    )
    question_text = st.text_area("Question text")
    fields_raw = st.text_input(
        "Field labels (comma-separated)", value="Answer",
        help="e.g. 'High %, Medium %, Low %, Unrated %' or just 'AED'"
    )
    weight = st.number_input("Relative weight", min_value=1, value=1, step=1)
    factor_choice = st.selectbox(
        "Link to a risk factor? (optional - affects scoring)",
        ["(none)", "geo_high_risk_exposure", "geo_sanctioned_dealings",
         "cust_high_risk_ratio", "cust_pep_exposure",
         "prod_high_risk_ratio", "chan_non_face_to_face"]
    )

    if st.button("Add Question"):
        if not section or not section.strip():
            st.error("Please provide a section.")
        elif not question_text.strip():
            st.error("Please enter the question text.")
        else:
            new_id = generate_id(QUESTIONS, section)
            fields = [f.strip() for f in fields_raw.split(",") if f.strip()]
            if not fields:
                fields = ["Answer"]
            new_q = {
                "section": section.strip(), "id": new_id, "type": q_type,
                "weight": int(weight), "question": question_text.strip(),
                "fields": fields,
            }
            if factor_choice != "(none)":
                new_q["risk_factor"] = factor_choice
            add_custom_question(new_q)
            st.success(f"Added question with ID '{new_id}' to {section}.")
            st.rerun()

    st.divider()
    custom = load_custom()
    st.subheader(f"Your Custom Questions ({len(custom)})")
    if not custom:
        st.info("No custom questions yet.")
    else:
        for q in custom:
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"**{q['id']}** ({q['section']}) — {q['question']} "
                    f"`{q['type']}` w={q.get('weight', 1)}"
                )
            with c2:
                if st.button("Delete", key=f"delcustom_{q['id']}"):
                    save_custom([x for x in custom if x["id"] != q["id"]])
                    st.rerun()

# ==========================================================
# VIEW 5: MANAGE QUESTIONS
# ==========================================================
elif view_mode == "Manage Questions":
    st.header("🗑️ Manage Questions")
    st.write("Remove questions without touching the code. Weightage "
             "auto-redistributes. Restore anytime — the master list is safe.")

    removed = load_removed()
    all_qs = QUESTIONS + load_custom()

    st.subheader("Active Questions")
    for section in sorted(set(q["section"] for q in all_qs)):
        active_in_sec = [q for q in all_qs
                         if q["section"] == section and q["id"] not in removed]
        if not active_in_sec:
            continue
        with st.expander(f"{section}  ({len(active_in_sec)} active)"):
            for q in active_in_sec:
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"**{q['id']}** — {q['question']}")
                with c2:
                    if st.button("Remove", key=f"rm_{q['id']}"):
                        removed.append(q["id"])
                        save_removed(removed)
                        st.rerun()

    st.divider()
    st.subheader(f"Removed Questions ({len(removed)})")
    if not removed:
        st.info("No questions removed.")
    else:
        for qid in list(removed):
            q = next((x for x in all_qs if x["id"] == qid), None)
            label = f"{qid} — {q['question']}" if q else qid
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"~~{label}~~")
            with c2:
                if st.button("Restore", key=f"rs_{qid}"):
                    removed.remove(qid)
                    save_removed(removed)
                    st.rerun()
        if st.button("♻️ Restore ALL"):
            save_removed([])
            st.rerun()

# ==========================================================
# VIEW 6: EXCEL IMPORT / EXPORT
# ==========================================================
elif view_mode == "Excel Import/Export":
    st.header("📤 Export to Excel")
    st.write("Only active questions are exported to the client template.")
    chosen = st.multiselect("Sections to include", sections, default=sections)
    filtered = [q for q in ACTIVE_QUESTIONS if q["section"] in chosen]
    st.info(f"{len(filtered)} active questions selected")
    st.download_button("⬇️ Download Excel Template", export_to_excel(filtered),
                       "EWRA_IRQ_Template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.divider()
    st.header("📥 Import Completed Excel (from folder)")
    xlsx_files = [f for f in os.listdir(".") if f.endswith(".xlsx")]
    if not xlsx_files:
        st.warning("No .xlsx files found. Drag one into the file explorer.")
    else:
        chosen_file = st.selectbox("Select Excel file", xlsx_files)
        if st.button("Load Answers"):
            imported = import_from_excel(chosen_file)
            with open(RESPONSE_FILE, "w") as f:
                json.dump({"assessment_name": assessment_name,
                           "assessment_year": assessment_year,
                           "responses": imported}, f, indent=4, default=str)
            st.success(f"Imported {len(imported)} questions and saved.")
            st.json(imported)

with st.sidebar.expander("View Saved Data"):
    st.json(saved_data)