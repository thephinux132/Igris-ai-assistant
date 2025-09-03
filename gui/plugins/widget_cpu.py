def run():
    import psutil
    cpu_usage = psutil.cpu_percent(interval=1)
    return f"CPU Usage: {cpu_usage}%"