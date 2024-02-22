from fastapi import APIRouter
from app.mail.controller import receive_mail_all_folder, replyEmail, forwardEmail

router = APIRouter(
    prefix="/mail",
    tags=["Mail"],
    responses={404: {"message": "Not found"}}
)

router.add_api_route(methods=["POST"], path="/", endpoint=receive_mail_all_folder)
router.add_api_route(methods=["POST"], path="/reply", endpoint=replyEmail)
router.add_api_route(methods=["POST"], path="/forward", endpoint=forwardEmail)