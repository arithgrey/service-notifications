ARG PYTHON_VERSION=python:3.11-slim
FROM ${PYTHON_VERSION}

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY requirements-dev.txt /app/
RUN pip install -r requirements-dev.txt

COPY . .

EXPOSE 8080

CMD ["watchmedo", "auto-restart", \
     "--directory=./", \
     "--pattern=*.py", \
     "--recursive", \
     "--", \
     "uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8080"]
