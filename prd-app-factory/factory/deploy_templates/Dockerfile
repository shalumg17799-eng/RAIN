# Runtime image for the generated app "__APP_ID__" (build context: the prd-app-factory folder).
#   az acr build --registry <acr> --image factory-__APP_DASH__:<tag> --file apppacks/__APP_ID__/deploy/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY insights insights
COPY skills skills
COPY agents agents
COPY factory factory
COPY apppacks/__APP_ID__ apppacks/__APP_ID__
ENV FACTORY_APP=__APP_ID__ PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
RUN useradd --uid 1000 --no-create-home app && chown -R app /app
USER app
CMD ["python", "-m", "factory.runtime_app.server"]
