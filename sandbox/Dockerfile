FROM python:3.11-slim

WORKDIR /code

# Install pytest and common libraries
RUN pip install pytest pytest-json-report

# No network access at runtime (enforced by docker run --network=none)
CMD ["pytest", "/code", "-q", "--tb=short"]
