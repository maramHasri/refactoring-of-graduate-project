import os

from app_factory import create_app

app = create_app()

if __name__ == "__main__":
    # TEMP DIAG — process identity (reloader check)
    print(f"[PID run.py] pid={os.getpid()}", flush=True)
    # flask-sock needs a concurrent WS-capable development server.
    # Werkzeug + threaded=True is the actual runtime for `python run.py`.
    # Disable the reloader so teacher-monitor subscribers stay in the same process
    # (reloader parent/child split caused intermittent non-WS / stale-handler behavior).
    app.run(
        host="0.0.0.0",
        port=5000,
        threaded=True,
        use_reloader=False,
    )
