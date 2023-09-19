from fastapi import APIRouter
from app.file.controller import up_img, up_multi_file, save_csv

router = APIRouter(
    prefix="/img",
    tags=["File"],
    responses={404: {"message": "Not found"}}
)

router.add_api_route(methods=["POST"], path="/", endpoint=up_img)
router.add_api_route(methods=["POST"], path="/multi", endpoint=up_multi_file)
router.add_api_route(methods=["POST"], path="/save-csv", endpoint=save_csv)