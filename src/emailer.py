from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email_html(subject: str, html_body: str) -> None:
    smtp_user = os.environ["GMAIL_SMTP_USER"]
    smtp_password = os.environ["GMAIL_SMTP_APP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = email_to

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [email_to], msg.as_string())
