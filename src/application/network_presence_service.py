import logging
import time
from datetime import datetime, date
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def parse_user_agent(ua_string: str) -> dict:
    """Parse browser, OS, and device type from User-Agent string."""
    if not ua_string:
        return {"browser": "Unknown", "os": "Unknown", "device_type": "Desktop"}
        
    ua = ua_string.lower()
    
    # OS Detection
    os_name = "Unknown"
    if "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "MacOS"
    elif "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "linux" in ua:
        os_name = "Linux"
        
    # Device Type Detection
    device_type = "Desktop"
    if "mobi" in ua or "iphone" in ua or "android" in ua:
        device_type = "Mobile"
        if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
            device_type = "Tablet"
    elif "ipad" in ua or "tablet" in ua:
        device_type = "Tablet"
        
    # Browser Detection
    browser = "Unknown"
    if "firefox" in ua and "seamonkey" not in ua:
        browser = "Firefox"
    elif "chrome" in ua and "chromium" not in ua:
        if "edg" in ua:
            browser = "Edge"
        elif "opr" in ua or "opera" in ua:
            browser = "Opera"
        else:
            browser = "Chrome"
    elif "safari" in ua and "chrome" not in ua and "chromium" not in ua:
        browser = "Safari"
    elif "msie" in ua or "trident" in ua:
        browser = "Internet Explorer"
        
    return {
        "browser": browser,
        "os": os_name,
        "device_type": device_type
    }

def ip_matches_range(ip: str, range_str: str) -> bool:
    """Check if IP address matches configured range string (supporting wildcards like 192.168.x.x)."""
    range_str = range_str.strip()
    ip = ip.strip()
    
    range_parts = range_str.split('.')
    ip_parts = ip.split('.')
    
    if len(range_parts) != 4 or len(ip_parts) != 4:
        return False
        
    for r_part, ip_part in zip(range_parts, ip_parts):
        r_part = r_part.lower()
        if r_part == 'x' or r_part == '*':
            continue
        if r_part != ip_part:
            return False
    return True

class NetworkPresenceService:
    """Passive presence monitoring service for connected users."""
    def __init__(self):
        from src.infrastructure.firebase_service import firebase_service
        self._legacy_firebase = firebase_service
        self.last_write_times = {}  # user_id -> float timestamp
        self.user_info_cache = {}  # user_id -> {"name": str, "student_id": str}

    def update_presence(self, user_id: str, institution_id: str, email: str, role: str, ip_address: str, user_agent: str):
        """Passively log or update user presence (throttled to max once/60s)."""
        try:
            now_time = time.time()
            last_write = self.last_write_times.get(user_id, 0)
            
            # Throttling to protect database performance
            if now_time - last_write < 60:
                return

            self.last_write_times[user_id] = now_time

            # Retrieve first/last name and student_id (cache values to minimize db reads)
            user_info = self.user_info_cache.get(user_id)
            if not user_info:
                user_doc = self._legacy_firebase.get_document('users', user_id)
                if user_doc:
                    first_name = user_doc.get('first_name', '')
                    last_name = user_doc.get('last_name', '')
                    name = f"{first_name} {last_name}".strip()
                    student_id = user_doc.get('student_id', '') or user_doc.get('id', '')
                    user_info = {"name": name, "student_id": student_id}
                    self.user_info_cache[user_id] = user_info
                else:
                    user_info = {"name": email, "student_id": user_id}

            ua_info = parse_user_agent(user_agent)
            
            presence_data = {
                'id': user_id,
                'user_id': user_id,
                'institution_id': institution_id,
                'email': email,
                'role': role,
                'name': user_info["name"],
                'student_id': user_info["student_id"],
                'ip_address': ip_address,
                'user_agent': user_agent,
                'browser': ua_info["browser"],
                'os': ua_info["os"],
                'device_type': ua_info["device_type"],
                'last_activity_time': datetime.utcnow().isoformat()
            }
            
            # Check existing doc to preserve the initial login_time
            existing = self._legacy_firebase.get_document('network_presence', user_id)
            if existing:
                presence_data['login_time'] = existing.get('login_time', datetime.utcnow().isoformat())
                self._legacy_firebase.update_document('network_presence', user_id, presence_data)
            else:
                presence_data['login_time'] = datetime.utcnow().isoformat()
                self._legacy_firebase.create_document('network_presence', presence_data, user_id)
                
        except Exception as e:
            logger.error(f"Failed to update user presence: {e}")

    def get_presence_list(self, institution_id: str) -> List[Dict[str, Any]]:
        """Retrieve connected users presence with dynamic attendance matches."""
        try:
            # Query presence list
            presences = self._legacy_firebase.query_documents(
                'network_presence',
                filters=[{'field': 'institution_id', 'value': institution_id}]
            )
            
            # Query IP ranges config
            config_doc = self._legacy_firebase.get_document('network_presence_config', institution_id)
            ranges = config_doc.get('ranges', []) if config_doc else []
            
            # Get current day in UTC
            today_str = date.today().isoformat()
            
            results = []
            now = datetime.utcnow()
            
            for p in presences:
                last_act_str = p.get('last_activity_time')
                status = "Offline"
                if last_act_str:
                    try:
                        last_act = datetime.fromisoformat(last_act_str)
                        diff_seconds = (now - last_act).total_seconds()
                        if diff_seconds < 300:
                            status = "Online"
                        elif diff_seconds < 900:
                            status = "Idle"
                    except:
                        pass
                
                ip = p.get('ip_address', '')
                on_campus = False
                for r in ranges:
                    if ip_matches_range(ip, r):
                        on_campus = True
                        break
                
                network_status = "On Campus" if on_campus else "Outside Campus"
                
                # Dynamic Attendance details (queries authoritative table, no duplicate writes)
                attendance_status = "Not Marked"
                face_status = "Pending"
                
                if p.get('role') == 'student':
                    student_id = p.get('user_id')
                    records = self._legacy_firebase.query_documents(
                        'attendance_records',
                        filters=[
                            {'field': 'student_id', 'value': student_id},
                            {'field': 'institution_id', 'value': institution_id}
                        ]
                    )
                    
                    marked_today = False
                    face_verified_today = False
                    has_face_provided = False
                    for r_doc in records:
                        mark_time_str = r_doc.get('mark_time', r_doc.get('created_at', ''))
                        if mark_time_str and mark_time_str.startswith(today_str):
                            marked_today = True
                            if r_doc.get('face_verified') is True:
                                face_verified_today = True
                            biometric_check = r_doc.get('biometric_check') or ('verified' if r_doc.get('face_verified') else '')
                            if biometric_check and biometric_check != 'not_provided':
                                has_face_provided = True
                    
                    if marked_today:
                        attendance_status = "Marked"
                        face_status = "Verified" if face_verified_today else ("Failed" if has_face_provided else "Not Provided")
                else:
                    attendance_status = "N/A"
                    face_status = "N/A"
                
                results.append({
                    'student_name': p.get('name', p.get('email', '')),
                    'student_id': p.get('student_id', p.get('user_id', '')),
                    'role': p.get('role', ''),
                    'login_status': status,  # maps to UI field
                    'attendance_status': attendance_status,
                    'face_status': face_status,
                    'login_time': p.get('login_time'),
                    'last_activity_time': p.get('last_activity_time'),
                    'ip_address': ip,
                    'browser': p.get('browser', 'Unknown'),
                    'os': p.get('os', 'Unknown'),
                    'device_type': p.get('device_type', 'Desktop'),
                    'session_status': 'Active' if status in ('Online', 'Idle') else 'Inactive',
                    'network_status': network_status
                })
                
            return results
        except Exception as e:
            logger.error(f"Failed to fetch presence list: {e}")
            return []

    def get_config(self, institution_id: str) -> List[str]:
        """Fetch institutional network ranges."""
        try:
            doc = self._legacy_firebase.get_document('network_presence_config', institution_id)
            if doc:
                return doc.get('ranges', [])
            return []
        except Exception as e:
            logger.error(f"Failed to fetch IP config: {e}")
            return []

    def save_config(self, institution_id: str, ranges: List[str]):
        """Save institutional network ranges."""
        try:
            data = {
                'id': institution_id,
                'institution_id': institution_id,
                'ranges': ranges,
                'updated_at': datetime.utcnow().isoformat()
            }
            doc = self._legacy_firebase.get_document('network_presence_config', institution_id)
            if doc:
                self._legacy_firebase.update_document('network_presence_config', institution_id, data)
            else:
                self._legacy_firebase.create_document('network_presence_config', data, institution_id)
        except Exception as e:
            logger.error(f"Failed to save IP config: {e}")

presence_service = NetworkPresenceService()
