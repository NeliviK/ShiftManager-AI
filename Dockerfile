# 1. Base Python image
FROM python:3.12-slim

# Disable log buffering
ENV PYTHONUNBUFFERED=1

# 2. Set working directory
WORKDIR /app

# 3. Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of the project
COPY . .

# 5. Run the bot
CMD ["python", "main.py"]