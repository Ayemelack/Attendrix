"""Infrastructure & Networking Intelligence.

Intelligent attendance edge node management, mesh synchronization health,
autonomous failover, self-healing sync, distributed load balancing.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from statistics import mean

from .registry import registry, InnovationEvent

logger = logging.getLogger(__name__)


class InfrastructureNet:
    """Network and infrastructure intelligence for distributed attendance.

    Features:
    - Edge node health monitoring
    - Mesh synchronization health scoring
    - Autonomous failover attendance nodes
    - Self-healing synchronization architecture
    - Distributed load balancing
    - Campus-wide intelligent sync optimization
    """

    def __init__(self):
        self._firebase = None
        self._repos = None
        self._node_health: Dict[str, Dict] = {}
        self._sync_history: List[Dict] = []
        self._config = {
            "health_check_interval_seconds": 30,
            "failover_threshold_missed_pings": 3,
            "sync_lag_warning_seconds": 60,
            "sync_lag_critical_seconds": 300,
            "load_balance_max_sessions_per_node": 50,
            "self_heal_retry_delay_seconds": 10,
        }

    def initialize(self, firebase_service=None, repositories: dict = None) -> None:
        self._firebase = firebase_service
        self._repos = repositories or {}
        registry.subscribe(InnovationEvent.SYNC_COMPLETED, self._on_sync)
        logger.info("InfrastructureNet initialized")

    def _on_sync(self, data: dict) -> None:
        """Track sync events for health analysis."""
        self._sync_history.append({
            "timestamp": datetime.utcnow(),
            "node_id": data.get("node_id", "unknown"),
            "status": data.get("status", "unknown"),
            "duration_ms": data.get("duration_ms", 0),
            "records_synced": data.get("records_count", 0),
        })
        if len(self._sync_history) > 1000:
            self._sync_history = self._sync_history[-500:]

    # ── Edge Node Management ──

    def register_node(self, node_id: str, node_type: str,
                      location: str, capabilities: List[str]) -> Dict:
        """Register an attendance edge node."""
        self._node_health[node_id] = {
            "node_id": node_id,
            "type": node_type,
            "location": location,
            "capabilities": capabilities,
            "status": "active",
            "registered_at": datetime.utcnow().isoformat(),
            "last_heartbeat": datetime.utcnow().isoformat(),
            "missed_pings": 0,
            "total_syncs": 0,
            "failed_syncs": 0,
            "avg_sync_duration_ms": 0.0,
            "active_sessions": 0,
            "load_score": 0.0,
        }
        logger.info(f"Edge node registered: {node_id} ({node_type}) at {location}")
        return self._node_health[node_id]

    def node_heartbeat(self, node_id: str, metrics: Dict = None) -> Dict:
        """Process edge node heartbeat."""
        node = self._node_health.get(node_id)
        if not node:
            return {"error": "Node not registered"}

        node["last_heartbeat"] = datetime.utcnow().isoformat()
        node["missed_pings"] = 0
        node["status"] = "active"

        if metrics:
            node["active_sessions"] = metrics.get("active_sessions", node["active_sessions"])
            node["load_score"] = metrics.get("load_score", node["load_score"])

        return {"node_id": node_id, "status": "ok"}

    def detect_failed_nodes(self) -> List[Dict]:
        """Detect nodes that have missed heartbeats."""
        failed = []
        now = datetime.utcnow()

        for node_id, node in self._node_health.items():
            if node["status"] != "active":
                continue
            last_hb = datetime.fromisoformat(node["last_heartbeat"])
            elapsed = (now - last_hb).total_seconds()

            if elapsed > self._config["health_check_interval_seconds"] * \
                         self._config["failover_threshold_missed_pings"]:
                node["missed_pings"] += 1
                if node["missed_pings"] >= self._config["failover_threshold_missed_pings"]:
                    node["status"] = "failed"
                    failed.append({
                        "node_id": node_id,
                        "location": node["location"],
                        "type": node["type"],
                        "last_heartbeat": node["last_heartbeat"],
                        "missed_pings": node["missed_pings"],
                    })
                    logger.warning(f"Edge node failed: {node_id}")
        return failed

    # ── Mesh Synchronization Health ──

    def mesh_sync_health(self, node_ids: List[str] = None) -> Dict[str, Any]:
        """Evaluate mesh synchronization health across nodes."""
        if not self._sync_history:
            return {"status": "no_sync_data"}

        relevant = self._sync_history
        if node_ids:
            relevant = [s for s in relevant if s["node_id"] in node_ids]

        if not relevant:
            return {"status": "no_data_for_nodes"}

        by_node = defaultdict(list)
        for entry in relevant:
            by_node[entry["node_id"]].append(entry)

        node_health = {}
        for node_id, entries in by_node.items():
            durations = [e["duration_ms"] for e in entries]
            failed = sum(1 for e in entries if e["status"] == "failed")
            avg_duration = mean(durations) if durations else 0
            node_health[node_id] = {
                "total_syncs": len(entries),
                "failed_syncs": failed,
                "success_rate": round(
                    (len(entries) - failed) / len(entries), 4
                ) if entries else 0,
                "avg_duration_ms": round(avg_duration, 2),
                "status": "healthy" if failed / len(entries) < 0.1
                else "degraded" if failed / len(entries) < 0.3
                else "unhealthy",
            }

        overall_success = mean(
            n["success_rate"] for n in node_health.values()
        ) if node_health else 0

        return {
            "mesh_status": "healthy" if overall_success > 0.95
            else "degraded" if overall_success > 0.8
            else "critical",
            "nodes_assessed": len(node_health),
            "node_details": node_health,
            "overall_success_rate": round(overall_success, 4),
            "total_syncs_assessed": len(relevant),
            "assessment_time": datetime.utcnow().isoformat()
        }

    # ── Autonomous Failover ──

    def trigger_failover(self, failed_node_id: str,
                          available_nodes: List[str]) -> Dict[str, Any]:
        """Trigger autonomous failover to backup nodes."""
        failed_node = self._node_health.get(failed_node_id)
        if not failed_node:
            return {"error": "Node not found"}

        backup_nodes = [n for n in available_nodes if n != failed_node_id]
        if not backup_nodes:
            return {
                "failover": "impossible",
                "reason": "No backup nodes available",
                "failed_node": failed_node_id
            }

        elected = backup_nodes[0]
        self._node_health[failed_node_id]["status"] = "failover"
        logger.info(
            f"Failover: {failed_node_id} -> {elected}"
        )

        return {
            "failover": "initiated",
            "failed_node": failed_node_id,
            "elected_node": elected,
            "available_backups": len(backup_nodes),
            "timestamp": datetime.utcnow().isoformat()
        }

    # ── Self-Healing ──

    def attempt_self_heal(self, node_id: str) -> Dict[str, Any]:
        """Attempt to self-heal a degraded node."""
        node = self._node_health.get(node_id)
        if not node:
            return {"error": "Node not found"}

        current_status = node["status"]
        if current_status == "active":
            return {"node_id": node_id, "action": "none_needed"}

        node["status"] = "recovering"
        node["recovery_attempts"] = node.get("recovery_attempts", 0) + 1

        recovery_actions = []
        if node.get("failed_syncs", 0) > 5:
            node["failed_syncs"] = 0
            recovery_actions.append("sync_reset")
        if node.get("load_score", 0) > 0.9:
            node["load_score"] = 0.7
            recovery_actions.append("load_rebalance")

        node["status"] = "active" if recovery_actions else "degraded"
        node["last_heartbeat"] = datetime.utcnow().isoformat()

        return {
            "node_id": node_id,
            "previous_status": current_status,
            "new_status": node["status"],
            "recovery_actions": recovery_actions,
            "recovery_attempt": node["recovery_attempts"],
            "timestamp": datetime.utcnow().isoformat()
        }

    # ── Distributed Load Balancing ──

    def balance_load(self) -> Dict[str, Any]:
        """Calculate optimal load distribution across nodes."""
        active_nodes = [
            n for n in self._node_health.values()
            if n["status"] == "active"
        ]
        if not active_nodes:
            return {"status": "no_active_nodes"}

        total_sessions = sum(n["active_sessions"] for n in active_nodes)
        node_count = len(active_nodes)
        target_per_node = total_sessions / node_count if node_count > 0 else 0

        overloaded = [
            n for n in active_nodes
            if n["active_sessions"] > self._config["load_balance_max_sessions_per_node"]
        ]
        underloaded = [
            n for n in active_nodes
            if n["active_sessions"] < target_per_node * 0.5
        ]

        return {
            "load_balancing": "required" if overloaded else "balanced",
            "total_sessions": total_sessions,
            "active_nodes": node_count,
            "target_per_node": round(target_per_node, 1),
            "overloaded_nodes": [
                {"node_id": n["node_id"], "sessions": n["active_sessions"]}
                for n in overloaded
            ],
            "underloaded_nodes": [
                {"node_id": n["node_id"], "sessions": n["active_sessions"]}
                for n in underloaded
            ],
            "recommendation": (
                f"Redistribute {sum(n['active_sessions'] for n in overloaded) - int(target_per_node * len(overloaded))} "
                f"sessions to underloaded nodes"
            ) if overloaded else "All nodes optimally balanced"
        }

    # ── Sync Optimization ──

    def optimize_sync(self, node_id: str,
                      recent_syncs: List[Dict] = None) -> Dict[str, Any]:
        """Recommend sync optimization parameters."""
        syncs = recent_syncs or self._sync_history
        node_syncs = [s for s in syncs if s.get("node_id") == node_id]

        if len(node_syncs) < 3:
            return {"node_id": node_id, "optimization": "insufficient_data"}

        durations = [s["duration_ms"] for s in node_syncs]
        records_counts = [s["records_synced"] for s in node_syncs]

        avg_duration = mean(durations)
        avg_records = mean(records_counts) if records_counts else 0
        throughput = avg_records / (avg_duration / 1000) if avg_duration > 0 else 0

        return {
            "node_id": node_id,
            "optimization": "recommended",
            "current_metrics": {
                "avg_sync_duration_ms": round(avg_duration, 2),
                "avg_records_per_sync": round(avg_records, 1),
                "throughput_records_per_sec": round(throughput, 2),
            },
            "recommendations": self._sync_recommendations(
                avg_duration, throughput, avg_records
            ),
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def _sync_recommendations(duration_ms: float, throughput: float,
                               records: float) -> List[str]:
        recs = []
        if duration_ms > 5000:
            recs.append("Consider batch size reduction for faster sync")
        if throughput < 10:
            recs.append("Compression recommended for sync payload")
        if records > 1000:
            recs.append("Implement incremental sync instead of full sync")
        if not recs:
            recs.append("Current sync parameters are optimal")
        return recs

    def get_network_status(self) -> Dict[str, Any]:
        """Get overall network infrastructure status."""
        failed = self.detect_failed_nodes()
        mesh_health = self.mesh_sync_health()
        load = self.balance_load()

        return {
            "total_nodes": len(self._node_health),
            "active_nodes": sum(
                1 for n in self._node_health.values()
                if n["status"] == "active"
            ),
            "failed_nodes": len(failed),
            "mesh_health": mesh_health,
            "load_balance": load,
            "sync_history_size": len(self._sync_history),
            "timestamp": datetime.utcnow().isoformat()
        }

    def cleanup(self) -> None:
        self._node_health.clear()
        self._sync_history.clear()
        logger.info("InfrastructureNet cleaned up")
