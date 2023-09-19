from fastapi import FastAPI
import uvicorn
from app.file.route import router as file
from app.user.route import router as user
from app.book.route import router as book

app = FastAPI()

app.include_router(file)
app.include_router(user)
app.include_router(book)

@app.get("/")
async def root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)