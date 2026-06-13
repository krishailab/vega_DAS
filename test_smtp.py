import smtplib
import traceback

email = "krish@motocrossindia.in"
pwd = "Krish123@"

servers = [
    ("smtp.hostinger.com", 465, True),
    ("smtp.titan.email", 465, True),
    ("smtp.gmail.com", 465, True),
    ("smtp.zoho.in", 465, True),
    ("mail.motocrossindia.in", 465, True)
]

print("Testing SMTP connections...")
for host, port, use_ssl in servers:
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=5)
        else:
            server = smtplib.SMTP(host, port, timeout=5)
            server.starttls()
        
        server.login(email, pwd)
        print(f"SUCCESS with {host}:{port}")
        server.quit()
        break
    except Exception as e:
        print(f"FAILED with {host}:{port} -> {e}")
