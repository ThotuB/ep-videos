import requests
from pathlib import Path
import threading

# USER CONSTS (can be changed)
FROM_PAGE = 1
COOKIE = "97060C7AC9A182EB50C06CB72D0F5154~000000000000000000000000000000~YAAQSBczF5MhxiWcAQAATt7WMh7lBl6GjtwzyTfq3imRkydO1zzQqGde8fY3lhz/yIyZNHx7nYlSAMUOORh3LI+SaYLXVHbJ55yuUNOmucHJ14KMwaSosb1+jhKVUtdD8V81W8DrmFsUoR2y6OhcSMhbwpMxuNQL2RJ5MbTcZGKInswb1WBEYJHRGUdNWCbb0/OjZOV4OJXvL8TnpdnavXwNeWvc4zaFoO09WoYy5u1Q5wnRu7o82AdjIQZGIG8wy0rBlYVA4uvK4NlsIMuFwFuILINJB1d4QoMFHG7y6KSbR/eiAtyh6XdzbISgc+20utzp2Int5BczTQKpDsL1KSpgOpWoxbzIJZbepM1Z8+GwTAlRQQZKeTsAzUiiOk8OysWaY/A4hZrVvdVnqAGNzCuUVcpZQ/2PHfTr0r+m86wEDDx02K/Q1tC6Oq4gw9maWDu94/EP0yxlm7cVKfSl3i22NR/nFi0="
FILE_SIZE_LIMIT = 50_000_000
FORMAT = ".mp4"

# SITE CONSTS (should probably not be changed)
SITE_URL = "https://www.justice.gov/epstein"
SEARCH_URL = "https://www.justice.gov/multimedia-search?"
MAX_PAGES = 381 # might change in future?
ENTRIES_PER_PAGE = 10
NORMAL_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Alt-Used": "www.justice.gov",
    "Connection": "keep-alive",
    "Host": "www.justice.gov",
    # "If-Modified-Since": "Fri, 06 Feb 2026 01:20:33 GMT",
    # "If-None-Match": "\"1770340833-gzip\"",
    "Priority": "u=0, i",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?!",
    "TE": "trailers",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0"
}

def search_url(keys: str, page: int):
    return f'{SEARCH_URL}keys={keys}&page={page}'


def get_home_page():
    return requests.get(
        url=SITE_URL,
        headers=NORMAL_HEADERS,
        cookies={
            "ak_bmsc": COOKIE,
            "justiceGovAgeVerified": "true"
        }
    )

def get_search(search: str, page: int):
    url = search_url(search, page)

    return requests.get(
        url=url,
        headers= {    
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Alt-Used": "www.justice.gov",
            "Connection": "keep-alive",
            "Host": "www.justice.gov",
            "Priority": "u=0",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
            "x-queueit-ajaxpageurl": "https%3A%2F%2Fwww.justice.gov%2Fepstein"
        },
        cookies={
            "ak_bmsc": COOKIE
        }
    )

def download_hit(hit, progress):
    source = hit["_source"]
    file_name: str = source["ORIGIN_FILE_NAME"]
    file_uri: str = source["ORIGIN_FILE_URI"]
    file_key: str = source["key"]
    file_doc = file_key.split("/")[0]

    file_name_new = file_name.removesuffix(".pdf")
    file_uri_new = file_uri.removesuffix(".pdf")

    file_name_new = file_name_new + FORMAT
    file_uri_new = file_uri_new + FORMAT

    print(f"[{progress}] Processing {file_doc}/{file_name} -> {FORMAT}")

    file_path = Path(f"./videos/{file_doc}/{file_name_new}")
    if file_path.exists():
        print(f"\033[33m[{progress}] SKIP\033[0m")
        return

    chunks = 0
    try:
        with requests.get(
            url=file_uri_new,
            headers=NORMAL_HEADERS,
            cookies={
                "ak_bmsc": COOKIE,
                "justiceGovAgeVerified": "true"
            },
            stream=True,
            timeout=(3,10)) as video:
            if video.status_code != 200:
                print(f"\033[31m[{progress}] {FORMAT} not found\033[0m")
                return

            video.raise_for_status()

            total_size = int(video.headers.get("Content-Length", 0))
            if total_size > FILE_SIZE_LIMIT:
                print(f"\033[33m[{progress}] SKIP TOO LARGE: {total_size:,}B\033[0m")
                return

            print(f"[{progress}] size: {total_size}")

            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as vf:
                for chunk in video.iter_content(1024 * 1024):
                    if not chunk:
                        continue

                    chunks += len(chunk)
                    vf.write(chunk)
            
            print(f"\033[32m[{progress}] OK\033[0m")
    except Exception as e:
        print(f"\033[31m[{progress}] EXCEPTION {e}\033[0m")

def search_and_download(term: str):
    search_key = term.replace(" ", "+")
    search_file = term.replace(" ", "_")

    for page in range(FROM_PAGE, MAX_PAGES):
        response = get_search(search_key, page)

        file_path = Path(f"./search/{search_file}-page_{page}.json")

        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as sf:
            sf.write(response.content)

        try:
            json = response.json()
            hits = json["hits"]["hits"]

            threads = []
            for i, hit in enumerate(hits):
                progress = (page-1) * ENTRIES_PER_PAGE + i
                
                t = threading.Thread(target=download_hit, args=(hit,progress,))
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

            print(f"PAGE {page}/{MAX_PAGES} DONE")
        except Exception as e:
            # if this throws, you probably lost access to site...
            print(f"PAGE {page} EXCEPTION {e}")


if __name__ == "__main__":
    search_and_download("no images produced")

