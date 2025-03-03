FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /

# Copy the pyproject.toml and poetry.lock files into the container
COPY . .

# Install Poetry
RUN pip install --no-cache-dir poetry

# Install the dependencies using Poetry
RUN poetry install --without dev --no-root

# Expose the port that the app runs on
EXPOSE 7860

# Command to run the application
CMD ["poetry",  "run", "gradio", "app.py"]
