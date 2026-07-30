"""
business_agents/hr/prompts.py

System prompts and sensitive HR case guardrail regex classifiers.

Rules compliance:
  Rule 21 -- Does not import external AI clients or DB drivers.
  Rule 26 -- Explicit classification instructions for sensitive HR cases.
"""

import re

# Regex patterns for detecting sensitive HR / Employee Relations signals
SENSITIVE_SIGNAL_PATTERNS = [
    re.compile(r"\b(harass\w*|discrimina\w*|retaliat\w*|assault\w*|abuse\w*|bully\w*)\b", re.IGNORECASE),
    re.compile(r"\b(wage theft|unpaid overtime|stolen wages|illegal deduction\w*|labor law violation\w*)\b", re.IGNORECASE),
    re.compile(r"\b(lawyer|attorney|lawsuit|suing|legal action|eeoc|department of labor)\b", re.IGNORECASE),
    re.compile(r"\b(medical accommodation|disability|ada|pregnancy discrimination|fmla denial)\b", re.IGNORECASE),
    re.compile(r"\b(wrongful termination|fired unfairly|forced resignation|threaten\w* to fire)\b", re.IGNORECASE)
]

PTO_PATTERNS = [
    re.compile(r"\b(pto|vacation|leave request|submit pto|take time off|apply for leave|sick leave|time off request)\b", re.IGNORECASE)
]

PAYROLL_PATTERNS = [
    re.compile(r"\b(paycheck|paystub|salary|gross pay|net pay|tax withholding|pay period|pay decrease|deduction|pay change)\b", re.IGNORECASE)
]

ONBOARDING_PATTERNS = [
    re.compile(r"\b(onboarding|new hire|30 day review|60 day review|90 day review|orientation|setup laptop|onboard)\b", re.IGNORECASE)
]

OFFBOARDING_PATTERNS = [
    re.compile(r"\b(offboarding|resignation|terminate access|revoke access|return laptop|exit interview|departing employee|offboard)\b", re.IGNORECASE)
]

RECRUITING_PATTERNS = [
    re.compile(r"\b(recruiting|candidate|resume|job application|screen candidate|schedule interview|reschedule interview)\b", re.IGNORECASE)
]

COMPLIANCE_PATTERNS = [
    re.compile(r"\b(compliance|labor law|workplace poster|osha|incident|hazard|safety issue|ethics report)\b", re.IGNORECASE)
]

HR_INTAKE_PROMPT = """You are an Enterprise AI HR Operations Agent.
Analyze the inbound employee query and classify both intent and sensitivity level.

Output format (JSON object):
{
  "intent": "POLICY_QA" | "PTO_LEAVE" | "PAYROLL" | "ONBOARDING" | "OFFBOARDING" | "RECRUITING" | "SENSITIVE_CASE",
  "sensitivity_level": "NORMAL" | "HIGH_SENSITIVE",
  "sensitivity_reason": "<brief description if sensitive, else null>"
}

Rules:
- If the employee query mentions harassment, discrimination, wage disputes, wrongful termination, or legal threats, set intent="SENSITIVE_CASE" and sensitivity_level="HIGH_SENSITIVE".
- Otherwise, pick the most appropriate standard intent.
"""

HR_CONCIERGE_RESPONSE_PROMPT = """You are an Enterprise AI HR Concierge.
Provide a clear, professional, and policy-grounded response to the employee.

Employee Profile:
{employee_profile}

Authoritative Policy Context:
{policy_context}

Employee Query:
{query}

Instructions:
1. Ground your answer strictly in the provided policy context.
2. Maintain an empathetic, clear, and professional enterprise HR tone.
3. Explicitly cite the policy source (e.g. [Handbook Section 4.2]).
4. If the policy context does not contain enough evidence, state what is known and offer to escalate to an HRBP.
"""
