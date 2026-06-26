# Firestore Rules Audit — Phase 2I

**File:** `firestore.rules` (616 lines, `rules_version = '2'`)

## Summary

The Firestore security rules are **well-structured** with deny-by-default, role-based access control, and institution-scoped data isolation. No critical vulnerabilities were found.

---

## Strengths

1. **Deny-by-default catch-all** (line 612-614): `allow read, write: if false;` — blocks all unmatched paths
2. **Consistent role enforcement**: `isSuperAdmin()`, `institutionAdmin()`, `lecturer()`, `student()` used throughout
3. **Institution data isolation**: `sameInstitutionRead()` / `sameInstitutionWrite()` patterns ensure multi-tenant separation
4. **Own-document access**: `isOwnDocument()` / `isOwnRequest()` checks for user-facing collections
5. **Granularity by operation**: Most collections split `read`, `create`, `update`, `delete` separately

---

## Findings

| # | Finding | Collection | Lines | Severity | Recommendation |
|---|---|---|---|---|---|
| 1 | Public unauthenticated create | `demo_bookings` | 499 | ⚠️ Low | Intentional (public demo); add Firebase rate limiting or App Check if abused |
| 2 | Broad `read, write` (not split) | `offline_sync_queue`, `offline_queue` | 407-415 | ⚠️ Low | Split into separate allow rules per operation if auditing needed |
| 3 | Broad `read, write` legacy collections | `attendance`, `sessions`, `enrollments`, `activity_log`, `payments` | 583-606 | ⚠️ Low | Legacy — migrate to per-operation rules as part of data migration |
| 4 | No subcollection recursion rules | All | N/A | ⚠️ Low | Subcollections inherit parent; add explicit rules for known subcollections |
| 5 | `network_nodes` allows create, update by authenticated | `network_nodes` | 302 | ✅ Info | Reasonable — institution-admin restricted |
| 6 | `ups_status`, `isp_status`, `generator_status` allow create by authenticated | Infrastructure collections | 367-382 | ✅ Info | Reasonable for status reporting |

---

## Recommendation Priority

1. **(Medium)** Add Firebase App Check enforcement to prevent abuse from untrusted clients
2. **(Low)** Split broad `read, write` rules on legacy collections into per-operation rules
3. **(Low)** Add explicit subcollection rules for any Firestore subcollections used by the app
4. **(Informational)** No action needed; rules are production-quality

---

## Verdict

**PASS** — No critical or high-severity findings. The rules enforce proper multi-tenant isolation, role-based access, and include a deny-by-default catch-all. The single public create on `demo_bookings` is intentional for the demo signup flow.
