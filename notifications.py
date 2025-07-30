import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sqlite3
try:
    from dotenv import load_dotenv
    load_dotenv()    # read .env into os.environ
except ImportError:
    print("python-dotenv not installed; skipping .env load")



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

# def send_low_stock_summary(to_email: str) -> bool:
#     """
#     Query for items whose on_hand ≤ reorder_threshold,
#     build a plain-text list, and e-mail it.
#     """
#     conn = sqlite3.connect("vet_management.db")
#     cur = conn.cursor()
#     cur.execute("""
#       SELECT name, on_hand, reorder_threshold
#         FROM items
#        WHERE on_hand <= reorder_threshold
#     """)
#     rows = cur.fetchall()
#     conn.close()
#
#     if not rows:
#         # nothing to report
#         return False
#
#     lines = ["Low-Stock Alert:", ""]
#     for name, on_hand, thr in rows:
#         lines.append(f" • {name:20} on_hand={on_hand:3}  reorder_threshold={thr}")
#
#     body = "\n".join(lines)
#     subject = "🐾 Daily Low-Stock Summary"
#     return send_email(to_email, subject, body)
