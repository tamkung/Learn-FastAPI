from fastapi import APIRouter
from app.user.controller import get_users, get_user, create_user, edit_user, delete_user

router = APIRouter(
    prefix="/user",
    tags=["User"],
    responses={404: {"message": "Not found"}}
)

router.add_api_route(methods=["GET"], path="/", endpoint=get_users)
router.add_api_route(methods=["GET"], path="/{user_id}", endpoint=get_user)
router.add_api_route(methods=["POST"], path="/", endpoint=create_user)
router.add_api_route(methods=["PUT"], path="/{user_id}", endpoint=edit_user)
router.add_api_route(methods=["DELETE"], path="/{user_id}", endpoint=delete_user)