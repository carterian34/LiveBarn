from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Annotated
from ...dependencies import has_credentials
import requests

url = "https://webapi.livebarn.com"
router = APIRouter(tags=["auth"], responses={200: {"description": "Success"}}, include_in_schema=False)


@router.post("/token", status_code=201)
def token(credentials: Annotated[dict, Depends(has_credentials)]):
    headers = {"Authorization": f"Basic TGl2ZUJhcm4gUWE6MDcyMDE0"}
    data = {"username": credentials["username"],
            "password": credentials["password"],
            "grant_type": "password",
            "device_id": "1725204350305_c8a5f6b5"}
    response = requests.post(f"{url}/oauth/token", headers=headers, data=data)
    if response.status_code == 200:
        try:
            access_token = response.json()["access_token"]
            response = JSONResponse(status_code=201, content={"success": True})
            response.set_cookie("access_token", access_token)
            return response
        except:
            return JSONResponse(content={"success": False})
    else:
        raise HTTPException(status_code=response.status_code, detail=response.json())