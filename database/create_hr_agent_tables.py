"""
database/create_hr_agent_tables.py

Migration script to create dedicated database tables for the Enterprise AI HR Agent:
  1. hr_employees
  2. hr_leave_requests
  3. hr_onboarding_checklists
  4. hr_offboarding_tasks
  5. hr_candidates
  6. hr_interviews
  7. hr_compliance_records
  8. hr_incidents

Existing tables (prospects, opportunities, support_tickets, decision_cards) remain 100% untouched.
Rule 24 compliance: Every table includes mandatory tenant_id multi-tenant column.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load root .env
load_dotenv(override=True)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from platform_core.db import get_connection


def create_hr_tables():
    conn = None
    retries = 3
    for attempt in range(retries):
        try:
            print(f"Connecting to database (attempt {attempt + 1}/{retries})...")
            conn = get_connection()
            cursor = conn.cursor()
            
            print("Creating dedicated database tables for HR Agent...")
            
            # Ensure tenants table exists first
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Insert default tenant if missing
            cursor.execute("""
                INSERT INTO tenants (tenant_id, name)
                VALUES ('tenant_1', 'Default Enterprise Tenant')
                ON CONFLICT (tenant_id) DO NOTHING;
            """)
            
            # 1. hr_employees table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_employees (
                    employee_id VARCHAR(100) PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    department VARCHAR(100),
                    role VARCHAR(100),
                    location VARCHAR(100),
                    jurisdiction VARCHAR(100) DEFAULT 'US',
                    status VARCHAR(50) DEFAULT 'ACTIVE',
                    pto_balance_days NUMERIC(5, 2) DEFAULT 15.00,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. hr_leave_requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_leave_requests (
                    request_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    employee_id VARCHAR(100) NOT NULL REFERENCES hr_employees(employee_id) ON DELETE CASCADE,
                    leave_type VARCHAR(50) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    total_days NUMERIC(5, 2) NOT NULL,
                    status VARCHAR(50) DEFAULT 'PENDING',
                    approved_by VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 3. hr_onboarding_checklists table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_onboarding_checklists (
                    checklist_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    employee_id VARCHAR(100) NOT NULL REFERENCES hr_employees(employee_id) ON DELETE CASCADE,
                    milestone VARCHAR(50) NOT NULL,
                    items JSONB NOT NULL,
                    status VARCHAR(50) DEFAULT 'IN_PROGRESS',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 4. hr_offboarding_tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_offboarding_tasks (
                    task_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    employee_id VARCHAR(100) NOT NULL REFERENCES hr_employees(employee_id) ON DELETE CASCADE,
                    task_name VARCHAR(255) NOT NULL,
                    owner VARCHAR(100) NOT NULL,
                    status VARCHAR(50) DEFAULT 'PENDING',
                    asset_returned BOOLEAN DEFAULT FALSE,
                    access_revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 5. hr_candidates table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_candidates (
                    candidate_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    candidate_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    job_title VARCHAR(150) NOT NULL,
                    skills TEXT[],
                    resume_parsed_json JSONB,
                    match_score NUMERIC(5, 2),
                    status VARCHAR(50) DEFAULT 'NEW',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 6. hr_interviews table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_interviews (
                    interview_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    candidate_id INT REFERENCES hr_candidates(candidate_id) ON DELETE CASCADE,
                    interviewer_ids TEXT[],
                    scheduled_slot TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(50) DEFAULT 'SCHEDULED',
                    meeting_link TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 7. hr_compliance_records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_compliance_records (
                    record_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    employee_id VARCHAR(100) NOT NULL REFERENCES hr_employees(employee_id) ON DELETE CASCADE,
                    requirement_name VARCHAR(255) NOT NULL,
                    due_date DATE NOT NULL,
                    status VARCHAR(50) DEFAULT 'PENDING',
                    verified_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 8. hr_incidents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hr_incidents (
                    incident_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    incident_type VARCHAR(100) NOT NULL,
                    affected_department VARCHAR(100),
                    description TEXT NOT NULL,
                    status VARCHAR(50) DEFAULT 'OPEN',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            conn.commit()
            print("Successfully created all dedicated HR Agent database tables!")
            return True
        except Exception as e:
            print(f"Error creating HR tables (attempt {attempt + 1}): {e}")
            if conn:
                conn.rollback()
            time.sleep(2)
    
    print("Failed to create HR tables after retries.")
    return False


if __name__ == "__main__":
    success = create_hr_tables()
    if not success:
        sys.exit(1)
