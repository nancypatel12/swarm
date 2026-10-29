# The Swarm API. Saved runs go to /data; on a host with a persistent volume, mount it there so shared links survive
# restarts. Hosts set PORT; it defaults to 8000.
FROM python:3.14-slim

WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY swarm swarm
COPY examples examples

# Writable by any user, since some hosts run the container as a non-root user.
RUN mkdir -p /data && chmod 777 /data
ENV SWARM_DATA_DIR=/data PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn swarm.app:app --host 0.0.0.0 --port ${PORT}"]
