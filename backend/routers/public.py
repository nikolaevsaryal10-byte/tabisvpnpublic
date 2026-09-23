import os
import time
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from database import get_db
from models import ReviewSubmitReq
from core.dependencies import get_current_user

router = APIRouter()

@router.get("/health")
@router.get("/api/health")
def health_check():
    return {"status": "ok", "time": int(time.time())}

@router.get("/privacy", response_class=HTMLResponse)
@router.get("/api/v1/privacy", response_class=HTMLResponse)
def get_privacy_page():
    candidate_paths = [
        "/var/www/tabisvpn/privacy.html",
        os.path.join(os.path.dirname(__file__), "..", "..", "privacy.html"),
        os.path.join(os.path.dirname(__file__), "..", "privacy.html"),
        "privacy.html"
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Политика конфиденциальности</h1><p>Документ доступен на <a href='https://tabisvpn.site'>tabisvpn.site</a></p>")

@router.get("/terms", response_class=HTMLResponse)
@router.get("/api/v1/terms", response_class=HTMLResponse)
def get_terms_page():
    candidate_paths = [
        "/var/www/tabisvpn/terms.html",
        os.path.join(os.path.dirname(__file__), "..", "..", "terms.html"),
        os.path.join(os.path.dirname(__file__), "..", "terms.html"),
        "terms.html"
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Пользовательское соглашение</h1><p>Документ доступен на <a href='https://tabisvpn.site'>tabisvpn.site</a></p>")

@router.post("/api/v1/reviews/submit", summary="Submit review (canonical)")
@router.post("/api/v1/profile/reviews", include_in_schema=False)
def submit_user_review(req: ReviewSubmitReq, user: dict = Depends(get_current_user)):
    """User submits a review from client/website. Requires admin approval before public show."""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст отзыва не может быть пустым")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="Слишком длинный отзыв (макс. 2000 символов)")
    rating = max(1, min(5, req.rating))
    
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute("""
            INSERT INTO reviews (user_id, author_name, rating, text, platform, approved, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (user["id"], user["nickname"], rating, text, req.platform or "Клиент Tabis", now_str))
        conn.commit()
    return {"status": "ok", "message": "Спасибо за ваш отзыв! Он появится на сайте после модерации."}

@router.get("/api/v1/reviews")
def get_public_reviews():
    """Publicly visible approved reviews for website."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, author_name, rating, text, platform, created_at 
            FROM reviews 
            WHERE approved = 1 
            ORDER BY id DESC 
            LIMIT 50
        """).fetchall()
        return {"status": "ok", "reviews": [dict(r) for r in rows]}
