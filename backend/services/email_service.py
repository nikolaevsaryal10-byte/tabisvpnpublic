import sys
import ssl
import smtplib
import socket
from typing import Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM

def send_email_otp(to_email: str, code: str, subject: Optional[str] = None) -> bool:
    """
    Sends 6-digit OTP code to the user via Gmail SMTP.
    Forces IPv4 resolution if possible.
    """
    if not subject:
        subject = f"Код входа Tabis VPN: {code}"
    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background-color: #f9f9f7; padding: 24px; color: #121416;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border: 1px solid #121416; padding: 32px;">
    <div style="font-family: monospace; font-size: 13px; font-weight: bold; background: #121416; color: #ffffff; display: inline-block; padding: 4px 10px; margin-bottom: 20px;">
      ТАБЫС // TABIS VPN
    </div>
    <h2 style="margin: 0 0 16px 0; font-size: 22px; color: #121416;">Код подтверждения</h2>
    <p style="font-size: 14px; color: #6c727a; line-height: 1.5; margin-bottom: 24px;">
      Используйте данный 6-значный одноразовый код для входа или регистрации в личном кабинете:
    </p>
    <div style="background: #f4f4f2; border: 1px solid #e2e3e1; padding: 16px; text-align: center; font-family: monospace; font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #089aff; margin-bottom: 24px;">
      {code}
    </div>
    <p style="font-size: 12px; color: #8f959e; font-family: monospace;">
      Код действует в течение 10 минут. Если вы не запрашивали этот код, просто проигнорируйте письмо.
    </p>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(f"Ваш код подтверждения для входа в Tabis VPN: {code}", "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    orig_getaddrinfo = socket.getaddrinfo
    try:
        def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
            return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        socket.getaddrinfo = getaddrinfo_ipv4

        if SMTP_PORT == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=4) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=4) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [to_email], msg.as_string())
        print(f"[SMTP] Successfully delivered OTP to {to_email}")
        return True
    except Exception as e:
        print(f"[SMTP WARNING] Direct delivery failed: {e}. OTP for {to_email}: {code}", file=sys.stderr)
        return False
    finally:
        socket.getaddrinfo = orig_getaddrinfo
