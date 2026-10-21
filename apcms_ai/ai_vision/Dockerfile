# 빌드 컨텍스트: apcms_ai. CPU / Linux amd64 배포 후보 이미지입니다.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg YOLO_AUTOINSTALL=false \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    HOME=/home/vision YOLO_CONFIG_DIR=/home/vision/.config/Ultralytics \
    VISION_MODEL_DIR=/app/ai_vision/models \
    VISION_DATA_DIR=/app/ai_vision/data VISION_RESULT_DIR=/var/lib/vision/results
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 vision
WORKDIR /app
COPY ai_vision/requirements-runtime.txt /tmp/requirements-runtime.txt
# Torch는 CPU wheel 저장소를 사용해 불필요한 CUDA 라이브러리 설치를 피합니다.
RUN python -m pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r /tmp/requirements-runtime.txt \
    && python -m pip check
COPY --chown=vision:vision ai_vision /app/ai_vision
RUN mkdir -p /var/lib/vision/results /home/vision/.config/Ultralytics \
    && chown -R vision:vision /var/lib/vision /home/vision
USER vision
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3).close()"
# 중복 억제·요청 제한이 프로세스 메모리 기준이므로 우선 worker는 하나만 사용합니다.
CMD ["python", "-m", "uvicorn", "ai_vision.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
