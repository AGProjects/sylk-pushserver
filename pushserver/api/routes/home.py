from fastapi import APIRouter

router = APIRouter()


@router.get('/')
async def welcome():
    return 'Welcome to sylk-push server'
