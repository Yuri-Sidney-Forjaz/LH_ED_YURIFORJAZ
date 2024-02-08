# Base image selection: Opt for an Airflow image with Python support tailored for the project's requirements
FROM apache/airflow:2.1.0

# Establish build arguments to enable customization during the Docker image build process
ARG EMBULK_VERSION=0.9.23

# Execute the installation of project-specific dependencies and Embulk
USER root
RUN apt-get update && apt-get install -y \
    default-jre \
    && rm -rf /var/lib/apt/lists/* # Clean up the apt cache to reduce image size

# Perform the Embulk installation
RUN curl -L https://dl.embulk.org/embulk-${EMBULK_VERSION}.jar -o /bin/embulk \
    && chmod +x /bin/embulk # Make Embulk executable

# Revert to the airflow user to mitigate permission issues
USER airflow

# Transfer Embulk configurations and essential scripts into the container
COPY ./embulk_config /opt/airflow/embulk_config

# (Optional) Transfer additional project files such as Python scripts, DAGs, etc., into the container
COPY ./dags /opt/airflow/dags
COPY ./plugins /opt/airflow/plugins

# Set the working directory for container operations
WORKDIR /opt/airflow

# Establish a default command to keep the container running
CMD ["tail", "-f", "/dev/null"]