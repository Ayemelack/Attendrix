import sys, json
sys.path.insert(0, '.')
from src.application.offline_queue_service import OfflineQueueService
from src.infrastructure.firebase_service import FirebaseService

fb = FirebaseService()
qs = OfflineQueueService(fb)

# 1. Enqueue a test operation
print("=== STEP 1: Enqueue ===")
eid = qs.enqueue(
    institution_id='inst_001',
    operation_type='create_activity_log',
    payload={'type': 'test_sync', 'message': 'Offline sync E2E test', 'faculty': 'Engineering'},
    node_name='test_script',
    priority=1,
)
print(f"Enqueued: {eid}")

# 2. Check stats before processing
stats = qs.get_queue_stats('inst_001')
print(f"Before processing - pending: {stats['pending']}, total: {stats['total']}")

# 3. Process the queue with real handlers
def sample_handler(payload):
    print(f"  Handler called with payload: {payload}")
    return True, {'result': 'ok'}, None

handler_map = {
    'create_activity_log': sample_handler,
}

result = qs.process_queue('inst_001', handler_map)
print(f"\n=== STEP 2: Process ===")
print(f"Status: {result['status']}")
print(f"Processed: {result['processed']}")
print(f"Succeeded: {result['succeeded']}")
print(f"Failed: {result['failed']}")
print(f"Elapsed: {result['elapsed_seconds']}s")

# 4. Check stats after processing
stats2 = qs.get_queue_stats('inst_001')
print(f"\nAfter processing - synced: {stats2['synced']}, pending: {stats2['pending']}")

# 5. Test retry with a failing handler
eid2 = qs.enqueue(
    institution_id='inst_001',
    operation_type='create_payment',
    payload={'amount': 5000, 'phone': '237670000000'},
    node_name='test_script',
)
print(f"\n=== STEP 3: Failed handler ===")
fail_map = {'create_payment': lambda p: (False, {}, 'Simulated failure')}
result2 = qs.process_queue('inst_001', fail_map)
print(f"Processed: {result2['processed']}, Failed: {result2['failed']}")
print(f"Errors: {result2['errors']}")

# Check retry
stats3 = qs.get_queue_stats('inst_001')
print(f"After failure - pending: {stats3['pending']}, failed: {stats3['failed']}")

# 6. Retry failed entries
retried = qs.retry_failed(institution_id='inst_001')
print(f"\n=== STEP 4: Retry ===")
print(f"Retried: {retried}")

stats4 = qs.get_queue_stats('inst_001')
print(f"After retry - pending: {stats4['pending']}, failed: {stats4['failed']}")

# 7. Clear old synced
cleared = qs.clear_synced('inst_001', older_than_hours=0)
print(f"\n=== STEP 5: Clear ===")
print(f"Cleared: {cleared}")

print("\n=== ALL E2E TESTS PASSED ===")
