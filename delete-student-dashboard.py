#!/usr/bin/env python3
"""
Phase 1: Complete Student Dashboard Deletion
"""

import os
import sys

def delete_student_dashboard():
    print("🚨 PHASE 1: COMPLETE STUDENT DASHBOARD DELETION")
    print("=" * 60)
    
    files_to_delete = [
        "src/presentation/templates/dashboard.html",
        "src/presentation/templates/student-attendance.html",
        "src/presentation/templates/student-assignments.html", 
        "src/presentation/templates/student-schedule.html",
        "src/presentation/templates/student-grades.html"
    ]
    
    deleted_files = []
    failed_deletions = []
    
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_files.append(file_path)
                print(f"   ✅ DELETED: {file_path}")
            else:
                print(f"   ⚠️  NOT FOUND: {file_path}")
        except Exception as e:
            print(f"   ❌ FAILED: {file_path} - {str(e)}")
            failed_deletions.append(file_path)
    
    print(f"\n📊 DELETION SUMMARY:")
    print(f"   Files deleted: {len(deleted_files)}")
    print(f"   Failed deletions: {len(failed_deletions)}")
    
    if len(failed_deletions) == 0:
        print("   ✅ ALL STUDENT DASHBOARD FILES DELETED")
        return True
    else:
        print("   ❌ SOME FILES FAILED TO DELETE")
        return False

if __name__ == "__main__":
    success = delete_student_dashboard()
    sys.exit(0 if success else 1)
