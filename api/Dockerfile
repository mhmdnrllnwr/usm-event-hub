# FILE FUNCTION: Instructions for building the API container image.
# WHAT YOU CAN DO: 
# - Change Python versions.
# - Install system-level tools (like git or compilers).
# WHEN TO CHANGE: When you need a different version of Python or extra Linux tools.

FROM python:3.11-slim

WORKDIR /app

# Copy and install requirements first (Efficiency: only re-runs if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the API code
COPY . .

# Launch command: 0.0.0.0 makes the app reachable outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# 1. Use a lightweight Python base image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy only the requirements first (for better caching)
COPY requirements.txt .

# 4. Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the code from the /api folder into the container
COPY . .

# 6. Run the FastAPI app using uvicorn
# We use 0.0.0.0 so it's accessible from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]