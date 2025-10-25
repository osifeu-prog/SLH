# slim image
FROM python:3.11-slim

# עדכוני מערכת קלים + wheel לשיפור התקנות פייתון
RUN apt-get update -y && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# ספריות הבוט
WORKDIR /app

# התקנת דרישות (מועתקות קודם כדי לא לפספס cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# קוד הבוט
COPY . /app

# סביבת ריצה
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# חשוב: בתוך SLH_bot/ מריצים main:app (לא SLH_bot.main:app)
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8080"]
