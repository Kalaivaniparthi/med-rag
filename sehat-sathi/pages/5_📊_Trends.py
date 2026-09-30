import plotly.graph_objects as go
import streamlit as st

from core import db

db.page_setup("Trends", "📊")
db.hero("📊 Lab trends", "See how your results changed across visits. The green band is the general reference range.")

# Small hard-coded reference ranges (low, high) - general adult ranges, for context only
REF = {"LDL": (0, 100), "HDL": (50, 100), "HbA1c": (4.0, 5.7), "Glucose": (70, 99), "TSH": (0.4, 4.0),
       "Hemoglobin": (12.0, 15.5), "Total Cholesterol": (0, 200), "Triglycerides": (0, 150),
       "Platelet": (150, 450), "WBC": (4.0, 11.0)}


def ref_for(test):
    t = test.lower()
    return next((v for k, v in REF.items() if k.lower() in t), None)


rows = db.q("SELECT * FROM lab_values ORDER BY date")
if not rows:
    st.info("No lab values yet. Upload a lab report on the Documents page (needs the Groq key for extraction).")
    st.stop()
tests = sorted({r["test"] for r in rows})
show = st.multiselect("Choose tests to show", tests,
                      default=[t for t in tests if any(k in t for k in ("LDL", "HbA1c"))] or tests[:2])
for test in show:
    pts = [r for r in rows if r["test"] == test]
    ref, last, first = ref_for(test), pts[-1], pts[0]
    delta = last["value"] - first["value"]
    if ref is None:
        where = db.pill("no reference", "idle")
    elif last["value"] > ref[1]:
        where = db.pill("above reference range", "warn")
    elif last["value"] < ref[0]:
        where = db.pill("below reference range", "warn")
    else:
        where = db.pill("within reference range", "ok")
    with st.container(border=True):
        db.stats([(f"{test} - latest", f"{last['value']:g} {last['unit']}", last["date"]),
                  ("Change since first", f"{'▲' if delta > 0 else '▼' if delta < 0 else '■'} {abs(delta):g}",
                   f"over {len(pts)} results")])
        st.markdown(where, unsafe_allow_html=True)
        fig = go.Figure(go.Scatter(x=[p["date"] for p in pts], y=[p["value"] for p in pts], mode="lines+markers",
                                   line=dict(width=3, color="#0d9488"), marker=dict(size=10)))
        if ref:
            fig.add_hrect(y0=ref[0], y1=ref[1], fillcolor="green", opacity=0.12, line_width=0,
                          annotation_text=f"Reference {ref[0]}-{ref[1]}", annotation_position="top left")
        fig.update_layout(height=280, xaxis_title=None, yaxis_title=last["unit"], margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
st.caption("Reference bands are general adult ranges for context. Ask your doctor what your results mean for you.")
with st.expander("All values"):
    st.dataframe(rows, width="stretch", hide_index=True)
