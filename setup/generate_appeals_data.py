#!/usr/bin/env python3
"""
Synthetic appeals & grievances data generator for the Lakebase Search demo.

Reskin of the BakeReview seeder: (franchise, review) -> (plan, case). Writes
data/plans.csv (~10) and data/cases.csv (800). The `narrative` is the searchable
free text, composed from many randomized clauses so **every case is essentially
unique** (no duplicate narratives -> distinct embeddings -> a real search demo).

Hybrid story: the structured code columns (CARC/CPT/ICD) give BM25 exact-token
hits, while the member's paraphrased language gives vector semantic recall.

Deterministic (fixed seed). Stdlib only.
"""
import csv, os, random
from datetime import date, timedelta

SEED = 20260910
random.seed(SEED)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)
N_CASES = 800

PLANS = [
    ("PLN-01", "BluePeak Health",       "Medicare Advantage", "WA", "Pacific Northwest"),
    ("PLN-02", "Cascade Care",          "Medicaid",           "OR", "Pacific Northwest"),
    ("PLN-03", "Evergreen Health Plan",  "Commercial",         "CA", "West"),
    ("PLN-04", "Summit Advantage",       "Medicare Advantage", "CO", "Mountain"),
    ("PLN-05", "Harbor Health",          "ACA Marketplace",    "TX", "South"),
    ("PLN-06", "Lakeshore Medicaid",     "Medicaid",           "IL", "Midwest"),
    ("PLN-07", "Keystone Care",          "Commercial",         "PA", "Northeast"),
    ("PLN-08", "Sunbelt D-SNP",          "D-SNP",              "FL", "South"),
    ("PLN-09", "Gateway Health Plan",    "ACA Marketplace",    "MO", "Midwest"),
    ("PLN-10", "Liberty Advantage",      "Medicare Advantage", "NY", "Northeast"),
]

CARC = {
    "auth_absent":  ("CO-197", "Precertification/authorization absent"),
    "not_med_nec":  ("CO-50",  "Not deemed medically necessary"),
    "non_covered":  ("CO-96",  "Non-covered charge(s)"),
    "exceeds_fee":  ("CO-45",  "Charge exceeds fee schedule"),
    "missing_info": ("CO-16",  "Claim lacks information"),
    "experimental": ("CO-55",  "Procedure/treatment is experimental/investigational"),
    "oon":          ("CO-242", "Services not provided by network provider"),
    "step_therapy": ("CO-198", "Precertification/step therapy requirement not met"),
    "none":         ("N/A",    "Not applicable (grievance)"),
}

# Per category: item(s) denied, a clinical reason/justification, and a consequence.
# Narratives are composed from these pools + connectors + member refs, so the
# number of distinct narratives per category is in the thousands.
CATEGORIES = [
    {
        "name": "Specialty Pharmacy (Rx)",
        "cpt": ["J1745", "J3380", "J2350", "J0178", "J9299"],
        "icd": ["K50.90", "M05.79", "L40.9", "G35", "C50.911"],
        "denials": ["step_therapy", "not_med_nec", "non_covered", "auth_absent"],
        "items": ["their biologic infusion", "adalimumab", "the specialty drug ocrelizumab",
                  "their monoclonal antibody therapy", "secukinumab", "a targeted DMARD",
                  "their maintenance biologic"],
        "reasons": ["they have been stable on it for over a year",
                    "prior formulary agents were tried and failed",
                    "the rheumatologist documented contraindications to alternatives",
                    "their disease is actively progressing on the current regimen",
                    "the prescriber submitted peer-reviewed support for the therapy"],
        "impacts": ["interrupting therapy risks a flare that could land them in the hospital",
                    "they have already missed two scheduled doses and symptoms are returning",
                    "without it their inflammation is no longer controlled",
                    "the delay is undoing months of clinical progress"],
    },
    {
        "name": "Behavioral Health",
        "cpt": ["90837", "H0015", "90853", "H2036", "90791"],
        "icd": ["F33.1", "F41.1", "F10.20", "F31.9", "F43.10"],
        "denials": ["not_med_nec", "auth_absent", "oon", "none"],
        "items": ["continued residential substance-use treatment", "an intensive outpatient program",
                  "additional therapy sessions", "a partial hospitalization step-down",
                  "ongoing trauma-focused therapy", "inpatient psychiatric stabilization"],
        "reasons": ["the care team warns that discharging now would likely trigger relapse",
                    "the member is still reporting thoughts of self-harm",
                    "the treating clinician documented ongoing severe symptoms",
                    "the only in-network provider has a three month wait",
                    "the member needs more time to stabilize safely"],
        "impacts": ["they are not safe to step down to a lower level of care",
                    "cutting care short now puts their recovery at serious risk",
                    "they have nowhere else to turn for this level of support",
                    "the gap in treatment is destabilizing their condition"],
    },
    {
        "name": "Imaging / Radiology",
        "cpt": ["70553", "72148", "74177", "78815", "71271"],
        "icd": ["R51.9", "M54.5", "R10.9", "C80.1", "R91.8"],
        "denials": ["auth_absent", "not_med_nec", "missing_info"],
        "items": ["an MRI of the brain", "a lumbar spine MRI", "a staging CT scan",
                  "a follow-up PET scan", "a CT of the abdomen"],
        "reasons": ["the neurologist ordered it for worsening headaches and new visual symptoms",
                    "the oncologist needs it to choose the next line of treatment",
                    "conservative care and physical therapy failed over three months",
                    "the ER physician recommended it after a fall",
                    "there is concern the mass has grown since the last scan"],
        "impacts": ["they cannot get answers about a possible fracture and are in severe pain",
                    "the delay is holding up a time-critical cancer treatment decision",
                    "surgery is on hold until the imaging is done",
                    "their symptoms are escalating while the review drags on"],
    },
    {
        "name": "Durable Medical Equipment",
        "cpt": ["E0601", "K0823", "E1390", "E0470", "L1960"],
        "icd": ["G47.33", "I50.9", "J96.11", "M21.371", "G82.20"],
        "denials": ["non_covered", "not_med_nec", "missing_info", "auth_absent"],
        "items": ["a power wheelchair", "a CPAP machine", "a home oxygen concentrator",
                  "a custom ankle-foot orthosis", "a hospital bed", "a mobility scooter"],
        "reasons": ["the physician documented severe mobility loss at home",
                    "the sleep study confirmed significant apnea",
                    "the pulmonologist recorded dangerously low oxygen readings",
                    "the member cannot safely transfer or ambulate without it",
                    "their prior equipment broke and cannot be repaired"],
        "impacts": ["they have already fallen twice and cannot move around their home safely",
                    "they are exhausted, untreated, and unsafe to drive",
                    "they are effectively housebound without it",
                    "their independence and safety at home are at risk"],
    },
    {
        "name": "Emergency / ER",
        "cpt": ["99284", "99285", "99283", "G0390", "99291"],
        "icd": ["R07.9", "I21.4", "R55", "K35.80", "S06.0X0A"],
        "denials": ["non_covered", "oon", "missing_info"],
        "items": ["their emergency room visit", "the ER claim", "the ambulance and ER charges"],
        "reasons": ["they arrived with crushing chest pain",
                    "they had severe abdominal pain that turned out to be appendicitis",
                    "they were unconscious and the ambulance chose the nearest hospital",
                    "they experienced a sudden fainting episode",
                    "a reasonable person would have considered the symptoms an emergency"],
        "impacts": ["denying it as 'not an emergency' after the fact feels unfair",
                    "the plan says it should have been urgent care, but there was no time",
                    "they are being billed thousands for a genuine emergency",
                    "the prudent-layperson standard clearly applied"],
    },
    {
        "name": "Surgery",
        "cpt": ["27447", "22630", "47562", "29881", "63030"],
        "icd": ["M17.11", "M51.36", "K80.20", "M23.205", "M48.06"],
        "denials": ["not_med_nec", "auth_absent", "experimental", "step_therapy"],
        "items": ["a total knee replacement", "a lumbar decompression", "gallbladder removal",
                  "an arthroscopic knee repair", "a spinal fusion"],
        "reasons": ["they have bone-on-bone arthritis and can barely walk a block",
                    "nerve compression is causing numbness and weakness in the leg",
                    "injections and therapy have not relieved the pain",
                    "the surgeon says it should not be delayed further",
                    "painful attacks keep recurring after eating"],
        "impacts": ["their mobility and quality of life keep deteriorating",
                    "they are in constant pain waiting for approval",
                    "the condition is worsening the longer surgery is postponed",
                    "they cannot work or sleep because of the pain"],
    },
    {
        "name": "Physical Therapy",
        "cpt": ["97110", "97140", "97530", "97112", "97161"],
        "icd": ["M54.5", "M25.551", "S83.511A", "I69.351", "M62.81"],
        "denials": ["not_med_nec", "none", "missing_info"],
        "items": ["continued physical therapy", "additional rehab visits",
                  "post-surgical knee rehabilitation", "post-stroke therapy",
                  "ongoing back-pain therapy"],
        "reasons": ["the therapist documents they are still making functional gains",
                    "they still cannot fully bend the joint after surgery",
                    "therapy is what keeps them working without opioids",
                    "recovery after the stroke is ongoing and measurable",
                    "authorization keeps lapsing between approvals"],
        "impacts": ["they lose progress every time coverage is interrupted",
                    "they were cut off after being told they had 'plateaued'",
                    "the visit limit was reached before recovery was complete",
                    "their function is regressing without continued therapy"],
    },
    {
        "name": "Out-of-Network / Access",
        "cpt": ["99205", "99215", "99244", "99354", "99417"],
        "icd": ["C50.912", "D57.1", "E10.9", "G20", "C71.9"],
        "denials": ["oon", "non_covered", "auth_absent"],
        "items": ["an out-of-network specialist visit", "continued care with their oncologist",
                  "a pediatric subspecialist visit", "an out-of-area expert consult"],
        "reasons": ["there is no in-network specialist within a hundred miles for their rare condition",
                    "the doctor who has managed their cancer for years left the network mid-treatment",
                    "the nearest in-network pediatric specialist has no openings for months",
                    "the provider directory listed a doctor as in-network who was not"],
        "impacts": ["continuity of care was denied and they are stuck with a large bill",
                    "they had no realistic in-network option and went out of network",
                    "interrupting this specialist relationship is medically dangerous",
                    "they are being penalized for the plan's inaccurate directory"],
    },
    {
        "name": "Skilled Nursing / Post-Acute",
        "cpt": ["99304", "99306", "G0299", "99315", "T1030"],
        "icd": ["Z51.5", "S72.001A", "I63.9", "J18.9", "Z48.01"],
        "denials": ["not_med_nec", "auth_absent", "missing_info"],
        "items": ["a skilled nursing stay", "continued rehab facility coverage",
                  "home health nursing visits", "post-acute recovery care"],
        "reasons": ["they were just discharged after a hip fracture and live alone",
                    "they still cannot safely transfer or manage medications after a stroke",
                    "they need wound care they cannot perform themselves",
                    "the discharge feels premature and unsafe"],
        "impacts": ["sending them home now is not safe without help",
                    "the family cannot provide the level of care required",
                    "recovery will stall or reverse without skilled support",
                    "they are at high risk of readmission"],
    },
    {
        "name": "Maternity / Newborn",
        "cpt": ["59400", "59510", "99460", "76805", "59025"],
        "icd": ["Z34.90", "O80", "P07.30", "O24.419", "Z38.00"],
        "denials": ["missing_info", "non_covered", "none"],
        "items": ["extra prenatal ultrasounds", "the newborn's additional nursery days",
                  "a longer hospital stay after a cesarean", "postpartum care visits"],
        "reasons": ["the pregnancy is high risk with gestational diabetes",
                    "the pediatrician needed to monitor the newborn after a difficult delivery",
                    "the mother had documented recovery complications",
                    "she is dealing with complications after birth"],
        "impacts": ["denying the monitoring puts mother and baby at risk",
                    "the family is being billed for medically necessary newborn care",
                    "she cannot get the postpartum follow-up she needs",
                    "the coverage decision ignores the documented complications"],
    },
]

DENIAL_VERB = {
    "auth_absent":  "was denied for lack of prior authorization",
    "not_med_nec":  "was denied as not medically necessary",
    "non_covered":  "was denied as a non-covered service",
    "exceeds_fee":  "was only partially paid, below the billed amount",
    "missing_info": "was denied pending additional documentation",
    "experimental": "was denied as experimental or investigational",
    "oon":          "was denied as out-of-network",
    "step_therapy": "was denied until a cheaper alternative is tried first",
    "none":         "is the subject of this complaint",
}

FIRST = ["James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David", "Jennifer",
         "William", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
         "Charles", "Karen", "Chen", "Aisha", "Miguel", "Fatima", "Devon", "Priya", "Omar",
         "Grace", "Hector", "Nadia", "Samuel", "Yuki"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Martinez", "Nguyen", "Patel", "Kim", "Okafor", "Hernandez", "Lee",
        "Walker", "Young", "Ahmed", "Torres", "Reyes", "Cohen", "Singh", "Baker"]

SUBJECT = ["The member", "Our member", "The patient", "My client", "This member"]


def make_narrative(cat, denial_key):
    subj = random.choice(SUBJECT)
    item = random.choice(cat["items"])
    reason = random.choice(cat["reasons"])
    impact = random.choice(cat["impacts"])
    verb = DENIAL_VERB[denial_key]
    connectors = [
        f"{subj}'s request for {item} {verb}. Even though {reason}, the decision stood, and {impact}.",
        f"{item.capitalize()} {verb}. {reason.capitalize()}, yet the plan upheld the denial, and {impact}.",
        f"{subj} is appealing because {item} {verb}. {reason.capitalize()}; {impact}.",
        f"{reason.capitalize()}, but {item} {verb}. {subj.lower() if subj[0].isupper() else subj} reports that {impact}.",
        f"{subj} disputes that {item} {verb}. The record shows {reason}, and {impact}.",
    ]
    return random.choice(connectors)


def gen():
    with open(os.path.join(OUT_DIR, "plans.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["plan_id", "plan_name", "line_of_business", "state", "region"])
        for p in PLANS:
            w.writerow(p)

    start = date(2025, 1, 1)
    rows = []
    for i in range(1, N_CASES + 1):
        cat = random.choice(CATEGORIES)
        denial_key = random.choice(cat["denials"])
        code, reason = CARC[denial_key]
        case_type = "Grievance" if denial_key == "none" else \
            ("Grievance" if random.random() < 0.18 else "Appeal")
        if case_type == "Grievance":
            if denial_key != "none":
                denial_key_for_text = denial_key
            else:
                denial_key_for_text = "none"
            code, reason = (CARC["none"] if denial_key == "none" else (code, reason))
            disposition = random.choice(["Resolved", "Substantiated", "Unsubstantiated", "Pending"])
        else:
            denial_key_for_text = denial_key
            disposition = random.choices(
                ["Upheld", "Overturned", "Partially Overturned", "Pending"],
                weights=[40, 30, 15, 15])[0]
        plan = random.choice(PLANS)
        filed = start + timedelta(days=random.randint(0, 250))
        rows.append([
            f"CASE-{i:06d}", plan[0], case_type, f"MBR-{random.randint(100000, 999999)}",
            f"{random.choice(FIRST)} {random.choice(LAST)}", filed.isoformat(),
            cat["name"], code, reason, random.choice(cat["cpt"]), random.choice(cat["icd"]),
            disposition, make_narrative(cat, denial_key_for_text),
        ])

    with open(os.path.join(OUT_DIR, "cases.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "plan_id", "case_type", "member_id", "member_name", "filed_date",
                    "service_category", "denial_reason_code", "denial_reason_desc",
                    "cpt_hcpcs_code", "icd10_code", "disposition", "narrative"])
        w.writerows(rows)

    uniq = len(set(r[-1] for r in rows))
    print(f"Wrote {len(PLANS)} plans, {len(rows)} cases; unique narratives: {uniq}/{len(rows)}")


if __name__ == "__main__":
    gen()
