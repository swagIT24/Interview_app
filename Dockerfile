FROM python:3.9

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt
RUN pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu
RUN python -m nltk.downloader stopwords

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]