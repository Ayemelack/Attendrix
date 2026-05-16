from typing import Dict, Any, Optional, List
from datetime import datetime
import io
import logging
import os
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class ReportService:
    """Professional report generation service using ReportLab."""

    def __init__(self, firebase_service):
        self.fb = firebase_service

    def generate_attendance_report(self, institution_id: str,
                                   report_type: str = 'summary') -> Optional[bytes]:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm, cm
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, Image, HRFlowable
            )
            from reportlab.graphics.shapes import Drawing
            from reportlab.graphics.charts.lineplots import LinePlot

            institution = self._get_institution_info(institution_id)
            inst_name = institution.get('name', 'Institution')
            stats = self._compute_report_stats(institution_id)

            buf = io.BytesIO()
            doc = SimpleDocTemplate(
                buf, pagesize=A4,
                leftMargin=20*mm, rightMargin=20*mm,
                topMargin=15*mm, bottomMargin=15*mm,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle', parent=styles['Title'],
                fontSize=20, leading=24, spaceAfter=4*mm,
                textColor=colors.HexColor('#1E293B'),
                fontName='Helvetica-Bold',
            )
            subtitle_style = ParagraphStyle(
                'CustomSubtitle', parent=styles['Normal'],
                fontSize=9, leading=12, spaceAfter=2*mm,
                textColor=colors.HexColor('#64748B'),
            )
            heading_style = ParagraphStyle(
                'CustomHeading2', parent=styles['Heading2'],
                fontSize=13, leading=16, spaceBefore=6*mm, spaceAfter=3*mm,
                textColor=colors.HexColor('#334155'),
                fontName='Helvetica-Bold',
            )
            normal_style = ParagraphStyle(
                'CustomNormal', parent=styles['Normal'],
                fontSize=8.5, leading=12, spaceAfter=1*mm,
                textColor=colors.HexColor('#475569'),
            )
            small_style = ParagraphStyle(
                'SmallText', parent=styles['Normal'],
                fontSize=7, leading=9, textColor=colors.HexColor('#94A3B8'),
            )

            elements = []

            elements.append(Paragraph(
                f'Attendrix &mdash; Attendance Report', title_style))
            elements.append(Paragraph(
                f'{inst_name} &nbsp;|&nbsp; {datetime.utcnow().strftime("%d %B %Y")} &nbsp;|&nbsp; {report_type.title()} Report',
                subtitle_style
            ))
            elements.append(HRFlowable(
                width='100%', thickness=1,
                color=colors.HexColor('#E2E8F0'),
                spaceAfter=4*mm, spaceBefore=1*mm
            ))

            elements.append(Paragraph('Executive Summary', heading_style))
            summary_data = [
                ['Metric', 'Value'],
                ['Total Students', str(stats['total_students'])],
                ['Total Sessions', str(stats['total_sessions'])],
                ['Attendance Records', str(stats['total_records'])],
                ['Overall Attendance Rate', f'{stats["attendance_rate"]}%'],
                ['Active Sessions', str(stats['active_sessions'])],
                ['Fraud Attempts Blocked', str(stats['fraud_attempts'])],
            ]
            summary_table = Table(summary_data, colWidths=[120*mm, 60*mm])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(summary_table)
            elements.append(Spacer(1, 4*mm))

            elements.append(Paragraph('Session Breakdown', heading_style))
            sessions = stats['sessions']
            if sessions:
                session_header = ['Course', 'Lecturer', 'Students', 'Present',
                                  'Rate', 'Status']
                session_rows = [session_header]
                for s in sessions:
                    session_rows.append([
                        s.get('course_name', '—'),
                        s.get('lecturer_name', '—'),
                        str(s.get('total_students', 0)),
                        str(s.get('present', 0)),
                        f'{s.get("attendance_rate", 0)}%',
                        s.get('status', '—').title(),
                    ])
                session_table = Table(
                    session_rows,
                    colWidths=[45*mm, 40*mm, 20*mm, 20*mm, 20*mm, 25*mm]
                )
                session_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 7.5),
                    ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                     [colors.HexColor('#F8FAFC'), colors.white]),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                elements.append(session_table)
            else:
                elements.append(Paragraph(
                    'No session data available.', normal_style))

            elements.append(Spacer(1, 6*mm))
            elements.append(HRFlowable(
                width='100%', thickness=0.5,
                color=colors.HexColor('#E2E8F0'),
                spaceAfter=2*mm, spaceBefore=2*mm
            ))
            elements.append(Paragraph(
                f'Generated by Attendrix on {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}',
                small_style
            ))
            elements.append(Paragraph(
                'MINESEC-compliant attendance report for Cameroonian educational institutions.',
                small_style
            ))

            doc.build(elements)
            pdf_bytes = buf.getvalue()
            buf.close()
            return pdf_bytes

        except ImportError as e:
            logger.error(f"ReportLab not installed: {e}")
            return None
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
            return None

    def _get_institution_info(self, institution_id: str) -> Dict[str, Any]:
        inst = self.fb.get_document('institutions', institution_id)
        if inst:
            return inst
        return {'name': institution_id.replace('_', ' ').title()}

    def _compute_report_stats(self, institution_id: str) -> Dict[str, Any]:
        students = self.fb.query_documents(
            'users',
            filters=[{'field': 'institution_id', 'value': institution_id},
                     {'field': 'role', 'value': 'student'}]
        )
        sessions = self.fb.query_documents(
            'attendance_sessions',
            filters=[{'field': 'institution_id', 'value': institution_id}],
        )
        records = self.fb.query_documents('attendance_records')
        session_ids = set(s['id'] for s in sessions)
        relevant_records = [r for r in records
                            if r.get('attendance_session_id') in session_ids]

        total_records = len(relevant_records)
        present = sum(1 for r in relevant_records if r.get('status') == 'present')
        attendance_rate = round(present / total_records * 100, 1) if total_records > 0 else 0

        security_logs = self.fb.query_documents(
            'security_logs',
            filters=[{'field': 'institution_id', 'value': institution_id}]
        )
        fraud_attempts = sum(1 for s in security_logs if s.get('event_type') in (
            'proxy_attempt', 'duplicate_qr', 'geo_anomaly', 'rapid_replay',
        ))

        session_details = []
        for s in sessions:
            s_records = [r for r in relevant_records
                         if r.get('attendance_session_id') == s.get('id')]
            s_total = len(s_records)
            s_present = sum(1 for r in s_records if r.get('status') == 'present')
            session_details.append({
                'course_name': s.get('course_name', s.get('course_id', '—')),
                'lecturer_name': s.get('lecturer_name', '—'),
                'total_students': s.get('total_students', s_total),
                'present': s_present,
                'attendance_rate': round(s_present / s_total * 100, 1) if s_total > 0 else 0,
                'status': s.get('status', 'completed'),
            })

        return {
            'total_students': len(students),
            'total_sessions': len(sessions),
            'total_records': total_records,
            'attendance_rate': attendance_rate,
            'active_sessions': sum(1 for s in sessions if s.get('is_active')),
            'fraud_attempts': fraud_attempts,
            'sessions': session_details,
        }

    def generate_minesec_xml(self, institution_id: str) -> Optional[bytes]:
        try:
            institution = self._get_institution_info(institution_id)
            inst_name = institution.get('name', institution_id)
            inst_code = institution.get('code', institution_id)
            stats = self._compute_report_stats(institution_id)

            root = ET.Element('MINESEC_Attendance_Report')
            root.set('xmlns', 'https://minesec.gov.cm/schemas/attendance')
            root.set('version', '1.0')

            header = ET.SubElement(root, 'ReportHeader')
            ET.SubElement(header, 'InstitutionName').text = inst_name
            ET.SubElement(header, 'InstitutionCode').text = inst_code
            ET.SubElement(header, 'AcademicYear').text = datetime.utcnow().strftime('%Y-%Y')
            ET.SubElement(header, 'ReportType').text = 'ATTENDANCE_SUMMARY'
            ET.SubElement(header, 'GeneratedAt').text = datetime.utcnow().isoformat()
            ET.SubElement(header, 'GeneratedBy').text = 'Attendrix v2.0'

            summary = ET.SubElement(root, 'ExecutiveSummary')
            ET.SubElement(summary, 'TotalStudents').text = str(stats['total_students'])
            ET.SubElement(summary, 'TotalSessions').text = str(stats['total_sessions'])
            ET.SubElement(summary, 'TotalAttendanceRecords').text = str(stats['total_records'])
            ET.SubElement(summary, 'OverallAttendanceRate').text = f'{stats["attendance_rate"]}%'
            ET.SubElement(summary, 'ActiveSessions').text = str(stats['active_sessions'])
            ET.SubElement(summary, 'FraudAttemptsBlocked').text = str(stats['fraud_attempts'])

            sessions_elem = ET.SubElement(root, 'Sessions')
            for s in stats['sessions']:
                se = ET.SubElement(sessions_elem, 'Session')
                ET.SubElement(se, 'Course').text = s.get('course_name', '')
                ET.SubElement(se, 'Lecturer').text = s.get('lecturer_name', '')
                ET.SubElement(se, 'TotalStudents').text = str(s.get('total_students', 0))
                ET.SubElement(se, 'Present').text = str(s.get('present', 0))
                absent = s.get('total_students', 0) - s.get('present', 0)
                ET.SubElement(se, 'Absent').text = str(max(0, absent))
                ET.SubElement(se, 'AttendanceRate').text = f'{s.get("attendance_rate", 0)}%'
                ET.SubElement(se, 'Status').text = s.get('status', 'completed')

            footer = ET.SubElement(root, 'ReportFooter')
            ET.SubElement(footer, 'Certification').text = 'This report is MINESEC-compliant and generated electronically.'
            ET.SubElement(footer, 'MINESECVersion').text = '2026.1'

            xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
            return xml_str.encode('utf-8')

        except Exception as e:
            logger.error(f"MINESEC XML generation failed: {str(e)}")
            return None
