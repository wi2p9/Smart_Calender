from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# MongoDB Setup (local or remote MongoDB)
client = MongoClient('mongodb://localhost:27017/')  # Change to your MongoDB URI
db = client["smartcalender"]
events_collection = db["cal_rem"]

reminders = []
# Global list to hold reminder messages for frontend
active_reminder_messages = []

# Email configuration from environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"  # Gmail SMTP server
SMTP_PORT = 587  # Gmail SMTP port for TLS

def send_email(to_email, subject, body):
    try:
        # Create the email
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject

        # Attach the body of the email
        msg.attach(MIMEText(body, "plain"))

        # Connect to the SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Enable TLS
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)  # Login to the SMTP server

        # Send the email
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()

        print(f"Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

def reminder_checker():
    while True:
        now = datetime.now()
        for event in reminders:
            if not event["sent"] and event["trigger_time"].strftime("%Y-%m-%d %H:%M") == now.strftime("%Y-%m-%d %H:%M"):
                # Create the reminder message
                msg = (
                    f"Hi {event['name']},\n"
                    f"🔔 Reminder:\n"
                    f"Event: {event['event_name']}\n"
                    f"Venue: {event['venue']}\n"
                    f"Date & Time: {event['event_datetime'].strftime('%Y-%m-%d %H:%M')}\n"
                    f"Description: {event['description']}\n"
                )
                print(msg)

                # Send email to the user
                email_subject = f"Reminder: {event['event_name']}"
                email_body = msg
                send_email(event["email"], email_subject, email_body)

                # Add to active reminders for frontend
                active_reminder_messages.append({
                    "name": event["name"],
                    "event_name": event['event_name'],
                    "event_datetime": event["event_datetime"].strftime('%Y-%m-%d %H:%M'),
                    "venue": event["venue"],
                    "description": event["description"],
                    "reminder_time": event["trigger_time"].strftime('%Y-%m-%d %H:%M'),
                    "email": event["email"]
                })

                event["sent"] = True
        time.sleep(10)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", message=None)

@app.route("/set_reminder", methods=["POST"])
def set_reminder():
    name = request.form["name"]
    email = request.form.get("email")
    event_name = request.form["event_name"]
    event_date = request.form["event_date"]
    event_time = request.form["event_time"]
    venue = request.form["venue"]
    description = request.form["description"]
    reminder_minutes = int(request.form["reminder_minutes"])

    # Parse the input
    event_datetime = datetime.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")
    reminder_time = event_datetime - timedelta(minutes=reminder_minutes)

    # Store event in MongoDB
    event_data = {
        "name": name,
        "email": email,
        "event_name": event_name,
        "event_datetime": event_datetime,
        "venue": venue,
        "description": description,
        "reminder_time": reminder_time,
        "sent": False
    }
    events_collection.insert_one(event_data)

    # Add to reminder list
    reminders.append({
        "name": name,
        "email": email,
        "event_name": event_name,
        "trigger_time": reminder_time,
        "sent": False,
        "venue": venue,
        "description": description,
        "event_datetime": event_datetime
    })

    return render_template("index.html", message="Reminder has been set!")

@app.route("/get_reminder")
def get_reminder():
    return jsonify(active_reminder_messages)

if __name__ == "__main__":
    threading.Thread(target=reminder_checker, daemon=True).start()
    app.run(debug=True)