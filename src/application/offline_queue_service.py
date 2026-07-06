"""Offline Queue Service — Network resilience engine for Attendrix.

This service enables the system to operate during internet/power disruptions
by queueing operations locally and synchronizing when connectivity is restored.
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import uuid

from src.infrastructure.pg_repositories import pg_repos
from src.infrastructure.models import OfflineQueueItem

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class OperationType(Enum):
    CREATE_ATTENDANCE = "create_attendance"
    MARK_ATTENDANCE = "mark_attendance"
    CREATE_SESSION = "create_session"
    UPDATE_USER = "update_user"
    CREATE_ENROLLMENT = "create_enrollment"
    CREATE_ACTIVITY_LOG = "create_activity_log"
    CREATE_SECURITY_ALERT = "create_security_alert"
    UPSERT_NETWORK_NODE = "upsert_network_node"
    CREATE_PAYMENT = "create_payment"


class OfflineQueueService:
    """Queue-based offline sync engine with retry and conflict resolution."""

    def __init__(self):
        self._processing = False
        self._max_retries = 5
        self._base_delay_seconds = 2
        self._batch_size = 25

    # ── QUEUE OPERATIONS ──

    def enqueue(self, institution_id: str, operation_type: str,
                payload: Dict[str, Any], node_name: str = "web",
                priority: int = 0) -> str:
        """Add an operation to the offline queue."""
        now = datetime.utcnow()
        entry = OfflineQueueItem(
            id=str(uuid.uuid4()),
            institution_id=institution_id,
            operation_type=operation_type,
            payload=payload,
            status=SyncStatus.PENDING.value,
            node_name=node_name,
            priority=priority,
            retry_count=0,
            max_retries=self._max_retries,
            checksum=self._compute_checksum(payload),
            created_at=now,
            updated_at=now,
        )

        created = pg_repos.offline_queue.create(entry)
        entry_id = created.id
        logger.info(
            f"OFFLINE QUEUE: Enqueued {operation_type} for {institution_id} "
            f"(id={entry_id}, node={node_name})"
        )
        return entry_id

    def dequeue(self, entry_id: str) -> bool:
        """Remove a completed entry from the queue."""
        entry = pg_repos.offline_queue.get(entry_id)
        if not entry:
            return False
        pg_repos.offline_queue.delete(entry)
        return True

    def get_pending(self, institution_id: str = None,
                    limit: int = 100) -> List[OfflineQueueItem]:
        """Get all pending operations, optionally filtered by institution."""
        return pg_repos.offline_queue.get_pending(institution_id, limit)

    def get_failed(self, institution_id: str = None,
                   limit: int = 50) -> List[OfflineQueueItem]:
        """Get all failed operations for retry inspection."""
        return pg_repos.offline_queue.get_failed(institution_id, limit)

    def get_queue_stats(self, institution_id: str = None) -> Dict[str, Any]:
        """Get queue statistics for dashboard display."""
        all_entries = pg_repos.offline_queue.list_all()
        if institution_id:
            all_entries = [e for e in all_entries if e.institution_id == institution_id]

        total = len(all_entries)
        by_status = {}
        for e in all_entries:
            s = e.status or 'pending'
            by_status[s] = by_status.get(s, 0) + 1

        pending = by_status.get('pending', 0)
        failed = by_status.get('failed', 0)
        synced = by_status.get('synced', 0)
        in_progress = by_status.get('in_progress', 0)
        conflicts = by_status.get('conflict', 0)

        retry_count = sum(e.retry_count or 0 for e in all_entries if e.status in ('pending', 'failed'))

        oldest_pending = None
        if pending:
            pendings = [e for e in all_entries if e.status == 'pending']
            oldest_pending = pendings[0].created_at.isoformat() if pendings and pendings[0].created_at else None

        return {
            'total': total,
            'pending': pending,
            'in_progress': in_progress,
            'synced': synced,
            'failed': failed,
            'conflicts': conflicts,
            'total_retries': retry_count,
            'oldest_pending': oldest_pending,
            'queue_healthy': failed < 10 and conflicts == 0,
            'by_operation': self._group_by_operation(all_entries),
        }

    # ── SYNC ENGINE ──

    def process_queue(self, institution_id: str = None,
                      handler_map: Dict[str, Callable] = None) -> Dict[str, Any]:
        """Process pending operations in the queue."""
        if self._processing:
            return {'status': 'already_processing', 'processed': 0}

        self._processing = True
        started_at = datetime.utcnow()
        processed = 0
        succeeded = 0
        failed = 0
        errors = []

        try:
            pending = self.get_pending(institution_id, limit=self._batch_size)
            if not pending:
                return {
                    'status': 'idle',
                    'processed': 0,
                    'message': 'No pending operations',
                }

            for entry in pending:
                processed += 1
                entry_id = entry.id
                op_type = entry.operation_type or 'unknown'
                retry_count = entry.retry_count or 0
                max_retries = entry.max_retries or self._max_retries

                if entry.next_retry_at and datetime.utcnow() < entry.next_retry_at:
                    continue

                entry.status = SyncStatus.IN_PROGRESS.value
                entry.updated_at = datetime.utcnow()
                pg_repos.offline_queue.update(entry)

                try:
                    payload = entry.payload or {}

                    if handler_map and op_type in handler_map:
                        handler = handler_map[op_type]
                        success, result, error = handler(payload)
                    else:
                        success, result, error = self._default_handler(op_type, payload)

                    if success:
                        entry.status = SyncStatus.SYNCED.value
                        entry.synced_at = datetime.utcnow()
                        entry.updated_at = datetime.utcnow()
                        pg_repos.offline_queue.update(entry)
                        succeeded += 1
                    else:
                        raise Exception(error or 'Handler returned failure')

                except Exception as e:
                    error_msg = str(e)
                    new_retry_count = retry_count + 1

                    if new_retry_count >= max_retries:
                        entry.status = SyncStatus.FAILED.value
                        entry.retry_count = new_retry_count
                        entry.error_message = error_msg
                        entry.updated_at = datetime.utcnow()
                        pg_repos.offline_queue.update(entry)
                        failed += 1
                        errors.append({
                            'id': entry_id,
                            'operation': op_type,
                            'error': error_msg,
                            'retries': new_retry_count,
                        })
                        logger.warning(
                            f"OFFLINE QUEUE: {entry_id} failed after "
                            f"{new_retry_count} retries: {error_msg}"
                        )
                    else:
                        delay = self._compute_backoff(new_retry_count)
                        next_retry = datetime.utcnow() + timedelta(seconds=delay)
                        entry.status = SyncStatus.PENDING.value
                        entry.retry_count = new_retry_count
                        entry.error_message = error_msg
                        entry.next_retry_at = next_retry
                        entry.updated_at = datetime.utcnow()
                        pg_repos.offline_queue.update(entry)
                        failed += 1
                        logger.info(
                            f"OFFLINE QUEUE: {entry_id} will retry in {delay}s "
                            f"(attempt {new_retry_count}/{max_retries})"
                        )

        except Exception as e:
            logger.error(f"OFFLINE QUEUE: Sync engine error: {e}")
        finally:
            self._processing = False

        elapsed = (datetime.utcnow() - started_at).total_seconds()
        return {
            'status': 'completed',
            'processed': processed,
            'succeeded': succeeded,
            'failed': failed,
            'errors': errors[:10],
            'elapsed_seconds': round(elapsed, 2),
            'timestamp': datetime.utcnow().isoformat(),
        }

    def retry_failed(self, entry_id: str = None,
                     institution_id: str = None) -> int:
        """Reset failed operations back to pending for retry."""
        if entry_id:
            entry = pg_repos.offline_queue.get(entry_id)
            if entry:
                entry.status = SyncStatus.PENDING.value
                entry.retry_count = 0
                entry.error_message = None
                entry.next_retry_at = None
                entry.updated_at = datetime.utcnow()
                pg_repos.offline_queue.update(entry)
                return 1
            return 0
        else:
            failed = pg_repos.offline_queue.get_failed(institution_id, limit=1000)
            count = 0
            for entry in failed:
                entry.status = SyncStatus.PENDING.value
                entry.retry_count = 0
                entry.error_message = None
                entry.next_retry_at = None
                entry.updated_at = datetime.utcnow()
                pg_repos.offline_queue.update(entry)
                count += 1
            logger.info(f"OFFLINE QUEUE: Reset {count} failed entries to pending")
            return count

    def clear_synced(self, institution_id: str = None,
                     older_than_hours: int = 24) -> int:
        """Remove synced entries older than the threshold."""
        all_entries = pg_repos.offline_queue.list_all()
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        removed = 0
        for entry in all_entries:
            if entry.status != SyncStatus.SYNCED.value:
                continue
            if institution_id and entry.institution_id != institution_id:
                continue
            synced_at = entry.synced_at or entry.updated_at
            if synced_at and synced_at < cutoff:
                pg_repos.offline_queue.delete(entry)
                removed += 1
        if removed:
            logger.info(f"OFFLINE QUEUE: Cleared {removed} old synced entries")
        return removed

    # ── CONFLICT RESOLUTION ──

    def resolve_conflict(self, entry_id: str, strategy: str = 'lww',
                         resolution: Dict[str, Any] = None) -> bool:
        """Resolve a conflict for a specific queue entry."""
        entry = pg_repos.offline_queue.get(entry_id)
        if not entry:
            return False

        now = datetime.utcnow()

        if strategy == 'lww':
            entry.status = SyncStatus.PENDING.value
            entry.conflict_info = None
            entry.updated_at = now
            pg_repos.offline_queue.update(entry)
            return True
        elif strategy == 'discard_local':
            entry.status = SyncStatus.SYNCED.value
            entry.conflict_info = 'discarded_local'
            entry.synced_at = now
            entry.updated_at = now
            pg_repos.offline_queue.update(entry)
            return True
        elif strategy == 'force_local':
            entry.status = SyncStatus.PENDING.value
            entry.priority = 1
            entry.conflict_info = None
            entry.updated_at = now
            pg_repos.offline_queue.update(entry)
            return True
        elif strategy == 'manual' and resolution:
            entry.status = SyncStatus.PENDING.value
            entry.payload = resolution
            entry.conflict_info = 'manual_resolution'
            entry.updated_at = now
            pg_repos.offline_queue.update(entry)
            return True

        return False

    # ── SYNC HEALTH & BANDWIDTH AWARENESS ──

    def estimate_sync_duration(self, institution_id: str = None) -> Dict[str, Any]:
        """Estimate how long a full sync would take based on queue size."""
        pending = self.get_pending(institution_id)
        total_pending = len(pending)
        estimated_seconds = total_pending * 0.5
        estimated_data_kb = sum(
            len(json.dumps(entry.payload, default=str)) for entry in pending
        ) / 1024

        return {
            'pending_operations': total_pending,
            'estimated_seconds': round(estimated_seconds, 1),
            'estimated_data_kb': round(estimated_data_kb, 1),
            'estimated_recovery_mins': round(estimated_seconds / 60, 1),
            'batches_needed': max(1, (total_pending + self._batch_size - 1) // self._batch_size),
        }

    def get_node_sync_status(self, institution_id: str) -> List[Dict[str, Any]]:
        """Get per-node sync status for the network topology view."""
        all_entries = pg_repos.offline_queue.list_all()
        if institution_id:
            all_entries = [e for e in all_entries if e.institution_id == institution_id]

        nodes = {}
        for entry in all_entries:
            node = entry.node_name or 'unknown'
            if node not in nodes:
                nodes[node] = {
                    'node_name': node,
                    'total': 0,
                    'pending': 0,
                    'synced': 0,
                    'failed': 0,
                    'last_sync': None,
                }
            nodes[node]['total'] += 1
            status = entry.status or 'pending'
            if status in nodes[node]:
                nodes[node][status] += 1
            synced_at = entry.synced_at
            if synced_at:
                iso = synced_at.isoformat()
                if not nodes[node]['last_sync'] or iso > nodes[node]['last_sync']:
                    nodes[node]['last_sync'] = iso

        return sorted(nodes.values(), key=lambda n: n['total'], reverse=True)

    # ── INTERNAL HELPERS ──

    def _compute_backoff(self, retry_count: int) -> int:
        """Exponential backoff with jitter."""
        delay = min(
            self._base_delay_seconds * (2 ** (retry_count - 1)),
            60
        )
        import random
        jitter = random.uniform(0, delay * 0.1)
        return int(delay + jitter)

    def _compute_checksum(self, payload: Dict[str, Any]) -> str:
        """Compute a checksum for conflict detection."""
        import hashlib
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _default_handler(self, op_type: str, payload: Dict[str, Any]):
        """Default handler when no custom handler is provided."""
        logger.info(f"OFFLINE QUEUE: Default handling {op_type}")
        return True, {'note': f'Default handler processed {op_type}'}, None

    def _group_by_operation(self, entries: List[OfflineQueueItem]) -> Dict[str, int]:
        """Group queue entries by operation type for stats."""
        groups = {}
        for e in entries:
            op = e.operation_type or 'unknown'
            groups[op] = groups.get(op, 0) + 1
        return groups