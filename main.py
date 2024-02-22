from fastapi import FastAPI
import uvicorn
import asyncio
import schedule

from app.file.route import router as file
from app.user.route import router as user
from app.book.route import router as book
from app.mail.route import router as mail

from app.mail.controller import netflixForwardEmail

app = FastAPI()

app.include_router(file)
app.include_router(user)
app.include_router(book)
app.include_router(mail)

async def scheduler():
    schedule.every(10).seconds.do(netflixForwardEmail)  # Run 'job' every minute
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scheduler())

@app.get("/")
async def root():
    result = {
        "message": "Hello FastAPI",
        "status": 200
    }
    return result

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)