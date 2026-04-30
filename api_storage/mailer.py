"""
mailer.py — Async Mailjet wrapper for transactional emails.

Why Mailjet?
  - Send API v3.1: simple JSON, HTTP Basic Auth (api_key : secret_key)
  - Generous free tier; works without a verified custom domain provided the
    sender address has been verified in the Mailjet dashboard.

Reference: https://dev.mailjet.com/email/guides/send-api-v31/

Configuration (env vars)
  MAIL_JET_API_KEY        — public API key
  MAIL_JET_SECRET_KEY     — secret API key
  MAILJET_FROM_EMAIL      — verified sender (default: jag.space.hashwhiskey@gmail.com)
  MAILJET_FROM_NAME       — display name in the From header (default: OmnesVident)
"""

from __future__ import annotations

import html
import logging
import os
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

MAILJET_API_KEY    = os.getenv("MAIL_JET_API_KEY", "")
MAILJET_SECRET_KEY = os.getenv("MAIL_JET_SECRET_KEY", "")
MAILJET_SEND_URL   = "https://api.mailjet.com/v3.1/send"
DEFAULT_FROM_EMAIL = os.getenv("MAILJET_FROM_EMAIL", "jag.space.hashwhiskey@gmail.com")
DEFAULT_FROM_NAME  = os.getenv("MAILJET_FROM_NAME",  "OmnesVident")


def _mailjet_configured() -> bool:
    return bool(MAILJET_API_KEY and MAILJET_SECRET_KEY)


# ─── Generic send helper ─────────────────────────────────────────────────────

async def send_email(
    *,
    to_email: str,
    to_name:  str,
    subject:  str,
    html_body: str,
    text_body: str,
) -> Tuple[bool, Optional[str]]:
    """
    Send a single email via Mailjet's Send API v3.1.

    Returns (ok, error_message). On success, error_message is None.
    The function never raises — callers can branch on `ok`.
    """
    if not _mailjet_configured():
        return False, "Mailjet is not configured (MAIL_JET_API_KEY / MAIL_JET_SECRET_KEY missing)."

    payload = {
        "Messages": [
            {
                "From":     {"Email": DEFAULT_FROM_EMAIL, "Name": DEFAULT_FROM_NAME},
                "To":       [{"Email": to_email, "Name": to_name}],
                "Subject":  subject,
                "TextPart": text_body,
                "HTMLPart": html_body,
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                MAILJET_SEND_URL,
                json=payload,
                auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
                headers={"Content-Type": "application/json"},
            )
            if r.status_code >= 400:
                logger.warning(
                    "Mailjet send failed (%s) for %s — %s",
                    r.status_code, to_email, r.text[:300],
                )
                return False, f"Mailjet returned HTTP {r.status_code}"
            logger.info("Mailjet send OK for %s (status %s)", to_email, r.status_code)
            return True, None
    except Exception as exc:
        logger.error("Mailjet send raised for %s: %s", to_email, exc)
        return False, str(exc)


# ─── Template: password reset ────────────────────────────────────────────────

def render_reset_password_email(
    name: str,
    email: str,
    reset_url: str,
) -> Tuple[str, str, str]:
    """
    Build the (subject, html_body, text_body) tuple for a password-reset email.
    All user-supplied values are HTML-escaped before interpolation into the
    HTML body. The reset_url is intentionally rendered as-is in `text_body`
    since it's the link the user must click.
    """
    safe_name  = html.escape(name or "there")
    safe_email = html.escape(email)
    safe_url   = html.escape(reset_url, quote=True)

    subject = "Reset your OmnesVident password"

    text_body = (
        f"Hi {name or 'there'},\n\n"
        f"Someone (hopefully you) requested a password reset for your\n"
        f"OmnesVident account at {email}.\n\n"
        f"To set a new password, open this link within 1 hour:\n\n"
        f"  {reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email —\n"
        f"your password won't change.\n\n"
        f"— Team OmnesVident\n"
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Reset your OmnesVident password</title></head>
<body style="margin:0;padding:0;background:#06060f;font-family:'Helvetica Neue',Arial,sans-serif;color:#e2e8f0;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#06060f;">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0" style="background:#0d0d1a;border:1px solid #2a2a50;border-radius:14px;overflow:hidden;max-width:560px;">

          <tr>
            <td align="center" style="padding:28px 28px 16px;border-bottom:1px solid #1c1c38;">
              <img src="https://frontendportal-nine.vercel.app/logo-icon.png"
                   alt="OmnesVident" width="48" height="48"
                   style="display:block;margin:0 auto 8px;">
              <div style="font-size:14px;font-weight:700;letter-spacing:0.04em;color:#22d3ee;">
                Omnes<span style="color:#fff;">Vident</span>
              </div>
              <div style="font-size:10px;color:#64748b;font-family:monospace;letter-spacing:0.1em;text-transform:uppercase;">
                Global News Discovery
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:28px;">
              <h1 style="margin:0 0 16px;font-size:18px;color:#f1f5f9;font-weight:700;">Reset your password</h1>
              <p style="margin:0 0 16px;font-size:14px;line-height:1.55;color:#cbd5e1;">
                Hi {safe_name},
              </p>
              <p style="margin:0 0 24px;font-size:14px;line-height:1.55;color:#cbd5e1;">
                Someone (hopefully you) requested a password reset for your
                OmnesVident account at <span style="color:#22d3ee;">{safe_email}</span>.
                Click the button below to set a new password.
              </p>

              <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
                <tr>
                  <td bgcolor="#22d3ee" style="border-radius:8px;">
                    <a href="{safe_url}"
                       style="display:inline-block;padding:12px 28px;font-size:13px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#0f0f23;text-decoration:none;border-radius:8px;">
                      Reset password
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 8px;font-size:11px;color:#64748b;line-height:1.5;">Or paste this link into your browser:</p>
              <p style="margin:0 0 24px;font-size:11px;color:#22d3ee;word-break:break-all;font-family:monospace;">
                <a href="{safe_url}" style="color:#22d3ee;text-decoration:none;">{safe_url}</a>
              </p>

              <p style="margin:0 0 8px;font-size:11px;color:#94a3b8;line-height:1.55;">
                <strong style="color:#f1f5f9;">This link expires in 1 hour</strong>
                and can only be used once. If you didn't request a reset, you can
                safely ignore this email — your password won't change.
              </p>
            </td>
          </tr>

          <tr>
            <td align="center" style="padding:20px 28px;border-top:1px solid #1c1c38;background:#08081a;">
              <p style="margin:0;font-size:10px;color:#475569;line-height:1.5;font-family:monospace;letter-spacing:0.04em;">
                Sent from OmnesVident · {html.escape(DEFAULT_FROM_EMAIL)}
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return subject, html_body, text_body
