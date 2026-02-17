# Use the official Playwright image which includes Python and browsers
# Must match the version of playwright installed via pip
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Create a non-root user with an arbitrary UID (1000 is standard)
# The Playwright image likely already has a user 1000 (pwuser)
# We will use that user instead of creating a new one to avoid conflicts

# Set ownership of the working directory to the user 1000
RUN chown -R 1000:1000 /app

USER 1000

# Set environment variables
# Set HOME to /app to avoid guessing the user's home directory name
ENV HOME=/app \
    PATH=/app/.local/bin:$PATH

# Expose the port that the application listens on
EXPOSE 7860

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
