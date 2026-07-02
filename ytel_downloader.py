import os
import time
import glob
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Load credentials from .env
load_dotenv()

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
YTEL_URL      = "https://app.ytel.com/"
YTEL_EMAIL    = os.getenv("YTEL_EMAIL")
YTEL_PASSWORD = os.getenv("YTEL_PASSWORD")

DOWNLOAD_DIR  = os.path.dirname(os.path.abspath(__file__))
CSV_SAVE_PATH = os.path.join(DOWNLOAD_DIR, "ytel_agent_report.csv")
# ─────────────────────────────────────────────

def download_report(report_url, log_fn=print):
    """
    Logs into Ytel, navigates to the report download URL,
    and saves the CSV to CSV_SAVE_PATH.
    Returns True on success, False on failure.
    """
    log_fn("Starting browser to download Ytel report...")

    # Chrome options — runs headless (no visible window)
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    # Set download directory
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        wait = WebDriverWait(driver, 20)

        # 1. Go to Ytel login page
        log_fn("Navigating to Ytel login...")
        driver.get(YTEL_URL)
        time.sleep(2)

        # 2. Enter email
        try:
            email_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[name='username'], input[placeholder='Email'], input[id='email']")
            ))
        except Exception:
            # Try any visible text input as fallback
            email_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='text']")
            ))
        email_field.clear()
        email_field.send_keys(YTEL_EMAIL)

        # 3. Enter password
        password_field = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[type='password']")
        ))
        password_field.clear()
        password_field.send_keys(YTEL_PASSWORD)

        # 4. Click login button
        try:
            login_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            ))
        except Exception:
            login_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'login') or contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]")
            ))
        login_btn.click()
        log_fn("Logged in, waiting for dashboard...")
        time.sleep(4)

        # 5. Navigate to the report download URL (HubSpot tracking link)
        log_fn(f"Navigating to report URL...")
        driver.get(report_url)
        time.sleep(5)  # Wait for JS redirect to complete

        # If redirected to Ytel login, log in again
        if "login" in driver.current_url.lower() or "signin" in driver.current_url.lower():
            log_fn("Redirected to login page, logging in again...")
            wait.until(EC.presence_of_element_located(
                (By.XPATH, "//input[@type='email' or @name='email']")
            )).send_keys(YTEL_EMAIL)
            driver.find_element(By.XPATH, "//input[@type='password']").send_keys(YTEL_PASSWORD)
            driver.find_element(
                By.XPATH, "//button[@type='submit' or contains(text(),'Login') or contains(text(),'Sign In')]"
            ).click()
            time.sleep(4)

        # If stuck on HubSpot tracking page, try to find the actual download link on page
        current = driver.current_url
        if "hubapi.com" in current or "hubspot" in current or "ask.ytel.com/e3t" in current:
            log_fn("HubSpot tracking page detected, looking for redirect target...")
            # Try clicking any download/report link on the page
            try:
                links = driver.find_elements(By.XPATH, "//a[contains(@href,'ytel') or contains(@href,'download') or contains(@href,'report')]")
                if links:
                    links[0].click()
                    time.sleep(4)
            except Exception:
                pass

        log_fn(f"Current URL after redirect: {driver.current_url}")

        # 6. Wait for CSV to appear in download folder
        log_fn("Waiting for CSV download to complete...")
        timeout = 30
        elapsed = 0
        downloaded_file = None

        while elapsed < timeout:
            csv_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv"))
            # Find any new CSV that isn't our existing report
            new_csvs = [f for f in csv_files if os.path.basename(f) != "ytel_agent_report.csv"]
            if new_csvs:
                # Pick the most recently modified
                downloaded_file = max(new_csvs, key=os.path.getmtime)
                break
            time.sleep(1)
            elapsed += 1

        if downloaded_file:
            # Rename/move to our standard filename
            if os.path.exists(CSV_SAVE_PATH):
                os.remove(CSV_SAVE_PATH)
            os.rename(downloaded_file, CSV_SAVE_PATH)
            log_fn(f"CSV saved to: {CSV_SAVE_PATH}")
            return True
        else:
            log_fn("ERROR: CSV did not download within timeout.")
            return False

    except Exception as e:
        log_fn(f"ERROR during browser automation: {e}")
        return False

    finally:
        driver.quit()


if __name__ == "__main__":
    # For manual testing — paste a report URL here
    test_url = input("Paste the Report Data URL from the email: ").strip()
    success = download_report(test_url)
    print("Download successful!" if success else "Download failed.")
