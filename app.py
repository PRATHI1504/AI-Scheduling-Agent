import os
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from dateutil import parser as dateparser

# ----------------------------
# CONFIG
# ----------------------------
PATIENTS_CSV = "patients.csv"
SCHEDULE_XLSX = "doctor_schedules.xlsx"
APPTS_EXPORT_XLSX = "appointments_export.xlsx"
COMM_LOG_CSV = "communications_log.csv"

# ----------------------------
# UTILITIES
# ----------------------------
def ensure_seed_data():
    """Create patients DB and doctor schedules if not exist"""
    if not os.path.exists(PATIENTS_CSV):
        rows = []
        base = datetime(1990, 1, 1)
        for i in range(1, 11):
            rows.append({
                "patient_id": f"P{i:03d}",
                "name": f"Test Patient {i}",
                "dob": (base + timedelta(days=i*200)).strftime("%Y-%m-%d"),
                "email": f"patient{i}@example.com",
                "phone": f"+91-90000000{i:02d}",
                "insurance_carrier": "Acme Health",
                "insurance_member_id": f"ACME-{10000+i}",
                "insurance_group": "GRP-01"
            })
        pd.DataFrame(rows).to_csv(PATIENTS_CSV, index=False)

    if not os.path.exists(SCHEDULE_XLSX):
        days = [datetime.now().date() + timedelta(days=d) for d in range(0, 7)]
        doctors = [
            {"doctor": "Dr. Rao", "location": "Main Clinic"},
            {"doctor": "Dr. Iyer", "location": "Downtown"},
            {"doctor": "Dr. Mehta", "location": "Uptown"},
        ]
        slots = []
        for d in doctors:
            for day in days:
                start = datetime.combine(day, datetime.min.time()) + timedelta(hours=9)
                for k in range(16):  # 9:00 to 17:00 in 30-min slots
                    s = start + timedelta(minutes=30*k)
                    e = s + timedelta(minutes=30)
                    slots.append({
                        "doctor": d["doctor"],
                        "location": d["location"],
                        "start": s.isoformat(),
                        "end": e.isoformat(),
                        "booked": False,
                        "patient_id": "",
                    })
        pd.DataFrame(slots).to_excel(SCHEDULE_XLSX, index=False)

def load_patients():
    return pd.read_csv(PATIENTS_CSV)

def save_patients(df):
    df.to_csv(PATIENTS_CSV, index=False)

def load_schedule():
    return pd.read_excel(SCHEDULE_XLSX)

def save_schedule(df):
    df.to_excel(SCHEDULE_XLSX, index=False)

def export_appointments(schedule_df):
    booked = schedule_df[schedule_df["booked"] == True].copy()
    if not booked.empty:
        booked.to_excel(APPTS_EXPORT_XLSX, index=False)

def simulate_email_sms(to_email, to_phone, subject, body):
    """Simulate email/SMS by logging into a CSV file."""
    log = {
        "ts": datetime.now().isoformat(),
        "email": to_email,
        "phone": to_phone,
        "subject": subject,
        "body": body[:4000]
    }
    df = pd.DataFrame([log])
    if os.path.exists(COMM_LOG_CSV):
        old = pd.read_csv(COMM_LOG_CSV)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(COMM_LOG_CSV, index=False)

def schedule_reminders(patient, appt_start_iso, doctor, location):
    """Create reminder entries in log for 72h, 24h, and 2h before appointment."""
    t0 = datetime.fromisoformat(appt_start_iso)
    plan = [
        ("Appointment Confirmation", datetime.now(),
         f"Your appointment with {doctor} at {location} is confirmed for {t0.strftime('%Y-%m-%d %H:%M')}."),
        ("Reminder 72h", t0 - timedelta(hours=72),
         f"Reminder: Appointment with {doctor} at {location} on {t0.strftime('%Y-%m-%d %H:%M')}."),
        ("Reminder 24h", t0 - timedelta(hours=24),
         f"Please confirm and complete forms. Appointment with {doctor} at {location} on {t0.strftime('%Y-%m-%d %H:%M')}."),
        ("Reminder 2h", t0 - timedelta(hours=2),
         f"Final reminder: Appointment with {doctor} at {location} at {t0.strftime('%Y-%m-%d %H:%M')}. Reply YES to confirm."),
    ]
    for subject, when, msg in plan:
        simulate_email_sms(patient.get("email",""), patient.get("phone",""), f"[Clinic] {subject}", msg)

def find_or_create_patient(name, dob, email, phone, insurance_carrier, insurance_member_id, insurance_group):
    df = load_patients()
    dob_norm = dateparser.parse(dob).date().strftime("%Y-%m-%d")
    match = df[(df["name"].str.lower() == name.lower()) & (df["dob"] == dob_norm)]
    if not match.empty:
        return match.iloc[0].to_dict(), False
    new_id = f"P{len(df)+1:03d}"
    row = {
        "patient_id": new_id,
        "name": name,
        "dob": dob_norm,
        "email": email,
        "phone": phone,
        "insurance_carrier": insurance_carrier,
        "insurance_member_id": insurance_member_id,
        "insurance_group": insurance_group,
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_patients(df)
    return row, True

def book_appointment(patient, doctor, date_str, time_str, duration_minutes=30):
    schedule = load_schedule()
    date_obj = dateparser.parse(date_str).date()
    time_obj = dateparser.parse(time_str).time()
    start_dt = datetime.combine(date_obj, time_obj)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    mask = (
        (schedule["doctor"] == doctor) &
        (schedule["booked"] == False) &
        (schedule["start"] == start_dt.isoformat())
    )
    if not mask.any():
        return None  # slot not free

    idx = schedule[mask].index[0]
    schedule.loc[idx, "booked"] = True
    schedule.loc[idx, "patient_id"] = patient["patient_id"]

    save_schedule(schedule)
    export_appointments(schedule)
    return {"doctor": doctor, "start": start_dt, "end": end_dt, "location": schedule.loc[idx, "location"]}

# ----------------------------
# STREAMLIT APP
# ----------------------------
st.set_page_config(page_title="AI Scheduling Agent", page_icon="🩺", layout="centered")
st.title("🩺 AI Scheduling Agent — Form Mode with Confirmations")

ensure_seed_data()

# ----------------------------
# PATIENT FORM
# ----------------------------
st.subheader("📝 Patient Information")
with st.form("appointment_form"):
    name = st.text_input("Full Name", placeholder="e.g., Prathiksha S")
    dob = st.text_input("Date of Birth (YYYY-MM-DD)", placeholder="e.g., 2004-11-15")
    email = st.text_input("Email", placeholder="e.g., prathi@example.com")
    phone = st.text_input("Phone", placeholder="e.g., +91-9876543210")
    insurance_carrier = st.text_input("Insurance Carrier", placeholder="e.g., Blue Shield")
    insurance_member_id = st.text_input("Insurance Member ID", placeholder="e.g., 123,124")
    insurance_group = st.text_input("Insurance Group", placeholder="e.g., A1,A2")

    st.subheader("📅 Appointment Request")
    doctor = st.selectbox("Select Doctor", ["Dr. Shyam", "Dr. John", "Dr. Mehta"])
    date_str = st.text_input("Preferred Date", placeholder="e.g., 2025-09-05")
    time_str = st.text_input("Preferred Time (HH:MM)", placeholder="e.g., 09:00")
    duration = st.selectbox("Appointment Duration", [30, 60], index=0)

    submitted = st.form_submit_button("📌 Book Appointment")

if submitted:
    patient, is_new = find_or_create_patient(
        name, dob, email, phone,
        insurance_carrier, insurance_member_id, insurance_group
    )

    booking = book_appointment(
        patient, doctor, date_str, time_str, duration_minutes=duration
    )

    if booking:
        st.success(
            f"✅ Appointment booked with {booking['doctor']} at {booking['location']} "
            f"on {booking['start'].strftime('%Y-%m-%d %H:%M')} "
            f"for {duration} minutes."
        )

        # Send simulated confirmations & reminders
        schedule_reminders(patient, booking["start"].isoformat(), booking["doctor"], booking["location"])
        st.info("📧 Confirmation + reminders logged in communications_log.csv")
    else:
        st.error("❌ Sorry, that slot is not available. Try another time.")

# ----------------------------
# ADMIN DASHBOARD
# ----------------------------
st.subheader("👥 Patients Database")
st.dataframe(load_patients())

st.subheader("📅 Doctor Schedules")
st.dataframe(load_schedule())

st.subheader("✅ Confirmed Appointments")
try:
    booked = pd.read_excel(APPTS_EXPORT_XLSX)
    st.dataframe(booked)
except FileNotFoundError:
    st.info("No appointments booked yet.")

st.subheader("📧 Communications Log (Confirmations & Reminders)")
if os.path.exists(COMM_LOG_CSV):
    comms = pd.read_csv(COMM_LOG_CSV)
    st.dataframe(comms)
else:
    st.info("No communications sent yet.")
