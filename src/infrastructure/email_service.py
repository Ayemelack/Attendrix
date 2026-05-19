import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class EmailDeliveryStatus:
    SENT = "sent"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"


PROVIDER_SMTP = "smtp"
PROVIDER_RESEND = "resend"
PROVIDER_NONE = "none"


def _build_confirmation_html(
    name: str,
    institution: str,
    demo_date: str,
    demo_time: str,
    timezone: str,
    portal_url: str = "",
) -> str:
    portal_section = ""
    if portal_url:
        portal_section = f'''
        <tr>
            <td align="center" style="padding: 0 30px 20px;">
                <a href="{portal_url}" style="display: inline-block; padding: 14px 36px; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: #ffffff; text-decoration: none; border-radius: 12px; font-size: 15px; font-weight: 700; font-family: 'Inter', 'Segoe UI', Arial, sans-serif; letter-spacing: 0.3px;">
                    Enter Demo Preparation Portal
                </a>
            </td>
        </tr>
        <tr>
            <td align="center" style="padding: 0 30px 20px;">
                <p style="margin: 0; font-size: 13px; color: #64748B; font-family: 'Inter', 'Segoe UI', Arial, sans-serif;">
                    <a href="{portal_url}" style="color: #818CF8; text-decoration: none;">Or copy this link to your browser</a>
                </p>
            </td>
        </tr>
        '''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demo Confirmed — Attendrix</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: 'Inter', 'Segoe UI', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F8FAFC; min-height: 100vh;">
        <tr>
            <td align="center" style="padding: 40px 16px;">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">
                    <tr>
                        <td align="center" style="padding: 0 0 24px;">
                            <table cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center" style="width: 44px; height: 44px; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); border-radius: 12px; vertical-align: middle;">
                                        <span style="font-size: 22px; line-height: 44px; color: #ffffff; font-weight: 800;">A</span>
                                    </td>
                                    <td style="padding-left: 10px; vertical-align: middle;">
                                        <span style="font-size: 22px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px;">Attendrix</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="background: #ffffff; border-radius: 20px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td height="6" style="background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 50%, #06B6D4 100%); border-radius: 20px 20px 0 0; font-size: 0; line-height: 0;">&nbsp;</td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 36px 30px 0;">
                                        <table cellpadding="0" cellspacing="0" border="0" style="display: inline-block; background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.2); border-radius: 100px;">
                                            <tr>
                                                <td style="padding: 6px 16px; font-size: 13px; font-weight: 600; color: #10B981; letter-spacing: 0.5px;">
                                                    &#10003; Demo Confirmed
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 20px 30px 8px;">
                                        <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px;">
                                            You're all set, <span style="background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">{name}</span>
                                        </h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 0 30px 24px;">
                                        <p style="margin: 0; font-size: 15px; color: #64748B; line-height: 1.6;">
                                            Your personalized Attendrix demo has been scheduled for <strong style="color: #1E293B;">{institution}</strong>. We're preparing a tailored walkthrough of our enterprise attendance platform.
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 0 30px;">
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="border-top: 1px solid #E2E8F0; font-size: 0; line-height: 0;">&nbsp;</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 24px 30px 8px;">
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="padding-bottom: 16px;">
                                                    <table cellpadding="0" cellspacing="0" border="0">
                                                        <tr>
                                                            <td style="width: 20px; font-size: 16px; color: #4F46E5;">&#128197;</td>
                                                            <td style="padding-left: 10px;">
                                                                <p style="margin: 0; font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Date</p>
                                                                <p style="margin: 4px 0 0; font-size: 16px; font-weight: 700; color: #0F172A;">{demo_date}</p>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                                <td style="padding-bottom: 16px;">
                                                    <table cellpadding="0" cellspacing="0" border="0">
                                                        <tr>
                                                            <td style="width: 20px; font-size: 16px; color: #4F46E5;">&#128339;</td>
                                                            <td style="padding-left: 10px;">
                                                                <p style="margin: 0; font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Time</p>
                                                                <p style="margin: 4px 0 0; font-size: 16px; font-weight: 700; color: #0F172A;">{demo_time}</p>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 4px;">
                                                    <table cellpadding="0" cellspacing="0" border="0">
                                                        <tr>
                                                            <td style="width: 20px; font-size: 16px; color: #4F46E5;">&#127758;</td>
                                                            <td style="padding-left: 10px;">
                                                                <p style="margin: 0; font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Timezone</p>
                                                                <p style="margin: 4px 0 0; font-size: 16px; font-weight: 600; color: #0F172A;">{timezone}</p>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                                <td style="padding-bottom: 4px;">
                                                    <table cellpadding="0" cellspacing="0" border="0">
                                                        <tr>
                                                            <td style="width: 20px; font-size: 16px; color: #4F46E5;">&#127970;</td>
                                                            <td style="padding-left: 10px;">
                                                                <p style="margin: 0; font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Institution</p>
                                                                <p style="margin: 4px 0 0; font-size: 16px; font-weight: 700; color: #0F172A;">{institution}</p>
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 30px;">
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="border-top: 1px solid #E2E8F0; font-size: 0; line-height: 0;">&nbsp;</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 20px 30px 0;">
                                        <h2 style="margin: 0 0 16px; font-size: 18px; font-weight: 800; color: #0F172A;">What Happens Next</h2>
                                        <table cellpadding="0" cellspacing="0" border="0" style="width: 100%;">
                                            <tr>
                                                <td style="padding-bottom: 14px; vertical-align: top; width: 28px;">
                                                    <table cellpadding="0" cellspacing="0" border="0" style="width: 28px; height: 28px; background: rgba(79,70,229,0.1); border-radius: 8px;">
                                                        <tr><td align="center" style="font-size: 14px; color: #4F46E5; font-weight: 700;">1</td></tr>
                                                    </table>
                                                </td>
                                                <td style="padding-bottom: 14px; padding-left: 12px;">
                                                    <p style="margin: 0; font-size: 14px; font-weight: 700; color: #0F172A;">Discovery &amp; Customization</p>
                                                    <p style="margin: 2px 0 0; font-size: 13px; color: #64748B; line-height: 1.5;">Our product specialist reviews your institution profile and customizes the demo environment to match your specific needs.</p>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 14px; vertical-align: top; width: 28px;">
                                                    <table cellpadding="0" cellspacing="0" border="0" style="width: 28px; height: 28px; background: rgba(79,70,229,0.1); border-radius: 8px;">
                                                        <tr><td align="center" style="font-size: 14px; color: #4F46E5; font-weight: 700;">2</td></tr>
                                                    </table>
                                                </td>
                                                <td style="padding-bottom: 14px; padding-left: 12px;">
                                                    <p style="margin: 0; font-size: 14px; font-weight: 700; color: #0F172A;">Sandbox Environment Setup</p>
                                                    <p style="margin: 2px 0 0; font-size: 13px; color: #64748B; line-height: 1.5;">We configure a sandbox with sample data matching your institution structure, ready for live exploration.</p>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="vertical-align: top; width: 28px;">
                                                    <table cellpadding="0" cellspacing="0" border="0" style="width: 28px; height: 28px; background: rgba(79,70,229,0.1); border-radius: 8px;">
                                                        <tr><td align="center" style="font-size: 14px; color: #4F46E5; font-weight: 700;">3</td></tr>
                                                    </table>
                                                </td>
                                                <td style="padding-left: 12px;">
                                                    <p style="margin: 0; font-size: 14px; font-weight: 700; color: #0F172A;">Live Demo Walkthrough</p>
                                                    <p style="margin: 2px 0 0; font-size: 13px; color: #64748B; line-height: 1.5;">Join a guided 30-45 minute session focused on your use cases with real-time Q&amp;A.</p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 20px 30px;">
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="border-top: 1px solid #E2E8F0; font-size: 0; line-height: 0;">&nbsp;</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                {portal_section}
                                <tr>
                                    <td align="center" style="padding: 0 30px 24px;">
                                        <table cellpadding="0" cellspacing="0" border="0" style="background: #F1F5F9; border-radius: 12px; border: 1px dashed #CBD5E1; width: 100%;">
                                            <tr>
                                                <td align="center" style="padding: 16px 20px;">
                                                    <p style="margin: 0 0 4px; font-size: 13px; color: #64748B;">
                                                        &#128279; Meeting link will be available <strong style="color: #1E293B;">15 minutes before</strong> your session
                                                    </p>
                                                    <p style="margin: 0; font-size: 12px; color: #94A3B8;">
                                                        You will receive a separate email with the join link when the session is ready.
                                                    </p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 24px 16px 0;">
                            <p style="margin: 0 0 8px; font-size: 13px; color: #94A3B8;">
                                Questions? Contact our team at
                                <a href="mailto:demo@attendrix.com" style="color: #4F46E5; text-decoration: none; font-weight: 600;">demo@attendrix.com</a>
                            </p>
                            <p style="margin: 0 0 4px; font-size: 12px; color: #CBD5E1;">
                                Attendrix &mdash; Intelligent Attendance Management for Modern Universities
                            </p>
                            <p style="margin: 0; font-size: 11px; color: #CBD5E1;">
                                &copy; {datetime.now().year} Attendrix. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''


def _build_reminder_html(
    name: str,
    institution: str,
    demo_date: str,
    demo_time: str,
    timezone: str,
    meeting_url: str = "",
) -> str:
    meeting_section = ""
    if meeting_url:
        meeting_section = f'''
        <tr>
            <td align="center" style="padding: 0 30px 24px;">
                <a href="{meeting_url}" style="display: inline-block; padding: 14px 36px; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: #ffffff; text-decoration: none; border-radius: 12px; font-size: 15px; font-weight: 700; font-family: 'Inter', 'Segoe UI', Arial, sans-serif; letter-spacing: 0.3px;">
                    Join Demo Session
                </a>
            </td>
        </tr>
        '''
    else:
        meeting_section = f'''
        <tr>
            <td align="center" style="padding: 0 30px 24px;">
                <table cellpadding="0" cellspacing="0" border="0" style="background: #F1F5F9; border-radius: 12px; border: 1px dashed #CBD5E1; width: 100%;">
                    <tr>
                        <td align="center" style="padding: 16px 20px;">
                            <p style="margin: 0; font-size: 13px; color: #64748B;">
                                &#128279; Meeting link will appear here <strong style="color: #1E293B;">15 minutes before</strong> your session
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        '''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demo Reminder — Attendrix</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: 'Inter', 'Segoe UI', Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F8FAFC; min-height: 100vh;">
        <tr>
            <td align="center" style="padding: 40px 16px;">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">
                    <tr>
                        <td align="center" style="padding: 0 0 24px;">
                            <table cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center" style="width: 44px; height: 44px; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); border-radius: 12px; vertical-align: middle;">
                                        <span style="font-size: 22px; line-height: 44px; color: #ffffff; font-weight: 800;">A</span>
                                    </td>
                                    <td style="padding-left: 10px; vertical-align: middle;">
                                        <span style="font-size: 22px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px;">Attendrix</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="background: #ffffff; border-radius: 20px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr><td height="6" style="background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 50%, #06B6D4 100%); border-radius: 20px 20px 0 0; font-size: 0; line-height: 0;">&nbsp;</td></tr>
                                <tr>
                                    <td align="center" style="padding: 36px 30px 0;">
                                        <span style="font-size: 40px;">&#9200;</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 16px 30px 8px;">
                                        <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px;">Demo Reminder</h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 0 30px 20px;">
                                        <p style="margin: 0; font-size: 15px; color: #64748B; line-height: 1.6;">
                                            Hi <strong style="color: #1E293B;">{name}</strong>, your Attendrix demo is coming up soon. Here's a quick reminder of your session details.
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 0 30px;">
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="border-top: 1px solid #E2E8F0; font-size: 0; line-height: 0;">&nbsp;</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 20px 30px;">
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="padding-bottom: 12px; font-size: 14px; color: #64748B; width: 50%;">Date</td>
                                                <td style="padding-bottom: 12px; font-size: 14px; font-weight: 700; color: #0F172A;">{demo_date}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 12px; font-size: 14px; color: #64748B;">Time</td>
                                                <td style="padding-bottom: 12px; font-size: 14px; font-weight: 700; color: #0F172A;">{demo_time}</td>
                                            </tr>
                                            <tr>
                                                <td style="padding-bottom: 12px; font-size: 14px; color: #64748B;">Timezone</td>
                                                <td style="padding-bottom: 12px; font-size: 14px; font-weight: 700; color: #0F172A;">{timezone}</td>
                                            </tr>
                                            <tr>
                                                <td style="font-size: 14px; color: #64748B;">Institution</td>
                                                <td style="font-size: 14px; font-weight: 700; color: #0F172A;">{institution}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 0 30px;">
                                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                            <tr>
                                                <td style="border-top: 1px solid #E2E8F0; font-size: 0; line-height: 0;">&nbsp;</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                {meeting_section}
                                <tr>
                                    <td align="center" style="padding: 0 30px 30px;">
                                        <p style="margin: 0; font-size: 12px; color: #94A3B8;">
                                            Need to reschedule? Reply to this email and we'll find a new time that works for you.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 24px 16px 0;">
                            <p style="margin: 0 0 8px; font-size: 13px; color: #94A3B8;">
                                Questions? <a href="mailto:demo@attendrix.com" style="color: #4F46E5; text-decoration: none; font-weight: 600;">demo@attendrix.com</a>
                            </p>
                            <p style="margin: 0 0 4px; font-size: 12px; color: #CBD5E1;">
                                Attendrix &mdash; Intelligent Attendance Management for Modern Universities
                            </p>
                            <p style="margin: 0; font-size: 11px; color: #CBD5E1;">
                                &copy; {datetime.now().year} Attendrix. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''


def _build_trial_activation_html(name: str, institution: str, trial_days: int = 14) -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trial Activated — Attendrix</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: 'Inter', 'Segoe UI', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F8FAFC;">
        <tr>
            <td align="center" style="padding: 40px 16px;">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">
                    <tr>
                        <td align="center" style="padding: 0 0 24px;">
                            <table cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center" style="width: 44px; height: 44px; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); border-radius: 12px; vertical-align: middle;">
                                        <span style="font-size: 22px; line-height: 44px; color: #ffffff; font-weight: 800;">A</span>
                                    </td>
                                    <td style="padding-left: 10px; vertical-align: middle;">
                                        <span style="font-size: 22px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px;">Attendrix</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="background: #ffffff; border-radius: 20px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr><td height="6" style="background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 50%, #06B6D4 100%); border-radius: 20px 20px 0 0; font-size: 0; line-height: 0;">&nbsp;</td></tr>
                                <tr>
                                    <td align="center" style="padding: 36px 30px 0;">
                                        <span style="font-size: 40px;">&#127881;</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 16px 30px 8px;">
                                        <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px;">Your Trial is Active</h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 0 30px 24px;">
                                        <p style="margin: 0; font-size: 15px; color: #64748B; line-height: 1.6;">
                                            Hi <strong style="color: #1E293B;">{name}</strong>, your {trial_days}-day trial of Attendrix for <strong style="color: #1E293B;">{institution}</strong> is now active. Explore the full platform with no limitations.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 24px 16px 0;">
                            <p style="margin: 0; font-size: 12px; color: #CBD5E1;">
                                &copy; {datetime.now().year} Attendrix. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''


def _build_follow_up_html(name: str, institution: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thanks — Attendrix</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: 'Inter', 'Segoe UI', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F8FAFC;">
        <tr>
            <td align="center" style="padding: 40px 16px;">
                <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">
                    <tr>
                        <td align="center" style="padding: 0 0 24px;">
                            <table cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td align="center" style="width: 44px; height: 44px; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); border-radius: 12px; vertical-align: middle;">
                                        <span style="font-size: 22px; line-height: 44px; color: #ffffff; font-weight: 800;">A</span>
                                    </td>
                                    <td style="padding-left: 10px; vertical-align: middle;">
                                        <span style="font-size: 22px; font-weight: 800; color: #0F172A; letter-spacing: -0.5px;">Attendrix</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="background: #ffffff; border-radius: 20px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr><td height="6" style="background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 50%, #06B6D4 100%); border-radius: 20px 20px 0 0; font-size: 0; line-height: 0;">&nbsp;</td></tr>
                                <tr>
                                    <td align="center" style="padding: 36px 30px 16px;">
                                        <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #0F172A;">Thanks, {name}!</h1>
                                    </td>
                                </tr>
                                <tr>
                                    <td align="center" style="padding: 0 30px 24px;">
                                        <p style="margin: 0; font-size: 15px; color: #64748B; line-height: 1.6;">
                                            We hope you enjoyed your Attendrix demo for <strong style="color: #1E293B;">{institution}</strong>. Our team will follow up with next steps, including trial access options and pricing tailored to your institution.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" style="padding: 24px 16px 0;">
                            <p style="margin: 0; font-size: 12px; color: #CBD5E1;">
                                &copy; {datetime.now().year} Attendrix. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''


class EmailService:
    """Enterprise transactional email service supporting SMTP and Resend API.

    Provider selection (priority):
      1. SMTP — if SMTP_HOST and SMTP_USER are set
      2. Resend — if RESEND_API_KEY is set (and SMTP is not configured)
      3. None — graceful skip with detailed logging
    """

    def __init__(self):
        self._provider = PROVIDER_NONE
        self._config = {}
        self._health_status = "unknown"
        self._health_detail = ""
        self._reload_config()

    def _reload_config(self):
        cfg = {
            # SMTP settings
            "smtp_host": os.environ.get("SMTP_HOST", ""),
            "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
            "smtp_user": os.environ.get("SMTP_USER", ""),
            "smtp_pass": os.environ.get("SMTP_PASS", ""),
            "smtp_use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() == "true",
            # Resend settings
            "resend_api_key": os.environ.get("RESEND_API_KEY", ""),
            # Common
            "from_email": os.environ.get("MAIL_FROM", os.environ.get("RESEND_FROM_EMAIL", "demo@lamela.com")),
            "from_name": os.environ.get("MAIL_FROM_NAME", os.environ.get("RESEND_FROM_NAME", "Attendrix Team")),
            "email_enabled": os.environ.get("EMAIL_ENABLED", "false").lower() == "true",
        }
        self._config = cfg

        if cfg["smtp_host"] and cfg["smtp_user"]:
            self._provider = PROVIDER_SMTP
        elif cfg["resend_api_key"]:
            self._provider = PROVIDER_RESEND
        else:
            self._provider = PROVIDER_NONE

        logger.info(
            "EmailService configured: provider=%s, smtp_host=%s, resend_key_set=%s, from=%s",
            self._provider,
            cfg["smtp_host"] or "(none)",
            "yes" if cfg["resend_api_key"] else "no",
            cfg["from_email"],
        )

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def health_status(self) -> str:
        return self._health_status

    @property
    def health_detail(self) -> str:
        return self._health_detail

    @property
    def is_available(self) -> bool:
        email_enabled = self._config.get("email_enabled", False)
        return email_enabled and self._provider != PROVIDER_NONE

    def test_smtp_connection(self) -> Dict[str, Any]:
        host = self._config["smtp_host"]
        port = self._config["smtp_port"]
        user = self._config["smtp_user"]
        use_tls = self._config["smtp_use_tls"]

        if not host or not user:
            self._health_status = "unconfigured"
            self._health_detail = "SMTP host or user not set"
            return {"success": False, "detail": self._health_detail}

        try:
            if use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(host, port, timeout=15)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.ehlo()

            server.login(user, self._config["smtp_pass"])
            server.quit()

            self._health_status = "healthy"
            self._health_detail = f"SMTP {host}:{port} authenticated successfully"
            logger.info("SMTP connection test PASSED: %s:%s as %s", host, port, user)
            return {"success": True, "detail": self._health_detail}

        except smtplib.SMTPAuthenticationError as exc:
            self._health_status = "auth_failed"
            self._health_detail = f"SMTP authentication failed: {exc.smtp_code}"
            logger.error("SMTP auth FAILED: %s:%s as %s — %s", host, port, user, exc)
            return {"success": False, "detail": self._health_detail}

        except (smtplib.SMTPException, ConnectionRefusedError, TimeoutError, OSError) as exc:
            self._health_status = "connection_failed"
            self._health_detail = f"SMTP connection failed: {exc}"
            logger.error("SMTP connection FAILED: %s:%s — %s", host, port, exc)
            return {"success": False, "detail": self._health_detail}

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        to_name: str = "",
        reply_to: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        self._reload_config()
        if not to_email:
            logger.error("Cannot send email: no recipient address provided")
            return {"status": EmailDeliveryStatus.FAILED, "message": "No recipient address", "provider": self._provider}

        if not self.is_available:
            logger.warning(
                "Email service not available — skipping send to %s (provider=%s, email_enabled=%s)",
                to_email, self._provider, self._config.get("email_enabled"),
            )
            return {"status": EmailDeliveryStatus.SKIPPED, "message": "Email service not configured", "provider": self._provider}

        if self._provider == PROVIDER_SMTP:
            return self._send_via_smtp(to_email, subject, html_body, to_name, reply_to)
        elif self._provider == PROVIDER_RESEND:
            return self._send_via_resend(to_email, subject, html_body, to_name, reply_to, headers)

        return {"status": EmailDeliveryStatus.SKIPPED, "message": "No email provider configured", "provider": self._provider}

    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        to_name: str = "",
        reply_to: str = "",
    ) -> Dict[str, Any]:
        host = self._config["smtp_host"]
        port = self._config["smtp_port"]
        user = self._config["smtp_user"]
        password = self._config["smtp_pass"]
        use_tls = self._config["smtp_use_tls"]
        from_email = self._config["from_email"]
        from_name = self._config["from_name"]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
        if reply_to:
            msg["Reply-To"] = reply_to
        msg["Message-ID"] = f"<attendrix-{datetime.utcnow().timestamp()}@{host}>"

        msg.attach(MIMEText(html_body, "html"))

        try:
            if use_tls:
                context = ssl.create_default_context()
                server = smtplib.SMTP(host, port, timeout=30)
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            else:
                server = smtplib.SMTP(host, port, timeout=30)
                server.ehlo()

            server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())
            server.quit()

            logger.info(
                "SMTP email SENT to=%s | subject=%s | host=%s:%s",
                to_email, subject, host, port,
            )
            return {"status": EmailDeliveryStatus.SENT, "message": "Email delivered via SMTP", "provider": PROVIDER_SMTP}

        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP auth FAILED for %s: %s", to_email, exc)
            return {"status": EmailDeliveryStatus.FAILED, "message": "SMTP authentication failed", "provider": PROVIDER_SMTP}

        except smtplib.SMTPRecipientsRefused as exc:
            logger.error("SMTP recipient REFUSED for %s: %s", to_email, exc)
            return {"status": EmailDeliveryStatus.FAILED, "message": "Recipient refused by server", "provider": PROVIDER_SMTP}

        except (smtplib.SMTPException, ConnectionRefusedError, TimeoutError, OSError) as exc:
            logger.error("SMTP send FAILED for %s: %s", to_email, exc)
            return {"status": EmailDeliveryStatus.FAILED, "message": f"SMTP error: {exc}", "provider": PROVIDER_SMTP}

    def _send_via_resend(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        to_name: str = "",
        reply_to: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        api_key = self._config["resend_api_key"]
        from_email = self._config["from_email"]
        from_name = self._config["from_name"]

        try:
            import requests
        except ImportError:
            logger.error("requests library not available for Resend API")
            return {"status": EmailDeliveryStatus.FAILED, "message": "requests library required", "provider": PROVIDER_RESEND}

        payload = {
            "from": f"{from_name} <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        if to_name:
            payload["to"] = [f"{to_name} <{to_email}>"]
        if reply_to:
            payload["reply_to"] = reply_to
        if headers:
            payload["headers"] = headers

        logger.info("Resend EMAIL QUEUED for=%s | from=%s | subject=%s", to_email, from_email, subject)

        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = {"raw_text": resp.text[:1000]}

            log_entry = {
                "status_code": resp.status_code,
                "response": resp_body,
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if resp.status_code in (200, 201):
                email_id = resp_body.get("id", "")
                logger.info(
                    "Resend EMAIL ACCEPTED for=%s | id=%s | subject=%s | full_response=%s",
                    to_email, email_id, subject, resp_body,
                )
                return {
                    "status": EmailDeliveryStatus.SENT,
                    "email_id": email_id,
                    "message": "Email accepted by Resend for delivery",
                    "provider": PROVIDER_RESEND,
                    "api_response": log_entry,
                }

            logger.error(
                "Resend EMAIL REJECTED for=%s | status=%s | full_response=%s",
                to_email, resp.status_code, resp_body,
            )
            error_msg = resp_body.get("message", resp_body.get("error", f"Resend API returned {resp.status_code}"))
            return {
                "status": EmailDeliveryStatus.FAILED,
                "message": error_msg,
                "provider": PROVIDER_RESEND,
                "api_response": log_entry,
            }

        except Exception as exc:
            logger.error("Resend EMAIL FAILED for=%s | error=%s", to_email, exc)
            return {
                "status": EmailDeliveryStatus.FAILED,
                "message": f"Resend connection error: {exc}",
                "provider": PROVIDER_RESEND,
                "api_response": {"error": str(exc), "timestamp": datetime.utcnow().isoformat()},
            }

    def send_demo_confirmation(
        self,
        to_email: str,
        to_name: str,
        institution: str,
        demo_date: str,
        demo_time: str,
        timezone: str,
        booking_token: str = "",
        portal_url: str = "",
    ) -> Dict[str, Any]:
        subject = f"Your Attendrix Demo is Confirmed — {demo_date}"
        html_body = _build_confirmation_html(
            name=to_name,
            institution=institution,
            demo_date=demo_date,
            demo_time=demo_time,
            timezone=timezone,
            portal_url=portal_url,
        )
        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            to_name=to_name,
            reply_to="demo@attendrix.com",
        )

    def send_reminder_email(
        self,
        to_email: str,
        to_name: str,
        institution: str,
        demo_date: str,
        demo_time: str,
        timezone: str,
        meeting_url: str = "",
    ) -> Dict[str, Any]:
        subject = "Reminder: Attendrix Demo in 24 Hours"
        html_body = _build_reminder_html(
            name=to_name,
            institution=institution,
            demo_date=demo_date,
            demo_time=demo_time,
            timezone=timezone,
            meeting_url=meeting_url,
        )
        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            to_name=to_name,
            reply_to="demo@attendrix.com",
        )

    def send_trial_activation(
        self,
        to_email: str,
        to_name: str,
        institution: str,
        trial_days: int = 14,
    ) -> Dict[str, Any]:
        subject = "Your Attendrix Trial is Now Active"
        html_body = _build_trial_activation_html(name=to_name, institution=institution, trial_days=trial_days)
        return self.send_email(to_email=to_email, subject=subject, html_body=html_body, to_name=to_name)

    def send_follow_up(
        self,
        to_email: str,
        to_name: str,
        institution: str,
    ) -> Dict[str, Any]:
        subject = "Thanks for Attending Your Attendrix Demo"
        html_body = _build_follow_up_html(name=to_name, institution=institution)
        return self.send_email(to_email=to_email, subject=subject, html_body=html_body, to_name=to_name)


email_service = EmailService()
