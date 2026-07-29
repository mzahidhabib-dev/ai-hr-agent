"""
database/create_support_agent_tables.py

Migration script to create dedicated database tables for the Enterprise AI Support Agent:
  1. support_tickets
  2. support_ticket_events
  3. support_decision_cards
  4. support_handoffs

Existing tables (prospects, opportunities, decision_cards, handoffs) remain 100% untouched.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load root .env
load_dotenv(override=True)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from platform_core.db import get_connection


def create_support_tables():
    conn = None
    retries = 3
    for attempt in range(retries):
        try:
            print(f"Connecting to database (attempt {attempt + 1}/{retries})...")
            conn = get_connection()
            cursor = conn.cursor()
            
            print("Creating dedicated database tables for Support Agent...")
            
            # 1. support_tickets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    ticket_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    customer_id VARCHAR(100),
                    external_message_id VARCHAR(255) UNIQUE,
                    inbound_message TEXT NOT NULL,
                    intent VARCHAR(50),
                    severity VARCHAR(50),
                    urgency VARCHAR(50),
                    frustration_score NUMERIC(3, 2),
                    churn_risk BOOLEAN DEFAULT FALSE,
                    status VARCHAR(50) DEFAULT 'NEW',
                    confidence_score NUMERIC(5, 2),
                    response_text TEXT,
                    sla_deadline TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. support_ticket_events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS support_ticket_events (
                    event_id SERIAL PRIMARY KEY,
                    ticket_id INT REFERENCES support_tickets(ticket_id) ON DELETE CASCADE,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    event_type VARCHAR(100) NOT NULL,
                    payload JSONB,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 3. support_decision_cards table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS support_decision_cards (
                    decision_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    ticket_id INT REFERENCES support_tickets(ticket_id) ON DELETE SET NULL,
                    agent_name VARCHAR(100) DEFAULT 'SupportAgent',
                    action VARCHAR(255) NOT NULL,
                    result TEXT,
                    confidence NUMERIC(5, 2),
                    reason TEXT[],
                    sources TEXT[],
                    model VARCHAR(100),
                    cost_usd NUMERIC(10, 4),
                    approval_status VARCHAR(50) DEFAULT 'WAITING_FOR_HUMAN',
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 4. support_handoffs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS support_handoffs (
                    handoff_id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(tenant_id),
                    ticket_id INT REFERENCES support_tickets(ticket_id) ON DELETE SET NULL,
                    customer_id VARCHAR(100),
                    intent VARCHAR(50),
                    urgency VARCHAR(50),
                    conversation_history JSONB,
                    retrieved_evidence JSONB,
                    diagnostic_summary TEXT,
                    handoff_package JSONB,
                    status VARCHAR(50) DEFAULT 'WAITING_FOR_HUMAN',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            conn.commit()
            print("SUCCESS: Dedicated Support Agent tables created successfully!")
            return
            
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {e}")
            if conn:
                conn.rollback()
            if attempt < retries - 1:
                time.sleep(3)
            else:
                raise e
        finally:
            if conn:
                conn.close()


if __name__ == "__main__":
    create_support_tables()
