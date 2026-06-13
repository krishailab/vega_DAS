import smtplib
from email.message import EmailMessage
import io

SMTP_SERVER = "mail.motocrossindia.in"
SMTP_PORT = 465
SMTP_USER = "krish@motocrossindia.in"
SMTP_PASS = "Krish123@"

def send_po_email(to_email: str, subject: str, body: str, pdf_buffer: io.BytesIO, filename: str):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    
    msg.set_content(body)
    
    # Attach PDF
    pdf_bytes = pdf_buffer.getvalue()
    msg.add_attachment(
        pdf_bytes,
        maintype='application',
        subtype='pdf',
        filename=filename
    )
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            print(f"Successfully sent PO email to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")

def send_signup_approval_email(to_email: str, contact_name: str, password: str):
    msg = EmailMessage()
    msg['Subject'] = "Dealer Account Approved - Welcome to Classic Helmets "
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    
    body = f"""Dear {contact_name},

Congratulations! Your signup request has been approved.

Your login credentials are:
Email/Username: {to_email}
Password: {password}

You can login and access the dealer dashboard now.

Thank you,
Vega Auto Accessories Ltd."""
    
    msg.set_content(body)
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            print(f"Successfully sent signup approval email to {to_email}")
    except Exception as e:
        print(f"Failed to send signup approval email to {to_email}: {e}")
