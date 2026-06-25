FROM python:3.12-slim

WORKDIR /app

COPY app ./app
COPY static ./static
COPY scripts ./scripts
COPY samples ./samples
COPY run.py .

RUN python scripts/create_sample_template.py

EXPOSE 8000

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
