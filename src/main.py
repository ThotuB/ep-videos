import json
import os
from typing import Callable, List
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from requests.models import HTTPError
from requests_ratelimiter import LimiterSession
from pyrate_limiter import Duration, Rate, Limiter

from src.consts import *
from src.db import *

rate = Rate(4, Duration.SECOND) # only make 4 requests per second
limiter = Limiter(rate)
session = LimiterSession(limiter=limiter)


# search
def search_url(keys: str, page: int):
    return f"{SEARCH_URL}keys={keys}&page={page}"


def get_search(search: str, page: int):
    url = search_url(search, page)

    return session.get(
        url=url,
        headers=SEARCH_HEADERS,
        cookies={"ak_bmsc": COOKIE},
    )


def search(term: str):
    search_key = term.replace(" ", "+")
    search_file = term.replace(" ", "_")

    pages = range(1, MAX_PAGES + 1)

    get_search_with_key = partial(get_search, search_key)

    with ThreadPoolExecutor(max_workers=4) as pool:
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


# file find/download
Fn = Callable[[int, File, str], bool]


def find_file(id: int, file: File, ext: str):
    uri = file.url.removesuffix(".pdf") + ext

    with session.head(
        url=uri, headers=NORMAL_HEADERS, cookies=COOKIES, timeout=(3, 10)
    ) as resp:
        if resp.status_code == 404:
            if isinstance(file.progress, Attempts):
                file.progress.extensions.append(ext)
            print(f"{R}[{id}] NOK - {ext} not found{X}")
            return False

        resp.raise_for_status()

        total_size = int(resp.headers.get("Content-Length", 0))
        file.progress = RealFile(extension=ext, size=total_size)

        print(f"{G}[{id}] OK - found with ext: {ext}, size:{total_size:,}{X}")

    return True


def download_file(id: int, file: File, ext: str):
    file_name_new = file.name + ext
    download_path = Path(f"./videos/{file.dataset}/{file_name_new}")

    if download_path.exists():
        file_size = download_path.stat().st_size
        file.progress = RealFile(extension=ext, size=file_size, downloaded=True)
        print(f"{Y}[{id}] SKIP - file downloaded{X}")
        return True

    print(f"[{id}] Trying to find {ext} and download")

    uri = file.url.removesuffix(".pdf") + ext

    with session.get(
        url=uri,
        headers=NORMAL_HEADERS,
        cookies=COOKIES,
        stream=True,
        timeout=(3, 10),
    ) as video:
        if video.status_code == 404:
            if isinstance(file.progress, Attempts):
                file.progress.extensions.append(ext)
            print(f"{R}[{id}] NOK - {ext} not found{X}")
            return False

        video.raise_for_status()

        total_size = int(video.headers.get("Content-Length", 0))
        file.progress = RealFile(extension=ext, size=total_size)

        if total_size > FILE_SIZE_LIMIT:
            print(f"{Y}[{id}] SKIP - too large: {total_size:,}B{X}")
            return True

        download_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"{G}[{id}] Downloading... {file_name_new} (size:{total_size}){X}")
        with open(download_path, "wb") as vf:
            for chunk in video.iter_content(1024 * 1024):
                if not chunk:
                    continue

                vf.write(chunk)

        file.progress.downloaded = True

        print(f"{G}[{id}] OK - dowloaded with ext: {ext}, size:{total_size:,}{X}")

    return True


def download_or_find_file(file: File, id: int, fn: Fn, ext: str) -> bool:
    if isinstance(file.progress, RealFile):
        file_extension = file.progress.extension
        # print(f"{Y}[{id}] SKIP - {file_extension} already found{X}")
        return True

    if ext in file.progress.extensions:
        # print(f"{Y}[{id}] SKIP - {ext} already tried{X}")
        return False

    try:
        return fn(id, file, ext)
    except HTTPError as e:
        if e.response.status_code == 403:
            print(f"{R}ACCESS DENIED - stopping{X}")
            raise Exception("ACCESS DENIED")

        print(f"{R}[{id}] EXCEPTION {e}{X}")
        return False


def uncover_file(fn: Fn, id: int, file: File):
    # print(f"[{id}] Processing {file.dataset}/{file.name}")

    partial_download_or_find_file = partial(
        download_or_find_file, file=file, id=id, fn=fn
    )

    # with ThreadPoolExecutor(max_workers=EXTENSION_THREADS) as pool:
    #     futures = [
    #         pool.submit(partial_download_or_find_file, ext=ext) for ext in EXTENSIONS
    #     ]
    #
    #     for future in as_completed(futures):
    #         found = future.result()
    #         if found:
    #             return id

    for ext in EXTENSIONS:
        found = download_or_find_file(file, id, fn, ext)
        if found:
            return id

    print(f"{R}[{id}] NOTHING FOUND{X}")

    return id


def uncover(files: List[File], download: bool):
    if download:
        fn = download_file
    else:
        fn = find_file

    uncover_file_with_fn = partial(uncover_file, fn)

    with ThreadPoolExecutor(max_workers=FILE_THREADS) as pool:
        futures = [
            pool.submit(uncover_file_with_fn, id, file) for id, file in enumerate(files)
        ]

        try:
            for future in as_completed(futures):
                _ = future.result()
                save_db(files)
        except:
            print("STOPPING POOL")
            pool.shutdown()
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
        db = uncover(db, False)
    except:
        print("STOPPING AND SAVING DB")

    save_db(db)
    pass


if __name__ == "__main__":
    main()
