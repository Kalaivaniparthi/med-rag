"""ntfy.sh push notifications + APScheduler medication reminders."""
from datetime import date, datetime, timedelta

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from core import db

_sched = None  # module globals survive Streamlit reruns


def send_ntfy(title, message, priority="default"):
    """Push to the user's ntfy.sh topic. Returns True on success."""
    try:
        r = requests.post(f"https://ntfy.sh/{db.cfg('NTFY_TOPIC')}", data=message.encode("utf-8"),
                          headers={"Title": title.encode("ascii", "ignore").decode(), "Priority": priority},
                          timeout=10)
        return r.ok
    except requests.RequestException:
        return False


def _remind(med_id, time):
    med = next((m for m in db.meds() if m["id"] == med_id), None)
    today = date.today().isoformat()
    if med and db._active(med, today) and db.dose_status(med_id, time) not in ("taken", "skipped"):
        send_ntfy("Medication reminder", f"Time for {med['name']} ({med['dose']})", "high")


def schedule_medication_reminders(meds):
    """(Re)register one daily cron job per medication time."""
    if _sched is None:
        return
    for job in _sched.get_jobs():
        if job.id.startswith("med:"):
            job.remove()
    for m in meds:
        for t in m["times"]:
            h, mi = (int(x) for x in t.split(":"))
            _sched.add_job(_remind, "cron", hour=h, minute=mi, args=[m["id"], t],
                           id=f"med:{m['id']}:{t}", replace_existing=True)


def snooze(med_id, time, minutes=10):
    db.log_dose(med_id, time, "snoozed")
    if _sched:
        _sched.add_job(_remind, "date", run_date=datetime.now() + timedelta(minutes=minutes), args=[med_id, time])


def start():
    """Start the background scheduler once, and load reminders for all medications."""
    global _sched
    if _sched is None:
        _sched = BackgroundScheduler(daemon=True)
        _sched.start()
    schedule_medication_reminders(db.meds())
