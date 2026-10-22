import sys
import subprocess
import os

def log(msg):
    with open("_install_log.txt", "a") as f:
        f.write(msg + "\n")
    print(msg)

def check_playwright():
    try:
        import playwright
        log(f"Playwright version: {playwright.__version__}")
        return True
    except ImportError:
        log("Playwright not found.")
        return False

def install_playwright():
    log("Attempting to install playwright...")
    try:
        pip_path = os.path.join(sys.prefix, "Scripts", "pip.exe")
        subprocess.check_call([pip_path, "install", "playwright==1.49.1"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        log("Installation successful.")
        return True
    except Exception as e:
        log(f"Installation failed: {e}")
        return False

if __name__ == "__main__":
    if os.path.exists("_install_log.txt"):
        os.remove("_install_log.txt")
    if not check_playwright():
        install_playwright()
        check_playwright()
    else:
        log("Playwright is already installed.")
