FROM python:3.9-bullseye

# Install system dependencies
# Combined list from original Dockerfile and docker_dependencies.sh
RUN apt-get update && apt-get install -y \
    wget build-essential cmake pkg-config git \
    libjpeg-dev libtiff5-dev libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev libxvidcore-dev libx264-dev \
    libgtk2.0-dev libgtk-3-dev \
    libatlas-base-dev gfortran \
    udev \
    libtbb2 libtbb-dev \
    libpng-dev libdc1394-22-dev \
    ffmpeg libsm6 libxext6 libgl1-mesa-glx \
    qt5-qmake qtbase5-dev qtbase5-dev-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /depthai

# Copy requirements first to leverage docker cache
COPY requirements.txt requirements-optional.txt /depthai/

# Install Python dependencies
RUN pip install -U pip && \
    pip install --prefer-binary -r requirements.txt && \
    pip install --prefer-binary -r requirements-optional.txt

# Copy the rest of the application
COPY . /depthai

# Set the default command to run the demo
CMD ["python3", "depthai_demo.py"]
