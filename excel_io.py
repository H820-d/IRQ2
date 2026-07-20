import pandas as pd
from io import BytesIO
from openpyxl.worksheet.datavalidation import DataValidation

SECTION_WEIGHTS = {
    "A - General Information": 10, "B - Geography": 30, "C - Customer Type": 30,
    "D - Channel": 15, "E - Products": 15, "F - Regulatory": 0,
    "G - Staff and Third Party": 0, "H - Cyber Risk": 0,
}


def export_to_excel(questions):
    rows = []
    for q in questions:
        for field in q["fields"]:
            rows.append({
                "ID": q["id"], "Section": q["section"], "Type": q["type"],
                "Question": q["question"], "Field": field, "Answer": ""
            })

    qdf = pd.DataFrame(rows)
    wdf = pd.DataFrame([{"Section": s, "Section Weight %": w}
                        for s, w in SECTION_WEIGHTS.items()])

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        qdf.to_excel(writer, sheet_name="Questions", index=False)
        wdf.to_excel(writer, sheet_name="Weightage", index=False)

        ws = writer.sheets["Questions"]

        dv_bool = DataValidation(type="list", formula1='"Yes,No"',
                                 allow_blank=True, showErrorMessage=True)
        dv_bool.error = "Please choose Yes or No from the dropdown."
        dv_bool.errorTitle = "Invalid entry"
        dv_bool.prompt = "Select Yes or No"
        dv_bool.promptTitle = "Yes/No question"

        dv_pct = DataValidation(type="whole", operator="between",
                                formula1=0, formula2=100,
                                allow_blank=True, showErrorMessage=True)
        dv_pct.error = "Enter a whole number between 0 and 100."
        dv_pct.errorTitle = "Invalid percentage"

        dv_num = DataValidation(type="whole", operator="greaterThanOrEqual",
                                formula1=0, allow_blank=True, showErrorMessage=True)
        dv_num.error = "Enter a whole number (0 or more)."
        dv_num.errorTitle = "Invalid number"

        dv_cur = DataValidation(type="decimal", operator="greaterThanOrEqual",
                                formula1=0, allow_blank=True, showErrorMessage=True)
        dv_cur.error = "Enter an amount (0 or more)."
        dv_cur.errorTitle = "Invalid amount"

        for dv in (dv_bool, dv_pct, dv_num, dv_cur):
            ws.add_data_validation(dv)

        for i, row in enumerate(rows):
            cell = f"F{i + 2}"
            t = row["Type"]
            if t == "boolean":
                dv_bool.add(cell)
            elif t == "percentage":
                dv_pct.add(cell)
            elif t == "number":
                dv_num.add(cell)
            elif t == "currency":
                dv_cur.add(cell)

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 24
        ws.column_dimensions["C"].width = 12
        ws.column_dimensions["D"].width = 60
        ws.column_dimensions["E"].width = 26
        ws.column_dimensions["F"].width = 20

    return out.getvalue()


def import_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file, sheet_name="Questions")
    responses = {}
    for _, row in df.iterrows():
        qid, field, answer = row["ID"], row["Field"], row["Answer"]
        responses.setdefault(qid, {})[field] = answer
    return responses