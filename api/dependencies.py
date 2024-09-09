from fastapi import Body, HTTPException, Depends, Request
from typing import Annotated
from datetime import datetime

def has_credentials(credentials: dict = Body(...), ):
    if "username" in credentials and "password" in credentials:
        return credentials
    raise HTTPException(status_code=401, detail="Missing credentials")

def has_access_token(request: Request):
    if "access_token" not in request.cookies:
        raise HTTPException(status_code=401, detail="Missing access token")
    return request.cookies["access_token"]

def has_surface_id(surface_id: str = None):
    try:
        int(surface_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid surface ID")
    return surface_id

def has_valid_date(date: str = None):
    if date is None:
        raise HTTPException(status_code=400, detail="Missing valid date")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")
    return date

def has_valid_time(time: str = None):
    if time is None:
        raise HTTPException(status_code=400, detail="Missing valid time")
    try:
        datetime.strptime(time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time")
    return time

def has_feed_mode(feed_mode: int = None):
    if feed_mode is None:
        raise HTTPException(status_code=400, detail="Missing feed mode")
    if feed_mode not in [4, 5]:
        raise HTTPException(status_code=400, detail="Invalid feed mode")
    return feed_mode

def has_filename(filename: str = None):
    if filename is None:
        raise HTTPException(status_code=400, detail="Missing filename")
    return filename
