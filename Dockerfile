FROM python:3.11-slim

# Install system dependencies for lxml, Pillow and EasyOCR runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Copy only requirements first to leverage Docker cache
COPY backend/requirements.txt /app/backend/requirements.txt

# Upgrade pip and install CPU-only PyTorch wheel first,
# then install the rest of the requirements (including easyocr)
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir torch==2.2.0+cpu torchvision==0.15.2+cpu -f https://download.pytorch.org/whl/cpu/torch_stable.html \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend /app/backend

# Pre-warm EasyOCR models (downloads model files during build)
RUN python - <<'PY'
import easyocr
# initialize reader (gpu=False) to force model download into image
easyocr.Reader(['en'], gpu=False)
print("EasyOCR models cached")
PY

ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# Use your preferred run command; keep same as before or use gunicorn for production
CMD ["python", "app.py"]