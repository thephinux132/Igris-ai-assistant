"""
Monitors and logs simulated login failures or scan attempts.
"""

import logging
from logging import FileHandler, Formatter
import datetime
import random

LOG_FILE = "failed_events.log"

def setup_logger():
    handler = FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    handler.setLevel(logging.DEBUG)
    formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger = logging.getLogger("EventMonitor")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger

def simulate_event(logger):
    fake_events = [
        ("login_failure", "Failed login attempt for user 'admin'"),
        ("port_scan_attempt", "Multiple SYN packets from 192.168.1.200"),
        ("unusual_connection", "Connection from unknown region IP 47.93.22.18")
    ]
    event = random.choice(fake_events)
    logger.warning(f"{event[0]}: {event[1]}")
    return f"Logged event: {event[0]}"

def run():
    logger = setup_logger()
    results = []
    for _ in range(2):  # simulate 2 events per run
        msg = simulate_event(logger)
        results.append(msg)
    return "\n".join(results)
