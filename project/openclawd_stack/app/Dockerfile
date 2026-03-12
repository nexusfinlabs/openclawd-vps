FROM python:3.12-slim

WORKDIR /app

RUN sed -i -e 's/Components: main/Components: main contrib non-free/' /etc/apt/sources.list.d/debian.sources || true && \
    apt-get update && \
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get install -y --no-install-recommends \
    curl \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libffi-dev \
    shared-mime-info \
    ttf-mscorefonts-installer \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
