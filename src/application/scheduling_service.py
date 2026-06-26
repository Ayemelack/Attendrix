from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, time
import logging

from src.domain.entities import (
    Schedule, ClassSession, Course, User, Department,
    Schedule, ClassSession, UserRole
)
from src.infrastructure.repositories import (
    schedule_repo, class_session_repo, course_repo, user_repo,
    course_enrollment_repo
)

logger = logging.getLogger(__name__)


class ConflictType:
    """Types of scheduling conflicts"""
    LECTURER_DOUBLE_BOOKING = "lecturer_double_booking"
    ROOM_DOUBLE_BOOKING = "room_double_booking"
    STUDENT_OVERLAP = "student_overlap"
    DEPARTMENT_CONFLICT = "department_conflict"
    TIME_SLOT_UNAVAILABLE = "time_slot_unavailable"


class ScheduleConflict:
    """Represents a scheduling conflict"""
    
    def __init__(self, conflict_type: str, description: str, 
                 conflicting_schedules: List[Dict[str, Any]], 
                 severity: str = "high"):
        self.conflict_type = conflict_type
        self.description = description
        self.conflicting_schedules = conflicting_schedules
        self.severity = severity
        self.detected_at = datetime.utcnow()


class SchedulingEngine:
    """Advanced scheduling engine with conflict detection"""
    
    def __init__(self):
        self.schedule_repo = schedule_repo
        self.class_session_repo = class_session_repo
        self.course_repo = course_repo
        self.user_repo = user_repo
        self.course_enrollment_repo = course_enrollment_repo
    
    def create_schedule(self, schedule_data: Dict[str, Any]) -> Tuple[Optional[str], List[ScheduleConflict]]:
        """Create a new schedule with conflict detection"""
        conflicts = []
        
        try:
            # Check for conflicts before creating
            conflicts = self.detect_conflicts(schedule_data)
            
            if conflicts:
                logger.warning(f"Schedule creation blocked due to {len(conflicts)} conflicts")
                return None, conflicts
            
            # Create schedule entity
            schedule = Schedule(
                institution_id=schedule_data['institution_id'],
                course_id=schedule_data['course_id'],
                lecturer_id=schedule_data['lecturer_id'],
                room_id=schedule_data.get('room_id'),
                day_of_week=schedule_data['day_of_week'],
                start_time=schedule_data['start_time'],
                end_time=schedule_data['end_time'],
                start_date=schedule_data.get('start_date'),
                end_date=schedule_data.get('end_date'),
                is_recurring=schedule_data.get('is_recurring', True)
            )
            
            # Convert to dict for storage
            schedule_dict = {
                'id': schedule.id,
                'institution_id': schedule.institution_id,
                'course_id': schedule.course_id,
                'lecturer_id': schedule.lecturer_id,
                'room_id': schedule.room_id,
                'day_of_week': schedule.day_of_week,
                'start_time': schedule.start_time,
                'end_time': schedule.end_time,
                'start_date': schedule.start_date.isoformat() if schedule.start_date else None,
                'end_date': schedule.end_date.isoformat() if schedule.end_date else None,
                'is_recurring': schedule.is_recurring,
                'is_active': schedule.is_active,
                'created_at': schedule.created_at.isoformat(),
                'updated_at': schedule.updated_at.isoformat()
            }
            
            # Save to database
            schedule_id = self.schedule_repo.create(schedule_dict)
            
            logger.info(f"Schedule created successfully: {schedule_id}")
            return schedule_id, []
            
        except Exception as e:
            logger.error(f"Failed to create schedule: {str(e)}")
            return None, []
    
    def detect_conflicts(self, schedule_data: Dict[str, Any]) -> List[ScheduleConflict]:
        """Detect all types of scheduling conflicts"""
        conflicts = []
        
        try:
            # Check lecturer double booking
            lecturer_conflicts = self._check_lecturer_conflicts(schedule_data)
            conflicts.extend(lecturer_conflicts)
            
            # Check room double booking
            room_conflicts = self._check_room_conflicts(schedule_data)
            conflicts.extend(room_conflicts)
            
            # Check student overlap
            student_conflicts = self._check_student_conflicts(schedule_data)
            conflicts.extend(student_conflicts)
            
            # Check department conflicts
            dept_conflicts = self._check_department_conflicts(schedule_data)
            conflicts.extend(dept_conflicts)
            
            # Check time slot availability
            time_conflicts = self._check_time_slot_conflicts(schedule_data)
            conflicts.extend(time_conflicts)
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Conflict detection failed: {str(e)}")
            return []
    
    def _check_lecturer_conflicts(self, schedule_data: Dict[str, Any]) -> List[ScheduleConflict]:
        """Check for lecturer double booking"""
        conflicts = []
        
        try:
            lecturer_id = schedule_data['lecturer_id']
            day_of_week = schedule_data['day_of_week']
            start_time = schedule_data['start_time']
            end_time = schedule_data['end_time']
            
            # Get existing schedules for the lecturer
            existing_schedules = self.schedule_repo.get_by_multiple_fields([
                {'field': 'lecturer_id', 'value': lecturer_id},
                {'field': 'day_of_week', 'value': day_of_week},
                {'field': 'is_active', 'value': True}
            ])
            
            for existing_schedule in existing_schedules:
                if self._time_ranges_overlap(
                    start_time, end_time,
                    existing_schedule['start_time'], existing_schedule['end_time']
                ):
                    conflict = ScheduleConflict(
                        conflict_type=ConflictType.LECTURER_DOUBLE_BOOKING,
                        description=f"Lecturer is already scheduled during this time slot",
                        conflicting_schedules=[existing_schedule],
                        severity="high"
                    )
                    conflicts.append(conflict)
            
        except Exception as e:
            logger.error(f"Lecturer conflict check failed: {str(e)}")
        
        return conflicts
    
    def _check_room_conflicts(self, schedule_data: Dict[str, Any]) -> List[ScheduleConflict]:
        """Check for room double booking"""
        conflicts = []
        
        try:
            room_id = schedule_data.get('room_id')
            if not room_id:
                return conflicts
            
            day_of_week = schedule_data['day_of_week']
            start_time = schedule_data['start_time']
            end_time = schedule_data['end_time']
            
            # Get existing schedules for the room
            existing_schedules = self.schedule_repo.get_by_multiple_fields([
                {'field': 'room_id', 'value': room_id},
                {'field': 'day_of_week', 'value': day_of_week},
                {'field': 'is_active', 'value': True}
            ])
            
            for existing_schedule in existing_schedules:
                if self._time_ranges_overlap(
                    start_time, end_time,
                    existing_schedule['start_time'], existing_schedule['end_time']
                ):
                    conflict = ScheduleConflict(
                        conflict_type=ConflictType.ROOM_DOUBLE_BOOKING,
                        description=f"Room is already booked during this time slot",
                        conflicting_schedules=[existing_schedule],
                        severity="high"
                    )
                    conflicts.append(conflict)
            
        except Exception as e:
            logger.error(f"Room conflict check failed: {str(e)}")
        
        return conflicts
    
    def _check_student_conflicts(self, schedule_data: Dict[str, Any]) -> List[ScheduleConflict]:
        """Check for student enrollment overlaps"""
        conflicts = []
        
        try:
            course_id = schedule_data['course_id']
            day_of_week = schedule_data['day_of_week']
            start_time = schedule_data['start_time']
            end_time = schedule_data['end_time']
            
            # Get enrolled students for the new course
            enrolled_students = self.course_enrollment_repo.get_active_enrollments(course_id)
            
            for enrollment in enrolled_students:
                student_id = enrollment['student_id']
                
                # Get student's existing schedules
                student_schedules = self._get_student_schedules(student_id, day_of_week)
                
                for existing_schedule in student_schedules:
                    if self._time_ranges_overlap(
                        start_time, end_time,
                        existing_schedule['start_time'], existing_schedule['end_time']
                    ):
                        conflict = ScheduleConflict(
                            conflict_type=ConflictType.STUDENT_OVERLAP,
                            description=f"Student {student_id} has overlapping course",
                            conflicting_schedules=[existing_schedule],
                            severity="medium"
                        )
                        conflicts.append(conflict)
            
        except Exception as e:
            logger.error(f"Student conflict check failed: {str(e)}")
        
        return conflicts
    
    def _check_department_conflicts(self, schedule_data: Dict[str, Any]) -> List[ScheduleConflict]:
        """Check for department-level conflicts or policies"""
        conflicts = []
        
        try:
            # Get course and department information
            course_id = schedule_data['course_id']
            course = self.course_repo.get_by_id(course_id)
            
            if not course:
                return conflicts
            
            # Check department-specific scheduling rules
            # This is a placeholder for department-specific business logic
            department_id = course.get('department_id')
            
            # Example: Check if department has maximum daily class limits
            day_schedules = self.schedule_repo.get_by_multiple_fields([
                {'field': 'department_id', 'value': department_id},
                {'field': 'day_of_week', 'value': schedule_data['day_of_week']},
                {'field': 'is_active', 'value': True}
            ])
            
            # Example rule: Maximum 8 classes per day per department
            if len(day_schedules) >= 8:
                conflict = ScheduleConflict(
                    conflict_type=ConflictType.DEPARTMENT_CONFLICT,
                    description="Department exceeds maximum daily class limit",
                    conflicting_schedules=day_schedules[:3],  # Show first 3 as examples
                    severity="medium"
                )
                conflicts.append(conflict)
            
        except Exception as e:
            logger.error(f"Department conflict check failed: {str(e)}")
        
        return conflicts
    
    def _check_time_slot_conflicts(self, schedule_data: Dict[str, Any]) -> List[ScheduleConflict]:
        """Check for institutional time slot restrictions"""
        conflicts = []
        
        try:
            start_time = schedule_data['start_time']
            end_time = schedule_data['end_time']
            
            # Convert time strings to datetime objects for comparison
            start_dt = datetime.strptime(start_time, '%H:%M').time()
            end_dt = datetime.strptime(end_time, '%H:%M').time()
            
            # Check if schedule is within institutional hours
            institutional_start = time(8, 0)  # 8:00 AM
            institutional_end = time(21, 0)   # 9:00 PM
            
            if start_dt < institutional_start or end_dt > institutional_end:
                conflict = ScheduleConflict(
                    conflict_type=ConflictType.TIME_SLOT_UNAVAILABLE,
                    description="Schedule outside institutional operating hours",
                    conflicting_schedules=[],
                    severity="high"
                )
                conflicts.append(conflict)
            
            # Check minimum class duration (e.g., 30 minutes)
            duration_minutes = (datetime.combine(datetime.today(), end_dt) - 
                               datetime.combine(datetime.today(), start_dt)).total_seconds() / 60
            
            if duration_minutes < 30:
                conflict = ScheduleConflict(
                    conflict_type=ConflictType.TIME_SLOT_UNAVAILABLE,
                    description="Class duration too short (minimum 30 minutes)",
                    conflicting_schedules=[],
                    severity="medium"
                )
                conflicts.append(conflict)
            
        except Exception as e:
            logger.error(f"Time slot conflict check failed: {str(e)}")
        
        return conflicts
    
    def _time_ranges_overlap(self, start1: str, end1: str, start2: str, end2: str) -> bool:
        """Check if two time ranges overlap"""
        try:
            # Convert time strings to datetime objects
            start1_dt = datetime.strptime(start1, '%H:%M').time()
            end1_dt = datetime.strptime(end1, '%H:%M').time()
            start2_dt = datetime.strptime(start2, '%H:%M').time()
            end2_dt = datetime.strptime(end2, '%H:%M').time()
            
            # Convert to minutes for easier comparison
            start1_min = start1_dt.hour * 60 + start1_dt.minute
            end1_min = end1_dt.hour * 60 + end1_dt.minute
            start2_min = start2_dt.hour * 60 + start2_dt.minute
            end2_min = end2_dt.hour * 60 + end2_dt.minute
            
            # Check for overlap
            return not (end1_min <= start2_min or end2_min <= start1_min)
            
        except Exception as e:
            logger.error(f"Time overlap check failed: {str(e)}")
            return False
    
    def _get_student_schedules(self, student_id: str, day_of_week: int) -> List[Dict[str, Any]]:
        """Get all schedules for a student on a specific day"""
        try:
            # Get student's active enrollments
            enrollments = self.course_enrollment_repo.get_active_enrollments(
                student_id=student_id
            )
            
            student_schedules = []
            
            for enrollment in enrollments:
                course_id = enrollment['course_id']
                
                # Get schedules for this course on the specified day
                course_schedules = self.schedule_repo.get_by_multiple_fields([
                    {'field': 'course_id', 'value': course_id},
                    {'field': 'day_of_week', 'value': day_of_week},
                    {'field': 'is_active', 'value': True}
                ])
                
                student_schedules.extend(course_schedules)
            
            return student_schedules
            
        except Exception as e:
            logger.error(f"Failed to get student schedules: {str(e)}")
            return []
    
    def generate_class_sessions(self, schedule_id: str, start_date: datetime, 
                              end_date: datetime) -> List[str]:
        """Generate individual class sessions from a recurring schedule"""
        sessions = []
        
        try:
            # Get the schedule
            schedule = self.schedule_repo.get_by_id(schedule_id)
            if not schedule:
                return sessions
            
            day_of_week = schedule['day_of_week']
            
            # Generate sessions for each occurrence within the date range
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() + 1 == day_of_week:  # Python weekday is 0-6, our is 1-7
                    # Create class session
                    session_start = datetime.combine(
                        current_date.date(),
                        datetime.strptime(schedule['start_time'], '%H:%M').time()
                    )
                    session_end = datetime.combine(
                        current_date.date(),
                        datetime.strptime(schedule['end_time'], '%H:%M').time()
                    )
                    
                    session_data = {
                        'schedule_id': schedule_id,
                        'course_id': schedule['course_id'],
                        'lecturer_id': schedule['lecturer_id'],
                        'session_date': session_start.isoformat(),
                        'start_time': session_start.isoformat(),
                        'end_time': session_end.isoformat(),
                        'room_id': schedule.get('room_id'),
                        'status': 'scheduled'
                    }
                    
                    session_id = self.class_session_repo.create(session_data)
                    if session_id:
                        sessions.append(session_id)
                
                current_date += timedelta(days=1)
            
            logger.info(f"Generated {len(sessions)} class sessions for schedule {schedule_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate class sessions: {str(e)}")
        
        return sessions
    
    def get_department_schedule_overview(self, department_id: str, 
                                      start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get comprehensive schedule overview for a department"""
        try:
            # Get all courses in the department
            courses = self.course_repo.get_by_department(department_id)
            
            overview = {
                'department_id': department_id,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'courses': [],
                'total_sessions': 0,
                'conflicts': [],
                'utilization': {}
            }
            
            for course in courses:
                course_id = course['id']
                
                # Get schedules for this course
                schedules = self.schedule_repo.get_by_course(course_id)
                
                course_info = {
                    'course_id': course_id,
                    'course_name': course['name'],
                    'course_code': course['code'],
                    'schedules': schedules,
                    'sessions_count': 0
                }
                
                # Count sessions for each schedule
                for schedule in schedules:
                    sessions = self.generate_class_sessions(
                        schedule['id'], start_date, end_date
                    )
                    course_info['sessions_count'] += len(sessions)
                    overview['total_sessions'] += len(sessions)
                
                overview['courses'].append(course_info)
            
            return overview
            
        except Exception as e:
            logger.error(f"Failed to get department schedule overview: {str(e)}")
            return {}
    
    def optimize_schedule(self, institution_id: str) -> Dict[str, Any]:
        """Optimize schedules for better resource utilization"""
        try:
            # This is a placeholder for schedule optimization logic
            # In a real implementation, this would use algorithms to:
            # 1. Minimize gaps between classes
            # 2. Balance room utilization
            # 3. Optimize lecturer workload
            # 4. Consider student preferences
            
            optimization_results = {
                'institution_id': institution_id,
                'optimizations': [],
                'potential_improvements': [],
                'utilization_metrics': {}
            }
            
            # Example: Check room utilization
            # Get all active schedules
            schedules = self.schedule_repo.get_by_institution(institution_id)
            
            room_usage = {}
            for schedule in schedules:
                room_id = schedule.get('room_id')
                if room_id:
                    if room_id not in room_usage:
                        room_usage[room_id] = 0
                    room_usage[room_id] += 1
            
            # Find underutilized rooms
            for room_id, usage_count in room_usage.items():
                if usage_count < 10:  # Example threshold
                    optimization_results['potential_improvements'].append({
                        'type': 'underutilized_room',
                        'room_id': room_id,
                        'usage_count': usage_count,
                        'suggestion': 'Consider consolidating classes or scheduling more classes in this room'
                    })
            
            return optimization_results
            
        except Exception as e:
            logger.error(f"Schedule optimization failed: {str(e)}")
            return {}


# Global scheduling engine instance
scheduling_engine = SchedulingEngine()
