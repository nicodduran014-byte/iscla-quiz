FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PORT=8000 ISCLA_DB=/datos/iscla.sqlite3
WORKDIR /app
RUN useradd --system --uid 10001 iscla && mkdir /datos && chown iscla /datos
COPY --chown=iscla:iscla index.html ./
COPY --chown=iscla:iscla templates ./templates
COPY --chown=iscla:iscla static ./static
COPY --chown=iscla:iscla servidor ./servidor
USER 10001
EXPOSE 8000
CMD ["python", "servidor/app.py"]
