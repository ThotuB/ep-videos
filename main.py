import json
import os
from typing import List, Literal, Union
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pydantic import BaseModel
from requests.models import HTTPError

# USER CONSTS (can be changed)
COOKIE = "97060C7AC9A182EB50C06CB72D0F5154~000000000000000000000000000000~YAAQSBczF5MhxiWcAQAATt7WMh7lBl6GjtwzyTfq3imRkydO1zzQqGde8fY3lhz/yIyZNHx7nYlSAMUOORh3LI+SaYLXVHbJ55yuUNOmucHJ14KMwaSosb1+jhKVUtdD8V81W8DrmFsUoR2y6OhcSMhbwpMxuNQL2RJ5MbTcZGKInswb1WBEYJHRGUdNWCbb0/OjZOV4OJXvL8TnpdnavXwNeWvc4zaFoO09WoYy5u1Q5wnRu7o82AdjIQZGIG8wy0rBlYVA4uvK4NlsIMuFwFuILINJB1d4QoMFHG7y6KSbR/eiAtyh6XdzbISgc+20utzp2Int5BczTQKpDsL1KSpgOpWoxbzIJZbepM1Z8+GwTAlRQQZKeTsAzUiiOk8OysWaY/A4hZrVvdVnqAGNzCuUVcpZQ/2PHfTr0r+m86wEDDx02K/Q1tC6Oq4gw9maWDu94/EP0yxlm7cVKfSl3i22NR/nFi0="
FILE_SIZE_LIMIT = 200_000_000
EXTENSIONS = [
    # video
    ".mp4",  # found
    ".mov",  # found
    ".m4v",  # found
    ".flv",
    ".vob",  # found
    ".wmv",  # found
    ".avi",  # found
    ".amv",
    ".qt",
    # audio
    ".mp3",  # found
    ".m4a",  # found
]
DOWNLOAD_THREADS = 3


# SITE CONSTS (should probably not be changed)
SITE_URL = "https://www.justice.gov/epstein"
SEARCH_URL = "https://www.justice.gov/multimedia-search?"
MAX_PAGES = 381  # might change in future?
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
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
}
SEARCH_HEADERS = {
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
    "x-queueit-ajaxpageurl": "https%3A%2F%2Fwww.justice.gov%2Fepstein",
}
COOKIES = {"ak_bmsc": COOKIE, "justiceGovAgeVerified": "true"}

R = "\033[31m"
Y = "\033[33m"
G = "\033[32m"
X = "\033[0m"


# database
class RealFile(BaseModel):
    type: Literal["real"] = "real"
    extension: str
    size: int
    downloaded: bool = False


class Attempts(BaseModel):
    type: Literal["attempts"] = "attempts"
    extensions: List[str] = []


Progress = Union[RealFile, Attempts]


class File(BaseModel):
    dataset: str
    name: str
    url: str
    progress: Progress


def save_db(files: list[File]):
    db_path = Path("db.json")

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump([f.model_dump() for f in files], f, indent=2)


def load_db():
    db_path = Path("db.json")

    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [File.model_validate(item) for item in data]


# search
def search_url(keys: str, page: int):
    return f"{SEARCH_URL}keys={keys}&page={page}"


def get_search(search: str, page: int):
    url = search_url(search, page)

    return requests.get(
        url=url,
        headers=SEARCH_HEADERS,
        cookies={"ak_bmsc": COOKIE},
    )


def search(term: str):
    search_key = term.replace(" ", "+")
    search_file = term.replace(" ", "_")

    pages = range(1, MAX_PAGES + 1)

    get_search_with_key = partial(get_search, search_key)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(get_search_with_key, page): page for page in pages}

        for future in as_completed(futures):
            page = futures[future]

            try:
                response = future.result()
            except Exception as e:
                print(f"PAGE {page} EXCEPTION {e}")
                continue

            file_path = Path(f"./search/{search_file}-page_{page}.json")

            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as sf:
                sf.write(response.content)

            print(f"PAGE {page}/{MAX_PAGES} DONE")


# parse search
def parse_search_results():
    search_dir = Path("./search")

    data = []
    for file_name in os.listdir(search_dir):
        path = os.path.join(search_dir, file_name)

        with open(path, "r", encoding="utf-8") as f:
            data.append(json.load(f))

    files = []
    for d in data:
        hits = d["hits"]["hits"]

        for hit in hits:
            source = hit["_source"]
            name: str = source["ORIGIN_FILE_NAME"]
            url: str = source["ORIGIN_FILE_URI"]
            key: str = source["key"]
            dataset = key.split("/")[0]

            file = File(
                dataset=dataset,
                name=name.removesuffix(".pdf"),
                url=url,
                progress=Attempts(),
            )
            files.append(file)

    return files


# attempt file download
def download_file(file: File, ext: str, id) -> bool:
    if isinstance(file.progress, RealFile):
        file_extension = file.progress.extension
        print(f"{Y}[{id}] SKIP - {file_extension} already found{X}")
        return True

    if ext in file.progress.extensions:
        print(f"{Y}[{id}] SKIP - {ext} already tried{X}")
        return False

    file_name_new = file.name + ext
    file_path = Path(f"./videos/{file.dataset}/{file_name_new}")

    if file_path.exists():
        file_size = file_path.stat().st_size
        file.progress = RealFile(extension=ext, size=file_size, downloaded=True)
        print(f"{Y}[{id}] SKIP - file downloaded{X}")
        return True

    print(f"[{id}] Trying {ext}")

    file_uri_new = file.url.removesuffix(".pdf") + ext
    try:
        with requests.get(
            url=file_uri_new,
            headers=NORMAL_HEADERS,
            cookies=COOKIES,
            stream=True,
            timeout=(3, 10),
        ) as video:
            if video.status_code == 404:
                file.progress.extensions.append(ext)
                print(f"{R}[{id}] NOK - {ext} not found{X}")
                return False

            video.raise_for_status()

            total_size = int(video.headers.get("Content-Length", 0))
            file.progress = RealFile(extension=ext, size=total_size)

            if total_size > FILE_SIZE_LIMIT:
                print(f"{Y}[{id}] SKIP - too large: {total_size:,}B{X}")
                return True

            file_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"{G}[{id}] Downloading... {file_name_new} (size:{total_size}){X}")
            with open(file_path, "wb") as vf:
                for chunk in video.iter_content(1024 * 1024):
                    if not chunk:
                        continue

                    vf.write(chunk)

            file.progress.downloaded = True

            print(f"{G}[{id}] OK - dowloaded with ext: {ext}, size:{total_size:,}{X}")
            return True
    except HTTPError as e:
        if e.response.status_code == 403:
            print(f"{R}ACCESS DENIED - stopping{X}")
            raise Exception("ACCESS DENIED")

        print(f"{R}[{id}] EXCEPTION {e}{X}")
        return False


def uncover_file(id: int, file: File):
    print(f"[{id}] Processing {file.dataset}/{file.name}")

    for ext in EXTENSIONS:
        found = download_file(file, ext, id)
        if found:
            return id

    print(f"{R}[{id}] NOTHING FOUND{X}")

    return id


def uncover(files: List[File]):
    with ThreadPoolExecutor(max_workers=DOWNLOAD_THREADS) as pool:
        futures = [pool.submit(uncover_file, id, file) for id, file in enumerate(files)]

        for future in as_completed(futures):
            _ = future.result()
            save_db(files)

    return files


# for fuck ups with code...
def reset_attempts(files: List[File]):
    for file in files:
        if isinstance(file.progress, Attempts):
            file.progress.extensions = []

    return files


def main():
    # search("no images produced")
    # db = parse_search_results()
    # save_db(db)
    db = load_db()
    # db = reset_attempts(db)
    try:
        db = uncover(db)
    except:
        print("STOPPING AND SAVING DB")

    save_db(db)


if __name__ == "__main__":
    main()
