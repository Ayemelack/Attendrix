from datetime import datetime, timedelta
import uuid, json, re, math
from src.infrastructure.feedback_models import (
    Feedback, FeedbackReply, FeedbackReaction, ModerationLog,
    FeedbackDiagnostics, EscalationHistory,
    get_db_session, FeedbackStatus
)
from sqlalchemy import func, desc, or_, and_, case

CRITICAL_KEYWORDS = ['sync fail', 'not working', 'crash', 'data loss', 'security breach',
                     'unable to access', 'lost data', 'emergency', 'urgent', 'blocked']
HIGH_KEYWORDS = ['bug', 'error', 'failed', 'broken', 'slow', 'timeout', 'inconsistent',
                 'missing', 'incorrect', 'wrong']

def _compute_sentiment(text):
    positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'perfect',
                      'works', 'improved', 'fantastic', 'helpful', 'thanks']
    negative_words = ['bad', 'terrible', 'awful', 'hate', 'broken', 'worst',
                      'useless', 'poor', 'horrible', 'frustrating', 'annoying']
    if not text:
        return 0.0, 'neutral'
    text_lower = text.lower()
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    total = pos_count + neg_count
    if total == 0:
        return 0.5, 'neutral'
    score = pos_count / total
    if score >= 0.7:
        return round(score, 2), 'positive'
    elif score <= 0.3:
        return round(score, 2), 'negative'
    return round(score, 2), 'neutral'

def _extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stopwords = {'the', 'and', 'for', 'was', 'but', 'are', 'not', 'all', 'any',
                 'can', 'has', 'had', 'its', 'may', 'our', 'out', 'too', 'very'}
    word_freq = {}
    for w in words:
        if w not in stopwords:
            word_freq[w] = word_freq.get(w, 0) + 1
    sorted_words = sorted(word_freq.items(), key=lambda x: -x[1])
    return [w for w, c in sorted_words[:10]]

def _compute_priority(feedback):
    score = 0
    if feedback.severity == 'critical':
        score += 40
    elif feedback.severity == 'high':
        score += 30
    elif feedback.severity == 'medium':
        score += 15
    score += min(feedback.upvotes * 2, 30)
    if feedback.escalation_count > 0:
        score += feedback.escalation_count * 10
    if feedback.sentiment_label == 'negative':
        score += 10
    return score

class FeedbackService:
    def __init__(self, firebase_service=None):
        self.firebase = firebase_service

    def _get_db(self):
        return get_db_session()

    def create_feedback(self, user_id, user_role, data):
        db = self._get_db()
        try:
            title = data.get('title', '').strip()
            description = data.get('description', '').strip()
            if not title or not description:
                return {'success': False, 'error': 'Title and description required'}

            sentiment_score, sentiment_label = _compute_sentiment(description + ' ' + title)
            keywords = _extract_keywords(description)

            is_anonymous = data.get('is_anonymous', True)
            community_visible = data.get('community_visible', True)

            network_diag = data.get('network_diagnostics', {})
            browser_info = data.get('browser_info', {})

            fb = Feedback(
                user_id=user_id,
                user_role=user_role,
                institution=data.get('institution', ''),
                category=data.get('category', 'general'),
                severity=data.get('severity', 'medium'),
                title=title,
                description=description,
                experience_rating=data.get('experience_rating'),
                screenshot_path=data.get('screenshot_path'),
                is_anonymous=is_anonymous,
                allow_contact=data.get('allow_contact', False),
                community_visible=community_visible,
                is_resolved=False,
                admin_viewed=False,
                device_info=data.get('device_info'),
                network_diagnostics=network_diag,
                browser_info=browser_info,
                sync_logs=data.get('sync_logs'),
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                keywords=keywords,
                escalation_level='none',
            )
            db.add(fb)
            db.flush()

            if network_diag and any(k in network_diag for k in ('network_latency_ms', 'vpn_active', 'mqtt_sync_status')):
                diag = FeedbackDiagnostics(
                    feedback_id=fb.id,
                    network_latency_ms=network_diag.get('network_latency_ms'),
                    vpn_active=network_diag.get('vpn_active', False),
                    offline_mode=network_diag.get('offline_mode', False),
                    mqtt_sync_status=network_diag.get('mqtt_sync_status'),
                    mqtt_sync_logs=network_diag.get('mqtt_sync_logs'),
                    packet_loss_pct=network_diag.get('packet_loss_pct'),
                    sync_duration_ms=network_diag.get('sync_duration_ms'),
                    browser_version=browser_info.get('browser_version') if browser_info else None,
                    os_platform=browser_info.get('os_platform') if browser_info else None,
                    device_type=browser_info.get('device_type') if browser_info else None,
                )
                db.add(diag)

            db.commit()
            return {'success': True, 'feedback_id': fb.id}
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    def get_public_feed(self, page=1, per_page=20, filters=None):
        db = self._get_db()
        try:
            query = db.query(Feedback).filter(
                Feedback.community_visible == True,
                Feedback.is_hidden == False,
                Feedback.status != FeedbackStatus.ARCHIVED.value
            )
            if filters:
                if filters.get('category'):
                    query = query.filter(Feedback.category == filters['category'])
                if filters.get('severity'):
                    query = query.filter(Feedback.severity == filters['severity'])
                if filters.get('status'):
                    query = query.filter(Feedback.status == filters['status'])
                if filters.get('institution'):
                    query = query.filter(Feedback.institution == filters['institution'])
                if filters.get('search'):
                    search_term = f"%{filters['search']}%"
                    query = query.filter(
                        or_(Feedback.title.ilike(search_term),
                            Feedback.description.ilike(search_term))
                    )
                if filters.get('unresolved_only'):
                    query = query.filter(Feedback.is_resolved == False)

            sort_by = (filters or {}).get('sort', 'latest')
            if sort_by == 'trending':
                query = query.order_by(Feedback.upvotes.desc(), Feedback.created_at.desc())
            elif sort_by == 'critical':
                query = query.order_by(
                    case((Feedback.severity == 'critical', 0), (Feedback.severity == 'high', 1),
                         (Feedback.severity == 'medium', 2), else_=3),
                    Feedback.created_at.desc()
                )
            elif sort_by == 'oldest':
                query = query.order_by(Feedback.created_at.asc())
            elif sort_by == 'most_discussed':
                query = query.order_by(Feedback.reply_count.desc(), Feedback.created_at.desc())
            else:
                query = query.order_by(Feedback.created_at.desc())

            total = query.count()
            total_pages = max(1, math.ceil(total / per_page))
            items = query.offset((page - 1) * per_page).limit(per_page).all()

            results = []
            for fb in items:
                display_name = 'Anonymous User'
                if fb.user_role == 'student':
                    display_name = 'Anonymous Student'
                elif fb.user_role == 'lecturer':
                    display_name = 'Anonymous Staff'
                elif fb.user_role == 'institutional_admin':
                    display_name = 'Anonymous Institution Staff'
                results.append({
                    'id': fb.id,
                    'display_name': display_name,
                    'role': fb.user_role,
                    'institution': fb.institution or '',
                    'category': fb.category,
                    'severity': fb.severity,
                    'title': fb.title,
                    'description': fb.description[:300] + ('...' if len(fb.description) > 300 else ''),
                    'experience_rating': fb.experience_rating,
                    'status': fb.status,
                    'is_resolved': fb.is_resolved,
                    'upvotes': fb.upvotes,
                    'reply_count': fb.reply_count,
                    'sentiment_label': fb.sentiment_label,
                    'created_at': fb.created_at.isoformat() if fb.created_at else None,
                })
            return {'success': True, 'data': results, 'total': total, 'page': page,
                    'total_pages': total_pages}
        finally:
            db.close()

    def get_feedback_detail(self, feedback_id, user_id=None):
        db = self._get_db()
        try:
            fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not fb:
                return {'success': False, 'error': 'Feedback not found'}
            replies = db.query(FeedbackReply).filter(
                FeedbackReply.feedback_id == feedback_id
            ).order_by(FeedbackReply.created_at.asc()).all()
            reply_data = []
            for r in replies:
                display_name = 'Anonymous User'
                if r.is_admin:
                    display_name = 'Administrator'
                elif r.user_role == 'student':
                    display_name = 'Anonymous Student'
                elif r.user_role == 'lecturer':
                    display_name = 'Anonymous Staff'
                reply_data.append({
                    'id': r.id,
                    'display_name': display_name,
                    'body': r.body,
                    'is_admin': r.is_admin,
                    'created_at': r.created_at.isoformat() if r.created_at else None,
                })
            upvoted = False
            if user_id:
                existing = db.query(FeedbackReaction).filter(
                    FeedbackReaction.feedback_id == feedback_id,
                    FeedbackReaction.user_id == user_id,
                    FeedbackReaction.reaction_type == 'upvote'
                ).first()
                upvoted = existing is not None
            result = {
                'id': fb.id,
                'category': fb.category,
                'severity': fb.severity,
                'title': fb.title,
                'description': fb.description,
                'experience_rating': fb.experience_rating,
                'status': fb.status,
                'is_resolved': fb.is_resolved,
                'upvotes': fb.upvotes,
                'reply_count': fb.reply_count,
                'is_anonymous': fb.is_anonymous,
                'community_visible': fb.community_visible,
                'institution': fb.institution or '',
                'sentiment_label': fb.sentiment_label,
                'device_info': fb.device_info,
                'network_diagnostics': fb.network_diagnostics,
                'created_at': fb.created_at.isoformat() if fb.created_at else None,
                'replies': reply_data,
                'upvoted': upvoted,
            }
            if not user_id or (user_id != fb.user_id):
                result['display_name'] = 'Anonymous User'
                if fb.user_role == 'student':
                    result['display_name'] = 'Anonymous Student'
                elif fb.user_role == 'lecturer':
                    result['display_name'] = 'Anonymous Staff'
                elif fb.user_role == 'institutional_admin':
                    result['display_name'] = 'Anonymous Institution Staff'
            else:
                result['display_name'] = 'You'
            return {'success': True, 'data': result}
        finally:
            db.close()

    def upvote_feedback(self, feedback_id, user_id):
        db = self._get_db()
        try:
            existing = db.query(FeedbackReaction).filter(
                FeedbackReaction.feedback_id == feedback_id,
                FeedbackReaction.user_id == user_id,
                FeedbackReaction.reaction_type == 'upvote'
            ).first()
            if existing:
                db.delete(existing)
                db.query(Feedback).filter(Feedback.id == feedback_id).update(
                    {Feedback.upvotes: Feedback.upvotes - 1}
                )
                db.commit()
                return {'success': True, 'upvoted': False}
            reaction = FeedbackReaction(
                feedback_id=feedback_id, user_id=user_id, reaction_type='upvote'
            )
            db.add(reaction)
            db.query(Feedback).filter(Feedback.id == feedback_id).update(
                {Feedback.upvotes: Feedback.upvotes + 1}
            )
            db.commit()
            self._check_escalation(feedback_id)
            return {'success': True, 'upvoted': True}
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    def add_reply(self, feedback_id, user_id, user_role, body, is_admin=False):
        db = self._get_db()
        try:
            fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not fb:
                return {'success': False, 'error': 'Feedback not found'}
            reply = FeedbackReply(
                feedback_id=feedback_id, user_id=user_id, user_role=user_role,
                is_anonymous=(not is_admin), body=body, is_admin=is_admin
            )
            db.add(reply)
            fb.reply_count = (fb.reply_count or 0) + 1
            db.commit()
            return {'success': True, 'reply_id': reply.id}
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    def _check_escalation(self, feedback_id):
        db = self._get_db()
        try:
            fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not fb:
                return
            priority = _compute_priority(fb)
            new_level = 'none'
            if priority >= 70:
                new_level = 'critical'
            elif priority >= 45:
                new_level = 'high'
            elif priority >= 25:
                new_level = 'medium'
            if new_level != fb.escalation_level and new_level != 'none':
                escalation = EscalationHistory(
                    feedback_id=feedback_id,
                    from_level=fb.escalation_level,
                    to_level=new_level,
                    reason=f'Priority score {priority} triggered escalation',
                    triggered_by='system'
                )
                db.add(escalation)
                fb.escalation_level = new_level
                fb.escalation_count = (fb.escalation_count or 0) + 1
                if new_level == 'critical':
                    fb.status = 'in_review'
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def admin_view_feedback(self, feedback_id):
        db = self._get_db()
        try:
            fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if fb and not fb.admin_viewed:
                fb.admin_viewed = True
                fb.admin_viewed_at = datetime.utcnow()
                db.commit()
            return {'success': True}
        finally:
            db.close()

    def admin_add_note(self, feedback_id, admin_id, note):
        db = self._get_db()
        try:
            fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not fb:
                return {'success': False, 'error': 'Feedback not found'}
            existing = json.loads(fb.admin_notes) if fb.admin_notes else []
            existing.append({
                'note': note,
                'admin_id': admin_id,
                'created_at': datetime.utcnow().isoformat()
            })
            fb.admin_notes = json.dumps(existing)
            db.commit()
            return {'success': True}
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    def admin_moderate(self, feedback_id, admin_id, action, reason=None):
        db = self._get_db()
        try:
            fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if not fb:
                return {'success': False, 'error': 'Feedback not found'}
            log = ModerationLog(
                feedback_id=feedback_id, admin_id=admin_id,
                action=action, reason=reason
            )
            db.add(log)
            if action == 'hide':
                fb.is_hidden = True
                fb.status = FeedbackStatus.HIDDEN.value
            elif action == 'unhide':
                fb.is_hidden = False
                fb.status = FeedbackStatus.OPEN.value
            elif action == 'flag':
                fb.is_flagged = True
                fb.flag_reason = reason
            elif action == 'unflag':
                fb.is_flagged = False
                fb.flag_reason = None
            elif action == 'resolve':
                fb.is_resolved = True
                fb.status = FeedbackStatus.RESOLVED.value
                fb.resolved_at = datetime.utcnow()
                fb.resolved_by = admin_id
            elif action == 'archive':
                fb.status = FeedbackStatus.ARCHIVED.value
            fb.moderation_action = action
            fb.moderation_by = admin_id
            fb.moderation_at = datetime.utcnow()
            db.commit()
            return {'success': True}
        except Exception as e:
            db.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            db.close()

    def get_admin_overview(self):
        db = self._get_db()
        try:
            total = db.query(Feedback).count()
            open_count = db.query(Feedback).filter(Feedback.status == FeedbackStatus.OPEN.value).count()
            critical_count = db.query(Feedback).filter(Feedback.severity == 'critical').count()
            high_count = db.query(Feedback).filter(Feedback.severity == 'high').count()
            resolved_count = db.query(Feedback).filter(Feedback.is_resolved == True).count()
            hidden_count = db.query(Feedback).filter(Feedback.is_hidden == True).count()
            flagged_count = db.query(Feedback).filter(Feedback.is_flagged == True).count()

            unviewed = db.query(Feedback).filter(Feedback.admin_viewed == False).count()
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_count = db.query(Feedback).filter(Feedback.created_at >= today_start).count()

            upvotes_total = db.query(func.sum(Feedback.upvotes)).scalar() or 0

            category_counts = db.query(
                Feedback.category, func.count(Feedback.id)
            ).group_by(Feedback.category).all()

            severity_counts = db.query(
                Feedback.severity, func.count(Feedback.id)
            ).group_by(Feedback.severity).all()

            institution_counts = db.query(
                Feedback.institution, func.count(Feedback.id)
            ).filter(Feedback.institution.isnot(None), Feedback.institution != ''
            ).group_by(Feedback.institution).order_by(func.count(Feedback.id).desc()).limit(10).all()

            sentiment_counts = db.query(
                Feedback.sentiment_label, func.count(Feedback.id)
            ).filter(Feedback.sentiment_label.isnot(None)
            ).group_by(Feedback.sentiment_label).all()

            trending = db.query(Feedback).filter(
                Feedback.community_visible == True,
                Feedback.is_hidden == False,
                Feedback.status != FeedbackStatus.ARCHIVED.value
            ).order_by(Feedback.upvotes.desc()).limit(5).all()

            return {'success': True, 'data': {
                'total': total,
                'open': open_count,
                'critical': critical_count,
                'high': high_count,
                'resolved': resolved_count,
                'hidden': hidden_count,
                'flagged': flagged_count,
                'unviewed': unviewed,
                'today': today_count,
                'upvotes_total': upvotes_total,
                'category_counts': dict(category_counts),
                'severity_counts': dict(severity_counts),
                'top_institutions': [{'name': i[0], 'count': i[1]} for i in institution_counts],
                'sentiment_counts': dict(sentiment_counts),
                'trending': [{
                    'id': f.id, 'title': f.title, 'category': f.category,
                    'upvotes': f.upvotes, 'severity': f.severity,
                    'created_at': f.created_at.isoformat() if f.created_at else None
                } for f in trending],
            }}
        finally:
            db.close()

    def get_all_feedback_admin(self, page=1, per_page=50, filters=None):
        db = self._get_db()
        try:
            query = db.query(Feedback)
            if filters:
                if filters.get('status'):
                    query = query.filter(Feedback.status == filters['status'])
                if filters.get('category'):
                    query = query.filter(Feedback.category == filters['category'])
                if filters.get('severity'):
                    query = query.filter(Feedback.severity == filters['severity'])
                if filters.get('institution'):
                    query = query.filter(Feedback.institution.ilike(f"%{filters['institution']}%"))
                if filters.get('search'):
                    s = f"%{filters['search']}%"
                    query = query.filter(or_(Feedback.title.ilike(s), Feedback.description.ilike(s)))
                if filters.get('unviewed_only'):
                    query = query.filter(Feedback.admin_viewed == False)
                if filters.get('flagged_only'):
                    query = query.filter(Feedback.is_flagged == True)
                if filters.get('hidden_only'):
                    query = query.filter(Feedback.is_hidden == True)
                if filters.get('unresolved_only'):
                    query = query.filter(Feedback.is_resolved == False)
                if filters.get('escalated_only'):
                    query = query.filter(Feedback.escalation_level != 'none')

            sort_by = (filters or {}).get('sort', 'latest')
            if sort_by == 'upvotes':
                query = query.order_by(Feedback.upvotes.desc())
            elif sort_by == 'severity':
                query = query.order_by(
                    case((Feedback.severity == 'critical', 0), (Feedback.severity == 'high', 1),
                         (Feedback.severity == 'medium', 2), else_=3),
                    Feedback.created_at.desc()
                )
            elif sort_by == 'oldest':
                query = query.order_by(Feedback.created_at.asc())
            else:
                query = query.order_by(Feedback.created_at.desc())

            total = query.count()
            total_pages = max(1, math.ceil(total / per_page))
            items = query.offset((page - 1) * per_page).limit(per_page).all()

            results = []
            for fb in items:
                results.append({
                    'id': fb.id,
                    'user_id': fb.user_id,
                    'user_role': fb.user_role,
                    'institution': fb.institution or '',
                    'category': fb.category,
                    'severity': fb.severity,
                    'title': fb.title,
                    'description': fb.description[:200],
                    'experience_rating': fb.experience_rating,
                    'status': fb.status,
                    'is_resolved': fb.is_resolved,
                    'is_hidden': fb.is_hidden,
                    'is_flagged': fb.is_flagged,
                    'admin_viewed': fb.admin_viewed,
                    'admin_viewed_at': fb.admin_viewed_at.isoformat() if fb.admin_viewed_at else None,
                    'upvotes': fb.upvotes,
                    'reply_count': fb.reply_count,
                    'escalation_level': fb.escalation_level,
                    'sentiment_label': fb.sentiment_label,
                    'created_at': fb.created_at.isoformat() if fb.created_at else None,
                })
            return {'success': True, 'data': results, 'total': total,
                    'page': page, 'total_pages': total_pages}
        finally:
            db.close()

    def get_admin_analytics(self):
        db = self._get_db()
        try:
            total = db.query(Feedback).count()

            daily = db.query(
                func.date(Feedback.created_at).label('date'),
                func.count(Feedback.id)
            ).group_by(func.date(Feedback.created_at)).order_by(
                func.date(Feedback.created_at).desc()
            ).limit(30).all()

            category_dist = db.query(
                Feedback.category, func.count(Feedback.id)
            ).group_by(Feedback.category).order_by(func.count(Feedback.id).desc()).all()

            severity_dist = db.query(
                Feedback.severity, func.count(Feedback.id)
            ).group_by(Feedback.severity).order_by(
                case((Feedback.severity == 'critical', 0), (Feedback.severity == 'high', 1),
                     (Feedback.severity == 'medium', 2), else_=3)
            ).all()

            sentiment_dist = db.query(
                Feedback.sentiment_label, func.count(Feedback.id)
            ).filter(Feedback.sentiment_label.isnot(None)
            ).group_by(Feedback.sentiment_label).all()

            network_issues = db.query(FeedbackDiagnostics).filter(
                or_(FeedbackDiagnostics.vpn_active == True,
                    FeedbackDiagnostics.offline_mode == True,
                    FeedbackDiagnostics.mqtt_sync_status != 'ok',
                    FeedbackDiagnostics.network_latency_ms > 500)
            ).count()

            device_breakdown = db.query(
                FeedbackDiagnostics.device_type, func.count(FeedbackDiagnostics.id)
            ).filter(FeedbackDiagnostics.device_type.isnot(None)
            ).group_by(FeedbackDiagnostics.device_type).all()

            resolution_rate = 0
            if total > 0:
                resolved = db.query(Feedback).filter(Feedback.is_resolved == True).count()
                resolution_rate = round((resolved / total) * 100, 1)

            avg_upvotes = db.query(func.avg(Feedback.upvotes)).scalar() or 0

            top_categories = [{'name': c[0], 'count': c[1]} for c in category_dist[:8]]
            top_severities = [{'name': s[0], 'count': s[1]} for s in severity_dist]
            top_sentiments = [{'label': s[0], 'count': s[1]} for s in sentiment_dist]

            return {'success': True, 'data': {
                'total': total,
                'daily_counts': [{'date': str(d[0]), 'count': d[1]} for d in daily[::-1]],
                'category_distribution': top_categories,
                'severity_distribution': top_severities,
                'sentiment_distribution': top_sentiments,
                'network_issues': network_issues,
                'device_breakdown': [{'type': d[0], 'count': d[1]} for d in device_breakdown],
                'resolution_rate': resolution_rate,
                'avg_upvotes': round(avg_upvotes, 1),
            }}
        finally:
            db.close()

    def get_user_activity_insights(self):
        db = self._get_db()
        try:
            top_contributors = db.query(
                Feedback.user_id, Feedback.user_role,
                func.count(Feedback.id).label('submissions'),
                func.sum(Feedback.upvotes).label('total_upvotes')
            ).group_by(Feedback.user_id, Feedback.user_role
            ).order_by(func.count(Feedback.id).desc()).limit(10).all()

            repeat_contributors = db.query(
                Feedback.user_id,
                func.count(Feedback.id).label('count')
            ).group_by(Feedback.user_id
            ).having(func.count(Feedback.id) > 1).count()

            total_unique = db.query(
                Feedback.user_id
            ).distinct().count()

            avg_upvotes_per_user = db.query(
                func.avg(Feedback.upvotes)
            ).scalar() or 0

            return {'success': True, 'data': {
                'total_unique_contributors': total_unique,
                'repeat_contributors': repeat_contributors,
                'avg_upvotes_per_user': round(avg_upvotes_per_user, 1),
                'top_contributors': [{
                    'user_id': u[0],
                    'role': u[1],
                    'submissions': u[2],
                    'total_upvotes': u[3] or 0
                } for u in top_contributors],
            }}
        finally:
            db.close()

    def get_response_time_analytics(self):
        db = self._get_db()
        try:
            resolved_items = db.query(Feedback).filter(
                Feedback.is_resolved == True,
                Feedback.resolved_at.isnot(None),
                Feedback.created_at.isnot(None)
            ).all()

            response_times = []
            for fb in resolved_items:
                created = fb.created_at
                resolved = fb.resolved_at
                if isinstance(created, datetime) and isinstance(resolved, datetime):
                    hours = (resolved - created).total_seconds() / 3600
                    response_times.append(hours)

            avg_hours = round(sum(response_times) / len(response_times), 1) if response_times else 0
            max_hours = round(max(response_times), 1) if response_times else 0
            min_hours = round(min(response_times), 1) if response_times else 0

            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today_start - timedelta(days=7)
            recent_resolved = db.query(Feedback).filter(
                Feedback.is_resolved == True,
                Feedback.resolved_at >= week_ago
            ).count()

            return {'success': True, 'data': {
                'avg_resolution_hours': avg_hours,
                'max_resolution_hours': max_hours,
                'min_resolution_hours': min_hours,
                'recently_resolved_7d': recent_resolved,
                'total_resolved': len(response_times),
            }}
        finally:
            db.close()

    def export_csv(self, filters=None):
        db = self._get_db()
        try:
            query = db.query(Feedback)
            if filters:
                if filters.get('status'):
                    query = query.filter(Feedback.status == filters['status'])
                if filters.get('category'):
                    query = query.filter(Feedback.category == filters['category'])
                if filters.get('severity'):
                    query = query.filter(Feedback.severity == filters['severity'])
                if filters.get('institution'):
                    query = query.filter(Feedback.institution.ilike(f"%{filters['institution']}%"))
            items = query.order_by(Feedback.created_at.desc()).all()
            import io, csv
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Title', 'Category', 'Severity', 'Status', 'Institution',
                           'Upvotes', 'Replies', 'IsResolved', 'Sentiment', 'CreatedAt'])
            for fb in items:
                writer.writerow([fb.id, fb.title, fb.category, fb.severity, fb.status,
                               fb.institution, fb.upvotes, fb.reply_count, fb.is_resolved,
                               fb.sentiment_label, fb.created_at.isoformat() if fb.created_at else ''])
            return {'success': True, 'csv': output.getvalue()}
        finally:
            db.close()
