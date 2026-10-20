# Factory image: the portal and the requirements / data / knowledge / app agent jobs.
# Build context: the prd-app-factory folder.   az acr build ... --file infra/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt python-multipart==0.0.32 azure-storage-queue==12.18.0
COPY insights insights
COPY skills skills
COPY agents agents
COPY factory factory
RUN mkdir -p apppacks && useradd --uid 1000 --no-create-home factory && chown -R factory /app
USER factory
ENV PYTHONUNBUFFERED=1 PORT=8090
EXPOSE 8090
# The portal by default; each agent job overrides the command with `python -m factory worker --agent <name>`.
CMD ["python", "-m", "factory", "portal", "--host", "0.0.0.0"]
