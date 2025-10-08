# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt .
COPY .env.example .env.example

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем необходимые директории
RUN mkdir -p files/audio files/documents files/images files/temp

# Создаем пользователя без root прав
RUN useradd --create-home --shell /bin/bash botuser
RUN chown -R botuser:botuser /app
USER botuser

# Запускаем бота
CMD ["python", "main.py"]
