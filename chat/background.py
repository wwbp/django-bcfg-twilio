import threading


def run_in_background(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    # Optional: allow program exit even if thread is running.
    thread.daemon = True
    thread.start()
