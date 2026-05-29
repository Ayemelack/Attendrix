"""Page route blueprints — static pages, demo flows, brochure."""

from flask import Blueprint, render_template, request, jsonify, make_response, send_file

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def landing():
    template_path = pages_bp.jinja_loader.get_source(
        pages_bp.jinja_env, 'landing.html'
    )[1] if pages_bp.jinja_loader else ''
    response = render_template('landing.html')
    resp = make_response(response)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@pages_bp.route('/request-demo')
def request_demo():
    response = render_template('request-demo.html')
    resp = make_response(response)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@pages_bp.route('/schedule-demo')
def schedule_demo():
    from src.application.demo_booking_service import demo_booking_service
    csrf_token = demo_booking_service.generate_csrf_token()
    session_token = request.args.get('sessionToken', '')
    response = render_template('schedule-demo.html', csrf_token=csrf_token, session_token=session_token)
    resp = make_response(response)
    if session_token:
        resp.set_cookie(
            'demoSessionToken',
            session_token,
            max_age=7 * 24 * 60 * 60,
            path='/',
            samesite='Lax'
        )
    return resp


@pages_bp.route('/legal/privacy')
def privacy_policy():
    return render_template('privacy-policy.html')


@pages_bp.route('/demo-prep')
def demo_prep():
    from src.application.demo_booking_service import demo_booking_service
    token = request.args.get('token', '')
    session_token = request.args.get('sessionToken', '')
    booking = None
    if token:
        booking = demo_booking_service.get_booking_by_token(token)
    elif session_token:
        booking = demo_booking_service.get_booking_by_session_token(session_token)
        if booking:
            token = booking.get('token', '')
    else:
        cookie_token = request.cookies.get('demoSessionToken', '')
        if cookie_token:
            booking = demo_booking_service.get_booking_by_session_token(cookie_token)
            if booking:
                token = booking.get('token', '')

    if not booking:
        return render_template('demo-prep.html', error='invalid_token')

    return render_template('demo-prep.html',
        token=token,
        name=booking['name'],
        email=booking['email'],
        institution=booking['institution'],
        time=booking['time'],
        date=booking['date'],
        status=booking['status'],
        onboarding_progress=booking.get('onboarding_progress', {}),
        onboarding_completed=booking.get('onboarding_completed', False),
        email_status=booking.get('email_status', 'pending'),
        email_error=booking.get('email_error', ''),
    )


@pages_bp.route('/trial-gate')
def trial_gate():
    return render_template('trial-gate.html')


@pages_bp.route('/product-overview')
def product_overview():
    return render_template('product-overview.html')


@pages_bp.route('/brochure')
def brochure():
    return render_template('brochure.html')


@pages_bp.route('/api/brochure/download')
def brochure_download():
    import io
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import mm

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=20*mm, bottomMargin=20*mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=26, spaceAfter=6, textColor=HexColor('#4F46E5'))
        heading_style = ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=16, spaceAfter=6, spaceBefore=14, textColor=HexColor('#1E293B'))
        body_style = ParagraphStyle('Body2', parent=styles['Normal'], fontSize=10, leading=15, spaceAfter=8, textColor=HexColor('#334155'))
        bullet_style = ParagraphStyle('Bullet2', parent=styles['Normal'], fontSize=10, leading=14, leftIndent=16, spaceAfter=4, textColor=HexColor('#334155'))

        elements = []
        elements.append(Paragraph("Attendrix", title_style))
        elements.append(Paragraph("Intelligent Attendance Management for Modern Universities", ParagraphStyle('Sub', fontSize=12, spaceAfter=20, textColor=HexColor('#64748B'))))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph("Introduction", heading_style))
        elements.append(Paragraph("Attendrix is a next-generation attendance management system purpose-built for higher education institutions. It replaces traditional, error-prone roll-calling methods with an AI-powered, anti-proxy platform that delivers real-time visibility, automated reporting, and seamless integration with existing campus infrastructure.", body_style))
        elements.append(Spacer(1, 4))

        elements.append(Paragraph("Key Features", heading_style))
        features = [
            ("<b>Anti-Proxy Shield</b> — Multi-layered detection using device fingerprinting, geolocation, and behavioral analysis prevents proxy attendance."),
            ("<b>Biometric Verification</b> — Facial recognition and fingerprint scanning ensure each attendance record is authentic."),
            ("<b>Real-Time Analytics</b> — Live dashboards with predictive insights help administrators identify trends and intervene early."),
            ("<b>Offline-First Architecture</b> — Distributed mesh network enables attendance recording without internet. Data syncs automatically when reconnected."),
            ("<b>Automated Reporting</b> — Export attendance reports to PDF or Excel. Schedule automated delivery to stakeholders."),
        ]
        for f in features:
            elements.append(ListFlowable([ListItem(Paragraph(f, bullet_style))], bulletType='bullet', bulletColor=HexColor('#4F46E5'), start='\u2022'))
        elements.append(Spacer(1, 4))

        elements.append(Paragraph("Architecture", heading_style))
        elements.append(Paragraph("Attendrix is built on a distributed, offline-first architecture. Each classroom operates as an independent node. Data synchronizes across LAN and cloud with automatic conflict resolution, ensuring high availability and data integrity even under adverse network conditions.", body_style))
        elements.append(Spacer(1, 4))

        elements.append(Paragraph("Benefits", heading_style))
        benefits = [
            "Eliminate proxy attendance completely",
            "Reduce administrative workload by up to 80%",
            "Real-time visibility across all classrooms",
            "Boost student accountability and engagement",
            "Seamless integration with existing LMS and SIS",
            "GDPR and FERPA compliant data handling",
            "Scalable from 500 to 50,000+ students",
            "24/7 support with dedicated account management",
        ]
        for b in benefits:
            elements.append(ListFlowable([ListItem(Paragraph(b, bullet_style))], bulletType='bullet', bulletColor=HexColor('#10B981'), start='\u2022'))
        elements.append(Spacer(1, 4))

        elements.append(Paragraph("Use Cases", heading_style))
        use_cases = [
            "University Lectures — 500-2000 student courses with multi-factor verification",
            "Lab Sessions — Small group attendance with biometric check-in",
            "Seminars & Workshops — Flexible attendance modes for events",
            "Multi-Campus Institutions — Unified attendance across all locations",
            "Examination Halls — Strict identity verification for exam integrity",
        ]
        for uc in use_cases:
            elements.append(ListFlowable([ListItem(Paragraph(uc, bullet_style))], bulletType='bullet', bulletColor=HexColor('#4F46E5'), start='\u2022'))

        elements.append(Spacer(1, 10))
        elements.append(Paragraph("For more information, visit attendrix.com or schedule a personalized demo.", body_style))

        doc.build(elements)
        buf.seek(0)

        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='Attendrix_Brochure.pdf')
    except ImportError:
        return jsonify({'error': 'PDF generation not available'}), 500
    except Exception as e:
        return jsonify({'error': 'Failed to generate PDF'}), 500


@pages_bp.route('/signup-voucher')
def signup_voucher_page():
    return render_template('signup-voucher.html')


@pages_bp.route('/logout', methods=['GET'])
def logout_page():
    return render_template('logout.html')


@pages_bp.route('/login', methods=['GET'])
def login_page():
    response = render_template('login.html')
    resp = make_response(response)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@pages_bp.route('/signup', methods=['GET'])
def signup_page():
    return render_template('signup.html')


@pages_bp.route('/email-diagnostics')
def email_diagnostics_page():
    return render_template('email-diagnostics.html')


@pages_bp.route('/offline')
def offline_page():
    return render_template('offline.html')


@pages_bp.route('/sw.js')
def service_worker():
    import os
    sw_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'sw.js')
    sw_path = os.path.normpath(sw_path)
    with open(sw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    resp = make_response(content)
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp
