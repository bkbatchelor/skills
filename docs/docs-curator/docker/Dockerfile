# Reference image for docs-curator. Build from the skill folder:
#   docker build -f docker/Dockerfile -t docs-curator:dev .
FROM python:3.11-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends libreoffice-impress fonts-dejavu fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /root/.claude/skills/docs-curator
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Cache the embedding model in the image so runs need no network.
ENV FASTEMBED_CACHE_PATH=/opt/fastembed
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

# Only the runtime parts of the skill (tests/ and docker/ stay out of the image).
COPY SKILL.md ./
COPY scripts ./scripts
COPY references ./references
RUN chmod +x scripts/check_env.sh

RUN bash scripts/check_env.sh
CMD ["bash", "scripts/check_env.sh"]
