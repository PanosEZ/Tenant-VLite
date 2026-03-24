import subprocess
import sys
import time

def main():
    print("[TENANT] Booting up the system (ZeroMQ Mode)...")

    # 1. Launch the Observers first
    reader_process = subprocess.Popen([sys.executable, "-u", "scripts/reader.py"])
    executor_process = subprocess.Popen([sys.executable, "-u", "scripts/executor.py"])
    context_process = subprocess.Popen([sys.executable, "-u", "scripts/context.py"])

    # Give the observers a second to boot up and look at the ZMQ port
    time.sleep(1)

    # 2. Launch the Brain (v-aws.py) — now listens on ZMQ instead of terminal
    vaws_process = subprocess.Popen([sys.executable, "-u", "scripts/v-aws.py"])

    # Give v-aws a moment to bind its ZMQ sockets
    time.sleep(1)

    # 3. Launch the API Gateway (serves the WebUI on port 5000)
    api_process = subprocess.Popen([sys.executable, "-u", "scripts/api.py"])

    print("[TENANT] All systems online. API Gateway at http://127.0.0.1:5000")
    print("[TENANT] Press Ctrl+C to shut down.")

    try:
        # Keep tenant alive until interrupted
        api_process.wait()
    except KeyboardInterrupt:
        print("\n[TENANT] Force quitting...")
    finally:
        # Clean up all processes
        print("[TENANT] Shutting down all processes...")
        for proc in [api_process, vaws_process, reader_process, executor_process, context_process]:
            if proc.poll() is None:
                proc.terminate()
        print("[TENANT] System offline.")

if __name__ == "__main__":
    main()