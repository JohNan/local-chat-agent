FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Git and SSH client
RUN apt-get update && apt-get install -y git openssh-client && rm -rf /var/lib/apt/lists/*

# Configure Git for container usage
RUN git config --global --add safe.directory /codebase \
    && git config --global user.email "agent@gemini.local" \
    && git config --global user.name "Gemini Agent"

COPY server.py .

EXPOSE 5000

CMD ["python", "server.py"]
