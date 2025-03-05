import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()

smtp_email = os.getenv('SMTP_EMAIL')
smtp_password = os.getenv('SMTP_PASSWORD')

def send_email(to_email, subject, message):
    """Send an email notification using SMTP."""
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        if not smtp_email or not smtp_password:
            print("SMTP credentials not configured.")
            return False

        msg = MIMEMultipart()
        msg["From"] = smtp_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()

        print(f"Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def send_sms(to_phone, message):
    """Placeholder for sending SMS notifications."""
    print(f"SMS to {to_phone}: {message}")
    return True

