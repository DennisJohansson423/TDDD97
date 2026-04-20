import os
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Selenium-test för Twidder


def run_tests():
    os.environ["TWIDDER_DB"] = "test_database.db"

    print("Startar webbservern i bakgrunden...")
    server_process = subprocess.Popen(["python3", "server.py"])
    time.sleep(2)

    chrome_options = Options()
    chrome_options.add_argument("--incognito")
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get("http://127.0.0.1:5001/")

        print("1. Testar Sign Up...")
        wait.until(EC.visibility_of_element_located((By.ID, "signupEmail"))).send_keys(
            "selenium@test.com"
        )
        driver.find_element(By.ID, "signupPassword").send_keys("password123")
        driver.find_element(By.ID, "signupRepeatPassword").send_keys("password123")
        driver.find_element(By.ID, "signupFirstname").send_keys("Test")
        driver.find_element(By.ID, "signupFamilyname").send_keys("Testsson")
        driver.find_element(By.ID, "signupCity").send_keys("Linköping")
        driver.find_element(By.ID, "signupCountry").send_keys("Sweden")
        Select(driver.find_element(By.ID, "signupGender")).select_by_value("Other")

        driver.find_element(By.ID, "signupButton").click()
        wait.until(
            EC.text_to_be_present_in_element(
                (By.ID, "signup_message"), "Registration successful!"
            )
        )

        print("2. Testar Sign In...")
        wait.until(EC.element_to_be_clickable((By.ID, "loginEmail"))).send_keys(
            "selenium@test.com"
        )
        driver.find_element(By.ID, "loginPassword").send_keys("password123")
        driver.find_element(By.ID, "loginButton").click()

        print("3. Testar att posta på väggen (Home)...")
        home_input = wait.until(
            EC.visibility_of_element_located((By.ID, "homeWallInput"))
        )
        home_input.send_keys("Detta är ett autogenererat testinlägg!")
        driver.find_element(
            By.CSS_SELECTOR, "button[onclick='postToHomeWall()']"
        ).click()

        print("4. Testar Navigering och Sök i Browse-vyn...")
        browse_tab = wait.until(EC.element_to_be_clickable((By.ID, "tabButtonBrowse")))
        browse_tab.click()

        browse_email = wait.until(
            EC.visibility_of_element_located((By.ID, "browseEmail"))
        )
        browse_email.send_keys("selenium@test.com")
        driver.find_element(By.CSS_SELECTOR, "button[onclick='browseUser()']").click()

        print("5. Testar Sign Out...")
        account_tab = wait.until(
            EC.element_to_be_clickable((By.ID, "tabButtonAccount"))
        )
        account_tab.click()

        logout_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[onclick='logout()']"))
        )
        logout_btn.click()

        print("Alla tester slutfördes framgångsrikt!")

    finally:
        print("Städar upp...")
        driver.quit()
        server_process.terminate()
        server_process.wait()

        if os.path.exists("test_database.db"):
            os.remove("test_database.db")
            print("Testdatabas raderad.")


if __name__ == "__main__":
    run_tests()
