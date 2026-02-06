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
- `FORMAT`
    - only tested mp4s, other formats might work as well
- `FILE_SIZE_LIMIT`
    - default to 50MB (some videos reach up to 10GB)
    - most videos are under the limit
    - may prevent being IP banned / timed out
- `FROM_PAGE`
    - edit if you're having issues with some page

# warning before running

YOU IP WILL PROBABLY GET BLACKLISTED\*

\*it seems to be only temporary, but good luck...

# run

`python main.py`
