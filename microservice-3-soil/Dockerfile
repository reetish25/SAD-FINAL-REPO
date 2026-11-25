FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home soil && mkdir -p /app/data && chown -R soil /app
COPY --chown=soil:soil . .
USER soil
EXPOSE 8091
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8091/health').status==200 else 1)"
CMD ["python", "-m", "soil_service", "serve"]
