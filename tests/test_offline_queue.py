"""Integration tests for the OfflineQueueService — the core networking engine.

These tests verify:
    1. Queue operations (enqueue, dequeue, pending, failed, stats)
    2. Sync engine (process queue, retry with exponential backoff)
    3. Conflict resolution strategies
    4. Queue health monitoring
    5. Integration with the mock Firebase backend
"""

import os
import sys
import json
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['USE_MOCK_FIREBASE'] = 'true'
os.environ['ENVIRONMENT'] = 'test'

from src.application.offline_queue_service import (
    OfflineQueueService,
    SyncStatus,
    OperationType,
)
from src.infrastructure.firebase_service import firebase_service


@pytest.fixture(autouse=True)
def reset_mock_db():
    """Reset the mock database before each test."""
    import src.infrastructure.firebase_service as fs
    fs._mock_database = {}
    fs.save_mock_database({})
    if not firebase_service._initialized:
        firebase_service.initialize()
    yield
    fs._mock_database = {}
    fs.save_mock_database({})


@pytest.fixture
def queue_service():
    """Create a fresh OfflineQueueService instance."""
    return OfflineQueueService(firebase_service)


class TestQueueOperations:
    """Test basic queue CRUD operations."""

    def test_enqueue_creates_entry(self, queue_service):
        entry_id = queue_service.enqueue(
            institution_id='inst_001',
            operation_type=OperationType.MARK_ATTENDANCE.value,
            payload={'student_id': 's1', 'session_code': 'ABC12345'},
            node_name='building_a',
        )
        assert entry_id is not None
        assert len(entry_id) > 0

        entry = firebase_service.get_document('offline_queue', entry_id)
        assert entry is not None
        assert entry['operation_type'] == 'mark_attendance'
        assert entry['status'] == SyncStatus.PENDING.value
        assert entry['node_name'] == 'building_a'

    def test_enqueue_with_priority(self, queue_service):
        normal_id = queue_service.enqueue(
            institution_id='inst_001',
            operation_type=OperationType.CREATE_ACTIVITY_LOG.value,
            payload={'message': 'normal'},
            priority=0,
        )
        high_id = queue_service.enqueue(
            institution_id='inst_001',
            operation_type=OperationType.MARK_ATTENDANCE.value,
            payload={'student_id': 's1'},
            priority=1,
        )
        assert normal_id != high_id

    def test_dequeue_removes_entry(self, queue_service):
        entry_id = queue_service.enqueue(
            institution_id='inst_001',
            operation_type=OperationType.CREATE_ATTENDANCE.value,
            payload={'course_id': 'c1'},
        )
        assert firebase_service.get_document('offline_queue', entry_id) is not None
        queue_service.dequeue(entry_id)
        assert firebase_service.get_document('offline_queue', entry_id) is None

    def test_get_pending_filters_correctly(self, queue_service):
        queue_service.enqueue('inst_001', 'type_a', {'d': 1})
        queue_service.enqueue('inst_001', 'type_b', {'d': 2})
        queue_service.enqueue('inst_002', 'type_a', {'d': 3})

        pending_inst1 = queue_service.get_pending(institution_id='inst_001')
        assert len(pending_inst1) == 2

        pending_all = queue_service.get_pending()
        assert len(pending_all) == 3

    def test_get_failed_returns_failed_only(self, queue_service):
        entry_id = queue_service.enqueue('inst_001', 'test_op', {'d': 1})
        firebase_service.update_document('offline_queue', entry_id, {
            'status': SyncStatus.FAILED.value,
        })
        failed = queue_service.get_failed('inst_001')
        assert len(failed) == 1
        assert failed[0]['id'] == entry_id

    def test_get_queue_stats(self, queue_service):
        e1 = queue_service.enqueue('inst_001', 'op_a', {'d': 1})
        e2 = queue_service.enqueue('inst_001', 'op_b', {'d': 2})
        e3 = queue_service.enqueue('inst_001', 'op_c', {'d': 3})

        firebase_service.update_document('offline_queue', e1, {
            'status': SyncStatus.SYNCED.value,
        })
        firebase_service.update_document('offline_queue', e2, {
            'status': SyncStatus.FAILED.value,
        })

        stats = queue_service.get_queue_stats('inst_001')
        assert stats['total'] == 3
        assert stats['synced'] == 1
        assert stats['failed'] == 1
        assert stats['pending'] == 1
        assert stats['queue_healthy'] is True

    def test_queue_stats_with_conflicts(self, queue_service):
        e1 = queue_service.enqueue('inst_001', 'op_a', {'d': 1})
        e2 = queue_service.enqueue('inst_001', 'op_b', {'d': 2})
        firebase_service.update_document('offline_queue', e2, {
            'status': SyncStatus.CONFLICT.value,
        })
        stats = queue_service.get_queue_stats('inst_001')
        assert stats['conflicts'] == 1
        assert stats['queue_healthy'] is False


class TestSyncEngine:
    """Test the core sync processing engine."""

    def test_process_queue_with_no_pending(self, queue_service):
        result = queue_service.process_queue('inst_001')
        assert result['status'] == 'idle'
        assert result['processed'] == 0

    def test_process_queue_single_success(self, queue_service):
        queue_service.enqueue('inst_001', 'test_op', {'key': 'value'})
        result = queue_service.process_queue('inst_001')
        assert result['processed'] == 1
        assert result['succeeded'] == 1
        assert result['failed'] == 0

        stats = queue_service.get_queue_stats('inst_001')
        assert stats['synced'] == 1

    def test_process_queue_with_custom_handler(self, queue_service):
        calls = []

        def handler(payload):
            calls.append(payload)
            return True, {'processed': payload}, None

        queue_service.enqueue('inst_001', 'custom_op', {'data': 'test'})
        result = queue_service.process_queue(
            'inst_001',
            handler_map={'custom_op': handler}
        )
        assert result['succeeded'] == 1
        assert len(calls) == 1
        assert calls[0]['data'] == 'test'

    def test_process_queue_handler_failure_retry(self, queue_service):
        call_count = [0]

        def failing_handler(payload):
            call_count[0] += 1
            return False, None, 'Simulated handler failure'

        queue_service.enqueue('inst_001', 'failing_op', {'data': 'x'})
        result = queue_service.process_queue(
            'inst_001',
            handler_map={'failing_op': failing_handler}
        )
        assert call_count[0] == 1
        assert result['failed'] == 1

        pending = queue_service.get_pending('inst_001')
        assert len(pending) == 1
        assert pending[0]['retry_count'] == 1

    def test_exponential_backoff(self, queue_service):
        delays = []
        for i in range(5):
            delays.append(queue_service._compute_backoff(i + 1))
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1] or delays[i] >= 2
        assert delays[-1] <= 60

    def test_eventual_failure_after_max_retries(self, queue_service):
        fail_count = [0]

        def always_fails(payload):
            fail_count[0] += 1
            return False, None, 'Always fails'

        queue_service._max_retries = 1
        queue_service._base_delay_seconds = 0
        entry_id = queue_service.enqueue('inst_001', 'doomed_op', {'x': 1})

        for i in range(queue_service._max_retries + 1):
            queue_service._processing = False
            result = queue_service.process_queue(
                'inst_001',
                handler_map={'doomed_op': always_fails}
            )

        entry = firebase_service.get_document('offline_queue', entry_id)
        assert entry['status'] == SyncStatus.FAILED.value


class TestConflictResolution:
    """Test conflict resolution strategies."""

    def test_lww_resolution(self, queue_service):
        entry_id = queue_service.enqueue('inst_001', 'test_op', {'data': 'v1'})
        firebase_service.update_document('offline_queue', entry_id, {
            'status': SyncStatus.CONFLICT.value,
            'conflict_info': 'version_mismatch',
        })
        result = queue_service.resolve_conflict(entry_id, strategy='lww')
        assert result is True
        entry = firebase_service.get_document('offline_queue', entry_id)
        assert entry['status'] == SyncStatus.PENDING.value

    def test_discard_local_strategy(self, queue_service):
        entry_id = queue_service.enqueue('inst_001', 'test_op', {'data': 'v1'})
        firebase_service.update_document('offline_queue', entry_id, {
            'status': SyncStatus.CONFLICT.value,
        })
        result = queue_service.resolve_conflict(entry_id, strategy='discard_local')
        assert result is True
        entry = firebase_service.get_document('offline_queue', entry_id)
        assert entry['status'] == SyncStatus.SYNCED.value
        assert entry['conflict_info'] == 'discarded_local'

    def test_force_local_strategy(self, queue_service):
        entry_id = queue_service.enqueue('inst_001', 'test_op', {'data': 'v1'})
        firebase_service.update_document('offline_queue', entry_id, {
            'status': SyncStatus.CONFLICT.value,
        })
        result = queue_service.resolve_conflict(entry_id, strategy='force_local')
        assert result is True
        entry = firebase_service.get_document('offline_queue', entry_id)
        assert entry['priority'] == 1
        assert entry['status'] == SyncStatus.PENDING.value


class TestRetryAndCleanup:
    """Test retry failed operations and cleanup."""

    def test_retry_single_failed_entry(self, queue_service):
        entry_id = queue_service.enqueue('inst_001', 'test_op', {'d': 1})
        firebase_service.update_document('offline_queue', entry_id, {
            'status': SyncStatus.FAILED.value,
            'retry_count': 3,
            'error_message': 'timeout',
        })
        count = queue_service.retry_failed(entry_id=entry_id)
        assert count == 1
        entry = firebase_service.get_document('offline_queue', entry_id)
        assert entry['status'] == SyncStatus.PENDING.value
        assert entry['retry_count'] == 0
        assert entry['error_message'] is None

    def test_retry_all_failed_in_institution(self, queue_service):
        e1 = queue_service.enqueue('inst_001', 'op_a', {'d': 1})
        e2 = queue_service.enqueue('inst_001', 'op_b', {'d': 2})
        e3 = queue_service.enqueue('inst_002', 'op_c', {'d': 3})
        for eid in [e1, e2, e3]:
            firebase_service.update_document('offline_queue', eid, {
                'status': SyncStatus.FAILED.value,
            })
        count = queue_service.retry_failed(institution_id='inst_001')
        assert count == 2
        e1e = firebase_service.get_document('offline_queue', e1)
        e3e = firebase_service.get_document('offline_queue', e3)
        assert e1e['status'] == SyncStatus.PENDING.value
        assert e3e['status'] == SyncStatus.FAILED.value

    def test_clear_synced_older_than(self, queue_service):
        e1 = queue_service.enqueue('inst_001', 'op_a', {'d': 1})
        e2 = queue_service.enqueue('inst_001', 'op_b', {'d': 2})
        for eid in [e1, e2]:
            firebase_service.update_document('offline_queue', eid, {
                'status': SyncStatus.SYNCED.value,
                'synced_at': (datetime.utcnow() - timedelta(hours=48)).isoformat(),
            })
        removed = queue_service.clear_synced('inst_001', older_than_hours=24)
        assert removed == 2
        assert firebase_service.get_document('offline_queue', e1) is None

    def test_clear_only_inst_001(self, queue_service):
        e1 = queue_service.enqueue('inst_001', 'op_a', {'d': 1})
        e2 = queue_service.enqueue('inst_002', 'op_b', {'d': 2})
        for eid, inst in [(e1, 'inst_001'), (e2, 'inst_002')]:
            firebase_service.update_document('offline_queue', eid, {
                'status': SyncStatus.SYNCED.value,
                'synced_at': (datetime.utcnow() - timedelta(hours=48)).isoformat(),
            })
        removed = queue_service.clear_synced('inst_001', older_than_hours=24)
        assert removed == 1


class TestSyncHealth:
    """Test sync health monitoring and estimation."""

    def test_estimate_sync_duration(self, queue_service):
        for i in range(5):
            queue_service.enqueue('inst_001', 'test_op', {'i': i})
        estimate = queue_service.estimate_sync_duration('inst_001')
        assert estimate['pending_operations'] == 5
        assert estimate['batches_needed'] == 1
        assert estimate['estimated_seconds'] > 0

    def test_get_node_sync_status(self, queue_service):
        queue_service.enqueue('inst_001', 'op_a', {'d': 1}, node_name='building_a')
        queue_service.enqueue('inst_001', 'op_b', {'d': 2}, node_name='building_a')
        queue_service.enqueue('inst_001', 'op_c', {'d': 3}, node_name='building_b')

        nodes = queue_service.get_node_sync_status('inst_001')
        assert len(nodes) == 2
        node_a = next(n for n in nodes if n['node_name'] == 'building_a')
        node_b = next(n for n in nodes if n['node_name'] == 'building_b')
        assert node_a['total'] == 2
        assert node_b['total'] == 1

    def test_checksum_generation(self, queue_service):
        cs1 = queue_service._compute_checksum({'a': 1, 'b': 2})
        cs2 = queue_service._compute_checksum({'b': 2, 'a': 1})
        cs3 = queue_service._compute_checksum({'a': 1, 'b': 3})
        assert cs1 == cs2
        assert cs1 != cs3
        assert len(cs1) == 16


class TestProcessingGuard:
    """Test that concurrent processing is prevented."""

    def test_prevents_concurrent_processing(self, queue_service):
        queue_service._processing = True
        result = queue_service.process_queue('inst_001')
        assert result['status'] == 'already_processing'
        queue_service._processing = False

    def test_releases_guard_after_processing(self, queue_service):
        queue_service.enqueue('inst_001', 'test_op', {'d': 1})
        result = queue_service.process_queue('inst_001')
        assert result['status'] == 'completed'
        assert queue_service._processing is False
