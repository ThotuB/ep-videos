# setup

## mandatory

- open `https://www.justice.gov/epstein` 
- open network tab: right click > inspect > network
- refresh site
- open up first request

![request](resources/req.png)

- open up cookies tab
- copy value of `ak_bmsc` cookie

![cookie](resources/network.png)

- open main.py
- paste cookie in the `COOKIE` variable 

## optional

change `USER CONSTS`:
- `COOKIE`
    - mandatory, mentioned above
- `EXTENSIONS`
    - add anything else to the list to try
    - don't forget `.` before extension
- `FILE_SIZE_LIMIT`
    - default: 200MB (some videos reach up to 10GB)
    - most videos are under the limit
    - may prevent being timed out
- `DOWNLOAD_THREADS`
    - default: 3
    - too many and you will get timed out pretty quick
    - preferably <5

## python and pip

install python (3+)

install packages
```
pip install -r requirements.txt
```

# database

`db.json` contains everything I've tried/downloaded so far
IMPORTANT: file should be deleted if you're running the code for the first time

if you want to help me out, check out `db.json` and go through files that are:
1. found but not downloaded
```json
{
    "type": "real",
    "extension": ...,
    "downloaded": False
}
```
and download them, since they are larger than my limit

2. not found:
```json
{
    "type": "attempts",
    "extensions": [...]
}
```
and try different extensions

# warning before running

YOU WILL PROBABLY GET RATE LIMITED (ACCESS DENIED)

you should be able to connect again after some time

# run

`python -m src.main`
