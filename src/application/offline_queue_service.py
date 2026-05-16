"""Offline Queue Service — Network resilience engine for Attendrix.

This service enables the system to operate during internet/power disruptions
by queueing operations locally and synchronizing when connectivity is restored.

Networking concepts demonstrated:
- Store-and-forward message queuing
- Exponential backoff retry
- Last-writer-wins conflict resolution
- Queue health monitoring
- Bandwidth-aware sync prioritization
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import uuid

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
    """Queue-based offline sync engine with retry and conflict resolution.

    The service queues operations when the network is unavailable and
    processes them in FIFO order when connectivity is restored. Each
    operation includes metadata for conflict detection and retry tracking.
    """

    def __init__(self, firebase_service):
        self.fb = firebase_service
        self._processing = False
        self._max_retries = 5
        self._base_delay_seconds = 2
        self._batch_size = 25

    # ── QUEUE OPERATIONS ──

    def enqueue(self, institution_id: str, operation_type: str,
                payload: Dict[str, Any], node_name: str = "web",
                priority: int = 0) -> str:
        """Add an operation to the offline queue.

        Args:
            institution_id: The institution this operation belongs to.
            operation_type: Type of operation (from OperationType enum).
            payload: The operation data to sync.
            node_name: The node that created this operation.
            priority: 0=normal, 1=high, -1=low.

        Returns:
            The queue entry ID.
        """
        entry = {
            'institution_id': institution_id,
            'operation_type': operation_type,
            'payload': json.dumps(payload, default=str),
            'status': SyncStatus.PENDING.value,
            'node_name': node_name,
            'priority': priority,
            'retry_count': 0,
            'max_retries': self._max_retries,
            'next_retry_at': None,
            'error_message': None,
            'conflict_info': None,
            'checksum': self._compute_checksum(payload),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'synced_at': None,
        }
        entry_id = self.fb.create_document('offline_queue', entry)
        logger.info(
            f"OFFLINE QUEUE: Enqueued {operation_type} for {institution_id} "
            f"(id={entry_id}, node={node_name})"
        )
        return entry_id

    def dequeue(self, entry_id: str) -> bool:
        """Remove a completed entry from the queue."""
        return self.fb.delete_document('offline_queue', entry_id)

    def get_pending(self, institution_id: str = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Get all pending operations, optionally filtered by institution."""
        filters = [{'field': 'status', 'value': SyncStatus.PENDING.value}]
        if institution_id:
            filters.append({'field': 'institution_id', 'value': institution_id})
        return self.fb.query_documents(
            'offline_queue',
            filters=filters,
            order_by='created_at',
            limit=limit
        )

    def get_failed(self, institution_id: str = None,
                   limit: int = 50) -> List[Dict[str, Any]]:
        """Get all failed operations for retry inspection."""
        filters = [{'field': 'status', 'value': SyncStatus.FAILED.value}]
        if institution_id:
            filters.append({'field': 'institution_id', 'value': institution_id})
        return self.fb.query_documents(
            'offline_queue',
            filters=filters,
            order_by='-updated_at',
            limit=limit
        )

    def get_queue_stats(self, institution_id: str = None) -> Dict[str, Any]:
        """Get queue statistics for dashboard display."""
        all_entries = self.fb.query_documents('offline_queue')
        if institution_id:
            all_entries = [e for e in all_entries
                          if e.get('institution_id') == institution_id]

        total = len(all_entries)
        by_status = {}
        for e in all_entries:
            s = e.get('status', 'pending')
            by_status[s] = by_status.get(s, 0) + 1

        pending = by_status.get('pending', 0)
        failed = by_status.get('failed', 0)
        synced = by_status.get('synced', 0)
        in_progress = by_status.get('in_progress', 0)
        conflicts = by_status.get('conflict', 0)

        retry_count = sum(e.get('retry_count', 0) for e in all_entries
                         if e.get('status') in ('pending', 'failed'))

        oldest_pending = None
        if pending:
            pendings = [e for e in all_entries if e.get('status') == 'pending']
            oldest_pending = pendings[0].get('created_at') if pendings else None

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
        """Process pending operations in the queue.

        This is the core sync engine. It processes operations in FIFO order,
        with retry and exponential backoff for failed operations.

        Args:
            institution_id: Optional filter for a specific institution.
            handler_map: Maps operation_type strings to handler functions.
                         Each handler receives (payload: dict) and returns
                         (success: bool, result: dict, error: str).

        Returns:
            Summary of the sync operation.
        """
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
                entry_id = entry.get('id')
                op_type = entry.get('operation_type', 'unknown')
                retry_count = entry.get('retry_count', 0)
                max_retries = entry.get('max_retries', self._max_retries)

                # Check if we should retry based on backoff
                next_retry = entry.get('next_retry_at')
                if next_retry and datetime.utcnow() < datetime.fromisoformat(next_retry):
                    continue

                # Mark as in progress
                self.fb.update_document('offline_queue', entry_id, {
                    'status': SyncStatus.IN_PROGRESS.value,
                    'updated_at': datetime.utcnow().isoformat(),
                })

                try:
                    payload = json.loads(entry.get('payload', '{}'))

                    if handler_map and op_type in handler_map:
                        handler = handler_map[op_type]
                        success, result, error = handler(payload)
                    else:
                        success, result, error = self._default_handler(op_type, payload)

                    if success:
                        self.fb.update_document('offline_queue', entry_id, {
                            'status': SyncStatus.SYNCED.value,
                            'synced_at': datetime.utcnow().isoformat(),
                            'updated_at': datetime.utcnow().isoformat(),
                        })
                        succeeded += 1
                    else:
                        raise Exception(error or 'Handler returned failure')

                except Exception as e:
                    error_msg = str(e)
                    new_retry_count = retry_count + 1

                    if new_retry_count >= max_retries:
                        self.fb.update_document('offline_queue', entry_id, {
                            'status': SyncStatus.FAILED.value,
                            'retry_count': new_retry_count,
                            'error_message': error_msg,
                            'updated_at': datetime.utcnow().isoformat(),
                        })
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
                        next_retry = (datetime.utcnow() + timedelta(seconds=delay)).isoformat()
                        self.fb.update_document('offline_queue', entry_id, {
                            'status': SyncStatus.PENDING.value,
                            'retry_count': new_retry_count,
                            'error_message': error_msg,
                            'next_retry_at': next_retry,
                            'updated_at': datetime.utcnow().isoformat(),
                        })
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
            self.fb.update_document('offline_queue', entry_id, {
                'status': SyncStatus.PENDING.value,
                'retry_count': 0,
                'error_message': None,
                'next_retry_at': None,
                'updated_at': datetime.utcnow().isoformat(),
            })
            return 1
        else:
            filters = [{'field': 'status', 'value': SyncStatus.FAILED.value}]
            if institution_id:
                filters.append({'field': 'institution_id', 'value': institution_id})
            failed = self.fb.query_documents('offline_queue', filters=filters)
            count = 0
            for entry in failed:
                self.fb.update_document('offline_queue', entry.get('id'), {
                    'status': SyncStatus.PENDING.value,
                    'retry_count': 0,
                    'error_message': None,
                    'next_retry_at': None,
                    'updated_at': datetime.utcnow().isoformat(),
                })
                count += 1
            logger.info(f"OFFLINE QUEUE: Reset {count} failed entries to pending")
            return count

    def clear_synced(self, institution_id: str = None,
                     older_than_hours: int = 24) -> int:
        """Remove synced entries older than the threshold."""
        all_entries = self.fb.query_documents('offline_queue')
        cutoff = (datetime.utcnow() - timedelta(hours=older_than_hours)).isoformat()
        removed = 0
        for entry in all_entries:
            if entry.get('status') != SyncStatus.SYNCED.value:
                continue
            if institution_id and entry.get('institution_id') != institution_id:
                continue
            synced_at = entry.get('synced_at', entry.get('updated_at', ''))
            if synced_at and synced_at < cutoff:
                self.fb.delete_document('offline_queue', entry.get('id'))
                removed += 1
        if removed:
            logger.info(f"OFFLINE QUEUE: Cleared {removed} old synced entries")
        return removed

    # ── CONFLICT RESOLUTION ──

    def resolve_conflict(self, entry_id: str, strategy: str = 'lww',
                         resolution: Dict[str, Any] = None) -> bool:
        """Resolve a conflict for a specific queue entry.

        Strategies:
            lww: Last-writer-wins (default). The most recent operation wins.
            manual: Manual resolution provided.
            discard_local: Keep the server state, discard local change.
            force_local: Overwrite server state with local change.
        """
        entry = self.fb.get_document('offline_queue', entry_id)
        if not entry:
            return False

        if strategy == 'lww':
            self.fb.update_document('offline_queue', entry_id, {
                'status': SyncStatus.PENDING.value,
                'conflict_info': None,
                'updated_at': datetime.utcnow().isoformat(),
            })
            return True
        elif strategy == 'discard_local':
            self.fb.update_document('offline_queue', entry_id, {
                'status': SyncStatus.SYNCED.value,
                'conflict_info': 'discarded_local',
                'synced_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat(),
            })
            return True
        elif strategy == 'force_local':
            self.fb.update_document('offline_queue', entry_id, {
                'status': SyncStatus.PENDING.value,
                'priority': 1,
                'conflict_info': None,
                'updated_at': datetime.utcnow().isoformat(),
            })
            return True
        elif strategy == 'manual' and resolution:
            self.fb.update_document('offline_queue', entry_id, {
                'status': SyncStatus.PENDING.value,
                'payload': json.dumps(resolution, default=str),
                'conflict_info': 'manual_resolution',
                'updated_at': datetime.utcnow().isoformat(),
            })
            return True

        return False

    # ── SYNC HEALTH & BANDWIDTH AWARENESS ──

    def estimate_sync_duration(self, institution_id: str = None) -> Dict[str, Any]:
        """Estimate how long a full sync would take based on queue size."""
        pending = self.get_pending(institution_id)
        total_pending = len(pending)
        estimated_seconds = total_pending * 0.5  # ~500ms per operation
        estimated_data_kb = sum(
            len(entry.get('payload', '{}')) for entry in pending
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
        all_entries = self.fb.query_documents('offline_queue')
        if institution_id:
            all_entries = [e for e in all_entries
                          if e.get('institution_id') == institution_id]

        nodes = {}
        for entry in all_entries:
            node = entry.get('node_name', 'unknown')
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
            status = entry.get('status', 'pending')
            if status in nodes[node]:
                nodes[node][status] += 1
            synced_at = entry.get('synced_at')
            if synced_at and (not nodes[node]['last_sync'] or synced_at > nodes[node]['last_sync']):
                nodes[node]['last_sync'] = synced_at

        return sorted(nodes.values(), key=lambda n: n['total'], reverse=True)

    # ── INTERNAL HELPERS ──

    def _compute_backoff(self, retry_count: int) -> int:
        """Exponential backoff with jitter.

        Base: 2s, then 4s, 8s, 16s, 32s (capped at 60s).
        """
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
        """Default handler when no custom handler is provided.

        For the mock/dev environment, simply log and succeed.
        In production, this would dispatch to the appropriate service.
        """
        logger.info(f"OFFLINE QUEUE: Default handling {op_type}")
        return True, {'note': f'Default handler processed {op_type}'}, None

    def _group_by_operation(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group queue entries by operation type for stats."""
        groups = {}
        for e in entries:
            op = e.get('operation_type', 'unknown')
            groups[op] = groups.get(op, 0) + 1
        return groups
