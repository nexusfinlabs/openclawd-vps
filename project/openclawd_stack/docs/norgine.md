# Norgine — Análisis IA de 14 Ensayos Clínicos

## Resumen Ejecutivo (ES)
Norgine divulga 14 ensayos clínicos en dos áreas: **Preparación Intestinal** (NER1006, NRL994) y **Diagnóstico Hepático** (NRL972). Se propone un marco de IA para automatizar extracción de datos, vigilancia de seguridad y apoyo al diseño de futuros ensayos.

## Executive Summary (EN)
Norgine discloses 14 clinical trials across two areas: **Bowel Cleansing** (NER1006, NRL994) and **Liver Function Diagnosis** (NRL972). An AI framework is proposed to automate data extraction, safety surveillance, and future trial design support.

## Data Mapping (14 Trials)
| # | Trial ID | Area | Goal | Data Assets |
|---|---|---|---|---|
| 1 | NER1006-03-2014 (DAYB) | Bowel | vs SP+MS, day-before | efficacy, safety |
| 2 | NER1006-02-2014 (MORA) | Bowel | vs MOVIPREP® | efficacy, safety |
| 3 | NER1006-01/2014 (NOCT) | Bowel | vs Trisulfate | efficacy, safety |
| 4 | NRL972_CFLD | Liver | CF diagnostic value | pilot data |
| 5 | NRL972_IVCO | Liver | IV PK (5/15 mg/h) | PK curves |
| 6 | NRL972 PK | Liver | CTP vs PK in cirrhosis | reproducibility |
| 7 | NRL972 (IN-X) | Liver | CYP450 interactions | metabolic data |
| 8 | NRL972 (CIR) PK | Liver | Severity vs PK | severity data |
| 9 | NRL972_ETOH | Liver | Alcohol withdrawal | clearance rates |
| 10 | NRL972_IV | Liver | Healthy volunteer PK | baseline PK |
| 11 | NRL972 VOLT | Liver | Volume/time effects | PK impact |
| 12 | NRL972 QTC | Liver | QTc (2/10 mg) | ECG, placebo |
| 13 | NRL972 KENDLE | Liver | Plasma clearance | cirrhosis dosing |
| 14 | NRL994-01/2007 (GLO) | Bowel | KLEAN-PREP vs MOVIPREP | scintigraphy |

## AI Outputs (Examples)
- **NLP Extraction:** PDF → JSON (`{"trial_id":"NER1006-DAYB","phase":"III","n":350,"safety_alerts":0}`)
- **Safety Dashboard:** AE rate por ensayo/dosis, PK variability (healthy vs cirrhosis)
- **Predictive Models:** QTc prolongation probability, efficacy/safety outcomes

## Pipeline ETL (Proposed)
1. **Ingest:** Download 14 PDFs/HTMLs
2. **Parse:** PyMuPDF / Unstructured
3. **Enrich:** LLM API (structured prompts)
4. **Store:** CSV / SQLite
5. **Visualize:** Power BI / Looker / Tableau

## Next Steps
1. Generate executive summary PDF (ES + EN)
2. Build ETL prototype (Python)
3. Design BI dashboard mockup
