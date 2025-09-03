"""Plugin: Disable Remote Desktop"""
from plugin_execution_logger import run as log_plugin_run

def run():
    log_plugin_run("disable_remote_desktop")
    return "Remote Desktop disabled via registry (simulated)."