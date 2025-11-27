import os
import csv
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.ie.webdriver import WebDriver
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement


PROGRESS_FILE = "data/completed_players.txt"
OUTPUT_FILE = "data/player_club_history.csv"


# Make a new class from uc_orig.Chrome and redefine __del__ function to suppress exception
class Chrome(uc.Chrome):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __del__(self):
        try:
            self.service.process.kill()
            self.quit()
        except:
            pass


def get_driver(headless: bool = False) -> WebDriver:
    """Create a Chrome driver with faster page load strategy."""
    chrome_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        *(["--headless=new"] if headless else []),
    ]

    options = uc.ChromeOptions()
    options.page_load_strategy = "eager"
    for arg in chrome_args:
        options.add_argument(arg)

    driver = Chrome(options=options, version_main=141)
    driver.set_page_load_timeout(60)

    return driver


def wait_for_id(driver: WebDriver, element_id: str, timeout: int = 5) -> WebElement:
    """Wait until an element with the given ID appears in the DOM."""
    print(f"⏳ Waiting for element with id='{element_id}' (timeout={timeout}s)...")
    try:
        element = WebDriverWait(driver, timeout).until(expected_conditions.presence_of_element_located((By.ID, element_id)))
        return element
    except TimeoutException:
        raise


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} hr" if h == 1 else f"{h} hrs")
    if m:
        parts.append(f"{m} min")
    if s or not parts:  # show "0 s" if everything else is zero
        parts.append(f"{s} s")
    return ", ".join(parts)


def load_completed_players() -> set[str]:
    """Load completed player URLs from a text file (one per line)."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_completed_player(link: str) -> None:
    """Append a single completed player URL to the progress file."""
    os.makedirs(os.path.dirname(PROGRESS_FILE) or ".", exist_ok=True)
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")


def generate_big5_season_league_urls(start_year: int, end_year: int) -> list[str]:
    """Generate FBref competition URLs for multiple seasons and leagues."""
    leagues = {
        9: "Premier-League",
        12: "La-Liga",
        # 20: "Bundesliga",
        # 11: "Serie-A",
        # 13: "Ligue-1",
    }

    urls = []
    for start in range(start_year, end_year):
        end = start + 1
        season_str = f"{start}-{end}"
        for comp_id, league_name in leagues.items():
            urls.append(f"https://fbref.com/en/comps/{comp_id}/{season_str}/{season_str}-{league_name}-Stats")
    return urls


def get_season_club_links(driver: WebDriver, url: str) -> tuple[str, list[str]]:
    """Fetch all Premier League club 'Stats' page links from the given season page using Selenium."""
    print(f"🌐 Fetching season clubs links from {url}")

    driver.get(url)

    # Example: https://fbref.com/en/comps/9/2024-2025/2024-2025-Premier-League-Stats
    url_parts = url.split("/")
    competition_id, season = url_parts[-3], url_parts[-2]

    table_id = f"results{season}{competition_id}1_overall"
    table_el = wait_for_id(driver, table_id)

    soup = BeautifulSoup(table_el.get_attribute("outerHTML"), "html.parser")
    table = soup.find("table")

    clubs = []
    for a in table.select("a[href^='/en/squads/']"):
        club_url = "https://fbref.com" + a["href"]
        clubs.append(club_url)

    return competition_id, clubs


def normalize_player_url(url: str) -> str:
    """
    Convert player matchlog URLs like:
    https://fbref.com/en/players/ef7cd87a/matchlogs/2024-2025/summary/Abdoulaye-Toure-Match-Logs
    into main profile URLs:
    https://fbref.com/en/players/ef7cd87a/Abdoulaye-Toure
    """
    parts = urlparse(url).path.strip("/").split("/")
    # detect matchlog pattern
    if len(parts) > 4 and parts[3] == "matchlogs":
        player_id = parts[2]
        name_part = parts[-1]
        clean_name = name_part.replace("-Match-Logs", "")
        return f"https://fbref.com/en/players/{player_id}/{clean_name}"
    return url


def get_player_links_from_season_club_link(driver: WebDriver, season_club_url: str, competition_id: str) -> list[str]:
    """Fetch all player profile links from a given club's page."""
    print(f"⚽ Fetching players from season club page: {season_club_url}")

    driver.get(season_club_url)

    table_id = f"stats_standard_{competition_id}"
    table_el = wait_for_id(driver, table_id)

    soup = BeautifulSoup(table_el.get_attribute("outerHTML"), "html.parser")
    table = soup.find("table")

    players = []
    for a in table.select("a[href^='/en/players/']"):
        player_url = "https://fbref.com" + a["href"]
        players.append(normalize_player_url(player_url))

    return players


def store_player_club_history(driver: WebDriver, url: str, csv_writer) -> None:
    """Fetch a player's club history page HTML using the shared Selenium driver."""
    print(f"🌐 Fetching page for {url}")

    driver.get(url)

    # Example: https://fbref.com/en/players/d70ce98e/Lionel-Messi -> d70ce98e
    url_parts = url.split("/")
    player_id, player_name = url_parts[-2], url_parts[-1]

    table_id = f"stats_player_summary_{player_id}"
    table_el = wait_for_id(driver, table_id)

    soup = BeautifulSoup(table_el.get_attribute("outerHTML"), "html.parser")
    table = soup.find("table")

    records = []
    for row in table.select("tbody tr"):
        season = row.select_one("th[data-stat='year_id']")
        club = row.select_one("td[data-stat='team']")
        apps = row.select_one("td[data-stat='all_games']")  # appearances column

        if not season or not club:
            continue

        season = season.text.strip()
        club = club.text.strip()
        try:
            apps = int((apps.text or "0").strip())
        except:
            apps = 0

        if not season or not club:
            continue

        records.append((season, club, apps))

    if not records:
        return

    current_club = records[0][1]
    start_season = records[0][0]
    end_season = records[0][0]
    apps_season = records[0][2]

    for season, club, apps in records[1:]:
        if club == current_club:
            end_season = season
            apps_season += apps
        else:
            csv_writer.writerow([player_id, player_name, current_club, start_season, end_season, apps_season])
            current_club = club
            start_season = end_season = season
            apps_season = apps

    csv_writer.writerow([player_id, player_name, current_club, start_season, end_season, apps_season])


if __name__ == "__main__":
    start_ts = time.time()

    driver = get_driver()

    player_links = set()

    season_league_urls = generate_big5_season_league_urls(2020, 2025)
    print(season_league_urls)

    MAX_RETRIES = 3

    for season_league_url in season_league_urls:
        for attempt in range(MAX_RETRIES):
            try:
                print(f"🌍 Processing season {season_league_url} (Attempt {attempt+1}/{MAX_RETRIES})")

                competition_id, season_club_links = get_season_club_links(driver, season_league_url)
                print(f"✅ Found {len(season_club_links)} clubs for {season_league_url}")

                for link in season_club_links:
                    player_links.update(get_player_links_from_season_club_link(driver, link, competition_id))

                # ✅ If successful, break out of retry loop
                break

            except Exception as e:
                print(f"⚠️ Error while processing {season_league_url}: {e}")
                print(f"🔁 Restarting driver (attempt {attempt+1}/{MAX_RETRIES})...")

                driver.quit()
                driver = get_driver()

                if attempt == MAX_RETRIES - 1:
                    print(f"❌ Failed {season_league_url} after {MAX_RETRIES} retries — skipping.")

    completed_players = load_completed_players()
    print(f"✅ Loaded {len(completed_players)} completed players")

    player_links = player_links - completed_players
    total = len(player_links)
    print(f"Starting processing of {total} players")

    os.makedirs(os.path.dirname(OUTPUT_FILE) or ".", exist_ok=True)
    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # only write header if file was empty
        if f.tell() == 0:
            writer.writerow(["player_id", "player_name", "club", "start", "end", "appearances"])

        # ["https://fbref.com/en/players/d70ce98e/Lionel-Messi"]
        for idx, link in enumerate(player_links, start=1):
            try:
                store_player_club_history(driver, link, writer)
                save_completed_player(link)

                # ✅ Force flush to disk after every write
                f.flush()
                os.fsync(f.fileno())

                print(f"[{idx}/{total}] 📝 Stored club history for: {link}")
            except TimeoutException:
                print(f"[{idx}/{total}] ⏰ Timeout — element not found for {link}. Skipping.")
                continue
            except:
                print(f"⚠️ Restarting driver.")
                driver.quit()
                driver = get_driver()
                continue

    driver.quit()
    print("✅ All done.")

    elapsed = time.time() - start_ts
    print(f"Processed major league player data for seasons 2015–2025 in {format_duration(elapsed)}")


# python script/scrape_fbref.py
