FROM python:3.13-slim
WORKDIR /app
RUN python -m pip install --no-cache-dir 'fastapi>=0.115,<1' 'uvicorn>=0.34,<1' 'selenium>=4.25,<5'
COPY shared_checkout/validation.py shared_checkout/browser.py shared_checkout/notify.py shared_checkout/worker.py /app/
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "8765"]
