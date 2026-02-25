import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

MAIL_SERVER   = os.getenv("MAIL_SERVER", "sandbox.smtp.mailtrap.io")
MAIL_PORT     = int(os.getenv("MAIL_PORT", 587))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM     = os.getenv("MAIL_FROM", "noreply@resumeai.com")
FRONTEND_URL  = os.getenv("FRONTEND_URL", "http://localhost")


def send_verification_email(to_email: str, name: str, token: str):
    verify_url = f"{FRONTEND_URL}/verify-email.html?token={token}"

    # ── HTML email body ──
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'DM Sans', Arial, sans-serif; background: #f5f5f2; margin: 0; padding: 40px 20px;">
      <div style="max-width: 520px; margin: 0 auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header -->
        <div style="background: #1a6b4a; padding: 32px 40px;">
          <h1 style="color: #fff; margin: 0; font-size: 1.5rem; letter-spacing: -0.02em;">ResumeAI</h1>
          <p style="color: rgba(255,255,255,0.75); margin: 4px 0 0; font-size: 0.88rem;">Verify your email address</p>
        </div>

        <!-- Body -->
        <div style="padding: 36px 40px;">
          <p style="color: #1a1a1a; font-size: 1rem; margin: 0 0 12px;">Hi {name},</p>
          <p style="color: #6b6b6b; font-size: 0.92rem; line-height: 1.7; margin: 0 0 28px;">
            Thanks for signing up for ResumeAI. Click the button below to verify your email address and activate your account.
          </p>

          <a href="{verify_url}"
             style="display: inline-block; background: #1a6b4a; color: #fff; padding: 13px 28px;
                    border-radius: 9px; text-decoration: none; font-weight: 600; font-size: 0.95rem;">
            Verify my email →
          </a>

          <p style="color: #aaa; font-size: 0.78rem; margin: 24px 0 0; line-height: 1.6;">
            This link expires in <strong>24 hours</strong>. If you didn't create an account, you can safely ignore this email.
          </p>
        </div>

        <!-- Footer -->
        <div style="padding: 20px 40px; border-top: 1px solid #e4e4e0; background: #f5f5f2;">
          <p style="color: #aaa; font-size: 0.75rem; margin: 0;">
            Or copy this link into your browser:<br />
            <span style="color: #1a6b4a; word-break: break-all;">{verify_url}</span>
          </p>
        </div>

      </div>
    </body>
    </html>
    """

    # ── Plain text fallback ──
    text = f"""
Hi {name},

Please verify your ResumeAI account by clicking this link:
{verify_url}

This link expires in 24 hours.

If you didn't create an account, ignore this email.
    """

    # ── Build message ──
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify your ResumeAI account"
    msg["From"]    = f"ResumeAI <{MAIL_FROM}>"
    msg["To"]      = to_email

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    # ── Send via SMTP ──
    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, to_email, msg.as_string())
        print(f"[email] Verification email sent to {to_email}")
    except Exception as e:
        print(f"[email] Failed to send email to {to_email}: {e}")
        raise
