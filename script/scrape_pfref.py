import os
import csv
import random
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


PROGRESS_FILE = "data/nfl_completed_players.txt"
OUTPUT_FILE = "data/nfl_player_club_history.csv"


NFL_TEAMS = [
    "crd",  # Arizona Cardinals
    "atl",  # Atlanta Falcons
    "rav",  # Baltimore Ravens
    "buf",  # Buffalo Bills
    "car",  # Carolina Panthers
    "chi",  # Chicago Bears
    "cin",  # Cincinnati Bengals
    "cle",  # Cleveland Browns
    "dal",  # Dallas Cowboys
    "den",  # Denver Broncos
    "det",  # Detroit Lions
    "gnb",  # Green Bay Packers
    "htx",  # Houston Texans
    "clt",  # Indianapolis Colts
    "jax",  # Jacksonville Jaguars
    "kan",  # Kansas City Chiefs
    "rai",  # Las Vegas Raiders
    "sdg",  # Los Angeles Chargers
    "ram",  # Los Angeles Rams
    "mia",  # Miami Dolphins
    "min",  # Minnesota Vikings
    "nwe",  # New England Patriots
    "nor",  # New Orleans Saints
    "nyg",  # New York Giants
    "nyj",  # New York Jets
    "phi",  # Philadelphia Eagles
    "pit",  # Pittsburgh Steelers
    "sfo",  # San Francisco 49ers
    "sea",  # Seattle Seahawks
    "tam",  # Tampa Bay Buccaneers
    "oti",  # Tennessee Titans
    "was",  # Washington Commanders
]


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
        "--window-size=1200,800",
        *(["--headless=new"] if headless else []),
    ]

    options = uc.ChromeOptions()
    options.page_load_strategy = "eager"
    for arg in chrome_args:
        options.add_argument(arg)

    driver = Chrome(options=options, version_main=141)
    driver.set_window_size(1200, 800)
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


def generate_nfl_season_league_urls(start_year: int, end_year: int) -> list[str]:
    """Generate Pro-Football-Reference NFL season URLs."""
    urls = []
    for year in range(start_year, end_year + 1):
        urls.append(f"https://www.pro-football-reference.com/years/{year}/")
    return urls


def get_season_club_links(season_league_url: str) -> list[str]:
    """
    Generate all NFL team *roster* URLs for a given season.
    Example:
      https://www.pro-football-reference.com/years/2023/
      returns list of "*/teams/phi/2023_roster.htm" etc.
    """
    year = int(season_league_url.rstrip("/").split("/")[-1])
    roster_urls = []

    for team in NFL_TEAMS:
        roster_urls.append(f"https://www.pro-football-reference.com/teams/{team}/{year}_roster.htm")

    return roster_urls


# def normalize_player_url(url: str) -> str:
#     """
#     Convert player matchlog URLs like:
#     https://fbref.com/en/players/ef7cd87a/matchlogs/2024-2025/summary/Abdoulaye-Toure-Match-Logs
#     into main profile URLs:
#     https://fbref.com/en/players/ef7cd87a/Abdoulaye-Toure
#     """
#     parts = urlparse(url).path.strip("/").split("/")
#     # detect matchlog pattern
#     if len(parts) > 4 and parts[3] == "matchlogs":
#         player_id = parts[2]
#         name_part = parts[-1]
#         clean_name = name_part.replace("-Match-Logs", "")
#         return f"https://fbref.com/en/players/{player_id}/{clean_name}"
#     return url


def get_player_links_from_season_club_link(driver: WebDriver, roster_url: str) -> list[str]:
    print(f"Fetching players from roster page: {roster_url}")
    driver.get(roster_url)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Every NFL team roster page has this table.
    table = soup.find("table", id="roster")

    players = set()
    if table:
        for a in table.select("a[href^='/players/']"):
            href = a.get("href", "")
            if href.endswith(".htm"):
                players.add("https://www.pro-football-reference.com" + href)

    return sorted(players)


def store_player_club_history(driver: WebDriver, url: str, csv_writer) -> None:
    print(f"Fetching NFL player page: {url}")
    driver.get(url)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    filename = url.split("/")[-1]
    player_id = filename.replace(".htm", "")

    name_el = soup.select_one("div#meta h1 span")
    if not name_el:
        raise ValueError(f"Player name not found on page: {url}")

    player_name = name_el.text.strip()

    table = (
        soup.find("table", id="passing")
        or soup.find("table", id="rushing_and_receiving")
        or soup.find("table", id="defense")
        or soup.find("table", id="returns")
    )

    if not table:
        raise ValueError(f"Career stats table not found for: {url}")

    records = []

    for row in table.select("tbody tr"):
        season_el = row.select_one("th[data-stat='year_id']")
        team_el = row.select_one("td[data-stat='team_name_abbr']")
        games_el = row.select_one("td[data-stat='games']")

        if not season_el or not team_el:
            continue

        season = season_el.text.strip()
        if not season.isdigit():
            continue

        club = team_el.text.strip()

        try:
            apps = int((games_el.text or "0").strip()) if games_el else 0
        except:
            apps = 0

        records.append((season, club, apps))

    if not records:
        raise ValueError(f"No season records found for: {url}")

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

    season_league_urls = generate_nfl_season_league_urls(2020, 2025)
    print(season_league_urls)

    MAX_RETRIES = 3

    for season_league_url in season_league_urls:
        for attempt in range(MAX_RETRIES):
            try:
                print(f"🌍 Processing season {season_league_url} (Attempt {attempt+1}/{MAX_RETRIES})")

                season_club_links = get_season_club_links(season_league_url)
                print(f"✅ Found {len(season_club_links)} clubs for {season_league_url}")

                for link in season_club_links:
                    time.sleep(random.uniform(0.5, 1))
                    player_links.update(get_player_links_from_season_club_link(driver, link))

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

        # player_links = ["https://www.pro-football-reference.com/players/B/BradTo00.htm"]
        # total = 1

        for idx, link in enumerate(player_links, start=1):
            try:
                time.sleep(random.uniform(0.5, 1))
                store_player_club_history(driver, link, writer)
                save_completed_player(link)

                # ✅ Force flush to disk after every write
                f.flush()
                os.fsync(f.fileno())

                print(f"[{idx}/{total}] 📝 Stored club history for: {link}")
            except TimeoutException:
                print(f"[{idx}/{total}] ⏰ Timeout — element not found for {link}. Skipping.")
                continue
            except ValueError as e:
                print(e)
            except:
                print(f"⚠️ Restarting driver.")
                driver.quit()
                driver = get_driver()
                continue

    driver.quit()
    print("✅ All done.")

    elapsed = time.time() - start_ts
    print(f"Processed major league player data for seasons 2020–2025 in {format_duration(elapsed)}")


# python script/scrape_pfref.py