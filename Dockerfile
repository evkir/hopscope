FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install . && useradd --uid 10001 --no-create-home range
USER 10001
ENTRYPOINT ["hopscope"]
CMD ["report", "--out", "/out"]
